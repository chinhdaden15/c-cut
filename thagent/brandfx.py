"""MG2 dùng TƯ LIỆU THẬT của thứ đang được nhắc tới (tạo bằng thagent/brandkit.py: tools brand / webshot / paper).

  brand    logo THẬT bật lên trong ô có vầng sáng màu thương hiệu + tên + dòng phụ. logo (assets_web/brand_x/logo.svg|png),
           name, sub, accent (kit.json accent), at [logo, tên, dòng phụ]
  webpage  khung trình duyệt kính tối (thanh địa chỉ đúng tên miền) + ảnh chụp trang thật trượt lên rồi cuộn chậm; tuỳ chọn
           khoanh vùng: mark {x, y, w, h} (0..1 trên ảnh) lúc at[1]. image (assets_web/web_x.jpg), url, scroll (0..0.6), at [vào, khoanh]
  paper    nhân vật / vật dạng STICKER GIẤY (assets_web/p_x.png từ tools paper) đập vào hơi nghiêng + lắc nhẹ, băng nhãn tên kiểu máy in nhãn.
           image, name, role, side "left"|"center"|"right", at [sticker, nhãn]
Chung: y (tâm 0..1), tone / accent; mặc định chồng lên hình (bg "none"). Tư liệu thật → ảnh phải đúng thứ đang nói (illus_check).
"""
from __future__ import annotations

KINDS = {"brand", "webpage", "paper"}

CSS = """
.bx{position:absolute;left:0;right:0;display:flex;flex-direction:column;align-items:center;font-family:Montserrat,sans-serif;color:#fff}
.bx-glow{position:absolute;border-radius:50%;filter:blur(calc(60px*var(--s)));opacity:.55}
.bx-tile{position:relative;display:flex;align-items:center;justify-content:center;border-radius:calc(56px*var(--s));
 background:rgba(14,16,24,.62);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1.5px solid rgba(255,255,255,.18);
 box-shadow:0 calc(26px*var(--s)) calc(60px*var(--s)) rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.2)}
.bx-tile img{max-width:72%;max-height:72%;object-fit:contain;filter:drop-shadow(0 6px 18px rgba(0,0,0,.35))}
.bx-name{font-weight:900;letter-spacing:-.02em;text-shadow:0 3px 14px rgba(0,0,0,.45);white-space:nowrap}
.bx-sub{font-weight:600;opacity:.92;text-shadow:0 2px 10px rgba(0,0,0,.45);white-space:nowrap;padding:calc(10px*var(--s)) calc(26px*var(--s));
 border-radius:999px;background:rgba(14,16,24,.55);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid rgba(255,255,255,.14)}
.wb{position:relative;border-radius:calc(26px*var(--s));overflow:hidden;background:rgba(14,16,24,.8);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);
 border:1.5px solid rgba(255,255,255,.18);box-shadow:0 calc(30px*var(--s)) calc(70px*var(--s)) rgba(0,0,0,.5)}
.wb-bar{display:flex;align-items:center;gap:calc(12px*var(--s));padding:calc(16px*var(--s)) calc(20px*var(--s))}
.wb-dot{width:calc(16px*var(--s));height:calc(16px*var(--s));border-radius:50%}
.wb-url{flex:1;margin-left:calc(10px*var(--s));padding:calc(8px*var(--s)) calc(20px*var(--s));border-radius:999px;background:rgba(255,255,255,.1);
 color:rgba(255,255,255,.88);font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.wb-view{position:relative;overflow:hidden}.wb-view img{display:block;width:100%}
.wb-mark{position:absolute;border:calc(5px*var(--s)) solid var(--acc);border-radius:calc(18px*var(--s));box-shadow:0 0 0 9999px rgba(0,0,0,.42),0 0 calc(30px*var(--s)) var(--acc)}
.pp{position:absolute}.pp img{display:block;width:100%;filter:drop-shadow(0 calc(18px*var(--s)) calc(24px*var(--s)) rgba(0,0,0,.4))}
.pp-tape{position:absolute;padding:calc(10px*var(--s)) calc(26px*var(--s));background:#141414;color:#F4F1EA;font-family:'JetBrains Mono',Menlo,monospace;
 font-weight:800;letter-spacing:.06em;white-space:nowrap;box-shadow:0 8px 18px rgba(0,0,0,.35);border-radius:4px}
.pp-role{display:block;font-weight:600;letter-spacing:.02em;opacity:.8;margin-top:2px}
"""


def _px(v) -> str:
    return f"calc({v}px*var(--s))"


def _r(x) -> float:
    return round(float(x), 3)


def layer(sc: dict, V: bool, tone: str, D: float):
    from .mg2 import _uri, E
    from .textfx import PAL, RUNTIME
    k = sc["kind"]
    pal = PAL.get(tone, PAL["gold"])
    acc = sc.get("accent") or pal["acc"]
    at = [float(x) for x in (sc.get("at") or [])]
    A = lambda i, d: _r(at[i]) if i < len(at) else _r(d)
    H = 1920 if V else 1080
    y = float(sc.get("y", 0.6 if V else 0.55))
    t_out = _r(max(0.4, D - 0.3))
    js, beats, sfx = [], [0.0], []
    if k == "brand":
        sz = 300 if V else 260
        logo = _uri(sc["logo"]) if sc.get("logo") else ""
        name, sub = E(sc.get("name", "")), E(sc.get("sub", ""))
        nsz = min(120 if V else 104, (1080 * 0.78) / max(1, len(sc.get("name", "")) * 0.66))
        h = sz + nsz * 1.3 + (90 if sub else 0)
        top = y * H - h / 2
        html = (f'<div class="bx" style="top:{_px(round(top))};--acc:{acc}">'
                f'<div class="bx-glow gw" style="width:{_px(sz * 1.6)};height:{_px(sz * 1.6)};top:{_px(-sz * 0.3)};background:{acc}"></div>'
                f'<div class="bx-tile tile" style="width:{_px(sz)};height:{_px(sz)}">' + (f'<img src="{logo}">' if logo else "") + '</div>'
                f'<div class="bx-name nm" style="font-size:{_px(round(nsz))};margin-top:{_px(28)}">{name}</div>'
                + (f'<div class="bx-sub sb" style="font-size:{_px(44 if V else 38)};margin-top:{_px(18)}">{sub}</div>' if sub else "") + '</div>')
        t0, t1, t2 = A(0, 0.15), A(1, 0.6), A(2, 1.1)
        js.append(f"gsap.set([q('.tile'),q('.gw')],{{opacity:0,scale:.55}});ft('.tile',{{opacity:0,scale:.55,rotation:-8}},{{opacity:1,scale:1,rotation:0,duration:.55,ease:'back.out(2.2)'}},{t0});"
                  f"ft('.gw',{{opacity:0,scale:.55}},{{opacity:.55,scale:1,duration:.8,ease:OUT}},{t0});"
                  f"tl.to(q('.gw'),{{scale:1.12,opacity:.4,duration:1.2,yoyo:true,repeat:3,ease:'sine.inOut'}},{_r(t0 + 0.8)});"
                  f"gsap.set(q('.nm'),{{opacity:0,y:30}});ft('.nm',{{opacity:0,y:30}},{{opacity:1,y:0,duration:.45,ease:OUT}},{t1});")
        if sub:
            js.append(f"gsap.set(q('.sb'),{{opacity:0,y:20}});ft('.sb',{{opacity:0,y:20}},{{opacity:1,y:0,duration:.4,ease:OUT}},{t2});")
        js.append(f"ft('.bx',{{opacity:1,scale:1}},{{opacity:0,scale:.96,duration:.3,ease:IN}},{t_out});")
        beats += [t0, t1, t2]
        sfx += [(t0, "pop_02", -14.0), (t1, "soft_00", -16.0)]
    elif k == "webpage":
        w = 940 if V else 1240
        img = _uri(sc["image"])
        url = E(sc.get("url", ""))
        vh = round(w * (0.9 if V else 0.56))
        h = vh + 70
        top = y * H - h / 2
        mk = sc.get("mark")
        mark = (f'<div class="wb-mark mk" style="left:{mk["x"] * 100:.1f}%;top:{mk["y"] * 100:.1f}%;width:{mk["w"] * 100:.1f}%;height:{mk["h"] * 100:.1f}%"></div>'
                if mk else "")
        html = (f'<div class="bx" style="top:{_px(round(top))};--acc:{acc};perspective:{_px(2400)}">'
                f'<div class="wb win" style="width:{_px(w)}"><div class="wb-bar"><i class="wb-dot" style="background:#FF5F57"></i>'
                f'<i class="wb-dot" style="background:#FEBC2E"></i><i class="wb-dot" style="background:#28C840"></i>'
                f'<span class="wb-url" style="font-size:{_px(30)}">🔒 {url}</span></div>'
                f'<div class="wb-view" style="height:{_px(vh)}"><img class="shot" src="{img}">{mark}</div></div></div>')
        t0 = A(0, 0.1)
        sc_ = float(sc.get("scroll", 0.25))
        js.append(f"gsap.set(q('.win'),{{opacity:0,y:160,rotationX:18}});ft('.win',{{opacity:0,y:160,rotationX:18}},{{opacity:1,y:0,rotationX:0,duration:.7,ease:OUT}},{t0});"
                  f"ft('.shot',{{yPercent:0}},{{yPercent:{-sc_ * 100:.0f},duration:{max(0.5, D - t0 - 1.2):.2f},ease:'power1.inOut'}},{_r(t0 + 0.8)});"
                  f"ft('.bx',{{opacity:1}},{{opacity:0,duration:.3,ease:IN}},{t_out});")
        if mk:
            t1 = A(1, 1.6)
            js.append(f"gsap.set(q('.mk'),{{opacity:0,scale:1.15}});ft('.mk',{{opacity:0,scale:1.15}},{{opacity:1,scale:1,duration:.35,ease:'back.out(2)'}},{t1});")
            beats.append(t1); sfx.append((t1, "pop_05", -15.0))
        beats.append(t0); sfx.append((t0, "whoosh_short", -14.0))
    elif k == "paper":
        side = sc.get("side", "center")
        w = round(float(sc.get("w", 560 if V else 520)))
        img = _uri(sc["image"])
        x = {"left": 0.28, "right": 0.72, "center": 0.5}.get(side, 0.5) * (1080 if V else 1920)
        top = y * H - w * 0.75
        rot = {"left": -4, "right": 4}.get(side, -3)
        name, role = E(sc.get("name", "")), E(sc.get("role", ""))
        tape = (f'<div class="pp-tape tp" style="left:50%;bottom:{_px(-30)};font-size:{_px(40)};transform:translateX(-50%) rotate({-rot}deg)">{name}'
                + (f'<span class="pp-role" style="font-size:{_px(26)}">{role}</span>' if role else "") + '</div>') if name else ""
        html = (f'<div class="pp st" style="left:{_px(round(x - w / 2))};top:{_px(round(top))};width:{_px(w)};transform-origin:50% 90%">'
                f'<img src="{img}">{tape}</div>')
        t0, t1 = A(0, 0.15), A(1, 0.7)
        js.append(RUNTIME)
        js.append(f"(()=>{{const P={{u:0}};const el=q('.st');const paint=()=>{{const t=tl.time();const u=t-{t0};"
                  f"if(u<0){{el.style.opacity='0';return}}const ox=t>{t_out}?KT.EI((t-{t_out})/.3):0;"
                  f"const sc=1+KT.spring(u,.42,1.7,.38),rr={rot}+KT.spring(u,-14,1.3,.32);"
                  f"el.style.opacity=String(KT.C(u/.06)*(1-ox));el.style.transform='rotate('+rr.toFixed(2)+'deg) scale('+(sc*(1-.06*ox)).toFixed(3)+')'}};"
                  f"tl.fromTo(P,{{u:0}},{{u:1,duration:{D},ease:'none',onUpdate:paint,immediateRender:false}},0);paint()}})();")
        if name:
            js.append(f"gsap.set(q('.tp'),{{opacity:0,y:30}});ft('.tp',{{opacity:0,y:30}},{{opacity:1,y:0,duration:.3,ease:OUT}},{t1});")
            beats.append(t1); sfx.append((t1, "u_tick", -15.0))
        beats.append(t0); sfx.append((t0, "impact_soft", -12.0))
    else:
        raise ValueError(k)
    wrap = f'<div data-layout-allow-overflow data-layout-allow-occlusion style="position:absolute;inset:0;--acc:{acc}">{html}</div>'
    from .textfx import RUNTIME as RT
    pre = "" if k == "paper" else RT
    return wrap, pre + "".join(js), sorted({b for b in beats if 0 <= b < D}), [(t, a, g) for t, a, g in sfx if 0 <= t < D]
