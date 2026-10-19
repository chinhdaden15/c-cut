"""Job (spec đã chuẩn hoá) → dự án HyperFrames: index.html (GSAP cục bộ, font app) + assets/ + index.motion.json.

Chỉ dùng hợp đồng đã kiểm trên bản ghim: gốc data-composition-id + class="clip" + data-start/data-duration,
<video>/<audio> với data-media-start / data-volume / muted|data-has-audio, timeline GSAP đăng ký ở window.__timelines["main"].
Thứ tự vẽ = z-index (track chỉ để xem trong Studio).
"""
from __future__ import annotations

import html
import json
import os
import re
import shutil
from pathlib import Path

from ..paths import ROOT

VERSION = "3"        # TĂNG khi đổi cách dựng HTML → mã băm job đổi → clip cũ tự hết hạn (không dùng lại kết quả sai)
FONT_DIR = ROOT / "assets" / "fonts"
DEFAULT_FONTS = [
    {"family": "Montserrat", "file": str(FONT_DIR / "Montserrat-VF.ttf"), "weight": "100 900"},
    {"family": "Be Vietnam Pro", "file": str(FONT_DIR / "BeVietnamPro-Regular.ttf"), "weight": "400"},
    {"family": "Be Vietnam Pro", "file": str(FONT_DIR / "BeVietnamPro-Medium.ttf"), "weight": "500"},
    {"family": "Be Vietnam Pro", "file": str(FONT_DIR / "BeVietnamPro-Bold.ttf"), "weight": "700"},
    {"family": "Be Vietnam Pro", "file": str(FONT_DIR / "BeVietnamPro-ExtraBold.ttf"), "weight": "800"},
]
ROLE = {"black": ("Montserrat", 900), "display": ("Montserrat", 800), "bold": ("Montserrat", 700), "semi": ("Montserrat", 600),
        "medium": ("Montserrat", 500), "light": ("Montserrat", 400), "body": ("Be Vietnam Pro", 500), "body_bold": ("Be Vietnam Pro", 700)}
ANCHOR = {"center": (-50, -50), "top-left": (0, 0), "top": (-50, 0), "top-right": (-100, 0), "left": (0, -50), "right": (-100, -50),
          "bottom-left": (0, -100), "bottom": (-50, -100), "bottom-right": (-100, -100)}


def _px(v, total):
    if isinstance(v, str) and v.endswith("%"):
        return float(v[:-1]) / 100 * total
    return float(v)


def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _css(d: dict) -> str:
    return ";".join(f"{k}:{v}" for k, v in (d or {}).items())


def _font(role: str) -> str:
    fam, w = ROLE.get(role, ROLE["bold"])
    return f"font-family:'{fam}';font-weight:{w}"


def _asset(proj: Path, src: str) -> str:
    p = Path(src)
    import hashlib
    dst = proj / "assets" / "media" / f"{hashlib.md5(str(p).encode('utf-8')).hexdigest()[:10]}_{p.name}"     # tên ổn định giữa các lần chạy
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(p, dst)                       # cùng ổ đĩa: không tốn dung lượng
        except OSError:
            shutil.copy2(p, dst)
    return dst.relative_to(proj).as_posix()


class _B:
    def __init__(self, s: dict, proj: Path):
        self.s, self.proj = s, proj
        self.W, self.H = int(s["width"]), int(s["height"])
        self.body, self.css, self.js, self.motion = [], [], [], []

    # ---------- chung ----------
    def place(self, L) -> str:
        x, y = _px(L.get("x", "50%"), self.W), _px(L.get("y", "50%"), self.H)
        st = {"position": "absolute", "left": f"{x:.1f}px", "top": f"{y:.1f}px"}
        if L.get("w") is not None:
            st["width"] = f"{_px(L['w'], self.W):.1f}px"
        if L.get("h") is not None:
            st["height"] = f"{_px(L['h'], self.H):.1f}px"
        return _css(st)

    def anim(self, L, sel: str, S: float, E: float):
        ax, ay = ANCHOR.get(L.get("anchor", "center"), (-50, -50))
        op = float(L.get("opacity", 1))
        self.js.append(f'gsap.set("{sel}",{{xPercent:{ax},yPercent:{ay},opacity:0}});')
        en = {"type": "fade", "dur": 0.35, "ease": "power2.out", **(L.get("enter") or {})}
        d, ease = float(en["dur"]), en.get("ease", "power2.out")
        fr = {"fade": "{opacity:0}", "up": "{opacity:0,y:40}", "down": "{opacity:0,y:-40}", "left": "{opacity:0,x:-60}",
              "right": "{opacity:0,x:60}", "pop": "{opacity:0,scale:0.6}", "wipe": '{opacity:1,clipPath:"inset(0% 100% 0% 0%)"}',
              "none": None}[en["type"]]
        if fr is None or d <= 0:
            self.js.append(f'tl.set("{sel}",{{opacity:{op}}},{S:.3f});')
        else:
            to = {"fade": f"opacity:{op}", "up": f"opacity:{op},y:0", "down": f"opacity:{op},y:0", "left": f"opacity:{op},x:0",
                  "right": f"opacity:{op},x:0", "pop": f"opacity:{op},scale:1", "wipe": f'opacity:{op},clipPath:"inset(0% 0% 0% 0%)"'}[en["type"]]
            if en["type"] == "pop":
                ease = en.get("ease", "back.out(1.7)")
            self.js.append(f'tl.fromTo("{sel}",{fr},{{{to},duration:{d:.3f},ease:"{ease}"}},{S:.3f});')
            self.motion.append({"kind": "appearsBy", "selector": sel, "bySec": round(S + d + 0.2, 3)})
        ex = L.get("exit")
        if ex is None:
            ex = {"type": "fade", "dur": 0.2}
        if ex.get("type", "fade") != "none" and float(ex.get("dur", 0.2)) > 0:
            d2 = min(float(ex.get("dur", 0.2)), max(E - S - d, 0.05))
            extra = {"up": ",y:-30", "down": ",y:30", "left": ",x:-40", "right": ",x:40", "pop": ",scale:0.8"}.get(ex.get("type", "fade"), "")
            self.js.append(f'tl.to("{sel}",{{opacity:0{extra},duration:{d2:.3f},ease:"power1.in"}},{E - d2:.3f});')
        kfs = sorted(L.get("keyframes") or [], key=lambda k: float(k["t"]))
        self.keyframes(sel, kfs, S, origin={k: L.get(k) for k in ("x", "y", "w", "h") if L.get(k) is not None} or None)

    def keyframes(self, sel: str, kfs: list, S: float, box_keys=("x", "y", "w", "h"), origin: dict | None = None):
        """vị trí/kích thước THẬT theo thời gian → transform (x/y/scaleX/scaleY) tính từ mốc đầu (mượt dưới pixel khi render
        từng khung — left/top bị lint chặn vì giật)."""
        if not kfs:
            return
        k0 = kfs[0]
        o = origin or k0                      # gốc = vị trí đã đặt của lớp (transform tính lệch so với nó)
        x0, y0 = _px(o.get("x", k0.get("x", 0)), self.W), _px(o.get("y", k0.get("y", 0)), self.H)
        w0, h0 = _px(o.get("w") or k0.get("w", 1), self.W), _px(o.get("h") or k0.get("h", 1), self.H)

        def props(k):
            p = []
            if "x" in k and "x" in box_keys:
                p.append(f"x:{_px(k['x'], self.W) - x0:.2f}")
            if "y" in k and "y" in box_keys:
                p.append(f"y:{_px(k['y'], self.H) - y0:.2f}")
            if "w" in k and "w" in box_keys and w0 > 0:
                p.append(f"scaleX:{_px(k['w'], self.W) / w0:.4f}")
            if "h" in k and "h" in box_keys and h0 > 0:
                p.append(f"scaleY:{_px(k['h'], self.H) / h0:.4f}")
            if "opacity" in k:
                p.append(f"opacity:{float(k['opacity'])}")
            if "scale" in k:
                p.append(f"scale:{float(k['scale'])}")
            return ",".join(p)
        if "w" in box_keys or "h" in box_keys:
            self.js.append(f'gsap.set("{sel}",{{transformOrigin:"0% 0%"}});')
        self.js.append(f'tl.set("{sel}",{{{props(k0)}}},{S + float(k0["t"]):.3f});')
        for a, b in zip(kfs, kfs[1:]):
            dt = float(b["t"]) - float(a["t"])
            if dt <= 0:
                continue
            self.js.append(f'tl.to("{sel}",{{{props(b)},duration:{dt:.3f},ease:"none"}},{S + float(a["t"]):.3f});')

    def clip(self, L, S, E, inner: str, inner_style: str = ""):
        lid = re.sub(r"[^A-Za-z0-9_-]", "_", L["id"])
        self.body.append(f'<div id="c_{lid}" class="clip" data-start="{S:.3f}" data-duration="{E - S:.3f}" data-track-index="{int(L.get("z", 1))}"'
                         f' data-layer-id="{_e(L["id"])}" style="position:absolute;inset:0;z-index:{int(L.get("z", 1))};pointer-events:none">'
                         f'<div id="{lid}" class="el {L["type"]}" style="{self.place(L)};{inner_style};{_css(L.get("style"))}">{inner}</div></div>')
        return f"#{lid}", lid

    # ---------- loại lớp ----------
    def text(self, L, S, E):
        words = str(L["text"]).split()
        hl = {}
        for h in L.get("highlight") or []:
            for w in str(h["match"]).lower().split():
                hl[w] = h.get("color", "#FFD34D")
        spans, i = [], 0
        for li, line in enumerate(str(L["text"]).split("\n")):     # giữ xuống dòng của nội dung (thẻ 2 dòng: tiêu đề nhỏ + nội dung)
            if li:
                spans.append("<br>")
            for w in line.split():
                key = re.sub(r"[.,!?:;“”\"]", "", w.lower())
                col = f"color:{hl[key]};" if key in hl else ""
                spans.append(f'<span class="w w{i}" style="{col}">{_e(w)}</span>')
                i += 1
        inner = " ".join(spans).replace(" <br> ", "<br>")
        size = float(L.get("size", 72))
        st = {"font-size": f"{size}px", "color": L.get("color", "#FFFFFF"), "text-align": L.get("align", "center"),
              "line-height": str(L.get("line_h", 1.15)), "white-space": "normal"}
        if L.get("max_w"):
            st["width"] = f"{_px(L['max_w'], self.W):.0f}px"
        else:
            st["white-space"] = "nowrap"
        if L.get("stroke", 0):
            st["-webkit-text-stroke"] = f"{float(L['stroke'])}px {L.get('stroke_color', '#000')}"
            st["paint-order"] = "stroke fill"
        if L.get("shadow", 0.5):
            st["text-shadow"] = f"0 {size * 0.05:.0f}px {size * 0.18:.0f}px rgba(0,0,0,{float(L.get('shadow', 0.5)):.2f})"
        if L.get("bg"):
            st.update({"background": L["bg"], "padding": f"{float(L.get('pad', size * 0.3)):.0f}px {float(L.get('pad', size * 0.3)) * 1.4:.0f}px",
                       "border-radius": f"{float(L.get('radius', size * 0.35)):.0f}px"})
        sel, lid = self.clip(L, S, E, inner, _font(L.get("font", "bold")) + ";" + _css(st))
        self.anim(L, sel, S, E)
        if L.get("reveal") == "words":
            times = L.get("word_times") or [i * 0.25 for i in range(len(words))]
            act = L.get("active_color")
            for i, t in enumerate(times):
                ws = f"{sel} .w{i}"
                self.js.append(f'gsap.set("{ws}",{{opacity:0}});tl.to("{ws}",{{opacity:1,duration:0.08}},{S + float(t):.3f});')
                if act:
                    t2 = times[i + 1] if i + 1 < len(times) else float(L["duration"])
                    base = hl.get(re.sub(r"[.,!?:;“”\"]", "", words[i].lower()), L.get("color", "#FFFFFF"))
                    self.js.append(f'tl.set("{ws}",{{color:"{act}"}},{S + float(t):.3f});tl.set("{ws}",{{color:"{base}"}},{S + float(t2):.3f});')
        if L.get("stay_in_frame", True):
            self.motion.append({"kind": "staysInFrame", "selector": sel})

    def image(self, L, S, E):
        src = _asset(self.proj, L["src"])
        st = f'width:100%;height:100%;object-fit:{L.get("fit", "cover")};border-radius:{float(L.get("radius", 0)):.0f}px;' \
             + (f'border:{L["border"]};' if L.get("border") else "")
        sel, _ = self.clip(L, S, E, f'<img src="{_e(src)}" style="{st}">', "overflow:hidden")
        self.anim(L, sel, S, E)

    def video(self, L, S, E):
        src = _asset(self.proj, L["src"])
        lid = re.sub(r"[^A-Za-z0-9_-]", "_", L["id"])
        aud = 'data-has-audio="true"' if L.get("muted") is False else "muted"
        self.body.append(f'<video id="{lid}" class="clip" src="{_e(src)}" data-start="{S:.3f}" data-duration="{E - S:.3f}" '
                         f'data-media-start="{float(L.get("in", 0)):.3f}" data-track-index="{int(L.get("z", 1))}" {aud} playsinline '
                         f'style="{self.place(L)};z-index:{int(L.get("z", 1))};object-fit:{L.get("fit", "cover")};'
                         f'border-radius:{float(L.get("radius", 0)):.0f}px;{_css(L.get("style"))}"></video>')
        self.anim(L, f"#{lid}", S, E)

    def shape(self, L, S, E):
        sh = L.get("shape", "rect")
        st = {"background": L.get("fill", "transparent"), "border-radius": "50%" if sh == "circle" else f"{float(L.get('radius', 0)):.0f}px"}
        if L.get("stroke"):
            st["border"] = f"{float(L.get('stroke_w', 4)):.0f}px solid {L['stroke']}"
        if sh == "line":
            st = {"background": L.get("stroke", L.get("fill", "#fff")), "height": f"{float(L.get('stroke_w', 4)):.0f}px"}
        sel, _ = self.clip(L, S, E, "", _css(st))
        self.anim(L, sel, S, E)

    def callout(self, L, S, E):
        side = L.get("side", "right")
        gap = float(L.get("gap", 120))
        size = float(L.get("size", 44))
        tgt0 = L.get("target_track") or [L["target"]]
        lw = len(str(L["text"])) * size * 0.62 + size * 1.2          # ước bề rộng nhãn
        m = 0.05 * self.W
        xs = [_px(p["x"], self.W) for p in tgt0]
        if side == "right" and max(xs) + gap + lw > self.W - m and min(xs) - gap - lw >= m:
            side = "left"                                           # nhãn sẽ ra ngoài khung trong lúc bám → đổi phía
        elif side == "left" and min(xs) - gap - lw < m and max(xs) + gap + lw <= self.W - m:
            side = "right"
        if side in ("left", "right") and (max(xs) + gap + lw > self.W - m if side == "right" else min(xs) - gap - lw < m):
            ys = [_px(p["y"], self.H) for p in tgt0]       # hai bên đều không đủ chỗ → nhãn trên/dưới điểm bám
            side = "top" if min(ys) - gap - size * 2 > 0.1 * self.H else "bottom"
        col = L.get("color", "#FFFFFF")
        acc = L.get("accent", "#FFD34D")
        tgt = L.get("target_track") or [{"t": 0, **L["target"]}]
        L2 = dict(L, x=tgt[0]["x"], y=tgt[0]["y"], anchor="top-left", keyframes=None, enter={"type": "none", "dur": 0})
        dx, dy = {"right": (gap, -gap * 0.55), "left": (-gap, -gap * 0.55), "top": (0, -gap), "bottom": (0, gap)}[side]
        ln = (dx ** 2 + dy ** 2) ** 0.5
        import math
        ang = math.degrees(math.atan2(dy, dx))
        lab_anchor = {"right": "translate(0,-50%)", "left": "translate(-100%,-50%)", "top": "translate(-50%,-100%)",
                      "bottom": "translate(-50%,0)"}[side]
        inner = (f'<div class="dot" style="position:absolute;left:-9px;top:-9px;width:18px;height:18px;border-radius:50%;background:{acc};'
                 f'box-shadow:0 0 0 5px rgba(0,0,0,.35)"></div>'
                 f'<div class="ln" style="position:absolute;left:0;top:-2px;width:{ln:.0f}px;height:4px;background:{acc};transform-origin:0 50%;'
                 f'transform:rotate({ang:.1f}deg)"></div>'
                 f'<div class="lab" style="position:absolute;left:{dx:.0f}px;top:{dy:.0f}px;transform:{lab_anchor};white-space:nowrap;'
                 f'{_font(L.get("font", "bold"))};font-size:{size}px;color:{col};background:{L.get("bg", "rgba(12,14,18,.82)")};'
                 f'padding:{size * 0.28:.0f}px {size * 0.45:.0f}px;border-radius:{size * 0.3:.0f}px;border-left:6px solid {acc}">'
                 f'{_e(L["text"])}</div>')
        sel, lid = self.clip(L2, S, E, inner, "width:0;height:0")
        self.js.append(f'gsap.set("{sel}",{{opacity:1}});')
        en = float((L.get("enter") or {}).get("dur", 0.45))
        self.js.append(f'tl.fromTo("{sel} .dot",{{scale:0}},{{scale:1,duration:{en * 0.4:.3f},ease:"back.out(2)"}},{S:.3f});')
        self.js.append(f'tl.fromTo("{sel} .ln",{{scaleX:0}},{{scaleX:1,duration:{en * 0.5:.3f},ease:"power2.out"}},{S + en * 0.25:.3f});')
        self.js.append(f'tl.fromTo("{sel} .lab",{{opacity:0}},{{opacity:1,duration:{en * 0.5:.3f}}},{S + en * 0.5:.3f});')
        self.js.append(f'tl.to("{sel}",{{opacity:0,duration:0.2}},{E - 0.2:.3f});')
        self.motion.append({"kind": "appearsBy", "selector": f"{sel} .lab", "bySec": round(S + en + 0.2, 3)})
        self.motion.append({"kind": "staysInFrame", "selector": f"{sel} .lab"})
        if len(tgt) > 1:
            self.keyframes(sel, [{"t": p["t"], "x": p["x"], "y": p["y"]} for p in tgt], S, box_keys=("x", "y"))

    def spotlight(self, L, S, E):
        tr = sorted(L.get("track") or [], key=lambda p: float(p["t"]))
        if not tr:                                     # chỉ khi validate cho phép (static_reason) — khung cố định có lý do
            tr = [{"t": 0, **L["box"]}]
        pad = float(L.get("pad", 18))
        dim = float(L.get("dim", 0.32))
        fe = float(L.get("feather", 22))
        r = float(L.get("radius", 36))
        p0 = tr[0]
        L2 = dict(L, x=_px(p0["x"], self.W) - pad, y=_px(p0["y"], self.H) - pad, w=_px(p0["w"], self.W) + 2 * pad,
                  h=_px(p0["h"], self.H) + 2 * pad, anchor="top-left", keyframes=None)
        st = f"border-radius:{r:.0f}px;box-shadow:0 0 0 4000px rgba(0,0,0,{dim:.2f});filter:blur({fe / 2:.1f}px)"
        fc = L.get("frame", True)
        fcol = fc if isinstance(fc, str) else "rgba(255,255,255,.85)"     # frame: true/false hoặc mã màu
        ring = "1" if fc else ""
        sel, lid = self.clip(L2, S, E, "", st)
        if ring:
            self.body[-1] = self.body[-1].replace(f'<div id="{lid}"', f'<div id="{lid}_ring" class="el ring" style="{self.place(L2)};'
                                                  f'border-radius:{r:.0f}px;border:{float(L.get("frame_w", 3)):.0f}px solid '
                                                  f'{fcol}"></div><div id="{lid}"', 1)
        fd = float((L.get("enter") or {}).get("dur", 0.24))
        for s_ in (sel, f"{sel}_ring") if ring else (sel,):
            self.js.append(f'gsap.set("{s_}",{{opacity:0}});tl.to("{s_}",{{opacity:1,duration:{fd:.3f}}},{S:.3f});'
                           f'tl.to("{s_}",{{opacity:0,duration:{fd:.3f}}},{E - fd:.3f});')
            self.keyframes(s_, [{"t": p["t"], "x": _px(p["x"], self.W) - pad, "y": _px(p["y"], self.H) - pad,
                                 "w": _px(p["w"], self.W) + 2 * pad, "h": _px(p["h"], self.H) + 2 * pad} for p in tr], S)

    def bars(self, L, S, E):
        items = L["items"]
        mx = float(L.get("max") or max(float(i["value"]) for i in items) * 1.1)
        w, h = _px(L.get("w", self.W * 0.8), self.W), _px(L.get("h", self.H * 0.35), self.H)
        bw = w / len(items) * 0.6
        col, lc = L.get("color", "#FFD34D"), L.get("label_color", "#FFFFFF")
        fs = float(L.get("size", 40))
        cells = []
        for i, it in enumerate(items):
            bh = h * float(it["value"]) / mx
            cells.append(f'<div class="cell" style="position:absolute;left:{(i + 0.5) * w / len(items) - bw / 2:.0f}px;bottom:0;width:{bw:.0f}px;height:{h:.0f}px">'
                         f'<div class="bar b{i}" style="position:absolute;left:0;bottom:{fs * 1.6:.0f}px;width:100%;height:{bh * (1 - fs * 1.6 / h):.0f}px;'
                         f'background:{it.get("color", col)};border-radius:{bw * 0.12:.0f}px {bw * 0.12:.0f}px 0 0;transform-origin:50% 100%"></div>'
                         f'<div class="val v{i}" style="position:absolute;left:50%;bottom:{fs * 1.7 + bh * (1 - fs * 1.6 / h):.0f}px;transform:translateX(-50%);'
                         f'{_font("black")};font-size:{fs * 1.1:.0f}px;color:{lc};white-space:nowrap">{_e(it.get("display", str(it["value"]) + L.get("unit", "")))}</div>'
                         f'<div style="position:absolute;left:50%;bottom:0;transform:translateX(-50%);{_font("bold")};font-size:{fs:.0f}px;'
                         f'color:{lc};white-space:nowrap">{_e(it["label"])}</div></div>')
        L2 = dict(L, w=w, h=h)
        sel, _ = self.clip(L2, S, E, "".join(cells))
        self.anim(L2, sel, S, E)
        for i in range(len(items)):
            self.js.append(f'tl.fromTo("{sel} .b{i}",{{scaleY:0}},{{scaleY:1,duration:0.6,ease:"power3.out"}},{S + 0.2 + i * 0.12:.3f});'
                           f'tl.fromTo("{sel} .v{i}",{{opacity:0}},{{opacity:1,duration:0.25}},{S + 0.6 + i * 0.12:.3f});')

    def table(self, L, S, E):
        fs = float(L.get("size", 44))
        acc = L.get("accent", "#FFD34D")
        cols, rows, win = L.get("cols", ["", ""]), L["rows"], L.get("win", [])
        cell = f"padding:{fs * 0.32:.0f}px {fs * 0.5:.0f}px;white-space:nowrap"
        h = [f'<div style="{cell}"></div>'] + [f'<div style="{cell};{_font("black")};color:{acc if k == 0 else "#fff"};text-align:center">{_e(c)}</div>'
                                              for k, c in enumerate(cols[:2])]
        body = []
        for i, r in enumerate(rows):
            w_ = win[i] if i < len(win) else 0
            body.append(f'<div class="row r{i}" style="display:contents">'
                        f'<div style="{cell};color:#C9D1DD;{_font("bold")}">{_e(r[0])}</div>'
                        + "".join(f'<div style="{cell};text-align:center;{_font("black" if w_ == k + 1 else "bold")};'
                                  f'color:{acc if w_ == k + 1 else "#fff"}">{_e(v)}</div>' for k, v in enumerate(r[1:3])) + "</div>")
        title = (f'<div style="grid-column:1/4;text-align:center;color:#A9B4C8;{_font("bold")};padding-bottom:{fs * 0.2:.0f}px">'
                 f'{_e(L["title"])}</div>') if L.get("title") else ""
        inner = (f'<div style="display:grid;grid-template-columns:auto auto auto;font-size:{fs:.0f}px;background:{L.get("bg", "rgba(14,17,22,.86)")};'
                 f'border-radius:{fs * 0.5:.0f}px;padding:{fs * 0.5:.0f}px">{title}{"".join(h)}{"".join(body)}</div>')
        sel, _ = self.clip(L, S, E, inner)
        self.anim(dict(L, enter=L.get("enter") or {"type": "pop", "dur": 0.4}), sel, S, E)
        self.motion.append({"kind": "staysInFrame", "selector": sel})

    def html_(self, L, S, E):
        sel, lid = self.clip(L, S, E, L.get("html", ""))
        if L.get("css"):
            self.css.append(L["css"])
        self.anim(dict(L, enter=L.get("enter") or {"type": "none", "dur": 0}), sel, S, E)
        if L.get("js"):
            self.js.append(f'(function(sel,S,D){{{L["js"]}}})("{sel}",{S:.3f},{E - S:.3f});')


def build(s: dict, proj: Path) -> Path:
    """viết dự án HyperFrames vào proj/ (ghi đè index.html). Trả về đường dẫn index.html."""
    from .runtime import gsap_js
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "assets").mkdir(exist_ok=True)
    shutil.copy2(gsap_js(), proj / "assets" / "gsap.min.js")
    b = _B(s, proj)
    faces = []
    for f in s.get("fonts") or DEFAULT_FONTS:
        p = Path(f["file"])
        dst = proj / "assets" / "fonts" / p.name
        dst.parent.mkdir(exist_ok=True)
        if not dst.exists():
            shutil.copy2(p, dst)
        faces.append(f"@font-face{{font-family:'{f['family']}';src:url('assets/fonts/{p.name}');font-weight:{f.get('weight', '400')};font-display:block}}")
    for c in s["scenes"]:
        cs = float(c["start"])
        for L in c.get("layers", []):
            S = cs + float(L["start"])
            E = S + float(L["duration"])
            getattr(b, "html_" if L["type"] == "html" else L["type"])(L, S, E)
    for i, a in enumerate(s.get("audio", [])):
        src = _asset(proj, a["src"])
        st = float(a.get("start", 0))
        dur = float(a.get("duration", float(s["duration"]) - st))
        b.body.append(f'<audio id="aud{i}" src="{_e(src)}" data-start="{st:.3f}" data-duration="{dur:.3f}" '
                      f'data-media-start="{float(a.get("in", 0)):.3f}" data-volume="{float(a.get("volume", 1))}" data-track-index="90"></audio>')
    bg = "transparent" if s["background"] == "transparent" else s["background"]
    W, H, T = b.W, b.H, float(s["duration"])
    doc = f"""<!doctype html>
<html lang="vi">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width={W}, height={H}">
<!-- job {_e(s['job_id'])} · dựng bởi thagent.hyper (C-Cut) -->
<script src="assets/gsap.min.js"></script>
<style>
{chr(10).join(faces)}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:{bg}}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;isolation:isolate;font-family:'Montserrat'}}
{chr(10).join(b.css)}
</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{T:.3f}" data-width="{W}" data-height="{H}" data-fps="{int(s['fps'])}">
{chr(10).join(b.body)}
</div>
<script>
const tl = gsap.timeline({{paused: true}});
{chr(10).join(b.js)}
tl.set({{}}, {{}}, {T:.3f});
window.__timelines["main"] = tl;
tl.seek(0);
</script>
</body>
</html>
"""
    idx = proj / "index.html"
    idx.write_text(doc, encoding="utf-8")
    mj = proj / "index.motion.json"
    if b.motion:
        mj.write_text(json.dumps({"duration": T, "assertions": b.motion}, ensure_ascii=False, indent=1), encoding="utf-8")
    else:
        mj.unlink(missing_ok=True)            # không có điều kiện chuyển động → không ghi (spec rỗng bị coi là sai)
    (proj / "job.spec.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    return idx
