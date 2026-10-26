"""Callout + chữ nổi bật kèm icon / ảnh cho Talking Head (cùng style neon 3 màu, Montserrat).

plan.callouts = [{"id", "kind", "start", "end" (frame timeline), "tone": "gold"|"red"|"blue", "layer": "front"|"behind",
                  "place": "auto"|"chest"|"low"|"above_head"|"left"|"right",
                  "zoom": "punch"|"out" (nhấn nhá ý chính, ~mỗi 10–12s, xen kẽ), "at": [frame…] (mốc hiện từng mục), …tham số theo kind}]
Vào: từng phần bật lần lượt (pop vượt cỡ + loé sáng), mục trong trio/checklist/stat_pair/photo_strip hiện theo `at` (đặt đúng lúc nói).
App TỰ ĐẶT vị trí: thử lần lượt các chỗ, chọn chỗ NẰM TRONG KHUNG AN TOÀN và KHÔNG CHẠM MẶT trong suốt lúc hiện
(mặt lấy từ work/anchors.json, nới thêm lề); không chỗ nào vừa → tự thu nhỏ. Không bao giờ đặt trước mặt nhân vật.

Kind (tham số):
  chữ + icon   icon_keyword(icon, text, sub) · two_tier(lead, text, icon) · step(step "1/3", text, icon) · quote(lead, text)
               warning(text, sub) · trio(items[{text, icon, tone}], at[frame…]) · checklist(items[{text, icon}], at[frame…])
               before_after(a, b, a_sub, b_sub) · stat_pair(items[{icon, value, label, tone}]) · big_number(text, sub)
               card(icon, text, sub) · dos_donts(bad, good) · circle_word(lead, text, mark "circle"|"underline")
               icon_badge(icon, label)
  chỉ vật      pointer(target [x, y] 0..1 khung dọc, label) · arrow_label(target [x, y], label)
  kẹp ảnh      photo_card(image, text) · photo_circle(image, label) · polaroid(image, script, text) · photo_split(image, lead, text, icon)
               photo_strip(images[3], title, at[frame…]) · photo_compare(a_image, b_image, a_label, b_label)
               photo_behind(image, label — layer behind, trên đầu) · thought(image, text) · phone(image, label)
  Ảnh: assets_web/i_* (minh hoạ — app ghi nhãn “Hình ảnh minh họa”), w_* (ảnh thật của chủ thể), c_* (khung cắt từ clip).
  Icon: tên Uicons như các phần khác (tra bằng neon.icon_exists).
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from . import neon as N

SAFE = {"top": 150, "bottom": 330, "side": 70}
FACE_PAD = 0.05            # nới khung mặt mỗi phía (tỉ lệ khung) — chữ/ảnh không được chạm vùng này
ENTER, EXIT = 8, 6

TEXT_KINDS = {"icon_keyword", "two_tier", "step", "quote", "warning", "trio", "checklist", "before_after", "stat_pair",
              "big_number", "card", "dos_donts", "circle_word", "icon_badge", "pointer", "arrow_label"}
PHOTO_KINDS = {"photo_card", "photo_circle", "polaroid", "photo_split", "photo_strip", "photo_compare", "photo_behind",
               "thought", "phone"}
KINDS = TEXT_KINDS | PHOTO_KINDS


# ---------------- lớp RGBA (premultiplied) ----------------
def _hex(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


def _tone(t: str) -> str:
    return t if t in N.PALETTES else "gold"


def _col(t: str) -> np.ndarray:
    return _hex(N.PALETTES[_tone(t)][2])


def blank(h: int, w: int) -> np.ndarray:
    return np.zeros((max(h, 1), max(w, 1), 4), np.float32)


def over(dst: np.ndarray, src: np.ndarray, x: int, y: int):
    H, W = dst.shape[:2]
    h, w = src.shape[:2]
    x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return
    s = src[y0 - y:y1 - y, x0 - x:x1 - x]
    d = dst[y0:y1, x0:x1]
    d *= (1 - s[..., 3:4])
    d += s


class Lay(np.ndarray):
    """sprite RGBA + danh sách thành phần lá [(x, y, sprite, t0)] để diễn hoạt từng phần (vào lần lượt, pop)."""
    def __array_finalize__(self, obj):
        self.parts = None


def leaves(a: np.ndarray) -> list:
    return getattr(a, "parts", None) or [(0, 0, a, getattr(a, "t0", None))]


def at(a: np.ndarray | None, t0: int | None):
    """gắn mốc hiện (frame tính từ đầu callout) cho mọi phần trong a."""
    if a is None:
        return a
    a = a.view(Lay)
    a.parts = [(x, y, p, t0) for x, y, p, _ in leaves(a)]
    return a


def _ink(p: np.ndarray, thr: float = 0.45) -> tuple[int, int, int, int]:
    """khung NÉT thật (bỏ quầng sáng): y0, y1, x0, x1."""
    al = p[..., 3]
    ys, xs = np.where(al.max(1) > thr)[0], np.where(al.max(0) > thr)[0]
    if not len(ys):
        return 0, p.shape[0], 0, p.shape[1]
    return int(ys[0]), int(ys[-1]) + 1, int(xs[0]), int(xs[-1]) + 1


def stack(parts: list[np.ndarray], axis: str = "v", gap: int = 14, align: str = "center") -> np.ndarray:
    """xếp theo NÉT chữ thật (quầng sáng được chồng lên nhau) — khoảng cách dòng gọn như chữ của Talking Head."""
    parts = [p for p in parts if p is not None and p.size]
    if not parts:
        return blank(1, 1)
    pos, cur = [], 0
    for p in parts:
        y0, y1, x0, x1 = _ink(p)
        if axis == "v":
            x = -x0 if align == "left" else -(x0 + x1) / 2
            pos.append((x, cur - y0)); cur += (y1 - y0) + gap
        else:
            pos.append((cur - x0, -(y0 + y1) / 2)); cur += (x1 - x0) + gap
    mx = min(x for x, _ in pos); my = min(y for _, y in pos)
    pos = [(int(round(x - mx)), int(round(y - my))) for x, y in pos]
    W = max(x + p.shape[1] for (x, _), p in zip(pos, parts))
    H = max(y + p.shape[0] for (_, y), p in zip(pos, parts))
    out = blank(H, W).view(Lay)
    out.parts = []
    for (x, y), p in zip(pos, parts):
        over(out, p, x, y)
        out.parts += [(x + lx, y + ly, lp, t0) for lx, ly, lp, t0 in leaves(p)]
    return out


def pad(s: np.ndarray, k: int) -> np.ndarray:
    return np.pad(s, ((k, k), (k, k), (0, 0)))


def glow_layer(h: int, w: int, draw, color: str, width: int = 6, blur: float = 12) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    draw(m, width)
    m = m.astype(np.float32) / 255.0
    g = np.clip(cv2.GaussianBlur(m, (0, 0), blur) * 0.9, 0, 1)
    a = np.clip(m + g, 0, 1)
    out = blank(h, w)
    out[..., :3] = _hex(color) * a[..., None]
    out[..., 3] = a
    return out


def T(text: str, size: int, tone: str = "white", role: str = "display", glow: float = 0.9) -> np.ndarray:
    return N.text_sprite(str(text), role, int(size), tone, glow_k=glow)


def I(name: str | None, size: int, tone: str) -> np.ndarray | None:
    if not name:
        return None
    try:
        return N.icon_sprite(name, int(size), _tone(tone) if tone != "white" else "white")
    except Exception:
        return None


def P(text: str, size: int, tone: str) -> np.ndarray:
    return N.pill_sprite(str(text), int(size), _tone(tone))


# ---------------- ảnh ----------------
@lru_cache(maxsize=64)
def _img(path: str) -> np.ndarray:
    from . import imgio
    im = imgio.imread(path)
    if im is None:
        raise FileNotFoundError(path)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0


def _cover(p: np.ndarray, w: int, h: int) -> np.ndarray:
    ph, pw = p.shape[:2]
    k = max(w / pw, h / ph)
    r = cv2.resize(p, (int(pw * k) + 1, int(ph * k) + 1), interpolation=cv2.INTER_AREA)
    y0, x0 = (r.shape[0] - h) // 2, (r.shape[1] - w) // 2
    return r[y0:y0 + h, x0:x0 + w]


def photo(path: str, w: int, h: int, color: str, shape: str = "round", rad: int = 26, border: int = 6, angle: float = 0,
          label: bool = True, kb: float = 1.0) -> np.ndarray:
    """ảnh bo góc / tròn, viền neon phát sáng, bóng đổ; kb > 1 = zoom chậm bên trong (Ken Burns)."""
    img = _img(path)
    if kb > 1.0005:
        ih, iw = img.shape[:2]
        cw, ch = int(iw / kb), int(ih / kb)
        img = img[(ih - ch) // 2:(ih - ch) // 2 + ch, (iw - cw) // 2:(iw - cw) // 2 + cw]
    pd = 40
    Wc, Hc = w + 2 * pd, h + 2 * pd
    m = np.zeros((Hc, Wc), np.uint8)
    if shape == "circle":
        cv2.circle(m, (Wc // 2, Hc // 2), w // 2, 255, -1, cv2.LINE_AA)
    else:
        cv2.rectangle(m, (pd + rad, pd), (pd + w - rad, pd + h), 255, -1)
        cv2.rectangle(m, (pd, pd + rad), (pd + w, pd + h - rad), 255, -1)
        for x, y in [(pd + rad, pd + rad), (pd + w - rad, pd + rad), (pd + rad, pd + h - rad), (pd + w - rad, pd + h - rad)]:
            cv2.circle(m, (x, y), rad, 255, -1, cv2.LINE_AA)
    mf = m.astype(np.float32) / 255.0
    ring = np.clip(cv2.dilate(m, np.ones((2 * border + 1,) * 2, np.uint8)).astype(np.float32) / 255.0 - mf, 0, 1)
    gl = np.clip(cv2.GaussianBlur(ring, (0, 0), 12) * 0.8, 0, 1)
    sh = cv2.GaussianBlur(mf, (0, 0), 16) * 0.45
    pic = np.zeros((Hc, Wc, 3), np.float32)
    pic[pd:pd + h, pd:pd + w] = _cover(img, w, h)
    c = _hex(color)
    edge = np.clip(ring + gl, 0, 1) * (1 - mf)
    out = blank(Hc, Wc)
    out[..., :3] = pic * mf[..., None] + c * edge[..., None]
    out[..., 3] = np.clip(np.maximum.reduce([mf, edge, sh]), 0, 1)
    if angle:
        M = cv2.getRotationMatrix2D((Wc / 2, Hc / 2), angle, 1)
        out = cv2.warpAffine(out, M, (Wc, Hc), flags=cv2.INTER_LINEAR)
    out = N._trim(out)
    name = Path(path).name
    if label and not name.startswith(("w_", "c_")):
        from . import fonts as FT
        out = stack([out, T(FT.label(), 22, "white", "semi", 0.2)], gap=2)
    elif label and name.startswith("w_"):
        from . import fonts as FT
        out = stack([out, T(FT.label(True), 22, "white", "semi", 0.2)], gap=2)
    return out


# ---------------- dựng sprite theo kind (trạng thái đầy đủ; n = số mục đã hiện với mẫu hiện dần) ----------------
def _t_items(co: dict, n: int) -> list:
    """mốc hiện từng mục (frame tính từ đầu callout) — `at` (frame timeline) hoặc lần lượt cách 8 frame."""
    a0, at_ = int(co["start"]), co.get("at") or []
    return [max(0, int(at_[i]) - a0) if i < len(at_) else 8 * i for i in range(n)]


def sprite(co: dict, kb: float = 1.0) -> np.ndarray:
    """cỡ chữ phụ ≈ 1/2 chữ nhấn; khoảng cách tính theo nét thật (stack)."""
    k, tone = co["kind"], _tone(co.get("tone", "gold"))
    col = N.PALETTES[tone][2]
    g = lambda key, d="": co.get(key, d) or d
    sub = lambda key, size: T(g(key), size, "white", "semi", 0.3) if g(key) else None
    if k == "icon_keyword":
        return stack([I(g("icon", "sparkles"), 140, tone), stack([T(g("text"), 108, tone), sub("sub", 54)], gap=12, align="left")], "h", 26)
    if k == "two_tier":
        return stack([sub("lead", 60), stack([T(g("text"), 118, tone), I(g("icon"), 92, tone)], "h", 20)], gap=12)
    if k == "step":
        return stack([P(f"BƯỚC {g('step', '1')}".replace("/", " / "), 50, "blue" if tone != "blue" else "gold"), T(g("text"), 108, tone),
                      I(g("icon"), 86, tone)], gap=16)
    if k == "quote":
        body = stack([T(g("lead"), 66, "white", "display_bold", 0.3), T(g("text"), 108, tone)], gap=12)
        u = glow_layer(24, int(body.shape[1] * 0.7), lambda m, w: cv2.line(m, (6, 12), (m.shape[1] - 6, 12), 255, w, cv2.LINE_AA), col, 6, 8)
        return stack([I("quote-right", 90, tone), body, u], gap=14)
    if k == "warning":
        return stack([I("triangle-warning", 130, "red"), T(g("text"), 108, "red"), sub("sub", 54)], gap=14)
    if k == "trio":
        its = (co.get("items") or [])[:3]
        ts = _t_items(co, len(its))
        return stack([at(stack([I(it.get("icon"), 88, it.get("tone", tone)), T(it.get("text", ""), 80, it.get("tone", tone))], gap=12), t)
                      for it, t in zip(its, ts)], "h", 70)
    if k == "checklist":
        its = (co.get("items") or [])[:5]
        ts = _t_items(co, len(its))
        return stack([at(stack([I(it.get("icon") or "check", 74, "blue"), T(it.get("text", ""), 64, "white", "display_bold", 0.3)], "h", 22), t)
                      for it, t in zip(its, ts)], gap=26, align="left")
    if k == "before_after":
        a = stack([T(g("a"), 104, "red"), sub("a_sub", 50)], gap=10)
        b = stack([T(g("b"), 104, "blue"), sub("b_sub", 50)], gap=10)
        return stack([a, at(I("arrow-right", 90, "white"), 6), at(b, 12)], "h", 30)
    if k == "stat_pair":
        its = (co.get("items") or [])[:3]
        cells = [at(stack([I(it.get("icon"), 92, it.get("tone", tone)), T(it.get("value", ""), 104, it.get("tone", tone)),
                           T(it.get("label", ""), 50, "white", "semi", 0.2)], gap=10), t) for it, t in zip(its, _t_items(co, len(its)))]
        return stack(cells, "h", 110)
    if k == "big_number":
        return stack([T(g("text"), 240, tone), P(g("sub"), 52, "blue" if tone != "blue" else "gold") if g("sub") else None], gap=10)
    if k == "card":
        inner = stack([I(g("icon"), 92, tone), stack([T(g("text"), 62, "white", "display", 0.4), T(g("sub"), 40, tone, "semi", 0.3) if g("sub") else None],
                                                      gap=10, align="left")], "h", 26)
        h, w = inner.shape[0] + 40, inner.shape[1] + 60
        bgc = blank(h, w)
        m = np.zeros((h, w), np.uint8)
        cv2.rectangle(m, (4, 4), (w - 5, h - 5), 255, -1)
        mf = cv2.GaussianBlur(m, (0, 0), 1.5).astype(np.float32) / 255
        bgc[..., :3] = np.array([0.04, 0.05, 0.09]) * 0.72 * mf[..., None]
        bgc[..., 3] = 0.72 * mf
        over(bgc, glow_layer(h, w, lambda mm, wd: cv2.rectangle(mm, (4, 4), (w - 5, h - 5), 255, wd), col, 3, 8), 0, 0)
        out = bgc.view(Lay)
        out.parts = [(0, 0, bgc.copy(), None)] + [(30 + x, 20 + y, p_, 5 if t is None else t) for x, y, p_, t in leaves(inner)]
        over(out, inner, 30, 20)
        return out
    if k == "dos_donts":
        return stack([stack([I("cross-circle", 84, "red"), P(g("bad"), 56, "red")], "h", 14),
                      at(stack([I("check", 84, "blue"), P(g("good"), 56, "blue")], "h", 14), 10)], gap=24, align="left")
    if k == "circle_word":
        main = T(g("text"), 124, tone)
        body = stack([T(g("lead"), 66, "white", "display", 0.3) if g("lead") else None, main], gap=12)
        out = pad(body, 40)
        mark = co.get("mark", "circle")
        H2, W2 = out.shape[:2]
        y0, y1, x0, x1 = _ink(main)
        cy = H2 - 40 - main.shape[0] + (y0 + y1) // 2
        if mark == "underline":
            d = lambda m, wd: cv2.line(m, (60, cy + (y1 - y0) // 2 + 24), (W2 - 60, cy + (y1 - y0) // 2 + 14), 255, wd, cv2.LINE_AA)
        else:
            d = lambda m, wd: cv2.ellipse(m, (W2 // 2, cy), ((x1 - x0) // 2 + 40, (y1 - y0) // 2 + 30), -3, 12, 348, 255, wd, cv2.LINE_AA)
        ring = glow_layer(H2, W2, d, N.PALETTES["red" if tone != "red" else "gold"][2], 7, 10)
        res = out.view(Lay)
        res.parts = [(40 + x, 40 + y, p_, t) for x, y, p_, t in leaves(body)] + [(0, 0, ring, 8)]
        over(res, ring, 0, 0)
        return res
    if k == "icon_badge":
        r = 110
        ring = glow_layer(2 * r + 60, 2 * r + 60, lambda m, w: cv2.circle(m, (r + 30, r + 30), r, 255, w, cv2.LINE_AA), col, 6, 14)
        over(ring, I(g("icon"), 120, tone), r + 30 - 70, r + 30 - 70)
        return stack([N._trim(ring), at(P(g("label"), 52, tone), 6)], gap=-18)
    if k in ("pointer", "arrow_label"):
        return P(g("label"), 52, tone)
    if k == "photo_card":
        return stack([photo(g("image"), 640, 380, col, kb=kb), at(T(g("text"), 92, tone), 6)], gap=14)
    if k == "photo_circle":
        return stack([photo(g("image"), 280, 280, col, shape="circle", label=False, kb=kb), at(P(g("label"), 48, tone), 6)], gap=-10)
    if k == "polaroid":
        return stack([photo(g("image"), 520, 400, "#FFFFFF", rad=10, border=14, angle=-5, kb=kb),
                      at(stack([T(g("script"), 66, "white", "script", 0.2) if g("script") else None, T(g("text"), 90, tone)], "h", 16), 6)], gap=10)
    if k == "photo_split":
        return stack([photo(g("image"), 380, 460, col, kb=kb), at(stack([T(g("lead"), 60, "white", "display_bold", 0.3) if g("lead") else None,
                                                                         T(g("text"), 96, tone), I(g("icon"), 80, tone)], gap=14, align="left"), 6)], "h", 30)
    if k == "photo_strip":
        ims = (co.get("images") or [])[:3]
        cells = [at(stack([P(str(i + 1), 40, "blue"), photo(p, 270, 200, N.PALETTES["blue"][2], rad=18, label=False, kb=kb)], gap=-8), t)
                 for i, (p, t) in enumerate(zip(ims, _t_items(co, len(ims))))]
        return stack([T(g("title"), 92, tone) if g("title") else None, stack(cells, "h", 26)], gap=18)
    if k == "photo_compare":
        a = stack([photo(g("a_image"), 380, 300, N.PALETTES["red"][2], rad=18, label=False, kb=kb), P(g("a_label", "TRƯỚC"), 46, "red")], gap=8)
        b = stack([photo(g("b_image"), 380, 300, N.PALETTES["blue"][2], rad=18, label=False, kb=kb), P(g("b_label", "SAU"), 46, "blue")], gap=8)
        return stack([a, at(I("arrow-right", 80, "white"), 6), at(b, 12)], "h", 20)
    if k == "photo_behind":
        return stack([photo(g("image"), 820, 460, col, label=False, kb=kb), at(P(g("label"), 52, tone), 6) if g("label") else None], gap=-10)
    if k == "thought":
        return stack([photo(g("image"), 300, 300, "#FFFFFF", shape="circle", border=8, label=False, kb=kb),
                      at(T(g("text"), 60, "white", "script", 0.3), 6) if g("text") else None], gap=8)
    if k == "phone":
        return stack([photo(g("image"), 300, 540, "#202020", rad=34, border=14, label=False, kb=kb), at(P(g("label"), 48, tone), 6) if g("label") else None],
                     gap=14)
    raise ValueError(f"không có mẫu callout “{k}” (có: {', '.join(sorted(KINDS))})")


# ---------------- đặt vị trí: trong khung an toàn, không chạm mặt ----------------
def face_box(anchors_tl: list[dict], a: int, b: int, W: int, H: int) -> tuple[float, float, float, float]:
    """khung đầu + mặt (px) gộp suốt [a, b) + lề; (x0, y0, x1, y1). anchors: head_top, face_cx, face_h, face_bottom (0..1)."""
    fr = [x for x in anchors_tl[max(a, 0):min(b, len(anchors_tl))] if x.get("face_h")] or [x for x in anchors_tl if x.get("face_h")][:1]
    if not fr:
        return (W * 0.25, H * 0.12, W * 0.75, H * 0.5)
    pw, ph = FACE_PAD * W, FACE_PAD * H
    hw = max(x["face_h"] for x in fr) * H * 0.42                     # nửa bề ngang mặt ≈ 0.42 × cao mặt (mặt ~0.8 rộng/cao)
    x0 = min(x["face_cx"] for x in fr) * W - hw - pw
    x1 = max(x["face_cx"] for x in fr) * W + hw + pw
    y0 = min(x.get("head_top", x["face_cy"] - x["face_h"]) for x in fr) * H - ph
    y1 = max(x["face_bottom"] for x in fr) * H + ph * 0.6
    return (max(0, x0), max(0, y0), min(W, x1), min(H, y1))


ZOOM = {"punch": 1.12, "out": 1.12}


def zoom_events(plan) -> list:
    """callout có "zoom": "punch" (đẩy vào nhanh lúc callout vào, giữ, nhả khi ra) | "out" (bắt đầu gần rồi lùi dần về) — nhấn nhá
    theo ý chính. Tâm zoom = mặt nhân vật (cx, cy) để mặt không trôi ra khỏi khung."""
    from types import SimpleNamespace as NS
    out = []
    for co in getattr(plan, "callouts", None) or []:
        z = co.get("zoom")
        if not z or not co.get("enabled", True):
            continue
        out.append(NS(type="zoom", enabled=True, start=int(co["start"]), end=int(co["end"]),
                      params={"scale": float(co.get("zoom_scale", ZOOM.get(z, 1.12))), "mode": "out" if z == "out" else "punch",
                              "cx": co.get("zoom_cx", 0.5), "cy": co.get("zoom_cy", 0.32)}))
    return out


def attach_objects(anchors: list[dict], gaze_file, fps: int = 30) -> list[dict]:
    """gắn vùng VẬT đang cầm/trình diễn (gaze.json: obj, mẫu mỗi STEP giây) vào anchors theo frame nguồn → callout tránh che vật."""
    gf = Path(gaze_file)
    if not gf.exists():
        return anchors
    from .clips import load_gaze
    gz = [g for g in load_gaze(gf) if g.get("obj") and g.get("demo")]
    if not gz:
        return anchors
    ts = np.array([g["t"] for g in gz])
    for a in anchors:
        t = a.get("f", 0) / fps
        k = int(np.abs(ts - t).argmin())
        if abs(ts[k] - t) <= 0.6:
            a["obj"] = gz[k]["obj"]
    return anchors


def obj_box(anchors_tl: list[dict], a: int, b: int, W: int, H: int):
    """khung vật (px) điển hình suốt [a, b) — trung vị các cạnh (tay đưa qua lại không phình cả khung); None nếu không có."""
    bs = np.array([x["obj"] for x in anchors_tl[max(a, 0):min(b, len(anchors_tl))] if x.get("obj")])
    if len(bs) < max(3, (b - a) // 4):                    # vật chỉ thoáng qua → không tính
        return None
    x0, y0 = np.median(bs[:, 0]), np.median(bs[:, 1])
    x1, y1 = np.median(bs[:, 0] + bs[:, 2]), np.median(bs[:, 1] + bs[:, 3])
    return (x0 * W, y0 * H, x1 * W, y1 * H)


def _inside(r, W, H) -> bool:
    x0, y0, x1, y1 = r
    return x0 >= SAFE["side"] and x1 <= W - SAFE["side"] and y0 >= SAFE["top"] and y1 <= H - SAFE["bottom"]


def _hit(r, f) -> bool:
    return not (r[2] <= f[0] or r[0] >= f[2] or r[3] <= f[1] or r[1] >= f[3])


ORDER = {"auto": ["chest", "low", "above_head", "right", "left"], "chest": ["chest", "low", "right", "left", "above_head"],
         "low": ["low", "chest", "right", "left", "above_head"], "above_head": ["above_head", "right", "left", "chest", "low"], "left": ["left", "right", "chest"],
         "right": ["right", "left", "chest"]}


def _spots(place: str, w: float, h: float, face, W: int, H: int):
    fx = (face[0] + face[2]) / 2
    for p in ORDER.get(place, ORDER["auto"]):
        if p == "chest":
            yield p, W / 2 - w / 2, face[3] + 24
        elif p == "low":
            yield p, W / 2 - w / 2, H - SAFE["bottom"] - h
        elif p == "above_head":
            yield p, min(max(fx - w / 2, SAFE["side"]), W - SAFE["side"] - w), face[1] - 24 - h
        elif p == "left":
            yield p, SAFE["side"], max(SAFE["top"], (face[1] + face[3]) / 2 - h / 2)
        elif p == "right":
            yield p, W - SAFE["side"] - w, max(SAFE["top"], (face[1] + face[3]) / 2 - h / 2)


def layout(co: dict, anchors_tl: list[dict], W: int, H: int) -> dict:
    """{"x", "y", "scale", "w", "h", "spot", "face", "ok", "why"} — vị trí góc trên trái của sprite đầy đủ."""
    face = face_box(anchors_tl, int(co["start"]), int(co["end"]), W, H)
    if co.get("zoom"):                                     # zoom phóng mặt ra quanh tâm zoom → khung mặt lúc phóng to nhất
        z = float(co.get("zoom_scale", ZOOM.get(co["zoom"], 1.12)))
        zx, zy = co.get("zoom_cx", 0.5) * W, co.get("zoom_cy", 0.32) * H
        face = (zx + (face[0] - zx) * z, zy + (face[1] - zy) * z, zx + (face[2] - zx) * z, zy + (face[3] - zy) * z)
    ob = obj_box(anchors_tl, int(co["start"]), int(co["end"]), W, H)
    try:
        spr = sprite(co)
    except Exception as e:
        return {"ok": False, "why": f"không dựng được: {e}", "face": face}
    h0, w0 = spr.shape[:2]
    place = co.get("place") or ("above_head" if co["kind"] in ("photo_behind", "thought", "big_number") else
                                "right" if co["kind"] in ("icon_badge", "photo_circle") else "auto")
    if co["kind"] in ("pointer", "arrow_label"):
        L = _layout_pointer(co, spr, face, W, H)
        if L["ok"] and ob and _hit((L["x"], L["y"], L["x"] + L["w"], L["y"] + L["h"]), ob) and not co.get("target"):
            L.update(ok=False, why="nhãn che vật đang cầm")
        return L
    for avoid_obj, k in [(True, k) for k in (1.0, 0.9, 0.8, 0.7, 0.62)] + [(False, k) for k in (1.0, 0.9, 0.8, 0.7, 0.62)]:
        if not avoid_obj and not ob:                      # lượt 2 (cho đè một phần vật, KHÔNG BAO GIỜ đè mặt) chỉ khi có vật
            break
        w, h = w0 * k, h0 * k
        if w > W - 2 * SAFE["side"]:
            continue
        for spot, x, y in _spots(place, w, h, face, W, H):
            r = (x, y, x + w, y + h)
            if _inside(r, W, H) and (co.get("layer") == "behind" and spot == "above_head" or not _hit(r, face)) \
                    and not (avoid_obj and ob and _hit(r, ob)):
                layer = co.get("layer", "front") if spot == "above_head" else "front"   # lớp sau đầu chỉ khi ở trên đầu
                return {"ok": True, "x": int(x), "y": int(y), "scale": k, "w": int(w), "h": int(h), "spot": spot, "face": face,
                        "layer": layer}
    return {"ok": False, "why": "không còn chỗ trong khung an toàn mà không chạm mặt" + (" / vật đang cầm" if ob else "") +
            " — rút ngắn chữ / bớt mục / đổi mẫu nhỏ hơn (chỉ vật thì dùng pointer / arrow_label)", "face": face}


def _layout_pointer(co, spr, face, W, H) -> dict:
    tx, ty = co.get("target") or [0.3, 0.65]
    tx, ty = tx * W, ty * H
    h, w = spr.shape[:2]
    side = 1 if tx < W / 2 else -1                                  # nhãn ra phía rộng hơn của khung
    best = None
    for side, dy in [(side, d) for d in (170, -170, 260, -260, 360)] + [(-side, d) for d in (170, 260, 360)]:   # dưới/trên, rồi phía kia
        x = tx + side * 140 if side > 0 else tx - 140 - w
        y = ty + dy - h / 2
        x = min(max(x, SAFE["side"]), W - SAFE["side"] - w)
        y = min(max(y, SAFE["top"]), H - SAFE["bottom"] - h)
        r = (x, y, x + w, y + h)
        pts = [(tx, ty), (tx + side * 110, y + h / 2), (x if side > 0 else x + w, y + h / 2)]
        rl = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
        ok = _inside(r, W, H) and not _hit(r, face) and not _hit(rl, face) and SAFE["top"] <= ty <= H - SAFE["bottom"]
        best = {"ok": ok, "x": int(x), "y": int(y), "scale": 1.0, "w": int(w), "h": int(h), "spot": "pointer", "face": face, "pts": pts}
        if ok:
            break
    best["why"] = "" if best["ok"] else "điểm chỉ / nhãn chạm mặt hoặc ra ngoài khung an toàn — chọn vật khác hoặc đổi mẫu"
    return best


def layout_all(plan, anchors_tl: list[dict], W: int, H: int) -> dict:
    return {co["id"]: layout(co, anchors_tl, W, H) for co in (getattr(plan, "callouts", None) or []) if co.get("enabled", True)}


# ---------------- vẽ từng frame ----------------
_SPR: dict = {}


def _ease(x: float) -> float:
    return 1 - (1 - min(max(x, 0), 1)) ** 4


def _back(x: float) -> float:
    """ease-out-back: vượt ~8% rồi về — kiểu pop của chữ Talking Head."""
    x = min(max(x, 0), 1)
    c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _leaves_scaled(co: dict, lay: dict, kb: float) -> list:
    key = (co["id"], kb, lay["scale"])
    L = _SPR.get(key)
    if L is None:
        spr = sprite(co, kb)
        k = lay["scale"]
        L = []
        for i, (x, y, p, t0) in enumerate(leaves(spr)):
            if k != 1.0:
                p = cv2.resize(p, (max(1, int(p.shape[1] * k)), max(1, int(p.shape[0] * k))), interpolation=cv2.INTER_AREA)
            L.append((x * k, y * k, p, t0 if t0 is not None else min(3 * i, 12)))
        if len(_SPR) > 300:
            _SPR.clear()
        _SPR[key] = L
    return L


POP = 9            # frame mỗi phần bật vào


def draw(buf: np.ndarray, co: dict, lay: dict, f: int):
    """vào: từng phần lần lượt (lá trước → lá sau, mục theo `at`) phóng 0.55 → vượt → 1, mờ → rõ, loé sáng nhẹ; ra: thu nhỏ + mờ + trôi lên."""
    a, b = int(co["start"]), int(co["end"])
    if not (a <= f < b) or not lay.get("ok"):
        return
    kb = round(1.0 + 0.05 * (f - a) / max(b - a, 1), 2) if co["kind"] in PHOTO_KINDS else 1.0
    x_out = min(max((f - (b - EXIT) + 1) / EXIT, 0), 1)
    if co["kind"] in ("pointer", "arrow_label"):
        _draw_lines(buf, co, lay, _ease((f - a + 1) / ENTER) * (1 - x_out))
    ox, oy = lay["x"], lay["y"]
    gs = 1 - 0.12 * x_out                                    # thu cả cụm khi ra
    gcx, gcy = ox + lay["w"] / 2, oy + lay["h"] / 2
    for x, y, p, t0 in _leaves_scaled(co, lay, kb):
        loc = f - a - t0
        if loc < 0:
            continue
        u = (loc + 1) / POP
        s = (0.55 + 0.45 * _back(u)) * gs
        o = min(1.0, (loc + 1) / 4) * (1 - x_out)
        if o <= 0.01:
            continue
        sp = p if abs(s - 1) < 0.004 else cv2.resize(p, (max(1, int(p.shape[1] * s)), max(1, int(p.shape[0] * s))), interpolation=cv2.INTER_LINEAR)
        fl = max(0.0, 1 - loc / 8) * 0.45                    # loé sáng lúc vào
        if fl > 0.01:
            sp = sp.copy()
            sp[..., :3] = np.minimum(sp[..., :3] * (1 + fl), sp[..., 3:4])
        sp = sp * o
        cx = gcx + (ox + x + p.shape[1] / 2 - gcx) * gs
        cy = gcy + (oy + y + p.shape[0] / 2 - gcy) * gs - 26 * x_out
        over(buf, sp, int(cx - sp.shape[1] / 2), int(cy - sp.shape[0] / 2))


def _draw_lines(buf, co, lay, k):
    if k <= 0.01:
        return
    H, W = buf.shape[:2]
    col = N.PALETTES[_tone(co.get("tone", "gold"))][2]
    pts = lay["pts"]
    if co["kind"] == "arrow_label":                                   # mũi tên cong: từ nhãn tới đích
        p0, p2 = np.array(pts[2]), np.array(pts[0])
        p1 = np.array([pts[1][0], (p0[1] + p2[1]) / 2])
        curve = [tuple((1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t ** 2 * p2) for t in np.linspace(0, k, 24)]
        seq = curve
    else:                                                             # chấm + đường gấp vẽ dần
        seq = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seq += [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for t in np.linspace(0, 1, 12)]
        seq = seq[:max(2, int(len(seq) * k))]

    def d(m, w):
        cv2.polylines(m, [np.array(seq, np.int32)], False, 255, w, cv2.LINE_AA)
        if co["kind"] == "pointer":
            cv2.circle(m, (int(pts[0][0]), int(pts[0][1])), 13, 255, -1, cv2.LINE_AA)
        elif k > 0.95:
            tip, prev = np.array(seq[-1]), np.array(seq[-3])
            ang = math.atan2(*(tip - prev)[::-1])
            for da in (2.6, -2.6):
                q = tip + 42 * np.array([math.cos(ang + da), math.sin(ang + da)])
                cv2.line(m, tuple(tip.astype(int)), tuple(q.astype(int)), 255, w, cv2.LINE_AA)
    over(buf, glow_layer(H, W, d, col, 5, 12) * min(1.0, k * 1.5), 0, 0)


# ---------------- kiểm tra (preflight) ----------------
def check(plan, anchors_tl: list[dict], W: int, H: int, fps: int, open_close: tuple[int, int] | None = None) -> list[tuple[str, str]]:
    """lỗi: chạm mặt, ra ngoài khung an toàn, mẫu sai tham số, ảnh trong đoạn mở đầu/kết; nhịp chữ nổi bật ≤ 5s; không lặp mẫu > 2 lần liền."""
    from . import timeline as Tm
    out = []
    cos = [c for c in (getattr(plan, "callouts", None) or []) if c.get("enabled", True)]
    lays = layout_all(plan, anchors_tl, W, H)
    for c in cos:
        tag = f"callout {c.get('id')} ({c.get('kind')}) {Tm.tc(int(c['start']))}"
        if c.get("kind") not in KINDS:
            out.append(("error", f"{tag}: không có mẫu này (có: {', '.join(sorted(KINDS))})")); continue
        if int(c["end"]) - int(c["start"]) < int(1.5 * fps):
            out.append(("error", f"{tag}: hiện < 1.5s — chưa kịp đọc"))
        L = lays.get(c["id"], {})
        if not L.get("ok"):
            out.append(("error", f"{tag}: {L.get('why', 'không đặt được')}"))
        if c["kind"] in PHOTO_KINDS:
            imgs = [c.get(k) for k in ("image", "a_image", "b_image") if c.get(k)] + list(c.get("images") or [])
            for p in imgs:
                if not Path(p).is_file():
                    out.append(("error", f"{tag}: không có ảnh {p}"))
            if open_close and (int(c["start"]) < open_close[0] or int(c["end"]) > open_close[1]):
                out.append(("error", f"{tag}: ảnh trong đoạn mở đầu / kết — hai đoạn này chỉ hình người + chữ"))
    for a, b in zip(cos, cos[1:]):
        if a["start"] < b["start"] < a["end"] and a.get("layer", "front") == b.get("layer", "front"):
            out.append(("error", f"callout {a['id']} và {b['id']} chồng nhau cùng lớp — cái trước rời trước khi cái sau vào"))
    seq = [c["kind"] for c in sorted(cos, key=lambda c: c["start"])]
    for i in range(2, len(seq)):
        if seq[i] == seq[i - 1] == seq[i - 2]:
            out.append(("warn", f"mẫu “{seq[i]}” dùng 3 lần liền — đổi mẫu cho đỡ nhàm")); break
    return out


def density(plan, fps: int, gap_s: float = 5.0) -> list[tuple[str, str]]:
    """mốc chữ nổi bật (nhóm chữ, callout, cảnh MG, lớp HyperFrames) cách nhau ≤ gap_s giây."""
    from . import timeline as Tm
    hits = [g.hit for g in plan.text_groups if g.enabled]
    hits += [int(c["start"]) + ENTER for c in (getattr(plan, "callouts", None) or []) if c.get("enabled", True)]
    for seg in plan.mg or []:
        hits += [int(s["start"]) for s in seg.get("scenes", [])]
    hits += [int(h["start"]) for h in getattr(plan, "hf", None) or [] if h.get("enabled", True)]   # lớp chữ HyperFrames
    hits = sorted(set(hits))
    end = plan.duration_frames
    out, prev = [], 0
    for h in hits + [end]:
        if h - prev > gap_s * fps:
            out.append(("error", f"{Tm.tc(prev)}→{Tm.tc(h)}: {(h - prev) / fps:.1f}s không có chữ nổi bật — thêm chữ nổi bật / callout "
                                 f"(khoảng mỗi 4s một lần)"))
        prev = h
    nz = len(zoom_events(plan)) + sum(1 for e in plan.fx if e.type == "zoom" and e.enabled and e.params.get("mode") != "cut")
    want = int(end / fps / 12)
    if want >= 2 and nz < want:
        out.append(("warn", f"chỉ {nz} lần zoom nhấn nhá cho {end / fps:.0f}s — thêm \"zoom\": \"punch\" / \"out\" vào callout ý chính "
                            f"(khoảng mỗi 10–12s một lần, xen kẽ vào/ra)"))
    return out
