"""Motion Graphics toàn khung (đoạn trám ~10s) — học bố cục từ mẫu MG người dùng gửi:
nền trắng + lưới mờ + bóng lá, chữ đen đậm + chữ dẫn nhỏ, thẻ highlight màu, ảnh bo góc có bóng,
mũi tên vẽ dần, sơ đồ vòng tròn, danh sách tích, mã vạch trang trí. Vẽ thủ tục, theo frame.
Màu nhấn dùng 3 tông cố định của dự án (gold / red / blue)."""
from __future__ import annotations

import math
import os
from functools import lru_cache

import cv2
import numpy as np

from . import imgio
from . import neon
from .paths import ROOT
from .typography import _blend, clamp01, ease_in_cubic, ease_out_back, ease_out_cubic, ease_out_quart, hex_rgb

W, H = 1080, 1920
ACC = {"gold": ("#FFC83A", "#FF9A1F"), "red": ("#FF6A5A", "#E8202F"), "blue": ("#4FC3FF", "#1E6BFF")}


@lru_cache(maxsize=4)
def _bg_file(path: str) -> np.ndarray:
    im = imgio.must_read(path)
    if im.shape[:2] != (H, W):
        im = cv2.resize(im, (W, H), interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2RGB).astype(np.float32) / 255


def background(seed: int = 0, bg: str | None = None) -> np.ndarray:
    """nền kênh (ảnh assets/backgrounds) nếu có, không thì nền xanh vẽ sẵn."""
    if bg:
        from pathlib import Path
        p = Path(bg) if Path(bg).is_absolute() else ROOT / "assets" / "backgrounds" / bg
        if p.exists():
            return _bg_file(str(p))
    return _blue_bg(seed)


@lru_cache(maxsize=4)
def _blue_bg(seed: int = 0) -> np.ndarray:
    """Nền đơn giản: gradient sáng + vài element nhấn nhá (quầng màu mờ, vòng mảnh, lấp lánh) theo 3 tông."""
    y = np.linspace(0, 1, H)[:, None, None]
    x = np.linspace(0, 1, W)[None, :, None]
    # gradient xanh dương như mẫu: đậm góc trên trái → sáng dần góc dưới phải
    t = np.clip(0.65 * y + 0.35 * x, 0, 1)
    top, bot = np.array([0.16, 0.33, 0.86]), np.array([0.62, 0.74, 0.99])
    bg = top * (1 - t) + bot * t
    def orb(cx, cy, r, col, a):
        m = np.zeros((H, W), np.float32)
        cv2.circle(m, (int(cx), int(cy)), int(r), 1.0, -1, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), r * 0.6) * a
        c = np.array(hex_rgb(col), np.float32) / 255
        return m[..., None], c
    rng = np.random.default_rng(seed)
    for (cx, cy, r, col, a) in [(W * 0.92, H * 0.10, 280, "#8FB5FF", 0.45), (W * 0.05, H * 0.88, 320, "#FFFFFF", 0.25),
                                (W * rng.uniform(0.6, 0.9), H * 0.62, 180, "#5B8CFF", 0.25)]:
        m, c = orb(cx, cy, r, col, a)
        bg = bg * (1 - m) + c * m
    out = np.zeros((H, W, 4), np.float32); out[..., :3] = bg; out[..., 3] = 1
    lay = np.zeros((H, W), np.uint8)
    cv2.circle(lay, (int(W * 0.88), int(H * 0.16)), 150, 255, 2, cv2.LINE_AA)
    cv2.circle(lay, (int(W * 0.10), int(H * 0.80)), 110, 255, 2, cv2.LINE_AA)
    for k in range(5):   # chấm nhỏ
        cv2.circle(lay, (int(W * (0.07 + 0.035 * k)), int(H * 0.12)), 5, 255, -1, cv2.LINE_AA)
    a = lay.astype(np.float32) / 255 * 0.25
    out[..., :3] = out[..., :3] * (1 - a[..., None]) + np.array([1.0, 1.0, 1.0]) * a[..., None]
    for (sx, sy, sz, tone) in [(W * 0.83, H * 0.07, 50, "gold"), (W * 0.15, H * 0.93, 40, "blue"), (W * 0.93, H * 0.55, 30, "gold")]:
        sp = neon.icon_sprite("sparkle", sz, tone)
        h, w = sp.shape[:2]
        _blend(out, sp * 0.8, int(sx - w / 2), int(sy - h / 2))
    return np.clip(out[..., :3], 0, 1)


@lru_cache(maxsize=256)
def ink_text(text: str, role: str, size: int, color: str = "#FFFFFF") -> np.ndarray:
    m = neon._mask(text, role, size)
    ys, xs = np.where(m > 0.02)
    m = m[max(ys.min() - 4, 0):ys.max() + 5, max(xs.min() - 4, 0):xs.max() + 5]
    out = np.zeros(m.shape + (4,), np.float32)
    out[..., :3] = np.array(hex_rgb(color), np.float32) / 255.0 * m[..., None]
    out[..., 3] = m
    return out


@lru_cache(maxsize=64)
def tag(text: str, tone: str, size: int = 40) -> np.ndarray:
    """Thẻ highlight: khối màu chuyển, chữ trắng đậm, hơi nghiêng như dán băng keo."""
    t = ink_text(text, "display_bold", size, "#FFFFFF")
    th, tw = t.shape[:2]
    ph, pw = int(th + size * 0.7), int(tw + size * 0.9)
    a, b = (np.array(hex_rgb(c), np.float32) / 255 for c in ACC[tone])
    g = np.linspace(0, 1, pw)[None, :, None]
    out = np.zeros((ph, pw, 4), np.float32)
    out[..., :3] = a * (1 - g) + b * g
    out[..., 3] = 1
    _blend(out, t, (pw - tw) // 2, (ph - th) // 2)
    pad = 30
    o2 = np.zeros((ph + 2 * pad, pw + 2 * pad, 4), np.float32)
    sh = np.zeros(o2.shape[:2], np.float32); sh[pad + 8:pad + 8 + ph, pad + 6:pad + 6 + pw] = 1
    o2[..., 3] = cv2.GaussianBlur(sh, (0, 0), 10) * 0.25
    _blend(o2, out, pad, pad)
    M = cv2.getRotationMatrix2D((o2.shape[1] / 2, o2.shape[0] / 2), 2.0, 1.0)
    return cv2.warpAffine(o2, M, (o2.shape[1], o2.shape[0]), flags=cv2.INTER_LINEAR)


@lru_cache(maxsize=32)
def photo_card(path: str, w: int, h: int, label: str = "") -> np.ndarray:
    img = cv2.cvtColor(imgio.must_read(path), cv2.COLOR_BGR2RGB).astype(np.float32) / 255
    ih, iw = img.shape[:2]
    s = max(w / iw, h / ih)
    img = cv2.resize(img, (int(iw * s) + 1, int(ih * s) + 1), interpolation=cv2.INTER_AREA)
    y0, x0 = (img.shape[0] - h) // 2, (img.shape[1] - w) // 2
    img = img[y0:y0 + h, x0:x0 + w]
    r, pad = 26, 50
    mask = np.zeros((h, w), np.uint8)
    cv2.rectangle(mask, (r, 0), (w - r, h), 255, -1); cv2.rectangle(mask, (0, r), (w, h - r), 255, -1)
    for cx, cy in [(r, r), (w - r, r), (r, h - r), (w - r, h - r)]:
        cv2.circle(mask, (cx, cy), r, 255, -1, cv2.LINE_AA)
    m = mask.astype(np.float32) / 255
    out = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.float32)
    sh = np.zeros(out.shape[:2], np.float32); sh[pad + 18:pad + 18 + h, pad + 8:pad + 8 + w] = m
    out[..., 3] = cv2.GaussianBlur(sh, (0, 0), 22) * 0.35
    reg = out[pad:pad + h, pad:pad + w]
    reg[..., :3] = reg[..., :3] * (1 - m[..., None]) + img * m[..., None]
    reg[..., 3] = reg[..., 3] * (1 - m) + m
    if label:
        lab = ink_text(label, "semi", 24, "#FFFFFF")
        lh, lw = lab.shape[:2]
        box = np.zeros((lh + 16, lw + 24, 4), np.float32); box[..., 3] = 0.45
        _blend(out, box, pad + 18, pad + 18)
        _blend(out, lab, pad + 30, pad + 26)
    if os.path.basename(path).startswith("i_"):   # ảnh minh họa ngoài dự án → ghi rõ, chữ nghiêng góc dưới phải
        t = ink_text("Hình ảnh minh họa", "semi", 24, "#FFFFFF")
        th, tw = t.shape[:2]
        t = cv2.warpAffine(t, np.float32([[1, -0.22, 0.22 * th], [0, 1, 0]]), (tw + int(0.22 * th) + 2, th))
        th, tw = t.shape[:2]
        box = np.zeros((th + 14, tw + 22, 4), np.float32); box[..., 3] = 0.45
        _blend(out, box, pad + w - tw - 40, pad + h - th - 32)
        _blend(out, t, pad + w - tw - 29, pad + h - th - 25)
    return out


@lru_cache(maxsize=4)
def barcode(w: int = 170, h: int = 46) -> np.ndarray:
    rng = np.random.default_rng(7)
    out = np.zeros((h, w, 4), np.float32)
    x = 0
    while x < w:
        bw = int(rng.choice([2, 2, 3, 5]))
        if rng.random() > 0.4:
            out[:, x:x + bw, :3] = 0.95; out[:, x:x + bw, 3] = 0.95
        x += bw + int(rng.choice([2, 3]))
    return out


def _put(dst, spr, cx, cy, o=1.0, s=1.0, blur=0.0, rot=0.0):
    if o <= 0.003:
        return
    if abs(s - 1) > 0.002 or abs(rot) > 0.01:
        h, w = spr.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), rot, s)
        nw, nh = int(w * s * 1.2) + 2, int(h * s * 1.2) + 2
        M[0, 2] += (nw - w) / 2; M[1, 2] += (nh - h) / 2
        spr = cv2.warpAffine(spr, M, (nw, nh), flags=cv2.INTER_LINEAR)
    if blur > 0.6:
        spr = cv2.GaussianBlur(spr, (0, 0), blur / 2)
    h, w = spr.shape[:2]
    _blend(dst, spr * o, int(cx - w / 2), int(cy - h / 2))


def _enter(f, t0, dur=9):
    return clamp01((f - t0 + 1) / dur)


# ---------------- phần tử cảnh ----------------
SAFE_W = 940          # vùng an toàn ngang: chừa lề 70px mỗi bên


def word_chunks(el) -> list[list[int]]:
    """Câu dài hơn vùng an toàn → cắt thành ít đoạn 1 dòng nhất, độ dài đều nhau, ưu tiên ngắt sau dấu phẩy/chấm."""
    words = el["text"].split()
    font = neon.nfont(el.get("role", "semi"), el["size"])
    sp = font.getlength(" ")
    adv = [font.getlength(w) for w in words]
    width = lambda i, j: sum(adv[i:j]) + sp * (j - i - 1)
    n = len(words)
    if width(0, n) <= SAFE_W:
        return [list(range(n))]
    for parts in range(2, n + 1):
        target = width(0, n) / parts
        # best[k][j]: chi phí nhỏ nhất cắt words[:j] thành k đoạn
        INF = float("inf")
        best = [[(INF, None)] * (n + 1) for _ in range(parts + 1)]
        best[0][0] = (0.0, None)
        for k in range(1, parts + 1):
            for j in range(1, n + 1):
                for i in range(k - 1, j):
                    if best[k - 1][i][0] == INF or width(i, j) > SAFE_W:
                        continue
                    cost = best[k - 1][i][0] + (width(i, j) - target) ** 2
                    if j < n and words[j - 1][-1] in ",.;:":
                        cost -= target ** 2 * 0.15        # thưởng cho chỗ ngắt tự nhiên
                    if j - i == 1 and n > 1:
                        cost += target ** 2               # tránh đoạn chỉ 1 từ
                    if cost < best[k][j][0]:
                        best[k][j] = (cost, i)
        if best[parts][n][0] < INF:
            cuts, j = [], n
            for k in range(parts, 0, -1):
                i = best[k][j][1]; cuts.append(list(range(i, j))); j = i
            return cuts[::-1]
    return [[k] for k in range(n)]


def el_words(dst, f, el):
    """Chữ dẫn rơi từng từ (đúng frame từ được nói). Câu dài: từng đoạn hiện rồi nhường đoạn sau."""
    words = el["text"].split()
    font = neon.nfont(el.get("role", "semi"), el["size"])
    sp = font.getlength(" ")
    fr = el.get("word_frames") or []
    wf = lambda k: fr[k] if k < len(fr) else (fr[-1] + 3 * (k - len(fr) + 1) if fr else el["t"] + 3 * k)
    chunks = word_chunks(el)
    ci = 0
    for i in range(1, len(chunks)):
        if f >= wf(chunks[i][0]):
            ci = i
    idx = chunks[ci]
    nxt = wf(chunks[ci + 1][0]) if ci + 1 < len(chunks) else None
    fade = clamp01((nxt - f) / 4) if nxt is not None else 1.0   # đoạn cũ mờ đi ngay trước đoạn mới
    adv = [font.getlength(words[k]) for k in idx]
    total = sum(adv) + sp * (len(idx) - 1)
    x = el["x"] - total / 2 if el.get("align", "center") == "center" else el["x"]
    for k, a in zip(idx, adv):
        s = ink_text(words[k], el.get("role", "semi"), el["size"], el.get("color", "#EAF1FF"))
        e = _enter(f, wf(k), 7)
        if e > 0:
            kk = ease_out_cubic(e)
            _put(dst, s, x + a / 2, el["y"] - (1 - kk) * 40, o=clamp01(e * 1.6) * fade, blur=(1 - kk) * 6)
        x += a + sp


def big_geom(el) -> tuple[int, int, int]:
    """(cỡ chữ sau khi thu vừa khung, y tâm, chiều cao nét) — dùng chung cho vẽ + đặt thẻ + preflight."""
    size = el["size"]
    w0 = ink_text(el["text"], "display", size, "#FFFFFF").shape[1]
    if w0 > SAFE_W:
        size = int(size * SAFE_W / w0)
    y = max(el["y"], 470 + int(size * 0.45)) if el.get("auto_y", True) else el["y"]
    return size, y, ink_text(el["text"], "display", size, "#FFFFFF").shape[0]


def layout_scene(sc: dict) -> dict:
    """Thẻ (tag) không ghi y → đặt sát dưới chữ lớn đứng trước nó, cách 44px theo nét thật."""
    if sc.get("_laid"):
        return sc
    last_big = None
    for el in sc["elements"]:
        if el["type"] == "big":
            last_big = el
        if el["type"] == "tag":   # thẻ dài → thu nhỏ cho vừa vùng an toàn
            tw = tag(el["text"], el.get("tone", "gold"), el.get("size", 64)).shape[1] - 60
            if tw > SAFE_W - 20:
                el["size"] = int(el.get("size", 64) * (SAFE_W - 20) / tw)
        if el["type"] == "tag" and el.get("y") is None:
            th = tag(el["text"], el.get("tone", "gold"), el.get("size", 64)).shape[0] - 60   # bỏ phần bóng đổ
            if last_big is not None:
                _, by, bh = big_geom(last_big)
                el["y"] = int(by + bh / 2 + 44 + th / 2)
            else:
                el["y"] = 640
    sc["_laid"] = True
    return sc


def el_big(dst, f, el):
    size, y, _ = big_geom(el)
    el = {**el, "size": size, "y": y}
    s = ink_text(el["text"], "display", el["size"], "#FFFFFF")
    sh = cv2.GaussianBlur(s[..., 3], (0, 0), el["size"] * 0.06) * 0.35   # bóng xanh đậm cho chữ trắng
    s2 = np.zeros_like(s); s2[..., :3] = np.array([0.05, 0.12, 0.4]) * sh[..., None]; s2[..., 3] = sh
    s2 = np.pad(s2, ((0, 8), (0, 0), (0, 0)))[:-8] if False else np.concatenate([np.zeros((6,) + s2.shape[1:], np.float32), s2[:-6]], 0)
    _blend(s2, s, 0, 0); s = s2
    e = _enter(f, el["t"], 10)
    if e > 0:
        k = ease_out_back(e, 1.6)
        _put(dst, s, el["x"], el["y"], o=clamp01(e * 2), s=0.7 + 0.3 * k, blur=(1 - e) * 10)


def el_tag(dst, f, el):
    s = tag(el["text"], el.get("tone", "gold"), el.get("size", 64))
    e = _enter(f, el["t"], 8)
    if e > 0:
        h, w = s.shape[:2]
        k = ease_out_quart(e)
        cut = int(w * k)
        part = s.copy(); part[:, cut:] = 0
        _put(dst, part, el["x"], el["y"])


def el_photo(dst, f, el):
    c = photo_card(el["file"], el["w"], el["h"], el.get("label", ""))
    e = _enter(f, el["t"], 12)
    if e > 0:
        k = ease_out_quart(e)
        drift = (f - el["t"]) * 0.25
        _put(dst, c, el["x"] + (1 - k) * el.get("from_dx", 0), el["y"] + (1 - k) * el.get("from_dy", 120) - drift * 0.2,
             o=clamp01(e * 1.8), s=0.92 + 0.08 * k, rot=el.get("rot", 0.0) * k, blur=(1 - k) * 8)


def el_arrow(dst, f, el):
    """Mũi tên vẽ tay cong, vẽ dần theo thời gian."""
    e = _enter(f, el["t"], 12)
    if e <= 0:
        return
    (x0, y0), (x1, y1) = el["p0"], el["p1"]
    bend = el.get("bend", 0.25)
    mx, my = (x0 + x1) / 2 - (y1 - y0) * bend, (y0 + y1) / 2 + (x1 - x0) * bend
    n = 40
    pts = [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * mx + t * t * x1, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * my + t * t * y1)
           for t in np.linspace(0, ease_out_cubic(e), n)]
    lay = np.zeros((H, W), np.uint8)
    cv2.polylines(lay, [np.array(pts, np.int32)], False, 255, 5, cv2.LINE_AA)
    if e >= 0.95:
        ex, ey = pts[-1]; px, py = pts[-4]
        ang = math.atan2(ey - py, ex - px)
        for da in (2.6, -2.6):
            cv2.line(lay, (int(ex), int(ey)), (int(ex + 28 * math.cos(ang + da)), int(ey + 28 * math.sin(ang + da))), 255, 5, cv2.LINE_AA)
    a = lay.astype(np.float32) / 255
    dst *= (1 - a[..., None]); dst[..., 3] += a; dst[..., :3] += a[..., None]   # mũi tên trắng


def el_circle(dst, f, el):
    """Sơ đồ vòng tròn: vòng vẽ dần + các nút có nhãn xuất hiện theo lời nói, xoay nhẹ."""
    e = _enter(f, el["t"], 14)
    if e <= 0:
        return
    cx, cy, r = el["x"], el["y"], el["r"]
    a1, a2 = (np.array(hex_rgb(c), np.float32) / 255 for c in ACC[el.get("tone", "blue")])
    lay = np.zeros((H, W, 4), np.float32)
    sweep = 360 * ease_out_cubic(e)
    ring = np.zeros((H, W), np.uint8)
    for a0 in range(0, int(sweep), 12):   # nét đứt như mẫu
        cv2.ellipse(ring, (int(cx), int(cy)), (r, r), -90 + (f - el["t"]) * 0.3, a0, min(a0 + 7, sweep), 255, 5, cv2.LINE_AA)
    rm = ring.astype(np.float32) / 255
    yy = (np.arange(H)[:, None] - (cy - r)) / (2 * r)
    col = a1 * (1 - np.clip(yy, 0, 1))[..., None] + a2 * np.clip(yy, 0, 1)[..., None]
    lay[..., :3] = rm[..., None]; lay[..., 3] = rm    # quỹ đạo trắng trên nền xanh
    _blend(dst, lay, 0, 0)
    rot = (f - el["t"]) * 0.4
    for k, (label, t) in enumerate(el["nodes"]):
        ang = math.radians(-90 + rot + 360 * k / len(el["nodes"]))
        nx, ny = cx + r * math.cos(ang), cy + r * math.sin(ang)
        ee = _enter(f, t, 9)
        if ee <= 0:
            continue
        dot = neon.icon_sprite("ring", 70, el.get("tone", "blue"))
        _put(dst, dot, nx, ny, o=clamp01(ee * 2), s=0.3 + 0.7 * ease_out_back(ee, 2.2))
        lab = tag(label, el.get("tone", "blue"), 34)
        _put(dst, lab, nx, ny + 70, o=clamp01(ee * 2), s=0.8 + 0.2 * ease_out_cubic(ee))


def el_checks(dst, f, el):
    """Danh sách tích: mỗi dòng có ô tích màu + chữ đen, xuất hiện theo lời."""
    for k, (text, t) in enumerate(el["items"]):
        e = _enter(f, t, 9)
        if e <= 0:
            continue
        y = el["y"] + k * el.get("gap", 110)
        k2 = ease_out_cubic(e)
        chk = neon.icon_sprite("check", 78, el.get("tone", "gold"))   # icon Flaticon Uicons
        _put(dst, chk, el["x"], y, o=clamp01(e * 2), s=0.4 + 0.6 * ease_out_back(e, 2.4))
        txt = ink_text(text, "display_bold", el.get("size", 48), "#FFFFFF")
        th, tw = txt.shape[:2]
        _put(dst, txt, el["x"] + 70 + tw / 2 - (1 - k2) * 30, y, o=clamp01(e * 1.6), blur=(1 - k2) * 6)


def el_barcode(dst, f, el):
    e = _enter(f, el["t"], 8)
    _put(dst, barcode(), el["x"], el["y"], o=e * 0.9)


def el_icon(dst, f, el):
    s = neon.icon_sprite(el["name"], el.get("size", 120), el.get("tone", "gold"))
    e = _enter(f, el["t"], 10)
    if e > 0:
        _put(dst, s, el["x"], el["y"] + 6 * math.sin((f - el["t"]) / 10), o=clamp01(e * 2), s=0.3 + 0.7 * ease_out_back(e, 2.4))


def el_photos(dst, f, el):
    """Chuỗi 2–3 ảnh trong một cảnh, mỗi ảnh vào đúng lúc nói tới nội dung của nó: ảnh mới trượt từ phải vào
    đè lên, ảnh cũ lùi ra sau (nhỏ lại, nghiêng, mờ dần) như xấp ảnh; ảnh đang xem zoom chậm."""
    items = [it for it in el["items"] if f >= it["t"]]
    if not items:
        return
    x, y, w, h = el["x"], el["y"], el["w"], el["h"]
    n = len(items)
    for k, it in enumerate(items):
        depth = n - 1 - k          # 0 = ảnh trên cùng
        if depth > 2:
            continue
        # khi ảnh kế tiếp vào, ảnh này lùi dần (theo tiến độ của ảnh trên nó)
        back = 0.0
        if depth > 0:
            nxt = items[k + 1]["t"]
            back = ease_out_cubic(clamp01((f - nxt + 1) / 18)) + (depth - 1)
        e = _enter(f, it["t"], 18)          # vào chậm, kịp nhìn
        kk = ease_out_quart(e)
        side = -1 if k % 2 else 1
        c = photo_card(it["file"], w, h, it.get("label", ""))
        zoom = 1 + 0.03 * clamp01((f - it["t"]) / 90) if depth == 0 else 1
        _put(dst, c, x + (1 - kk) * 700 - back * side * 70, y - back * 70,
             o=clamp01(e * 1.8) * (1 - 0.25 * min(back, 2)), s=(0.94 + 0.06 * kk) * (1 - 0.08 * back) * zoom,
             rot=back * side * 4.0, blur=(1 - kk) * 6 + back * 1.5)


DRAW = {"photos": el_photos, "words": el_words, "big": el_big, "tag": el_tag, "photo": el_photo, "arrow": el_arrow, "circle": el_circle,
        "checks": el_checks, "barcode": el_barcode, "icon": el_icon}


def render_scene_frame(segment: dict, f: int) -> np.ndarray | None:
    """Trả về RGB float (H,W,3) nếu f thuộc đoạn MG, kèm alpha chuyển cảnh (để hòa với video)."""
    if not (segment["start"] <= f < segment["end"]):
        return None
    out = np.zeros((H, W, 4), np.float32)
    out[..., :3] = background(segment.get("seed", 0), segment.get("bg")); out[..., 3] = 1
    scenes = segment["scenes"]
    for i, sc in enumerate(scenes):
        if not (sc["start"] <= f < sc["end"]):
            continue
        lay = np.zeros((H, W, 4), np.float32)
        for el in layout_scene(sc)["elements"]:
            if segment.get("swap"):      # kênh nền hồng/cam: thẻ vàng chìm → đổi vàng ↔ xanh
                t = el.get("tone", "blue" if el["type"] == "circle" else "gold")
                el = dict(el, tone={"gold": "blue", "blue": "gold"}.get(t, t))
            DRAW[el["type"]](lay, f, el)
        # chuyển cảnh trong đoạn: cảnh cũ trượt lên + nhòe ở 6 frame cuối
        x = clamp01((f - (sc["end"] - 6) + 1) / 6) if i < len(scenes) - 1 else 0
        if x > 0:
            k = ease_in_cubic(x)
            M = np.float32([[1, 0, 0], [0, 1, -k * 160]])
            lay = cv2.warpAffine(lay, M, (W, H))
            lay = cv2.GaussianBlur(lay, (0, 0), 1 + k * 10) * (1 - k)
        _blend(out, lay, 0, 0)
    return out[..., :3]


_YY, _XX = np.mgrid[0:H, 0:W].astype(np.float32)


def mg_alpha(segment: dict, f: int):
    """Chuyển cảnh vòng tròn (học từ mẫu MG 3): hình tròn nở từ tâm để mở MG (10 frame), thu lại khi rời (8 frame).
    Trả về mặt nạ (H,W,1) có viền mềm."""
    cx, cy = segment.get("reveal_xy", (540, 980))
    R = math.hypot(max(cx, W - cx), max(cy, H - cy)) + 40
    a = ease_out_cubic(clamp01((f - segment["start"] + 1) / 10))
    b = ease_out_cubic(clamp01((segment["end"] - f) / 8))
    r = R * min(a, b)
    if r >= R - 1:
        return 1.0
    d = np.sqrt((_XX - cx) ** 2 + (_YY - cy) ** 2)
    return np.clip((r - d) / 18 + 0.5, 0, 1)[..., None]


SLIDE_IN, SLIDE_OUT = 8, 8


def mg_slide(segment: dict, f: int) -> float:
    """Chuyển cảnh trượt (thay vòng tròn — vòng tròn để lộ video phía ngoài): tấm MG trượt từ phải vào đè kín
    khung cũ, rời đi thì trượt sang trái. Trả về độ lệch x (px); 0 = phủ kín. Hai đoạn MG nối liền → không mở/đóng."""
    if not segment.get("chain_in") and f < segment["start"] + SLIDE_IN:
        return W * (1 - ease_out_cubic(clamp01((f - segment["start"] + 1) / SLIDE_IN)))
    if not segment.get("chain_out") and f >= segment["end"] - SLIDE_OUT:
        return -W * ease_in_cubic(clamp01((f - (segment["end"] - SLIDE_OUT) + 1) / SLIDE_OUT))
    return 0.0


def covered_range(segment: dict) -> tuple[int, int]:
    """các frame MG phủ KÍN (không tính lúc đang trượt) — preflight dùng để xét lộ cảnh."""
    a = segment["start"] + (0 if segment.get("chain_in") else SLIDE_IN)
    b = segment["end"] - (0 if segment.get("chain_out") else SLIDE_OUT)
    return a, b


def chain(segments: list[dict]):
    for s in segments:
        # MG mở đầu video (frame 0) phủ kín ngay, không trượt vào — trước nó không có gì để lộ
        s["chain_in"] = s["start"] <= 0 or any(o is not s and abs(o["end"] - s["start"]) <= 1 for o in segments)
        s["chain_out"] = any(o is not s and abs(o["start"] - s["end"]) <= 1 for o in segments)
