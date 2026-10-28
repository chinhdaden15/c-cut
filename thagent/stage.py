"""Lớp "sân khấu" quanh / sau lưng nhân vật cho Talking Head — làm video sinh động hơn ngoài chữ + callout ở giữa.

plan.stage = [{"id", "kind", "start", "end" (frame timeline), "tone": "gold"|"red"|"blue", …tham số theo kind}]
Mọi thứ "sau lưng" vẽ vào lớp behind (nhân vật tách nền đè lên) → không bao giờ che mặt; thứ phía trước (icon trước, khung HUD)
chỉ nằm ở mép / hai bên, tránh mặt.

Kind (tham số):
  giant_text  text — MỘT từ KHỔNG LỒ viền mảnh nghiêng 10° sau lưng, tràn hết bề ngang (cắt mép chút được); app tự phủ đen nền sau người 55%, zoom 1.5× và kéo khung cho mặt ở ~30% chiều cao — chọn từ NGẮN 1–2 chữ, start ĐÚNG lúc nói từ đó (không sớm) — LOÉ 1.5s
  orbit_icons icons ["3d:<id>", …] (2–5) — icon 3D lơ lửng hai bên — CHỈ khi lời nói nhắc ĐÚNG các vật đó (icon không liên quan = xấu);
              mặc định dùng giant_text / big_number / marquee (chữ viền sáng sau lưng)
  bokeh       — hạt sáng trôi + ánh sáng màu loang phía sau (nền cho đoạn nói dài)
  marquee     text — 2 băng chữ nghiêng chạy ngược chiều sau lưng (tên sản phẩm, slogan, CTA) — LOÉ 1.5s
  spotlight   — nền tối + đèn rọi vào người + tia tốc độ (hook, câu bẻ lái)
  big_number  text ("30%", "#1", "3X"), angle (mặc định -10) — số khổng lồ nằm xéo sau lưng, to tràn khung — LOÉ 1.5s
Chữ sau lưng (giant_text, marquee, big_number) chỉ loé 1.5s rồi mất dù end dài hơn — nhấn đúng từ đang nói, đặt start ngay lúc nói.
Lúc hiệu ứng vào app TỰ nhấn: zoom khung hình (punch đẩy vào rồi nhả; spotlight thì zoom lùi), loé sáng nhẹ, SFX hợp kiểu
(tắt bằng "accent": false). Không cần thêm zoom/flash/SFX tay cho các mốc này.
Nhịp: mỗi đoạn ý chính 1 kiểu (~6–10s đổi), không 2 kiểu nền (bokeh/spotlight) cùng lúc.
"""
from __future__ import annotations

import math
from functools import lru_cache

import cv2
import numpy as np

from . import neon as N
from .callouts import putf, blank, over, _hex, _tone, glow_layer, icon3d, _ease, _back, _rot, SAFE

KINDS = {"giant_text", "orbit_icons", "bokeh", "marquee", "spotlight", "big_number"}
FLASH_KINDS = {"giant_text", "marquee", "big_number"}   # chữ sau lưng: chỉ loé 1.5s rồi mất (để lâu rối)
FLASH_LEN = 45                         # 1.5s
FADE = 10


@lru_cache(maxsize=2)
def _grid(H, W):
    return np.mgrid[0:H, 0:W].astype(np.float32)


def _col(t):
    return N.PALETTES[_tone(t)][2]


@lru_cache(maxsize=32)
def _outline(text: str, size: int, color: str, width: int = 4, fill: float = 0.0) -> np.ndarray:
    m = N._mask(text, "display", size)
    m8 = (m > 0.4).astype(np.uint8) * 255
    edge = cv2.morphologyEx(m8, cv2.MORPH_GRADIENT, np.ones((width * 2 + 1,) * 2, np.uint8)).astype(np.float32) / 255
    a = np.clip(edge + cv2.GaussianBlur(edge, (0, 0), 10) * 0.8 + fill * m, 0, 1)
    out = blank(*m.shape)
    out[..., :3] = _hex(color) * a[..., None]
    out[..., 3] = a
    return out


def _thin(text: str, size: int, color: str) -> np.ndarray:
    """viền mảnh ~5px, phát sáng nhẹ, lòng chữ trong suốt."""
    m8 = np.pad((N._mask(text, "display", size) > 0.4).astype(np.uint8) * 255, 40)
    e = cv2.morphologyEx(m8, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8)).astype(np.float32) / 255
    a = np.clip(e + cv2.GaussianBlur(e, (0, 0), 4) * 0.5, 0, 1)
    out = blank(*a.shape)
    out[..., :3] = _hex(color) * a[..., None]
    out[..., 3] = a
    return out


def _tilt(t: np.ndarray, ang: float = 10) -> np.ndarray:
    h, w = t.shape[:2]
    d = int(np.hypot(h, w)) + 2
    p = blank(d, d)
    p[(d - h) // 2:(d - h) // 2 + h, (d - w) // 2:(d - w) // 2 + w] = t
    return _tight(cv2.warpAffine(p, cv2.getRotationMatrix2D((d / 2, d / 2), ang, 1), (d, d)), 4)


@lru_cache(maxsize=16)
def _giant(txt: str, col: str, W: int, H: int) -> np.ndarray:
    """chữ khổng lồ viền mảnh, nghiêng 10°, tràn hết bề ngang (cắt mép chút được); cụm 2 chữ mà một dòng quá thấp → xếp 2 dòng chồng sát."""
    return _tilt(_giant0(txt, col, W, H))


def _giant0(txt: str, col: str, W: int, H: int) -> np.ndarray:
    def one(line):
        t = _tight(_outline(line, 200, col, 6, 0.35))
        size = int(min(200 * W * 1.04 / t.shape[1], 200 * H * 0.42 / t.shape[0]))
        return _tight(_thin(line, size, col))
    t = one(txt)
    ws = txt.split()
    if len(ws) >= 2 and t.shape[0] < H * 0.16:
        k = max(range(1, len(ws)), key=lambda i: -abs(len(" ".join(ws[:i])) - len(" ".join(ws[i:]))))
        rows = [_tight(_outline(r, 200, col, 6, 0.35)) for r in (" ".join(ws[:k]), " ".join(ws[k:]))]
        sc = min(W * 1.04 / max(r.shape[1] for r in rows), H * 0.21 / max(r.shape[0] for r in rows))
        size = int(200 * sc)
        rows = [_tight(_thin(r, size, col), 8) for r in (" ".join(ws[:k]), " ".join(ws[k:]))]
        w = max(r.shape[1] for r in rows)
        out = blank(sum(r.shape[0] for r in rows), w)
        y = 0
        for r in rows:
            over(out, r, (w - r.shape[1]) // 2, y)
            y += r.shape[0]
        t = out
    return t


def _tight(t: np.ndarray, pad: int = 24) -> np.ndarray:
    """cắt lề trống quanh chữ (đo cỡ theo nét thật, không theo khung ảnh)."""
    ys, xs = np.where(t[..., 3] > 0.03)
    if not len(ys):
        return t
    return t[max(0, ys.min() - pad):ys.max() + pad + 1, max(0, xs.min() - pad):xs.max() + pad + 1]


@lru_cache(maxsize=64)
def _icon(name: str, size: int, blur: float) -> np.ndarray:
    s = icon3d(name if name.startswith("3d:") else "3d:" + name, int(size / 1.35))
    return cv2.GaussianBlur(s, (0, 0), blur) if blur else s


def _env(st: dict, f: int) -> float:
    a, b = int(st["start"]), int(st["end"])
    return min(1.0, (f - a + 1) / FADE, (b - f) / FADE)


def _head(anchors_tl, f, W, H):
    x = anchors_tl[min(max(f, 0), len(anchors_tl) - 1)] if anchors_tl else {}
    cx = x.get("face_cx", 0.5) * W
    cy = x.get("face_cy", 0.33) * H
    fh = x.get("face_h", 0.16) * H
    return cx, cy, fh, x


@lru_cache(maxsize=16)
def _row(text, size, color, n, gap, fill=0.0):
    t = _outline(text, size, color, 3, fill)
    out = blank(t.shape[0], (t.shape[1] + gap) * n)
    for i in range(n):
        over(out, t, i * (t.shape[1] + gap), 0)
    return out, t.shape[1] + gap


@lru_cache(maxsize=8)
def _strip(text, size, color, gap, angle, W):
    """băng chữ lặp đủ dài (≥ 2 khung + 1 chu kỳ), đã nghiêng sẵn — mỗi frame chỉ dịch."""
    t = _outline(text, size, color, 3, 0.15)
    per = t.shape[1] + gap
    n = int(2.2 * W / per) + 3
    row = blank(t.shape[0], per * n)
    for i in range(n):
        over(row, t, i * per, 0)
    row = np.pad(row, ((300, 300), (0, 0), (0, 0)))
    M = cv2.getRotationMatrix2D((row.shape[1] / 2, row.shape[0] / 2), angle, 1)
    return cv2.warpAffine(row, M, (row.shape[1], row.shape[0])), per


def put(dst: np.ndarray, src: np.ndarray, x: int, y: int, k: float = 1.0):
    """over() nhưng cắt phần nằm trong khung TRƯỚC khi nhân độ mờ — sprite lớn (băng chữ dài) không tốn công."""
    H, W = dst.shape[:2]
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0 or k <= 0.003:
        return
    over(dst, src[y0 - y:y1 - y, x0 - x:x1 - x] * k, x0, y0)


Q = 4              # hiệu ứng mềm (ánh sáng, tia, hạt) tính ở 1/Q độ phân giải rồi phóng lại — nhanh, nhìn như nhau


def _up(lay_small: np.ndarray, W: int, H: int) -> np.ndarray:
    return cv2.resize(lay_small, (W, H), interpolation=cv2.INTER_LINEAR)


@lru_cache(maxsize=4)
def _speed(W, H, color):
    """tia tốc độ (1/2 độ phân giải, ảnh lớn hơn khung để xoay không lộ góc)."""
    n = int(math.hypot(W, H) / 2) + 20
    def lines(m, w):
        for j in range(48):
            th = j / 48 * 2 * math.pi
            r0 = n * 0.3 + (j % 3) * 30
            cv2.line(m, (int(n + r0 * math.cos(th)), int(n + r0 * math.sin(th))), (int(n + 2 * n * math.cos(th)), int(n + 2 * n * math.sin(th))),
                     255, w, cv2.LINE_AA)
    return glow_layer(2 * n, 2 * n, lines, color, 1, 2)


def _stable_head(anchors_tl, a, b, W, H):
    """tâm đầu + cỡ mặt CỐ ĐỊNH suốt hiệu ứng (trung vị) — bám từng frame thì hiệu ứng rung theo đầu."""
    fr = [x for x in anchors_tl[max(a, 0):min(b, len(anchors_tl))] if x.get("face_h")] or [{}]
    med = lambda k, d: float(np.median([x.get(k, d) for x in fr]))
    return med("face_cx", 0.5) * W, med("face_cy", 0.33) * H, med("face_h", 0.16) * H


def span(st: dict) -> tuple[int, int]:
    a, b = int(st["start"]), int(st["end"])
    if st.get("kind") in FLASH_KINDS:
        b = min(b, a + FLASH_LEN)
    return a, b


def draw(st: dict, f: int, behind: np.ndarray, front: np.ndarray, anchors_tl: list[dict], fps: int = 30, total: int = 0, zm=(1.0, 0.5, 0.4)):
    a, b = span(st)
    if not (a <= f < b):
        return
    H, W = behind.shape[:2]
    k, col = st["kind"], _col(st.get("tone", "gold"))
    loc = f - a
    if k in FLASH_KINDS:                                       # loé: vào 3 frame, ra 4 frame
        e = min(1.0, (loc + 1) / 3, (b - f) / 4)
    else:
        e = _env(st, f)
    cx, cy, fh = _stable_head(anchors_tl, a, b, W, H)
    fh = round(fh / 20) * 20
    if k == "giant_text":
        txt = st.get("text", "").upper()                       # MỘT từ KHỔNG LỒ: rộng ~90% khung, cao tới ~¼ khung (như mẫu "REMOTE")
        t = _giant(txt, col, W, H)
        z = 0.88 + 0.12 * min(1.0, (loc + 1) / 6) + 0.0015 * loc   # nảy vào rồi phóng rất chậm
        if abs(z - 1) > 1e-3:
            t = cv2.resize(t, (max(1, int(t.shape[1] * z)), max(1, int(t.shape[0] * z))), interpolation=cv2.INTER_LINEAR)
        z0, zcx, zcy = zm                                       # khung đang zoom → mặt dời / to theo
        cy, fh = z0 * cy + (1 - z0) * zcy * H, fh * z0
        y = min(cy + fh * 0.35 - t.shape[0] / 2, cy + fh * 0.55 - t.shape[0])                    # ngang mặt–cằm: chữ lộ rõ hai bên người, không nấp sau đầu
        dim = blank(H, W)                                      # phủ đen sau lưng người nói → chữ sáng, nổi
        dim[..., 3] = 0.55
        putf(behind, dim, 0, 0, e)
        putf(behind, t, (W - t.shape[1]) / 2, y, e)
    elif k == "orbit_icons":
        ics = (st.get("icons") or [])[:5]
        slots = [(0.12, -0.55, True), (0.86, -0.8, True), (0.88, 0.75, False), (0.1, 0.95, False), (0.84, 1.9, False)]
        for i, (name, (sx, sy, back)) in enumerate(zip(ics, slots)):
            t0 = 4 * i
            if loc < t0:
                continue
            u = _back((loc - t0 + 1) / 12)
            spr = _icon(name, 170 if back else 190, 3.0 if back else 0.0)
            z = max(0.05, 0.4 + 0.6 * u)
            M = cv2.getRotationMatrix2D((spr.shape[1] / 2, spr.shape[0] / 2), 8 * math.sin((f + 17 * i) / 40) + (1 - min(1, u)) * 25, z)
            spr = cv2.warpAffine(spr, M, (spr.shape[1], spr.shape[0]), flags=cv2.INTER_LINEAR)   # xoay + co giãn một lần, mượt
            x = sx * W - spr.shape[1] / 2
            y = cy + sy * fh * 2 - spr.shape[0] / 2 + 10 * math.sin((f + 23 * i) * 2 * math.pi / 70)
            x = min(max(x, SAFE["side"] - 30), W - SAFE["side"] + 30 - spr.shape[1])
            y = min(max(y, SAFE["top"]), H - SAFE["bottom"] - spr.shape[0])
            putf(behind if back else front, spr, x, y, e * (0.85 if back else 1))
    elif k == "bokeh":
        w, h = W // Q, H // Q
        rng = np.random.default_rng(abs(hash(st["id"])) % 2 ** 31)
        n = 46
        xs, ys = rng.uniform(0, w, n), rng.uniform(25, h - 75, n)
        rs, sp, al = rng.uniform(1.5, 6.5, n), rng.uniform(0.1, 0.35, n), rng.uniform(0.25, 0.7, n)
        tones = rng.choice([st.get("tone", "gold"), "blue"], n)
        yy, xx = _grid(h, w)
        lay = blank(h, w)
        for lx, ly, tn, kk in ((w * 0.9, h * 0.2, st.get("tone", "gold"), 0.5), (w * 0.06, h * 0.58, "blue", 0.38)):
            lk = np.exp(-(((xx - lx - 10 * math.sin(loc / 60)) / (420 / Q)) ** 2 + ((yy - ly) / (520 / Q)) ** 2)) * kk
            lay[..., :3] += _hex(_col(tn)) * lk[..., None]
            lay[..., 3] = np.clip(lay[..., 3] + lk * 0.6, 0, 1)
        m = np.zeros((h * 4, w * 4), np.float32)              # hạt vẽ ở toạ độ ×4 (shift=2) → trôi mượt dưới 1 pixel
        cols = np.zeros((h * 4, w * 4, 3), np.float32)
        for i in range(n):
            yv = (ys[i] - loc * sp[i]) % (h - 75) + 25
            c = (int((xs[i] + 3 * math.sin(loc / 30 + i)) * 16), int(yv * 16))
            tw = 0.75 + 0.25 * math.sin(loc / 9 + i)
            cv2.circle(m, c, int(rs[i] * 16), float(al[i] * tw), -1, cv2.LINE_AA, shift=2)
            cv2.circle(cols, c, int(rs[i] * 16), tuple(float(v) for v in _hex(N.PALETTES[tones[i]][0])), -1, cv2.LINE_AA, shift=2)
        m = cv2.resize(cv2.GaussianBlur(np.clip(m, 0, 1), (0, 0), 4), (w, h), interpolation=cv2.INTER_AREA)
        cols = cv2.resize(cv2.GaussianBlur(cols, (0, 0), 4), (w, h), interpolation=cv2.INTER_AREA)
        lay[..., :3] += np.clip(cols, 0, 1) * m[..., None]
        lay[..., 3] = np.clip(lay[..., 3] + m, 0, 1)
        lay[..., :3] = np.minimum(lay[..., :3], lay[..., 3:4])
        over(behind, _up(lay, W, H) * e, 0, 0)
    elif k == "marquee":
        for i, (y, tn, d) in enumerate([(cy - fh * 0.6, st.get("tone", "gold"), 1), (cy + fh * 0.9, "red" if st.get("tone") != "red" else "gold", -1)]):
            rw, per = _strip(st.get("text", ""), int(fh * 0.72), _col(tn), 70, -8, W)
            t = (d * loc * 4.0) % per
            ca, sa = math.cos(math.radians(8)), math.sin(math.radians(8))
            putf(behind, rw, W / 2 - rw.shape[1] / 2 + (t - per / 2) * ca, y - rw.shape[0] / 2 - (t - per / 2) * sa, 0.85 * e)
    elif k == "spotlight":
        w, h = W // Q, H // Q
        yy, xx = _grid(h, w)
        spot = np.clip(1 - np.hypot((xx - cx / Q) / (640 / Q), (yy - (cy + fh) / Q) / (950 / Q)), 0, 1) ** 1.2
        lay = blank(h, w)
        lay[..., 3] = (1 - spot) * 0.62
        over(behind, _up(lay, W, H) * e, 0, 0)
        sl = _speed(W, H, "#FFFFFF")
        n = sl.shape[0] // 2
        M = cv2.getRotationMatrix2D((n, n), loc * 0.25, 1 + 0.03 * math.sin(loc / 3))
        M[0, 2] += cx / 2 - n
        M[1, 2] += cy / 2 - n
        lines = cv2.warpAffine(sl, M, (W // 2, H // 2))
        over(behind, _up(lines, W, H) * (0.5 * e), 0, 0)
    elif k == "big_number":
        s = _bigtilt(st.get("text", ""), int(fh * 2.3), _tone(st.get("tone", "gold")), float(st.get("angle", -10)), W)
        z = 1.18 - 0.18 * _ease((loc + 1) / 5)
        M = cv2.getRotationMatrix2D((s.shape[1] / 2, s.shape[0] / 2), 0, z)
        s2 = cv2.warpAffine(s, M, (s.shape[1], s.shape[0]), flags=cv2.INTER_LINEAR)
        putf(behind, s2, W / 2 - s.shape[1] / 2, cy - fh * 0.4 - s.shape[0] / 2, 0.85 * e)


@lru_cache(maxsize=8)
def _bigtilt(text, size, tone, angle, W):
    """số khổng lồ nằm xéo — nét chữ rộng ≈ cả khung (đọc trọn, quầng sáng được tràn mép)."""
    s = N.text_sprite(text, "display", size, tone, glow_k=0.8)
    from .callouts import _ink
    y0, y1, x0, x1 = _ink(s)
    k = W * 0.96 / max(1, x1 - x0)
    s = cv2.resize(s, None, fx=k, fy=k, interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR)
    size = int(size * k)
    s = np.pad(s, ((size // 2, size // 2), (size // 3, size // 3), (0, 0)))
    M = cv2.getRotationMatrix2D((s.shape[1] / 2, s.shape[0] / 2), -angle, 1)
    return cv2.warpAffine(s, M, (s.shape[1], s.shape[0]), flags=cv2.INTER_LINEAR)


@lru_cache(maxsize=8)
def _pill(text, tone):
    return N.pill_sprite(text, 44, tone)


@lru_cache(maxsize=8)
def _big(text, size, tone):
    return N.text_sprite(text, "display", size, tone, glow_k=0.8)


# nhấn lúc hiệu ứng vào: zoom khung hình + loé sáng nhẹ + SFX (kiểu: (zoom, độ zoom, loé, âm, dB))
ACCENT = {"spotlight": ("out", 1.16, 0.22, "hit_02", -12), "giant_text": ("punch", 1.08, 0.16, "impact_soft", -13),
          "big_number": ("punch", 1.10, 0.20, "impact_soft", -12),
          "orbit_icons": ("punch", 1.06, 0.12, "pop_soft", -14), "marquee": ("punch", 1.06, 0.12, "card_01", -14),
          "bokeh": (None, 0, 0.10, "shimmer_light", -17)}


GIANT_ZOOM = 1.5
GIANT_FACE_Y = 0.30          # sau khi zoom, tâm mặt đặt ở ~30% chiều cao → khoảng trống trên đầu cân, người không bị đẩy xuống


def fit_zoom(plan, anchors_tl, H: int) -> None:
    """chọn tâm zoom dọc cho từng chữ sau lưng để mặt (đã phóng) nằm đúng GIANT_FACE_Y — zoom + kéo khung lên."""
    for st in getattr(plan, "stage", None) or []:
        if st.get("kind") == "giant_text":
            a, b = span(st)
            _, cy, _ = _stable_head(anchors_tl, a, b, 1, H)
            z = GIANT_ZOOM
            st["_zcy"] = min(1.0, max(0.0, (GIANT_FACE_Y * H - z * cy) / ((1 - z) * H)))


def _accent(st):
    a = ACCENT.get(st.get("kind"))
    if not a or st.get("accent") is False or not st.get("enabled", True):
        return None
    return a


def zoom_events(plan) -> list:
    """zoom khung hình lúc hiệu ứng vào: punch = đẩy vào nhanh ~0.8s rồi nhả; out = bắt đầu gần rồi lùi dần (hook)."""
    from types import SimpleNamespace as NS
    out = []
    for st in getattr(plan, "stage", None) or []:
        a = _accent(st)
        if a and a[0]:
            s0 = int(st["start"])
            if st.get("kind") == "giant_text":          # chữ sau lưng: zoom vào người suốt lúc chữ hiện → bớt trống phía trên, chữ tràn khung
                out.append(NS(type="zoom", enabled=True, start=s0, end=int(st["end"]), params={"scale": GIANT_ZOOM, "mode": "punch", "cx": 0.5, "cy": st.get("_zcy", 0.6)}))
                continue
            out.append(NS(type="zoom", enabled=True, start=s0, end=s0 + (14 if a[0] == "punch" else min(60, int(st["end"]) - s0)),
                          params={"scale": a[1], "mode": a[0], "cx": 0.5, "cy": 0.32}))
    return out


def flash_events(plan) -> list:
    from types import SimpleNamespace as NS
    return [NS(type="flash", enabled=True, start=int(st["start"]), end=int(st["start"]) + 8, params={"opacity": a[2]})
            for st in getattr(plan, "stage", None) or [] if (a := _accent(st)) and a[2] > 0]


def sound_events(plan) -> list:
    from .schema import SoundEvent
    return [SoundEvent(id=f"stage_{st['id']}", asset=a[3], linked_event=st["id"], hit=int(st["start"]) + 1, gain_db=a[4], priority=4)
            for st in getattr(plan, "stage", None) or [] if (a := _accent(st)) and a[3]]


def draw_all(plan, f: int, behind, front, anchors_tl, fps: int = 30):
    from .render import zoom_at
    zm = zoom_at(plan, f)
    for st in getattr(plan, "stage", None) or []:
        if st.get("enabled", True):
            draw(st, f, behind, front, anchors_tl, fps, plan.duration_frames, zm)


def check(plan, fps: int) -> list[tuple[str, str]]:
    from . import timeline as Tm
    out = []
    sts = [s for s in getattr(plan, "stage", None) or [] if s.get("enabled", True)]
    for s in sts:
        tag = f"stage {s.get('id')} ({s.get('kind')}) {Tm.tc(int(s['start']))}"
        if s.get("kind") not in KINDS:
            out.append(("error", f"{tag}: không có kiểu này (có: {', '.join(sorted(KINDS))})"))
            continue
        if s["kind"] in ("giant_text", "marquee", "big_number") and not s.get("text"):
            out.append(("error", f"{tag}: thiếu text"))
        if s["kind"] == "orbit_icons":
            from . import icons3d as K
            for n in s.get("icons") or []:
                if not K.exists(n.removeprefix("3d:")):
                    out.append(("error", f"{tag}: không có icon 3D {n} — tra: python -m thagent.tools icon3d <từ khoá>"))
    bgs = [s for s in sts if s.get("kind") in ("bokeh", "spotlight")]
    for x, y in zip(bgs, bgs[1:]):
        if y["start"] < x["end"]:
            out.append(("warn", f"stage {x['id']} và {y['id']}: hai kiểu nền chồng nhau — rối mắt"))
    return out
