"""Tạo nền Motion Graphics theo kênh → assets/backgrounds/<kênh>/nen-1..5.png (+ ảnh tổng hợp nếu truyền đường dẫn).
Cùng ngôn ngữ nền MG của app (gradient sáng, quầng mờ, nét mảnh, lấp lánh); mỗi kênh một bảng màu + bộ hình trang trí
riêng + 1 icon lớn mờ; giữa khung để trống cho thẻ/chữ.
  .venv/bin/python packaging/make_backgrounds.py [ra=assets/backgrounds] [tong_hop.png]"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from thagent import neon                                  # noqa: E402
from thagent.typography import _blend, hex_rgb            # noqa: E402

W, H = 1080, 1920
# kênh: (màu đậm, màu sáng, quầng 1, quầng 2, tông lấp lánh chính, phụ, icon lớn)
FIELDS = {
    "bat-dong-san": ("#1F3A93", "#B7C8EE", "#7FA0F0", "#F3D9A4", "gold", "gold", ["building", "city"]),
    "suc-khoe":     ("#0E8F83", "#B5F0DE", "#5CD6B8", "#FFFFFF", "gold", "blue", ["heart", "leaf"]),
    "giao-duc":     ("#2954DB", "#9EBDFD", "#8FB5FF", "#5B8CFF", "gold", "blue", ["book-open-cover", "graduation-cap"]),
    "chia-se":      ("#6C3FD8", "#F4B8D2", "#B48CFF", "#FFD1A8", "gold", "red", ["comments", "comment-heart"]),
    "lam-dep":      ("#D9467E", "#FFD9E5", "#FF9CC0", "#FFFFFF", "gold", "red", ["flower", "spa"]),
    "fnb":          ("#E2550F", "#FFD58F", "#FF9A4D", "#FFF0C9", "gold", "red", ["bowl-chopsticks", "utensils"]),
}
NAMES = {"bat-dong-san": "Bất động sản", "suc-khoe": "Sức khỏe", "giao-duc": "Giáo dục", "chia-se": "Chia sẻ",
         "lam-dep": "Làm đẹp", "fnb": "F&B"}

# 5 bố cục: hướng gradient, quầng, 4 ô đặt hình (x,y,cỡ — luôn ở mép/góc), icon lớn (x,y,cỡ), lấp lánh
LAYOUTS = [
    dict(flip=False, orbs=[(.92, .10, 280, 0, .45), (.05, .88, 320, 1, .25), (.75, .62, 180, 0, .25)],
         slots=[(.86, .15, 1.0), (.12, .82, .9), (.12, .10, .6), (.90, .90, .7)], big=(.86, .84, 520),
         sparks=[(.70, .06, 50, 0), (.22, .93, 40, 1), (.94, .55, 30, 0)]),
    dict(flip=True, orbs=[(.08, .12, 300, 0, .45), (.95, .85, 300, 1, .3), (.30, .55, 160, 0, .22)],
         slots=[(.14, .16, 1.0), (.86, .80, .9), (.88, .09, .6), (.10, .92, .6)], big=(.12, .86, 500),
         sparks=[(.32, .06, 46, 0), (.70, .93, 40, 1), (.05, .50, 28, 0)]),
    dict(flip=False, orbs=[(.50, .05, 340, 0, .40), (.50, .98, 360, 1, .30)],
         slots=[(.50, .08, 1.1), (.14, .88, .8), (.88, .86, .8), (.08, .45, .5)], big=(.92, .40, 440),
         sparks=[(.82, .18, 44, 0), (.18, .20, 32, 1), (.85, .70, 30, 0), (.12, .72, 26, 0)]),
    dict(flip=True, orbs=[(.90, .40, 260, 0, .40), (.10, .20, 220, 1, .28), (.30, .90, 240, 0, .25)],
         slots=[(.88, .40, .9), (.10, .14, .8), (.82, .90, .7), (.14, .92, .6)], big=(.10, .16, 460),
         sparks=[(.20, .30, 48, 0), (.78, .18, 30, 1), (.92, .76, 40, 0)]),
    dict(flip=False, orbs=[(.15, .45, 300, 0, .35), (.85, .15, 240, 1, .35), (.80, .85, 260, 0, .30)],
         slots=[(.10, .42, .9), (.88, .12, .9), (.80, .88, 1.0), (.14, .93, .5)], big=(.88, .14, 480),
         sparks=[(.30, .08, 42, 0), (.58, .94, 36, 1), (.10, .78, 30, 0), (.94, .34, 26, 1)]),
]

T = 3   # nét mảnh


def _p(x, y):
    return int(round(x)), int(round(y))


# ---------- hình trang trí (vẽ lên mặt nạ trắng, toạ độ tâm cx,cy, cỡ s ≈ 1 → ~200px) ----------
def m_square(m, cx, cy, s, rot=0):
    r = 70 * s
    pts = [(cx + r * math.cos(math.radians(rot + 45 + 90 * k)), cy + r * math.sin(math.radians(rot + 45 + 90 * k))) for k in range(4)]
    cv2.polylines(m, [np.int32(pts)], True, 255, T, cv2.LINE_AA)


def m_roof(m, cx, cy, s):
    w = 120 * s
    for k, dy in enumerate((0, 34 * s)):
        pts = [(cx - w + k * 20 * s, cy + 50 * s + dy), (cx, cy - 40 * s + dy), (cx + w - k * 20 * s, cy + 50 * s + dy)]
        cv2.polylines(m, [np.int32(pts)], False, 255, T, cv2.LINE_AA)


def m_dots(m, cx, cy, s, n=5, vertical=False):
    for k in range(n):
        x, y = (cx + (k - n / 2) * 38 * s, cy) if not vertical else (cx, cy + (k - n / 2) * 38 * s)
        cv2.circle(m, _p(x, y), max(4, int(5 * s)), 255, -1, cv2.LINE_AA)


def m_capsule(m, cx, cy, s, rot=-35):
    L, r = 90 * s, 34 * s
    a = math.radians(rot)
    ux, uy = math.cos(a), math.sin(a)
    c1, c2 = (cx - ux * L / 2, cy - uy * L / 2), (cx + ux * L / 2, cy + uy * L / 2)
    nx, ny = -uy * r, ux * r
    cv2.line(m, _p(c1[0] + nx, c1[1] + ny), _p(c2[0] + nx, c2[1] + ny), 255, T, cv2.LINE_AA)
    cv2.line(m, _p(c1[0] - nx, c1[1] - ny), _p(c2[0] - nx, c2[1] - ny), 255, T, cv2.LINE_AA)
    d = math.degrees(a)
    cv2.ellipse(m, _p(*c1), (int(r), int(r)), d, 90, 270, 255, T, cv2.LINE_AA)
    cv2.ellipse(m, _p(*c2), (int(r), int(r)), d, -90, 90, 255, T, cv2.LINE_AA)
    cv2.line(m, _p(cx + nx, cy + ny), _p(cx - nx, cy - ny), 255, T, cv2.LINE_AA)


def m_plus(m, cx, cy, s):
    r = 26 * s
    cv2.line(m, _p(cx - r, cy), _p(cx + r, cy), 255, T + 1, cv2.LINE_AA)
    cv2.line(m, _p(cx, cy - r), _p(cx, cy + r), 255, T + 1, cv2.LINE_AA)


def m_pulse(m, cx, cy, s):
    w = 130 * s
    cx = min(max(cx, w + 40), W - w - 40)     # không tràn mép
    xs = [-1, -.35, -.22, -.08, .06, .2, 1]
    ys = [0, 0, -.9, .8, -.3, 0, 0]
    pts = [(cx + x * w, cy + y * 60 * s) for x, y in zip(xs, ys)]
    cv2.polylines(m, [np.int32(pts)], False, 255, T, cv2.LINE_AA)


def m_ring(m, cx, cy, s, n=1):
    for k in range(n):
        cv2.circle(m, _p(cx, cy), int((110 - k * 30) * s), 255, T - 1 if k else T, cv2.LINE_AA)


def m_triangle(m, cx, cy, s, rot=0):
    r = 46 * s
    pts = [(cx + r * math.cos(math.radians(rot - 90 + 120 * k)), cy + r * math.sin(math.radians(rot - 90 + 120 * k))) for k in range(3)]
    cv2.polylines(m, [np.int32(pts)], True, 255, T, cv2.LINE_AA)


def m_stroke(m, cx, cy, s):
    """gạch chân kiểu bút: cung thoải."""
    xs = np.linspace(-1, 1, 30)
    pts = [(cx + x * 120 * s, cy + (x * x - 1) * -14 * s + x * 10 * s) for x in xs]
    cv2.polylines(m, [np.int32(pts)], False, 255, T + 1, cv2.LINE_AA)


def m_bubble(m, cx, cy, s, flip=False):
    w, h, r = 150 * s, 96 * s, 30 * s
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    for (ax, ay, bx, by) in [(x0 + r, y0, x1 - r, y0), (x0 + r, y1, x1 - r, y1), (x0, y0 + r, x0, y1 - r), (x1, y0 + r, x1, y1 - r)]:
        if (ay == y1 and ax == x0 + r):     # cạnh đáy chừa chỗ đuôi
            tx = cx + (-w / 4 if not flip else w / 4)
            cv2.line(m, _p(x0 + r, y1), _p(tx - 14 * s, y1), 255, T, cv2.LINE_AA)
            cv2.line(m, _p(tx + 14 * s, y1), _p(x1 - r, y1), 255, T, cv2.LINE_AA)
            tip = (tx + (-22 * s if not flip else 22 * s), y1 + 34 * s)
            cv2.polylines(m, [np.int32([(tx - 14 * s, y1), tip, (tx + 14 * s, y1)])], False, 255, T, cv2.LINE_AA)
            continue
        cv2.line(m, _p(ax, ay), _p(bx, by), 255, T, cv2.LINE_AA)
    for (ox, oy, a0) in [(x0 + r, y0 + r, 180), (x1 - r, y0 + r, 270), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90)]:
        cv2.ellipse(m, _p(ox, oy), (int(r), int(r)), 0, a0, a0 + 90, 255, T, cv2.LINE_AA)
    for k in range(3):
        cv2.circle(m, _p(cx + (k - 1) * 30 * s, cy), max(4, int(7 * s)), 255, -1, cv2.LINE_AA)


def m_quote(m, cx, cy, s):
    """dấu ngoặc kép “ vẽ bằng chữ đậm."""
    from PIL import Image, ImageDraw, ImageFont
    sz = int(150 * s)
    f = ImageFont.truetype(str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "BeVietnamPro-ExtraBold.ttf"), sz)
    im = Image.new("L", (sz * 2, sz * 2), 0)
    ImageDraw.Draw(im).text((sz, sz), "\u201c", font=f, fill=255, anchor="mm")
    g = np.asarray(im)
    x0, y0 = int(cx - sz), int(cy - sz + sz * 0.25)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + 2 * sz, W), min(y0 + 2 * sz, H)
    m[ya:yb, xa:xb] = np.maximum(m[ya:yb, xa:xb], g[ya - y0:yb - y0, xa - x0:xb - x0])


def m_icon(m, name, cx, cy, size, a=1.0):
    g = neon._uicon_mask(name, int(size))
    if g is None:
        return
    h, w = g.shape
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    xa, ya, xb, yb = max(x0, 0), max(y0, 0), min(x0 + w, W), min(y0 + h, H)
    if xa >= xb or ya >= yb:
        return
    sub = g[ya - y0:yb - y0, xa - x0:xb - x0] * 255 * a
    m[ya:yb, xa:xb] = np.maximum(m[ya:yb, xa:xb], sub.astype(m.dtype))


def m_heart(m, cx, cy, s):
    m_icon(m, "heart", cx, cy, 44 * s)


def m_crescent(m, cx, cy, s, rot=0):
    r = 70 * s
    cv2.ellipse(m, _p(cx, cy), (int(r), int(r)), rot, 200, 340, 255, T, cv2.LINE_AA)
    cv2.ellipse(m, _p(cx, cy - 18 * s), (int(r * 0.82), int(r * 0.82)), rot, 215, 325, 255, T - 1, cv2.LINE_AA)


def m_flower(m, cx, cy, s, rot=0):
    for k in range(5):
        a = math.radians(rot + 72 * k)
        px, py = cx + math.cos(a) * 34 * s, cy + math.sin(a) * 34 * s
        cv2.ellipse(m, _p(px, py), (int(34 * s), int(17 * s)), math.degrees(a), 0, 360, 255, T - 1, cv2.LINE_AA)
    cv2.circle(m, _p(cx, cy), max(4, int(9 * s)), 255, -1, cv2.LINE_AA)


def m_plate(m, cx, cy, s):
    cv2.circle(m, _p(cx, cy), int(115 * s), 255, T, cv2.LINE_AA)
    cv2.circle(m, _p(cx, cy), int(80 * s), 255, T - 1, cv2.LINE_AA)


def m_spice(m, cx, cy, s, seed=0):
    rng = np.random.default_rng(seed)
    for _ in range(9):
        x, y = cx + rng.uniform(-90, 90) * s, cy + rng.uniform(-60, 60) * s
        cv2.circle(m, _p(x, y), max(3, int(rng.uniform(3, 7) * s)), 255, -1, cv2.LINE_AA)


def m_steam(m, cx, cy, s):
    for k in (-1, 0, 1):
        ys = np.linspace(0, 1, 30)
        pts = [(cx + k * 34 * s + math.sin(y * math.pi * 1.6 + k) * 10 * s, cy + (0.5 - y) * 110 * s) for y in ys]
        cv2.polylines(m, [np.int32(pts)], False, 255, T, cv2.LINE_AA)


# bộ hình mỗi kênh: 4 hàm theo 4 ô của bố cục (xoay vòng theo số nền để 5 nền khác nhau)
MOTIFS = {
    "bat-dong-san": [lambda m, x, y, s, i: m_roof(m, x, y, s), lambda m, x, y, s, i: m_square(m, x, y, s, rot=i * 15),
                     lambda m, x, y, s, i: m_dots(m, x, y, s), lambda m, x, y, s, i: m_square(m, x, y, s * 0.6, rot=45)],
    "suc-khoe": [lambda m, x, y, s, i: m_capsule(m, x, y, s, rot=-35 + i * 20), lambda m, x, y, s, i: m_pulse(m, x, y, s),
                 lambda m, x, y, s, i: m_plus(m, x, y, s), lambda m, x, y, s, i: m_plus(m, x, y, s * 0.7)],
    "giao-duc": [lambda m, x, y, s, i: m_ring(m, x, y, s), lambda m, x, y, s, i: m_stroke(m, x, y, s),
                 lambda m, x, y, s, i: m_dots(m, x, y, s), lambda m, x, y, s, i: m_triangle(m, x, y, s, rot=i * 20)],
    "chia-se": [lambda m, x, y, s, i: m_bubble(m, x, y, s, flip=i % 2 == 1), lambda m, x, y, s, i: m_quote(m, x, y, s),
                lambda m, x, y, s, i: m_heart(m, x, y, s), lambda m, x, y, s, i: m_bubble(m, x, y, s * 0.55, flip=i % 2 == 0)],
    "lam-dep": [lambda m, x, y, s, i: m_flower(m, x, y, s, rot=i * 14), lambda m, x, y, s, i: m_crescent(m, x, y, s, rot=i * 30),
                lambda m, x, y, s, i: m_flower(m, x, y, s * 0.6, rot=i * 30), lambda m, x, y, s, i: m_crescent(m, x, y, s * 0.6, rot=180)],
    "fnb": [lambda m, x, y, s, i: m_plate(m, x, y, s), lambda m, x, y, s, i: m_steam(m, x, y, s),
            lambda m, x, y, s, i: m_spice(m, x, y, s, seed=i), lambda m, x, y, s, i: m_spice(m, x, y, s * 0.7, seed=i + 7)],
}
EXTRA_SPARKS = {"lam-dep": 7}     # ánh nhũ: thêm lấp lánh nhỏ


def _blob(m, cx, cy, s, seed):
    """mảng mềm hữu cơ (làm đẹp): đa giác cong ngẫu nhiên, làm nhòe."""
    rng = np.random.default_rng(seed)
    n = 9
    rs = rng.uniform(0.75, 1.15, n)
    pts = [(cx + math.cos(2 * math.pi * k / n) * 170 * s * rs[k], cy + math.sin(2 * math.pi * k / n) * 130 * s * rs[k]) for k in range(n)]
    cv2.fillPoly(m, [np.int32(pts)], 1.0, cv2.LINE_AA)


def make(fid: str, li: int) -> np.ndarray:
    top, bot, o1, o2, t1, t2, bigs = FIELDS[fid]
    L = LAYOUTS[li]
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    if L["flip"]:
        x = 1 - x
    t = np.clip(0.65 * y + 0.35 * x, 0, 1)
    c = lambda h: np.array(hex_rgb(h), np.float32) / 255
    bg = c(top) * (1 - t) + c(bot) * t
    for (cx, cy, r, ci, a) in L["orbs"]:
        m = np.zeros((H, W), np.float32)
        cv2.circle(m, _p(W * cx, H * cy), int(r), 1.0, -1, cv2.LINE_AA)
        m = (cv2.GaussianBlur(m, (0, 0), r * 0.6) * a)[..., None]
        bg = bg * (1 - m) + c((o1, o2)[ci]) * m
    if fid == "lam-dep":         # 2 mảng mềm sáng
        for k, (sx, sy, s) in enumerate(L["slots"][:2]):
            m = np.zeros((H, W), np.float32)
            _blob(m, W * sx, H * sy, s, li * 3 + k)
            m = (cv2.GaussianBlur(m, (0, 0), 40) * 0.22)[..., None]
            bg = bg * (1 - m) + c("#FFFFFF") * m
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = bg
    out[..., 3] = 1
    # icon lớn mờ (tràn ra mép)
    big = np.zeros((H, W), np.uint8)
    bx, by, bs = L["big"]
    m_icon(big, bigs[li % len(bigs)], W * bx, H * by, bs)
    a = big.astype(np.float32) / 255 * 0.07
    out[..., :3] = out[..., :3] * (1 - a[..., None]) + a[..., None]
    # hình trang trí nét mảnh
    lay = np.zeros((H, W), np.uint8)
    fs = MOTIFS[fid]
    for k, (sx, sy, s) in enumerate(L["slots"]):
        fs[(k + li) % len(fs)](lay, W * sx, H * sy, s, li)
    a = lay.astype(np.float32) / 255 * 0.28
    out[..., :3] = out[..., :3] * (1 - a[..., None]) + a[..., None]
    sparks = list(L["sparks"])
    rng = np.random.default_rng(li + 11)
    for _ in range(EXTRA_SPARKS.get(fid, 0)):
        sx, sy = rng.uniform(0.04, 0.96), rng.choice([rng.uniform(0.03, 0.22), rng.uniform(0.78, 0.97)])
        sparks.append((sx, sy, int(rng.uniform(14, 24)), int(rng.integers(0, 2))))
    for (sx, sy, sz, ti) in sparks:
        sp = neon.icon_sprite("sparkle", sz, (t1, t2)[ti])
        h, w = sp.shape[:2]
        _blend(out, sp * 0.8, int(W * sx - w / 2), int(H * sy - h / 2))
    return (np.clip(out[..., :3], 0, 1) * 255).astype(np.uint8)


def sheet(root: Path, out: Path):
    from PIL import Image, ImageDraw, ImageFont
    tw, th, pad, hd = 240, 427, 12, 56
    img = Image.new("RGB", (pad + 5 * (tw + pad), len(FIELDS) * (hd + th + pad)), (24, 24, 24))
    d = ImageDraw.Draw(img)
    fnt = ImageFont.truetype(str(Path(__file__).resolve().parent.parent / "assets" / "fonts" / "BeVietnamPro-Bold.ttf"), 30)
    for r, fid in enumerate(FIELDS):
        y = r * (hd + th + pad)
        d.text((pad, y + 12), f"{r + 1}. {NAMES[fid]}", fill=(240, 240, 240), font=fnt)
        for k in range(5):
            im = Image.open(root / fid / f"nen-{k + 1}.png").convert("RGB").resize((tw, th), Image.LANCZOS)
            img.paste(im, (pad + k * (tw + pad), y + hd))
    img.save(out)


if __name__ == "__main__":
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "assets" / "backgrounds")
    for fid in FIELDS:
        (root / fid).mkdir(parents=True, exist_ok=True)
        for li in range(len(LAYOUTS)):
            cv2.imwrite(str(root / fid / f"nen-{li + 1}.png"), cv2.cvtColor(make(fid, li), cv2.COLOR_RGB2BGR))
        print(root / fid)
    if len(sys.argv) > 2:
        sheet(root, Path(sys.argv[2]))
        print(sys.argv[2])
