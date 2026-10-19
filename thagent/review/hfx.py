"""Review × HyperFrames (công cụ dựng dùng chung thagent.hyper): nhãn/callout, spotlight, bảng so sánh, thẻ thông tin, lớp tự do.

Bật cho từng chữ: texts[] có "engine": "hyperframes"; hoặc cả bản dựng: edit["graphics_engine"] = "hyperframes"
(áp cho label, spotlight, compare, info). Lớp tự do: role "hf" + "layers" (chuẩn thagent/hyper/spec.py, giờ tính từ lúc chữ hiện).
- Spotlight/nhãn: vị trí lấy từ TRACK THẬT (review/tracks/<tên>.json) qua đúng phép crop/reframe/Cắt sạch của Review
  (_track_boxes, mẫu 0,1s) — không có track → lỗi check, không vẽ khung cố định.
- Bộ dựng Review sở hữu timeline: mỗi mục render một clip mov có alpha đúng độ dài của nó (lưu đệm theo mã băm),
  ghép DƯỚI lớp chữ của Review. HyperFrames không sẵn sàng → mục có phương án tương đương (label/spotlight/compare/info)
  dùng bộ vẽ hiện có của Review và QA ghi rõ; mục "hf" không có tương đương → check báo CHẶN.
"""
from __future__ import annotations

from pathlib import Path

from .edit import FORMATS, layout

ROLES = ("label", "spotlight", "compare", "info")


def wants(edit: dict, t: dict) -> bool:
    if t.get("role") == "hf":
        return True
    return t.get("engine") == "hyperframes" or (edit.get("graphics_engine") == "hyperframes" and t.get("role") in ROLES
                                                and t.get("engine") != "builtin")


_READY = {}


def ready() -> bool:
    if "ok" not in _READY:
        from ..capabilities import status
        _READY["ok"] = bool(status("hyperframes").get("ok"))
    return _READY["ok"]


def uses(edit: dict, t: dict) -> bool:
    """chữ này do HyperFrames dựng (cần sẵn sàng; role hf luôn thuộc HyperFrames)."""
    return wants(edit, t) and (t.get("role") == "hf" or ready())


def _spans(edit):
    segs = layout(edit)
    for s in segs:
        grp = s.get("group", s["id"])
        g_end = max(x["t1"] for x in segs if x.get("group", x["id"]) == grp)
        for k, t in enumerate(s.get("texts", [])):
            at = s["t0"] + float(t["at"])
            d = min(float(t.get("dur", 2.5)), g_end - at + (0.0 if g_end < segs[-1]["t1"] - 1e-6 else 99))
            yield s, k, t, at, d


def specs(edit: dict, pdir, fmt: str) -> list[tuple[dict, dict]]:
    """[(spec, item)] — item {path, start, dur} cho Overlays."""
    from .graphics import _track_boxes, SAFE
    W, H = FORMATS[fmt]
    V = fmt == "9x16"
    acc = edit.get("accent") or "#FFD34D"
    out = []
    root = Path(pdir) / "review" / "hf"
    for s, k, t, at, d in _spans(edit):
        if not wants(edit, t):
            continue
        role = t["role"]
        L = []
        if role == "spotlight":
            pts = _track_boxes(t, s, edit, pdir, fmt, at, d, 0.1) if t.get("track") else []
            L.append({"type": "spotlight", "start": 0, "duration": d, "dim": float(t.get("dim", 0.32)), "pad": float(t.get("pad", 22)),
                      "radius": float(t.get("radius", 36)), "feather": float(t.get("feather", 22)), "frame": t.get("frame", True),
                      "track": [{"t": round(tt - at, 3), "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0} for tt, x0, y0, x1, y1 in pts]})
        elif role == "label":
            pts = _track_boxes(t, s, edit, pdir, fmt, at, d, 0.1) if t.get("track") else []
            side = t.get("side") or ("top" if V else "right")
            L.append({"type": "callout", "text": t["text"], "start": 0, "duration": d, "side": side, "accent": acc,
                      "size": 46 if V else 40, "gap": 110 if V else 130,
                      "target_track": [{"t": round(tt - at, 3), "x": (x0 + x1) / 2, "y": y0 if side == "top" else (y0 + y1) / 2}
                                       for tt, x0, y0, x1, y1 in pts]})
        elif role == "compare":
            fs = 50 if V else 36
            cells = [str(c) for c in t.get("cols", [])] + [str(x) for r in t["rows"] for x in r]
            w_est = (max(len(c) for c in cells) * 3 + 6) * fs * 0.6
            h_est = (len(t["rows"]) + 1 + (1 if t.get("title") else 0)) * fs * 1.6 + fs
            x, y, mw, sc = _place(edit, pdir, fmt, s, at, d, w_est, h_est, min_w=w_est)
            k = min(1.0, mw / w_est) * sc
            L.append({"type": "table", "title": t.get("title"), "cols": t.get("cols", ["", ""]), "rows": t["rows"], "win": t.get("win", []),
                      "accent": acc, "size": int(fs * k), "start": 0, "duration": d, "x": t.get("x", x), "y": t.get("y", y)})
        elif role == "info":
            fs = 40 if V else 34
            txt = (t["sub"] + "\n" if t.get("sub") else "") + t["text"]
            w_est = max(len(l) for l in txt.split("\n")) * fs * 0.6 + fs * 1.6
            h_est = (txt.count("\n") + 1) * fs * 1.3 + fs
            x, y, mw, sc = _place(edit, pdir, fmt, s, at, d, w_est, h_est)
            L.append({"type": "text", "text": txt, "font": "bold", "size": int(fs * sc), "bg": "rgba(16,16,16,.8)", "align": "left",
                      "max_w": mw, "x": x, "y": y, "start": 0, "duration": d, "enter": {"type": "up", "dur": 0.35},
                      "highlight": [{"match": t["hl"], "color": acc}] if t.get("hl") else []})
        elif role == "hf":
            L = [dict(x) for x in t.get("layers", [])]
        else:
            continue
        jid = f"rv-{fmt}-{s['id']}-{k}-{role}"
        sp = {"job_id": jid, "width": W, "height": H, "fps": int(edit.get("fps", 30)), "duration": round(d, 3),
              "background": "transparent", "output": {"path": str(root / f"{jid}.mov"), "format": "mov"}, "layers": L}
        out.append((sp, {"path": str(root / f"{jid}.mov"), "start": at, "dur": d, "role": role, "seg": s["id"]}))
    return out


def _place(edit, pdir, fmt, s, at, d, w, h, min_w=0):
    """cùng bộ chọn vị trí của Review: né mặt/tóc, vật đang nhấn, dải phụ đề (vùng cấm)."""
    from .graphics import _caption_y, _emph_pos
    W, H = FORMATS[fmt]
    cap_h = (54 if fmt == "9x16" else 46) * 1.15 * 2 + 20
    band = None
    if edit.get("subtitles", True):
        cy = _caption_y(edit, pdir, fmt, s, cap_h)
        band = (0, cy - cap_h / 2, W, cy + cap_h / 2)
    return _emph_pos(edit, pdir, fmt, s, at, d, w, h, band, min_w=min_w)


def check(edit: dict, pdir) -> list[tuple[str, str]]:
    from ..hyper import spec as S
    out = []
    any_hf = any(wants(edit, t) for s in edit.get("segments", []) for t in s.get("texts", []))
    if not any_hf:
        return out
    if not ready():
        blocked = [t for s in edit["segments"] for t in s.get("texts", []) if t.get("role") == "hf"]
        if blocked:
            out.append(("error", f"HyperFrames chưa sẵn sàng — {len(blocked)} lớp 'hf' không có phương án tương đương (BỊ CHẶN); "
                                 "chạy python -m thagent.hyper doctor"))
        else:
            out.append(("warn", "HyperFrames chưa sẵn sàng — nhãn/spotlight/bảng dùng bộ vẽ hiện có của Review"))
        return out
    for fmt in edit.get("formats", ["9x16", "16x9"]):
        for sp, it in specs(edit, pdir, fmt):
            s = S.normalize(sp)
            for lv, m in S.validate(s):
                out.append((lv, f"[{fmt}] HyperFrames {it['seg']} ({it['role']}): {m}"))
    return out


def prerender(edit: dict, pdir, fmt: str, progress=print) -> list[dict]:
    if not any(uses(edit, t) for s in edit.get("segments", []) for t in s.get("texts", [])):
        return []
    from ..hyper.job import Job
    items = []
    wd = Path(pdir) / "review" / "hf_jobs"
    for sp, it in specs(edit, pdir, fmt):
        st = Job(sp, wd).run(progress=progress)
        items.append({**it, "path": st["output"], "state": str(wd / sp["job_id"] / "state.json")})
    return items
