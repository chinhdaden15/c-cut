"""Dựng video từ timeline.json (skill voice-to-motion).

Mỗi frame là hàm thuần của (timeline, t):  nền → lớp trang trí (parallax) → đối tượng (theo layer) → chuyển cảnh.
Toạ độ đối tượng ở "không gian thế giới"; camera (x, y, zoom, rot) quyết định phần nào lên khung.
"""
from __future__ import annotations

import json
import math
import subprocess
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np

from . import draw as D, vtext as VT

DEFAULT_THEME = {"bg": "#15171C", "bg2": "#1D2027", "glow": "#2A2F3B", "accent": "#FFB020", "alt": "#E8402F",
                 "text": "#FFFFFF", "muted": "#9AA0AA", "deco": ["dots", "dashes"]}
EASE = {
    "linear": lambda x: x,
    "in": lambda x: x ** 3,
    "out": lambda x: 1 - (1 - x) ** 3,
    "inout": lambda x: 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2,
    "quart": lambda x: 1 - (1 - x) ** 4,
    "back": lambda x: 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2,
    "expo": lambda x: 1 if x >= 1 else 1 - 2 ** (-10 * x),
}
NUM_PROPS = {"x", "y", "scale", "rot", "opacity", "w", "h", "r", "size", "progress", "value", "bend", "width",
             "max_w", "bg_r", "tilt", "spacing", "blur", "dim"}


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease(name, x):
    return EASE.get(name or "inout", EASE["inout"])(clamp01(x))


# ---------------- nạp + chuẩn hoá timeline ----------------
class Timeline:
    def __init__(self, data: dict, base: Path):
        self.d = data
        self.base = base
        cv = data.get("canvas", {})
        self.W, self.H, self.fps = int(cv.get("width", 1080)), int(cv.get("height", 1920)), int(cv.get("fps", 30))
        from .layout import SAFE as _SAFE, fmt_of
        self.fmt = cv.get("format") or fmt_of(self.W, self.H)
        self.safe = tuple(cv.get("safe") or _SAFE[self.fmt])      # (x0, y0, x1, y1) vùng an toàn theo tỷ lệ khung
        self.theme = {**DEFAULT_THEME, **data.get("theme", {})}
        self.duration = float(data.get("audio", {}).get("duration_s") or max(s["end_s"] for s in data["scenes"]))
        self.scenes = sorted(data["scenes"], key=lambda s: s["start_s"])
        self.objs: dict[str, dict] = {}
        self.order: list[str] = []
        self.events: dict[str, list[dict]] = {}
        for si, sc in enumerate(self.scenes):
            for o in sc.get("objects", []):
                o = dict(o)
                o["_scene"] = sc["id"]
                o["_s0"], o["_s1"] = sc["start_s"], sc["end_s"]
                if o["id"] in self.objs:
                    raise ValueError(f"trùng object id {o['id']}")
                self.objs[o["id"]] = o
                self.order.append(o["id"])
            for e in sc.get("events", []):
                self.events.setdefault(e["object_id"], []).append(e)
        for oid, evs in self.events.items():
            if oid not in self.objs:
                raise ValueError(f"event trỏ tới object không có: {oid}")
            evs.sort(key=lambda e: e["start_s"])
        cams = list(data.get("camera", []))
        for sc in self.scenes:
            cams += sc.get("camera", [])
        self.camera = sorted(cams, key=lambda k: k["t"])
        if any(o["type"] in ("map", "geo", "region", "geoline") for o in self.objs.values()) and self.theme.get("map_fixed", True):
            for o in self.objs.values():   # quy tắc: trên bản đồ, chữ/shape/callout không phóng theo zoom — chỉ giữ đúng vị trí
                if o["type"] in ("text", "icon", "circle", "rect", "callout", "counter", "list", "halo") and o.get("space") != "screen":
                    o.setdefault("fixed", True)
        for o in self.objs.values():   # con thừa hưởng không gian + lớp của cha (vẽ ngay trên cha)
            q, n = o, 0
            while q.get("parent") in self.objs and n < 8:
                q = self.objs[q["parent"]]; n += 1
            o["_root"] = q
            o.setdefault("space", q.get("space", "world"))
            o["_layer"] = o.get("layer", q.get("layer", 0) if q is not o else 0) + (0.5 if q is not o and "layer" not in o else 0)
        # sort ổn định: cùng layer giữ thứ tự khai báo; chữ/hình cố định trên màn hình (space=screen) luôn nằm trên không gian
        self.order.sort(key=lambda i: (self.objs[i].get("space") == "screen", self.objs[i]["_layer"]))
        for oid in self.order:
            self._vis_of(self.objs[oid])

    def _vis_of(self, o):
        if "_vis" not in o:
            own = self.events.get(o["id"]) or o.get("until_s") is not None or o.get("persist")
            par = self.objs.get(o.get("parent") or "")
            o["_vis"] = self._vis_of(par) if (par is not None and not own) else self._visibility(o)
        return o["_vis"]

    def path(self, p: str) -> str:
        q = Path(p)
        return str(q if q.is_absolute() else self.base / q)

    def _visibility(self, o: dict) -> tuple[float, float]:
        evs = self.events.get(o["id"], [])
        rev = [e for e in evs if e["action"] == "reveal"]
        hid = [e for e in evs if e["action"] == "hide"]
        t0 = rev[0]["start_s"] if rev else o["_s0"]
        if hid:
            t1 = hid[-1].get("end_s", hid[-1]["start_s"] + 0.4)
        elif o.get("until_s") is not None:
            t1 = float(o["until_s"])
        elif o.get("persist"):
            t1 = self.duration + 1
        else:
            t1 = o["_s1"]
        return t0, t1

    # ---------- thuộc tính tại thời điểm t ----------
    def props(self, oid: str, t: float) -> dict:
        o = self.objs[oid]
        p = {k: v for k, v in o.items() if not k.startswith("_")}
        p.setdefault("scale", 1.0); p.setdefault("rot", 0.0); p.setdefault("opacity", 1.0)
        enter = leave = None
        for e in self.events.get(oid, []):
            a, b = e["start_s"], e.get("end_s", e["start_s"] + 0.4)
            if t < a and e["action"] not in ("reveal",):
                continue
            k = 1.0 if b <= a else (t - a) / (b - a)
            if e["action"] == "reveal":
                enter = (e, clamp01(k))
            elif e["action"] == "hide":
                if t >= a:
                    leave = (e, clamp01(k))
            elif e["action"] in ("animate", "draw", "count"):
                to = dict(e.get("to") or {})
                if e["action"] == "draw" and not to:
                    to = {"progress": 1.0}
                x = ease(e.get("ease", "inout"), k)
                for kk, v in to.items():
                    if kk in NUM_PROPS and isinstance(p.get(kk, 0), (int, float)) and isinstance(v, (int, float)):
                        base = p.get(kk, 0.0 if kk in ("progress",) else v)
                        if e["action"] == "draw" and kk == "progress" and "progress" not in o:
                            base = 0.0
                        p[kk] = base + (v - base) * x
                    elif x >= 1 or k >= 0.5:
                        p[kk] = v
            elif e["action"] == "pulse":
                if a <= t <= b:
                    p["scale"] = p["scale"] * (1 + 0.08 * math.sin(math.pi * clamp01(k)))
        # các object có "draw" mà chưa tới lúc vẽ → progress = 0
        if o["type"] in ("line", "bars", "progress", "path") and "progress" not in o:
            draws = [e for e in self.events.get(oid, []) if e["action"] == "draw"]
            if draws and t < draws[0]["start_s"]:
                p["progress"] = 0.0
            p.setdefault("progress", 1.0)
        idle = o.get("idle", self.theme.get("idle", False))
        if idle and o["type"] in ("icon", "rect", "image", "circle", "quote", "counter") and not o.get("parent") \
                and o.get("space") == "screen" and enter is not None:
            # sống sau khi hiện: trôi dọc ±5px + giãn ±1,5%, lệch pha theo id (không rung, không đồng loạt)
            ph = (sum(map(ord, oid)) % 97) / 97.0 * 2 * math.pi
            k_in = clamp01((t - enter[0].get("end_s", enter[0]["start_s"])) / 0.6)
            amp = float(idle) if not isinstance(idle, bool) else 1.0
            p["y"] = p.get("y", 0) + 5 * amp * k_in * math.sin(2 * math.pi * t / 3.4 + ph)
            p["scale"] = p["scale"] * (1 + 0.015 * amp * k_in * math.sin(2 * math.pi * t / 4.6 + ph * 1.7))
            if o["type"] == "icon":
                p["rot"] = p.get("rot", 0) + 2.0 * amp * k_in * math.sin(2 * math.pi * t / 5.2 + ph)
        p["_enter"], p["_leave"] = enter, leave
        return p


# ---------------- camera ----------------
def camera_at(tl: Timeline, t: float) -> tuple[float, float, float, float]:
    """camera theo key + “thở” rất nhẹ (zoom ±drift, trôi ngang) để không cảnh nào đứng hình hoàn toàn."""
    x, y, z, r = _camera_keys(tl, t)
    d = float(tl.theme.get("drift", 0.0))
    if d:
        z *= 1 + d * math.sin(2 * math.pi * t / 7.0)
        x += d * 600 * math.sin(2 * math.pi * t / 11.0) / max(z, 1e-3)   # trôi theo px màn hình, không theo zoom
    return x, y, z, r


def _cam_segments(tl: Timeline):
    """đoạn camera (t0, t1, từ, tới, ease). Đoạn sau bắt đầu từ vị trí THẬT của camera tại t0 → không nhảy khi các key chồng
    thời gian; zoom nội suy theo log (cảm giác tốc độ đều khi phóng từ 0,4× lên 150×)."""
    if getattr(tl, "_segs", None) is not None:
        return tl._segs
    segs = []
    tgt = {"x": tl.W / 2, "y": tl.H / 2, "zoom": 1.0, "rot": 0.0}
    if tl.camera:   # camera mở đầu ĐÃ ở key đầu tiên (không có frame camera mặc định rồi nhảy)
        tgt = {**tgt, **{a: float(tl.camera[0][a]) for a in ("x", "y", "zoom", "rot") if a in tl.camera[0]}}
    for k in tl.camera:
        dur = max(float(k.get("dur", 0.6)), 0.0)
        t1 = float(k["t"]); t0 = t1 - dur
        start = dict(_cam_eval(segs, t0, tgt))
        new = {**tgt, **{a: float(k[a]) for a in ("x", "y", "zoom", "rot") if a in k}}
        segs.append((t0, t1, start, new, k.get("ease", "inout")))
        tgt = new
    tl._segs = segs
    return segs


def _cam_eval(segs, t, base):
    cur = dict(base) if not segs else None
    val = None
    for t0, t1, a, b, e in segs:
        if t < t0:
            break
        if t >= t1 or t1 <= t0:
            val = b
            continue
        x = ease(e, (t - t0) / (t1 - t0))
        za, zb = max(a["zoom"], 1e-6), max(b["zoom"], 1e-6)
        val = {"x": a["x"] + (b["x"] - a["x"]) * x, "y": a["y"] + (b["y"] - a["y"]) * x,
               "zoom": za * (zb / za) ** x, "rot": a["rot"] + (b["rot"] - a["rot"]) * x}
    if val is None:
        val = segs[0][2] if segs else base
    return val if cur is None else cur


def _camera_keys(tl: Timeline, t: float) -> tuple[float, float, float, float]:
    """mỗi key: camera tới (x, y, zoom, rot) đúng lúc t, di chuyển trong `dur` giây trước đó."""
    segs = _cam_segments(tl)
    if not segs:
        return tl.W / 2, tl.H / 2, 1.0, 0.0
    v = _cam_eval(segs, t, {"x": tl.W / 2, "y": tl.H / 2, "zoom": 1.0, "rot": 0.0})
    return v["x"], v["y"], v["zoom"], v["rot"]


def world_to_screen(tl, cam, x, y):
    cx, cy, z, r = cam
    a = math.radians(-r)
    dx, dy = (x - cx) * z, (y - cy) * z
    return tl.W / 2 + dx * math.cos(a) - dy * math.sin(a), tl.H / 2 + dx * math.sin(a) + dy * math.cos(a)


# ---------------- nền ----------------
@lru_cache(maxsize=16)
def _bg(W, H, c1, c2, glow) -> np.ndarray:
    g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    bg = D.rgb(c1) * (1 - g) + D.rgb(c2) * g
    bg = np.broadcast_to(bg, (H, W, 3)).copy()
    if glow:   # quầng sáng mềm phía trên
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        m = np.exp(-(((xx - W * 0.5) / (W * 0.75)) ** 2 + ((yy - H * 0.3) / (H * 0.38)) ** 2))
        bg = bg * (1 - 0.55 * m[..., None]) + D.rgb(glow) * 0.55 * m[..., None]
    return bg


@lru_cache(maxsize=8)
def _deco(W, H, kinds: tuple, color: str) -> np.ndarray:
    """lớp trang trí mờ, rộng gấp 1.6 khung để lia camera không lộ mép."""
    S = 1.6
    w, h = int(W * S), int(H * S)
    m = np.zeros((h, w), np.uint8)
    rng = np.random.default_rng(7)
    if "dots" in kinds:
        for y in range(0, h, 54):
            for x in range(0, w, 54):
                cv2.circle(m, (x, y), 2, 90, -1, cv2.LINE_AA)
    if "grid" in kinds:
        for y in range(0, h, 108):
            cv2.line(m, (0, y), (w, y), 40, 1, cv2.LINE_AA)
        for x in range(0, w, 108):
            cv2.line(m, (x, 0), (x, h), 40, 1, cv2.LINE_AA)
    if "dashes" in kinds:
        for _ in range(9):
            cx, cy = rng.uniform(0, w), rng.uniform(0, h)
            R = rng.uniform(220, 520)
            a0 = rng.uniform(0, 360)
            for k in range(0, 70, 7):
                cv2.ellipse(m, (int(cx), int(cy)), (int(R), int(R)), 0, a0 + k, a0 + k + 3.5, 150, 2, cv2.LINE_AA)
    a = m.astype(np.float32) / 255 * 0.35
    out = np.zeros((h, w, 4), np.float32)
    out[..., :3] = D.rgb(color) * a[..., None]
    out[..., 3] = a
    return out


def scene_at(tl: Timeline, t: float) -> int:
    idx = 0
    for i, s in enumerate(tl.scenes):
        if s["start_s"] <= t:
            idx = i
    return idx


def background(tl: Timeline, t: float, cam) -> np.ndarray:
    th = tl.theme
    i = scene_at(tl, t)

    def cols(sc):
        b = sc.get("bg") or {}
        return b.get("color", th["bg"]), b.get("color2", b.get("color", th["bg2"])), b.get("glow", th.get("glow"))

    bg = _bg(tl.W, tl.H, *cols(tl.scenes[i]))
    tr = tl.scenes[i].get("transition_in") or {}
    if i > 0 and tr.get("type") in ("fade", "flip"):
        k = (t - tl.scenes[i]["start_s"]) / max(float(tr.get("dur", 0.5)), 1e-3)
        if k < 1:
            old = _bg(tl.W, tl.H, *cols(tl.scenes[i - 1]))
            x = ease("inout", k)
            bg = old * (1 - x) + bg * x
    bg = bg.copy()
    kinds = tuple(th.get("deco") or ())
    if kinds:
        lay = _deco(tl.W, tl.H, kinds, th.get("deco_color", th["muted"]))
        cx, cy, z, r = cam
        par = 0.35   # parallax: lớp trang trí đi chậm hơn nội dung
        ox = (lay.shape[1] - tl.W) / 2 + (cx - tl.W / 2) * par
        oy = (lay.shape[0] - tl.H) / 2 + (cy - tl.H / 2) * par
        zz = 1 + (z - 1) * par
        M = D.affine(tl.W / 2, tl.H / 2, zz, -r * par, ox + tl.W / 2, oy + tl.H / 2)
        D.place(bg, lay, M)
    return bg


def transition_overlay(tl: Timeline, frame: np.ndarray, t: float):
    """chuyển cảnh dạng phủ: bars (vạch dọc quét qua), wipe (mảng màu quét ngang)."""
    i = scene_at(tl, t)
    for j in (i, i + 1):
        if j <= 0 or j >= len(tl.scenes):
            continue
        sc = tl.scenes[j]
        tr = sc.get("transition_in") or {}
        typ = tr.get("type")
        if typ not in ("bars", "wipe"):
            continue
        dur = float(tr.get("dur", 0.6))
        k = (t - (sc["start_s"] - dur / 2)) / dur   # phủ kín đúng lúc đổi cảnh
        if not 0 <= k <= 1:
            continue
        col = D.rgb(tr.get("color", tl.theme["accent"]))
        if typ == "bars":
            n = int(tr.get("n", 6))
            bw = tl.W / n
            for b in range(n):
                kk = clamp01(k * 1.4 - b * 0.4 / n)
                cover = ease("inout", kk * 2) if kk < 0.5 else 1 - ease("inout", kk * 2 - 1)
                hh = int(tl.H * cover)
                if hh <= 0:
                    continue
                x0, x1 = int(b * bw), int((b + 1) * bw) + 1
                if kk < 0.5:
                    frame[:hh, x0:x1] = col
                else:
                    frame[tl.H - hh:, x0:x1] = col
        else:
            if k < 0.5:
                x1 = int(tl.W * ease("inout", k * 2))
                frame[:, :x1] = col
            else:
                x0 = int(tl.W * ease("inout", k * 2 - 1))
                frame[:, x0:] = col


# ---------------- vẽ từng loại đối tượng ----------------
def _q(v, step=0.05):
    return max(step, round(v / step) * step)


def _fmt_num(v: float, dec: int) -> str:
    s = f"{v:,.{dec}f}"   # 1,234.5 → 1.234,5 (kiểu Việt)
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _entrance(p: dict, t: float):
    """(dx, dy, dscale, opacity, blur, clip) do reveal/hide gây ra."""
    dx = dy = 0.0
    sc = 1.0
    op = 1.0
    blur = 0.0
    clip = None
    for which in ("_enter", "_leave"):
        ev = p.get(which)
        if not ev:
            continue
        e, k = ev
        style = e.get("style", "up" if which == "_enter" else "fade")
        x = ease(e.get("ease", "back" if style == "pop" else "out"), k) if which == "_enter" else 1 - ease("in", k)
        if which == "_enter" and k <= 0 and t < e["start_s"]:
            return 0, 0, 1, 0, 0, None
        dist = float(e.get("dist", 60))
        op *= clamp01(x * 1.6) if style not in ("mask_left", "mask_up", "draw") else 1.0
        if style == "up":
            dy += (1 - x) * dist
        elif style == "down":
            dy -= (1 - x) * dist
        elif style == "left":
            dx += (1 - x) * dist * 2
        elif style == "right":
            dx -= (1 - x) * dist * 2
        elif style in ("pop", "scale"):
            sc *= 0.6 + 0.4 * x if style == "scale" else max(x, 0.01)
        elif style == "blur":
            blur += (1 - x) * 24
            sc *= 1.06 - 0.06 * x
        elif style == "mask_left":
            clip = ("x", x)
        elif style == "mask_up":
            clip = ("y", x)
        if style in ("up", "down", "left", "right"):
            blur += (1 - x) * 10
    return dx, dy, sc, op, blur, clip


def lod_fade(lod, z: float, band: float = 0.18) -> float:
    """lod = [zmin, zmax] (zmax có thể null): độ đục 0..1, chuyển mềm trong ±18% quanh ngưỡng (thang log)."""
    lo, hi = (lod + [None])[:2] if isinstance(lod, list) else (lod, None)
    k = 1.0
    lz = math.log(max(z, 1e-6))
    if lo:
        k *= clamp01((lz - math.log(lo)) / band + 0.5)
    if hi:
        k *= clamp01((math.log(hi) - lz) / band + 0.5)
    return k


def _mix(c1: str, c2: str, k: float) -> str:
    a, b = D.rgb(c1), D.rgb(c2)
    c = a + (b - a) * clamp01(round(k * 12) / 12)
    return "#%02X%02X%02X" % tuple(int(round(v * 255)) for v in c)


def _lum(rgb) -> float:
    c = np.where(rgb <= 0.03928, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2])


def contrast(c1, c2) -> float:
    a, b = sorted((_lum(np.asarray(c1, np.float64)), _lum(np.asarray(c2, np.float64))))
    return (b + 0.05) / (a + 0.05)


def _clip(spr: np.ndarray, clip):
    if not clip:
        return spr
    axis, k = clip
    s = spr.copy()
    if axis == "x":
        s[:, int(s.shape[1] * k):] = 0
    else:
        s[:int(s.shape[0] * (1 - k))] = 0   # lộ dần từ dưới lên
    return s


class Renderer:
    def __init__(self, tl: Timeline):
        self.tl = tl
        self.prev_screen: dict[str, tuple] = {}
        self.boxes: list[dict] = []     # khung chữ/shape đã vẽ ở frame hiện tại (QA va chạm, cắt khung, tương phản)
        self.cur_id = None
        self.slots: dict = {}           # vị trí nhãn đã chọn (giữ ổn định qua các frame, chỉ đổi khi bị chạm)

    # --- toạ độ thế giới của object (có parent) ---
    def world(self, oid: str, t: float, depth=0) -> dict:
        p = self.tl.props(oid, t)
        par = p.get("parent")
        if par and par in self.tl.objs and depth < 6:
            pp = self.world(par, t, depth + 1)
            # con đi theo hiệu ứng vào/ra của cha (pop, trượt, mờ) → chữ không “lòi” khỏi thẻ đang mở
            pdx, pdy, pdsc, pop, _, _ = _entrance(pp, t)
            pp = dict(pp, x=pp.get("x", 0) + pdx, y=pp.get("y", 0) + pdy, scale=pp["scale"] * pdsc, opacity=pp["opacity"] * pop)
            s = pp["scale"]
            a = math.radians(pp["rot"])   # vị trí con xoay theo cha (vd quả nặng nằm trên đòn bập bênh)
            ox, oy = p.get("x", 0) * s, p.get("y", 0) * s
            if p.get("fixed") and pp.get("space") != "screen":   # nhãn cỡ cố định: độ lệch tính bằng px màn hình
                z = camera_at(self.tl, t)[2]
                ox, oy = ox / z, oy / z
            p["x"] = pp["x"] + ox * math.cos(a) - oy * math.sin(a)
            p["y"] = pp["y"] + ox * math.sin(a) + oy * math.cos(a)
            if pp.get("space") == "screen":
                p["space"] = "screen"
            p["scale"] *= s
            p["rot"] += pp["rot"]
            p["opacity"] *= pp["opacity"]
            pv0, pv1 = self.tl.objs[par]["_vis"]
            p["_parent_vis"] = pv0 <= t < pv1
        return p

    def _prepass(self):
        """chạy dựng ở thời điểm mỗi nhãn/callout ổn định (hết hiệu ứng vào) theo thứ tự thời gian → vị trí được tính
        một lần rồi khoá; mọi frame sau (kể cả ảnh tĩnh lẻ) dùng đúng vị trí đó → chữ không xê dịch."""
        self._prepassed = True
        need = []
        for oid, o in self.tl.objs.items():
            if o.get("inside") or o.get("avoid") or o["type"] in ("callout", "routelabel"):
                ev = [e for e in self.tl.events.get(oid, []) if e["action"] == "reveal"]
                t0 = (ev[0].get("end_s", ev[0]["start_s"] + 0.4) if ev else o["_vis"][0]) + 0.02
                t1 = min(o["_vis"][1], self.tl.duration) - 0.05
                sc_end = min((s_["end_s"] for s_ in self.tl.scenes if s_["start_s"] <= t0 < s_["end_s"]), default=t1) - 0.05
                need += [t0, (t0 + max(t1, t0)) / 2, min(sc_end, t1), t1]
        times = sorted(set(round(min(max(x, 0), self.tl.duration - 0.01), 2) for x in need))
        self._voting = True        # pass 1: mỗi thời điểm, mỗi nhãn ghi vị trí nào còn trống
        self._votes = {}
        for t in times:
            self.frame(t, t - 1 / self.tl.fps)
        self._voting = False       # chốt: vị trí trống ở nhiều thời điểm nhất (hoà → ưu tiên thứ tự đề xuất)
        for key, (cands, tally) in self._votes.items():
            best = max(range(len(cands)), key=lambda i: (tally[i], -i))
            self.slots[key] = cands[best]

    def frame(self, t: float, prev_t: float | None = None) -> np.ndarray:
        tl = self.tl
        if not getattr(self, "_prepassed", False):
            self._prepass()
        cam = camera_at(tl, t)
        cam0 = camera_at(tl, prev_t) if prev_t is not None else cam
        out = background(tl, t, cam)
        self.boxes = []
        self.route_mask = np.zeros((tl.H, tl.W), np.uint8)
        self.reserved = self._screen_text_boxes(t)   # chữ cố định trên màn hình (tiêu đề…) vẽ sau cùng → giữ chỗ trước
        for oid in tl.order:
            o = tl.objs[oid]
            v0, v1 = o["_vis"]
            if not (v0 <= t < v1):
                continue
            p = self.world(oid, t)
            if p.get("_parent_vis") is False:
                continue
            p0 = self.world(oid, prev_t) if prev_t is not None else p
            self.draw_obj(out, p, p0, t, cam, cam0)
        transition_overlay(tl, out, t)
        return out

    def draw_obj(self, dst, p, p0, t, cam, cam0):
        tl = self.tl
        screen = p.get("space") == "screen"
        dx, dy, dsc, op, blur, clip = _entrance(p, t)
        op *= p["opacity"]
        if p.get("lod") and not screen:    # mức chi tiết theo zoom: mờ dần quanh ngưỡng (không nhấp nháy)
            op *= lod_fade(p["lod"], cam[2])
        self.cur_id = p.get("id")
        if op <= 0.003:
            return
        x, y = p.get("x", tl.W / 2) + dx, p.get("y", tl.H / 2) + dy
        if screen:
            sx, sy, z, crot = x, y, 1.0, 0.0
            sx0, sy0 = p0.get("x", sx), p0.get("y", sy)
        else:
            sx, sy = world_to_screen(tl, cam, x, y)
            sx0, sy0 = world_to_screen(tl, cam0, p0.get("x", x) + dx, p0.get("y", y) + dy)
            z, crot = cam[2], cam[3]
        mv = (sx - sx0, sy - sy0)
        bv = (mv[0] * 0.6, mv[1] * 0.6) if math.hypot(*mv) > 5 else (0.0, 0.0)
        bl = math.hypot(*bv)
        if bl > 36:   # nhòe vừa đủ cảm giác chuyển động, không nhoè nát hình
            bv = (bv[0] * 36 / bl, bv[1] * 36 / bl)
        if blur > 1:   # nhòe khi đang vào/ra: dồn theo hướng trượt (dọc nếu không rõ hướng)
            bv = (bv[0], bv[1] + blur) if abs(bv[0]) < 1 else (bv[0] + math.copysign(blur, bv[0]), bv[1])
        scale = p["scale"] * dsc * (1.0 if p.get("fixed") else z)
        upright = p.get("fixed") or p["type"] in ("text", "counter", "callout", "routelabel", "icon", "list", "halo")
        rot = p["rot"] - (0.0 if upright else crot)      # camera xoay: nền + hình học xoay, chữ/nhãn vẫn thẳng
        if p.get("inside") and p["type"] == "text" and not screen:   # tên lãnh thổ phải nằm trong lãnh thổ đó
            fit = self._fit_inside(p, sx, sy, scale, cam)
            if fit is None:
                return
            sx, sy, scale = fit
            p = dict(p, anchor="center", text="\n".join(self._inside_lines), max_w=0, line_h=p.get("line_h", 1.05))
        fn = getattr(self, "d_" + p["type"], None)
        if fn is None:
            raise ValueError(f"loại object chưa hỗ trợ: {p['type']}")
        fn(dst, p, sx, sy, scale, rot, op, bv, clip, t, cam)

    # --- từng loại ---
    def d_text(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        th = self.tl.theme
        size = float(p.get("size", 64))
        qs = _q(scale, 0.05)
        rs = int(round(size * qs))
        role = p.get("font", "display")
        txt = p["text"]
        if p.get("upper"):
            txt = txt.upper()
        hl = p.get("highlight") or {}
        keep = tuple(p.get("keep", [])) + ((hl["match"],) if hl.get("match") else ())
        # ngắt dòng theo nghĩa ở CỠ GỐC rồi chốt — phóng to/thu nhỏ hay hiện từng từ không làm nhảy bố cục
        lines = VT.break_lines(txt, role, int(size), float(p.get("max_w", 0)), keep, bool(p.get("allow_orphan", False)))
        words, bw, bh = D.text_layout("\n".join(lines), role, rs, 0.0, p.get("align", "center"), float(p.get("line_h", 1.15)),
                                      float(p.get("spacing", 0)) * qs)
        hl_idx = set(hl.get("words", []))
        if hl.get("match"):
            keys = [w.lower() for w in hl["match"].split()]
            ws = [w[0].lower().strip(".,!?:;“”\"") for w in words]
            for i in range(len(ws) - len(keys) + 1):
                if ws[i:i + len(keys)] == keys:
                    hl_idx.update(range(i, i + len(keys)))
        times = list(p.get("word_times") or [])
        if times:   # từ thiếu mốc KHÔNG được hiện sớm: lấy mốc từ trước (validator vẫn báo lỗi thiếu mốc)
            while len(times) < len(words):
                times.append((times[-1] if times else 0) + 0.12)
        anchor = p.get("anchor", "center")
        ax = {"left": 0, "right": bw}.get(anchor.split("-")[-1] if "-" in anchor else anchor, bw / 2)
        ay = 0 if anchor.startswith("top") else bh / 2
        res = scale / qs
        a0 = math.radians(rot)
        if p.get("avoid") and op > 0.05:
            sx, sy = self._place_label(p, sx, sy, (bw / 2 - ax) * res, (bh / 2 - ay) * res, bw * res, bh * res,
                                       float(p.get("plate_pad", size * 0.45)) * qs if p.get("plate") else 4, op, dst)
        cx_ = sx + ((bw / 2 - ax) * res) * math.cos(a0) - ((bh / 2 - ay) * res) * math.sin(a0)
        cy_ = sy + ((bw / 2 - ax) * res) * math.sin(a0) + ((bh / 2 - ay) * res) * math.cos(a0)
        box = (cx_ - bw * res / 2, cy_ - bh * res / 2, cx_ + bw * res / 2, cy_ + bh * res / 2)
        H, W = dst.shape[:2]
        if p.get("space") != "screen" and (p.get("fixed") or p.get("edge_fade")):   # nhãn gắn bản đồ trôi ra mép → mờ dần, không cắt dở
            m_ = min(box[0], box[1], W - box[2], H - box[3])
            op *= clamp01(m_ / 36.0 + 0.0) if m_ < 36 else 1.0
            if op <= 0.01:
                return
        bx0, by0, bx1, by1 = (int(max(box[0], 0)), int(max(box[1], 0)), int(min(box[2], W)), int(min(box[3], H)))
        bg_mean = dst[by0:by1, bx0:bx1].reshape(-1, 3).mean(0) if bx1 > bx0 and by1 > by0 else np.zeros(3)
        plate = p.get("plate")
        if plate:   # nền chữ: “auto” chọn theo vùng nền thật phía sau + làm tối chi tiết bản đồ quanh chữ
            pad = float(p.get("plate_pad", size * 0.45)) * qs
            fill, stroke = plate, p.get("plate_stroke")
            if plate == "auto":   # đảo tương phản: nền tối → hộp sáng chữ tối; nền sáng → hộp tối chữ trắng
                l = _lum(bg_mean)
                if l < 0.2:
                    fill = p.get("plate_light", "#F3F5F8")
                    p = dict(p, color=p.get("plate_text_dark", "#0E1622"), shadow=0)
                else:
                    fill = p.get("plate_dark", "#111820")
                    p = dict(p, color="#FFFFFF", shadow=0)
                stroke = stroke or ("#FFFFFF" if l >= 0.2 else None)
                k = np.zeros(dst.shape[:2], np.float32)   # backdrop: tối mềm quanh khối chữ
                cv2.rectangle(k, (int(box[0] - pad * 2), int(box[1] - pad * 2)), (int(box[2] + pad * 2), int(box[3] + pad * 2)), 1.0, -1)
                k = cv2.GaussianBlur(k, (0, 0), pad * 1.2 + 6) * 0.45 * op
                dst *= (1 - k[..., None])
            pr = {"w": (bw + 2 * pad) / qs, "h": (bh + 2 * pad) / qs, "r": float(p.get("plate_r", size * 0.35)), "fill": fill,
                  "stroke": stroke, "stroke_w": 2 if stroke else 0, "scale": 1, "rot": 0}
            self.d_rect(dst, pr, cx_, cy_, scale, rot, op * float(p.get("plate_opacity", 0.92)), bv, clip, t, cam)
            bg_mean = D.rgb(fill) * float(p.get("plate_opacity", 0.92)) + bg_mean * (1 - float(p.get("plate_opacity", 0.92)))
            box = (box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad)
        mk = p.get("marker")
        if mk:   # dải nhấn chạy dưới/sau cụm chữ, trái → phải
            mkeys = [w.lower() for w in mk.get("match", "").split()]
            ws = [w[0].lower().strip(".,!?:;“”\"") for w in words]
            hit = [i for i in range(len(ws) - len(mkeys) + 1) if ws[i:i + len(mkeys)] == mkeys]
            kk = ease("out", (t - float(mk.get("t", 0))) / float(mk.get("dur", 0.45)))
            if hit and kk > 0:
                i0 = hit[0]; i1 = i0 + len(mkeys) - 1
                x0 = words[i0][1]; x1 = words[i1][1] + words[i1][3]
                yb = words[i0][2] + rs * (0.98 if mk.get("mode", "under") == "under" else 0.62)
                hh = rs * (0.16 if mk.get("mode", "under") == "under" else 0.78)
                wv = (x1 - x0 + rs * 0.2) * kk
                lx, ly = (x0 - rs * 0.1 + wv / 2 - ax) * res, (yb - ay) * res
                mr = {"w": wv / qs, "h": hh / qs, "r": hh / qs / 3, "fill": mk.get("color", th["accent"]), "scale": 1, "rot": 0}
                self.d_rect(dst, mr, sx + lx * math.cos(a0) - ly * math.sin(a0), sy + lx * math.sin(a0) + ly * math.cos(a0),
                            scale, rot, op * float(mk.get("opacity", 0.9)), bv, None, t, cam)
        style = p.get("word_style", "up")
        hl_k = 1.0 if hl.get("t") is None else ease("inout", (t - float(hl["t"])) / float(hl.get("dur", 0.35)))
        base_col = p.get("color", th["text"])
        if base_col == "auto":   # nền sáng (vd vùng tô vàng) → chữ tối; nền tối → chữ trắng
            base_col = "#1E1606" if _lum(bg_mean) > 0.3 else "#FFFFFF"
            p = dict(p, shadow=0 if _lum(bg_mean) > 0.3 else p.get("shadow", 0.6))
        for i, (w, wx, wy, ww) in enumerate(words):
            col = _mix(base_col, hl.get("color", th["accent"]), hl_k) if i in hl_idx else base_col
            wrole = hl.get("font", role) if i in hl_idx else role
            wsz = rs
            spr, ox, oy = D.word_sprite(w, wrole, wsz, col, float(p.get("spacing", 0)) * qs,
                                        float(p.get("shadow", 0.25)), int(p.get("stroke", 0)), p.get("stroke_color", "#000000"))
            wop, wdy, wbl, wsc, wclip = op, 0.0, 0.0, 1.0, None
            if times:   # từng từ vào theo lời, trong bố cục đã chốt
                k = (t - float(times[i])) / float(p.get("word_dur", 0.26))
                if k < 0:
                    continue
                e = ease("out", k)
                if style == "mask":       # trượt lên trong mặt nạ dòng: chữ không bay ngoài dòng
                    wdy = (1 - e) * rs * 0.9
                    wclip = ("y", clamp01(e * 1.15))
                elif style == "fade":
                    wop *= clamp01(k * 1.4); wdy = (1 - e) * rs * 0.12
                elif style == "scale":
                    wop *= clamp01(k * 2.0); wsc = 0.82 + 0.18 * ease("back", k)
                else:                     # up: dịch lên + nhòe nhẹ, rõ nét hẳn khi xong
                    wop *= clamp01(k * 1.8); wdy = (1 - e) * rs * 0.4; wbl = (1 - e) * 8
            if i in hl_idx and hl.get("punch") and hl.get("t") is not None:   # nhấn scale nhẹ đúng lúc đổi màu
                kp = (t - float(hl["t"])) / 0.35
                if 0 <= kp <= 1:
                    wsc *= 1 + 0.12 * math.sin(math.pi * kp)
            lx, ly = (wx - ax) * res, (wy - ay + wdy) * res
            px = sx + lx * math.cos(a0) - ly * math.sin(a0)
            py = sy + lx * math.sin(a0) + ly * math.cos(a0)
            M = D.affine(px + ox * res * (1 - wsc) + (spr.shape[1] - 2 * ox) * res * (1 - wsc) / 2,
                         py + oy * res * (1 - wsc) + (spr.shape[0] - 2 * oy) * res * (1 - wsc) / 2, res * wsc, rot, ox, oy)
            D.place(dst, _clip(_clip(spr, clip), wclip), M, wop, (bv[0], bv[1] + wbl))
        if op > 0.05:
            fg = D.rgb(base_col)
            cr = contrast(fg, bg_mean)
            if p.get("stroke"):                       # viền chữ tạo tương phản riêng
                cr = max(cr, contrast(fg, D.rgb(p.get("stroke_color", "#000000"))))
            elif float(p.get("shadow", 0)) >= 0.6:   # bóng tối mềm quanh chữ (halo) → đọc được trên nền sáng
                cr = max(cr, 3.2)
            self.boxes.append({"id": self.cur_id, "kind": "text", "box": box, "op": op, "contrast": cr,
                               "px": rs * res, "text": txt[:30], "fixed_screen": p.get("space") == "screen"})

    def _territory_mask(self, inside, cam):
        """mặt nạ (khung màn hình) của lãnh thổ: {"iso": "VNM"} (Natural Earth) hoặc {"src": geojson, "name": tên}."""
        if inside.get("iso"):
            fm, _ = _geo_masks(self.tl, cam, (inside["iso"],), str(GEO_DIR / inside.get("geo", "ne_50m_admin_0_countries.geojson")),
                               MAP_W, 0, (-1, 0, 1, 2))
            return fm
        A, b = _cam_affine(self.tl, cam)
        m = np.zeros((self.tl.H, self.tl.W), np.uint8)
        polys = []
        for props, parts in _gj(_gpath(inside["src"]), MAP_W):
            if props.get("name") == inside.get("name"):
                polys += [((xy @ A.T + b) * 16).astype(np.int32) for xy in parts]
        if polys:
            cv2.fillPoly(m, polys, 255, cv2.LINE_8, 4)
        return m

    def _fit_inside(self, p, sx, sy, scale, cam):
        """tìm vị trí khối chữ nằm TRỌN trong lãnh thổ (lề ≥ 6px), gần điểm mong muốn nhất; thử thu nhỏ tới 70%;
        không vừa → None (ẩn). Giữ vị trí cũ nếu vẫn vừa (không nhảy)."""
        m = self._territory_mask(p["inside"], cam).copy()
        for (x0, y0, x1, y1) in getattr(self, "reserved", []):    # vùng tiêu đề/chú thích/nguồn không tính là chỗ trống
            m[max(int(y0) - 8, 0):max(int(y1) + 8, 0), max(int(x0) - 8, 0):max(int(x1) + 8, 0)] = 0
        if not m.any():
            return None
        size = float(p.get("size", 64))
        role = p.get("font", "display")
        lines = VT.break_lines(p["text"], role, int(size), float(p.get("max_w", 0)), tuple(p.get("keep", [])))
        k = 4                                                     # lưới thô cho nhanh
        ms = cv2.resize((m > 127).astype(np.uint8), (self.tl.W // k, self.tl.H // k), interpolation=cv2.INTER_AREA)
        ii = cv2.integral(ms)
        key = ("in", p.get("id"))
        if key in self.slots:
            wx, wy, lns, f = self.slots[key]
            self._inside_lines = lns
            X, Y = world_to_screen(self.tl, cam, wx, wy)
            _, bw, bh = D.text_layout("\n".join(lns), role, max(int(size * f * scale), 8), 0.0, "center", float(p.get("line_h", 1.05)), 0.0)
            k2 = 2                                     # còn nằm trọn trong lãnh thổ không? không → ẩn (không dời chỗ)
            x0, y0, x1, y1 = int((X - bw / 2) / k2), int((Y - bh / 2) / k2), int((X + bw / 2) / k2), int((Y + bh / 2) / k2)
            mm = cv2.resize((m > 127).astype(np.uint8), (self.tl.W // k2, self.tl.H // k2), interpolation=cv2.INTER_NEAREST)
            if x0 < 0 or y0 < 0 or x1 >= mm.shape[1] or y1 >= mm.shape[0] or mm[y0:y1, x0:x1].mean() < 0.97:
                return None
            return X, Y, scale * f
        stacked = tuple(" ".join(lines).split())
        fmin = max(float(p.get("min_size", 22)) / size, 0.3)        # không nhỏ hơn cỡ còn đọc được trên điện thoại
        fs = [f for f in (1.0, 0.85, 0.7, 0.6, 0.5, 0.42, 0.36, 0.3) if f >= fmin - 1e-6] or [fmin]
        variants = [(tuple(lines), f) for f in fs[:2]] + ([(stacked, f) for f in fs] if len(stacked) > 1 else []) \
            + [(tuple(lines), f) for f in fs[2:]]
        for vi, (lns, f) in enumerate(variants):
            _, bw, bh = D.text_layout("\n".join(lns), role, max(int(size * f * scale), 8), 0.0, "center", float(p.get("line_h", 1.05)), 0.0)
            w2, h2 = int((bw + 6) / k / 2) + 1, int((bh + 4) / k / 2) + 1

            def fits(cx, cy):
                x0, y0, x1, y1 = cx - w2, cy - h2, cx + w2, cy + h2
                if x0 < 0 or y0 < 0 or x1 >= ms.shape[1] or y1 >= ms.shape[0]:
                    return False
                return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0] >= (x1 - x0) * (y1 - y0)
            ys, xs = np.nonzero(ms)
            if not len(xs):
                return None
            d = (xs * k - sx) ** 2 + (ys * k - sy) ** 2
            for i in np.argsort(d)[:4000:3]:
                if fits(xs[i], ys[i]):
                    X, Y = float(xs[i] * k), float(ys[i] * k)
                    cx, cy, z, r = cam
                    self.slots[key] = (cx + (X - self.tl.W / 2) / z, cy + (Y - self.tl.H / 2) / z, lns, f)   # (rot = 0 trên bản đồ)
                    self._inside_lines = lns
                    return X, Y, scale * f
        return None

    def _screen_text_boxes(self, t):
        out = []
        for oid in self.tl.order:
            o = self.tl.objs[oid]
            if o["type"] != "text" or o.get("space") != "screen" or o.get("parent"):
                continue
            v0, v1 = o["_vis"]
            if not (v0 <= t < v1):
                continue
            size = float(o.get("size", 64))
            role = o.get("font", "display")
            keep = tuple(o.get("keep", [])) + (((o.get("highlight") or {}).get("match"),) if (o.get("highlight") or {}).get("match") else ())
            txt = o["text"].upper() if o.get("upper") else o["text"]
            lines = VT.break_lines(txt, role, int(size), float(o.get("max_w", 0)), keep)
            _, bw, bh = D.text_layout("\n".join(lines), role, int(size), 0.0, "center", float(o.get("line_h", 1.15)), 0.0)
            pad = float(o.get("plate_pad", size * 0.45)) if o.get("plate") else 6
            x, y = float(o.get("x", self.tl.W / 2)), float(o.get("y", self.tl.H / 2))
            out.append((x - bw / 2 - pad, y - bh / 2 - pad, x + bw / 2 + pad, y + bh / 2 + pad))
        return out

    def _place_label(self, p, sx, sy, cdx, cdy, bw, bh, pad, op, dst):
        """chọn vị trí nhãn không chạm chữ/shape đã vẽ (cách ≥ gap px). Giữ vị trí cũ nếu vẫn trống → không nhảy."""
        gap = float(p.get("avoid_gap", 10))
        W, H = self.tl.W, self.tl.H
        others = [b["box"] for b in self.boxes if b["op"] > 0.3 and b["id"] != self.cur_id]

        def box_at(dx, dy):
            cx, cy = sx + cdx + dx, sy + cdy + dy
            return (cx - bw / 2 - pad - gap, cy - bh / 2 - pad - gap, cx + bw / 2 + pad + gap, cy + bh / 2 + pad + gap)

        def free(b):
            sx0, sy0, sx1, sy1 = self.tl.safe
            if b[0] < sx0 - 20 or b[2] > sx1 + 20 or b[1] < sy0 - 30 or b[3] > sy1 + 40:
                return False
            return all(min(b[2], o[2]) - max(b[0], o[0]) <= 0 or min(b[3], o[3]) - max(b[1], o[1]) <= 0 for o in others)
        key = self.cur_id
        if key in self.slots and not getattr(self, "_voting", False):   # đã khoá: giữ nguyên chỗ
            dx, dy = self.slots[key]
            return self._leader_and_pos(p, sx, sy, cdx, cdy, bw, bh, pad, op, dst, dx, dy)
        cands = [(0, 0)]
        step_y, step_x = bh + 2 * pad + gap, bw / 2 + pad + gap
        for r in (1, 1.6, 2.3, 3.2):
            cands += [(0, -step_y * r), (0, step_y * r), (step_x * r, 0), (-step_x * r, 0),
                      (step_x * r, -step_y * r), (-step_x * r, -step_y * r), (step_x * r, step_y * r), (-step_x * r, step_y * r)]
        if getattr(self, "_voting", False):
            v = self._votes.setdefault(key, (cands, [0] * len(cands)))
            for i, c in enumerate(cands):
                v[1][i] += 1 if free(box_at(*c)) else 0
            pick = next((c for c in cands if free(box_at(*c))), (0, 0))
        else:
            pick = next((c for c in cands if free(box_at(*c))), (0, 0))
            self.slots[key] = pick
        dx, dy = pick
        return self._leader_and_pos(p, sx, sy, cdx, cdy, bw, bh, pad, op, dst, dx, dy)

    def _leader_and_pos(self, p, sx, sy, cdx, cdy, bw, bh, pad, op, dst, dx, dy):
        if math.hypot(dx, dy) > 20 and p.get("leader", True):   # đường dẫn về điểm neo
            m = np.zeros(dst.shape[:2], np.uint8)
            tx, ty = sx + cdx + dx, sy + cdy + dy
            ex = min(max(sx, tx - bw / 2 - pad), tx + bw / 2 + pad)
            ey = min(max(sy, ty - bh / 2 - pad), ty + bh / 2 + pad)
            cv2.line(m, (int(sx * 16), int(sy * 16)), (int(ex * 16), int(ey * 16)), 255, 2, cv2.LINE_AA, 4)
            _tint(dst, m, p.get("leader_color", "#C9D3E0"), op * 0.9)
        return sx + dx, sy + dy

    def d_rect(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        qs = _q(scale, 0.05)
        w, h = float(p.get("w", 300)), float(p.get("h", 200))
        spr, pad = D.rect_sprite(int(w * qs), int(h * qs), float(p.get("r", 24)) * qs, p.get("fill", "#FFFFFF"),
                                 p.get("stroke"), int(p.get("stroke_w", 0) * qs), float(p.get("shadow", 0)),
                                 p.get("fill2"))
        res = scale / qs
        M = D.affine(sx, sy, res, rot, pad + w * qs / 2, pad + h * qs / 2)
        D.place(dst, _clip(spr, clip), M, op, bv)
        if p.get("id") and op > 0.3 and (p.get("stroke") or p.get("fill")) and abs(rot) < 3:
            self.boxes.append({"id": p["id"], "kind": "shape", "box": (sx - w * scale / 2, sy - h * scale / 2, sx + w * scale / 2, sy + h * scale / 2),
                               "op": op})

    def d_circle(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        qs = _q(scale, 0.05)
        r = float(p.get("r", 80))
        spr, pad = D.circle_sprite(int(r * qs), p.get("fill", "#FFFFFF"), p.get("stroke"),
                                   int(p.get("stroke_w", 0) * qs), float(p.get("shadow", 0)))
        res = scale / qs
        M = D.affine(sx, sy, res, rot, pad + int(r * qs), pad + int(r * qs))
        D.place(dst, _clip(spr, clip), M, op, bv)

    def d_image(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        qs = _q(scale, 0.05)
        w, h = float(p.get("w", 600)), float(p.get("h", 400))
        spr, pad = D.image_sprite(self.tl.path(p["src"]), int(w * qs), int(h * qs), float(p.get("r", 24)) * qs,
                                  p.get("fit", "cover"), float(p.get("shadow", 0.35)), p.get("stroke"),
                                  int(p.get("stroke_w", 0) * qs), bool(p.get("gray", False)))
        res = scale / qs
        M = D.affine(sx, sy, res, rot, pad + w * qs / 2, pad + h * qs / 2)
        D.place(dst, _clip(spr, clip), M, op, bv)
        for key, dy, role, sz, col in (("label", h / 2 + 34, "bold", 34, self.tl.theme["text"]),
                                       ("source", h / 2 + (78 if p.get("label") else 30), "medium", 24, self.tl.theme["muted"])):
            if p.get(key):
                q = {"text": (("Nguồn: " if key == "source" else "") + p[key]), "font": role, "size": sz, "color": col,
                     "shadow": 0.3, "align": "center", "type": "text", "scale": 1, "rot": 0}
                a = math.radians(rot)
                ly = dy * scale
                self.d_text(dst, q, sx - ly * math.sin(a), sy + ly * math.cos(a), scale, rot, op, bv, None, t, cam)

    def d_video(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        """clip trong khung bo góc: chạy từ giây `in` của nguồn, bắt đầu lúc object hiện; `rate` <1 = chậm lại."""
        w, h = int(p.get("w", 600)), int(p.get("h", 400))
        v0 = self.tl.objs[p["id"]]["_vis"][0] if p.get("id") in self.tl.objs else 0
        span = self.tl.objs[p["id"]]["_vis"][1] - v0 if p.get("id") in self.tl.objs else 5
        rate = float(p.get("rate", 1.0))
        span = min(span, self.tl.duration - v0 + 0.5) * rate
        fr = D.video_frames(self.tl.path(p["src"]), float(p.get("in", 0)), round(span, 2), w, h, self.tl.fps, bool(p.get("gray", False)))
        i = min(max(int((t - v0) * rate * self.tl.fps), 0), len(fr) - 1)
        m, sh, pad = D.frame_mask(w, h, float(p.get("r", 24)), float(p.get("shadow", 0.35)))
        spr = sh.copy()
        img = fr[i].astype(np.float32) / 255
        reg = spr[pad:pad + h, pad:pad + w]
        reg[..., :3] = reg[..., :3] * (1 - m[..., None]) + img * m[..., None]
        reg[..., 3] = reg[..., 3] * (1 - m) + m
        if p.get("stroke"):
            ring, _ = D.rect_sprite(w, h, float(p.get("r", 24)), None, p["stroke"], int(p.get("stroke_w", 4)), 0)
            p2 = int(p.get("stroke_w", 4)) + 2
            spr[pad:pad + h, pad:pad + w] = D.over(spr[pad:pad + h, pad:pad + w], ring[p2:p2 + h, p2:p2 + w])
        M = D.affine(sx, sy, scale, rot, pad + w / 2, pad + h / 2)
        D.place(dst, _clip(spr, clip), M, op, bv)
        for key, dy, role, sz, col in (("label", h / 2 + 34, "bold", 32, self.tl.theme["text"]),
                                       ("source", h / 2 + (74 if p.get("label") else 30), "medium", 22, self.tl.theme["muted"])):
            if p.get(key):
                q = {"text": (("Nguồn: " if key == "source" else "") + p[key]), "font": role, "size": sz, "color": col,
                     "shadow": 0, "align": "center", "type": "text", "scale": 1, "rot": 0}
                a = math.radians(rot)
                ly = dy * scale
                self.d_text(dst, q, sx - ly * math.sin(a), sy + ly * math.cos(a), scale, rot, op, bv, None, t, cam)

    def d_icon(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        th = self.tl.theme
        qs = _q(scale, 0.05)
        if p.get("bg"):
            r = float(p.get("bg_r", p.get("size", 96) * 0.95))
            spr, pad = D.circle_sprite(int(r * qs), p["bg"], p.get("ring"), int(p.get("ring_w", 0) * qs), float(p.get("shadow", 0.3)))
            M = D.affine(sx, sy, scale / qs, rot, pad + int(r * qs), pad + int(r * qs))
            D.place(dst, _clip(spr, clip), M, op, bv)
        spr = D.icon_sprite(p["name"], int(float(p.get("size", 96)) * qs), p.get("color", th["text"]))
        h, w = spr.shape[:2]
        M = D.affine(sx, sy, scale / qs, rot, w / 2, h / 2)
        D.place(dst, _clip(spr, clip), M, op, bv)
        if p.get("label"):
            q = {"text": p["label"], "font": "bold", "size": p.get("label_size", 34), "color": p.get("label_color", th["text"]),
                 "shadow": 0.3, "scale": 1, "rot": 0, "type": "text"}
            off = float(p.get("bg_r", p.get("size", 96))) + 40
            self.d_text(dst, q, sx, sy + off * scale, scale, rot, op, bv, None, t, cam)

    def _pt(self, ref, t, cam, screen):
        if isinstance(ref, str):
            q = self.world(ref, t)
            x, y = q.get("x", 0), q.get("y", 0)
        else:
            x, y = ref
        return (x, y) if screen else world_to_screen(self.tl, cam, x, y)

    def d_line(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        th = self.tl.theme
        screen = p.get("space") == "screen"
        pts = [self._pt(r, t, cam, screen) for r in (p.get("points") or [p["from"], p["to"]])]
        zt = 1.0 if (p.get("fixed") or screen) else cam[2]      # đường trên màn hình không phóng theo zoom bản đồ
        trim0, trim1 = float(p.get("trim_start", 0)) * zt, float(p.get("trim_end", 0)) * zt
        if len(pts) == 2:
            (x0, y0), (x1, y1) = pts
            L = math.hypot(x1 - x0, y1 - y0) or 1
            ux, uy = (x1 - x0) / L, (y1 - y0) / L
            x0, y0, x1, y1 = x0 + ux * trim0, y0 + uy * trim0, x1 - ux * trim1, y1 - uy * trim1
            bend = float(p.get("bend", 0)) * (1.0 if p.get("bend_screen") else cam[2])
            if bend:   # cong bậc hai
                mx, my = (x0 + x1) / 2 - uy * bend, (y0 + y1) / 2 + ux * bend
                ts = np.linspace(0, 1, 48)
                pts = [((1 - s) ** 2 * x0 + 2 * (1 - s) * s * mx + s * s * x1, (1 - s) ** 2 * y0 + 2 * (1 - s) * s * my + s * s * y1) for s in ts]
            else:
                pts = [(x0, y0), (x1, y1)]
        prog = clamp01(float(p.get("progress", 1)))
        if prog <= 0:
            return
        seg = np.array(pts, np.float64)
        d = np.r_[0, np.cumsum(np.hypot(*np.diff(seg, axis=0).T))]
        cut = d[-1] * prog
        k = np.searchsorted(d, cut)
        keep = seg[:k]
        if k < len(seg) and k > 0:
            f = (cut - d[k - 1]) / max(d[k] - d[k - 1], 1e-6)
            keep = np.vstack([keep, seg[k - 1] + (seg[k] - seg[k - 1]) * f])
        if len(keep) < 2:
            return
        zz = 1.0 if (p.get("fixed") or screen) else cam[2]
        wpx = max(float(p.get("width", 4)) * zz * p["scale"], 1)
        col = p.get("color", th["muted"])
        x0, y0 = keep.min(0) - wpx * 6 - 30
        x1, y1 = keep.max(0) + wpx * 6 + 30
        H, W = dst.shape[:2]
        x0, y0, x1, y1 = int(max(x0, 0)), int(max(y0, 0)), int(min(x1, W)), int(min(y1, H))
        if x1 <= x0 or y1 <= y0:
            return
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        P = ((keep - [x0, y0]) * 16).astype(np.int32)
        if p.get("dash"):
            dl, gl = float(p["dash"]) * zt, float(p.get("gap", p["dash"])) * zt
            dd = np.r_[0, np.cumsum(np.hypot(*np.diff(keep, axis=0).T))]
            s = 0.0
            while s < dd[-1]:
                e = min(s + dl, dd[-1])
                ss = np.linspace(s, e, 4)
                q = np.c_[np.interp(ss, dd, keep[:, 0]), np.interp(ss, dd, keep[:, 1])]
                cv2.polylines(m, [((q - [x0, y0]) * 16).astype(np.int32)], False, 255, int(round(wpx)), cv2.LINE_AA, 4)
                s = e + gl
        else:
            cv2.polylines(m, [P], False, 255, int(round(wpx)), cv2.LINE_AA, 4)
        if p.get("arrow") and prog > 0.02:
            (ax0, ay0), (ax1, ay1) = keep[-2], keep[-1]
            ang = math.atan2(ay1 - ay0, ax1 - ax0)
            L = wpx * 4 + 10
            tip = np.array([ax1, ay1])
            l = tip - L * np.array([math.cos(ang - 0.45), math.sin(ang - 0.45)])
            r = tip - L * np.array([math.cos(ang + 0.45), math.sin(ang + 0.45)])
            tri = ((np.array([tip, l, r]) - [x0, y0]) * 16).astype(np.int32)
            cv2.fillPoly(m, [tri], 255, cv2.LINE_AA, 4)
        a = m.astype(np.float32) / 255 * op
        sub = dst[y0:y1, x0:x1]
        sub *= (1 - a[..., None])
        sub += D.rgb(col) * a[..., None]

    def d_list(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        th = self.tl.theme
        gap = float(p.get("gap", p.get("size", 48) * 1.6))
        for i, it in enumerate(p.get("items", [])):
            it = it if isinstance(it, dict) else {"text": it}
            ti = it.get("t")
            k = 1.0 if ti is None else (t - float(ti)) / 0.3
            if k <= 0:
                continue
            e = ease("out", k)
            ly = i * gap * scale
            lx = (1 - e) * 60 * scale
            iop = op * clamp01(k * 1.6)
            style = p.get("style", "dot")
            if style == "pill":
                q = {"type": "text", "text": it["text"], "font": p.get("font", "bold"), "size": p.get("size", 48),
                     "color": p.get("pill_text", "#FFFFFF"), "shadow": 0, "scale": 1, "rot": 0, "anchor": "center"}
                fw = D.font(q["font"], int(q["size"])).getlength(it["text"]) + q["size"] * 1.2
                rp = {"w": fw, "h": q["size"] * 1.7, "r": q["size"] * 0.85, "fill": p.get("pill_fill", "#111111"),
                      "shadow": 0.35, "scale": 1, "rot": 0}
                self.d_rect(dst, rp, sx + lx, sy + ly, scale, rot, iop, bv, None, t, cam)
                self.d_text(dst, q, sx + lx, sy + ly, scale, rot, iop, bv, None, t, cam)
            else:
                dot = {"r": p.get("size", 48) * 0.18, "fill": it.get("color", p.get("bullet", th["accent"])), "scale": 1, "rot": 0}
                self.d_circle(dst, dot, sx + lx, sy + ly + p.get("size", 48) * 0.05 * scale, scale, rot, iop, bv, None, t, cam)
                q = {"type": "text", "text": it["text"], "font": p.get("font", "semi"), "size": p.get("size", 48),
                     "color": it.get("text_color", p.get("color", th["text"])), "shadow": 0.25, "scale": 1, "rot": 0,
                     "anchor": "left", "align": "left"}
                self.d_text(dst, q, sx + lx + p.get("size", 48) * 0.6 * scale, sy + ly, scale, rot, iop, bv, None, t, cam)

    def d_counter(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        v = float(p.get("value", 0))
        txt = p.get("prefix", "") + _fmt_num(v, int(p.get("decimals", 0))) + p.get("suffix", "")
        q = {**p, "text": txt, "type": "text"}
        self.d_text(dst, q, sx, sy, scale, rot, op, bv, clip, t, cam)

    def d_progress(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        th = self.tl.theme
        w, h = float(p.get("w", 700)), float(p.get("h", 36))
        val = clamp01(float(p.get("value", 0.5)) * float(p.get("progress", 1)))
        track = {"w": w, "h": h, "r": h / 2, "fill": p.get("track", "#2C3038"), "scale": 1, "rot": 0}
        self.d_rect(dst, track, sx, sy, scale, rot, op, bv, None, t, cam)
        if val > 0.005:
            fw = max(w * val, h)
            a = math.radians(rot)
            off = (fw - w) / 2 * scale
            bar = {"w": fw, "h": h, "r": h / 2, "fill": p.get("color", th["accent"]), "scale": 1, "rot": 0}
            self.d_rect(dst, bar, sx + off * math.cos(a), sy + off * math.sin(a), scale, rot, op, bv, None, t, cam)
        if p.get("show_value", True):
            q = {"type": "text", "text": _fmt_num(val * 100, int(p.get("decimals", 0))) + "%", "font": "display",
                 "size": p.get("value_size", h * 1.6), "color": p.get("value_color", th["text"]), "scale": 1, "rot": 0, "shadow": 0.3}
            self.d_text(dst, q, sx, sy - (h / 2 + p.get("value_size", h * 1.6) * 0.8) * scale, scale, rot, op, bv, None, t, cam)

    def d_bars(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        th = self.tl.theme
        data = p.get("data", [])
        if not data:
            return
        w, h = float(p.get("w", 760)), float(p.get("h", 520))
        mx = float(p.get("max") or max(float(d["value"]) for d in data) or 1)
        n = len(data)
        slot = w / n
        bw = slot * float(p.get("bar_ratio", 0.62))
        prog = clamp01(float(p.get("progress", 1)))
        base_y = sy + h / 2 * scale
        axis = {"w": w + 40, "h": 4, "r": 2, "fill": p.get("axis", th["muted"]), "scale": 1, "rot": 0}
        self.d_rect(dst, axis, sx, base_y, scale, 0, op * 0.8, bv, None, t, cam)
        for i, d in enumerate(data):
            kk = clamp01(prog * 1.25 - i * 0.25 / max(n, 1))
            kk = ease("out", kk)
            val = float(d["value"]) * kk
            bh = max(h * val / mx, 2)
            cx = sx + (-w / 2 + slot * (i + 0.5)) * scale
            bar = {"w": bw, "h": bh, "r": min(14, bw / 4), "fill": d.get("color", p.get("color", th["accent"])), "scale": 1, "rot": 0}
            self.d_rect(dst, bar, cx, base_y - bh / 2 * scale, scale, 0, op, bv, None, t, cam)
            lab = {"type": "text", "text": d.get("label", ""), "font": "semi", "size": p.get("label_size", 30),
                   "color": th["muted"], "scale": 1, "rot": 0, "shadow": 0, "max_w": slot * 0.95}
            self.d_text(dst, lab, cx, base_y + 40 * scale, scale, 0, op, bv, None, t, cam)
            if kk > 0.05:
                num = {"type": "text", "text": _fmt_num(val, int(p.get("decimals", 0))) + p.get("unit", ""), "font": "display",
                       "size": p.get("value_size", 40), "color": th["text"], "scale": 1, "rot": 0, "shadow": 0.3}
                self.d_text(dst, num, cx, base_y - (bh + 34) * scale, scale, 0, op * clamp01(kk * 2), bv, None, t, cam)

    def d_quote(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
        """khung trích dẫn: giấy sáng nghiêng nhẹ, câu chính tô màu, dòng nguồn."""
        th = self.tl.theme
        w = float(p.get("w", 860))
        size = float(p.get("size", 40))
        role = p.get("font", "body")
        words, bw, bh = D.text_layout(p["text"], role, int(size), w - 90, "left", 1.4, 0.0)
        h = bh + 90 + (60 if p.get("source") else 0)
        tilt = float(p.get("tilt", -2.5))
        paper = {"w": w, "h": h, "r": 10, "fill": p.get("paper", "#F4F1EA"), "shadow": 0.45, "scale": 1, "rot": 0}
        R = rot + tilt
        self.d_rect(dst, paper, sx, sy, scale, R, op, bv, clip, t, cam)
        a = math.radians(R)

        def at(lx, ly):
            return sx + (lx * math.cos(a) - ly * math.sin(a)) * scale, sy + (lx * math.sin(a) + ly * math.cos(a)) * scale

        hl = (p.get("highlight") or "").lower().split()
        ws = [x[0].lower().strip(".,!?:;“”\"") for x in words]
        hit = set()
        for i in range(len(ws) - len(hl) + 1):
            if hl and ws[i:i + len(hl)] == hl:
                hit.update(range(i, i + len(hl)))
        hk = 1.0
        if p.get("highlight_t") is not None:
            hk = ease("out", (t - float(p["highlight_t"])) / 0.5)
        f = D.font(role, int(size))
        sp = f.getlength(" ")
        for i, (wd, wx, wy, ww) in enumerate(words):   # dải tô sau chữ, chạy trái → phải
            if i in hit and hk > 0:
                bx, by = -w / 2 + 45 + wx, -h / 2 + 45 + wy + size * 0.62
                ext = ww + (sp if i + 1 in hit else 0)
                hw = ext * clamp01(hk * 1.15)
                cx, cy = at(bx + hw / 2, by)
                hr = {"w": max(hw, 1), "h": size * 1.05, "r": 3, "fill": p.get("hl_color", th["accent"]), "scale": 1, "rot": 0}
                self.d_rect(dst, hr, cx, cy, scale, R, op * 0.85, bv, None, t, cam)
        for i, (wd, wx, wy, ww) in enumerate(words):
            q = {"type": "text", "text": wd, "font": role, "size": size, "color": p.get("ink", "#1B1C1F"), "shadow": 0,
                 "scale": 1, "rot": 0, "anchor": "top-left", "align": "left"}
            cx, cy = at(-w / 2 + 45 + wx, -h / 2 + 45 + wy)
            self.d_text(dst, q, cx, cy, scale, R, op, bv, None, t, cam)
        if p.get("source"):
            q = {"type": "text", "text": "Nguồn: " + p["source"], "font": "medium", "size": size * 0.62, "color": "#6B6F78",
                 "shadow": 0, "scale": 1, "rot": 0, "anchor": "top-left", "align": "left"}
            cx, cy = at(-w / 2 + 45, h / 2 - 62)
            self.d_text(dst, q, cx, cy, scale, R, op, bv, None, t, cam)


# ---------------- xuất ----------------
def load(path: Path) -> Timeline:
    return Timeline(json.loads(path.read_text(encoding="utf-8")), path.parent)


def render_video(tl: Timeline, out_mp4: Path, progress=print, t_range=None) -> dict:
    """dựng toàn bộ frame → mp4 không tiếng (h264). Trả số đo đứng hình để QA."""
    fps = tl.fps
    n = int(math.ceil(tl.duration * fps))
    f0, f1 = (0, n) if not t_range else (int(t_range[0] * fps), min(n, int(math.ceil(t_range[1] * fps))))
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{tl.W}x{tl.H}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_mp4)], stdin=subprocess.PIPE)
    R = Renderer(tl)
    still_run, max_still, last = 0, 0.0, None
    stills = []
    samples = []      # khung chữ/shape mỗi 6 frame → QA va chạm trong lúc animate
    try:
        for f in range(f0, f1):
            t = f / fps
            img = R.frame(t, (f - 1) / fps if f > 0 else None)
            u8 = (np.clip(img, 0, 1) * 255).astype(np.uint8)
            enc.stdin.write(u8.tobytes())
            if (f - f0) % 6 == 0:
                samples.append((t, list(R.boxes)))
            small = cv2.resize(u8, (108, 192), interpolation=cv2.INTER_AREA).astype(np.int16)
            if last is not None and np.abs(small - last).mean() < 0.06:
                still_run += 1
                max_still = max(max_still, still_run / fps)
                if still_run == fps * 2:
                    stills.append(round(t - 2, 2))
            else:
                still_run = 0
            last = small
            if f % 30 == 0:
                progress(f"v2m frame {f - f0}/{f1 - f0}")
    finally:
        enc.stdin.close()
        enc.wait()
    if enc.returncode:
        raise RuntimeError("ffmpeg dựng video lỗi")
    _STILL_R[id(tl)] = R
    return {"frames": f1 - f0, "max_still_s": round(max_still, 2), "still_from": stills, "samples": samples}


_STILL_R: dict = {}


def still(tl: Timeline, t: float, fresh: bool = False) -> np.ndarray:
    """ảnh một frame. Dùng lại renderer của timeline (vị trí nhãn đã khoá chỉ tính một lần); fresh=True để kiểm tất định."""
    R = Renderer(tl) if fresh else _STILL_R.setdefault(id(tl), Renderer(tl))
    return (np.clip(R.frame(t, t - 1 / tl.fps), 0, 1) * 255).astype(np.uint8)


# ---------------- bản đồ (Natural Earth, chiếu Mercator, lặp 3 bản ngang để camera đi qua Thái Bình Dương) ----------------
GEO_DIR = D.ROOT / "assets" / "geo"
MAP_W = 4000.0   # bề rộng thế giới (px ở zoom 1) cho 360° kinh độ


def geo_xy(lon: float, lat: float, copy: int = 0, map_w: float = MAP_W) -> tuple[float, float]:
    """kinh/vĩ độ → toạ độ thế giới. copy = bản lặp (−1 tây, 0 giữa, +1 đông)."""
    lat = max(min(lat, 84.0), -84.0)
    R = map_w / (2 * math.pi)
    return (lon + 180) / 360 * map_w + copy * map_w, -R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


@lru_cache(maxsize=2)
def _geo(path: str, map_w: float):
    """→ {ISO3: [mảng điểm thế giới (bản 0)]}, nhãn, tên."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    polys, labels = {}, {}
    for f in data["features"]:
        p = f["properties"]
        iso = p.get("ADM0_A3") or p.get("ISO_A3")
        g = f["geometry"]
        rings = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
        out = []
        for poly in rings:
            ring = np.array(poly[0], np.float64)
            xy = np.empty_like(ring)
            lat = np.clip(ring[:, 1], -84, 84)
            xy[:, 0] = (ring[:, 0] + 180) / 360 * map_w
            xy[:, 1] = -map_w / (2 * math.pi) * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
            out.append(xy)
        polys.setdefault(iso, []).extend(out)
        if p.get("LABEL_X") is not None:
            labels[iso] = (p["LABEL_X"], p["LABEL_Y"])
    return polys, labels


def _cam_affine(tl, cam):
    cx, cy, z, r = cam
    a = math.radians(-r)
    c, s = math.cos(a) * z, math.sin(a) * z
    return np.array([[c, -s], [s, c]]), np.array([tl.W / 2 - c * cx + s * cy, tl.H / 2 - s * cx - c * cy])


def _copies(tl, cam, p, map_w):
    """bản lặp kinh độ cần vẽ. Khi cả vòng thế giới hẹp hơn khung (zoom ra rất xa), chỉ vẽ bản gần tâm camera
    → không bao giờ thấy một quốc gia hai lần trong cùng khung."""
    cp = tuple(p.get("copies", (-1, 0, 1, 2)))
    if map_w * cam[2] < tl.W * 1.1:
        k0 = int(math.floor(cam[0] / map_w))
        return (k0,)
    return cp


def _geo_masks(tl, cam, isos, path, map_w, stroke_w, copies, fill=True, trace=1.0):
    """mặt nạ tô + viền (uint8, khung) cho các nước isos (None = tất cả)."""
    polys, _ = _geo(path, map_w)
    A, b = _cam_affine(tl, cam)
    fm = np.zeros((tl.H, tl.W), np.uint8)
    sm = np.zeros((tl.H, tl.W), np.uint8) if stroke_w > 0 else None
    pts_f = []
    for iso, rings in polys.items():
        if isos is not None and iso not in isos:
            continue
        for k in copies:
            for xy in rings:
                s = (xy + [k * map_w, 0]) @ A.T + b
                mn, mx = s.min(0), s.max(0)
                if mx[0] < -50 or mn[0] > tl.W + 50 or mx[1] < -50 or mn[1] > tl.H + 50:
                    continue
                if (mx - mn).max() < 0.6:
                    continue
                pts_f.append((s * 16).astype(np.int32))
    if pts_f:
        if fill:
            cv2.fillPoly(fm, pts_f, 255, cv2.LINE_AA, 4)
        if sm is not None:
            if trace >= 0.999:
                cv2.polylines(sm, pts_f, True, 255, max(int(round(stroke_w)), 1), cv2.LINE_AA, 4)
            else:   # viền vẽ dần: mỗi vòng (kể cả đảo nhỏ) chạy cùng tỉ lệ chu vi → các phần nhỏ không bị bỏ sót
                for q in pts_f:
                    seg = np.linalg.norm(np.diff(np.vstack([q, q[:1]]), axis=0), axis=1)
                    cum = np.concatenate([[0], np.cumsum(seg)])
                    n = int(np.searchsorted(cum, cum[-1] * trace)) + 1
                    if n >= 2:
                        cv2.polylines(sm, [np.vstack([q, q[:1]])[:n]], False, 255, max(int(round(stroke_w)), 1), cv2.LINE_AA, 4)
    return fm, sm


def _tint(dst, mask, color, alpha):
    if mask is None or alpha <= 0:
        return
    a = mask.astype(np.float32) * (alpha / 255.0)
    dst *= (1 - a[..., None])
    dst += D.rgb(color) * a[..., None]


def _d_map(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """nền bản đồ thế giới: lục địa + đường biên quốc gia (dữ liệu vector thật)."""
    path = str(GEO_DIR / p.get("geo", "ne_50m_admin_0_countries.geojson"))
    mw = float(p.get("map_w", MAP_W))
    fm, sm = _geo_masks(self.tl, cam, None, path, mw, float(p.get("stroke_w", 1.2)), _copies(self.tl, cam, p, mw))
    _tint(dst, fm, p.get("fill", "#1E2A3A"), op)
    _tint(dst, sm, p.get("stroke", "#3A4C64"), op * float(p.get("stroke_op", 0.9)))


def _d_region(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """tô sáng lãnh thổ các nước (ISO3), có quầng sáng mềm."""
    path = str(GEO_DIR / p.get("geo", "ne_50m_admin_0_countries.geojson"))
    mw = float(p.get("map_w", MAP_W))
    isos = tuple(p["iso"]) if isinstance(p["iso"], list) else (p["iso"],)
    # tô dần (progress 0→1): 0–45% viền vẽ dần/sáng lên để nhận diện hình; 25–100% màu lan từ tâm ra, mask theo đúng ranh giới
    pr = clamp01(float(p.get("progress", 1.0)))
    k_line = ease("inout", clamp01(pr / 0.45))
    k_fill = ease("out", clamp01((pr - 0.25) / 0.75))
    fm, sm = _geo_masks(self.tl, cam, isos, path, mw, float(p.get("stroke_w", 2.5)), _copies(self.tl, cam, p, mw), trace=k_line)
    col = p.get("fill", self.tl.theme["accent"])
    full = fm
    if k_fill < 0.999:
        ys, xs = np.nonzero(fm > 127)
        if len(xs):
            cx, cy = (float(np.mean(xs)), float(np.mean(ys)))
            rmax = float(np.sqrt(((xs - cx) ** 2 + (ys - cy) ** 2).max())) + 4
            yy, xx = np.ogrid[:fm.shape[0], :fm.shape[1]]
            rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            edge = max(rmax * 0.18, 6)
            rad = np.clip((rmax * k_fill * 1.18 - rr) / edge, 0, 1)
            fm = (fm.astype(np.float32) * rad).astype(np.uint8)    # lan dần nhưng KHÔNG ra ngoài mask lãnh thổ
        else:
            fm = (fm.astype(np.float32) * k_fill).astype(np.uint8)
    if p.get("dim"):   # giảm nhấn mọi thứ ngoài lãnh thổ đang nói (theo mask thật, viền mềm)
        soft = cv2.GaussianBlur(full, (0, 0), 6).astype(np.float32) / 255.0
        dst *= (1 - float(p["dim"]) * op * k_line * (1 - soft))[..., None]
    if pr < 1 and k_line < 1:   # viền sáng hơn trong lúc vẽ
        _tint(dst, sm, "#FFFFFF", op)
    if p.get("glow", 0.6) > 0:
        g = cv2.GaussianBlur(fm, (0, 0), 18)
        dst += D.rgb(col) * (g.astype(np.float32)[..., None] / 255.0) * float(p.get("glow", 0.6)) * op * 0.6
    _tint(dst, fm, col, op * float(p.get("fill_op", 0.85)))
    _tint(dst, sm, p.get("stroke", "#FFFFFF"), op * 0.9)
    if "VNM" in isos and p.get("islands", True):   # Việt Nam luôn kèm Hoàng Sa, Trường Sa
        _islands(self, dst, p, op * k_fill, cam, col)


# Natural Earth 1:50m bỏ qua các đảo nhỏ → khi tô Việt Nam, vẽ kèm hai quần đảo Hoàng Sa, Trường Sa (toạ độ các đảo chính, gần đúng)
VN_ISLANDS = {
    "hoang_sa": [(112.34, 16.83), (111.61, 16.53), (111.20, 15.78), (112.73, 16.67), (111.51, 16.45), (112.53, 16.03),
                 (111.75, 16.97), (112.27, 16.95), (111.95, 16.30)],
    "truong_sa": [(111.92, 8.64), (114.37, 10.38), (114.33, 11.43), (114.33, 9.88), (114.36, 10.18), (112.91, 7.89),
                  (114.48, 10.37), (114.29, 11.05), (112.35, 8.93), (113.67, 8.97), (115.53, 10.72), (113.42, 9.70),
                  (114.66, 10.91), (112.85, 8.10)],
}
VN_ISLAND_LABELS = {"hoang_sa": ((112.0, 16.5), "QĐ. Hoàng Sa"), "truong_sa": ((113.8, 9.9), "QĐ. Trường Sa")}


def _islands(self, dst, p, op, cam, col):
    """điểm đảo Hoàng Sa, Trường Sa: hiện ở cấp quốc gia; zoom ra châu lục/thế giới thì mờ dần (không phóng chấm quá cỡ)."""
    op *= lod_fade(p.get("islands_lod", [1.6, None]), cam[2])
    if op <= 0.01:
        return
    mw = float(p.get("map_w", MAP_W))
    A, b = _cam_affine(self.tl, cam)
    r = float(p.get("island_r", max(3.0, min(7.0, 2.2 * cam[2]))))
    m = np.zeros((self.tl.H, self.tl.W), np.uint8)
    for k in _copies(self.tl, cam, p, mw):
        for pts in VN_ISLANDS.values():
            for lon, lat in pts:
                x, y = np.array(geo_xy(lon, lat, k, mw)) @ A.T + b
                if -20 < x < self.tl.W + 20 and -20 < y < self.tl.H + 20:
                    cv2.circle(m, (int(x * 16), int(y * 16)), int(r * 16), 255, -1, cv2.LINE_AA, 4)
    _tint(dst, m, col, op)


def _d_halo(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """dấu hiệu thu hút chú ý: chấm tâm + vòng gợn lan ra rồi tan (rõ là tín hiệu, không giống đường biên)."""
    col = D.rgb(p.get("color", self.tl.theme["accent"]))
    r0 = float(p.get("r", 70))
    per = float(p.get("period", 1.6))
    m = np.zeros((self.tl.H, self.tl.W), np.uint8)
    for j in range(int(p.get("rings", 2))):
        ph = ((t - float(p.get("t0", 0))) / per + j / max(int(p.get("rings", 2)), 1)) % 1.0
        rr = r0 * (0.35 + 0.9 * ph)
        a = int(255 * (1 - ph) ** 1.5)
        cv2.circle(m, (int(sx * 16), int(sy * 16)), int(rr * 16), a, max(int(p.get("width", 4)), 1), cv2.LINE_AA, 4)
    cv2.circle(m, (int(sx * 16), int(sy * 16)), int(float(p.get("dot", 9)) * 16), 255, -1, cv2.LINE_AA, 4)
    a = m.astype(np.float32)[..., None] / 255.0 * op
    dst *= 1 - a
    dst += col * a


Renderer.d_halo = _d_halo
Renderer.d_map = _d_map
Renderer.d_region = _d_region


# ---------------- lớp GeoJSON: ranh giới hành chính + tuyến đường (cùng phép chiếu với bản đồ nền) ----------------
def _ll_to_world(arr: np.ndarray, map_w: float) -> np.ndarray:
    xy = np.empty_like(arr, dtype=np.float64)
    lat = np.clip(arr[:, 1], -84, 84)
    xy[:, 0] = (arr[:, 0] + 180) / 360 * map_w
    xy[:, 1] = -map_w / (2 * math.pi) * np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
    return xy


@lru_cache(maxsize=32)
def _gj(path: str, map_w: float):
    """GeoJSON → [(properties, [vòng/đường toạ độ thế giới])]."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    out = []
    for f in d.get("features", [d] if d.get("type") == "Feature" else []):
        g = f["geometry"]
        t = g["type"]
        if t == "Polygon":
            parts = [g["coordinates"][0]]
        elif t == "MultiPolygon":
            parts = [p[0] for p in g["coordinates"]]
        elif t == "LineString":
            parts = [g["coordinates"]]
        elif t == "MultiLineString":
            parts = g["coordinates"]
        else:
            continue
        out.append((f.get("properties", {}), [_ll_to_world(np.array(p, np.float64), map_w) for p in parts]))
    return out


def _gpath(p: str) -> str:
    q = Path(p)
    return str(q if q.is_absolute() else D.ROOT / q)


def _d_geo(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """vùng hành chính từ GeoJSON: tô theo tên (fill_by) + viền mảnh."""
    mw = float(p.get("map_w", MAP_W))
    A, b = _cam_affine(self.tl, cam)
    files = p["src"] if isinstance(p["src"], list) else [p["src"]]
    fill_by = p.get("fill_by", {})
    groups: dict[str, list] = {}
    strokes = []
    for fpath in files:
        for props, parts in _gj(_gpath(fpath), mw):
            name = props.get("name", "")
            col = fill_by.get(name, p.get("fill"))
            for xy in parts:
                s = xy @ A.T + b
                mn, mx = s.min(0), s.max(0)
                if mx[0] < -50 or mn[0] > self.tl.W + 50 or mx[1] < -50 or mn[1] > self.tl.H + 50 or (mx - mn).max() < 0.8:
                    continue
                q = (s * 16).astype(np.int32)
                if col:
                    groups.setdefault(col, []).append(q)
                strokes.append(q)
    for col, polys in groups.items():
        m = np.zeros((self.tl.H, self.tl.W), np.uint8)
        cv2.fillPoly(m, polys, 255, cv2.LINE_AA, 4)
        _tint(dst, m, col, op * float(p.get("fill_op", 1.0)))
    if strokes and p.get("stroke"):
        m = np.zeros((self.tl.H, self.tl.W), np.uint8)
        cv2.polylines(m, strokes, True, 255, max(int(round(float(p.get("stroke_w", 1.5)))), 1), cv2.LINE_AA, 4)
        _tint(dst, m, p["stroke"], op * float(p.get("stroke_op", 0.9)))


@lru_cache(maxsize=64)
def _line_world(path: str, fid: str, map_w: float):
    for props, parts in _gj(path, map_w):
        if str(props.get("id")) == fid or props.get("name") == fid:
            return parts
    raise ValueError(f"không có tuyến {fid} trong {path}")


def _d_geoline(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """tuyến đường thật (LineString) vẽ dần theo progress; tùy chọn chấm sáng chạy ở đầu nét."""
    mw = float(p.get("map_w", MAP_W))
    A, b = _cam_affine(self.tl, cam)
    parts = _line_world(_gpath(p["src"]), str(p["feature"]), mw)
    prog = clamp01(float(p.get("progress", 1)))
    if prog <= 0:
        return
    if p.get("reverse"):
        parts = [q[::-1] for q in parts][::-1]
    lens = [np.r_[0, np.cumsum(np.hypot(*np.diff(q, axis=0).T))] for q in parts]
    total = sum(l[-1] for l in lens)
    cut = total * prog
    keep, head = [], None
    acc = 0.0
    for q, l in zip(parts, lens):
        if acc >= cut:
            break
        c = cut - acc
        if c >= l[-1]:
            keep.append(q); head = q[-1]
        else:
            k = int(np.searchsorted(l, c))
            f = (c - l[k - 1]) / max(l[k] - l[k - 1], 1e-9)
            pt = q[k - 1] + (q[k] - q[k - 1]) * f
            keep.append(np.vstack([q[:k], pt])); head = pt
        acc += l[-1]
    w = max(float(p.get("width", 6)), 1)
    col = p.get("color", self.tl.theme["accent"])
    polys = [((q @ A.T + b) * 16).astype(np.int32) for q in keep if len(q) > 1]
    if not polys:
        return
    if p.get("glow", 0.5):
        g = np.zeros((self.tl.H, self.tl.W), np.uint8)
        cv2.polylines(g, polys, False, 255, int(w * 3), cv2.LINE_AA, 4)
        g = cv2.GaussianBlur(g, (0, 0), w * 1.6)
        dst += D.rgb(col) * (g.astype(np.float32)[..., None] / 255.0) * float(p.get("glow", 0.5)) * op
    if p.get("casing"):
        m = np.zeros((self.tl.H, self.tl.W), np.uint8)
        cv2.polylines(m, polys, False, 255, int(w + 4), cv2.LINE_AA, 4)
        _tint(dst, m, p["casing"], op)
    if getattr(self, "route_mask", None) is not None:   # vùng tuyến: callout/nhãn không được che
        cv2.polylines(self.route_mask, polys, False, 255, int(w + 14), cv2.LINE_8, 4)
    m = np.zeros((self.tl.H, self.tl.W), np.uint8)
    if p.get("dash"):   # nét đứt theo px màn hình (phân biệt tuyến song song)
        dl, gl = float(p["dash"]), float(p.get("gap", p["dash"] * 0.7))
        for q in [(q @ A.T + b) for q in keep if len(q) > 1]:
            dd = np.r_[0, np.cumsum(np.hypot(*np.diff(q, axis=0).T))]
            s_ = 0.0
            while s_ < dd[-1]:
                e_ = min(s_ + dl, dd[-1])
                ss = np.linspace(s_, e_, 6)
                seg = np.c_[np.interp(ss, dd, q[:, 0]), np.interp(ss, dd, q[:, 1])]
                cv2.polylines(m, [(seg * 16).astype(np.int32)], False, 255, int(round(w)), cv2.LINE_AA, 4)
                s_ = e_ + gl
    else:
        cv2.polylines(m, polys, False, 255, int(round(w)), cv2.LINE_AA, 4)
    _tint(dst, m, col, op)
    if p.get("head") and head is not None and prog < 0.999:
        hx, hy = head @ A.T + b
        r = float(p.get("head", 9))
        m = np.zeros((self.tl.H, self.tl.W), np.uint8)
        cv2.circle(m, (int(hx * 16), int(hy * 16)), int(r * 2.2 * 16), 255, -1, cv2.LINE_AA, 4)
        m = cv2.GaussianBlur(m, (0, 0), r)
        dst += D.rgb(col) * (m.astype(np.float32)[..., None] / 255.0) * 0.8 * op
        m = np.zeros((self.tl.H, self.tl.W), np.uint8)
        cv2.circle(m, (int(hx * 16), int(hy * 16)), int(r * 16), 255, -1, cv2.LINE_AA, 4)
        _tint(dst, m, "#FFFFFF", op)


Renderer.d_geo = _d_geo
Renderer.d_geoline = _d_geoline


# ---------------- nhãn gắn tuyến (luôn bám đúng đường đang chỉ) ----------------
def _route_point(parts, frac):
    lens = [np.r_[0, np.cumsum(np.hypot(*np.diff(q, axis=0).T))] for q in parts]
    total = sum(l[-1] for l in lens)
    cut = total * clamp01(frac)
    for q, l in zip(parts, lens):
        if cut <= l[-1]:
            k = max(int(np.searchsorted(l, cut)), 1)
            f = (cut - l[k - 1]) / max(l[k] - l[k - 1], 1e-9)
            pt = q[k - 1] + (q[k] - q[k - 1]) * f
            d = q[k] - q[k - 1]
            return pt, d / max(np.hypot(*d), 1e-9)
        cut -= l[-1]
    q = parts[-1]
    d = q[-1] - q[-2]
    return q[-1], d / max(np.hypot(*d), 1e-9)


def _d_routelabel(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """nhãn tên tuyến = callout neo vào điểm `at` (0..1) trên chính hình học tuyến → không trôi sang tuyến khác."""
    mw = float(p.get("map_w", MAP_W))
    parts = _line_world(_gpath(p["src"]), str(p["feature"]), mw)
    pt, _d = _route_point(parts, float(p.get("at", 0.5)))
    A, b = _cam_affine(self.tl, cam)
    s0 = pt @ A.T + b
    o_ = max(float(p.get("opacity", 1.0)), 1e-3)
    q = dict(p, type="callout", color=p.get("color", self.tl.theme["accent"]),
             _label_boost=min(1.0 / o_, max(o_, float(p.get("label_min_op", 0.85))) / o_))   # giảm nhấn: mờ thân/neo, chữ vẫn đọc rõ
    _d_callout(self, dst, q, float(s0[0]), float(s0[1]), 1.0, 0.0, op, (0, 0), None, t, cam)


# ---------------- callout (theo bộ callout tham khảo): dấu neo nhỏ + thân mảnh + nhãn ở xa ----------------
def _d_callout(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """dấu neo đúng điểm, thân dẫn mảnh vẽ ra trước, nhãn hiện sau ở đầu thân.
    Tự chọn hướng/độ dài thân để nhãn KHÔNG che tuyến đường (route_mask) và không chạm chữ/shape đã vẽ; giữ ổn định qua frame.
    style: "tag" (thẻ tối viền màu nhấn — nhãn quan trọng) | "plain" (chữ trơn — nhãn phụ). sub = dòng nhỏ phía trên tên."""
    col = p.get("color", self.tl.theme["accent"])
    k = 1.0
    if p.get("_enter"):
        e, kk = p["_enter"]
        k = kk
    k_stem, k_lab = clamp01(k * 2.2), clamp01(k * 2.2 - 1.0)
    style = p.get("style", "tag")
    size = float(p.get("size", 30))
    title = p["text"]
    sub = p.get("sub")
    f = D.font("bold", int(size))
    lines = VT.break_lines(title, "bold", int(size), float(p.get("max_w", 420)), tuple(p.get("keep", [])))
    tw = max(f.getlength(l) for l in lines)
    th = len(lines) * size * 1.12 + (size * 0.72 if sub else 0)
    pad = 12 if style == "tag" else 2
    bw_, bh_ = tw + 2 * pad, th + 2 * pad
    W, H = self.tl.W, self.tl.H
    others = [o["box"] for o in self.boxes if o["op"] > 0.3 and o["id"] != p.get("id")] + list(getattr(self, "reserved", []))
    rm = getattr(self, "route_mask", None)
    L0 = float(p.get("stem", 120))
    dirs = p.get("dirs") or ["up", "down", "up-right", "up-left", "down-right", "down-left", "right", "left"]
    vec = {"up": (0, -1), "down": (0, 1), "right": (1, 0), "left": (-1, 0), "up-right": (0.6, -0.8), "up-left": (-0.6, -0.8),
           "down-right": (0.6, 0.8), "down-left": (-0.6, 0.8)}

    def geom(d, L):
        vx, vy = vec[d]
        ex, ey = sx + vx * L, sy + vy * L                          # đầu thân
        cx = ex + (bw_ / 2 if vx > 0.3 else -bw_ / 2 if vx < -0.3 else 0)
        cy = ey + (bh_ / 2 if vy > 0.3 else -bh_ / 2 if vy < -0.3 else 0)
        return (ex, ey), (cx - bw_ / 2 - 8, cy - bh_ / 2 - 8, cx + bw_ / 2 + 8, cy + bh_ / 2 + 8), (cx, cy)

    def ok(d, L):
        (ex, ey), bb, _c = geom(d, L)
        sx0_, sy0_, sx1_, sy1_ = self.tl.safe
        if bb[0] < sx0_ - 20 or bb[2] > sx1_ + 20 or bb[1] < sy0_ - 20 or bb[3] > sy1_ + 30:
            return False
        if any(min(bb[2], o[2]) - max(bb[0], o[0]) > 0 and min(bb[3], o[3]) - max(bb[1], o[1]) > 0 for o in others):
            return False
        if rm is not None:
            x0, y0, x1, y1 = (int(max(v, 0)) for v in bb)
            if rm[y0:min(y1, H), x0:min(x1, W)].any():          # nhãn đè lên đường
                return False
            n = 12                                               # thân dẫn không cắt ngang tuyến khác (bỏ đoạn sát điểm neo)
            for i in range(3, n):
                u = i / n
                px_, py_ = int(sx + (ex - sx) * u), int(sy + (ey - sy) * u)
                if 0 <= px_ < W and 0 <= py_ < H and rm[py_, px_] and math.hypot(px_ - sx, py_ - sy) > 26:
                    return False
        return True
    key = ("co", p.get("id"))
    cands = [(d, L0 * m) for m in (1.0, 1.35, 1.75, 2.3) for d in dirs if d in vec]
    if getattr(self, "_voting", False):   # prepass: ghi phiếu cho mọi vị trí còn trống ở thời điểm này
        v = self._votes.setdefault(key, (cands, [0] * len(cands)))
        for i, c in enumerate(cands):
            v[1][i] += 1 if ok(*c) else 0
        pick = next((c for c in cands if ok(*c)), (dirs[0], L0))
    elif key in self.slots:    # vị trí đã khoá → không dời theo camera
        pick = self.slots[key]
    else:
        pick = next((c for c in cands if ok(*c)), (dirs[0], L0))
        self.slots[key] = pick
    (ex, ey), bb, (cx, cy) = geom(*pick)
    # dấu neo + thân
    m = np.zeros(dst.shape[:2], np.uint8)
    hx, hy = sx + (ex - sx) * k_stem, sy + (ey - sy) * k_stem
    cv2.line(m, (int(sx * 16), int(sy * 16)), (int(hx * 16), int(hy * 16)), 255, 2, cv2.LINE_AA, 4)
    mk = p.get("marker", "diamond")
    r = 7
    if mk == "diamond":
        pts = np.array([[sx, sy - r], [sx + r, sy], [sx, sy + r], [sx - r, sy]]) * 16
        cv2.fillPoly(m, [pts.astype(np.int32)], 255, cv2.LINE_AA, 4)
    else:
        cv2.circle(m, (int(sx * 16), int(sy * 16)), r * 16, 255, -1, cv2.LINE_AA, 4)
    _tint(dst, m, col, op * (0.6 + 0.4 * k_stem))
    edge = min(bb[0] + 8, bb[1] + 8, W - bb[2] + 8, H - bb[3] + 8, sx, sy, W - sx, H - sy)
    if edge < 36:                       # callout trôi ra mép khi camera đi → mờ dần cả thân lẫn nhãn
        op *= clamp01(edge / 36.0)
        if op <= 0.01:
            return
    if k_lab <= 0:
        return
    lop = op * k_lab * float(p.get("_label_boost", 1.0))
    lift = (1 - ease("out", k_lab)) * 14
    if style == "tag":   # thẻ tối, chuyển nhẹ sang màu nhấn, viền mảnh màu nhấn
        tint = (D.rgb(col) * 0.28 + np.array([0.03, 0.04, 0.06]) * 0.72)
        top = "#%02X%02X%02X" % tuple(int(v * 255) for v in np.clip(tint, 0, 1))
        rr = {"w": bw_, "h": bh_, "r": 8, "fill": top, "fill2": "#0A0E14", "stroke": col, "stroke_w": 2, "scale": 1, "rot": 0}
        self.d_rect(dst, rr, cx, cy + lift, 1.0, 0, lop * 0.96, (0, 0), None, t, cam)
    y = cy - th / 2 + lift
    if sub:
        q = {"type": "text", "text": sub, "font": "semi", "size": size * 0.62, "color": col if style == "tag" else "#C9D3E0", "shadow": 0.4,
             "scale": 1, "rot": 0, "anchor": "top"}
        self.d_text(dst, q, cx, y, 1.0, 0, lop, (0, 0), None, t, cam)
        y += size * 0.72
    q = {"type": "text", "text": "\n".join(lines), "font": "bold", "size": size, "color": p.get("text_color", "#FFFFFF"),
         "shadow": 0.55 if style == "plain" else 0, "scale": 1, "rot": 0, "anchor": "top", "line_h": 1.12}
    self.cur_id = p.get("id")
    self.d_text(dst, q, cx, y, 1.0, 0, lop, (0, 0), None, t, cam)


# ---------------- nhân vật minh họa đổi tư thế (pictogram có khớp) ----------------
# góc độ (0 = chỉ xuống, + = xoay về phía trước/ra ngoài): vai-khuỷu trái/phải, hông-gối trái/phải, nghiêng thân
POSES = {
    "stand":      {"ua": (12, 12), "la": (0, 0), "th": (12, 12), "sh": (0, 0), "lean": 0, "crouch": 0},
    "arms_up":    {"ua": (165, 165), "la": (10, 10), "th": (12, 12), "sh": (0, 0), "lean": 0, "crouch": 0},
    "arms_side":  {"ua": (90, 90), "la": (0, 0), "th": (13, 13), "sh": (0, 0), "lean": 0, "crouch": 0},
    "arms_front": {"ua": (70, 70), "la": (25, 25), "th": (12, 12), "sh": (0, 0), "lean": 0, "crouch": 0},
    "squat":      {"ua": (80, 80), "la": (10, 10), "th": (70, 70), "sh": (-85, -85), "lean": 8, "crouch": 0.32},
    "lean_left":  {"ua": (150, 20), "la": (10, 0), "th": (8, 0), "sh": (0, 0), "lean": -14, "crouch": 0},
    "lean_right": {"ua": (20, 150), "la": (0, 10), "th": (0, 8), "sh": (0, 0), "lean": 14, "crouch": 0},
    "breathe_in": {"ua": (110, 110), "la": (30, 30), "th": (12, 12), "sh": (0, 0), "lean": 0, "crouch": 0, "chest": 1.08},
    "breathe_out": {"ua": (30, 30), "la": (60, 60), "th": (12, 12), "sh": (0, 0), "lean": 0, "crouch": 0.04, "chest": 0.96},
    "step":       {"ua": (35, -25), "la": (10, 20), "th": (25, -15), "sh": (-30, 0), "lean": 3, "crouch": 0.03},
}


def _pose_at(p, t):
    keys = sorted(p.get("poses", [{"t": 0, "pose": p.get("pose", "stand")}]), key=lambda k: k["t"])
    if p.get("cycle"):   # lặp tư thế theo chu kỳ (vd nhịp thở): cycle = {"poses": [..], "period": 4, "t0": ..., "t1": ...}
        cy = p["cycle"]
        if cy.get("t0", 0) <= t <= cy.get("t1", 1e9):
            seq = cy["poses"]; per = float(cy.get("period", 3.0))
            u = ((t - cy.get("t0", 0)) % per) / per * len(seq)
            i = int(u) % len(seq)
            return POSES[seq[i]], POSES[seq[(i + 1) % len(seq)]], ease("inout", u - int(u))
    a = keys[0]
    for b in keys[1:]:
        if t < b["t"]:
            d = float(b.get("dur", 0.6))
            k = ease("inout", (t - (b["t"] - d)) / d) if t > b["t"] - d else 0.0
            return POSES[a["pose"]], POSES[b["pose"]], k
        a = b
    return POSES[a["pose"]], POSES[a["pose"]], 0.0


def _d_figure(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """người minh họa (không phải người thật): đầu + thân + tay chân dày bo tròn; cao `h` px."""
    A, B, k = _pose_at(p, t)
    L = lambda key, i: A[key][i] + (B[key][i] - A[key][i]) * k if isinstance(A[key], tuple) else A[key] + (B[key] - A[key]) * k
    h = float(p.get("h", 420)) * scale
    u = h / 8.0
    lean = math.radians(L("lean", 0) if False else A["lean"] + (B["lean"] - A["lean"]) * k)
    crouch = A["crouch"] + (B["crouch"] - A["crouch"]) * k
    chest = A.get("chest", 1) + (B.get("chest", 1) - A.get("chest", 1)) * k
    hip = np.array([sx, sy + h / 2 - 3.9 * u - crouch * h * 0.45])
    neck = hip + np.array([math.sin(lean), -math.cos(lean)]) * 2.9 * u * chest
    head = neck + np.array([math.sin(lean), -math.cos(lean)]) * 1.05 * u

    def limb(o, a1, a2, l1, l2, side):
        a1r = math.radians(a1) * side + lean
        j = o + np.array([math.sin(a1r), math.cos(a1r)]) * l1
        a2r = a1r + math.radians(a2) * side
        e = j + np.array([math.sin(a2r), math.cos(a2r)]) * l2
        return o, j, e
    col = p.get("color", self.tl.theme["accent"])
    w = max(int(u * 0.55), 3)
    m = np.zeros(dst.shape[:2], np.uint8)
    segs = [(hip, neck)]
    for side, i in ((-1, 0), (1, 1)):
        sh_ = neck + np.array([0, 0.25 * u])
        _, j, e = limb(sh_, L("ua", i), L("la", i), 1.35 * u, 1.25 * u, side)
        segs += [(sh_, j), (j, e)]
        _, j, e = limb(hip, L("th", i), L("sh", i), 1.9 * u, 1.9 * u, side * 0.6)
        segs += [(hip, j), (j, e)]
    for a_, b_ in segs:
        cv2.line(m, tuple((a_ * 16).astype(int)), tuple((b_ * 16).astype(int)), 255, w, cv2.LINE_AA, 4)
    cv2.circle(m, tuple((head * 16).astype(int)), int(0.72 * u * 16), 255, -1, cv2.LINE_AA, 4)
    if p.get("shadow", True):
        sm = np.zeros(dst.shape[:2], np.uint8)
        cv2.ellipse(sm, (int(sx), int(sy + h / 2)), (int(2.2 * u), int(0.35 * u)), 0, 0, 360, 255, -1, cv2.LINE_AA)
        _tint(dst, cv2.GaussianBlur(sm, (0, 0), u * 0.3), "#000000", op * 0.25)
    _tint(dst, m, col, op)


# ---------------- nhịp thở: vòng giãn – thu có chu kỳ ----------------
def _d_pulse(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    per = float(p.get("period", 4.0)); t0 = float(p.get("t0", 0))
    ph = ((t - t0) % per) / per
    k = 0.5 - 0.5 * math.cos(2 * math.pi * ph)            # 0 → 1 → 0: hít vào rồi thở ra, vận tốc liên tục
    r0, r1 = float(p.get("r_min", 120)), float(p.get("r_max", 190))
    r = (r0 + (r1 - r0) * k) * scale
    col = p.get("color", self.tl.theme["accent"])
    m = np.zeros(dst.shape[:2], np.uint8)
    cv2.circle(m, (int(sx * 16), int(sy * 16)), int(r * 16), 255, -1, cv2.LINE_AA, 4)
    _tint(dst, m, col, op * float(p.get("fill_op", 0.22)))
    for j in range(int(p.get("rings", 2))):
        rr = r * (1 + 0.16 * (j + 1)) * (0.92 + 0.08 * k)
        m = np.zeros(dst.shape[:2], np.uint8)
        cv2.circle(m, (int(sx * 16), int(sy * 16)), int(rr * 16), 255, max(int(3 * scale), 1), cv2.LINE_AA, 4)
        _tint(dst, m, col, op * (0.5 - 0.15 * j) * (0.6 + 0.4 * k))
    if p.get("labels"):   # “hít vào” khi giãn, “thở ra” khi thu
        lab = p["labels"][0] if math.sin(2 * math.pi * ph) >= 0 else p["labels"][1]
        q = {"type": "text", "text": lab, "font": "bold", "size": p.get("label_size", 40), "color": p.get("label_color", "#FFFFFF"),
             "shadow": 0, "scale": 1, "rot": 0}
        self.d_text(dst, q, sx, sy, scale, 0, op, (0, 0), None, t, cam)


# ---------------- luồng khí / tia sáng đi qua khung (minh họa “thông thoáng”, “đủ sáng”) ----------------
def _d_flow(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """các đường sóng chạy theo hướng `angle` trong vùng w×h; kind = air (sóng) | light (dải sáng chéo)."""
    w, h = float(p.get("w", 600)) * scale, float(p.get("h", 300)) * scale
    ang = math.radians(float(p.get("angle", 0)))
    n = int(p.get("n", 4))
    spd = float(p.get("speed", 0.5))
    col = p.get("color", "#BFE8FF")
    m = np.zeros(dst.shape[:2], np.uint8)
    ca, sa = math.cos(ang), math.sin(ang)
    for i in range(n):
        off = (i + 0.5) / n - 0.5
        if p.get("kind", "air") == "light":
            ph = ((t * spd + i * 0.37) % 1.0)
            c = np.array([sx, sy]) + np.array([-sa, ca]) * off * h
            a_ = c - np.array([ca, sa]) * w / 2; b_ = c + np.array([ca, sa]) * w / 2
            g = int(max(h / n * 0.55, 4))
            cv2.line(m, tuple((a_ * 16).astype(int)), tuple((b_ * 16).astype(int)), int(110 + 90 * math.sin(math.pi * ph)), g, cv2.LINE_AA, 4)
        else:
            xs = np.linspace(-w / 2, w / 2, 60)
            ph = t * spd * 2 * math.pi + i * 1.3
            ys = np.sin(xs / (w / 3) * 2 * math.pi + ph) * h / n * 0.18 + off * h
            seg_len = 0.45                                       # đoạn sáng chạy dọc đường sóng
            head = ((t * spd + i * 0.29) % 1.2) - 0.1
            keep = (np.linspace(0, 1, 60) > head - seg_len) & (np.linspace(0, 1, 60) < head)
            P = np.stack([sx + xs * ca - ys * sa, sy + xs * sa + ys * ca], 1)[keep]
            if len(P) > 1:
                cv2.polylines(m, [(P * 16).astype(np.int32)], False, 255, max(int(4 * scale), 2), cv2.LINE_AA, 4)
    box = np.zeros(dst.shape[:2], np.uint8)       # chỉ hiện trong khung (cửa sổ) w×h
    cv2.rectangle(box, (int(sx - w / 2), int(sy - h / 2)), (int(sx + w / 2), int(sy + h / 2)), 255, -1)
    m = cv2.GaussianBlur(m, (0, 0), 1.2) if p.get("kind") == "light" else m
    m = (m.astype(np.uint16) * box // 255).astype(np.uint8)
    _tint(dst, m, col, op * float(p.get("alpha", 0.8)))


# ---------------- khối cộng dồn (thành phần thêm vào tổng thể, KHÔNG số liệu) ----------------
def _d_stack(self, dst, p, sx, sy, scale, rot, op, bv, clip, t, cam):
    """các khối xếp chồng từ đáy: mỗi item {text, t, color}; chiều cao bằng nhau → không gợi tỷ lệ định lượng."""
    th = self.tl.theme
    w, bh = float(p.get("w", 520)), float(p.get("item_h", 96))
    gap = float(p.get("gap", 10))
    items = p.get("items", [])
    base_y = sy + (len(items) * (bh + gap)) * scale / 2
    for i, it in enumerate(items):
        k = ease("out", (t - float(it.get("t", 0))) / 0.4)
        if k <= 0:
            continue
        y = base_y - (i + 0.5) * (bh + gap) * scale - (1 - k) * 160 * scale
        r = {"id": f"{p.get('id')}_{i}", "w": w, "h": bh, "r": 18, "fill": it.get("color", th["accent"]), "scale": 1, "rot": 0}
        self.d_rect(dst, r, sx, y, scale, 0, op * clamp01(k * 1.5), bv, None, t, cam)
        q = {"type": "text", "text": it["text"], "font": "bold", "size": p.get("size", 40), "color": it.get("text_color", "#111111"),
             "shadow": 0, "scale": 1, "rot": 0, "max_w": w - 40}
        self.cur_id = p.get("id")
        self.d_text(dst, q, sx, y, scale, 0, op * clamp01(k * 1.5), bv, None, t, cam)


Renderer.d_routelabel = _d_routelabel
Renderer.d_callout = _d_callout
Renderer.d_figure = _d_figure
Renderer.d_pulse = _d_pulse
Renderer.d_flow = _d_flow
Renderer.d_stack = _d_stack
