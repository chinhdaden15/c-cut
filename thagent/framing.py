"""Cỡ cảnh (framing) cho video một người nói: đổi rộng / trung / cận ở chỗ NGẮT CÂU, như quay nhiều máy — bớt nhàm, che jump cut.

plan.framing:
  None (mặc định) → app tự chia: mỗi 3–6s đổi cỡ ở khoảng lặng giữa câu / cụm (≥ 4 frame), hai cảnh liền nhau khác cỡ,
                    cận không nối cận; tránh đoạn MG phủ khung, chữ khổng lồ sau lưng và callout có zoom (đã tự zoom riêng).
  []              → tắt (giữ một cỡ suốt video).
  [{"at": frame timeline, "size": "wide" | "medium" | "close"}, …] → tự đặt (cắt đúng frame `at`, nên đặt ở khoảng lặng).
Tâm phóng = mặt nhân vật (trung vị trong cảnh) → mặt đứng yên chỗ cũ, khung siết lại quanh mặt.
"""
from __future__ import annotations

SIZES = {"wide": 1.0, "medium": 1.14, "close": 1.30}
_SHOTS: dict[int, list[tuple[int, int, float, float, float]]] = {}   # id(plan) → [(start, end, z, cx, cy)]
MIN_S, MAX_S, HARD_MAX_S = 3.0, 6.0, 8.0


def _face(anchors_tl, a, b):
    xs, ys = [], []
    for an in anchors_tl[max(0, a):max(a + 1, b)]:
        fc = an.get("face") if an else None
        if fc:
            xs.append(fc[0] + fc[2] / 2)
            ys.append(fc[1] + fc[3] / 2)
    if not xs:
        return 0.5, 0.32
    xs.sort(); ys.sort()
    return xs[len(xs) // 2], ys[len(ys) // 2]


def _blocked(plan) -> list[tuple[int, int]]:
    """khoảng không được cắt đổi cỡ (đã có zoom / MG riêng), nới ±8 frame."""
    from . import mg2 as MG2
    out = [(a - 8, b + 8) for a, b in MG2.covers(plan)]
    for st in getattr(plan, "stage", None) or []:
        if st.get("enabled", True):
            out.append((int(st["start"]) - 8, int(st["end"]) + 8))
    for co in getattr(plan, "callouts", None) or []:
        if co.get("enabled", True) and co.get("zoom"):
            out.append((int(co["start"]) - 8, int(co["start"]) + 20))
    return out


def auto(plan, words, anchors_tl) -> list[dict]:
    from . import timeline as T
    fps, D = plan.fps, plan.duration_frames
    ws = []
    for w in words or []:
        a, b = T.src_to_tl(plan, w.source_start), T.src_to_tl(plan, w.source_end)
        if a is not None and b is not None:
            ws.append((a, b, w.text))
    ws.sort()
    strong, weak = [], []                     # strong: khoảng lặng / hết câu; weak: ranh giới từ (nguồn đã cắt sát, nói liền)
    for (a0, b0, t0), (a1, b1, t1) in zip(ws, ws[1:]):
        gap = a1 - b0
        if gap >= 4 or (gap >= 2 and t0.rstrip()[-1:] in ".?!,;:"):
            strong.append((b0 + a1) // 2)
        elif gap >= 0:
            weak.append(a1)                        # cắt đúng frame đầu từ kế tiếp
    blocked = _blocked(plan)
    keep = lambda cs: [c for c in cs if not any(x <= c <= y for x, y in blocked) and 1.5 * fps < c < D - 2 * fps]
    strong, weak = keep(strong), keep(weak)
    cuts, cur = [], 0
    while True:
        win = [c for c in strong if cur + MIN_S * fps <= c <= cur + MAX_S * fps] or \
              [c for c in weak if cur + MIN_S * fps <= c <= cur + MAX_S * fps]
        if not win:
            win = [c for c in strong + weak if cur + MAX_S * fps < c <= cur + HARD_MAX_S * fps]
            win = sorted(win)[:1]
        if not win:
            nxt = sorted(c for c in strong + weak if c > cur + MIN_S * fps)
            if not nxt:
                break
            win = nxt[:1]
        c = min(win, key=lambda x: abs(x - (cur + 4.5 * fps)))   # gần ~4.5s nhất
        cuts.append(c)
        cur = c
    seq = ["medium", "wide", "close", "medium", "close", "wide"]
    seed = sum(map(ord, getattr(plan, "recipe", "") or "x")) % len(seq)
    out, prev = [{"at": 0, "size": "medium"}], "medium"
    for i, c in enumerate(cuts):
        s = seq[(seed + i + 1) % len(seq)]
        if s == prev or (s == "close" and prev == "close"):
            s = "wide" if prev != "wide" else "medium"
        out.append({"at": int(c), "size": s})
        prev = s
    return out


def prepare(plan, words, anchors_tl) -> list[dict]:
    fr = getattr(plan, "framing", None)
    shots = auto(plan, words, anchors_tl) if fr is None else list(fr)
    shots = sorted([s for s in shots if s.get("size") in SIZES], key=lambda s: int(s["at"]))
    D = plan.duration_frames
    seg = []
    for i, s in enumerate(shots):
        a = int(s["at"])
        b = int(shots[i + 1]["at"]) if i + 1 < len(shots) else D
        if b <= a:
            continue
        cx, cy = _face(anchors_tl, a, b)
        seg.append((a, b, SIZES[s["size"]], float(s.get("cx", cx)), float(s.get("cy", cy))))
    _SHOTS[id(plan)] = seg
    return shots


def at(plan, f: int) -> tuple[float, float, float]:
    for a, b, z, cx, cy in _SHOTS.get(id(plan), ()):
        if a <= f < b:
            return z, cx, cy
    return 1.0, 0.5, 0.4


def cuts(plan) -> list[int]:
    return [a for a, *_ in _SHOTS.get(id(plan), ())[1:]]
