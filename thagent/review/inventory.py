"""Review Editor — kiểm kê + phân tích tư liệu. Kết quả lưu theo chữ ký file → sửa một cảnh không phải phân tích lại.

    inventory(pdir, files)  → <dự-án>/review/inventory.json + review/media/<ID>.json + review/sheets/<ID>.jpg

Mỗi file (ID ổn định F01, F02… theo thứ tự tên): thời lượng, độ phân giải, fps, hướng (dọc/ngang/vuông), xoay, audio,
độ to (LUFS), file trùng, khoảng đen, đoạn đứng hình cuối (outro nền tảng), cảnh (shot) theo điểm cắt,
mỗi cảnh: độ nét, độ rung, phơi sáng, có mặt người (vị trí mặt để crop), lời nói (chép lời từng từ, độ tin cậy),
từ cần soát (tên riêng, số, giá, diện tích, mã sản phẩm, độ tin cậy thấp).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac"}
SAMPLE = 0.5            # giây giữa 2 mẫu phân tích hình
ANA_W = 360             # bề rộng khung phân tích (nhanh)


def _run(cmd, text=True):
    return subprocess.run(cmd, capture_output=True, text=text)


def _sig(path: Path) -> str:
    """chữ ký nhanh: kích thước + 1MB đầu + 1MB cuối (đổi file → phân tích lại)."""
    h = hashlib.sha1(str(path.stat().st_size).encode())
    with open(path, "rb") as f:
        h.update(f.read(1 << 20))
        f.seek(max(path.stat().st_size - (1 << 20), 0))
        h.update(f.read(1 << 20))
    return h.hexdigest()[:16]


def probe(path: Path) -> dict:
    r = _run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)])
    if r.returncode:
        return {"error": r.stderr.strip()[:200] or "không đọc được"}
    j = json.loads(r.stdout)
    v = next((s for s in j.get("streams", []) if s["codec_type"] == "video"), None)
    a = next((s for s in j.get("streams", []) if s["codec_type"] == "audio"), None)
    out = {"duration": round(float(j["format"].get("duration", 0) or 0), 3), "has_audio": a is not None,
           "size": int(j["format"].get("size", 0))}
    if v:
        rot = 0
        for sd in v.get("side_data_list", []):
            rot = int(sd.get("rotation", rot))
        rot = int(v.get("tags", {}).get("rotate", rot))
        w, h = v["width"], v["height"]
        if abs(rot) in (90, 270):
            w, h = h, w
        num, den = map(int, v.get("r_frame_rate", "30/1").split("/"))
        out.update(w=w, h=h, rotation=rot, fps=round(num / max(den, 1), 3), codec=v.get("codec_name"),
                   hdr=v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
                   orientation="doc" if h > w * 1.05 else ("ngang" if w > h * 1.05 else "vuong"))
    if a:
        out.update(audio_codec=a.get("codec_name"), channels=a.get("channels"), sample_rate=a.get("sample_rate"))
    return out


def _black(path: Path, dur: float) -> list[list[float]]:
    r = _run(["ffmpeg", "-v", "info", "-i", str(path), "-vf", "scale=160:-2,blackdetect=d=0.3:pix_th=0.10", "-an", "-f", "null", "-"])
    return [[round(float(a), 2), round(float(b), 2)] for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", r.stderr)]


def _loudness(path: Path) -> dict:
    r = _run(["ffmpeg", "-v", "info", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"])
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return {"lufs": float(i[-1]) if i else None, "peak_db": float(pk[-1]) if pk else None}


def _frames(path: Path, info: dict):
    """khung xám nhỏ + màu (cho mặt) mỗi SAMPLE giây."""
    h = int(round(ANA_W * info["h"] / info["w"] / 2) * 2)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={1 / SAMPLE:g},scale={ANA_W}:{h}", "-an",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n = ANA_W * h * 3
    i = 0
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield round(i * SAMPLE, 2), np.frombuffer(buf, np.uint8).reshape(h, ANA_W, 3)
            i += 1
    finally:                       # dừng giữa chừng → đóng ffmpeg gọn (không log "Broken pipe")
        if p.poll() is None:
            p.kill()
        p.stdout.close()
        p.wait()


def _visual(path: Path, info: dict, log, cancel=None) -> list[dict]:
    """mỗi mẫu: nét (phương sai Laplacian), sáng (trung bình, % cháy/tối), chuyển động (lệch khung), điểm cắt, mặt."""
    try:
        import mediapipe as mp
        fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.55)
    except Exception:
        fd = None
    out, prev, prev_hist = [], None, None
    for t, rgb in _frames(path, info):
        if cancel and cancel():                      # bấm Dừng: thôi ngay ở khung đang xét
            raise RuntimeError("cancelled")
        g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
        mean = float(g.mean())
        clip_hi, clip_lo = float((g > 245).mean()), float((g < 12).mean())
        hist = cv2.calcHist([g], [0], None, [32], [0, 256]).ravel()
        hist /= hist.sum() + 1e-6
        cut = bool(prev_hist is not None and 0.5 * np.abs(hist - prev_hist).sum() > 0.45)
        motion = 0.0
        if prev is not None and not cut:
            (dx, dy), _ = cv2.phaseCorrelate(np.float32(prev), np.float32(g))
            motion = float(np.hypot(dx, dy)) / ANA_W            # tỷ lệ bề rộng khung dịch đi giữa 2 mẫu
        rec = {"t": t, "sharp": round(sharp, 1), "luma": round(mean, 1), "hi": round(clip_hi, 3), "lo": round(clip_lo, 3),
               "motion": round(motion, 4), "cut": cut}
        if fd is not None:
            det = fd.process(rgb).detections
            if det:
                bb = max(det, key=lambda d: d.location_data.relative_bounding_box.width).location_data.relative_bounding_box
                rec["face"] = [round(bb.xmin + bb.width / 2, 3), round(bb.ymin + bb.height / 2, 3), round(bb.width, 3), round(bb.height, 3)]
                H_, W_ = g.shape
                fx0, fy0 = int(max(bb.xmin, 0) * W_), int(max(bb.ymin, 0) * H_)
                fx1, fy1 = int(min(bb.xmin + bb.width, 1) * W_), int(min(bb.ymin + bb.height, 1) * H_)
                if fx1 > fx0 + 2 and fy1 > fy0 + 2:
                    rec["face_luma"] = round(float(g[fy0:fy1, fx0:fx1].mean()), 1)
        out.append(rec)
        prev, prev_hist = g, hist
        if len(out) % 120 == 0:
            log(f"  hình {t:.0f}s")
    if fd is not None:
        fd.close()
    return out


def _shots(vis: list[dict], dur: float, black: list) -> list[dict]:
    """chia cảnh theo điểm cắt; chấm chất lượng từng cảnh."""
    cuts = [0.0] + [v["t"] for v in vis if v["cut"]] + [dur]
    shots = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 0.25:
            continue
        vs = [v for v in vis if a <= v["t"] < b] or [min(vis, key=lambda v: abs(v["t"] - a))] if vis else []
        if not vs:
            continue
        sharp = float(np.median([v["sharp"] for v in vs]))
        mot = [v["motion"] for v in vs[1:]]
        shake = float(np.std(mot)) if len(mot) > 2 else 0.0
        faces = [v["face"] for v in vs if "face" in v]
        luma = float(np.mean([v["luma"] for v in vs]))
        fl = [v["face_luma"] for v in vs if "face_luma" in v]
        bright = float(np.mean([v["hi"] for v in vs]))
        blk = sum(max(0, min(b, y) - max(a, x)) for x, y in black)
        flags = []
        if sharp < 25: flags.append("mờ")
        if shake > 0.02: flags.append("rung")
        if luma < 40: flags.append("tối")
        if luma > 215: flags.append("cháy sáng")
        if blk > 0.6 * (b - a): flags.append("đen")
        if fl and (float(np.median(fl)) < 0.7 * luma or bright > 0.12) and float(np.median(fl)) < 125:
            flags.append("ngược sáng")
        shots.append({"start": round(a, 2), "end": round(b, 2), "sharp": round(sharp, 1), "shake": round(shake, 4),
                      "move": round(float(np.mean(mot)) if mot else 0.0, 4), "luma": round(luma, 1),
                      "face_ratio": round(len(faces) / len(vs), 2),
                      "face": [round(float(np.median([f[k] for f in faces])), 3) for k in range(4)] if faces else None,
                      "flags": flags})
    return shots


NUM = re.compile(r"\d")
COMMON = set("và thì đây đó tôi mình em anh chị sau thay bây nhưng còn khi nếu vì nên cho có là đúng rồi cái một hai ba "
             "này kia các những chúng ta bạn họ cũng mà với để từ ở trong ngoài trên dưới không chưa đã sẽ đang hay hoặc vậy thế".split())
UNIT = re.compile(r"^(m2|m²|mét|tỷ|triệu|tr|k|nghìn|ngàn|đồng|usd|\$|%|gb|tb|mah|ml|g|kg|inch|hz|w)$", re.I)


def _words(path: Path, info: dict, d: Path, log) -> list[dict]:
    if not info.get("has_audio"):
        return []
    from ..transcribe import transcribe
    wav = d / f"{path.stem}.16k.wav"
    _run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ar", "16000", "-ac", "1", str(wav)])
    try:
        ws, _ = transcribe(str(wav), progress=log)
    finally:
        wav.unlink(missing_ok=True)
    out = []
    for w in ws:
        txt = w.text
        flag = []
        if w.confidence < 0.6: flag.append("tin cậy thấp")
        if NUM.search(txt) or UNIT.match(txt.strip(".,")): flag.append("số/đơn vị")
        gap = w.source_start - out[-1]["end"] if out else 9
        if txt[:1].isupper() and out and gap < 0.35 and txt.lower().strip(".,") not in COMMON and \
                not out[-1]["text"].rstrip().endswith((".", "?", "!")):
            flag.append("tên riêng?")
        out.append({"text": txt, "start": round(w.source_start, 3), "end": round(w.source_end, 3), "conf": round(w.confidence, 3),
                    **({"check": flag} if flag else {})})
    return out


def _sentences(words: list[dict]) -> list[dict]:
    """câu nói: ngắt ở dấu câu hoặc ngừng > 0,6s."""
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 9
        if re.search(r"[.?!…]$", w["text"]) or gap > 0.6:
            out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["text"] for x in cur),
                        "conf": round(float(np.mean([x["conf"] for x in cur])), 3), "n": len(cur)})
            cur = []
    if cur:
        out.append({"start": cur[0]["start"], "end": cur[-1]["end"], "text": " ".join(x["text"] for x in cur),
                    "conf": round(float(np.mean([x["conf"] for x in cur])), 3), "n": len(cur)})
    return out


def _sheet(path: Path, info: dict, shots: list[dict], dst: Path, fid: str):
    """ảnh tổng hợp: mỗi cảnh 1 khung giữa cảnh, ghi ID + giây + cờ chất lượng."""
    th_w = 200
    th_h = int(th_w * info["h"] / info["w"])
    thumbs = []
    for k, s in enumerate(shots[:40]):
        t = (s["start"] + s["end"]) / 2
        raw = _run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(path), "-frames:v", "1", "-vf", f"scale={th_w}:{th_h}",
                    "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], text=False).stdout
        if len(raw) < th_w * th_h * 3:
            continue
        im = np.frombuffer(raw, np.uint8).reshape(th_h, th_w, 3).copy()
        cv2.rectangle(im, (0, 0), (th_w, 20), (0, 0, 0), -1)
        lab = f"{fid}#{k + 1} {s['start']:.1f}-{s['end']:.1f}s"
        cv2.putText(im, lab, (3, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        if s["flags"]:
            cv2.rectangle(im, (0, th_h - 18), (th_w, th_h), (0, 0, 160), -1)
            cv2.putText(im, ",".join(s["flags"]).encode("ascii", "ignore").decode() or "!", (3, th_h - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (255, 255, 255), 1)
        thumbs.append(im)
    if not thumbs:
        return
    cols = 6 if th_h > th_w else 4
    rows = [thumbs[i:i + cols] for i in range(0, len(thumbs), cols)]
    rows[-1] += [np.zeros_like(thumbs[0])] * (cols - len(rows[-1]))
    cv2.imwrite(str(dst), np.vstack([np.hstack(r) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 80])


def inventory(pdir, files: list[str], log=print, refs: list[str] | None = None, cancel=None) -> dict:
    """kiểm kê + phân tích; tư liệu tham khảo (refs) chỉ ghi nhận, KHÔNG dùng để dựng."""
    pdir = Path(pdir)
    d = pdir / "review"
    (d / "media").mkdir(parents=True, exist_ok=True)
    (d / "sheets").mkdir(exist_ok=True)
    srcs = sorted((Path(f) for f in files), key=lambda p: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", p.name)])
    old = {}
    if (d / "inventory.json").exists():
        for m in json.loads((d / "inventory.json").read_text(encoding="utf-8"))["media"]:
            old[m["path"]] = m["id"]
    used = set(old.values())
    nxt = max([int(i[1:]) for i in used if i[1:].isdigit()] + [0]) + 1
    media, sigs = [], {}
    for p in srcs:
        fid = old.get(str(p))
        if not fid:
            fid = f"F{nxt:02d}"; nxt += 1
        kind = "anh" if p.suffix.lower() in IMAGE_EXT else ("am_thanh" if p.suffix.lower() in AUDIO_EXT else "video")
        sig = _sig(p)
        cache = d / "media" / f"{fid}.json"
        if cache.exists():
            rec = json.loads(cache.read_text(encoding="utf-8"))
            if rec.get("sig") == sig:
                media.append(rec); sigs.setdefault(sig, fid); continue
        log(f"Phân tích {fid}: {p.name}")
        rec = {"id": fid, "path": str(p), "name": p.name, "kind": kind, "sig": sig, **probe(p)}
        if sig in sigs:
            rec["duplicate_of"] = sigs[sig]
        sigs.setdefault(sig, fid)
        if "error" in rec:
            rec["usable"] = False
        elif kind == "video" and "w" in rec:
            rec["black"] = _black(p, rec["duration"])
            vis = _visual(p, rec, log, cancel)
            rec["shots"] = _shots(vis, rec["duration"], rec["black"])
            rec["backlit"] = sum(s["end"] - s["start"] for s in rec["shots"] if "ngược sáng" in s["flags"]) > 0.5 * rec["duration"]
            rec["sharp_track"] = [[v["t"], v["sharp"], v["motion"]] for v in vis]   # nét/chuyển động mỗi 0,5s → cắt bỏ đoạn nhòe
            rec["samples"] = [{k: v[k] for k in ("t", "face") if k in v} for v in vis if "face" in v]
            # đứng hình/đen ở cuối (outro nền tảng, màn kết TikTok…)
            tail = [v for v in vis if v["t"] > rec["duration"] - 6]
            still = [v for v in tail[1:] if v["motion"] < 0.001 and not v["cut"]]
            if rec["black"] and rec["black"][-1][1] >= rec["duration"] - 0.3:
                rec["outro"] = [rec["black"][-1][0], rec["duration"]]
            elif tail and len(still) >= len(tail) - 1 and len(tail) > 4:
                rec["outro"] = [tail[0]["t"], rec["duration"]]
            _sheet(p, rec, rec["shots"], d / "sheets" / f"{fid}.jpg", fid)
            rec["sheet"] = f"review/sheets/{fid}.jpg"
        if rec.get("has_audio"):
            rec.update(_loudness(p))
            rec["words"] = _words(p, rec, d, log)
            rec["sentences"] = _sentences(rec["words"])
            rec["speech_s"] = round(sum(s["end"] - s["start"] for s in rec["sentences"]), 2)
            rec["check_words"] = [{"t": w["start"], "text": w["text"], "why": w["check"]} for w in rec["words"] if w.get("check")]
        if kind == "video" and "w" in rec:
            talk = rec.get("speech_s", 0)
            fr = float(np.mean([s["face_ratio"] for s in rec.get("shots", [])] or [0]))
            rec["role_guess"] = "nguoi_dan" if talk > 0.4 * rec["duration"] and fr > 0.3 else ("broll" if talk < 1.0 else "hon_hop")
        rec["usable"] = rec.get("usable", "error" not in rec and not rec.get("duplicate_of"))
        cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        media.append(rec)
    ref_list = []
    for i, r in enumerate(refs or [], 1):
        rp = Path(r)
        ref_list.append({"id": f"R{i:02d}", "path": str(rp), "name": rp.name, "note": "CHỈ tham khảo phong cách — không chèn vào video", **probe(rp)})
    summary = {"media": [{k: v for k, v in m.items() if k not in ("words", "samples", "sentences", "shots")}
                         | {"shots": len(m.get("shots", [])), "sentences": len(m.get("sentences", []))} for m in media],
               "references": ref_list}
    (d / "inventory.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def load(pdir, fid: str) -> dict:
    return json.loads((Path(pdir) / "review" / "media" / f"{fid}.json").read_text(encoding="utf-8"))
