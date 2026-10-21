"""Engine typography theo frame: font, sprite chữ, preset chuyển động, bố cục nhóm.

Chuyển động là hàm thuần của (frame, group) → preview và render luôn trùng nhau.
"""
from __future__ import annotations

import math
import unicodedata
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .schema import TextGroup, TextSpan

from .paths import ROOT
FONT_DIR = ROOT / "assets" / "fonts"

# Vai trò font → (file, trục wght nếu là variable font). Sửa trong config/style.json.
FONT_ROLES = {
    "body": ("BeVietnamPro-Medium.ttf", None),
    "body_bold": ("BeVietnamPro-Bold.ttf", None),
    "number": ("BeVietnamPro-ExtraBold.ttf", None),
    "emphasis": ("PlayfairDisplay-Italic-VF.ttf", 600),
    "decorative": ("DancingScript-VF.ttf", 600),
}


def get_font(role: str, size: int) -> ImageFont.FreeTypeFont:
    from . import fonts as FT
    return _get_font(role, size, FT.current())


@lru_cache(maxsize=256)
def _get_font(role: str, size: int, lang: str) -> ImageFont.FreeTypeFont:
    from . import fonts as FT
    fname, wght = FONT_ROLES[role]
    path, wght = FT.pick(FONT_DIR / fname, wght)
    f = ImageFont.truetype(path, size)
    if wght is not None:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _sprite(text: str, role: str, size: int, color: str, spacing: float, shadow: float) -> np.ndarray:
    from . import fonts as FT
    return _sprite_l(text, role, size, color, spacing, shadow, FT.current())


@lru_cache(maxsize=512)
def _sprite_l(text: str, role: str, size: int, color: str, spacing: float, shadow: float, lang: str) -> np.ndarray:
    """RGBA float32 premultiplied, có padding cho dấu tiếng Việt và bóng mềm."""
    from . import fonts as FT
    text = FT.shape_line(unicodedata.normalize("NFC", text))
    if FT.complex_script():
        spacing = 0.0                              # chữ ghép/dấu chồng (Thái, Ả Rập, Hindi…) phải vẽ nguyên cụm
    font = get_font(role, size)
    pad = int(size * 0.6)
    # đo theo từng ký tự để hỗ trợ letter-spacing
    adv = []
    for ch in text:
        adv.append(font.getlength(ch) + spacing)
    width = int(sum(adv) - spacing) + 2 * pad
    asc, desc = font.getmetrics()
    height = asc + desc + 2 * pad
    mask = Image.new("L", (max(width, 1), height), 0)
    d = ImageDraw.Draw(mask)
    if spacing == 0:
        d.text((pad, pad), text, font=font, fill=255)
    else:
        x = pad
        for ch, a in zip(text, adv):
            d.text((x, pad), ch, font=font, fill=255)
            x += a
    m = np.asarray(mask, np.float32) / 255.0
    rgb = np.array(hex_rgb(color), np.float32) / 255.0
    out = np.zeros((height, width, 4), np.float32)
    if shadow > 0:
        sh = np.asarray(mask.filter(ImageFilter.GaussianBlur(size * 0.10)), np.float32) / 255.0
        sh = np.roll(sh, (int(size * 0.04), 0), (0, 1)) * shadow
        out[..., 3] = sh  # bóng đen premultiplied: rgb = 0
    out[..., :3] = out[..., :3] * (1 - m[..., None]) + rgb * m[..., None]
    out[..., 3] = out[..., 3] * (1 - m) + m
    # cắt viền trống nhưng giữ lề an toàn cho dấu
    ys, xs = np.where(out[..., 3] > 0.004)
    if len(ys):
        y0, y1 = max(ys.min() - 4, 0), min(ys.max() + 5, height)
        x0, x1 = max(xs.min() - 4, 0), min(xs.max() + 5, width)
        out = out[y0:y1, x0:x1]
    return out


def span_sprite(s: TextSpan, shadow: float = 0.6) -> np.ndarray:
    if s.style != "classic":
        from . import neon
        if s.style == "neon":
            return neon.text_sprite(s.text, s.neon_role, s.size, s.palette, spacing=s.letter_spacing)
        if s.style == "outline":
            return neon.text_sprite(s.text, s.neon_role, s.size, s.palette, outline=True, spacing=s.letter_spacing)
        if s.style == "pill":
            return neon.pill_sprite(s.text, s.size, s.palette)
        if s.style == "icon":
            return neon.icon_sprite(s.text, s.size, s.palette)
    return _sprite(s.text, s.font_role, s.size, s.color, s.letter_spacing, shadow)


# ---------------- easing ----------------
def clamp01(x):
    return max(0.0, min(1.0, x))


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_out_quart(t):
    return 1 - (1 - t) ** 4


def ease_in_cubic(t):
    return t ** 3


def ease_out_back(t, s=1.7):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def preset_state(g: TextGroup, si: int, f: int) -> dict | None:
    """Trạng thái của span si tại frame f: opacity, dx, dy, scale, blur. None = ẩn."""
    span = g.spans[si]
    start = g.start + span.delay_frames
    if f < start or f >= g.end:
        return None
    e = clamp01((f - start + 1) / max(g.enter_frames, 1))
    x = clamp01((f - (g.end - g.exit_frames) + 1) / max(g.exit_frames, 1))
    st = {"o": 1.0, "dx": 0.0, "dy": 0.0, "s": 1.0, "b": 0.0, "wipe": 1.0}
    p = g.preset
    if span.motion:
        e2 = clamp01((f - start + 1) / max(_enter(g, span), 1))
        m = span.motion
        if m == "pop":
            st["s"] = 0.6 + 0.4 * ease_out_back(e2, 2.0); st["o"] = clamp01(e2 * 2.5); st["b"] = (1 - e2) * 8
        elif m == "icon":
            st["s"] = 0.2 + 0.8 * ease_out_back(e2, 2.6); st["o"] = clamp01(e2 * 3)
        elif m == "write":
            st["wipe"] = ease_out_cubic(e2); st["o"] = clamp01(e2 * 3)
        elif m == "wipe":
            st["wipe"] = ease_out_quart(e2); st["dx"] = -(1 - ease_out_quart(e2)) * 30
        elif m == "slide":
            k = ease_out_cubic(e2); st["dy"] = (1 - k) * 40; st["o"] = e2 ** 0.7; st["b"] = (1 - k) * 8
        else:
            st["o"] = e2
        if x > 0:
            k = ease_in_cubic(x); st["o"] *= 1 - x; st["b"] += k * 8; st["s"] *= 1 - 0.06 * k
        return st
    main_pop = p == "keyword_pop" or (p == "number_callout" and span.font_role == "number")
    if p == "caption":
        st["o"] = e
        st["dy"] = (1 - ease_out_cubic(e)) * 14
    elif main_pop or (p == "staggered_phrase" and span.font_role in ("emphasis", "decorative")):
        st["s"] = 0.55 + 0.45 * ease_out_back(e)
        st["o"] = clamp01(e * 2.2)
        st["b"] = (1 - e) * 6
    elif p == "behind_head_title":
        k = ease_out_quart(e)
        st["s"] = 1.22 - 0.22 * k
        st["o"] = clamp01(e * 1.6)
        st["b"] = (1 - k) * 16
        st["dy"] = (1 - k) * 30
    elif p == "staggered_phrase" or p == "number_callout":
        k = ease_out_cubic(e)
        st["dy"] = (1 - k) * 46
        st["o"] = e ** 0.7
        st["b"] = (1 - k) * 8
    else:  # phrase_slide
        k = ease_out_cubic(e)
        direction = -1 if g.align == "right" else 1
        st["dx"] = (1 - k) * 90 * -direction
        st["o"] = e ** 0.7
        st["b"] = (1 - k) * 10
    if x > 0:
        k = ease_in_cubic(x)
        st["o"] *= 1 - x
        st["dy"] -= k * 24
        st["b"] += k * 8
        st["s"] *= 1 - 0.05 * k
    return st


def _enter(g: TextGroup, s: TextSpan) -> int:
    return {"write": int(g.enter_frames * 1.8), "wipe": g.enter_frames, "icon": g.enter_frames}.get(s.motion, g.enter_frames)


def hit_frame(g: TextGroup) -> int:
    """Frame đạt điểm nhấn: khi span chính chạm vị trí (pop: đỉnh overshoot)."""
    main = max(range(len(g.spans)), key=lambda i: g.spans[i].size)
    d = g.spans[main].delay_frames
    if g.preset in ("keyword_pop", "number_callout") or g.spans[main].font_role in ("emphasis", "decorative") \
            and g.preset == "staggered_phrase":
        return g.start + d + int(round(g.enter_frames * 0.55))
    return g.start + d + g.enter_frames - 1


def group_extent(g: TextGroup, skip_icons: bool = False) -> tuple[float, float, float, float]:
    """bbox (x0,y0,x1,y1) của nhóm quanh điểm neo (0,0) ở trạng thái nghỉ."""
    xs0, ys0, xs1, ys1 = [], [], [], []
    for s in g.spans:
        if skip_icons and s.style == "icon":
            continue
        h, w = span_sprite(s).shape[:2]
        cx = s.dx + _align_offset(g, w)
        xs0.append(cx - w / 2); xs1.append(cx + w / 2)
        ys0.append(s.dy - h / 2); ys1.append(s.dy + h / 2)
    return min(xs0), min(ys0), max(xs1), max(ys1)


def _align_offset(g: TextGroup, w: float) -> float:
    if g.align == "left":
        return w / 2
    if g.align == "right":
        return -w / 2
    return 0.0


def draw_group(layer: np.ndarray, g: TextGroup, f: int, ax: float, ay: float):
    """Vẽ nhóm g vào layer RGBA premultiplied (float32), neo tại (ax, ay) px."""
    H, W = layer.shape[:2]
    for i, s in enumerate(g.spans):
        if s.motion == "words":
            _draw_words(layer, g, s, f, ax, ay)
            continue
        st = preset_state(g, i, f)
        if st is None or st["o"] <= 0.003:
            continue
        if s.motion == "float":   # element trôi nhẹ liên tục
            st["dy"] += 6 * math.sin((f - g.start) / 9.0 + i)
        spr = span_sprite(s)
        rest = spr
        if st.get("wipe", 1.0) < 0.999:
            w0 = spr.shape[1]
            edge = max(int(w0 * 0.12), 4)
            pos = st["wipe"] * (w0 + edge)
            ramp = np.clip((pos - np.arange(w0)) / edge, 0, 1).astype(np.float32)
            spr = spr * ramp[None, :, None]
        if s.echo:
            # viền rỗng lan ra từ điểm nhấn của span (≈ lúc chạm vị trí)
            t0 = g.start + s.delay_frames + int(_enter(g, s) * 0.5)
            k = (f - t0) / 16
            if 0 <= k <= 1:
                from . import neon
                ol = neon.text_sprite(s.text, s.neon_role, s.size, s.palette, outline=True)
                sc = 1 + 0.5 * ease_out_cubic(k)
                ol = cv2.resize(ol, None, fx=sc, fy=sc, interpolation=cv2.INTER_LINEAR)
                oh, ow = ol.shape[:2]
                ecx = ax + s.dx + _align_offset(g, rest.shape[1])
                _blend(layer, ol * (0.85 * (1 - k)), int(ecx - ow / 2), int(ay + s.dy - oh / 2))
        if abs(st["s"] - 1) > 0.002:
            spr = cv2.resize(spr, None, fx=st["s"], fy=st["s"], interpolation=cv2.INTER_LINEAR)
        if st["b"] > 0.6:
            k = int(st["b"]) * 2 + 1
            pad = k
            spr = cv2.copyMakeBorder(spr, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
            spr = cv2.GaussianBlur(spr, (k, k), st["b"] / 2)
        h, w = spr.shape[:2]
        rest_w = span_sprite(s).shape[1]
        cx = ax + s.dx + _align_offset(g, rest_w) + st["dx"]
        cy = ay + s.dy + st["dy"]
        x0, y0 = int(round(cx - w / 2)), int(round(cy - h / 2))
        _blend(layer, spr * st["o"], x0, y0)


def _draw_words(layer, g: TextGroup, s: TextSpan, f: int, ax: float, ay: float):
    """Chữ trượt xuống từng từ: mỗi từ rơi từ trên xuống + rõ dần, đúng frame từ được nói."""
    from . import neon
    if f < g.start or f >= g.end:
        return
    words = s.text.split()
    font = neon.nfont(s.neon_role, s.size)
    space = font.getlength(" ")
    sprites = [neon.text_sprite(w, s.neon_role, s.size, s.palette) for w in words]
    advs = [font.getlength(w) for w in words]
    total = sum(advs) + space * (len(words) - 1)
    full_w = span_sprite(s).shape[1]
    cx0 = ax + s.dx + _align_offset(g, full_w) - total / 2
    x = clamp01((f - (g.end - g.exit_frames) + 1) / max(g.exit_frames, 1))
    pos = cx0
    for k, (w, spr, a) in enumerate(zip(words, sprites, advs)):
        d = s.word_delays[k] if k < len(s.word_delays) else s.delay_frames + 3 * k
        e = clamp01((f - g.start - d + 1) / 7)
        if e <= 0:
            pos += a + space
            continue
        kk = ease_out_cubic(e)
        o = clamp01(e * 1.6) * (1 - x)
        dy = -(1 - kk) * 46 - ease_in_cubic(x) * 20
        sp = spr
        b = (1 - kk) * 6 + ease_in_cubic(x) * 6
        if b > 0.6:
            sp = cv2.GaussianBlur(np.pad(sp, ((8, 8), (8, 8), (0, 0))), (0, 0), b / 2)
        h, wd = sp.shape[:2]
        _blend(layer, sp * o, int(pos + a / 2 - wd / 2), int(ay + s.dy + dy - h / 2))
        pos += a + space


def _blend(dst: np.ndarray, src: np.ndarray, x0: int, y0: int):
    H, W = dst.shape[:2]
    h, w = src.shape[:2]
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1, dy1 = min(W, x0 + w), min(H, y0 + h)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    s = src[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
    d = dst[dy0:dy1, dx0:dx1]
    d *= (1 - s[..., 3:4])
    d += s
