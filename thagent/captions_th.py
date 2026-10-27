"""Phụ đề TOÀN BỘ lời nói cho Talking Head — kiểu TỪNG TỪ (theo mẫu người dùng duyệt), app tự thêm.

- Mỗi lần hiện 1 từ / 1 cụm ngắn đúng lúc nói (tiếng Việt ghép từ 2–3 âm tiết liền nhau: "đơn điệu", "chuyên nghiệp",
  "hiệu ứng động"); không hiện cả câu.
- Vị trí: ngay DƯỚI CẰM, giữa khung (dải cổ) — gần mặt, dễ xem. Trong các đoạn MG: KHÔNG phụ đề.
- Có chữ nhấn / callout đang hiện ở dải cổ → phụ đề tạm ẩn (không chồng chữ).
- Chữ trắng, nét vừa (SemiBold), không nền, bóng mờ nhẹ; hiện CẮT THẲNG (không mờ / phóng), đổi từ đúng lúc nói.
- Tắt: plan.captions = False.
"""
from __future__ import annotations

import re
from functools import lru_cache

import cv2
import numpy as np

SIZE = {"v": 74, "h": 60}          # theo mẫu: chữ ~4% chiều cao khung dọc
def _seg_counts(sylls: list[str]) -> list[int] | None:
    """tách từ tiếng Việt (pyvi, MIT): số âm tiết của từng từ — None nếu không có thư viện."""
    try:
        from pyvi import ViTokenizer
    except Exception:
        return None
    clean = [re.sub(r"[^\w%$€£₫]", "", s, flags=re.UNICODE) or "x" for s in sylls]
    toks = ViTokenizer.tokenize(" ".join(clean)).split()
    counts = [t.count("_") + 1 for t in toks]
    return counts if sum(counts) == len(sylls) else None


def _group_vi(tl, fps) -> list[list]:
    counts = _seg_counts([t for _, _, t in tl])
    groups, i = [], 0
    if counts is None:                                 # không tách được → từng âm tiết
        return [[x] for x in tl]
    for n in counts:
        g = tl[i:i + n]
        i += n
        cur = [g[0]]                                   # trong một từ mà ngừng lâu / có dấu câu → tách
        for x in g[1:]:
            if x[0] - cur[-1][1] > fps * 0.25 or cur[-1][2][-1:] in ".,!?;:…":
                groups.append(cur); cur = []
            cur.append(x)
        groups.append(cur)
    return groups


MIN_S = 0.3                         # cụm hiện < 0.3s (chưa kịp đọc) → ghép với cụm sau
MERGE_MAX = 18                      # ký tự tối đa của cụm sau khi ghép (gọn một dòng)


def _merge_short(groups, fps) -> list[list]:
    """cụm quá ngắn ghép với cụm kế tiếp (không qua dấu kết câu / chỗ ngừng dài); cụm cuối câu ngắn ghép ngược vào cụm trước."""
    txt = lambda g: " ".join(x[2] for x in g)
    out, i = [], 0
    while i < len(groups):
        g = list(groups[i])
        while i + 1 < len(groups):
            nxt = groups[i + 1]
            shown = nxt[0][0] - g[0][0]
            ends = g[-1][2][-1:] in ".!?…" or nxt[0][0] - g[-1][1] > fps * 0.5
            if shown >= MIN_S * fps or ends or len(txt(g)) + 1 + len(txt(nxt)) > MERGE_MAX:
                break
            g += nxt
            i += 1
        out.append(g)
        i += 1
    for k in range(len(out) - 1, 0, -1):            # cụm cuối câu vẫn quá ngắn → ghép ngược vào cụm trước nếu vừa
        g, p = out[k], out[k - 1]
        if g[-1][1] - g[0][0] < MIN_S * fps * 0.6 and len(txt(p)) + 1 + len(txt(g)) <= MERGE_MAX \
                and p[-1][2][-1:] not in ".!?…" and g[0][0] - p[-1][1] <= fps * 0.3:
            out[k - 1] = p + g
            del out[k]
    return out


def chunks(plan, words) -> list[tuple[int, int, str]]:
    """[(frame vào, frame ra, chữ)] theo timeline đã cắt — mỗi mục 1 từ / cụm ngắn."""
    from . import timeline as T
    T.build_mapping(plan)
    tl = []
    for w in words or []:
        a = T.src_to_tl(plan, w.source_start)
        if a is None:
            continue
        b = T.src_to_tl(plan, w.source_end)
        tl.append((a, b if b is not None else a + 8, w.text.strip()))
    tl.sort()
    from . import fonts as FT
    vi = FT.current() == "vi"                       # ghép âm tiết thành từ chỉ với tiếng Việt; ngôn ngữ khác: từng từ
    groups = _group_vi(tl, plan.fps) if vi else [[x] for x in tl]
    groups = _merge_short(groups, plan.fps)
    out = []
    for i, g in enumerate(groups):
        a = g[0][0]
        nxt = groups[i + 1][0][0] if i + 1 < len(groups) else plan.duration_frames
        b = min(nxt, g[-1][1] + int(plan.fps * 0.35))
        t = re.sub(r"(\d) ([.,]?\d)", r"\1\2", " ".join(x[2] for x in g))      # số bị chép lời tách: "5 ,500" → "5,500"
        t = re.sub(r"(\d) ([.,]\d)", r"\1\2", t)
        out.append((a, max(b, a + 5), re.sub(r"[.,;:!?…]+$", "", t)))
    return out


@lru_cache(maxsize=512)
def sprite(text: str, V: bool) -> np.ndarray:
    from . import neon as N, fonts as FT
    size = SIZE["v" if V else "h"]
    m = N._mask(FT.shape_line(text), "semi", size)
    pad = 24
    a = np.pad(np.clip(m, 0, 1), pad)
    sh = np.roll(cv2.GaussianBlur(a, (0, 0), 5), 3, 0) * 0.55            # bóng mờ nhẹ, lệch xuống
    out = np.zeros(a.shape + (4,), np.float32)
    out[..., 3] = np.clip(np.maximum(a, sh), 0, 1)
    out[..., :3] = a[..., None]                                            # chữ trắng (premultiplied), bóng = đen
    return out


def neck_y(anchors_tl, a: int, b: int, H: int) -> float:
    fr = [x for x in anchors_tl[max(a, 0):min(b, len(anchors_tl))] if x.get("face_bottom")] or \
         [x for x in anchors_tl if x.get("face_bottom")][::30]
    if not fr:
        return H * 0.55
    fb = float(np.median([x["face_bottom"] for x in fr])) * H
    fh = float(np.median([x["face_h"] for x in fr])) * H
    return fb + max(14.0, fh * 0.06)                # sát cằm như mẫu (cằm ~0.49H → chữ ~0.51H)


def draw(buf: np.ndarray, caps, f: int, anchors_tl=None, busy: bool = False, low: bool = False):
    """vẽ từ / cụm đang nói ngay dưới cằm (giữa khung). busy = đang có chữ nhấn / callout ở dải cổ → không vẽ;
    low = cảnh MG che kín đang chạy → đặt ở dải dưới cùng của khung an toàn (không đè nội dung thẻ giữa khung)."""
    if not caps or busy:
        return
    from .callouts import over
    H, W = buf.shape[:2]
    for a, b, t in caps:
        if a <= f < b:
            spr = sprite(t, H > W)
            if low:
                from .callouts import SAFE_V, SAFE_H
                y = H - (SAFE_V if H > W else SAFE_H)["bottom"] - spr.shape[0] + 24
            else:
                y = neck_y(anchors_tl or [], a, b, H)
            k = 1.0                                         # cắt thẳng như mẫu: không mờ / phóng — nhịp đổi từ đúng lời tạo độ cuốn
            over(buf, spr * k, (W - spr.shape[1]) // 2, int(y - 24))
            return
