"""Review Editor — dựng theo edit.json cho từng tỷ lệ: hình (cắt/crop/30fps/b-roll) → tiếng (lời + hiện trường + nhạc) → lớp chữ → kiểm tra.

File gốc không bị sửa; mọi đoạn đều dựng lại từ nguồn theo timecode → sửa một cảnh chỉ cần sửa edit.json rồi dựng lại.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np

from .edit import FORMATS, crop_at, crop_box, crop_for, duration, layout, load, media, validate


def _ff(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"ffmpeg lỗi: {r.stderr[-400:]}")
    return r


def _tone(m: dict, lift, warm=0.0) -> str:
    """ngược sáng: nâng vùng tối/trung vừa phải (đường cong mềm), KHÔNG tăng bão hoà → giữ màu da, bao bì; vùng cháy không cứu được.
    warm (ẩm thực): ấm nhẹ trung thực ở trung/sáng — không đổi màu món. Mỹ phẩm: lift=0, warm=0 (khoá màu)."""
    if lift is None:
        lift = 0.08 if m.get("backlit") else 0.0
    f = ""
    if lift > 0:
        f += f"curves=master='0/0 0.25/{0.25 + lift:.3f} 0.5/{0.5 + lift * 0.75:.3f} 0.75/{0.75 + lift * 0.35:.3f} 1/1',"
    if warm and warm > 0:
        f += f"colorbalance=rm={warm:.3f}:bm={-warm:.3f}:rh={warm * 0.6:.3f}:bh={-warm * 0.6:.3f},"
    return f


def _vf(m: dict, fmt: str, c: dict, fps: int, c2: dict | None = None, dur: float = 0.0, lift=None, warm=0.0) -> str:
    W, H = FORMATS[fmt]
    tm = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,"
          if m.get("hdr") else "") + _tone(m, lift, warm)
    if c.get("fit") == "blur":   # nguồn không hợp tỷ lệ và không có cảnh thay thế → khung chứa footage có chủ đích (nền mờ cùng hình)
        return (f"{tm}split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.08[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={fps},setsar=1,format=yuv420p")
    x, y, w, h, _ = crop_box(m["w"], m["h"], fmt, c)
    if c2 and c2 != c and dur > 0:   # reframe: chuyển mượt (smoothstep) từ khung c sang c2 trong dur giây — phóng theo từng khung
        x2, y2, w2, h2, _ = crop_box(m["w"], m["h"], fmt, c2)
        u = f"(3*pow(clip(t/{dur:.4f},0,1),2)-2*pow(clip(t/{dur:.4f},0,1),3))"
        cw = f"({w}+({w2}-{w})*{u})"
        S = f"({W}/{cw})"
        return (f"{tm}scale=w='2*trunc(iw*{S}/2)':h='2*trunc(ih*{S}/2)':eval=frame:flags=lanczos,"
                f"crop={W}:{H}:x='({x}+({x2}-{x})*{u})*{S}':y='({y}+({y2}-{y})*{u})*{S}',fps={fps},setsar=1,format=yuv420p")
    return f"{tm}crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos,fps={fps},setsar=1,format=yuv420p"


def _pieces(edit: dict, pdir, fmt: str) -> list[dict]:
    """hình: mỗi đoạn tách thành các khúc (người nói / cutaway thay hình); tiếng không đổi (cutaway giữ lời đang nói)."""
    M = media(pdir)
    out = []
    for s in layout(edit):
        m = M[s["src"]]
        cuts = sorted((c for c in s.get("cutaways", []) if c.get("kind", "full") == "full"), key=lambda c: c["at"])
        t = 0.0
        base = crop_for(s, m, fmt)
        keys = sorted(((s.get("reframe") or {}).get(fmt) or []), key=lambda k: k["at"])
        marks = sorted({0.0, s["dur"]} | {k["at"] for k in keys} | {min(k["at"] + k.get("dur", 0.6), s["dur"]) for k in keys})
        lift = (s.get("tone") or {}).get("lift")
        warm = (s.get("tone") or {}).get("warm", 0.0)
        for c in cuts + [None]:
            end = c["at"] if c else s["dur"]
            # chia khúc người nói theo mốc reframe → khúc tĩnh hoặc khúc chuyển khung
            cuts_t = [t] + [x for x in marks if t + 1e-3 < x < end - 1e-3] + [end]
            for a, b in zip(cuts_t, cuts_t[1:]):
                if b - a <= 1 / 60:
                    continue
                ca, cb = crop_at(pdir, s, m, fmt, a + 1e-4, base), crop_at(pdir, s, m, fmt, b - 1e-4, base)
                moving = any(abs(ca[k] - cb[k]) > 1e-3 for k in ("cx", "cy", "zoom")) and ca.get("fit") != "blur"
                out.append({"m": m, "in": s["in"] + a, "dur": b - a, "crop": ca, "crop2": cb if moving else None, "seg": s["id"], "lift": lift, "warm": warm})
            if c:
                mc = M[c["src"]]
                cc = (c.get("crop") or {}).get(fmt) or crop_for({"in": c.get("in", 0), "out": c.get("in", 0) + c["dur"]}, mc, fmt, role="broll")
                out.append({"m": mc, "in": float(c.get("in", 0)), "dur": c["dur"], "crop": {"fit": "crop", "zoom": 1.0, **cc}, "seg": s["id"],
                            "cutaway": True, "lift": (c.get("tone") or {}).get("lift"), "warm": (c.get("tone") or {}).get("warm", 0.0)})
                t = c["at"] + c["dur"]
    return out


def _video(edit, pdir, fmt, work: Path, progress) -> Path:
    fps = int(edit.get("fps", 30))
    parts = []
    ps = _pieces(edit, pdir, fmt)
    for i, p in enumerate(ps):
        f = work / f"p{i:03d}.mp4"
        nf = max(1, round(p["dur"] * fps))
        _ff(["ffmpeg", "-v", "error", "-y", "-ss", f"{p['in']:.3f}", "-i", p["m"]["path"], "-frames:v", str(nf), "-an",
             "-filter_complex", f"[0:v]{_vf(p['m'], fmt, p['crop'], fps, p.get('crop2'), p['dur'], p.get('lift'), p.get('warm', 0.0))}[o]", "-map", "[o]", "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "16", "-r", str(fps), str(f)])
        parts.append(f)
        progress(f"build frame {i + 1}/{len(ps)}")
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    base = work / "base.mp4"
    _ff(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(base)])
    # PiP: đè hình nhỏ bo góc (góc trên phải) trong khoảng của nó
    pips = [(s, c) for s in layout(edit) for c in s.get("cutaways", []) if c.get("kind") == "pip"]
    if pips:
        W, H = FORMATS[fmt]
        M = media(pdir)
        cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(base)]
        flt, last = [], "[0:v]"
        for k, (s, c) in enumerate(pips, 1):
            mc = M[c["src"]]
            cmd += ["-ss", f"{float(c.get('in', 0)):.3f}", "-t", f"{c['dur']:.3f}", "-i", mc["path"]]
            bw, bh = (int(W * 0.42), int(H * 0.3)) if fmt == "9x16" else (int(W * 0.3), int(H * 0.56))   # ô PiP: giới hạn cả rộng lẫn cao
            t0 = s["t0"] + c["at"]
            flt.append(f"[{k}:v]fps={fps},scale={bw}:{bh}:force_original_aspect_ratio=decrease,scale=trunc(iw/2)*2:trunc(ih/2)*2,"
                       f"pad=iw+12:ih+12:6:6:white,setpts=PTS-STARTPTS+{t0:.3f}/TB[q{k}]")
            flt.append(f"{last}[q{k}]overlay=W-w-{int(W * 0.05)}:{int(H * 0.12)}:enable='between(t,{t0:.3f},{t0 + c['dur']:.3f})':eof_action=pass[v{k}]")
            last = f"[v{k}]"
        out = work / "base_pip.mp4"
        _ff(cmd + ["-filter_complex", ";".join(flt), "-map", last, "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(out)])
        base = out
    return base


def _audio(edit, pdir, work: Path) -> Path:
    """lời (giữ trọn qua cutaway) + J/L-cut + tiếng hiện trường + nhạc tự giảm khi có lời → chuẩn −16 LUFS, đỉnh ≤ −1.5 dB."""
    M = media(pdir)
    inputs, flt, labs = [], [], []
    k = 0
    segs = layout(edit)
    for i, s in enumerate(segs):
        m = M[s["src"]]
        if not m.get("has_audio") or s.get("audio") == "mute":
            continue
        j = float(s.get("j", 0))
        l_next = float(segs[i + 1].get("l", 0)) if i + 1 < len(segs) else 0.0
        a, b = max(float(s["in"]) - j, 0), float(s["out"]) + l_next
        start = s["t0"] - (float(s["in"]) - a)
        gain = 0.0 if s.get("audio", "voice") == "voice" and s.get("role", "talk") == "talk" else float(s.get("nat_db", -14))
        inputs += ["-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", m["path"]]
        flt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.015,afade=t=out:st={max(b - a - 0.02, 0):.3f}:d=0.02,"
                   f"volume={gain}dB,adelay={int(max(start, 0) * 1000)}|{int(max(start, 0) * 1000)}[a{k}]")
        labs.append(f"[a{k}]"); k += 1
        for c in s.get("cutaways", []):
            mc = M[c["src"]]
            if c.get("nat_db") is None or not mc.get("has_audio"):
                continue
            st = s["t0"] + c["at"]
            inputs += ["-ss", f"{float(c.get('in', 0)):.3f}", "-t", f"{c['dur']:.3f}", "-i", mc["path"]]
            flt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.08,afade=t=out:st={max(c['dur'] - 0.15, 0):.3f}:d=0.15,"
                       f"volume={float(c['nat_db'])}dB,adelay={int(st * 1000)}|{int(st * 1000)}[a{k}]")
            labs.append(f"[a{k}]"); k += 1
    T = duration(edit)
    out = work / "mix.wav"
    if not labs:
        _ff(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-t", f"{T:.3f}", "-i", "anullsrc=r=48000:cl=stereo", str(out)])
        return out
    flt.append(f"{''.join(labs)}amix=inputs={len(labs)}:normalize=0:duration=longest,highpass=f=70,"
               f"afftdn=nr=8:nf=-35,apad,atrim=0:{T:.3f}[voice0]")
    from .sfx import inputs as sfx_inputs        # SFX dùng chung kho Voice to Motion — trộn SAU khử nhiễu giọng
    sx = sfx_inputs(edit)
    labs2 = []
    for e in sx:
        inputs += ["-i", e["path"]]
        ms = int(e["start"] * 1000)
        flt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,afade=t=in:d=0.004,volume={e['gain_db']}dB,adelay={ms}|{ms}[s{k}]")
        labs2.append(f"[s{k}]"); k += 1
    if labs2:
        flt.append(f"[voice0]{''.join(labs2)}amix=inputs={len(labs2) + 1}:normalize=0:duration=first[voice]")
    else:
        flt.append("[voice0]anull[voice]")
    mu = edit.get("music")
    if mu and Path(pdir, mu["src"]).exists():
        inputs += ["-stream_loop", "-1", "-i", str(Path(pdir, mu["src"]))]
        flt.append(f"[{k}:a]aresample=48000,aformat=channel_layouts=stereo,volume={float(mu.get('gain_db', -20))}dB,atrim=0:{T:.3f}[mu]")
        flt.append("[voice]asplit[v1][v2]")
        flt.append("[mu][v2]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400[duck]")
        flt.append("[v1][duck]amix=inputs=2:normalize=0[mx]")
        last = "[mx]"
    else:
        last = "[voice]"
    flt.append(f"{last}loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]")
    _ff(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(flt), "-map", "[out]", "-ac", "2", str(out)])
    return out


def _composite(edit, pdir, fmt, base: Path, audio: Path, out: Path, progress) -> list:
    """đè lớp chữ RGBA lên hình + ghép tiếng → MP4 H.264/AAC."""
    from .graphics import Layer
    W, H = FORMATS[fmt]
    fps = int(edit.get("fps", 30))
    T = duration(edit)
    n = int(round(T * fps))
    L = Layer(edit, pdir, fmt)
    dec = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(base), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                            "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)],
                           stdin=subprocess.PIPE)
    from .edit import face_out
    samples, size = [], W * H * 3
    last = None
    try:
        for f in range(n):
            buf = dec.stdout.read(size)
            if len(buf) < size:
                buf = last if last is not None else bytes(size)
            last = buf
            t = f / fps
            fr = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
            g = L.rgba(t, (f - 1) / fps if f else None)
            if g is not None:
                a = g[..., 3:4]
                fr = (fr.astype(np.float32) / 255 * (1 - a) + g[..., :3] * a)
                fr = (np.clip(fr, 0, 1) * 255).astype(np.uint8)
                if f % 6 == 0:
                    samples.append((t, list(L.boxes), face_out(pdir, edit, fmt, t)))
            enc.stdin.write(np.ascontiguousarray(fr).tobytes())
            if f % 30 == 0:
                progress(f"finish frame {f}/{n}")
    finally:
        enc.stdin.close(); enc.wait(); dec.kill()
    if enc.returncode:
        raise RuntimeError("ffmpeg ghép lớp chữ lỗi")
    spots = [{"at": round(sp.at, 2), "dur": sp.d, "frames": int(sp.d * fps), "miss": sp.miss} for sp in L.spots]
    return samples, spots


def _sub_sync(out: Path, edit: dict, pdir, fmt: str = "9x16") -> tuple[list, list, int]:
    """phụ đề ↔ tiếng trên FILE XUẤT: mỗi cụm phụ đề bắt đầu phải có tiếng nói trong ±0,3s (năng lượng > nền lặng 12 dB)."""
    from .graphics import captions
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(out), "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    if a.size == 0:
        return ["không đọc được tiếng để kiểm phụ đề"], [], 0
    hop = 80                                                     # 10ms
    rms = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, mode="same")[::hop] + 1e-12)
    db = 20 * np.log10(rms)
    floor = float(np.percentile(db, 10))
    err, warn, n = [], [], 0
    for ph in captions(edit, pdir, fmt):
        t = ph[0]["t"]
        i0, i1 = max(int((t - 0.3) * 100), 0), int((t + 0.3) * 100)
        if i1 >= len(db):
            continue
        n += 1
        if float(db[i0:i1].max()) < floor + 12:
            warn.append(f"phụ đề “{' '.join(w['text'] for w in ph)[:30]}” ở {t:.2f}s: năng lượng tiếng thấp ±0,3s — CẦN NGHE kiểm đồng bộ "
                        "(đo năng lượng không chắc khi nền ồn/nói nhỏ; mốc phụ đề lấy từ máy chép lời)")
    return err, warn, n


def check_output(out: Path, edit: dict, fmt: str, samples, pdir=None, spots=None) -> dict:
    """kiểm file xuất thật: kích thước/fps/thời lượng, khung đen, đoạn lặng dài, độ to/đỉnh, chữ chồng/cắt khung."""
    W, H = FORMATS[fmt]
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out)],
                                  capture_output=True, text=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    num, den = map(int, v["r_frame_rate"].split("/"))
    dur = float(j["format"]["duration"])
    errors, warns = [], []
    if (v["width"], v["height"]) != (W, H): errors.append(f"kích thước {v['width']}x{v['height']} ≠ {W}x{H}")
    if abs(num / den - edit.get("fps", 30)) > 0.01: errors.append(f"fps {num / den:.2f} ≠ {edit.get('fps', 30)}")
    if abs(dur - duration(edit)) > 0.2: errors.append(f"thời lượng {dur:.2f}s ≠ bản dựng {duration(edit):.2f}s")
    if not a: errors.append("không có tiếng")
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(out), "-vf", "scale=160:-2,blackdetect=d=0.25:pix_th=0.08", "-af",
                        "silencedetect=n=-45dB:d=2.0,ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    import re
    for x, y in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r):
        errors.append(f"khung đen {float(x):.2f}–{float(y):.2f}s")
    for x in re.findall(r"silence_start: ([\d.]+)", r):
        warns.append(f"lặng > 2s từ {float(x):.1f}s")
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    peak = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    if peak and float(peak[-1]) > -0.5: errors.append(f"đỉnh âm {peak[-1]} dBFS (nguy cơ vỡ tiếng)")
    from ..v2m import qa as Q

    class _TL:   # QA chữ dùng chung của Voice to Motion (bỏ tương phản: nền là footage, chữ đã có viền)
        pass
    tl = _TL(); tl.W, tl.H = W, H; tl.safe = (60, 150, 1020, 1600) if fmt == "9x16" else (90, 70, 1830, 1000)
    for lv, msg in Q.frames(tl, [(t, b) for t, b, _ in samples]) if samples else []:
        if "tương phản" in msg:
            continue
        (errors if lv == "error" else warns).append(msg)
    sync_n = 0
    if pdir is not None and edit.get("subtitles", True):
        e2, w2, sync_n = _sub_sync(out, edit, pdir, fmt)
        errors += e2
        warns += w2
    # chữ nhấn / nhãn / thông tin không được chạm mặt + tóc
    hit = {}
    for t, boxes, face in samples:
        if not face:
            continue
        fx0, fy0, fx1, fy1 = face
        for b in boxes:
            bid = str(b.get("id") or "")
            if b.get("kind") != "text" or not bid.startswith(("emph", "labt", "infot")) or b["op"] < 0.5:
                continue
            x0, y0, x1, y1 = b["box"]
            ov = max(0, min(x1, fx1) - max(x0, fx0)) * max(0, min(y1, fy1) - max(y0, fy0))
            if ov > 0.08 * max((x1 - x0) * (y1 - y0), 1):
                hit.setdefault((bid, b.get("text", "")), []).append(t)
    for (bid, txt), ts in hit.items():
        (errors if len(ts) >= 2 else warns).append(f"chữ “{txt[:24]}” chạm mặt/tóc {ts[0]:.1f}–{ts[-1]:.1f}s")
    # spotlight theo đúng vật suốt thời gian hiện
    for sp in spots or []:
        if sp["frames"] and sp["miss"] > 0.15 * sp["frames"]:
            warns.append(f"spotlight {sp['at']}s: mất dấu vật {sp['miss']}/{sp['frames']} khung — đã tắt ở các khung đó")
    # điểm nối (từ audio nguồn): nghỉ / đầu-cuối hụt
    if pdir is not None:
        from .audiocut import junctions
        for j in junctions(edit, pdir):
            for lv, msg in j["flags"]:
                (errors if lv == "error" else warns).append(msg)
    # phụ đề đủ thời gian đọc
    if pdir is not None and edit.get("subtitles", True):
        from .graphics import captions
        phs = captions(edit, pdir, fmt)
        for k, ph in enumerate(phs):
            txt = " ".join(w["text"] for w in ph)
            nxt = phs[k + 1][0]["t"] if k + 1 < len(phs) else 1e9
            if min(nxt, ph[-1]["t_end"] + 1) - ph[0]["t"] < max(0.6, len(txt) / 20):
                warns.append(f"phụ đề “{txt[:28]}” ở {ph[0]['t']:.1f}s đổi nhanh ({min(nxt, ph[-1]['t_end'] + 1) - ph[0]['t']:.1f}s)")
    return {"format": fmt, "file": str(out), "w": v["width"], "subtitle_sync_checked": sync_n, "h": v["height"], "fps": round(num / den, 3), "duration": round(dur, 2),
            "lufs": float(lufs[-1]) if lufs else None, "peak_db": float(peak[-1]) if peak else None, "errors": errors, "warnings": warns,
            "ok": not errors, "listened": False,
            "note": "Âm thanh chỉ kiểm bằng số đo (độ to, đỉnh, đoạn lặng) — môi trường không nghe trực tiếp được."}


def render(pdir, fmts=None, progress=print) -> list[dict]:
    pdir = Path(pdir)
    edit = load(pdir)
    issues = validate(pdir, edit)
    errs = [m for s, m in issues if s == "error"]
    if errs:
        raise SystemExit("LỖI bản dựng — sửa edit.json trước khi dựng:\n- " + "\n- ".join(errs))
    fmts = list(fmts or edit.get("formats") or ["9x16", "16x9"])
    vs = sorted((d for d in (pdir / "review" / "versions").glob("v[0-9][0-9][0-9]")), key=lambda d: d.name) \
        if (pdir / "review" / "versions").exists() else []
    vdir = pdir / "review" / "versions" / f"v{(int(vs[-1].name[1:]) + 1) if vs else 1:03d}"
    vdir.mkdir(parents=True)
    shutil.copy2(pdir / "review" / "edit.json", vdir / "edit.json")
    work = vdir / "work"
    work.mkdir()
    audio = _audio(edit, pdir, work)
    res = []
    for fmt in fmts:
        t0 = time.time()
        wf = work / fmt
        wf.mkdir()
        base = _video(edit, pdir, fmt, wf, progress)
        out = vdir / f"review_{fmt}.mp4"
        samples, spots = _composite(edit, pdir, fmt, base, audio, out, progress)
        qa = check_output(out, edit, fmt, samples, pdir, spots)
        qa["spotlights"] = spots
        qa["warnings"] += [m for s, m in issues if s == "warn"]
        qa["render_s"] = round(time.time() - t0, 1)
        (vdir / f"qa_{fmt}.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
        shutil.copy2(out, pdir / f"{pdir.name}_{fmt}.mp4")
        res.append(qa)
        progress(json.dumps({k: qa[k] for k in ("format", "ok", "errors")}, ensure_ascii=False))
    shutil.rmtree(work, ignore_errors=True)
    return res
