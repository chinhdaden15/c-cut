"""QA tự động cho Voice to Motion (skill v1.1). Lỗi “error” chặn bàn giao; “warn” cần xem lại.

- static(tl, transcript)  : kiểm tra không cần dựng (mốc từ, ngắt dòng, câu kết, SFX, camera).
- frames(tl, samples)     : phân tích khung chữ/shape đã vẽ ở các frame mẫu (va chạm TRONG lúc animate, cắt khung,
                            chạm viền, tương phản, cỡ chữ trên điện thoại).
- scan(tl, step)          : dựng frame (không mã hoá video) để lấy mẫu → frames(); dùng được khi chưa render.
- determinism(tl)         : cùng một frame dựng 2 lần phải giống hệt.
"""
from __future__ import annotations

import math

import numpy as np

from . import audio as A, render as R, vtext as VT

SAFE = {"x0": 60, "x1": 1020, "y0": 150, "y1": 1600}   # vùng an toàn dọc 9:16 (chừa thanh UI nền tảng)
READ_CPS = 14.0                                         # tốc độ đọc màn hình ~14 ký tự/giây (tiếng Việt có dấu)


def _texts(tl):
    for oid, o in tl.objs.items():
        if o["type"] == "text":
            yield oid, o


def static(tl: R.Timeline, transcript: dict | None = None) -> list[tuple[str, str]]:
    out = []
    # 1) mốc từng từ phải khớp số từ (thiếu → từ cuối hiện sớm/lẻ)
    for oid, o in _texts(tl):
        wt = o.get("word_times")
        if wt is not None:
            n = len(o["text"].split())
            if len(wt) != n:
                out.append(("error", f"{oid}: {n} từ nhưng {len(wt)} mốc word_times — từ thiếu mốc sẽ hiện lệch nhịp"))
            if any(b < a - 1e-6 for a, b in zip(wt, wt[1:])):
                out.append(("error", f"{oid}: word_times không tăng dần"))
    # 2) ngắt dòng theo nghĩa
    for oid, o in _texts(tl):
        if o.get("max_w"):
            keep = tuple(o.get("keep", [])) + (((o.get("highlight") or {}).get("match"),) if (o.get("highlight") or {}).get("match") else ())
            for m in VT.layout_issues(o["text"], o.get("font", "display"), int(o.get("size", 64)), float(o["max_w"]), keep):
                out.append(("error" if "giữ liền" in m else "warn", f"{oid}: {m}"))
    # 3) câu kết: hoàn tất sớm, đủ thời gian đọc
    last = tl.scenes[-1]
    keys = [o for o in last.get("objects", []) if o["type"] == "text" and float(o.get("size", 0)) >= 56]
    for o in keys:
        ev = [e for e in tl.events.get(o["id"], []) if e["action"] == "reveal"]
        t_done = max([e.get("end_s", e["start_s"]) for e in ev] + [max(o.get("word_times") or [0]) + 0.3])
        need = max(1.6, len(o["text"]) / READ_CPS)
        have = tl.duration - t_done
        if have < need - 0.05:
            out.append(("error", f"câu kết {o['id']} hoàn tất lúc {t_done:.2f}s, chỉ còn {have:.2f}s để đọc (cần ≥ {need:.1f}s)"))
    # 4) mọi chữ chính có đủ thời gian đọc trước khi biến mất
    for oid, o in _texts(tl):
        v0, v1 = o["_vis"]
        ev = [e for e in tl.events.get(oid, []) if e["action"] == "reveal"]
        t_done = max([e.get("end_s", e["start_s"]) for e in ev] + [max(o.get("word_times") or [v0]) + 0.3])
        need = max(0.9, len(o["text"]) / READ_CPS)
        if v1 < tl.duration and (v1 - t_done) < need - 0.05 and not o.get("fixed") and o.get("role") != "caption":
            out.append(("warn", f"{oid} “{o['text'][:28]}” chỉ đọc được {v1 - t_done:.2f}s (cần ≈ {need:.1f}s)"))
    # 5) SFX: vai trò rõ, không lặp một âm cho mọi hành động, không dày đặc
    ev = [(float(e["t"]), e.get("role") or e.get("sfx", "?")) for sc in tl.scenes for e in sc.get("audio_events", [])]
    if tl.theme.get("sfx_auto", True):
        from .sfxkit import auto_events
        ev += [(float(e["t"]), e["role"]) for e in auto_events(tl)]
    ev = sorted(ev)
    if ev:
        from collections import Counter
        c = Counter(n.rsplit("_", 1)[0] for _, n in ev)
        top, k = c.most_common(1)[0]
        if k > max(4, 0.45 * len(ev)):
            out.append(("warn", f"SFX “{top}*” dùng {k}/{len(ev)} lần — đa dạng theo vai trò (click điểm đến, whoosh chuyển vùng, impact thông điệp)"))
        for (a, na), (b, nb) in zip(ev, ev[1:]):
            if b - a < 0.12:
                out.append(("warn", f"hai SFX sát nhau {a:.2f}s/{b:.2f}s ({na}, {nb})"))
        dens = len(ev) / max(tl.duration, 1)
        if dens > 0.9:
            out.append(("warn", f"mật độ SFX {dens:.2f}/giây — quá dày"))
    # 6) camera: vận tốc không đổi đột ngột ngoài chủ đích
    out += camera_jerk(tl)
    # 8) nhịp hình theo lời: không đứng im quá 3s, không khung trống
    out += rhythm(tl)
    # 7) nhãn bản đồ cỡ cố định nên có mức chi tiết (lod) để không tụ lại khi zoom xa
    has_map = any(o["type"] in ("map", "geo", "region") for o in tl.objs.values())
    if has_map:
        nolod = [oid for oid, o in _texts(tl) if o.get("fixed") and not o.get("lod") and not o.get("parent")]
        if nolod:
            out.append(("warn", f"{len(nolod)} nhãn bản đồ không có lod (vd {', '.join(nolod[:4])}) — sẽ hiện ở mọi mức zoom"))
    return out


HOLD_MAX = 3.0     # tối đa giây không có thay đổi hình (trừ đoạn giữ câu kết)
END_HOLD = 4.0


def _bg_obj(o) -> bool:
    """lớp nền/phụ không tính là “thay đổi hình”: bản đồ nền, phủ nền, nguồn, phụ đề chạy chữ."""
    return o["type"] in ("map", "geo") or o.get("role") in ("caption", "backdrop", "source") or o.get("id") == "src"


def rhythm(tl) -> list[tuple[str, str]]:
    """lỗi chặn: (a) khoảng > HOLD_MAX giây không có hành động hình nào (hiện/ẩn/biến đổi/vẽ/đếm/camera/chuyển cảnh)
    — phụ đề chạy chữ không tính; (b) khung trống (không có khối nội dung nào) > 0,8s."""
    out = []
    ts = [0.0] + [float(sc["start_s"]) for sc in tl.scenes]
    for oid, evs in tl.events.items():
        o = tl.objs.get(oid)
        if o is None or _bg_obj(o):
            continue
        ts += [float(e["start_s"]) for e in evs]
    for k in tl.camera:
        ts += [float(k["t"]) - float(k.get("dur", 0.6)), float(k["t"])]
    for oid, o in tl.objs.items():          # lớp HyperFrames: lớp con hiện/ẩn bên trong cũng là hành động hình (theo spec)
        if o["type"] == "hf":
            v0 = o["_vis"][0]
            sp = o.get("spec") or {}
            for sc in sp.get("scenes") or [{"start": 0, "layers": sp.get("layers", [])}]:
                for L in sc.get("layers", []):
                    if L.get("type") == "shape" and not L.get("keyframes"):
                        continue
                    a0 = v0 + float(sc.get("start", 0)) + float(L.get("start", 0))
                    ts += [a0] + ([a0 + float(L["duration"])] if L.get("duration") else [])
    ts = sorted(t for t in ts if 0 <= t <= tl.duration)
    end = tl.duration - END_HOLD
    for a, b in zip(ts, ts[1:] + [tl.duration]):
        b = min(b, max(end, a))
        if b - a > HOLD_MAX + 1e-3:
            out.append(("error", f"hình đứng im {b - a:.1f}s ({a:.1f}–{b:.1f}s) — thêm nhịp theo lời: khối mới, đổi trạng thái, camera (≤ {HOLD_MAX:.0f}s)"))
    def _shown(oid, o):   # đường chỉ có “draw” (chưa reveal) thì chỉ thấy từ lúc bắt đầu vẽ
        evs = tl.events.get(oid, [])
        if not any(e["action"] == "reveal" for e in evs):
            d = [float(e["start_s"]) for e in evs if e["action"] == "draw"]
            if d:
                return max(o["_vis"][0], min(d)), o["_vis"][1]
        return o["_vis"]
    vis = sorted(_shown(k, o) for k, o in tl.objs.items() if not _bg_obj(o))
    t, cover = 0.0, []
    for a, b in vis:
        if a > t + 0.8 and a < tl.duration:
            cover.append((t, a))
        t = max(t, b)
    if t < tl.duration - 0.8:
        cover.append((t, tl.duration))
    for a, b in cover:
        out.append(("error", f"khung trống {a:.1f}–{b:.1f}s — không có khối nội dung nào trên hình"))
    return out


def camera_jerk(tl) -> list[tuple[str, str]]:
    fps = tl.fps
    n = int(tl.duration * fps)
    pos = np.array([R.camera_at(tl, f / fps) for f in range(n)])
    if len(pos) < 4:
        return []
    z = pos[:, 2]
    # vận tốc màn hình ≈ dịch chuyển tâm × zoom + đổi zoom (log)
    v = np.hypot(np.diff(pos[:, 0]) * z[1:], np.diff(pos[:, 1]) * z[1:]) + np.abs(np.diff(np.log(np.maximum(z, 1e-6)))) * 900
    a = np.abs(np.diff(v))
    bad = np.where(a > np.maximum(18, 0.6 * np.maximum(v[1:], v[:-1])))[0]
    out = []
    last = -99
    for i in bad:
        if i - last > fps // 2:
            out.append(("warn", f"camera đổi vận tốc đột ngột quanh {i / fps:.2f}s (Δ{a[i]:.0f}px/frame)"))
            last = i
    return out[:8]


def _inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0]); h = min(a[3], b[3]) - max(a[1], b[1])
    return max(w, 0) * max(h, 0)


def _area(a):
    return max(a[2] - a[0], 0) * max(a[3] - a[1], 0)


def frames(tl, samples: list[tuple[float, list[dict]]]) -> list[tuple[str, str]]:
    """samples: [(t, boxes)] — boxes do Renderer ghi khi vẽ."""
    W, H = tl.W, tl.H
    found: dict[tuple, list[float]] = {}

    def add(key, t):
        found.setdefault(key, []).append(t)
    for t, boxes in samples:
        inside = lambda b: b["box"][2] > 0 and b["box"][0] < W and b["box"][3] > 0 and b["box"][1] < H
        txt = [b for b in boxes if b["kind"] == "text" and b["op"] > 0.6 and inside(b)]   # nằm hẳn ngoài khung = không hiện
        shp = [b for b in boxes if b["kind"] == "shape" and b["op"] > 0.6]
        for i, a in enumerate(txt):
            x0, y0, x1, y1 = a["box"]
            if x0 < -2 or y0 < -2 or x1 > W + 2 or y1 > H + 2:
                add(("error", "cắt", a["id"], a["text"]), t)
            elif x0 < tl.safe[0] or x1 > tl.safe[2] or y0 < tl.safe[1] or y1 > tl.safe[3]:
                add(("warn", "an toàn", a["id"], a["text"]), t)
            if a["px"] < 22:
                add(("warn", "nhỏ", a["id"], a["text"]), t)
            if a["contrast"] < 2.0:
                add(("error", "tương phản", a["id"], a["text"]), t)
            elif a["contrast"] < (3.0 if a["px"] >= 40 else 4.5):
                add(("warn", "tương phản", a["id"], a["text"]), t)
            for b in txt[i + 1:]:
                if b["id"] == a["id"]:
                    continue
                ov = _inter(a["box"], b["box"])
                if ov > 0.06 * min(_area(a["box"]), _area(b["box"])):
                    add(("error", "chồng", a["id"] + " × " + str(b["id"]), a["text"] + " / " + b["text"]), t)
            for s in shp:
                if s["id"] == a["id"]:
                    continue
                ov = _inter(a["box"], s["box"])
                if 0 < ov < 0.97 * _area(a["box"]) and ov > 0.04 * _area(a["box"]):   # chữ nằm vắt qua viền shape
                    add(("error", "chạm viền", f"{a['id']} × {s['id']}", a["text"]), t)
    out = []
    step = (samples[1][0] - samples[0][0]) if len(samples) > 1 else 0.2
    for (lvl, kind, oid, text), ts in sorted(found.items(), key=lambda kv: kv[1][0]):
        if lvl == "error" and kind in ("chồng", "chạm viền", "cắt") and len(ts) < 2:
            lvl = "warn"   # chỉ 1 mẫu: chạm thoáng qua lúc đang chuyển động — xem lại bằng mắt
        msg = {"cắt": "chữ bị cắt khỏi khung", "an toàn": "chữ ra ngoài vùng an toàn", "nhỏ": "chữ < 22px trên điện thoại",
               "tương phản": "tương phản chữ/nền thấp", "chồng": "chữ chồng nhau", "chạm viền": "chữ vắt qua viền shape"}[kind]
        out.append((lvl, f"{msg}: {oid} “{text[:40]}” {ts[0]:.2f}–{ts[-1]:.2f}s"))
    return out


def scan(tl, step: float = 0.2, progress=None) -> list[tuple[float, list[dict]]]:
    Rr = R.Renderer(tl)
    samples = []
    n = int(tl.duration / step)
    for i in range(n + 1):
        t = min(i * step, tl.duration - 1 / tl.fps)
        Rr.frame(t, t - 1 / tl.fps)
        samples.append((t, list(Rr.boxes)))
        if progress and i % 25 == 0:
            progress(f"qa scan {i}/{n}")
    return samples


def determinism(tl, t: float | None = None) -> list[tuple[str, str]]:
    t = tl.duration * 0.53 if t is None else t
    a = R.still(tl, t)               # renderer đã dựng video
    b = R.still(tl, t, fresh=True)   # renderer mới hoàn toàn → phải ra đúng frame đó
    if not np.array_equal(a, b):
        return [("error", f"frame {t:.2f}s dựng 2 lần cho kết quả khác nhau — animation không tất định")]
    return []
