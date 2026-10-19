"""Lệnh Voice to Motion.

  python -m thagent.v2m broll  <dự-án> <url> v_ten.mp4 [nguồn]  tải video b-roll (ưu tiên Pinterest, không được thì Pexels)
  python -m thagent.v2m icons  <từ khóa…>                    tra tên icon trong kho của app (tiếng Anh/Việt)
  python -m thagent.v2m init   <voice|video> <thư-mục-dự-án>   kiểm tra file, chép voice, chép lời → transcript.json
  python -m thagent.v2m clean  <dự-án> [--no-denoise]           cắt vấp/lắp bắp/từ đệm/khoảng lặng (như Talking Head) → voice_clean.wav
  python -m thagent.v2m restore <dự-án>                          bỏ cắt, dùng voice gốc
  python -m thagent.v2m speed  <dự-án> 1.1                       tốc độ xuất 0.8–1.5 (giọng giữ cao độ)
  python -m thagent.v2m words  <dự-án> [t0 t1]                   transcript kèm giây
  python -m thagent.v2m check  <dự-án>                            kiểm tra timeline.json trước khi dựng
  python -m thagent.v2m stills <dự-án> t1 t2 …                    ảnh tĩnh tại các giây → stills.jpg (không dựng video)
  python -m thagent.v2m render <dự-án> [9x16|16x9|both]           mặc định: cả dọc lẫn ngang (song song) nếu có đủ timeline_9x16/16x9
                                                                   → versions/vNNN/video_<fmt>.mp4 + <id>_<fmt>.mp4
  python -m thagent.v2m revise <dự-án> '<json>'                   sửa nhanh rồi dựng phiên bản mới:
        {"op":"text_scale","t0":15,"t1":20,"k":1.15}   chữ hiện trong khoảng giây ×k
        {"op":"sfx_gain","t0":0,"t1":999,"db":-4}       tăng/giảm SFX trong khoảng
"""
from __future__ import annotations

import json
import os
import math
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from . import audio as A, draw as D, qa as Q, render as R

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}
SAFE = {"x0": 80, "x1": 1000, "y0": 160, "y1": 1560}   # vùng ưu tiên cho nội dung quan trọng (dọc 1080×1920)


def _dur(path) -> float:
    return float(A.probe(str(path))["format"]["duration"])


def init(src, pdir, progress=print):
    src, pdir = Path(src).expanduser(), Path(pdir).expanduser()
    info = A.probe(str(src))
    auds = [s for s in info.get("streams", []) if s["codec_type"] == "audio"]
    if not auds:
        raise SystemExit(f"LỖI: {src.name} không có tiếng")
    pdir.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() in AUDIO_EXT:
        voice = pdir / f"voice{src.suffix.lower()}"
        shutil.copy2(src, voice)                       # giữ nguyên bản gốc
    else:                                              # video: chỉ lấy tiếng, không nén lại
        voice = pdir / "voice.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-c:a", "pcm_s16le", str(voice)], check=True)
    dur = _dur(voice)
    wav16 = pdir / "work_asr.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(voice), "-ac", "1", "-ar", "16000", str(wav16)], check=True)
    from ..transcribe import transcribe
    words, sents = transcribe(str(wav16), progress=progress)
    wav16.unlink(missing_ok=True)
    tr = {"voice": voice.name, "duration_s": round(dur, 3), "channels": auds[0].get("channels"),
          "codec": auds[0].get("codec_name"), "sample_rate": auds[0].get("sample_rate"),
          "words": [{"i": i, "text": w.text, "start": w.source_start, "end": w.source_end, "conf": w.confidence}
                    for i, w in enumerate(words)],
          "sentences": [{"text": s.text, "start": s.source_start, "end": s.source_end} for s in sents]}
    (pdir / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"project": str(pdir), "voice": voice.name, "duration_s": round(dur, 3), "words": len(words),
                      "codec": tr["codec"], "channels": tr["channels"]}, ensure_ascii=False))


def words(pdir, t0=0, t1=1e9):
    tr = json.loads((Path(pdir) / "transcript.json").read_text(encoding="utf-8"))
    print(" ".join(f"{w['text']}@{w['start']:.2f}" for w in tr["words"] if float(t0) <= w["start"] <= float(t1)))


FMT = {"value": None}     # định dạng đang xử lý (render/check/stills theo --fmt)


def _tl_path(pdir: Path, fmt: str | None = None) -> Path:
    fmt = fmt or FMT["value"]
    if fmt:
        q = pdir / f"timeline_{fmt}.json"
        if q.exists():
            return q
        base = pdir / "timeline.json"
        if base.exists():
            d = json.loads(base.read_text(encoding="utf-8"))
            cv = d.get("canvas", {})
            from .layout import fmt_of
            if fmt_of(int(cv.get("width", 1080)), int(cv.get("height", 1920))) == fmt:
                return base
        raise SystemExit(f"LỖI: chưa có timeline_{fmt}.json — bố cục {fmt} phải được thiết kế riêng, không suy ra từ bản kia")
    return pdir / "timeline.json"


def _timeline(pdir: Path) -> R.Timeline:
    return R.load(_tl_path(pdir))


def validate(pdir: Path) -> list[tuple[str, str]]:
    """lỗi chặn dựng (error) + cảnh báo (warn)."""
    out = []
    try:
        tl = _timeline(pdir)
    except Exception as e:
        return [("error", f"timeline.json không hợp lệ: {e}")]
    d = tl.d
    vf = pdir / d.get("audio", {}).get("path", "")
    if not vf.is_file():
        out.append(("error", f"không có file voice {vf.name}"))
    else:
        vd = _dur(vf)
        if abs(vd - tl.duration) > 0.6:
            out.append(("warn", f"audio.duration_s {tl.duration:.2f}s khác độ dài voice thật {vd:.2f}s"))
    prev = 0.0
    for sc in tl.scenes:
        if sc["end_s"] <= sc["start_s"]:
            out.append(("error", f"{sc['id']}: end_s ≤ start_s"))
        if sc["start_s"] > prev + 0.05:
            out.append(("error", f"hở khoảng {prev:.2f}→{sc['start_s']:.2f}s không có cảnh"))
        prev = max(prev, sc["end_s"])
        if sc["end_s"] > tl.duration + 0.05:
            out.append(("error", f"{sc['id']}: vượt thời lượng voice"))
        for e in sc.get("audio_events", []):
            role = e.get("role") or (e.get("sfx", "")[5:] if str(e.get("sfx", "")).startswith("role:") else None)
            if role:
                from .sfxkit import roles
                if role not in roles():
                    out.append(("error", f"{sc['id']}: vai trò SFX “{role}” không có trong kho (có: {', '.join(roles())})"))
                continue
            try:
                A.sfx_path(e["sfx"])
            except FileNotFoundError as ex:
                out.append(("error", f"{sc['id']}: {ex}"))
    if prev < tl.duration - 0.05:
        out.append(("error", f"cảnh cuối dừng ở {prev:.2f}s, voice dài {tl.duration:.2f}s"))
    for o in tl.objs.values():
        if o["type"] == "image":
            if not Path(tl.path(o["src"])).is_file():
                out.append(("error", f"{o['id']}: không có ảnh {o['src']}"))
            if not o.get("source") and not o.get("label_only_concept"):
                out.append(("warn", f"{o['id']}: ảnh chưa ghi nguồn"))
        if o["type"] == "icon" and not D.icon_exists(o["name"]):
            from .icons import suggest
            sg = suggest(o["name"])
            out.append(("error", f"{o['id']}: icon “{o['name']}” không có trong kho"
                        + (f" — dùng: {', '.join(sg)}" if sg else "") + " (tra: python -m thagent.v2m icons <từ khóa>)"))
        if o["type"] in ("line",):
            for ref in ([o.get("from"), o.get("to")] + list(o.get("points") or [])):
                if isinstance(ref, str) and ref not in tl.objs:
                    out.append(("error", f"{o['id']}: nối tới object không có {ref}"))
        if o.get("parent") and o["parent"] not in tl.objs:
            out.append(("error", f"{o['id']}: parent {o['parent']} không có"))
        if o["type"] == "video" and not Path(tl.path(o["src"])).is_file():
            out.append(("error", f"{o['id']}: không có clip {o['src']}"))
        if o["type"] not in ("text", "rect", "circle", "image", "video", "icon", "line", "list", "counter", "progress", "bars", "quote", "map", "region", "geo", "geoline", "routelabel", "callout", "figure", "pulse", "flow", "stack", "halo", "hf"):
            out.append(("error", f"{o['id']}: loại {o['type']} chưa hỗ trợ"))
        if o["type"] == "hf":                     # lớp HyperFrames (công cụ dựng chung) — spec hợp lệ + công cụ sẵn sàng
            from ..capabilities import status
            from ..hyper import spec as HS
            st = status("hyperframes")
            if not st.get("ok"):
                out.append(("error", f"{o['id']}: HyperFrames chưa sẵn sàng ({'; '.join(st.get('problems', []))}) — object hf bị chặn"))
            else:
                for lv, m in HS.validate(HS.normalize(R.hf_spec(tl, o))):
                    out.append((lv, f"{o['id']} (HyperFrames): {m}"))
    return out


def safe_area(tl: R.Timeline) -> list[str]:
    """chữ ra ngoài vùng an toàn tại lúc đọc (giữa thời gian hiện, camera đứng)."""
    warns = []
    Rr = R.Renderer(tl)
    for oid, o in tl.objs.items():
        if o["type"] not in ("text", "counter"):
            continue
        v0, v1 = o["_vis"]
        t = min((v0 + v1) / 2, tl.duration - 0.01)
        p = Rr.world(oid, t)
        cam = R.camera_at(tl, t)
        sx, sy = (p.get("x", tl.W / 2), p.get("y", tl.H / 2)) if p.get("space") == "screen" else R.world_to_screen(tl, cam, p.get("x", tl.W / 2), p.get("y", tl.H / 2))
        sc = p["scale"] * (1 if (p.get("space") == "screen" or p.get("fixed")) else cam[2])
        txt = p.get("text") or (p.get("prefix", "") + R._fmt_num(float(p.get("value", 0)), int(p.get("decimals", 0))) + p.get("suffix", ""))
        _, bw, bh = D.text_layout(txt.upper() if p.get("upper") else txt, p.get("font", "display"),
                                  int(p.get("size", 64)), float(p.get("max_w", 0)), "center", float(p.get("line_h", 1.15)), 0.0)
        anc = p.get("anchor", "center")
        x0 = sx - (0 if "left" in anc else bw * sc if "right" in anc else bw * sc / 2)
        y0 = sy - (0 if anc.startswith("top") else bh * sc / 2)
        x1, y1 = x0 + bw * sc, y0 + bh * sc
        if x0 < tl.safe[0] - 2 or x1 > tl.safe[2] + 2 or y0 < tl.safe[1] - 2 or y1 > tl.safe[3] + 2:
            warns.append(f"{oid} “{txt[:24]}” @ {t:.1f}s ra ngoài vùng an toàn ({int(x0)},{int(y0)})–({int(x1)},{int(y1)})")
        if bh * sc < 26 and p.get("font") not in ("medium", "body"):
            warns.append(f"{oid} chữ quá nhỏ trên điện thoại ({bh * sc:.0f}px)")
    return warns


def sheet(tl: R.Timeline, times: list[float], out: Path, cols=6):
    tiles = []
    for t in times:
        im = R.still(tl, min(max(t, 0), tl.duration - 1 / tl.fps))
        tw, th_ = (270, 480) if tl.H >= tl.W else (480, 270)
        im = cv2.resize(im, (tw, th_), interpolation=cv2.INTER_AREA)
        im = cv2.cvtColor(im, cv2.COLOR_RGB2BGR)
        cv2.putText(im, f"{t:.2f}s", (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        tiles.append(im)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
    return out


def stills(pdir, *ts):
    pdir = Path(pdir)
    FMT["value"] = next((f for f in ts if f in ("9x16", "16x9")), None)
    ts = [t for t in ts if t not in ("9x16", "16x9")]
    tl = _timeline(pdir)
    if not ts:
        ts = []
        for sc in tl.scenes:
            ts += [sc["start_s"] + 0.35, (sc["start_s"] + sc["end_s"]) / 2, sc["end_s"] - 0.05]
    print(sheet(tl, [float(t) for t in ts], pdir / f"stills{'_' + FMT['value'] if FMT['value'] else ''}.jpg"))


def _next_version(pdir: Path) -> Path:
    vs = sorted(int(p.name[1:]) for p in (pdir / "versions").glob("v[0-9][0-9][0-9]") if p.is_dir())
    v = (vs[-1] + 1) if vs else 1
    d = pdir / "versions" / f"v{v:03d}"
    d.mkdir(parents=True)
    return d


def render(pdir, *fmts, progress=print):
    """render <dự-án> [9x16|16x9|both] — mặc định: định dạng của timeline.json (dọc nếu không ghi).
    Mỗi định dạng dùng timeline bố cục riêng (timeline_<fmt>.json), dựng và kiểm tra RIÊNG."""
    pdir = Path(pdir)
    want = [f for f in fmts if not str(f).startswith("-")]
    have = [f for f in ("9x16", "16x9") if (pdir / f"timeline_{f}.json").exists()]
    if not want:   # mặc định: dự án có bố cục cả hai tỷ lệ → xuất cả hai; dự án cũ chỉ có timeline.json → như trước
        want = ["both"] if len(have) == 2 else []
    if "both" in want:
        want = ["9x16", "16x9"]
    if not want:
        return [_render_one(pdir, None, progress)]
    vdir = _next_version(pdir)
    if len(want) == 2 and "--serial" not in fmts:
        # dựng song song: bản ngang ở tiến trình con, bản dọc ở tiến trình này → tổng thời gian ≈ một bản
        import subprocess as sp
        py = sys.executable
        if getattr(sys, "frozen", False):   # app đóng gói: gọi runtime phụ ccut-py (gọi chính app sẽ mở thêm cửa sổ)
            py = str(Path(sys.executable).with_name("ccut-py.exe" if os.name == "nt" else "ccut-py"))
        child = sp.Popen([py, "-u", "-m", "thagent.v2m", "_render_one", str(pdir), want[1], str(vdir)],
                         stdout=open(vdir / f"render_{want[1]}.log", "w"), stderr=sp.STDOUT)
        res = [_render_one(pdir, want[0], progress, vdir)]
        if child.wait() != 0:
            raise SystemExit(f"bản {want[1]} dựng lỗi — xem {vdir / f'render_{want[1]}.log'}")
        qf = vdir / f"qa_{want[1]}.json"
        res.append((vdir / f"video_{want[1]}.mp4", json.loads(qf.read_text(encoding="utf-8"))))
        print(json.dumps({"video": str(vdir / f"video_{want[1]}.mp4"), "format": want[1], "qa": res[1][1]}, ensure_ascii=False, indent=1))
        return res
    return [_render_one(pdir, f, progress, vdir) for f in want]


def _render_one_cli(pdir, fmt, vdir):
    _render_one(Path(pdir), fmt, print, Path(vdir))


def _render_one(pdir, fmt, progress=print, vdir=None):
    FMT["value"] = fmt
    issues = validate(pdir)
    errs = [m for s, m in issues if s == "error"]
    if errs:
        raise SystemExit(f"LỖI timeline {fmt or ''} — chưa dựng:\n- " + "\n- ".join(errs))
    tl = _timeline(pdir)
    st = Q.static(tl)
    if any(lv == "error" for lv, _ in st):
        raise SystemExit(f"LỖI QA tĩnh {fmt or ''} — sửa timeline trước khi dựng:\n- " + "\n- ".join(m for lv, m in st if lv == "error"))
    issues += st
    vdir = vdir or _next_version(pdir)
    sfx = f"_{fmt}" if fmt else ""
    t0 = time.time()
    shutil.copy2(_tl_path(pdir), vdir / f"timeline{sfx}.json")
    silent = vdir / f"video_noaudio{sfx}.mp4"
    stat = R.render_video(tl, silent, progress)
    voice = str(pdir / tl.d["audio"]["path"])
    rep = A.mix(tl, voice, vdir / f"mix{sfx}.m4a", tl.d.get("music"))
    final = vdir / f"video{sfx}.mp4"
    A.mux(silent, vdir / f"mix{sfx}.m4a", final, tl.duration)
    sp = float(tl.d.get("speed") or (json.loads((pdir / "speed.json").read_text())["speed"] if (pdir / "speed.json").exists() else 1.0))
    if abs(sp - 1) > 0.005:   # tăng/giảm tốc như Talking Head: hình + tiếng cùng lúc, giọng giữ cao độ
        from ..render import change_speed
        change_speed(str(final), sp, tl.fps)
    silent.unlink(missing_ok=True)
    (vdir / f"mix{sfx}.m4a").unlink(missing_ok=True)
    qa = check_output(tl, final, voice, stat, rep, sp)
    qa["format"] = tl.fmt
    qa["speed"] = sp
    qa["warnings"] += [m for s, m in issues if s == "warn"]
    fr = Q.frames(tl, stat["samples"]) + Q.determinism(tl)
    qa["errors"] += [m for lv, m in fr if lv == "error"]
    qa["warnings"] += [m for lv, m in fr if lv == "warn"]
    qa["ok"] = not qa["errors"]
    qa["status"] = "đạt kiểm tra tự động" if qa["ok"] else "CHƯA ĐẠT — còn lỗi chặn bàn giao"
    qa["render_s"] = round(time.time() - t0, 1)
    times = []
    for sc in tl.scenes:
        times += [sc["start_s"] + 0.35, sc["end_s"] - 0.05]
    sheet(tl, times, vdir / f"sheet{sfx}.jpg")
    (vdir / f"qa{sfx}.json").write_text(json.dumps(qa, ensure_ascii=False, indent=1), encoding="utf-8")
    if fmt:   # bản bàn giao có hậu tố định dạng
        shutil.copy2(final, pdir / f"{tl.d.get('project_id', pdir.name)}_{fmt}.mp4")
    print(json.dumps({"video": str(final), "format": tl.fmt, "qa": qa}, ensure_ascii=False, indent=1))
    return final, qa


def check_output(tl, final: Path, voice: str, stat: dict, mixrep: dict, sp: float = 1.0) -> dict:
    info = A.probe(str(final))
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    fd = float(info["format"]["duration"]) * sp      # quy về thời gian voice (video đã đổi tốc độ)
    vd = _dur(voice)
    errors, warns = [], []
    if not v or v.get("codec_name") != "h264":
        errors.append("thiếu hình H.264")
    elif (int(v["width"]), int(v["height"])) != (tl.W, tl.H):
        errors.append(f"kích thước {v['width']}×{v['height']} ≠ {tl.W}×{tl.H}")
    from fractions import Fraction
    if v and abs(float(Fraction(v.get("r_frame_rate", "0/1"))) - tl.fps) > 0.01:
        errors.append(f"fps {v['r_frame_rate']} ≠ {tl.fps}")
    if not a or a.get("codec_name") != "aac":
        errors.append("thiếu tiếng AAC")
    if fd + 0.1 < vd:
        errors.append(f"video {fd:.2f}s ngắn hơn voice {vd:.2f}s — mất lời cuối")
    elif abs(fd - tl.duration) > 0.1:
        warns.append(f"thời lượng video {fd:.2f}s lệch timeline {tl.duration:.2f}s")
    if stat["max_still_s"] > 4:   # khoảng dừng có chủ đích được phép; quá 4s mới đáng ngờ
        warns.append(f"hình đứng yên tới {stat['max_still_s']}s (bắt đầu ~{stat['still_from'][:4]}s) — kiểm tra có chủ đích không")
    if mixrep["peak_db"] > -1:
        warns.append(f"đỉnh âm {mixrep['peak_db']} dBFS — đã chặn đỉnh (limiter), voice gốc có thể bị nén nhẹ ở đỉnh")
    return {"ok": not errors, "errors": errors, "warnings": warns, "duration_s": round(fd, 3), "voice_s": round(vd, 3),
            "audio": mixrep, "frames": stat["frames"], "max_still_s": stat["max_still_s"],
            "limits": ["Không nghe trực tiếp được âm thanh: chỉ đo đỉnh/độ dài, không đánh giá cảm giác mix."]}


def check(pdir, *flags):
    """kiểm tra trước khi dựng. --deep: dựng frame mẫu mỗi 0,2s (không mã hoá) để bắt chồng chữ/cắt khung trong lúc animate.
    Thêm 9x16 / 16x9 để kiểm bố cục của định dạng đó."""
    pdir = Path(pdir)
    FMT["value"] = next((f for f in flags if f in ("9x16", "16x9")), None)
    issues = validate(pdir)
    if not any(s == "error" for s, _ in issues):
        tl = _timeline(pdir)
        issues += Q.static(tl)
        if "--deep" in flags:
            issues += Q.frames(tl, Q.scan(tl, 0.2, print)) + Q.determinism(tl)
    for s, m in issues:
        print(f"[{s}] {m}")
    print(f"{sum(s == 'error' for s, _ in issues)} lỗi, {sum(s == 'warn' for s, _ in issues)} cảnh báo")


def revise(pdir, spec):
    pdir = Path(pdir)
    tlj = pdir / "timeline.json"
    d = json.loads(tlj.read_text(encoding="utf-8"))
    ops = json.loads(spec)
    ops = ops if isinstance(ops, list) else [ops]
    changed = 0
    for op in ops:
        t0, t1 = float(op.get("t0", 0)), float(op.get("t1", 1e9))
        for sc in d["scenes"]:
            if op["op"] == "text_scale":
                evs = {e["object_id"]: e for e in sc.get("events", []) if e["action"] == "reveal"}
                for o in sc.get("objects", []):
                    if o["type"] in ("text", "counter", "list", "quote"):
                        ts = evs[o["id"]]["start_s"] if o["id"] in evs else sc["start_s"]
                        te = sc["end_s"]
                        if ts < t1 and te > t0:
                            o["size"] = round(float(o.get("size", 64)) * float(op["k"]), 1)
                            changed += 1
            elif op["op"] == "sfx_gain":
                for e in sc.get("audio_events", []):
                    if t0 <= float(e["t"]) <= t1:
                        e["gain_db"] = round(float(e.get("gain_db", -12)) + float(op["db"]), 1)
                        changed += 1
            else:
                raise SystemExit(f"op chưa hỗ trợ: {op['op']}")
    d["version"] = int(d.get("version", 1)) + 1
    tlj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"đã sửa {changed} mục → dựng phiên bản mới")
    render(pdir)


def clean(pdir, *flags):
    """cắt vấp, lắp bắp, từ đệm, khoảng lặng thừa (bộ Cắt sạch của Talking Head) → voice_clean.wav + transcript dời mốc."""
    from .voiceprep import clean as _clean
    r = _clean(Path(pdir), denoise="--no-denoise" not in flags)
    print(json.dumps({k: r[k] for k in ("source_s", "clean_s", "removed_s", "denoise")}, ensure_ascii=False))


def restore(pdir):
    """dùng lại voice + transcript gốc (không cắt)."""
    from .voiceprep import restore as _restore
    _restore(Path(pdir))
    print("đã dùng lại voice gốc")


def speed(pdir, v):
    """tốc độ cả video lúc xuất (0.8–1.5; 1 = gốc), giọng giữ cao độ; chữ/hình/âm thanh tăng cùng nhau."""
    pdir = Path(pdir)
    sp = min(1.5, max(0.8, float(v)))
    n = 0
    for f in [pdir / "timeline.json", pdir / "timeline_9x16.json", pdir / "timeline_16x9.json"]:
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            d["speed"] = sp
            f.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            n += 1
    (pdir / "speed.json").write_text(json.dumps({"speed": sp}), encoding="utf-8")   # builder đọc lại khi viết timeline mới
    print(f"tốc độ xuất ×{sp:g} ({n} timeline) — áp lúc xuất, không cần đổi timing chữ/hình")


def icons(*q):
    """icons <từ khóa…> — tra tên icon trong kho của app (tiếng Anh hoặc tiếng Việt)."""
    from .icons import search
    r = search(*q)
    print("\n".join(r) if r else "không thấy — thử từ khóa tiếng Anh khác (vd: house, money, heart, user)")


def broll(pdir, url, name, source=""):
    """broll <dự-án> <url> v_ten.mp4 ["nguồn"] — tải video b-roll (ưu tiên Pinterest, không được thì Pexels)."""
    from .broll import fetch
    fetch(pdir, url, name, source)


CMDS = {"broll": broll, "icons": icons, "_render_one": _render_one_cli, "init": init, "clean": clean, "restore": restore, "speed": speed, "words": words, "check": check, "stills": stills, "render": render, "revise": revise}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return
    CMDS[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
