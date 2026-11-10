"""Kiểu khung hình cho video một người nói (Talking Head) — ngoài đổi cỡ cảnh (framing.py). Học từ ghost-editor
(Seoul list: cảnh thu vào thẻ; Product page: người nói trên thẻ bo góc; Whiteboard: chia đôi bảng / mặt) và EditAtlas
("ease the camera back from the bottom edge with a blurred fill").

plan.layouts = [{"kind": "card" | "split" | "pullback", "start": frame, "end": frame, …}]
  card      cảnh quay thu vào một THẺ bo góc ở trên (giữ mặt + ngực, ~80% bề ngang), nền là bản mờ tối của chính cảnh → nửa dưới
            trống cho MG / chữ (bento, so sánh, danh sách). y: tâm thẻ 0..1 (mặc định 0.34); scale 0.80; band [0.08, 0.62] dải nguồn giữ lại
  split     chia đôi: TẤM PANEL phía trên (đồ hoạ / bảng), mặt người nói dời xuống nửa dưới. color: màu panel (mặc định kính tối),
            seam: mép dưới panel 0..1 (mặc định 0.47)
  pullback  lùi khung từ mép dưới (thu nhỏ ~82%), lấp phần trên bằng bản mờ của chính cảnh → chừa chỗ TRÊN ĐẦU cho chữ lớn
Vào / ra mượt 10 frame (expo). Trong lúc khung đổi, chữ nhấn / callout / sân khấu (vốn đặt theo khung thường) tạm ẩn,
phụ đề xuống dải dưới; đặt MG2 kiểu chồng (bg "none") vào vùng trống của khung đó.
"""
from __future__ import annotations

import math

import cv2
import numpy as np

KINDS = {"card", "split", "pullback"}
EASE_F = 10


def _ease(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return 1 - math.pow(2, -10 * u) if u < 1 else 1.0


def at(plan, f: int):
    """(layout, k 0..1) đang hiệu lực ở frame f, hoặc (None, 0)."""
    for L in getattr(plan, "layouts", None) or []:
        if not L.get("enabled", True) or L.get("kind") not in KINDS:
            continue
        a, b = int(L["start"]), int(L["end"])
        if a <= f < b:
            k = min(_ease((f - a + 1) / EASE_F), _ease((b - f) / EASE_F))
            return L, k
    return None, 0.0


def _blur_bg(img: np.ndarray, dim: float = 0.45) -> np.ndarray:
    h, w = img.shape[:2]
    small = cv2.resize(img, (w // 8, h // 8), interpolation=cv2.INTER_AREA)
    small = cv2.GaussianBlur(small, (0, 0), 6)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR) * (1 - dim)


def _round_mask(w: int, h: int, r: int) -> np.ndarray:
    m = np.zeros((h, w), np.float32)
    r = max(1, min(r, w // 2, h // 2))
    cv2.rectangle(m, (r, 0), (w - r, h), 1.0, -1)
    cv2.rectangle(m, (0, r), (w, h - r), 1.0, -1)
    for cx, cy in ((r, r), (w - r, r), (r, h - r), (w - r, h - r)):
        cv2.circle(m, (cx, cy), r, 1.0, -1, cv2.LINE_AA)
    return cv2.GaussianBlur(m, (0, 0), 1.0)


def apply(plan, f: int, base: np.ndarray, alpha: np.ndarray):
    """→ (base, alpha, layout | None, k). base float RGB 0..1, alpha float 0..1, cùng kích thước khung xuất."""
    L, k = at(plan, f)
    if L is None or k <= 0.001:
        return base, alpha, None, 0.0
    H, W = base.shape[:2]
    kind = L["kind"]
    if kind == "pullback":
        s = 1 - (1 - float(L.get("scale", 0.82))) * k
        M = np.float32([[s, 0, (1 - s) * W / 2], [0, s, (1 - s) * H]])        # neo mép DƯỚI giữa
        bg = _blur_bg(base, 0.5)
        fg = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        m = cv2.warpAffine(np.ones((H, W), np.float32), M, (W, H), flags=cv2.INTER_LINEAR)[..., None]
        return bg * (1 - m) + fg * m, cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_LINEAR), L, k
    if kind == "card":
        # thẻ giữ phần MẶT + NGỰC (dải nguồn y 8%–62%, ~4:5) thu còn ~80% bề ngang, đặt ở trên; vào / ra nội suy từ khung đầy
        s = 1 - (1 - float(L.get("scale", 0.80))) * k
        b0, b1 = float(L.get("band", [0.08, 0.62])[0]) * k, 1 - (1 - float(L.get("band", [0.08, 0.62])[1])) * k
        cy = 0.5 + (float(L.get("y", 0.34)) - 0.5) * k
        tx = (1 - s) * W / 2
        ty = cy * H - s * (b0 + b1) / 2 * H
        M = np.float32([[s, 0, tx], [0, s, ty]])
        bg = _blur_bg(base, 0.55)
        fg = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        x0, y0 = int(round(tx)), int(round(ty + s * b0 * H))
        cw, ch = int(round(s * W)), int(round(s * (b1 - b0) * H))
        rm = np.zeros((H, W), np.float32)
        r = int(56 * k * W / 1080)
        mm = _round_mask(max(2, cw), max(2, ch), r)
        ya, yb, xa, xb = max(0, y0), min(H, y0 + ch), max(0, x0), min(W, x0 + cw)
        if yb > ya and xb > xa:
            rm[ya:yb, xa:xb] = mm[ya - y0:yb - y0, xa - x0:xb - x0]
        sh = cv2.GaussianBlur(np.roll(rm, int(24 * W / 1080), axis=0), (0, 0), 28 * W / 1080) * 0.55 * k   # bóng đổ mềm
        bg = bg * (1 - sh[..., None])
        out = bg * (1 - rm[..., None]) + fg * rm[..., None]
        edge = np.clip(cv2.dilate(rm, np.ones((3, 3), np.uint8)) - rm, 0, 1)[..., None] * 0.25 * k      # viền sáng mảnh
        out = out + (1 - out) * edge
        a2 = cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_LINEAR) * rm
        return out, a2, L, k
    if kind == "split":
        seam = float(L.get("seam", 0.47))
        ty = seam * H * 0.72 * k                       # dời cảnh xuống để mặt nằm dưới mép panel
        M = np.float32([[1, 0, 0], [0, 1, ty]])
        fg = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        a2 = cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_LINEAR)
        ph = int(round(seam * H * k))
        col = L.get("color")
        if col:
            c = np.array([int(col.lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
            panel = np.broadcast_to(c, (ph, W, 3)).copy()
        else:                                          # kính tối: bản mờ của cảnh + phủ tối
            panel = _blur_bg(base, 0.7)[:ph] if ph else np.zeros((0, W, 3), np.float32)
        out = fg.copy()
        if ph > 0:
            out[:ph] = panel
            g = min(ph, int(6 * W / 1080))
            out[ph - g:ph] = out[ph - g:ph] * 0.6 + 0.4               # đường seam sáng mảnh
            a2[:ph] = 0
        return out, a2, L, k
    return base, alpha, None, 0.0


def check(plan, fps: int) -> list[tuple[str, str]]:
    out = []
    for L in getattr(plan, "layouts", None) or []:
        if L.get("kind") not in KINDS:
            out.append(("error", f"layout {L.get('kind')}: không có (card | split | pullback)")); continue
        d = (int(L["end"]) - int(L["start"])) / fps
        if d < 1.2:
            out.append(("warn", f"layout {L['kind']} {L['start']}: chỉ {d:.1f}s — đổi khung quá nhanh"))
    tot = sum((int(L["end"]) - int(L["start"])) for L in getattr(plan, "layouts", None) or [])
    if plan.duration_frames and tot / plan.duration_frames > 0.35:
        out.append(("warn", f"khung card / split / pullback chiếm {tot / plan.duration_frames:.0%} thời lượng — mặt người nói nên giữ khung thường ≥ 65%"))
    return out
