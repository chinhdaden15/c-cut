"""Cảnh hoạt hình MINH HOẠ ĐÚNG LỜI (HyperFrames + GSAP), toàn khung, có nền riêng: dùng chung cho Text to Video / Voice to Motion
(`s.mg("<kind>", t0, t1, ...)`) và Talking Head (plan.mg2). Không phải icon đặt cho có: mỗi mẫu là một màn diễn hoạt thật.

  mapdraw   vẽ bản đồ (viền tự vẽ + phát sáng → tô màu → ghim thành phố rơi xuống + vòng sóng → tuyến cong nối các điểm, chấm chạy)
            countries ["VNM"] (mã ISO3), pins [{name, lonlat?, at}], routes [[i, j, at]], title, sub, tone
            Việt Nam: tự vẽ kèm QĐ. Hoàng Sa, QĐ. Trường Sa. Tên thành phố VN phổ biến tự tra toạ độ (Hà Nội, TP.HCM, Đà Nẵng…)
  tech      công nghệ / AI / phần mềm: chip trung tâm (logo/icon/chữ) + vòng quay + mạch điện tự vẽ toả ra, xung sáng chạy trên mạch,
            sàn lưới phối cảnh, thẻ HUD bật ra theo lời. center (icon "3d:…" | ảnh logo | chữ), title, items [text…] (≤4), at
  prompt    "gõ vài dòng lệnh → ra video": cửa sổ app gõ chữ từng ký tự + con trỏ → bấm nút → thanh tiến trình % → thẻ video bay ra.
            app (tên), logo (ảnh), text (lệnh gõ), button, outputs ["9:16","16:9"], image (ảnh thumbnail), at [gõ, bấm, xong]
  devices   đăng mạng xã hội / dọc + ngang: điện thoại (tim bay, số view chạy) + laptop màn ngang chạy video.
            image, labels ["TikTok","YouTube"], views (số), at [điện thoại, laptop]
  pipeline  A → máy xử lý → B, hạt sáng chảy theo đường nối: input {icon|wave:true, label}, engine {icon|logo, label},
            output {icon|image, label}, at [vào, xử lý, ra]
  kinetic   chữ động toàn khung (kinetic typography): lines [{text, at, hl}] — từng cụm đập vào theo lời, cụm cũ đẩy lên,
            từ nhấn có khối màu quét nền, chữ nền khổng lồ trôi. Dùng cho câu khẳng định / lợi ích / hook.
Mốc "at" = GIÂY tính từ đầu cảnh (kit tự đổi từ giây voice). Màu: tone gold|blue|red.
"""
from __future__ import annotations

import json
import math
import random
import unicodedata
from functools import lru_cache

from .paths import ROOT

FULL = {"mapdraw", "tech", "prompt", "devices", "pipeline", "kinetic"}
ACC = {"gold": ("#FFB000", "#FFE47A", "#FF7A00"), "blue": ("#2EA8FF", "#A6EEFF", "#2E5BFF"), "red": ("#FF2B4A", "#FF9A86", "#FF6B00")}


def _E(s):
    import html
    return html.escape(str(s or ""))


def _px(v):
    return f"calc({round(v, 2)}px*var(--s))"


def _ws(sc):
    return float(sc.get("_W", 1080)), float(sc.get("_H", 1920))


def _at(sc, i, default):
    at = sc.get("at") or []
    return round(float(at[i]), 3) if i < len(at) else default


@lru_cache(maxsize=128)
def _glyph(name: str, tone: str = "gold", size: int = 320) -> str:
    """icon nét đặc hiện đại (Flaticon Uicons solid-rounded) tô gradient trắng → màu nhấn, nền trong suốt → data URI PNG."""
    import base64, io
    import numpy as np
    from PIL import Image
    from .neon import _uicon_mask
    m = _uicon_mask(name, size)
    if m is None:
        return ""
    h, w = m.shape
    a = ACC.get(tone, ACC["gold"])
    hexrgb = lambda c: np.array([int(c[i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    top, mid, bot = np.array([255, 255, 255], np.float32), hexrgb(a[1]), hexrgb(a[0])
    y = np.linspace(0, 1, h)[:, None, None]
    col = np.where(y < 0.5, top + (mid - top) * (y / 0.5), mid + (bot - mid) * ((y - 0.5) / 0.5))
    rgba = np.dstack([np.broadcast_to(col, (h, w, 3)), m[..., None] * 255]).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _icon(name, tone="gold"):
    from .mg2 import icon_uri, _uri
    from pathlib import Path
    if not name:
        return ""
    if str(name).startswith("ui:"):
        return _glyph(str(name)[3:], tone)
    p = Path(str(name))
    if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and p.exists():
        return _uri(str(p))                         # logo/ảnh thật giữ nguyên (không đổi glow)
    return icon_uri(name)


def _img(src):
    from .mg2 import _uri
    from pathlib import Path
    return _uri(src) if src and Path(src).exists() else ""


def _fit(text, size, width_px, k=0.66):
    n = max(1, max((len(x) for x in str(text or "").split("\n")), default=1))
    return min(size, width_px / (n * k))


def _bg(tone, kind="tech"):
    a = ACC[tone]
    return f"""<div class=fxbg style="position:absolute;inset:-3%;background:radial-gradient(60% 40% at 50% 42%,{a[0]}33 0%,transparent 70%),
radial-gradient(130% 90% at 50% 50%,#0B1022 35%,#03050C 100%)"></div>
<div class=fxgrid style="position:absolute;inset:0;opacity:.35;background-image:linear-gradient(rgba(120,170,255,.10) 1px,transparent 1px),
linear-gradient(90deg,rgba(120,170,255,.10) 1px,transparent 1px);background-size:{_px(60)} {_px(60)};
-webkit-mask-image:radial-gradient(70% 55% at 50% 45%,#000 30%,transparent 80%)"></div>"""


CSS = """
.fxroot{position:absolute;inset:0;overflow:hidden;font-family:Montserrat,sans-serif;color:#fff}
.glow{filter:drop-shadow(0 0 calc(10px*var(--s)) var(--a)) drop-shadow(0 0 calc(26px*var(--s)) var(--a))}
.lbl{position:absolute;white-space:nowrap;font-weight:800;padding:calc(10px*var(--s)) calc(24px*var(--s));border-radius:999px;
 background:rgba(8,12,26,.72);border:2px solid var(--a);box-shadow:0 0 calc(22px*var(--s)) var(--a)}
.hud{position:absolute;font-family:Menlo,monospace;font-weight:600;color:rgba(170,210,255,.55);letter-spacing:.08em}
.big{font-weight:900;letter-spacing:-.01em;line-height:1.02;text-align:center}
.grad{background:linear-gradient(180deg,#fff 0%,var(--a2) 55%,var(--a) 100%);-webkit-background-clip:text;color:transparent;
 filter:drop-shadow(0 0 calc(20px*var(--s)) var(--a))}
"""


def _wrap(sc, inner, tone):
    a = ACC[tone]
    return (f'<style>{CSS}</style><div class=fxroot style="--a:{a[0]};--a2:{a[1]};--a3:{a[2]}">'
            + _bg(tone) + inner + "</div>")


# ------------------------------------------------------------------ mapdraw
VN_CITIES = {"ha noi": (105.85, 21.03), "hanoi": (105.85, 21.03), "tp hcm": (106.70, 10.78), "tphcm": (106.70, 10.78),
             "ho chi minh": (106.70, 10.78), "sai gon": (106.70, 10.78), "da nang": (108.22, 16.05), "hai phong": (106.68, 20.86),
             "can tho": (105.78, 10.03), "nha trang": (109.19, 12.24), "hue": (107.58, 16.46), "da lat": (108.44, 11.94),
             "vung tau": (107.08, 10.35), "phu quoc": (103.96, 10.22), "quy nhon": (109.22, 13.78), "ha long": (107.08, 20.95),
             "vinh": (105.68, 18.67), "buon ma thuot": (108.05, 12.67), "bien hoa": (106.82, 10.95), "sa pa": (103.84, 22.34),
             "hoi an": (108.33, 15.88), "thanh hoa": (105.78, 19.81), "nam dinh": (106.17, 20.42), "phan thiet": (108.10, 10.93),
             "ca mau": (105.15, 9.18), "pleiku": (108.00, 13.98), "long xuyen": (105.43, 10.38), "binh duong": (106.65, 11.0)}


def _norm(s):
    s = unicodedata.normalize("NFD", str(s).replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace(".", " ").replace("-", " ").split())


@lru_cache(maxsize=1)
def _countries():
    p = ROOT / "assets" / "geo" / "ne_50m_admin_0_countries.geojson"
    return json.loads(p.read_text(encoding="utf-8"))["features"]


@lru_cache(maxsize=1)
def _places():
    p = ROOT / "assets" / "geo" / "ne_50m_populated_places_simple.geojson"
    try:
        return {_norm(f["properties"].get("name") or ""): tuple(f["geometry"]["coordinates"][:2])
                for f in json.loads(p.read_text(encoding="utf-8"))["features"]}
    except Exception:
        return {}


def lonlat_of(name):
    k = _norm(name)
    k2 = k.replace("thanh pho ", "").replace("tp ", "tp ").strip()
    return VN_CITIES.get(k) or VN_CITIES.get(k2) or _places().get(k) or _places().get(k2)


def _rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def _t_mapdraw(sc, V, tone):
    from .v2m.render import VN_ISLANDS, VN_ISLAND_LABELS
    W, H = _ws(sc)
    S = min(W, H) / 1080
    isos = [c.upper() for c in (sc.get("countries") or ["VNM"])]
    feats = [f for f in _countries() if f["properties"].get("ADM0_A3") in isos or f["properties"].get("ISO_A3") in isos]
    rings = [r for f in feats for r in _rings(f["geometry"])]
    pins = []
    for i, p in enumerate((sc.get("pins") or [])[:8]):
        ll = p.get("lonlat") or lonlat_of(p.get("name", ""))
        if ll:
            pins.append(dict(p, ll=tuple(ll), at=float(p.get("at", 1.6 + 0.45 * i))))
    vn = "VNM" in isos
    pts = [pt for r in rings for pt in r] + [p["ll"] for p in pins]
    if vn:
        pts += [pt for v in VN_ISLANDS.values() for pt in v]
    if not pts:
        return "<div></div>", ""
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    lat0 = (min(lats) + max(lats)) / 2
    kx = math.cos(math.radians(lat0))
    x0, x1 = min(lons) * kx, max(lons) * kx
    y0, y1 = -max(lats), -min(lats)
    # vùng vẽ: chừa tiêu đề phía trên và phụ đề phía dưới
    top = (300 if V else 170) * S if sc.get("title") else 120 * S
    bot = H - (330 if V else 190) * S
    left, right = 90 * S, W - 90 * S
    k = min((right - left) / max(1e-6, x1 - x0), (bot - top) / max(1e-6, y1 - y0))
    ox = (left + right) / 2 - (x0 + x1) / 2 * k
    oy = (top + bot) / 2 - (y0 + y1) / 2 * k
    P = lambda lon, lat: (round(lon * kx * k + ox, 1), round(-lat * k + oy, 1))
    # nước láng giềng (mờ) — cho cảm giác bản đồ thật
    pad = 6
    neigh = []
    for f in _countries():
        if f in feats:
            continue
        for r in _rings(f["geometry"]):
            if any(min(lons) - pad < x < max(lons) + pad and min(lats) - pad < y < max(lats) + pad for x, y in r[::5]):
                neigh.append(r)
    path = lambda r: "M" + "L".join(f"{a},{b}" for a, b in (P(x, y) for x, y in r)) + "Z"
    main = [path(r) for r in rings if len(r) > 3]
    a = ACC[tone]
    sw = 4.2 * S
    svg = [f'<svg class=mp viewBox="0 0 {W:.0f} {H:.0f}" style="position:absolute;inset:0;width:100%;height:100%;overflow:visible">',
           f'<defs><linearGradient id=mf x1=0 y1=0 x2=0 y2=1><stop offset=0 stop-color="{a[1]}" stop-opacity=".55"/>'
           f'<stop offset=1 stop-color="{a[0]}" stop-opacity=".25"/></linearGradient>'
           f'<pattern id=mg width="{14*S:.1f}" height="{14*S:.1f}" patternUnits=userSpaceOnUse><circle cx="{7*S:.1f}" cy="{7*S:.1f}" r="{1.6*S:.1f}" fill="{a[1]}" opacity=".5"/></pattern></defs>',
           '<g class=cam>']
    svg += [f'<path class=nb d="{path(r)}" fill="rgba(120,150,200,.07)" stroke="rgba(150,180,230,.28)" stroke-width="{1.4*S:.1f}"/>' for r in neigh]
    svg += [f'<path class=mfill d="{d}" fill="url(#mf)"/><path class=mdot d="{d}" fill="url(#mg)"/>' for d in main]
    svg += [f'<path class="ml glow" d="{d}" fill=none stroke="{a[1]}" stroke-width="{sw:.1f}" stroke-linejoin=round/>' for d in main]
    if vn:
        for key, isl in VN_ISLANDS.items():
            for lon, lat in isl:
                x, y = P(lon, lat)
                svg.append(f'<circle class=isl cx="{x}" cy="{y}" r="{4.5*S:.1f}" fill="{a[1]}"/>')
            (lx, ly), name = VN_ISLAND_LABELS[key]
            x, y = P(lx, ly)
            svg.append(f'<text class=isl x="{x + 26*S:.0f}" y="{y:.0f}" fill="rgba(255,255,255,.75)" font-size="{24*S:.0f}" font-weight=700 '
                       f'font-family=Montserrat>{_E(name)}</text>')
    # tuyến cong
    for j, rt in enumerate((sc.get("routes") or [])[:6]):
        try:
            i1, i2 = int(rt[0]), int(rt[1])
            ta = float(rt[2]) if len(rt) > 2 else max(pins[i1]["at"], pins[i2]["at"]) + 0.3
            (ax, ay), (bx, by) = P(*pins[i1]["ll"]), P(*pins[i2]["ll"])
        except Exception:
            continue
        mx, my = (ax + bx) / 2, (ay + by) / 2
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy) or 1
        cx, cy = mx - dy / L * L * 0.28, my + dx / L * L * 0.28
        d = f"M{ax},{ay} Q{cx:.1f},{cy:.1f} {bx},{by}"
        svg.append(f'<path class="rt rt{j} glow" data-t="{ta}" d="{d}" fill=none stroke="{a[2]}" stroke-width="{5*S:.1f}" stroke-linecap=round/>')
        svg.append(f'<path class="rd rd{j}" data-t="{ta}" d="{d}" fill=none stroke="#fff" stroke-width="{9*S:.1f}" stroke-linecap=round '
                   f'stroke-dasharray="1 4000" opacity=0/>')
    svg.append("</g></svg>")
    out = "".join(svg)
    for i, p in enumerate(pins):
        x, y = P(*p["ll"])
        side = -1 if x > W * 0.6 else 1
        out += (f'<div class="pin pin{i}" style="position:absolute;left:{x:.0f}px;top:{y:.0f}px">'
                f'<div class=ring style="position:absolute;left:{_px(-60)};top:{_px(-60)};width:{_px(120)};height:{_px(120)};border-radius:50%;border:3px solid {a[1]}"></div>'
                f'<div class=ring2 style="position:absolute;left:{_px(-60)};top:{_px(-60)};width:{_px(120)};height:{_px(120)};border-radius:50%;border:3px solid {a[1]}"></div>'
                f'<div class=dot style="position:absolute;left:{_px(-16)};top:{_px(-16)};width:{_px(32)};height:{_px(32)};border-radius:50%;background:#fff;'
                f'box-shadow:0 0 0 {_px(7)} {a[0]},0 0 {_px(40)} {a[0]}"></div>'
                f'<div class=lbl style="{"left" if side > 0 else "right"}:{_px(34)};top:{_px(-34)};font-size:{_px(40)}">{_E(p.get("name"))}</div></div>')
    if sc.get("title"):
        out += (f'<div class="big grad mt" style="position:absolute;left:4%;right:4%;top:{_px(110 if V else 50)};'
                f'font-size:{_px(_fit(sc["title"], 110 if V else 96, (W*0.9)/S))}">{_E(sc["title"])}</div>')
        if sc.get("sub"):
            out += (f'<div class=msub style="position:absolute;left:0;right:0;text-align:center;top:{_px((110 if V else 50) + 125)};'
                    f'font-weight:700;font-size:{_px(42)};opacity:.85">{_E(sc["sub"])}</div>')
    out += f'<div class=hud style="left:{_px(40)};bottom:{_px(40)};font-size:{_px(22)}">LAT {lat0:.2f}° · SCALE 1:{int(4e6/k)}</div>'
    Dm = float(sc.get("_D", 5))
    dr = round(max(0.6, min(1.5, Dm * 0.4)), 2)            # cảnh ngắn → vẽ nhanh, vẫn kịp hiện đủ bản đồ
    js = f"""const A=s=>[...document.querySelectorAll(sel+' '+s)];
A('.ml').forEach(p=>{{const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;}});
tl.from(A('.nb'),{{opacity:0,duration:.4,stagger:.005}},0)
.to(A('.ml'),{{strokeDashoffset:0,duration:{dr},ease:'power2.inOut',stagger:.01}},0.05)
.from(A('.mfill'),{{opacity:0,duration:.5}},{dr*0.7:.2f}).from(A('.mdot'),{{opacity:0,duration:.6}},{dr*0.85:.2f})
.from(A('.isl'),{{opacity:0,scale:0,transformOrigin:'50% 50%',duration:.3,stagger:.01}},{dr*0.8:.2f})
.fromTo(q('.cam'),{{scale:1.08,transformOrigin:'50% 50%'}},{{scale:1,duration:{float(sc.get('_D', 5))},ease:'power1.out'}},0);
if(q('.mt'))tl.from(q('.mt'),{{y:-40,opacity:0,duration:.5,ease:'power3.out'}},0.05);
if(q('.msub'))tl.from(q('.msub'),{{opacity:0,duration:.4}},0.4);
"""
    for i, p in enumerate(pins):
        t = round(p["at"], 3)
        js += (f"tl.from(q('.pin{i} .dot'),{{y:-160,opacity:0,duration:.45,ease:'bounce.out'}},{t})"
               f".fromTo(q('.pin{i} .ring'),{{scale:.2,opacity:1}},{{scale:2.2,opacity:0,duration:1.1,repeat:3,ease:'power1.out'}},{t + .35})"
               f".fromTo(q('.pin{i} .ring2'),{{scale:.2,opacity:1}},{{scale:2.2,opacity:0,duration:1.1,repeat:3,ease:'power1.out'}},{t + .9})"
               f".from(q('.pin{i} .lbl'),{{x:-30,opacity:0,duration:.4,ease:'back.out(2)'}},{t + .25});")
    js += """A('.rt').forEach(p=>{const L=p.getTotalLength(),t=+p.dataset.t;p.style.strokeDasharray=L;p.style.strokeDashoffset=L;
tl.to(p,{strokeDashoffset:0,duration:.9,ease:'power2.inOut'},t);});
A('.rd').forEach(p=>{const L=p.getTotalLength(),t=+p.dataset.t;tl.set(p,{opacity:1},t+.9)
.fromTo(p,{strokeDashoffset:0},{strokeDashoffset:-L,duration:1.2,repeat:2,ease:'none'},t+.9);});"""
    return _wrap(sc, out, tone), js


# ------------------------------------------------------------------ tech
def _t_tech(sc, V, tone):
    W, H = _ws(sc)
    S = min(W, H) / 1080
    a = ACC[tone]
    rnd = random.Random(7)
    cx, cy = W / 2, H * (0.42 if V else 0.56)
    chip = 330 * S
    traces = []
    for i in range(18):
        side = i % 4
        off = (rnd.random() - 0.5) * chip * 0.8
        if side == 0:
            x, y, dx, dy = cx + off, cy - chip / 2, 0, -1
        elif side == 1:
            x, y, dx, dy = cx + chip / 2, cy + off, 1, 0
        elif side == 2:
            x, y, dx, dy = cx + off, cy + chip / 2, 0, 1
        else:
            x, y, dx, dy = cx - chip / 2, cy + off, -1, 0
        pts = [(x, y)]
        for seg in range(3):
            ln = (70 + rnd.random() * 200) * S
            x, y = x + dx * ln, y + dy * ln
            pts.append((x, y))
            if seg < 2:                                   # rẽ 45°
                tdx, tdy = (dx + (rnd.choice([-1, 1]) if dx == 0 else 0)), (dy + (rnd.choice([-1, 1]) if dy == 0 else 0))
                ln2 = (40 + rnd.random() * 90) * S
                x, y = x + tdx * ln2, y + tdy * ln2
                pts.append((x, y))
        traces.append(pts)
    svg = f'<svg class=tc viewBox="0 0 {W:.0f} {H:.0f}" style="position:absolute;inset:0;width:100%;height:100%">'
    for i, pts in enumerate(traces):
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg += (f'<path class=tr d="{d}" fill=none stroke="{a[0]}" stroke-opacity=".55" stroke-width="{3*S:.1f}"/>'
                f'<path class="tp glow" d="{d}" fill=none stroke="{a[1]}" stroke-width="{5*S:.1f}" stroke-linecap=round stroke-dasharray="{40*S:.0f} 3000"/>'
                f'<circle class=pad cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="{9*S:.1f}" fill="#0B1022" stroke="{a[1]}" stroke-width="{3*S:.1f}"/>')
    svg += "</svg>"
    # sàn lưới phối cảnh
    floor = (f'<div style="position:absolute;left:-50%;right:-50%;bottom:-10%;height:{"38%" if V else "45%"};perspective:{_px(600)};overflow:hidden">'
             f'<div class=fl style="position:absolute;inset:-100% 0 0 0;transform:rotateX(62deg);transform-origin:50% 100%;'
             f'background-image:linear-gradient({a[0]}66 2px,transparent 2px),linear-gradient(90deg,{a[0]}66 2px,transparent 2px);'
             f'background-size:{_px(90)} {_px(90)};-webkit-mask-image:linear-gradient(transparent,#000 60%)"></div></div>')
    c = sc.get("center")
    from pathlib import Path
    if c and (str(c).startswith(("3d:", "ui:")) or Path(str(c)).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")):
        inner = f'<img src="{_icon(c, tone)}" style="width:{"60%" if str(c).startswith("ui:") else "72%"};height:72%;object-fit:contain">'
    else:
        inner = f'<div class="big grad" style="font-size:{_px(_fit(c or "AI", 150, 260))}">{_E(c or "AI")}</div>'
    rings = "".join(
        f'<svg class="rg rg{k}" viewBox="0 0 100 100" style="position:absolute;left:{_px(-(r - 330) / 2)};top:{_px(-(r - 330) / 2)};width:{_px(r)};height:{_px(r)}">'
        f'<circle cx=50 cy=50 r=48 fill=none stroke="{a[1]}" stroke-opacity="{op}" stroke-width="{sw}" stroke-dasharray="{da}"/></svg>'
        for k, (r, op, sw, da) in enumerate([(430, .8, .7, "2 3"), (520, .45, .5, "18 6 2 6"), (620, .25, .4, "1 2")]))
    chiphtml = (f'<div class=chipw style="position:absolute;left:{cx - chip/2:.0f}px;top:{cy - chip/2:.0f}px;width:{chip:.0f}px;height:{chip:.0f}px">{rings}'
                f'<div class=cglow style="position:absolute;inset:-35%;border-radius:50%;background:radial-gradient({a[0]}AA,transparent 62%)"></div>'
                f'<div class=chip0 style="position:absolute;inset:0;border-radius:{_px(64)};background:linear-gradient(145deg,#1A2348,#070B18);'
                f'border:{_px(4)} solid {a[1]};box-shadow:0 0 {_px(60)} {a[0]},inset 0 0 {_px(50)} {a[0]}66;display:flex;align-items:center;justify-content:center">{inner}</div></div>')
    pins = "".join(f'<div style="position:absolute;left:{cx - chip/2 + (j+1)*chip/7 - 4*S:.0f}px;top:{cy + (chip/2 if s_ else -chip/2 - 22*S):.0f}px;width:{8*S:.0f}px;'
                   f'height:{22*S:.0f}px;background:{a[1]};border-radius:2px;opacity:.8"></div>' for j in range(6) for s_ in (0, 1))
    out = floor + svg + pins + chiphtml
    items = (sc.get("items") or [])[:4]
    spots = ([(0.08, 0.09), (0.52, 0.09), (0.08, 0.665), (0.52, 0.665)] if V else [(0.04, 0.30), (0.69, 0.30), (0.04, 0.62), (0.69, 0.62)])
    for i, it in enumerate(items):
        x, y = spots[i]
        ic = it.get("icon") if isinstance(it, dict) else None
        it = it.get("text", "") if isinstance(it, dict) else it
        icon_html = (f'<img src="{_icon(ic, tone)}" style="position:absolute;right:{_px(18)};top:{_px(16)};width:{_px(54)};height:{_px(54)};'
                     f'object-fit:contain">') if ic else ""
        out += (f'<div class="hc hc{i}" style="position:absolute;left:{x*100:.0f}%;top:{y*100:.0f}%;width:{"40%" if V else "27%"};padding:{_px(22)} {_px(26)};'
                f'border-radius:{_px(22)};background:rgba(8,14,32,.78);border:2px solid {a[0]}AA;box-shadow:0 0 {_px(30)} {a[0]}55">'
                f'{icon_html}<div class=hud style="position:static;font-size:{_px(22)};color:{a[1]}">0{i+1} //</div>'
                f'<div style="font-weight:800;font-size:{_px(_fit(it, 44, 380, 0.6))};margin-top:{_px(6)}">{_E(it)}</div></div>')
    if sc.get("title"):
        ty = (cy + chip / 2 + 40 * S) if V else 40 * S
        out += (f'<div class="big grad tt0" style="position:absolute;left:3%;right:3%;top:{ty:.0f}px;'
                f'font-size:{_px(_fit(sc["title"], 120 if V else 100, (W*0.92)/S))}">{_E(sc["title"])}</div>')
    out += (f'<div class=scan style="position:absolute;left:0;right:0;height:{_px(140)};top:0;background:linear-gradient(transparent,{a[0]}22,transparent)"></div>'
            f'<div class=hud style="left:{_px(40)};top:{_px(40)};font-size:{_px(22)}">SYS.CORE // ONLINE</div>'
            f'<div class="hud cnt" style="right:{_px(40)};top:{_px(40)};font-size:{_px(22)}">0000</div>')
    D = float(sc.get("_D", 5))
    js = f"""const A=s=>[...document.querySelectorAll(sel+' '+s)];
A('.tr').forEach(p=>{{const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;}});
A('.tp').forEach((p,i)=>{{const L=p.getTotalLength();tl.fromTo(p,{{strokeDashoffset:{40*S:.0f}}},{{strokeDashoffset:-L,duration:1.1+(i%5)*.15,repeat:{int(D)+1},ease:'none'}},.9+(i%6)*.12);}});
tl.from(q('.chip0'),{{scale:0,rotation:-90,duration:.6,ease:'back.out(1.7)'}},0.05)
.to(A('.tr'),{{strokeDashoffset:0,duration:.8,stagger:.03,ease:'power2.out'}},.3)
.from(A('.pad'),{{scale:0,transformOrigin:'50% 50%',duration:.3,stagger:.03}},.8)
.to(q('.rg0'),{{rotation:360,duration:{D},ease:'none'}},0).to(q('.rg1'),{{rotation:-240,duration:{D},ease:'none'}},0)
.to(q('.rg2'),{{rotation:180,duration:{D},ease:'none'}},0).from(A('.rg'),{{scale:.4,opacity:0,duration:.7,stagger:.1,ease:'power3.out'}},.15)
.fromTo(q('.fl'),{{y:0}},{{y:{90*S*6:.0f},duration:{D},ease:'none'}},0)
.fromTo(q('.scan'),{{y:{-200*S:.0f}}},{{y:{H + 60*S:.0f},duration:2.2,repeat:{int(D/2.2)+1},ease:'none'}},0)
.fromTo(q('.cglow'),{{opacity:.35,scale:.9}},{{opacity:1,scale:1.15,duration:.6,yoyo:true,repeat:{int(D/1.2)+1},ease:'sine.inOut'}},.7);
{{const o={{v:0}};tl.to(o,{{v:9999,duration:{D},ease:'none',onUpdate:()=>q('.cnt').textContent=String(Math.floor(o.v)).padStart(4,'0')}},0);}}
if(q('.tt0'))tl.from(q('.tt0'),{{y:60,opacity:0,duration:.5,ease:'power3.out'}},.5);
"""
    for i in range(len(items)):
        t = _at(sc, i, 0.9 + i * 0.45)
        js += f"tl.from(q('.hc{i}'),{{scale:.6,opacity:0,y:{30 if i < 2 else -30},duration:.45,ease:'back.out(2)'}},{t});"
    return _wrap(sc, out, tone), js


# ------------------------------------------------------------------ prompt
def _t_prompt(sc, V, tone):
    W, H = _ws(sc)
    S = min(W, H) / 1080
    a = ACC[tone]
    text = str(sc.get("text") or "Tạo video giới thiệu sản phẩm, có phụ đề, nhạc nền")
    t_type, t_btn, t_done = _at(sc, 0, 0.3), _at(sc, 1, 0), _at(sc, 2, 0)
    t_btn = t_btn or round(t_type + min(2.2, 0.035 * len(text)) + 0.3, 2)
    t_done = t_done or round(t_btn + 1.4, 2)
    ww = (940 if V else 900)
    wx = (W / S - ww) / 2 if V else 110
    wy = 260 if V else 200
    logo = _icon(sc.get("logo")) if sc.get("logo") else ""
    win = (f'<div class=win style="position:absolute;left:{_px(wx)};top:{_px(wy)};width:{_px(ww)};border-radius:{_px(34)};overflow:hidden;'
           f'background:rgba(14,18,34,.92);border:2px solid rgba(255,255,255,.16);box-shadow:0 {_px(40)} {_px(90)} rgba(0,0,0,.6),0 0 {_px(60)} {a[0]}33">'
           f'<div style="height:{_px(78)};display:flex;align-items:center;gap:{_px(14)};padding:0 {_px(28)};background:rgba(255,255,255,.05)">'
           + "".join(f'<span style="width:{_px(20)};height:{_px(20)};border-radius:50%;background:{c}"></span>' for c in ("#FF5F57", "#FEBC2E", "#28C840"))
           + (f'<img src="{logo}" style="height:{_px(46)};margin-left:{_px(18)};border-radius:{_px(10)}">' if logo else "")
           + f'<b style="font-size:{_px(32)};margin-left:{_px(8)}">{_E(sc.get("app") or "C-Cut")}</b></div>'
           f'<div style="padding:{_px(34)} {_px(38)} {_px(30)}"><div class=hud style="position:static;font-size:{_px(24)};color:{a[1]}">KỊCH BẢN ›</div>'
           f'<div style="min-height:{_px(250 if V else 220)};margin-top:{_px(14)};font-weight:700;font-size:{_px(56 if len(text) < 70 else 46)};line-height:1.3">'
           f'<span class=typ></span><span class=cur style="display:inline-block;width:{_px(5)};height:1.1em;vertical-align:-.15em;background:{a[1]};margin-left:{_px(4)}"></span></div>'
           f'<div style="display:flex;align-items:center;gap:{_px(24)};margin-top:{_px(20)}">'
           f'<div class=btn style="position:relative;padding:{_px(20)} {_px(40)};border-radius:999px;font-weight:900;font-size:{_px(36)};color:#111;'
           f'background:linear-gradient(90deg,{a[1]},{a[0]});box-shadow:0 0 {_px(30)} {a[0]}">{_E(sc.get("button") or "▶  TẠO VIDEO")}'
           f'<div class=rip style="position:absolute;left:50%;top:50%;width:{_px(80)};height:{_px(80)};margin:{_px(-40)};border-radius:50%;border:3px solid #fff;opacity:0"></div></div>'
           f'<div style="flex:1;height:{_px(18)};border-radius:99px;background:rgba(255,255,255,.12);overflow:hidden"><div class=bar style="height:100%;width:100%;'
           f'transform-origin:0 50%;transform:scaleX(0);background:linear-gradient(90deg,{a[0]},{a[1]})"></div></div>'
           f'<b class=pct style="font-size:{_px(34)};min-width:{_px(90)};text-align:right">0%</b></div></div></div>')
    outs = sc.get("outputs") or ["9:16", "16:9"]
    th = _img(sc.get("image"))
    fill = (f"background:url({th}) center/cover" if th else f"background:linear-gradient(135deg,{a[2]},#3A1C71 60%,#0B1022)")
    cards = ""
    if V:
        y = wy + 700
        geo = [(150, y, 330, 586), (520, y + 120, 470, 264)] if len(outs) > 1 else [(375, y, 330, 586)]
    else:
        geo = [(1150, 170, 330, 586), (1110, 800 - 264 + 40, 470, 264)] if len(outs) > 1 else [(1250, 220, 380, 676)]
        geo = [(1120, 150, 300, 534), (1450, 330, 400, 225)] if len(outs) > 1 else geo
    for i, (o, (x, y, w, h)) in enumerate(zip(outs, geo)):
        cards += (f'<div class="oc oc{i}" style="position:absolute;left:{_px(x)};top:{_px(y)};width:{_px(w)};height:{_px(h)};border-radius:{_px(26)};overflow:hidden;'
                  f'{fill};border:3px solid #fff;box-shadow:0 {_px(30)} {_px(60)} rgba(0,0,0,.55),0 0 {_px(50)} {a[0]}88">'
                  f'<div style="position:absolute;inset:0;background:linear-gradient(transparent 50%,rgba(0,0,0,.6))"></div>'
                  f'<div style="position:absolute;left:50%;top:50%;width:{_px(90)};height:{_px(90)};margin:{_px(-45)};border-radius:50%;background:rgba(255,255,255,.9);'
                  f'display:flex;align-items:center;justify-content:center;color:#111;font-size:{_px(40)};padding-left:{_px(6)};box-sizing:border-box">▶</div>'
                  f'<div style="position:absolute;left:{_px(18)};bottom:{_px(14)};font-weight:900;font-size:{_px(34)}">{_E(o)}</div>'
                  f'<div class=shine style="position:absolute;top:0;bottom:0;width:40%;left:0;transform:translateX(-150%) skewX(-18deg);background:linear-gradient(100deg,transparent,rgba(255,255,255,.55),transparent)"></div></div>')
    rnd = random.Random(3)
    sp = "".join(f'<div class="sp" style="position:absolute;left:{_px((W/S)*(0.35+0.3*rnd.random()) if V else 1500)};top:{_px((wy+760) if V else 540)};width:{_px(14)};height:{_px(14)};'
                 f'border-radius:50%;background:{rnd.choice(a)};opacity:0" data-x="{(rnd.random()-.5)*700*S:.0f}" data-y="{(rnd.random()-.7)*600*S:.0f}"></div>' for _ in range(22))
    out = win + cards + sp
    nt = max(0.6, t_btn - 0.3 - t_type)
    js = f"""const A=s=>[...document.querySelectorAll(sel+' '+s)];const TX={json.dumps(text)};
tl.from(q('.win'),{{y:120,opacity:0,scale:.92,duration:.55,ease:'back.out(1.5)'}},0);
{{const o={{n:0}};tl.to(o,{{n:TX.length,duration:{nt:.2f},ease:'none',onUpdate:()=>q('.typ').textContent=TX.slice(0,Math.round(o.n))}},{t_type});}}
tl.to(q('.cur'),{{opacity:0,duration:.01,repeat:{int(float(sc.get('_D', 6))/0.5)},yoyo:true,repeatDelay:.25}},0)
.to(q('.btn'),{{scale:.88,duration:.1,yoyo:true,repeat:1}},{t_btn}).fromTo(q('.rip'),{{scale:.5,opacity:1}},{{scale:5,opacity:0,duration:.6}},{t_btn})
.to(q('.bar'),{{scaleX:1,duration:{max(0.5, t_done - t_btn - 0.15):.2f},ease:'power1.inOut'}},{t_btn + 0.1});
{{const o={{v:0}};tl.to(o,{{v:100,duration:{max(0.5, t_done - t_btn - 0.15):.2f},ease:'power1.inOut',onUpdate:()=>q('.pct').textContent=Math.round(o.v)+'%'}},{t_btn + 0.1});}}
A('.oc').forEach((e,i)=>tl.from(e,{{y:{-300*S:.0f},x:{(0 if V else -500*S):.0f},scale:.2,rotation:i?8:-8,opacity:0,duration:.6,ease:'back.out(1.6)'}},{t_done}+i*.18)
 .fromTo(e.querySelector('.shine'),{{xPercent:-150,skewX:-18}},{{xPercent:300,skewX:-18,duration:.8,ease:'power2.inOut'}},{t_done}+.5+i*.18));
A('.sp').forEach((e,i)=>tl.fromTo(e,{{x:0,y:0,opacity:1,scale:1}},{{x:+e.dataset.x,y:+e.dataset.y,opacity:0,scale:.3,duration:.9,ease:'power2.out',immediateRender:false}},{t_done}+.05));
"""
    return _wrap(sc, out, tone), js


# ------------------------------------------------------------------ devices
def _t_devices(sc, V, tone):
    W, H = _ws(sc)
    S = min(W, H) / 1080
    a = ACC[tone]
    th = _img(sc.get("image"))
    fill = f"background:url({th}) center/cover" if th else f"background:linear-gradient(160deg,{a[2]},#3A1C71 55%,#0B1022)"
    labels = sc.get("labels") or ["TikTok", "YouTube"]
    pw, ph = (470, 960) if V else (360, 740)
    px, py = ((W / S) / 2 - pw / 2 - 170, 200) if V else (330, 170)
    lw, lh = (700, 394) if V else (900, 506)
    lx, ly = ((W / S) / 2 - lw / 2 + 110, 930) if V else (820, 210)
    heart = (f'<svg viewBox="0 0 24 24" style="width:100%;height:100%"><path fill="#FF2B55" d="M12 21s-7.5-4.6-10-9.2C.3 8.4 2.3 4 6.3 4c2.2 0 3.7 1.2 4.7 2.6C12 5.2 13.5 4 15.7 4c4 0 6 4.4 4.3 7.8C19.5 16.4 12 21 12 21z"/></svg>')
    rnd = random.Random(11)
    hearts = "".join(f'<div class=ht data-x="{(rnd.random()-0.5)*120*S:.0f}" style="position:absolute;right:{_px(40)};bottom:{_px(260)};width:{_px(56 + rnd.random()*30)};'
                     f'height:{_px(56)};opacity:0">{heart}</div>' for _ in range(10))
    side = "".join(f'<div style="width:{_px(66)};height:{_px(66)};border-radius:50%;background:rgba(255,255,255,.22);margin-top:{_px(26)}"></div>' for _ in range(3))
    phone = (f'<div class=ph style="position:absolute;left:{_px(px)};top:{_px(py)};width:{_px(pw)};height:{_px(ph)};border-radius:{_px(60)};padding:{_px(14)};'
             f'background:#111;box-shadow:0 0 0 {_px(4)} #444,0 {_px(50)} {_px(100)} rgba(0,0,0,.7),0 0 {_px(80)} {a[0]}55">'
             f'<div style="position:relative;width:100%;height:100%;border-radius:{_px(48)};overflow:hidden;{fill}">'
             f'<div class=kb style="position:absolute;inset:0;{fill};transform-origin:50% 40%"></div>'
             f'<div style="position:absolute;inset:0;background:linear-gradient(transparent 55%,rgba(0,0,0,.65))"></div>'
             f'<div style="position:absolute;left:50%;top:{_px(14)};width:{_px(110)};height:{_px(30)};margin-left:{_px(-55)};border-radius:99px;background:#000"></div>'
             f'<div style="position:absolute;right:{_px(18)};bottom:{_px(150)};display:flex;flex-direction:column;align-items:center">{side}</div>'
             f'{hearts}'
             f'<div style="position:absolute;left:{_px(24)};bottom:{_px(60)};font-weight:800;font-size:{_px(30)}">@{_E(labels[0]).lower()}</div>'
             f'<div style="position:absolute;left:{_px(24)};bottom:{_px(24)};font-weight:700;font-size:{_px(26)};opacity:.85">▶ <span class=vw>0</span> lượt xem</div>'
             f'</div></div>'
             f'<div class="lbl l0" style="left:{_px(px + pw/2)};top:{_px(py - 80)};transform:translateX(-50%);font-size:{_px(40)}">{_E(labels[0])} · 9:16</div>')
    laptop = (f'<div class=lp style="position:absolute;left:{_px(lx)};top:{_px(ly)};width:{_px(lw + 40)}">'
              f'<div style="padding:{_px(18)};border-radius:{_px(26)} {_px(26)} 0 0;background:#1a1a1e;box-shadow:0 0 0 {_px(3)} #444,0 0 {_px(80)} {a[0]}44">'
              f'<div style="position:relative;height:{_px(lh)};border-radius:{_px(8)};overflow:hidden;{fill}">'
              f'<div class=kb2 style="position:absolute;inset:0;{fill}"></div>'
              f'<div style="position:absolute;left:0;right:0;bottom:0;height:{_px(8)};background:rgba(255,255,255,.3)"><div class=yb style="height:100%;width:100%;'
              f'background:#FF0033;transform-origin:0 50%;transform:scaleX(0)"></div></div>'
              f'<div style="position:absolute;left:50%;top:50%;width:{_px(120)};height:{_px(84)};margin:{_px(-42)} 0 0 {_px(-60)};border-radius:{_px(22)};'
              f'background:#FF0033;display:flex;align-items:center;justify-content:center;font-size:{_px(40)}">▶</div></div></div>'
              f'<div style="height:{_px(26)};margin:0 {_px(-40)};border-radius:0 0 {_px(30)} {_px(30)};background:linear-gradient(#c9c9cf,#7a7a80)"></div></div>'
              f'<div class="lbl l1" style="left:{_px(lx + lw/2)};top:{_px(ly + lh + 90)};transform:translateX(-50%);font-size:{_px(40)}">{_E(labels[1] if len(labels) > 1 else "YouTube")} · 16:9</div>')
    t0, t1 = _at(sc, 0, 0.1), _at(sc, 1, 1.2)
    D = float(sc.get("_D", 5))
    views = int(sc.get("views") or 128000)
    out = phone + laptop
    js = f"""const A=s=>[...document.querySelectorAll(sel+' '+s)];
tl.from(q('.ph'),{{y:{400*S:.0f},rotation:-12,opacity:0,duration:.65,ease:'back.out(1.4)'}},{t0}).from(q('.l0'),{{y:30,opacity:0,duration:.35}},{t0 + .4})
.fromTo(q('.kb'),{{scale:1.25}},{{scale:1,duration:{D},ease:'none'}},0)
.from(q('.lp'),{{x:{600*S:.0f},rotationY:-30,opacity:0,duration:.7,ease:'back.out(1.3)'}},{t1}).from(q('.l1'),{{y:30,opacity:0,duration:.35}},{t1 + .4})
.to(q('.yb'),{{scaleX:1,duration:{max(1, D - t1)},ease:'none'}},{t1 + .3})
.fromTo(q('.kb2'),{{scale:1.15}},{{scale:1,duration:{D},ease:'none'}},0);
A('.ht').forEach((e,i)=>tl.fromTo(e,{{y:0,x:0,opacity:0,scale:.4}},{{y:{-520*S:.0f},x:+e.dataset.x,opacity:1,scale:1.1,duration:1.4,ease:'power1.out'}},{t0}+.6+i*.28)
 .to(e,{{opacity:0,duration:.3}},{t0}+1.75+i*.28));
{{const o={{v:0}};tl.to(o,{{v:{views},duration:{max(1.2, D - 0.8):.2f},ease:'power2.out',onUpdate:()=>q('.vw').textContent=Math.round(o.v).toLocaleString('vi-VN')}},{t0}+.4);}}
"""
    return _wrap(sc, out, tone), js


# ------------------------------------------------------------------ pipeline
def _t_pipeline(sc, V, tone):
    W, H = _ws(sc)
    S = min(W, H) / 1080
    a = ACC[tone]
    I, M, O = sc.get("input") or {}, sc.get("engine") or {}, sc.get("output") or {}
    if V:
        nodes = [(W / 2, H * 0.18), (W / 2, H * 0.41), (W / 2, H * 0.63)]
    else:
        nodes = [(W * 0.18, H * 0.48), (W * 0.5, H * 0.48), (W * 0.82, H * 0.48)]
    R = (165 if V else 175) * S

    def node(i, it, x, y, eng=False):
        r = R * (1.25 if eng else 1)
        ring = ""
        if it.get("wave"):                                # giọng nói: micro + sóng âm toả ra (vòng tròn lan)
            body = f'<img src="{_icon(it.get("icon") or "ui:microphone", tone)}" style="width:52%;height:52%;object-fit:contain" class=gl>'
            ring = "".join(f'<div class="sw sw{k}" style="position:absolute;inset:0;border-radius:50%;border:{_px(4)} solid {a[1]};opacity:0"></div>' for k in range(3))
        elif it.get("image"):
            body = f'<div style="width:100%;height:100%;border-radius:50%;background:url({_img(it["image"])}) center/cover"></div>'
        else:
            nm = it.get("logo") or it.get("icon") or "ui:sparkles"
            src = _icon(nm, tone)
            sz = "62%" if str(nm).startswith("ui:") else "70%"
            body = f'<img src="{src}" class=gl style="width:{sz};height:{sz};object-fit:contain">'
        # viền gradient xoay (conic) + lõi kính tối
        spin = (f'<div class="cr cr{i}" style="position:absolute;inset:0;border-radius:50%;'
                f'background:conic-gradient(from 0deg,{a[0]},{a[1]},transparent 40%,{a[2]},{a[0]})"></div>')
        if eng:
            ring = (f'<div class=eg style="position:absolute;inset:-45%;border-radius:50%;background:radial-gradient({a[0]}99,transparent 62%)"></div>'
                    f'<svg class=er viewBox="0 0 100 100" style="position:absolute;inset:-18%;width:136%;height:136%"><circle cx=50 cy=50 r=48 fill=none '
                    f'stroke="{a[1]}" stroke-width=".6" stroke-dasharray="1 3"/></svg>') + ring
        return (f'<div class="nd nd{i}" style="position:absolute;left:{x - r:.0f}px;top:{y - r:.0f}px;width:{2*r:.0f}px;height:{2*r:.0f}px">{ring}{spin}'
                f'<div class=nb style="position:absolute;inset:{_px(5)};border-radius:50%;background:radial-gradient(circle at 35% 25%,#26305C,#070A16 70%);'
                f'box-shadow:0 0 {_px(50 if eng else 26)} {a[0]}88,inset 0 {_px(6)} {_px(20)} rgba(255,255,255,.12);'
                f'display:flex;align-items:center;justify-content:center;overflow:hidden">{body}</div>'
                f'<div class=nl style="position:absolute;left:50%;top:{2*r + 18*S:.0f}px;transform:translateX(-50%);white-space:nowrap;'
                f'font-weight:900;font-size:{_px(46)};text-shadow:0 2px 14px #000">{_E(it.get("label"))}</div></div>')
    svg = f'<svg viewBox="0 0 {W:.0f} {H:.0f}" style="position:absolute;inset:0;width:100%;height:100%">'
    for j in range(2):
        (x1, y1), (x2, y2) = nodes[j], nodes[j + 1]
        r1 = R * (1.25 if j == 1 else 1)
        r2 = R * (1.25 if j == 0 else 1)
        if V:
            y1, y2 = y1 + r1 + 90 * S, y2 - r2 - 30 * S
            d = f"M{x1},{y1:.0f} C{x1 + 50*S:.0f},{(y1*2+y2)/3:.0f} {x2 - 50*S:.0f},{(y1+y2*2)/3:.0f} {x2},{y2:.0f}"
        else:
            x1, x2 = x1 + r1 + 20 * S, x2 - r2 - 20 * S
            d = f"M{x1:.0f},{y1} C{(x1*2+x2)/3:.0f},{y1 - 110*S:.0f} {(x1+x2*2)/3:.0f},{y2 + 110*S:.0f} {x2:.0f},{y2}"
        svg += (f'<path class="ln ln{j}" d="{d}" fill=none stroke="{a[0]}" stroke-opacity=".5" stroke-width="{4*S:.1f}"/>'
                f'<path d="{d}" fill=none stroke="{a[0]}" stroke-opacity=".18" stroke-width="{22*S:.1f}" stroke-linecap=round/>'
                f'<path class="fl fl{j}" d="{d}" fill=none stroke="{a[1]}" stroke-width="{11*S:.1f}" stroke-linecap=round stroke-dasharray="1 {34*S:.0f}"/>')
    svg += "</svg>"
    out = svg + node(0, I, *nodes[0]) + node(1, M, *nodes[1], eng=True) + node(2, O, *nodes[2])
    if sc.get("title"):
        out += (f'<div class="big grad pt" style="position:absolute;left:3%;right:3%;top:{_px(70 if V else 60)};'
                f'font-size:{_px(_fit(sc["title"], 100 if V else 90, (W*0.92)/S))}">{_E(sc["title"])}</div>')
    t0, t1, t2 = _at(sc, 0, 0.1), _at(sc, 1, 0.9), _at(sc, 2, 1.8)
    D = float(sc.get("_D", 5))
    t0 = max(0.05, t0)                                   # mốc phải tăng dần và ≥ 0 (mốc âm làm trình dựng HyperFrames hỏng)
    t1 = max(t1, t0 + 0.5)
    t2 = min(max(t2, t1 + 0.5), max(t1 + 0.3, D - 0.6))
    js = f"""const A=s=>[...document.querySelectorAll(sel+' '+s)];
A('.ln').forEach(p=>{{const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;}});
tl.from(q('.nd0'),{{scale:0,opacity:0,duration:.5,ease:'back.out(2)'}},{t0})
.to(q('.ln0'),{{strokeDashoffset:0,duration:.6,ease:'power2.out'}},{t1 - .5})
.from(q('.nd1'),{{scale:0,rotation:-60,opacity:0,duration:.6,ease:'back.out(1.8)'}},{t1})
.to(q('.ln1'),{{strokeDashoffset:0,duration:.6,ease:'power2.out'}},{t2 - .5})
.from(q('.nd2'),{{scale:0,opacity:0,duration:.55,ease:'back.out(2)'}},{t2})
.fromTo(q('.fl0'),{{strokeDashoffset:0,opacity:0}},{{strokeDashoffset:{-35*S*30:.0f},opacity:1,duration:{D},ease:'none'}},{t1 - .3})
.fromTo(q('.fl1'),{{strokeDashoffset:0,opacity:0}},{{strokeDashoffset:{-35*S*30:.0f},opacity:1,duration:{D},ease:'none'}},{t2 - .3});
if(q('.er'))tl.to(q('.er'),{{rotation:360,transformOrigin:'50% 50%',duration:{max(2, D)},ease:'none'}},0);
A('.cr').forEach((e,i)=>tl.to(e,{{rotation:i%2?-360:360,duration:{max(2.5, D)},ease:'none'}},0));
A('.gl').forEach(e=>tl.fromTo(e,{{y:-6}},{{y:6,duration:.9,yoyo:true,repeat:{int(D/0.9)+1},ease:'sine.inOut'}},0));
if(q('.pt'))tl.from(q('.pt'),{{y:-40,opacity:0,duration:.45}},0);
A('.sw').forEach((e,i)=>tl.fromTo(e,{{scale:1,opacity:.9}},{{scale:1.7,opacity:0,duration:1.2,repeat:{int(D/1.2)},ease:'power1.out',immediateRender:false}},{t0}+.3+i*.4));
if(q('.eg'))tl.fromTo(q('.eg'),{{opacity:.3,scale:.9}},{{opacity:1,scale:1.2,duration:.5,yoyo:true,repeat:{int(D)},ease:'sine.inOut'}},{t1 + .4});
"""
    return _wrap(sc, out, tone), js


# ------------------------------------------------------------------ kinetic
def _t_kinetic(sc, V, tone):
    W, H = _ws(sc)
    S = min(W, H) / 1080
    a = ACC[tone]
    lines = []
    for i, ln in enumerate((sc.get("lines") or [])[:5]):
        if isinstance(ln, str):
            ln = {"text": ln}
        lines.append(dict(ln, at=float(ln.get("at", 0.1 + i * 0.7))))
    avail = (W * 0.88) / S
    rows = ""
    for i, ln in enumerate(lines):
        txt = str(ln["text"]).upper()
        ws_ = txt.split()
        if len(txt) > (11 if V else 18) and len(ws_) > 1:          # dòng dài → 2 hàng cân nhau (chữ vẫn to)
            best = min(range(1, len(ws_)), key=lambda j: abs(len(" ".join(ws_[:j])) - len(" ".join(ws_[j:]))))
            txt = " ".join(ws_[:best]) + "\n" + " ".join(ws_[best:])
        size = _fit(txt, ln.get("size") or (190 if V else 160), avail, 0.84)   # Montserrat Black chữ hoa ≈ 0.8em
        hl = str(ln.get("hl") or "").upper()
        words = ""
        for w in txt.replace("\n", " \n ").split(" "):
            if w == "\n":
                words += "<br>"
                continue
            if not w:
                continue
            if hl and w.strip(",.!?") in hl.split():
                words += (f'<span class="w hw" style="position:relative;display:inline-block;margin:0 .12em;color:#0B1022;padding:0 .12em">'
                          f'<span class=hb style="position:absolute;inset:6% -2%;background:linear-gradient(90deg,{a[1]},{a[0]});border-radius:.12em;z-index:-1;'
                          f'transform-origin:0 50%;box-shadow:0 0 {_px(40)} {a[0]}"></span>{_E(w)}</span>')
            else:
                words += f'<span class=w style="display:inline-block;margin:0 .12em">{_E(w)}</span>'
        rows += (f'<div class="kl kl{i}" style="font-weight:900;line-height:1.05;font-size:{_px(size)};text-align:center;white-space:nowrap;'
                 f'white-space:nowrap;position:relative;z-index:1;isolation:isolate;text-shadow:0 {_px(6)} {_px(30)} rgba(0,0,0,.5)">{words}</div>')
    back = _E(str((lines[-1].get("hl") or lines[-1]["text"]) if lines else "").upper())
    out = (f'<div class=bk style="position:absolute;top:{"30%" if V else "22%"};left:0;white-space:nowrap;font-weight:900;font-size:{_px(420)};'
           f'color:{a[0]}30;-webkit-text-stroke:{_px(3)} {a[0]}55;opacity:.35">{back} · {back} · {back}</div>'
           f'<div class=fl style="position:absolute;left:50%;top:46%;width:{_px(900)};height:{_px(900)};margin:{_px(-450)};border-radius:50%;'
           f'background:radial-gradient({a[0]}88,transparent 65%);opacity:0"></div>'
           f'<div class=stk style="position:absolute;left:0;right:0;top:0;bottom:{"14%" if V else "12%"};display:flex;flex-direction:column;'
           f'justify-content:center;align-items:center;gap:{_px(18)}">{rows}</div>')
    D = float(sc.get("_D", 5))
    ats = [round(ln["at"], 3) for ln in lines]
    js = f"""const A=s=>[...document.querySelectorAll(sel+' '+s)];const L=A('.kl');const AT={json.dumps(ats)};
const hs=L.map(e=>e.offsetHeight+{18*S:.1f});const tot=hs.reduce((x,y)=>x+y,0);
let acc=0;const ys=hs.map(h=>{{acc+=h;return (tot-acc)/2;}});
tl.set(q('.stk'),{{y:ys[0]||0}},0).fromTo(q('.bk'),{{x:0}},{{x:{-900*S:.0f},duration:{D},ease:'none'}},0);
L.forEach((e,i)=>{{const t=AT[i];
 if(i>0)tl.to(q('.stk'),{{y:ys[i],duration:.45,ease:'power3.out'}},t);
 if(i>0)tl.to(L.slice(0,i),{{opacity:.45,scale:.94,duration:.4}},t);
 tl.from(e.querySelectorAll('.w'),{{scale:2.4,opacity:0,filter:'blur(14px)',y:-40,duration:.42,stagger:.07,ease:'expo.out'}},t);
 const hb=e.querySelectorAll('.hb');if(hb.length)tl.from(hb,{{scaleX:0,duration:.35,ease:'power3.out'}},t+.25);
 tl.fromTo(q('.fl'),{{opacity:.9,scale:.6}},{{opacity:0,scale:1.4,duration:.6,ease:'power2.out'}},t)
   .fromTo(q('.stk'),{{scale:1.04}},{{scale:1,duration:.3,ease:'power2.out'}},t+.05);
}});
"""
    return _wrap(sc, out, tone), js


T = {"mapdraw": _t_mapdraw, "tech": _t_tech, "prompt": _t_prompt, "devices": _t_devices, "pipeline": _t_pipeline, "kinetic": _t_kinetic}


def beats(sc: dict, D: float) -> list[float]:
    at = [float(x) for x in sc.get("at") or []]
    at += [float(p.get("at", 0)) for p in sc.get("pins") or [] if isinstance(p, dict)]
    at += [float(ln.get("at", 0)) for ln in sc.get("lines") or [] if isinstance(ln, dict)]
    return sorted({round(x, 2) for x in [0.0, 0.5, 1.2, 2.0] + at if x < D})


def sfx(sc: dict, D: float) -> list[tuple[float, str, float]]:
    k = sc.get("kind")
    out = [(0.0, "mgtrans_01", -14.0)]
    if k == "mapdraw":
        out += [(0.15, "role:data", -16.0)] + [(float(p.get("at", 1.6)), f"pop_0{i % 10}", -15.0) for i, p in enumerate(sc.get("pins") or [])]
    elif k == "tech":
        out += [(0.05, "role:glitch", -16.0), (0.35, "role:data", -16.0)] + \
               [(_at(sc, i, 0.9 + i * .45), f"pop_0{(i*3) % 10}", -16.0) for i in range(len(sc.get("items") or []))]
    elif k == "prompt":
        b = _at(sc, 1, 0) or 2.5
        out += [(_at(sc, 0, 0.3), "role:typing", -18.0), (b, "card_01", -13.0), (b + 0.15, "role:data", -16.0),
                ((_at(sc, 2, 0) or b + 1.4), "role:boom", -13.0)]
    elif k == "devices":
        out += [(_at(sc, 0, .1), "pop_02", -15.0), (_at(sc, 1, 1.2), "pop_05", -15.0)]
    elif k == "pipeline":
        out += [(_at(sc, i, d), f"pop_0{i*3}", -15.0) for i, d in enumerate((0.1, 0.9, 1.8))]
    elif k == "kinetic":
        out += [(float((ln if isinstance(ln, dict) else {}).get("at", 0.1 + i * .7)), "hit_03", -15.0) for i, ln in enumerate(sc.get("lines") or [])]
    return [(t, a, g) for t, a, g in out if t < D - 0.2]
