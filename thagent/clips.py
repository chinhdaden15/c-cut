"""Dự án nhiều đoạn (TH2): nhiều file quay → 1 video, ghép theo kịch bản.

1. analyze(): mỗi đoạn → chép lời từng từ + mặt/hướng nhìn mỗi 0.5s + ảnh tổng hợp → projects/<id>/clips/
2. Claude viết projects/<id>/edl.json (thứ tự câu, take, b-roll, đoạn chỉ lấy tiếng).
3. validate() + assemble(): ghép bản thô 1080x1920@30 (zoom nhẹ ở chỗ nối khác góc), transcript ánh xạ sẵn,
   covers.json = các khoảng hình b-roll / cần Motion Graphics trên timeline mới.

edl.json:
{"ready": true,
 "segments": [{"clip": "IMG_1.MOV", "in": 12.3, "out": 18.9, "line": "câu kịch bản", "cam": true,
               "broll": [{"clip": "IMG_7.MOV", "in": 2.0, "at": 1.5, "dur": 3.0, "desc": "hồ bơi"}],
               "cover": [{"at": 4.5, "dur": 2.4, "desc": "MG: 3 tiện ích"}]}],
 "notes": "..."}
- in/out: giây trong file đoạn nói. at: giây tính từ đầu segment. cam=false → phải che kín bằng broll/cover.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import imgio
from . import pipeline as P
from .render import run

W, H, FPS = 1080, 1920, 30
STEP = 0.5          # giây giữa 2 mẫu hướng nhìn
ZOOM = 1.08         # zoom nhẹ ở chỗ nối khác góc


def _vf(info, zoom: float = 1.0, w: int = W, h: int = H) -> str:
    zw, zh = int(round(w * zoom / 2) * 2), int(round(h * zoom / 2) * 2)
    fit = (f"scale={zw}:{zh}:force_original_aspect_ratio=increase:flags=lanczos,"
           f"crop={w}:{h}:(iw-{w})/2:(ih-{h})*0.4,")
    tm = ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
          "zscale=t=bt709:m=bt709:r=tv,") if info.hdr else ""
    return fit + tm + f"fps={FPS},format=yuv420p"


def _stem(name: str) -> str:
    return Path(name).stem.replace(" ", "_")


# ---------------- 1. phân tích ----------------
def _gaze(path: str, info, log) -> list[dict]:
    """Dò mặt tầm xa (cảnh rộng, mặt nhỏ) → phóng to vùng mặt → FaceMesh đo hướng đầu + mí mắt."""
    import mediapipe as mp
    sw, sh = 720, 1280
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", _vf(info, 1.0, sw, sh).replace(f"fps={FPS}", f"fps={1 / STEP:g}")
                          .replace("format=yuv420p", "format=rgb24"), "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    out, i = [], 0
    with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as fd, \
            mp.solutions.face_mesh.FaceMesh(static_image_mode=True, max_num_faces=1, refine_landmarks=True,
                                            min_detection_confidence=0.4) as fm:
        while True:
            buf = p.stdout.read(sw * sh * 3)
            if len(buf) < sw * sh * 3:
                break
            img = np.frombuffer(buf, np.uint8).reshape(sh, sw, 3)
            t = round(i * STEP, 2); i += 1
            det = fd.process(img).detections
            if not det:
                out.append({"t": t, "face": False}); continue
            bb = max(det, key=lambda d: d.location_data.relative_bounding_box.width).location_data.relative_bounding_box
            cx, cy, s0 = (bb.xmin + bb.width / 2) * sw, (bb.ymin + bb.height / 2) * sh, max(bb.width * sw, bb.height * sh) * 1.8
            x0, y0 = int(max(0, cx - s0 / 2)), int(max(0, cy - s0 / 2))
            crop = img[y0:int(min(sh, cy + s0 / 2)), x0:int(min(sw, cx + s0 / 2))]
            rec = {"t": t, "face": True, "size": round(bb.width, 3)}
            if crop.size:
                r = fm.process(cv2.resize(crop, (256, 256)))
                if r.multi_face_landmarks:
                    L = r.multi_face_landmarks[0].landmark
                    ew = abs(L[263].x - L[33].x) or 1e-6
                    rec["yaw"] = round((L[1].x - (L[33].x + L[263].x) / 2) / ew, 3)
                    rec["open"] = round(((L[145].y - L[159].y) + (L[374].y - L[386].y)) / 2 / ew, 3)
            out.append(rec)
            if i % 60 == 0:
                log(f"hướng nhìn {t:.0f}s")
    p.wait()
    opens = [g["open"] for g in out if "open" in g]
    base = float(np.percentile(opens, 80)) if opens else 0
    for i, g in enumerate(out):   # nhìn máy: mặt chính diện + mí mắt mở như lúc nhìn thẳng (cúi đọc → mí sụp)
        near = [x["open"] for x in out[max(0, i - 1):i + 2] if "open" in x]   # trung vị 3 mẫu: bỏ qua cái chớp mắt
        op = sorted(near)[len(near) // 2] if near else 0
        g["cam"] = bool("yaw" in g and abs(g["yaw"]) < 0.2 and op > 0.55 * base)
        g["down"] = bool("yaw" in g and abs(g["yaw"]) < 0.35 and op <= 0.55 * base)   # cúi nhìn điện thoại/kịch bản
    return out


def _sheet(path: str, info, gaze: list[dict], dst: Path):
    n = min(48, max(1, int(info.duration)))
    step = info.duration / n
    by_t = {g["t"]: g for g in gaze}
    thumbs = []
    for k in range(n):
        t = k * step
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                              "-vf", _vf(info, 1.0, 180, 320).replace("format=yuv420p", "format=bgr24"),
                              "-f", "rawvideo", "-"], capture_output=True).stdout
        if len(raw) < 180 * 320 * 3:
            continue
        im = np.frombuffer(raw, np.uint8).reshape(320, 180, 3).copy()
        g = by_t.get(round(round(t / STEP) * STEP, 2), {})
        lab = "cam" if g.get("cam") else ("mat" if g.get("face") else "-")
        cv2.rectangle(im, (0, 0), (180, 22), (0, 0, 0), -1)
        cv2.putText(im, f"{t:5.1f}s {lab}", (4, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 255, 0) if lab == "cam" else (0, 200, 255), 1)
        thumbs.append(im)
    if thumbs:
        cols = 8
        rows = [thumbs[i:i + cols] for i in range(0, len(thumbs), cols)]
        rows[-1] += [np.zeros_like(thumbs[0])] * (cols - len(rows[-1]))
        imgio.imwrite(str(dst), np.vstack([np.hstack(r) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 82])


def _spans(words: list[dict], gaze: list[dict], dur: float) -> tuple[list, list]:
    speech, cur = [], None
    for w in words:
        if cur and w["source_start"] - cur["end"] <= 0.7:
            cur["end"] = w["source_end"]; cur["words"].append(w["text"])
        else:
            cur = {"start": w["source_start"], "end": w["source_end"], "words": [w["text"]]}; speech.append(cur)

    def ratio(a, b, key):
        gs = [g for g in gaze if a <= g["t"] <= b]
        return round(sum(1 for g in gs if g.get(key)) / len(gs), 2) if gs else 0.0
    sp = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": " ".join(s["words"]),
           "cam": ratio(s["start"], s["end"], "cam")} for s in speech]
    quiet, prev = [], 0.0
    for s in sp + [{"start": dur, "end": dur}]:
        if s["start"] - prev >= 1.5:
            quiet.append({"start": round(prev, 2), "end": round(s["start"], 2), "face": ratio(prev, s["start"], "face")})
        prev = s["end"]
    return sp, quiet


def analyze(pid: str, clips: list[str], log=print) -> dict:
    from .transcribe import transcribe
    d = P.PROJECTS / pid / "clips"
    d.mkdir(parents=True, exist_ok=True)
    index = []
    for n, path in enumerate(clips, 1):
        name = Path(path).name
        cache = d / f"{_stem(name)}.json"
        if cache.exists():
            index.append(json.loads(cache.read_text(encoding="utf-8"))); continue
        log(f"Phân tích đoạn {n}/{len(clips)}: {name}")
        info = P.probe_source(path)
        words = []
        if info.has_audio:
            wav = d / f"{_stem(name)}.16k.wav"
            run(["ffmpeg", "-v", "error", "-y", "-i", path, "-vn", "-ar", "16000", "-ac", "1", str(wav)])
            ws, _ = transcribe(str(wav), progress=lambda m: log(f"[{n}/{len(clips)}] {m}"))
            from .transcribe import LAST
            from . import fonts as FT
            if ws:
                FT.set_language(P.PROJECTS / pid, LAST["language"])
            words = [w.model_dump() for w in ws]
            wav.unlink(missing_ok=True)
        gaze = _gaze(path, info, log)
        _sheet(path, info, gaze, d / f"{_stem(name)}_sheet.jpg")
        speech, quiet = _spans(words, gaze, info.duration)
        talk = sum(s["end"] - s["start"] for s in speech)
        rec = {"name": name, "path": path, "duration": round(info.duration, 2), "w": info.width, "h": info.height,
               "hdr": info.hdr, "has_audio": info.has_audio,
               "kind_guess": "broll" if talk < 1.0 else ("talk" if talk > 0.6 * info.duration else "mixed"),
               "speech": speech, "quiet": quiet, "sheet": f"clips/{_stem(name)}_sheet.jpg",
               "words": words, "gaze": gaze}
        cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        index.append(rec)
    summary = [{k: v for k, v in r.items() if k not in ("words", "gaze")} for r in index]
    (d / "index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"clips": summary}


# ---------------- 2. kiểm EDL ----------------
def load_edl(pid: str) -> dict | None:
    f = P.PROJECTS / pid / "edl.json"
    try:
        e = json.loads(f.read_text(encoding="utf-8"))
        return e if e.get("ready") else None
    except Exception:
        return None


def validate(pid: str, edl: dict) -> list[str]:
    d = P.PROJECTS / pid / "clips"
    clips = {r["name"]: r for r in json.loads((d / "index.json").read_text(encoding="utf-8"))}
    errs = []
    segs = edl.get("segments") or []
    if not segs:
        return ["edl.json không có segments"]
    for i, s in enumerate(segs, 1):
        c = clips.get(s.get("clip"))
        if not c:
            errs.append(f"seg {i}: không có đoạn '{s.get('clip')}'"); continue
        if not c["has_audio"]:
            errs.append(f"seg {i}: '{c['name']}' không có tiếng, không làm đoạn nói được")
        if not (0 <= s["in"] < s["out"] <= c["duration"] + 0.05):
            errs.append(f"seg {i}: in/out {s['in']}–{s['out']} ngoài 0–{c['duration']}s")
        L = s["out"] - s["in"]
        cov = []
        for b in s.get("broll", []):
            bc = clips.get(b.get("clip"))
            if not bc:
                errs.append(f"seg {i}: b-roll '{b.get('clip')}' không tồn tại"); continue
            if b["in"] < 0 or b["in"] + b["dur"] > bc["duration"] + 0.05:
                errs.append(f"seg {i}: b-roll {bc['name']} {b['in']}+{b['dur']}s vượt độ dài {bc['duration']}s")
            cov.append((b["at"], b["at"] + b["dur"]))
        for m in s.get("cover", []):
            cov.append((m["at"], m["at"] + m["dur"]))
        for a, b in cov:
            if a < -0.01 or b > L + 0.05:
                errs.append(f"seg {i}: khoảng che {a:.2f}–{b:.2f}s ra ngoài đoạn dài {L:.2f}s")
        if s.get("cam") is False:   # không nhìn máy → che kín
            cov.sort(); t = 0.0
            for a, b in cov:
                if a > t + 0.2:
                    break
                t = max(t, b)
            if t < L - 0.2:
                errs.append(f"seg {i}: cam=false nhưng chỉ che {t:.1f}/{L:.1f}s — thêm broll/cover cho kín")
    return errs


# ---------------- 3. ghép ----------------
def assemble(pid: str, edl: dict, log=print) -> Path:
    pdir = P.PROJECTS / pid
    clips = {r["name"]: r for r in json.loads((pdir / "clips" / "index.json").read_text(encoding="utf-8"))}
    tmp = pdir / "work" / "assemble"
    tmp.mkdir(parents=True, exist_ok=True)
    infos = {}

    def info(name):
        if name not in infos:
            infos[name] = P.probe_source(clips[name]["path"])
        return infos[name]

    vparts, aparts, covers, words, sents = [], [], [], [], []
    t0, zoom, prev = 0, 1.0, None       # t0 tính bằng frame
    segs = edl["segments"]
    for i, s in enumerate(segs, 1):
        log(f"Ghép đoạn {i}/{len(segs)}")
        c = clips[s["clip"]]
        nf = max(1, round((s["out"] - s["in"]) * FPS))
        # zoom nhẹ khi nối 2 cảnh nói không liền mạch (khác file hoặc nhảy thời gian)
        joined = prev and (prev["clip"] != s["clip"] or abs(prev["out"] - s["in"]) > 0.15)
        zoom = (ZOOM if zoom == 1.0 else 1.0) if joined else zoom
        prev = s
        # tiếng: nguyên đoạn nói
        a = tmp / f"a{i:03d}.wav"
        run(["ffmpeg", "-v", "error", "-y", "-ss", f"{s['in']:.3f}", "-i", c["path"], "-vn", "-t", f"{nf / FPS:.4f}",
             "-af", f"afade=t=in:d=0.012,afade=t=out:st={nf / FPS - 0.012:.4f}:d=0.012",
             "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", str(a)])
        aparts.append(a)
        # hình: đoạn nói, thay bằng b-roll ở các khoảng broll
        brs = sorted(s.get("broll", []), key=lambda b: b["at"])
        cuts, f = [], 0
        for b in brs:
            fa, fb = round(b["at"] * FPS), min(nf, round((b["at"] + b["dur"]) * FPS))
            if fa > f:
                cuts.append(("self", f, fa, None))
            if fb > max(fa, f):
                cuts.append(("broll", max(fa, f), fb, b))
            f = max(f, fb)
            covers.append({"start": round((t0 + fa) / FPS, 3), "end": round((t0 + fb) / FPS, 3), "kind": "broll",
                           "clip": b["clip"], "desc": b.get("desc", "")})
        if f < nf:
            cuts.append(("self", f, nf, None))
        for k, (kind, fa, fb, b) in enumerate(cuts):
            v = tmp / f"v{i:03d}_{k}.mp4"
            src, start, z = (c, s["in"] + fa / FPS, zoom) if kind == "self" else (clips[b["clip"]], b["in"], 1.0)
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.3f}", "-i", src["path"], "-an", "-frames:v", str(fb - fa),
                 "-vf", _vf(info(src["name"]), z), "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-g", "30",
                 str(v)])
            vparts.append(v)
        for m in s.get("cover", []):
            covers.append({"start": round(t0 / FPS + m["at"], 3), "end": round(t0 / FPS + m["at"] + m["dur"], 3),
                           "kind": "mg", "desc": m.get("desc", "")})
        if s.get("cam") is False:
            covers.append({"start": round(t0 / FPS, 3), "end": round((t0 + nf) / FPS, 3), "kind": "audio_only",
                           "desc": "nhân vật không nhìn máy — chỉ dùng tiếng"})
        # transcript ánh xạ sang timeline mới
        ids = []
        for w in json.loads((pdir / "clips" / f"{_stem(c['name'])}.json").read_text(encoding="utf-8"))["words"]:
            if w["source_start"] >= s["in"] - 0.05 and w["source_end"] <= s["out"] + 0.05:
                sh = t0 / FPS - s["in"]
                wid = f"w{len(words):04d}"
                words.append({**w, "id": wid, "sentence_id": i - 1,
                              "source_start": round(max(0, w["source_start"] + sh), 3),
                              "source_end": round(min((t0 + nf) / FPS, w["source_end"] + sh), 3)})
                ids.append(wid)
        if ids:
            sents.append({"id": i - 1, "text": " ".join(w["text"] for w in words[-len(ids):]),
                          "source_start": words[-len(ids)]["source_start"], "source_end": words[-1]["source_end"],
                          "word_ids": ids})
        t0 += nf

    def concat(parts, dst):
        lst = dst.with_suffix(".txt")
        lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
        run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(dst)])

    concat(vparts, tmp / "video.mp4")
    concat(aparts, tmp / "audio.wav")
    out = pdir / "work" / "assembled.mov"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp / "video.mp4"), "-i", str(tmp / "audio.wav"),
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "pcm_s16le", "-t", f"{t0 / FPS:.4f}", str(out)])
    (pdir / "covers.json").write_text(json.dumps(covers, ensure_ascii=False, indent=1), encoding="utf-8")
    (pdir / "work").mkdir(exist_ok=True)
    (pdir / "work" / "transcript.json").write_text(json.dumps({"words": words, "sentences": sents}, ensure_ascii=False,
                                                              indent=1), encoding="utf-8")
    for p in tmp.iterdir():
        p.unlink()
    log(f"Bản ghép thô: {t0 / FPS:.1f}s, {len(segs)} câu, {sum(1 for x in covers if x['kind'] == 'broll')} b-roll")
    return out
