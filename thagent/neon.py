"""Phong cách “neon pack” BĐS (học từ mẫu text CapCut người dùng gửi — chỉ học kiểu, không trích asset):
- chữ chính đậm, tô màu chuyển dọc + phát sáng cùng tông
- chữ viết tay chồng lên chữ chính, hiện dần trái→phải
- nhãn viên thuốc (pill) màu chuyển, chữ trắng đậm
- icon nét mảnh phát sáng (vẽ thủ tục, không lấy từ mẫu)
- hiệu ứng vào: pop + viền rỗng lan ra rồi mờ (echo)
"""
from __future__ import annotations

import math
import unicodedata
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .typography import FONT_DIR, hex_rgb

NEON_FONTS = {
    "display": ("Montserrat-VF.ttf", 900),
    "display_bold": ("Montserrat-VF.ttf", 700),
    "thin": ("Montserrat-VF.ttf", 300),
    "semi": ("Montserrat-VF.ttf", 600),
    "condensed": ("Anton-Regular.ttf", None),
    "script": ("GreatVibes-Regular.ttf", None),
    "serif": ("PlayfairDisplay-Italic-VF.ttf", 700),
    "body": ("BeVietnamPro-Bold.ttf", None),
}

PALETTES = {  # (trên, dưới, glow) — 3 tông cố định theo góp ý người dùng
    "gold": ("#FFE47A", "#FF9A1F", "#FF9A00"),   # vàng cam: ý thông thường
    "red": ("#FF9A86", "#FF2B3A", "#FF2B3A"),    # đỏ: cảnh báo / nhấn mạnh mức độ
    "blue": ("#A6EEFF", "#1E86FF", "#1E90FF"),   # xanh: tin tưởng, an tâm
    "white": ("#FFFFFF", "#EEF2F7", "#FFFFFF"),
}
PALETTES["orange"] = PALETTES["gold"]; PALETTES["cyan"] = PALETTES["blue"]; PALETTES["teal"] = PALETTES["blue"]


@lru_cache(maxsize=64)
def nfont(role: str, size: int):
    f, w = NEON_FONTS[role]
    font = ImageFont.truetype(str(FONT_DIR / f), size)
    if w is not None:
        try:
            font.set_variation_by_axes([w])
        except Exception:
            pass
    return font


def _mask(text: str, role: str, size: int, spacing: float = 0.0) -> np.ndarray:
    text = unicodedata.normalize("NFC", text)
    font = nfont(role, size)
    pad = int(size * 0.7)
    adv = [font.getlength(ch) + spacing for ch in text]
    w = int(sum(adv)) + 2 * pad
    asc, desc = font.getmetrics()
    h = asc + desc + 2 * pad
    im = Image.new("L", (max(w, 1), h), 0)
    d = ImageDraw.Draw(im)
    x = pad
    for ch, a in zip(text, adv):
        d.text((x, pad), ch, font=font, fill=255)
        x += a
    return np.asarray(im, np.float32) / 255.0


def _grad(h: int, w: int, top: str, bot: str, m: np.ndarray) -> np.ndarray:
    ys = np.where(m.max(1) > 0.05)[0]
    y0, y1 = (ys[0], ys[-1]) if len(ys) else (0, h)
    t = np.clip((np.arange(h) - y0) / max(y1 - y0, 1), 0, 1)[:, None, None]
    a, b = np.array(hex_rgb(top)) / 255.0, np.array(hex_rgb(bot)) / 255.0
    return np.broadcast_to(a * (1 - t) + b * t, (h, w, 3)).astype(np.float32)


def _compose(fill_rgb: np.ndarray, m: np.ndarray, glow: str | None, glow_k: float, size: int,
             shadow: float = 0.5) -> np.ndarray:
    h, w = m.shape
    out = np.zeros((h, w, 4), np.float32)
    if shadow:
        # bóng tối 2 lớp: sát chữ + quầng rộng, để neon vẫn nổi trên nền trời/áo sáng
        tight = np.roll(cv2.GaussianBlur(m, (0, 0), size * 0.05), int(size * 0.04), 0)
        wide = cv2.GaussianBlur(m, (0, 0), size * 0.28)
        out[..., 3] = np.clip(tight * shadow * 1.3 + wide * shadow * 0.9, 0, 0.85)
    if glow:
        g = cv2.GaussianBlur(m, (0, 0), size * 0.16) * glow_k * 0.8
        g = np.clip(g, 0, 1)
        gc = np.array(hex_rgb(glow), np.float32) / 255.0
        a = g
        out[..., :3] = out[..., :3] * (1 - a[..., None]) + gc * a[..., None]
        out[..., 3] = out[..., 3] * (1 - a) + a
    out[..., :3] = out[..., :3] * (1 - m[..., None]) + fill_rgb * m[..., None]
    out[..., 3] = out[..., 3] * (1 - m) + m
    return out


def _trim(out: np.ndarray) -> np.ndarray:
    ys, xs = np.where(out[..., 3] > 0.01)
    if not len(ys):
        return out
    return out[max(ys.min() - 2, 0):ys.max() + 3, max(xs.min() - 2, 0):xs.max() + 3]


@lru_cache(maxsize=256)
def text_sprite(text: str, role: str, size: int, palette: str, glow_k: float = 0.9, outline: bool = False,
                spacing: float = 0.0) -> np.ndarray:
    top, bot, glow = PALETTES.get(palette, PALETTES["white"])
    m = _mask(text, role, size, spacing)
    if outline:
        k = max(2, size // 40)
        dil = cv2.dilate(m, np.ones((2 * k + 1, 2 * k + 1), np.uint8))
        m = np.clip(dil - m, 0, 1)
        return _trim(_compose(_grad(*m.shape, top, bot, m), m, None, 0, size, shadow=0))
    return _trim(_compose(_grad(*m.shape, top, bot, m), m, glow, glow_k, size))


@lru_cache(maxsize=64)
def pill_sprite(text: str, size: int, palette: str) -> np.ndarray:
    top, bot, glow = PALETTES.get(palette, PALETTES["cyan"])
    tm = _mask(text, "display_bold", size)
    ys, xs = np.where(tm > 0.05)
    tm = tm[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    th, tw = tm.shape
    ph, pw = int(th * 1.9), int(tw + th * 1.6)
    S = 4
    big = np.zeros((ph * S, pw * S), np.uint8)
    r = ph * S // 2
    cv2.rectangle(big, (r, 0), (pw * S - r, ph * S), 255, -1)
    cv2.circle(big, (r, r), r, 255, -1); cv2.circle(big, (pw * S - r, r), r, 255, -1)
    pm = cv2.resize(big, (pw, ph), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    pad = int(size * 0.8)
    M = np.zeros((ph + 2 * pad, pw + 2 * pad), np.float32)
    M[pad:pad + ph, pad:pad + pw] = pm
    a, b = np.array(hex_rgb(top)) / 255.0, np.array(hex_rgb(bot)) / 255.0
    t = np.linspace(0, 1, M.shape[1])[None, :, None]   # chuyển màu ngang
    fill = (a * (1 - t) + b * t) * np.ones((M.shape[0], 1, 1))
    out = _compose(fill.astype(np.float32), M, glow, 0.7, size, shadow=0.3)
    T = np.zeros_like(M)
    oy, ox = pad + (ph - th) // 2, pad + (pw - tw) // 2
    T[oy:oy + th, ox:ox + tw] = tm
    out[..., :3] = out[..., :3] * (1 - T[..., None]) + T[..., None]
    out[..., 3] = np.maximum(out[..., 3], T)
    return _trim(out)


# ---------------- icon nét mảnh ----------------
def _draw_icon(name: str, S: int) -> np.ndarray:
    im = np.zeros((S, S), np.uint8)
    t = max(2, S // 14)
    c = S // 2
    L = lambda p, q: cv2.line(im, p, q, 255, t, cv2.LINE_AA)
    if name == "key":
        cv2.circle(im, (int(S * .32), int(S * .32)), int(S * .17), 255, t, cv2.LINE_AA)
        L((int(S * .44), int(S * .44)), (int(S * .82), int(S * .82)))
        L((int(S * .64), int(S * .64)), (int(S * .54), int(S * .74)))
        L((int(S * .74), int(S * .74)), (int(S * .64), int(S * .84)))
    elif name == "house":
        pts = np.array([[.15, .5], [.5, .16], [.85, .5]]) * S
        cv2.polylines(im, [pts.astype(np.int32)], False, 255, t, cv2.LINE_AA)
        cv2.rectangle(im, (int(S * .25), int(S * .45)), (int(S * .75), int(S * .85)), 255, t, cv2.LINE_AA)
        cv2.rectangle(im, (int(S * .43), int(S * .62)), (int(S * .57), int(S * .85)), 255, t, cv2.LINE_AA)
    elif name == "coins":
        for i in range(3):
            y = int(S * (.72 - i * .17))
            cv2.ellipse(im, (c, y), (int(S * .3), int(S * .1)), 0, 0, 360, 255, t, cv2.LINE_AA)
    elif name == "bill":
        cv2.rectangle(im, (int(S * .1), int(S * .28)), (int(S * .9), int(S * .72)), 255, t, cv2.LINE_AA)
        cv2.circle(im, (c, c), int(S * .12), 255, t, cv2.LINE_AA)
    elif name == "pin":
        cv2.circle(im, (c, int(S * .38)), int(S * .22), 255, t, cv2.LINE_AA)
        cv2.circle(im, (c, int(S * .38)), int(S * .07), 255, t, cv2.LINE_AA)
        L((int(S * .32), int(S * .5)), (c, int(S * .88))); L((int(S * .68), int(S * .5)), (c, int(S * .88)))
    elif name == "chart":
        pts = (np.array([[.12, .78], [.38, .52], [.56, .64], [.86, .3]]) * S).astype(np.int32)
        cv2.polylines(im, [pts], False, 255, t, cv2.LINE_AA)
        L((int(S * .86), int(S * .3)), (int(S * .66), int(S * .3))); L((int(S * .86), int(S * .3)), (int(S * .86), int(S * .5)))
    elif name == "leaf":
        cv2.ellipse(im, (c, c), (int(S * .36), int(S * .2)), -40, 0, 360, 255, t, cv2.LINE_AA)
        L((int(S * .22), int(S * .78)), (int(S * .72), int(S * .28)))
    elif name == "star":
        pts = [(c + S * .38 * math.sin(i * math.pi * .8), c - S * .38 * math.cos(i * math.pi * .8)) for i in range(5)]
        cv2.polylines(im, [np.array(pts, np.int32)], True, 255, t, cv2.LINE_AA)
    elif name == "building":
        cv2.rectangle(im, (int(S * .25), int(S * .12)), (int(S * .75), int(S * .88)), 255, t, cv2.LINE_AA)
        for yy in (.28, .45, .62):
            for xx in (.37, .58):
                cv2.rectangle(im, (int(S * xx), int(S * yy)), (int(S * (xx + .06)), int(S * (yy + .07))), 255, -1)
    elif name == "sparkle":   # ngôi sao 4 cánh
        pts = []
        for i in range(8):
            r = S * (.46 if i % 2 == 0 else .1)
            a = i * math.pi / 4
            pts.append((c + r * math.sin(a), c - r * math.cos(a)))
        cv2.fillPoly(im, [np.array(pts, np.int32)], 255, cv2.LINE_AA)
    elif name == "ring":
        cv2.circle(im, (c, c), int(S * .38), 255, t, cv2.LINE_AA)
        cv2.circle(im, (c, c), int(S * .08), 255, -1, cv2.LINE_AA)
    elif name == "chevrons":
        for i in range(3):
            x = int(S * (.18 + i * .24))
            cv2.polylines(im, [np.array([[x, int(S * .3)], [x + int(S * .16), c], [x, int(S * .7)]], np.int32)], False, 255, t, cv2.LINE_AA)
    elif name == "underline":
        cv2.line(im, (int(S * .04), c), (int(S * .96), c), 255, t + 2, cv2.LINE_AA)
    elif name == "dots":
        for i in range(3):
            cv2.circle(im, (int(S * (.2 + i * .3)), c), max(3, S // 16), 255, -1, cv2.LINE_AA)
    elif name == "arrow_up":
        L((c, int(S * .85)), (c, int(S * .18))); L((c, int(S * .18)), (int(S * .28), int(S * .4))); L((c, int(S * .18)), (int(S * .72), int(S * .4)))
    return im.astype(np.float32) / 255.0


# Icon Flaticon Uicons (Solid Rounded, font chính thức từ npm @flaticon/flaticon-uicons@3.3.1).
# Giấy phép Flaticon: dùng thương mại được, cần ghi nguồn “Uicons by Flaticon”.
UICONS = {"house": "home", "building": "building", "coins": "coins", "key": "key", "pin": "marker",
          "chart": "chart-line-up", "star": "star", "coffee": "coffee", "store": "store-alt", "shop": "shop",
          "school": "chalkboard-user", "users": "users", "road": "road", "check": "check-circle",
          "briefcase": "briefcase", "handshake": "handshake", "city": "city", "home-location": "home-location",
          "warning": "triangle-warning", "list": "list-check", "area": "ruler-combined", "money": "money-bill-wave",
          "aircon": "snowflake", "bank": "bank", "calendar": "calendar-clock", "trophy": "trophy"}
_UI_DIR = FONT_DIR.parent / "uicons"


@lru_cache(maxsize=1)
def _uicons_map() -> dict:
    import re
    css = (_UI_DIR / "solid.css").read_text(encoding="utf-8")
    return {m.group(1): chr(int(m.group(2), 16)) for m in re.finditer(r"\.fi-sr-([a-z0-9-]+):+before\{content:\"\\([0-9a-f]+)\"", css)}


DRAWN = {"bill", "building", "chart", "chevrons", "coins", "dots", "house", "key", "leaf", "pin", "ring", "sparkle",
         "star", "underline"}


def _uicon_cls(name: str) -> str:
    """tên ngắn trong UICONS, hoặc bất kỳ tên Uicons solid-rounded (heart, syringe, fi-sr-pills…)."""
    return UICONS.get(name) or name.removeprefix("fi-sr-")


def icon_exists(name: str) -> bool:
    return _uicon_cls(name) in _uicons_map() or name in DRAWN


def _uicon_mask(name: str, size: int) -> np.ndarray | None:
    cls = _uicon_cls(name)
    if not cls:
        return None
    ch = _uicons_map().get(cls)
    if ch is None:
        return None
    font = ImageFont.truetype(str(next(_UI_DIR.glob("uicons-solid-rounded-*.woff"))), size)
    im = Image.new("L", (int(size * 1.4), int(size * 1.4)), 0)
    ImageDraw.Draw(im).text((size * 0.7, size * 0.7), ch, font=font, fill=255, anchor="mm")
    return np.asarray(im, np.float32) / 255.0


@lru_cache(maxsize=64)
def icon_sprite(name: str, size: int, palette: str) -> np.ndarray:
    top, bot, glow = PALETTES.get(palette, PALETTES["gold"])
    um = _uicon_mask(name, size)
    if um is not None:
        pad = size // 3
        m = np.pad(um, pad)
        return _trim(_compose(_grad(*m.shape, top, bot, m), m, glow, 0.9, size // 2, shadow=0.35))
    m = _draw_icon(name, size)
    if name == "underline":
        m = cv2.resize(m, (size, max(size // 10, 6)), interpolation=cv2.INTER_AREA)
        m = cv2.resize(_draw_icon(name, size), (size, size))[size // 2 - 6:size // 2 + 6]
    pad = size // 3
    m = np.pad(m, pad)
    return _trim(_compose(_grad(*m.shape, top, bot, m), m, glow, 1.1, size // 2, shadow=0.3))
