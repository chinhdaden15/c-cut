"""Chuẩn dữ liệu job HyperFrames của app (dùng chung mọi skill). Kiểm TRƯỚC khi dựng composition.

{
  "job_id": "rv-9x16-spot-01",                 # tuỳ chọn — thiếu thì app đặt theo mã băm nội dung
  "width": 1080, "height": 1920, "fps": 30, "duration": 3.2,
  "background": "transparent",                 # "transparent" (lớp phủ) | "#101010"
  "output": {"path": "…/spot.mov", "format": "mov", "quality": "looks"},
       # mov = ProRes 4444 CÓ alpha (lớp phủ ghép vào bộ dựng của skill) | webm (VP9 alpha) | mp4 (đoạn hoàn chỉnh) | png-sequence
  "fonts": [{"family": "Montserrat", "file": "assets/fonts/Montserrat-VF.ttf", "weight": "100 900"}],   # mặc định: font app
  "audio": [{"src": "voice.wav", "start": 0, "volume": 1}],            # chỉ khi xuất đoạn hoàn chỉnh (mp4)
  "scenes": [{"id": "s1", "start": 0, "duration": 3.2, "layers": [ … ]}]   # hoặc "layers" ở gốc = 1 cảnh
}

Lớp (mọi lớp): id, type, start, duration (giây, tính trong cảnh), x, y (điểm neo; px hoặc "50%"), anchor (center|top-left|…),
  w, h, z, opacity, style {css}, enter {type: fade|up|down|left|right|pop|wipe|none, dur, ease}, exit {type, dur},
  keyframes [{t, x, y, w, h, opacity, scale}]  (t tính từ đầu lớp — vị trí THẬT theo thời gian, vd dữ liệu bám vật).
Loại:
  text      text, font (black|display|bold|semi|medium|body|body_bold), size, color, stroke, stroke_color, align, max_w,
            line_h, bg, pad, radius, highlight [{match, color}], reveal "words" + word_times [giây] + active_color (phụ đề theo lời)
  image     src, fit (cover|contain), radius, border
  video     src, in (giây nguồn), muted (mặc định true), fit
  shape     shape (rect|circle|line), fill, stroke, stroke_w, radius
  callout   text, target {x, y} hoặc target_track [{t, x, y}] (điểm bám thật), side (left|right|top|bottom), gap, dot
  spotlight track [{t, x, y, w, h}] BẮT BUỘC (vị trí thật theo thời gian — từ tracking), dim 0.25–0.4, radius, pad, feather
            (không có dữ liệu bám → lỗi; khung cố định chỉ khi ghi rõ "static_reason")
  bars      items [{label, value}], unit, max, color, label_color
  table     title, cols [A, B], rows [[nhãn, a, b]], win [1|2|0…]
  html      html, css, js (đoạn GSAP dùng biến `tl` và `sel` = selector gốc của lớp) — lối thoát cho hiệu ứng riêng
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

TYPES = {"text", "image", "video", "shape", "callout", "spotlight", "bars", "table", "html"}
FORMATS = {"mov", "webm", "mp4", "png-sequence"}
ENTERS = {"fade", "up", "down", "left", "right", "pop", "wipe", "none"}


def _num(v, total):
    if isinstance(v, str) and v.endswith("%"):
        return float(v[:-1]) / 100 * total
    return float(v)


def normalize(spec: dict, base: Path | None = None) -> dict:
    s = json.loads(json.dumps(spec))
    s.setdefault("fps", 30)
    s.setdefault("background", "transparent")
    out = s.setdefault("output", {})
    out.setdefault("format", "mov" if s["background"] == "transparent" else "mp4")
    out.setdefault("quality", "looks")
    if "scenes" not in s:
        s["scenes"] = [{"id": "s1", "start": 0, "duration": s.get("duration"), "layers": s.pop("layers", [])}]
    if not s.get("duration"):
        s["duration"] = max(float(c["start"]) + float(c["duration"]) for c in s["scenes"])
    for k, c in enumerate(s["scenes"]):
        c.setdefault("id", f"s{k + 1}")
        c.setdefault("start", 0)
        c.setdefault("duration", s["duration"] - float(c["start"]))
        for i, L in enumerate(c.get("layers", [])):
            L.setdefault("id", f"{c['id']}_{L.get('type', 'x')}{i + 1}")
            L.setdefault("start", 0)
            L.setdefault("duration", float(c["duration"]) - float(L["start"]))
            L.setdefault("z", 0 if L.get("type") == "spotlight" else i + 1)   # lớp tối của spotlight luôn DƯỚI chữ/nhãn
    if out.get("path") and not Path(out["path"]).is_absolute():
        out["path"] = str(((base or Path.cwd()) / out["path"]).resolve())
    if base:
        for key in ("src",):
            for c in s["scenes"]:
                for L in c["layers"]:
                    if L.get(key) and not Path(L[key]).is_absolute():
                        L[key] = str((base / L[key]).resolve())
        for a in s.get("audio", []):
            if not Path(a["src"]).is_absolute():
                a["src"] = str((base / a["src"]).resolve())
    if not s.get("job_id"):
        s["job_id"] = "hf-" + content_hash(s)[:12]
    return s


def content_hash(s: dict) -> str:
    """băm nội dung (kể cả mtime/kích thước file nguồn) — dùng để bỏ qua render lại phần đã thành công."""
    files = []
    for c in s.get("scenes", []):
        for L in c.get("layers", []):
            if L.get("src") and Path(L["src"]).exists():
                st = Path(L["src"]).stat()
                files.append([L["src"], st.st_size, int(st.st_mtime)])
    for a in s.get("audio", []):
        if Path(a["src"]).exists():
            st = Path(a["src"]).stat()
            files.append([a["src"], st.st_size, int(st.st_mtime)])
    body = {k: v for k, v in s.items() if k not in ("job_id",)}
    body["output"] = {k: v for k, v in body.get("output", {}).items() if k != "path"}
    from .runtime import pinned
    from .compose import VERSION
    return hashlib.sha256(json.dumps([body, files, pinned(), VERSION], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def validate(s: dict) -> list[tuple[str, str]]:
    """[(error|warn, thông điệp)] — lỗi thì KHÔNG dựng."""
    out = []
    W, H, T = int(s.get("width", 0)), int(s.get("height", 0)), float(s.get("duration") or 0)
    if not (16 <= W <= 7680 and 16 <= H <= 7680):
        out.append(("error", f"kích thước không hợp lệ {W}x{H}"))
    if not (1 <= int(s["fps"]) <= 120):
        out.append(("error", f"fps {s['fps']} ngoài 1–120"))
    if T <= 0:
        out.append(("error", "thời lượng phải > 0"))
    fmt = s["output"]["format"]
    if fmt not in FORMATS:
        out.append(("error", f"định dạng {fmt} không hỗ trợ (mov|webm|mp4|png-sequence)"))
    if fmt == "mp4" and s["background"] == "transparent":
        out.append(("warn", "mp4 không có alpha — nền trong suốt sẽ thành đen; lớp phủ nên dùng mov/webm"))
    if not s["output"].get("path"):
        out.append(("error", "thiếu output.path"))
    ids = set()
    for c in s["scenes"]:
        if float(c["start"]) + float(c["duration"]) > T + 1e-3:
            out.append(("error", f"cảnh {c['id']} vượt thời lượng job"))
        for L in c.get("layers", []):
            lid, t = L["id"], L.get("type")
            if lid in ids:
                out.append(("error", f"trùng id lớp {lid}"))
            ids.add(lid)
            if t not in TYPES:
                out.append(("error", f"{lid}: loại lớp '{t}' không hỗ trợ ({', '.join(sorted(TYPES))})"))
                continue
            if float(L["start"]) < 0 or float(L["start"]) + float(L["duration"]) > float(c["duration"]) + 1e-3:
                out.append(("error", f"{lid}: {L['start']}+{L['duration']}s nằm ngoài cảnh {c['id']} ({c['duration']}s)"))
            for k in ("enter", "exit"):
                if L.get(k) and L[k].get("type", "fade") not in ENTERS:
                    out.append(("error", f"{lid}: {k}.type '{L[k]['type']}' không hỗ trợ"))
            if t in ("image", "video") and not Path(L.get("src", "")).exists():
                out.append(("error", f"{lid}: không thấy file {L.get('src')}"))
            if t in ("text", "callout") and not str(L.get("text", "")).strip():
                out.append(("error", f"{lid}: chữ rỗng"))
            if t == "text" and L.get("reveal") == "words" and L.get("word_times"):
                n = len(str(L["text"]).split())
                if len(L["word_times"]) != n:
                    out.append(("error", f"{lid}: word_times có {len(L['word_times'])} mốc cho {n} từ"))
            if t == "spotlight":
                tr = L.get("track") or []
                if len(tr) < 2 and not L.get("static_reason"):
                    out.append(("error", f"{lid}: spotlight cần dữ liệu bám vật thật (track ≥ 2 mốc) — không tự vẽ khung cố định"))
                for p in tr:
                    if not all(k in p for k in ("t", "x", "y", "w", "h")):
                        out.append(("error", f"{lid}: mốc track thiếu t/x/y/w/h")); break
                d = float(L.get("dim", 0.32))
                if not 0.15 <= d <= 0.6:
                    out.append(("warn", f"{lid}: dim {d} ngoài khoảng nên dùng 0,25–0,4"))
            if t == "callout" and not (L.get("target") or L.get("target_track")):
                out.append(("error", f"{lid}: callout cần target hoặc target_track"))
            if t == "table" and not L.get("rows"):
                out.append(("error", f"{lid}: bảng không có hàng"))
            if t == "bars" and not L.get("items"):
                out.append(("error", f"{lid}: biểu đồ không có dữ liệu"))
            for kf in L.get("keyframes", []):
                if not 0 <= float(kf.get("t", -1)) <= float(L["duration"]) + 1e-3:
                    out.append(("error", f"{lid}: keyframe t={kf.get('t')} ngoài thời lượng lớp")); break
    for a in s.get("audio", []):
        if not Path(a["src"]).exists():
            out.append(("error", f"không thấy audio {a['src']}"))
    for f in s.get("fonts", []):
        if not Path(f["file"]).exists():
            out.append(("error", f"không thấy font {f['file']}"))
    return out
