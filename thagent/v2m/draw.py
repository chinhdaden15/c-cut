"""Sprite RGBA (float32, premultiplied) cho từng loại đối tượng + hàm ghép lên khung.

Mọi sprite là hàm thuần của tham số (có cache) → dựng lại cùng timeline luôn ra cùng hình.
"""
from __future__ import annotations

import math
import unicodedata
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .. import imgio
from ..paths import ROOT

FONT_DIR = ROOT / "assets" / "fonts"
# vai trò font → (file, trọng lượng nếu là variable font)
FONTS = {
    "black": ("Montserrat-VF.ttf", 900),
    "display": ("Montserrat-VF.ttf", 800),
    "bold": ("Montserrat-VF.ttf", 700),
    "semi": ("Montserrat-VF.ttf", 600),
    "medium": ("Montserrat-VF.ttf", 500),
    "light": ("Montserrat-VF.ttf", 400),
    "body": ("BeVietnamPro-Medium.ttf", None),
    "body_bold": ("BeVietnamPro-Bold.ttf", None),
    "serif_italic": ("PlayfairDisplay-Italic-VF.ttf", 600),
    "hand": ("DancingScript-VF.ttf", 700),
}


def rgb(c) -> np.ndarray:
    if isinstance(c, (list, tuple)):
        return np.array(c[:3], np.float32) / (255.0 if max(c[:3]) > 1 else 1.0)
    c = c.lstrip("#")
    return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


@lru_cache(maxsize=128)
def font(role: str, size: int) -> ImageFont.FreeTypeFont:
    fname, w = FONTS.get(role, FONTS["display"])
    f = ImageFont.truetype(str(FONT_DIR / fname), max(int(size), 4))
    if w is not None:
        try:
            f.set_variation_by_axes([w])
        except Exception:
            pass
    return f


def _premul(mask: np.ndarray, color) -> np.ndarray:
    out = np.zeros(mask.shape + (4,), np.float32)
    out[..., :3] = rgb(color) * mask[..., None]
    out[..., 3] = mask
    return out


def _shadow(spr: np.ndarray, blur: float, alpha: float, dy: float) -> np.ndarray:
    """bóng đổ mềm phía dưới sprite (sprite đã có lề đủ rộng)."""
    if alpha <= 0:
        return spr
    a = cv2.GaussianBlur(spr[..., 3], (0, 0), max(blur, 0.5)) * alpha
    a = np.roll(a, int(dy), axis=0)
    out = np.zeros_like(spr)
    out[..., 3] = a
    return over(out, spr)


def over(bot: np.ndarray, top: np.ndarray) -> np.ndarray:
    return top + bot * (1 - top[..., 3:4])


# ---------------- chữ ----------------
def wrap(text: str, role: str, size: int, max_w: float | None, spacing: float = 0) -> list[list[str]]:
    """xuống dòng theo max_w; "\n" trong chữ = xuống dòng chủ động (để ngắt cụm cho đẹp)."""
    f = font(role, size)
    lines = []
    for para in text.split("\n"):
        words = para.split()
        if not max_w:
            lines.append(words)
            continue
        cur = []
        for w in words:
            t = " ".join(cur + [w])
            if cur and f.getlength(t) + spacing * len(t) > max_w:
                lines.append(cur); cur = [w]
            else:
                cur.append(w)
        lines.append(cur)
    return [ln for ln in lines if ln] or [[]]


@lru_cache(maxsize=1024)
def text_layout(text: str, role: str, size: int, max_w: float, align: str, line_h: float, spacing: float):
    """vị trí từng từ (x, y, w) trong khối chữ + kích thước khối. Gốc (0,0) = góc trên trái khối."""
    text = unicodedata.normalize("NFC", text)
    f = font(role, size)
    lines = wrap(text, role, size, max_w or None, spacing)
    sp = f.getlength(" ")
    lh = size * line_h
    widths = [sum(f.getlength(w) + spacing * len(w) for w in ln) + sp * (len(ln) - 1) for ln in lines]
    W = max(widths) if widths else 0
    words = []
    for li, (ln, lw) in enumerate(zip(lines, widths)):
        x = {"left": 0, "right": W - lw}.get(align, (W - lw) / 2)
        for w in ln:
            ww = f.getlength(w) + spacing * len(w)
            words.append((w, x, li * lh, ww))
            x += ww + sp
    return words, W, lh * len(lines)


@lru_cache(maxsize=2048)
def word_sprite(word: str, role: str, size: int, color: str, spacing: float, shadow: float,
                stroke: int = 0, stroke_color: str = "#000000") -> tuple[np.ndarray, int, int]:
    """sprite một từ + (ox, oy): độ lệch từ góc sprite tới gốc chữ (đỉnh dòng)."""
    f = font(role, size)
    pad = int(size * 0.45) + stroke + 2
    asc, desc = f.getmetrics()
    w = int(f.getlength(word) + spacing * len(word)) + 2 * pad
    h = asc + desc + 2 * pad
    im = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(im)
    if spacing:
        x = pad
        for ch in word:
            d.text((x, pad), ch, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
            x += f.getlength(ch) + spacing
    else:
        d.text((pad, pad), word, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    m = np.asarray(im, np.float32) / 255
    spr = _premul(m, color)
    if stroke:
        im2 = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im2).text((pad, pad), word, font=f, fill=255)
        inner = np.asarray(im2, np.float32) / 255
        spr = over(_premul(m, stroke_color), _premul(inner, color))
    if shadow:
        spr = _shadow(spr, size * 0.08, shadow, size * 0.06)
    return spr, pad, pad


# ---------------- hình ----------------
def _rrect_mask(w: int, h: int, r: float, ss: int = 2) -> np.ndarray:
    W, H, R = w * ss, h * ss, int(max(0, min(r, w / 2, h / 2)) * ss)
    m = np.zeros((H, W), np.uint8)
    if R <= 0:
        m[:] = 255
    else:
        cv2.rectangle(m, (R, 0), (W - R - 1, H - 1), 255, -1)
        cv2.rectangle(m, (0, R), (W - 1, H - R - 1), 255, -1)
        for cx, cy in ((R, R), (W - R - 1, R), (R, H - R - 1), (W - R - 1, H - R - 1)):
            cv2.circle(m, (cx, cy), R, 255, -1, cv2.LINE_AA)
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


@lru_cache(maxsize=256)
def rect_sprite(w: int, h: int, r: float, fill: str | None, stroke: str | None, stroke_w: int,
                shadow: float, gradient: str | None = None) -> tuple[np.ndarray, int]:
    """thẻ bo góc (+ viền, bóng, chuyển màu dọc). Trả (sprite, lề)."""
    w, h = max(int(w), 2), max(int(h), 2)
    pad = int(max(w, h) * 0.06 + 24) if shadow else stroke_w + 2
    m = _rrect_mask(w, h, r)
    out = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.float32)
    if fill:
        col = np.empty((h, w, 3), np.float32)
        if gradient:
            g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
            col[:] = rgb(fill) * (1 - g) + rgb(gradient) * g
        else:
            col[:] = rgb(fill)
        out[pad:pad + h, pad:pad + w, :3] = col * m[..., None]
        out[pad:pad + h, pad:pad + w, 3] = m
    if stroke and stroke_w:
        inner = _rrect_mask(max(w - 2 * stroke_w, 1), max(h - 2 * stroke_w, 1), max(r - stroke_w, 0))
        ring = m.copy()
        ring[stroke_w:h - stroke_w, stroke_w:w - stroke_w] -= inner[:h - 2 * stroke_w, :w - 2 * stroke_w] if h > 2 * stroke_w and w > 2 * stroke_w else 0
        ring = np.clip(ring, 0, 1)
        s = _premul(ring, stroke)
        out[pad:pad + h, pad:pad + w] = over(out[pad:pad + h, pad:pad + w], s)
    if shadow:
        out = _shadow(out, max(w, h) * 0.035 + 6, shadow, max(h * 0.03, 6))
    return out, pad


@lru_cache(maxsize=256)
def circle_sprite(r: int, fill: str | None, stroke: str | None, stroke_w: int, shadow: float) -> tuple[np.ndarray, int]:
    return rect_sprite(2 * r, 2 * r, r, fill, stroke, stroke_w, shadow)


@lru_cache(maxsize=64)
def _image(path: str) -> np.ndarray:
    im = imgio.must_read(path)
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    if im.shape[2] == 4:
        a = im[..., 3:4].astype(np.float32) / 255
        rgbim = cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2RGB).astype(np.float32) / 255
        return np.concatenate([rgbim * a, a], -1)
    rgbim = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    return np.concatenate([rgbim, np.ones(rgbim.shape[:2] + (1,), np.float32)], -1)


@lru_cache(maxsize=96)
def image_sprite(path: str, w: int, h: int, r: float, fit: str, shadow: float, stroke: str | None,
                 stroke_w: int, gray: bool, kb: tuple = (1.0, 0.0, 0.0), dim: float = 0.0) -> tuple[np.ndarray, int]:
    """kb = (zoom ≥ 1, lệch x, lệch y theo −1..1 phần dư) — zoom/trượt chậm bên trong khung (Ken Burns); dim = làm tối ảnh nền."""
    src = _image(path)
    ih, iw = src.shape[:2]
    w, h = max(int(w), 2), max(int(h), 2)
    z, kx, ky = kb
    s = (max(w / iw, h / ih) * max(z, 1.0)) if fit == "cover" else min(w / iw, h / ih)
    canvas = np.zeros((h, w, 4), np.float32)
    if fit == "cover":
        # cắt vùng nguồn trước rồi mới resize (nhanh, nét)
        cw, ch = w / s, h / s
        cx = iw / 2 + kx * (iw - cw) / 2
        cy = ih / 2 + ky * (ih - ch) / 2
        M = np.array([[s, 0, w / 2 - s * cx], [0, s, h / 2 - s * cy]], np.float32)
        canvas[:] = cv2.warpAffine(src, M, (w, h), flags=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REPLICATE)
    else:   # contain: cả ảnh nằm gọn trong khung
        im = cv2.resize(src, (max(int(iw * s), 1), max(int(ih * s), 1)), interpolation=cv2.INTER_AREA)
        oy, ox = (h - im.shape[0]) // 2, (w - im.shape[1]) // 2
        canvas[oy:oy + im.shape[0], ox:ox + im.shape[1]] = im
    if gray:
        g = canvas[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
        canvas[..., :3] = g[..., None]
    if dim:
        canvas[..., :3] *= 1 - dim
    m = _rrect_mask(w, h, r)
    canvas *= m[..., None]
    pad = int(max(w, h) * 0.06 + 24) if shadow else stroke_w + 2
    out = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.float32)
    out[pad:pad + h, pad:pad + w] = canvas
    if stroke and stroke_w:
        ring, _ = rect_sprite(w, h, r, None, stroke, stroke_w, 0)
        p2 = stroke_w + 2
        out[pad:pad + h, pad:pad + w] = over(out[pad:pad + h, pad:pad + w], ring[p2:p2 + h, p2:p2 + w])
    if shadow:
        out = _shadow(out, max(w, h) * 0.035 + 6, shadow, max(h * 0.03, 6))
    return out, pad


@lru_cache(maxsize=128)
def icon_sprite(name: str, size: int, color: str) -> np.ndarray:
    """icon Uicons (solid-rounded) một màu."""
    from .. import neon
    m = neon._uicon_mask(name, int(size))
    if m is None:
        m = neon._draw_icon(name, int(size))
    ys, xs = np.where(m > 0.02)
    if len(ys):
        m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = np.pad(m, 4)
    return _premul(m, color)


def icon_exists(name: str) -> bool:
    from .. import neon
    return neon.icon_exists(name)


# ---------------- ghép lên khung ----------------
def place(dst: np.ndarray, spr: np.ndarray, M: np.ndarray, opacity: float = 1.0, blur_vec=(0.0, 0.0)):
    """đặt sprite lên dst theo ma trận affine 2x3 (toạ độ sprite → toạ độ khung), chỉ warp vùng bao."""
    if opacity <= 0.003:
        return
    h, w = spr.shape[:2]
    corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], np.float32) @ M.T
    bx, by = abs(blur_vec[0]), abs(blur_vec[1])
    x0 = int(math.floor(corners[:, 0].min() - bx)) - 1
    y0 = int(math.floor(corners[:, 1].min() - by)) - 1
    x1 = int(math.ceil(corners[:, 0].max() + bx)) + 1
    y1 = int(math.ceil(corners[:, 1].max() + by)) + 1
    H, W = dst.shape[:2]
    cx0, cy0, cx1, cy1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    if cx0 >= cx1 or cy0 >= cy1:
        return
    M2 = M.copy()
    M2[0, 2] -= cx0
    M2[1, 2] -= cy0
    sc = math.hypot(M[0, 0], M[1, 0])
    interp = cv2.INTER_AREA if sc < 0.7 else cv2.INTER_LINEAR
    if sc < 0.7:   # thu nhỏ nhiều: giảm mẫu trước cho mịn
        k = max(sc, 0.05)
        spr = cv2.resize(spr, (max(int(w * k), 1), max(int(h * k), 1)), interpolation=cv2.INTER_AREA)
        M2 = M2 @ np.array([[1 / k, 0, 0], [0, 1 / k, 0], [0, 0, 1]], np.float32)
        interp = cv2.INTER_LINEAR
    reg = cv2.warpAffine(spr, M2.astype(np.float32), (cx1 - cx0, cy1 - cy0), flags=interp,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    n = int(round(math.hypot(*blur_vec)))
    if n >= 3:   # nhòe chuyển động theo hướng di chuyển
        k = np.zeros((2 * n + 1, 2 * n + 1), np.float32)
        ang = math.atan2(blur_vec[1], blur_vec[0])
        cv2.line(k, (int(n - n * math.cos(ang)), int(n - n * math.sin(ang))),
                 (int(n + n * math.cos(ang)), int(n + n * math.sin(ang))), 1.0, 1, cv2.LINE_AA)
        k /= max(k.sum(), 1e-6)
        reg = cv2.filter2D(reg, -1, k)
    if opacity < 1:
        reg = reg * opacity
    sub = dst[cy0:cy1, cx0:cx1]
    sub *= (1 - reg[..., 3:4])
    sub += reg[..., :3]


def affine(cx: float, cy: float, scale: float, rot_deg: float, ax: float, ay: float) -> np.ndarray:
    """ma trận đưa điểm neo (ax, ay) của sprite tới (cx, cy), co giãn + xoay quanh điểm neo."""
    a = math.radians(rot_deg)
    c, s = math.cos(a) * scale, math.sin(a) * scale
    return np.array([[c, -s, cx - (c * ax - s * ay)], [s, c, cy - (s * ax + c * ay)]], np.float32)


# ---------------- clip video trong khung ----------------
@lru_cache(maxsize=12)
def video_frames(path: str, t_in: float, dur: float, w: int, h: int, fps: int, gray: bool = False) -> np.ndarray:
    """giải mã một đoạn clip, cắt vừa khung w×h (cover) → mảng uint8 (n, h, w, 3) RGB."""
    import subprocess
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}"
    if gray:
        vf += ",hue=s=0"
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t_in:.3f}", "-t", f"{dur + 0.5:.3f}", "-i", path, "-vf", vf,
                        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
    n = len(r.stdout) // (w * h * 3)
    if n == 0:
        raise RuntimeError(f"không giải mã được clip {path} @ {t_in}s")
    return np.frombuffer(r.stdout[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)


@lru_cache(maxsize=32)
def frame_mask(w: int, h: int, r: float, shadow: float) -> tuple[np.ndarray, np.ndarray, int]:
    """mặt nạ bo góc + lớp bóng (RGBA) dùng lại cho mọi frame của clip."""
    pad = int(max(w, h) * 0.06 + 24) if shadow else 2
    m = _rrect_mask(w, h, r)
    sh = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.float32)
    if shadow:
        a = np.zeros(sh.shape[:2], np.float32)
        a[pad:pad + h, pad:pad + w] = m
        a = np.roll(cv2.GaussianBlur(a, (0, 0), max(w, h) * 0.035 + 6), int(max(h * 0.03, 6)), axis=0) * shadow
        sh[..., 3] = a
    return m, sh, pad
