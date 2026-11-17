"""BỘ CHUYỂN ĐỘNG RIÊNG THEO PHONG CÁCH KÊNH (pack) — dựng lại TẬN GỐC các loại cảnh MG hay dùng nhất, không khoác áo mẫu cũ.

Cùng lời gọi K.mg("money" | "chart" | "compare" | "checklist" | "kinetic" | "spring" | "headline", …) → mỗi pack ra
bố cục + ngữ pháp chuyển động khác hẳn. Kind pack chưa làm → rơi về mẫu chung (mg2/fx/textfx).

Pack "swiss" (kênh Chia sẻ / tài chính): nền phẳng tương phản cao, chữ không chân đậm căn trái, lộ chữ bằng mặt nạ
và vệt màu quét, số chạy từng chữ số (đồng hồ cơ), đường kẻ tự vẽ, ease expo — không kính mờ, không glow, không nảy.
Hàm: (sc, V, P) → (html, js, css). P = bảng màu của look (bg, ink, acc, acc2, panel)."""
from __future__ import annotations

import html as _h
import json


def E(s) -> str:
    return _h.escape(str(s if s is not None else ""), quote=True)


def px(v) -> str:
    return f"calc({v}px*var(--s))"


def _at(sc, i, default):
    a = sc.get("at") or []
    return round(float(a[i]), 3) if i < len(a) else default


def _fit(text, size, chars):
    n = len(str(text or ""))
    return size if n <= chars else max(size * 0.5, size * chars / n)


# ------------------------------------------------------------------ SWISS
SWISS_CSS = """
.sw{position:absolute;inset:0;font-family:'CCut Display','Be Vietnam Pro',sans-serif;color:var(--ink);font-synthesis:none}
.sw .m{display:block;overflow:hidden;padding-bottom:.08em;margin-bottom:-.08em}
.sw .m>i{display:block;font-style:normal}
.sw .wd{display:inline-block;overflow:hidden;vertical-align:top;padding-bottom:.1em;margin-bottom:-.1em}
.sw .wd>i{display:inline-block;font-style:normal;position:relative;isolation:isolate}
.sw .hlb{position:absolute;left:-.08em;right:-.08em;top:.06em;bottom:-.02em;background:var(--acc);transform-origin:0 50%;z-index:-1}
.sw .lab{font-family:'Be Vietnam Pro',sans-serif;font-weight:700;letter-spacing:.14em;text-transform:uppercase}
.sw .rule{height:calc(6px*var(--s));background:var(--ink);transform-origin:0 50%}
.sw .od{display:inline-block;overflow:hidden;height:1em;line-height:1em;vertical-align:top}
.sw .od>span{display:block}
.sw .od>span>b{display:block;height:1em;font-weight:inherit}
.sw .pnl{position:absolute;background:var(--paper)}
"""


def _pal(P):
    return f"--ink:{P['ink']};--acc:{P['acc']};--acc2:{P['acc2']};--paper:{P['paper']}"


def _wrap(P, inner, panel=None):
    """panel=(x,y,w,h) → nền giấy đặc phía sau (cảnh có ảnh/video phía sau: chữ luôn đọc được)."""
    bg = (f";background:linear-gradient(var(--paper),var(--paper)) no-repeat {px(panel[0])} {px(panel[1])}/{px(panel[2])} {px(panel[3])}"
          if panel else "")
    return f'<div class=sw style="{_pal(P)}{bg}">{inner}</div>'


def _words(text, hl=None, cls="w"):
    """chữ → từng từ trong mặt nạ (lộ từ dưới lên); từ thuộc cụm hl có khối màu nhấn phía sau."""
    hlw = set(str(hl or "").upper().split())
    out = []
    for j, w in enumerate(str(text).split()):
        mark = '<b class=hlb></b>' if w.upper().strip("?!.,") in {x.strip("?!.,") for x in hlw} else ""
        col = ";color:#fff" if mark else ""
        out.append(f'<span class=wd data-layout-allow-overflow data-layout-allow-occlusion><i class="{cls} {cls}{j}" style="position:relative{col}">{mark}{E(w)}</i></span>')
    return " ".join(out)


def sw_kinetic(sc, V, P):
    """chữ động toàn khung: mỗi cụm vào bằng mặt nạ từng từ, căn trái; cụm cũ đẩy lên + mờ đi; từ nhấn có khối màu quét."""
    lines = [x if isinstance(x, dict) else {"text": str(x)} for x in (sc.get("lines") or [])][:5]
    W = 1080 if V else 1920
    left, top = (90, 520) if V else (160, 260)
    rows, js = "", []
    n = len(lines)
    for i, L in enumerate(lines):
        t = round(float(L.get("at", 0.2 + i * 0.9)), 3)
        size = _fit(L["text"], 132 if V else 120, 12 if V else 20)
        rows += (f'<div class="kl kl{i}" style="font-weight:800;font-size:{px(size)};line-height:1.04;letter-spacing:-.02em;'
                 f'margin-bottom:{px(26)}">{_words(L["text"], L.get("hl"), f"k{i}w")}</div>')
        js.append(f"tl.from(q('.kl{i} .k{i}w'),{{yPercent:110,duration:.55,ease:'expo.out',stagger:.06}},{t});"
                  f"tl.from(q('.kl{i} .hlb'),{{scaleX:0,duration:.45,ease:'expo.inOut'}},{t + .25});")
        if i:
            js.append(f"tl.to(q('.kl{i - 1}'),{{opacity:.28,duration:.4,ease:'power2.out'}},{t});")
    bar = f'<div class="rule kr" style="position:absolute;left:{px(left)};top:{px(top - 70)};width:{px(180)};background:var(--acc)"></div>'
    tag = E(sc.get("tag", ""))
    tg = f'<div class="lab kt" style="position:absolute;left:{px(left)};top:{px(top - 140)};font-size:{px(34)}">{tag}</div>' if tag else ""
    bg = ""
    grid = "".join(f'<div class="gl gl{k}" style="position:absolute;top:0;bottom:0;left:{k * W / 6}px;width:1px;background:var(--ink);opacity:.07"></div>'
                   for k in range(1, 6))
    html = _wrap(P, bg + grid + bar + tg + f'<div class=kst style="position:absolute;left:{px(left)};right:{px(left)};top:{px(top)}">{rows}</div>', (0, 0, W, 1920 if V else 1080))
    js0 = (f"tl.from(q('.gl'),{{scaleY:0,transformOrigin:'0 0',duration:.8,ease:'expo.out',stagger:.05}},0);"
           f"tl.from(q('.kr'),{{scaleX:0,duration:.5,ease:'expo.out'}},.05);" + ("tl.from(q('.kt'),{yPercent:100,opacity:0,duration:.4,ease:'expo.out'},.15);" if tag else ""))
    if n > 3:      # nhiều cụm: cả khối trượt lên để cụm mới luôn nằm giữa khung
        for i in range(3, n):
            t = round(float(lines[i].get("at", 0.2 + i * 0.9)), 3)
            js.append(f"tl.to(q('.kst'),{{y:'-={170 if V else 150}',duration:.5,ease:'expo.inOut'}},{t - .05});")
    return html, js0 + "".join(js), SWISS_CSS


def sw_money(sc, V, P, panel=None):
    """số lớn căn trái, từng chữ số lăn như đồng hồ cơ, dừng đúng lúc nói; nhãn lộ bằng mặt nạ, đường kẻ tự vẽ."""
    d = int(sc.get("decimals", 0))
    vt = float(sc.get("value_to", 0))
    loc_en = sc.get("locale") == "en"
    s = f"{vt:,.{d}f}"
    if not loc_en:
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
    unit = str(sc.get("unit", "") or "")
    pre = str(sc.get("prefix", "") or "")
    h = max(float(sc.get("hit_at", 1.5)), 0.9)
    size = min(230 if V else 220, int((860 if V else 1300) / (0.6 * max(1, len(pre + s)))))
    cols, js = "", []
    k = 0
    for ch in s:
        if ch.isdigit():
            strip = "".join(f"<b>{x % 10}</b>" for x in range(0, 10 + int(ch) + 1))
            cols += f'<span class="od" data-layout-allow-overflow data-layout-allow-occlusion><span class="os os{k}">{strip}</span></span>'
            js.append(f"tl.fromTo(q('.os{k}'),{{yPercent:0}},{{yPercent:-100*{10 + int(ch)}/{11 + int(ch)},duration:{max(.6, h - .3):.2f},ease:'expo.inOut'}},.15+{k * .04});")
            k += 1
        else:
            cols += f'<span>{E(ch)}</span>'
    x, y = (90, 640) if V else (160, 330)
    title, sub = sc.get("title", ""), sc.get("sub", "")
    lbl = (f'<div class="m" data-layout-allow-overflow data-layout-allow-occlusion style="margin-top:{px(34)}"><i class="lab mt" style="font-size:{px(38)};color:var(--acc)">{E(title)}</i></div>' if title else "")
    sb = (f'<div class="m" data-layout-allow-overflow data-layout-allow-occlusion style="margin-top:{px(14)}"><i class="ms" style="font-family:\'Be Vietnam Pro\';font-weight:600;font-size:{px(44)};opacity:.75">{E(sub)}</i></div>' if sub else "")
    un = f'<span class=mu style="font-size:.42em;margin-left:.18em;letter-spacing:0">{E(unit)}</span>' if unit else ""
    num = (f'<div style="font-weight:800;font-size:{px(size)};line-height:1;letter-spacing:-.04em;white-space:nowrap">'
           f'<span>{E(pre)}</span>{cols}{un}</div>')
    html = _wrap(P, f'<div style="position:absolute;left:{px(x)};top:{px(y)}">'
                    f'<div class="rule mr" style="width:{px(860 if V else 1200)};margin-bottom:{px(40)}"></div>{num}{lbl}{sb}</div>', panel)
    js0 = (f"tl.from(q('.mr'),{{scaleX:0,duration:.7,ease:'expo.out'}},0);"
           + (f"tl.from(q('.mu'),{{opacity:0,x:-30,duration:.4,ease:'expo.out'}},{h - .2});" if unit else "")
           + (f"tl.from(q('.mt'),{{yPercent:110,duration:.5,ease:'expo.out'}},.35);" if title else "")
           + (f"tl.from(q('.ms'),{{yPercent:110,duration:.5,ease:'expo.out'}},.5);" if sub else "")
           + f"tl.fromTo(q('.mr'),{{background:'{P['ink']}'}},{{background:'{P['acc']}',duration:.2}},{h});")
    return html, js0 + "".join(js), SWISS_CSS


def sw_chart(sc, V, P, panel=None):
    """đồ thị bậc thang tự vẽ trên lưới mảnh, chấm đầu đường chạy theo + nhãn số bám chấm; số lớn đếm tới đích."""
    vf, vt = float(sc.get("value_from", 0)), float(sc.get("value_to", 0))
    sfx = str(sc.get("suffix", "%"))
    h = max(float(sc.get("hit_at", 2.0)), 1.0)
    W, H = (900, 560) if V else (1300, 520)
    x0, y0 = (90, 440) if V else (310, 220)
    up = vt >= vf
    ys = [0.85, 0.72, 0.76, 0.55, 0.48, 0.25, 0.12] if up else [0.15, 0.3, 0.26, 0.45, 0.52, 0.75, 0.88]
    pts = [(round(i * W / (len(ys) - 1)), round(y * H)) for i, y in enumerate(ys)]
    d = "M" + " L".join(f"{a},{b}" for a, b in pts)
    grid = "".join(f'<line class=gr x1=0 x2={W} y1={round(k * H / 4)} y2={round(k * H / 4)} stroke="{P["ink"]}" stroke-opacity=".12" stroke-width=2 />' for k in range(5))
    svg = (f'<svg width="{px(W)}" height="{px(H)}" viewBox="0 0 {W} {H}" style="position:absolute;left:0;top:{px(220)};overflow:visible">{grid}'
           f'<path class=cl d="{d}" fill=none stroke="{P["acc"]}" stroke-width=12 stroke-linejoin=miter stroke-linecap=square />'
           f'<circle class=cd r=18 fill="{P["ink"]}" cx="{pts[0][0]}" cy="{pts[0][1]}" /></svg>')
    head = (f'<div style="display:flex;align-items:baseline;gap:{px(20)}"><div class=m data-layout-allow-overflow data-layout-allow-occlusion><i class=cv style="font-weight:800;font-size:{px(170)};'
            f'letter-spacing:-.04em;line-height:1">{E(vf)}{E(sfx)}</i></div>'
            f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion><i class="lab cla" style="font-size:{px(36)}">{E(sc.get("label", ""))}</i></div></div>')
    foot = (f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion style="position:absolute;left:0;top:{px(H + 260)}"><i class=ct style="font-family:\'Be Vietnam Pro\';font-weight:700;'
            f'font-size:{px(42)}">{E(sc.get("title", ""))}{(" · " + E(sc["sub"])) if sc.get("sub") else ""}</i></div>')
    html = _wrap(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">{head}{svg}{foot}</div>', panel)
    js = (f"const p=q('.cl'),L=p.getTotalLength(),c=q('.cd');p.style.strokeDasharray=L;p.style.strokeDashoffset=L;"
          f"tl.from(q('.gr'),{{attr:{{x2:0}},duration:.7,ease:'expo.out',stagger:.06}},0);"
          f"tl.from(q('.cv'),{{yPercent:110,duration:.5,ease:'expo.out'}},.1).from(q('.cla'),{{yPercent:110,duration:.5,ease:'expo.out'}},.2)"
          f".from(q('.ct'),{{yPercent:110,duration:.5,ease:'expo.out'}},.45);"
          f"const o={{k:0,v:{vf}}};tl.to(o,{{k:1,v:{vt},duration:{h - .3:.2f},ease:'power2.inOut',onUpdate:()=>{{p.style.strokeDashoffset=L*(1-o.k);"
          f"const pt=p.getPointAtLength(L*o.k);c.setAttribute('cx',pt.x);c.setAttribute('cy',pt.y);"
          f"q('.cv').textContent=(Math.round(o.v*10)/10).toLocaleString('vi-VN')+{json.dumps(sfx)}}}}},.3);"
          f"tl.fromTo(c,{{attr:{{r:18}}}},{{attr:{{r:34}},duration:.18,yoyo:true,repeat:1,ease:'power2.out',immediateRender:false}},{h});")
    return html, js, SWISS_CSS


def sw_compare(sc, V, P, panel=None):
    """hai dải màu đặc chồng nhau (dọc) / cạnh nhau (ngang), mỗi dải lộ bằng mặt nạ quét ngược chiều; số khổng lồ; mũi tên kẻ."""
    a, b = sc.get("a") or {}, sc.get("b") or {}
    W = 900 if V else 1500
    bh = 420 if V else 520
    x0, y0 = (90, 430) if V else (210, 260)
    blocks = ""
    for i, (it, bgc, fg) in enumerate(((a, P["ink"], P["paper"]), (b, P["acc"], "#FFFFFF"))):
        val = str(it.get("value", ""))
        vs = _fit(val, 170 if V else 150, 8)
        y = i * (bh + 70) if V else 0
        x = 0 if V else i * (W / 2 + 30)
        w = W if V else W / 2 - 30
        blocks += (f'<div class="cb cb{i}" style="position:absolute;left:{px(x)};top:{px(y)};width:{px(w)};height:{px(bh)};background:{bgc};color:{fg}">'
                   f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion style="position:absolute;left:{px(50)};top:{px(46)}"><i class="lab cl{i}" style="font-size:{px(34)}">{E(it.get("label", "TRƯỚC" if not i else "SAU"))}</i></div>'
                   f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion style="position:absolute;left:{px(46)};bottom:{px(110 if it.get("sub") else 50)}"><i class=cv{i} style="font-weight:800;font-size:{px(vs)};letter-spacing:-.04em;line-height:1;white-space:nowrap">{E(val)}</i></div>'
                   + (f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion style="position:absolute;left:{px(50)};bottom:{px(44)}"><i class=cs{i} style="font-family:\'Be Vietnam Pro\';font-weight:600;font-size:{px(38)};opacity:.85">{E(it.get("sub"))}</i></div>' if it.get("sub") else "")
                   + '</div>')
    ar = (f'<svg class=ca style="position:absolute;left:{px(W - 130 if V else W / 2 - 60)};top:{px(bh - 20 if V else bh / 2 - 60)};overflow:visible" width="{px(120)}" height="{px(120)}" viewBox="0 0 120 120">'
          f'<path class=cap d="{"M60,0 L60,110 M30,80 L60,110 L90,80" if V else "M0,60 L110,60 M80,30 L110,60 L80,90"}" fill=none stroke="{P["ink"]}" stroke-width=10 /></svg>')
    html = _wrap(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)};height:{px(2 * bh + 70 if V else bh)}">{blocks}{ar}</div>', panel)
    t0, t1 = _at(sc, 0, .1), _at(sc, 1, .9)
    js = (f"tl.fromTo(q('.cb0'),{{clipPath:'inset(0 100% 0 0)'}},{{clipPath:'inset(0 0% 0 0)',duration:.6,ease:'expo.inOut'}},{t0});"
          f"tl.from(q('.cl0'),{{yPercent:110,duration:.45,ease:'expo.out'}},{t0 + .3}).from(q('.cv0'),{{yPercent:110,duration:.55,ease:'expo.out'}},{t0 + .35});"
          f"if(q('.cs0'))tl.from(q('.cs0'),{{yPercent:110,duration:.45,ease:'expo.out'}},{t0 + .45});"
          f"const ap=q('.cap'),AL=ap.getTotalLength();ap.style.strokeDasharray=AL;ap.style.strokeDashoffset=AL;"
          f"tl.to(ap,{{strokeDashoffset:0,duration:.45,ease:'expo.out'}},{max(t0 + .5, t1 - .3)});"
          f"tl.fromTo(q('.cb1'),{{clipPath:'inset(0 0 0 100%)'}},{{clipPath:'inset(0 0 0 0%)',duration:.6,ease:'expo.inOut'}},{t1});"
          f"tl.from(q('.cl1'),{{yPercent:110,duration:.45,ease:'expo.out'}},{t1 + .3}).from(q('.cv1'),{{yPercent:110,duration:.55,ease:'expo.out'}},{t1 + .35});"
          f"if(q('.cs1'))tl.from(q('.cs1'),{{yPercent:110,duration:.45,ease:'expo.out'}},{t1 + .45});")
    return html, js, SWISS_CSS


def sw_checklist(sc, V, P, panel=None):
    """tiêu đề lớn gạch chân tự vẽ; từng dòng: số thứ tự to màu nhấn + chữ lộ bằng mặt nạ + đường kẻ mảnh + dấu tích vẽ nét."""
    items = [(t if isinstance(t, str) else t.get("text", "")) for t in (sc.get("items") or [])[:5]]
    W = 900 if V else 1300
    x0, y0 = (90, 460) if V else (310, 220)
    title = sc.get("title", "")
    rows = ""
    for i, t in enumerate(items):
        rows += (f'<div class="cr cr{i}" style="position:relative;display:flex;align-items:center;gap:{px(30)};padding:{px(30)} 0">'
                 f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion><i class=cn{i} style="font-weight:800;font-size:{px(64)};color:var(--acc);width:{px(110)};display:block">{i + 1:02d}</i></div>'
                 f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion style="flex:1"><i class=ct{i} style="font-family:\'Be Vietnam Pro\';font-weight:700;font-size:{px(_fit(t, 50, 24 if V else 34))}">{E(t)}</i></div>'
                 f'<svg width="{px(64)}" height="{px(64)}" viewBox="0 0 64 64"><path class=ck{i} d="M8,34 L26,52 L58,12" fill=none stroke="{P["ink"]}" stroke-width=9 /></svg>'
                 f'<div class="rule rr{i}" style="position:absolute;left:0;right:0;bottom:0;height:2px;opacity:.25"></div></div>')
    head = (f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion><i class=clt style="font-weight:800;font-size:{px(_fit(title, 96, 16 if V else 24))};letter-spacing:-.03em;line-height:1.05">{E(title)}</i></div>'
            f'<div class="rule cu" style="width:{px(200)};margin:{px(28)} 0 {px(20)};background:var(--acc)"></div>') if title else ""
    html = _wrap(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">{head}{rows}</div>', panel)
    js = ("tl.from(q('.clt'),{yPercent:110,duration:.55,ease:'expo.out'},.05).from(q('.cu'),{scaleX:0,duration:.5,ease:'expo.out'},.25);" if title else "")
    for i in range(len(items)):
        t = _at(sc, i, .45 + i * .4)
        js += (f"{{const c=q('.ck{i}'),L=c.getTotalLength();c.style.strokeDasharray=L;c.style.strokeDashoffset=L;"
               f"tl.from(q('.rr{i}'),{{scaleX:0,duration:.5,ease:'expo.out'}},{t}).from(q('.cn{i}'),{{yPercent:110,duration:.45,ease:'expo.out'}},{t})"
               f".from(q('.ct{i}'),{{yPercent:110,duration:.5,ease:'expo.out'}},{t + .06}).to(c,{{strokeDashoffset:0,duration:.3,ease:'power2.out'}},{t + .35})}}")
    return html, js, SWISS_CSS


def sw_headline(sc, V, P, panel=None):
    """chữ to căn trái: một vệt màu nhấn quét qua rồi rút đi để lộ chữ (wipe kiểu báo thiết kế), dòng phụ lộ từ dưới."""
    text = str(sc.get("text", ""))
    sub = sc.get("sub", "")
    size = _fit(text, 150 if V else 140, 10 if V else 18)
    x0, y0 = (90, 640) if V else (160, 380)
    t = _at(sc, 0, .15)
    html = _wrap(P, f'<div style="position:absolute;left:{px(x0)};right:{px(x0)};top:{px(y0)}">'
                    f'<div style="position:relative;display:inline-block"><div class=hx style="font-weight:800;font-size:{px(size)};line-height:1.02;letter-spacing:-.03em">{E(text)}</div>'
                    f'<div class=hw style="position:absolute;left:-2%;right:-2%;top:0;bottom:0;background:var(--acc);transform-origin:0 50%"></div></div>'
                    + (f'<div class=m data-layout-allow-overflow data-layout-allow-occlusion style="margin-top:{px(30)}"><i class=hs style="font-family:\'Be Vietnam Pro\';font-weight:600;font-size:{px(50)};opacity:.8">{E(sub)}</i></div>' if sub else "")
                    + '</div>', panel)
    js = (f"tl.set(q('.hx'),{{opacity:0}},0).fromTo(q('.hw'),{{scaleX:0}},{{scaleX:1,duration:.4,ease:'expo.in'}},{t})"
          f".set(q('.hx'),{{opacity:1}},{t + .4}).set(q('.hw'),{{transformOrigin:'100% 50%'}},{t + .4})"
          f".to(q('.hw'),{{scaleX:0,duration:.45,ease:'expo.out'}},{t + .4});"
          + (f"tl.from(q('.hs'),{{yPercent:110,duration:.5,ease:'expo.out'}},{t + .7});" if sub else ""))
    return html, js, SWISS_CSS


# ------------------------------------------------------------------ chung: chuyển loại cảnh ít dùng sang mẫu của pack
def _num(sc):
    d = int(sc.get("decimals", 0))
    s = f"{float(sc.get('value_to', 0)):,.{d}f}"
    return s if sc.get("locale") == "en" else s.replace(",", "X").replace(".", ",").replace("X", ".")


def _adapters(T):
    """drum / flipstack → chữ động; doc → tiêu đề; pipeline → danh sách bước — đều bằng ngữ pháp của chính pack."""
    def drum(sc, V, P):
        items = [sc.get("lead")] + list(sc.get("items") or []) if sc.get("lead") else list(sc.get("items") or [])
        at = list(sc.get("at") or [])
        if sc.get("lead") and len(at) < len(items):
            at = [max(0.1, (at[0] if at else .4) - .35)] + at
        lines = [{"text": str(t), "at": at[k] if k < len(at) else .2 + k * .8, "hl": str(t) if k == len(items) - 1 else None}
                 for k, t in enumerate(items) if t]
        return T["kinetic"](dict(sc, lines=lines), V, P)

    def doc(sc, V, P, panel=None):
        return T["headline"](dict(sc, text=sc.get("highlight") or sc.get("title", ""),
                                  sub=" · ".join(x for x in (sc.get("title"), sc.get("heading")) if x)), V, P, panel)

    def pipeline(sc, V, P):
        items = [((sc.get(k) or {}).get("label") or "") for k in ("input", "engine", "output")]
        html, js, css = T["checklist"](dict(sc, items=[x for x in items if x] or ["…"], title=sc.get("title", ""), _steps=True), V, P,
                                       (0, 0, 1080 if V else 1920, 1920 if V else 1080))
        return html, js, css
    out = dict(T)
    out.setdefault("drum", drum)
    out.setdefault("flipstack", drum)
    out.setdefault("doc", doc)
    out.setdefault("pipeline", pipeline)
    out.setdefault("spring", T["headline"])
    return out


# ------------------------------------------------------------------ BẢN TIN (Bất động sản) — dải bảng tin, quét ngang, in hoa hẹp
NEWS_CSS = SWISS_CSS + """
.nw{text-transform:uppercase}
.nw .bar{position:absolute;background:var(--acc);transform-origin:0 50%}
.nw .strip{position:relative;display:inline-block;padding:.12em .32em .06em;background:var(--strip);color:var(--ink);overflow:hidden}
.nw .strip.a{background:var(--acc);color:var(--paper)}
.nw .tick{font-family:'Be Vietnam Pro',sans-serif;font-weight:700;letter-spacing:.2em}
"""


def _nw(P, inner, panel=None):
    return _wrap(dict(P), f'<div class=nw style="position:absolute;inset:0;--strip:{P.get("strip", "#18294A")}">{inner}</div>', panel)


def nw_kinetic(sc, V, P):
    lines = [x if isinstance(x, dict) else {"text": str(x)} for x in (sc.get("lines") or [])][:5]
    left, top = (70, 560) if V else (140, 300)
    rows, js = "", ""
    for i, L in enumerate(lines):
        t = round(float(L.get("at", .2 + i * .9)), 3)
        a = " a" if L.get("hl") and str(L["hl"]).upper() in str(L["text"]).upper() else ""
        size = _fit(L["text"], 120 if V else 110, 14 if V else 24)
        rows += (f'<div style="margin-bottom:{px(20)}"><span class="strip{a} s{i}" style="font-weight:700;font-size:{px(size)};line-height:1.05">'
                 f'<span class=st{i} style="display:inline-block">{E(L["text"])}</span></span></div>')
        js += (f"tl.fromTo(q('.s{i}'),{{clipPath:'inset(0 100% 0 0)'}},{{clipPath:'inset(0 0% 0 0)',duration:.45,ease:'power4.out'}},{t})"
               f".from(q('.st{i}'),{{x:-60,duration:.6,ease:'power4.out'}},{t});")
        if i >= 3:
            js += (f"tl.to(q('.ks'),{{y:'-={150 if V else 140}',duration:.4,ease:'power4.inOut'}},{t - .05});"
                   + (f"tl.to([q('.tk'),q('.b0')],{{opacity:0,duration:.2}},{t - .1});" if i == 3 else ""))
    W = 1080 if V else 1920
    H = 1920 if V else 1080
    deco = (f'<div class="bar b0" style="left:0;top:{px(top - 90)};width:{px(W * .55)};height:{px(14)}"></div>'
            f'<div class="tick tk" style="position:absolute;left:{px(left)};top:{px(top - 150)};font-size:{px(32)};color:var(--acc)">{E(sc.get("tag", "TIÊU ĐIỂM"))}</div>')
    html = _nw(P, deco + f'<div class=ks style="position:absolute;left:{px(left)};right:{px(left)};top:{px(top)}">{rows}</div>', (0, 0, W, H))
    js = ("tl.from(q('.b0'),{scaleX:0,duration:.5,ease:'power4.out'},0).from(q('.tk'),{x:-80,opacity:0,duration:.4,ease:'power4.out'},.1);") + js
    return html, js, NEWS_CSS


def nw_money(sc, V, P, panel=None):
    h = max(float(sc.get("hit_at", 1.5)), .9)
    s = _num(sc)
    pre, unit = str(sc.get("prefix", "") or ""), str(sc.get("unit", "") or "")
    size = min(220, int((900 if V else 1300) / (0.5 * max(1, len(pre + s)))))
    x, y = (70, 620) if V else (140, 300)
    vt, vf, d = float(sc.get("value_to", 0)), float(sc.get("value_from", 0)), int(sc.get("decimals", 0))
    html = _nw(P, f'<div style="position:absolute;left:{px(x)};top:{px(y)}">'
                  f'<div class="tick mt" style="font-size:{px(34)};color:var(--acc);margin-bottom:{px(18)}">{E(sc.get("title", ""))}</div>'
                  f'<div class="strip nb" style="font-weight:700;font-size:{px(size)};line-height:1"><span class=nv>{E(pre)}{E(s)}</span>'
                  f'<span style="font-size:.4em;margin-left:.2em">{E(unit)}</span></div>'
                  f'<div class="bar nu" style="position:relative;height:{px(16)};width:100%;margin-top:{px(10)}"></div>'
                  + (f'<div class="tick ns" style="font-size:{px(36)};margin-top:{px(22)};letter-spacing:.06em;text-transform:none;opacity:.85">{E(sc.get("sub"))}</div>' if sc.get("sub") else "")
                  + '</div>', panel)
    loc = "en-US" if sc.get("locale") == "en" else "vi-VN"
    js = (f"tl.from(q('.mt'),{{x:-80,opacity:0,duration:.4,ease:'power4.out'}},0)"
          f".fromTo(q('.nb'),{{clipPath:'inset(0 100% 0 0)'}},{{clipPath:'inset(0 0% 0 0)',duration:.5,ease:'power4.out'}},.1)"
          f".from(q('.nu'),{{scaleX:0,transformOrigin:'0 50%',duration:{h:.2f},ease:'none'}},.2);"
          f"const o={{v:{vf}}};tl.to(o,{{v:{vt},duration:{max(.5, h - .25):.2f},ease:'power3.out',onUpdate:()=>q('.nv').textContent={json.dumps(pre)}+"
          f"o.v.toLocaleString('{loc}',{{minimumFractionDigits:{d},maximumFractionDigits:{d}}})}},.2);"
          f"tl.fromTo(q('.nb'),{{x:0}},{{x:14,duration:.05,yoyo:true,repeat:3,immediateRender:false}},{h});"
          + ("tl.from(q('.ns'),{x:-60,opacity:0,duration:.4,ease:'power4.out'},.5);" if sc.get("sub") else ""))
    return html, js, NEWS_CSS


def nw_chart(sc, V, P, panel=None):
    vf, vt = float(sc.get("value_from", 0)), float(sc.get("value_to", 0))
    h = max(float(sc.get("hit_at", 2.0)), 1.0)
    n = 6
    W, H = (920, 620) if V else (1300, 520)
    x0, y0 = (80, 520) if V else (310, 250)
    hs = [0.25, 0.38, 0.33, 0.52, 0.66, 0.95] if vt >= vf else [0.95, 0.7, 0.74, 0.5, 0.4, 0.22]
    bw = W / n * 0.62
    bars = "".join(f'<div class="cb cb{k}" style="position:absolute;bottom:0;left:{px(k * W / n)};width:{px(bw)};height:{px(H * v)};'
                   f'background:{"var(--acc)" if k == n - 1 else "var(--strip)"};transform-origin:50% 100%"></div>' for k, v in enumerate(hs))
    sfx = str(sc.get("suffix", "%"))
    html = _nw(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">'
                  f'<div class="tick cl" style="font-size:{px(34)};color:var(--acc);margin-bottom:{px(24)}">{E(sc.get("label", ""))}</div>'
                  f'<div class=cv style="font-weight:700;font-size:{px(170)};line-height:1.1">{E(vf)}{E(sfx)}</div>'
                  f'<div style="position:relative;height:{px(H)};margin-top:{px(30)};border-bottom:{px(6)} solid var(--ink)">{bars}</div>'
                  f'<div class="tick ct" style="font-size:{px(32)};margin-top:{px(24)};letter-spacing:.08em">{E(sc.get("title", ""))}</div></div>', panel)
    js = (f"tl.from(q('.cl'),{{x:-60,opacity:0,duration:.4,ease:'power4.out'}},0).from(q('.ct'),{{x:-60,opacity:0,duration:.4,ease:'power4.out'}},.2);"
          f"tl.from(q('.cb'),{{scaleY:0,duration:.5,ease:'power4.out',stagger:{max(.08, (h - .8) / n):.2f}}},.25);"
          f"const o={{v:{vf}}};tl.to(o,{{v:{vt},duration:{h - .3:.2f},ease:'power2.inOut',onUpdate:()=>q('.cv').textContent=(Math.round(o.v*10)/10).toLocaleString('vi-VN')+{json.dumps(sfx)}}},.3);")
    return html, js, NEWS_CSS


def nw_compare(sc, V, P, panel=None):
    a, b = sc.get("a") or {}, sc.get("b") or {}
    W, ch = (940, 420) if V else (1500, 520)
    x0, y0 = (70, 420) if V else (210, 260)
    cards = ""
    for i, it in enumerate((a, b)):
        w = W if V else W / 2 - 40
        x, y = (0, i * (ch + 100)) if V else (i * (W / 2 + 40), 0)
        val = str(it.get("value", ""))
        cards += (f'<div class="cc cc{i}" style="position:absolute;left:{px(x)};top:{px(y)};width:{px(w)};height:{px(ch)};background:var(--strip);'
                  f'border-top:{px(14)} solid {"var(--acc)" if i else "var(--ink)"}">'
                  f'<div class=tick style="position:absolute;left:{px(44)};top:{px(40)};font-size:{px(34)};color:{"var(--acc)" if i else "var(--ink)"}">{E(it.get("label", "TRƯỚC" if not i else "SAU"))}</div>'
                  f'<div class=cv{i} style="position:absolute;left:{px(40)};bottom:{px(90 if it.get("sub") else 40)};font-weight:700;font-size:{px(_fit(val, 170, 8))};line-height:1;white-space:nowrap">{E(val)}</div>'
                  + (f'<div class=tick style="position:absolute;left:{px(44)};bottom:{px(36)};font-size:{px(30)};letter-spacing:.06em;text-transform:none;opacity:.8">{E(it.get("sub"))}</div>' if it.get("sub") else "")
                  + '</div>')
    vs = (f'<div class=vs style="position:absolute;left:{px(W / 2 - 70)};top:{px(ch + 50 - 70 if V else ch / 2 - 70)};width:{px(140)};height:{px(140)};'
          f'background:var(--acc);color:var(--paper);transform:rotate(45deg);display:flex;align-items:center;justify-content:center">'
          f'<span style="transform:rotate(-45deg);font-weight:700;font-size:{px(56)}">VS</span></div>')
    html = _nw(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">{cards}{vs}</div>', panel)
    t0, t1 = _at(sc, 0, .1), _at(sc, 1, .9)
    js = (f"tl.from(q('.cc0'),{{{'x' if V else 'y'}:{-1200 if V else 900},duration:.55,ease:'power4.out'}},{t0})"
          f".from(q('.vs'),{{scale:0,rotation:-180,duration:.45,ease:'power4.out'}},{max(t0 + .3, t1 - .35)})"
          f".from(q('.cc1'),{{{'x' if V else 'y'}:{1200 if V else 900},duration:.55,ease:'power4.out'}},{t1});")
    return html, js, NEWS_CSS


def nw_checklist(sc, V, P, panel=None):
    items = [(t if isinstance(t, str) else t.get("text", "")) for t in (sc.get("items") or [])[:5]]
    W = 940 if V else 1300
    x0, y0 = (70, 480) if V else (310, 240)
    rows = ""
    for i, t in enumerate(items):
        rows += (f'<div class="nr nr{i}" style="display:flex;align-items:stretch;margin-bottom:{px(22)};background:var(--strip)">'
                 f'<div style="flex:none;width:{px(120)};background:var(--acc);color:var(--paper);display:flex;align-items:center;justify-content:center;'
                 f'font-weight:700;font-size:{px(64)}">{i + 1}</div>'
                 f'<div style="padding:{px(30)} {px(34)};font-weight:700;font-size:{px(_fit(t, 54, 20 if V else 30))};line-height:1.1">{E(t)}</div></div>')
    title = sc.get("title", "")
    head = f'<div class="tick nt" style="font-size:{px(40)};color:var(--acc);margin-bottom:{px(30)}">{E(title)}</div>' if title else ""
    html = _nw(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">{head}{rows}</div>', panel)
    js = "tl.from(q('.nt'),{x:-80,opacity:0,duration:.4,ease:'power4.out'},0);" if title else ""
    for i in range(len(items)):
        t = _at(sc, i, .35 + i * .4)
        js += f"tl.from(q('.nr{i}'),{{x:{-1100 if i % 2 == 0 else 1100},duration:.5,ease:'power4.out'}},{t});"
    return html, js, NEWS_CSS


def nw_headline(sc, V, P, panel=None):
    text, sub = str(sc.get("text", "")), sc.get("sub", "")
    x0, y0 = (70, 700) if V else (140, 400)
    t = _at(sc, 0, .15)
    html = _nw(P, f'<div style="position:absolute;left:{px(x0)};right:{px(x0)};top:{px(y0)}">'
                  f'<div class="bar hb" style="position:relative;height:{px(18)};width:{px(260)};margin-bottom:{px(26)}"></div>'
                  f'<div class="strip a hs" style="font-weight:700;font-size:{px(_fit(text, 140, 12 if V else 20))};line-height:1.05">{E(text)}</div>'
                  + (f'<div><span class="strip hu" style="margin-top:{px(14)};font-weight:700;font-size:{px(48)}">{E(sub)}</span></div>' if sub else "")
                  + '</div>', panel)
    js = (f"tl.from(q('.hb'),{{scaleX:0,transformOrigin:'0 50%',duration:.35,ease:'power4.out'}},{t})"
          f".fromTo(q('.hs'),{{clipPath:'inset(0 100% 0 0)'}},{{clipPath:'inset(0 0% 0 0)',duration:.5,ease:'power4.out'}},{t + .15});"
          + (f"tl.fromTo(q('.hu'),{{clipPath:'inset(0 100% 0 0)'}},{{clipPath:'inset(0 0% 0 0)',duration:.45,ease:'power4.out'}},{t + .45});" if sub else ""))
    return html, js, NEWS_CSS


# ------------------------------------------------------------------ MỀM (Sức khỏe / Làm đẹp) — mờ → rõ, bay nhẹ, vòng tròn, thẻ bo tròn
SOFT_CSS = SWISS_CSS + """
.sf .cd{position:absolute;background:#fff;border-radius:calc(48px*var(--s));box-shadow:0 calc(24px*var(--s)) calc(60px*var(--s)) rgba(40,60,90,.14)}
.sf .pill{display:inline-block;padding:.25em .8em;border-radius:999px;background:var(--acc);color:#fff;font-family:'Be Vietnam Pro';font-weight:700}
.sf .bub{position:absolute;border-radius:50%;background:var(--acc);opacity:.10}
"""


def _sf(P, inner, panel=None):
    bubs = "".join(f'<div class="bub bu{k}" style="left:{px(x)};top:{px(y)};width:{px(r)};height:{px(r)}"></div>'
                   for k, (x, y, r) in enumerate(((-120, 180, 420), (760, 1300, 520), (820, 260, 220))))
    return _wrap(P, f'<div class=sf style="position:absolute;inset:0">{bubs}{inner}</div>', panel)


def _soft_in(sel, t, d=.8):
    return f"tl.from(q('{sel}'),{{opacity:0,y:40,filter:'blur(14px)',duration:{d},ease:'power2.out'}},{t});"


def sf_kinetic(sc, V, P):
    lines = [x if isinstance(x, dict) else {"text": str(x)} for x in (sc.get("lines") or [])][:4]
    rows, js = "", "tl.from(q('.bub'),{scale:0,duration:1.4,ease:'power2.out',stagger:.15},0);"
    for i, L in enumerate(lines):
        t = round(float(L.get("at", .2 + i * .9)), 3)
        ws = ""
        hlw = {x.strip("?!.,") for x in str(L.get("hl") or "").upper().split()}
        for j, w in enumerate(str(L["text"]).split()):
            hi = w.upper().strip("?!.,") in hlw
            ws += (f'<span class="sw{i} sw{i}_{j}" style="display:inline-block;margin:0 .14em;position:relative;{"color:var(--acc)" if hi else ""}">{E(w)}'
                   + (f'<svg style="position:absolute;left:0;bottom:-.18em;width:100%;height:.3em;overflow:visible" viewBox="0 0 100 20" preserveAspectRatio="none">'
                      f'<path class=ul{i} d="M2,14 C30,4 70,4 98,12" fill=none stroke="var(--acc)" stroke-width=7 stroke-linecap=round /></svg>' if hi else "") + '</span>')
        rows += f'<div style="font-weight:700;font-size:{px(_fit(L["text"], 110 if V else 100, 14 if V else 24))};line-height:1.2;margin-bottom:{px(24)}">{ws}</div>'
        js += f"tl.from(q('.sw{i}'),{{opacity:0,y:30,filter:'blur(12px)',duration:.7,ease:'power2.out',stagger:.09}},{t});"
        js += (f"document.querySelectorAll(sel+' .ul{i}').forEach(u=>{{const L=u.getTotalLength();u.style.strokeDasharray=L;u.style.strokeDashoffset=L;"
               f"tl.to(u,{{strokeDashoffset:0,duration:.6,ease:'power2.inOut'}},{t + .5})}});")
    W, H = (1080, 1920) if V else (1920, 1080)
    html = _sf(P, f'<div style="position:absolute;left:{px(80)};right:{px(80)};top:{px(620 if V else 300)};text-align:center">{rows}</div>', (0, 0, W, H))
    return html, js, SOFT_CSS


def sf_money(sc, V, P, panel=None):
    h = max(float(sc.get("hit_at", 1.5)), .9)
    vt, vf, d = float(sc.get("value_to", 0)), float(sc.get("value_from", 0)), int(sc.get("decimals", 0))
    pre, unit = str(sc.get("prefix", "") or ""), str(sc.get("unit", "") or "")
    R = 330
    cx, cy = (540, 900) if V else (960, 520)
    s = _num(sc)
    size = min(150, int(560 / (0.58 * max(1, len(pre + s)))))
    ring = (f'<svg style="position:absolute;left:{px(cx - R - 30)};top:{px(cy - R - 30)}" width="{px(2 * R + 60)}" height="{px(2 * R + 60)}" viewBox="0 0 {2 * R + 60} {2 * R + 60}">'
            f'<circle cx={R + 30} cy={R + 30} r={R} fill="#fff" stroke="var(--acc)" stroke-opacity=".15" stroke-width=26 />'
            f'<circle class=rg cx={R + 30} cy={R + 30} r={R} fill=none stroke="var(--acc)" stroke-width=26 stroke-linecap=round transform="rotate(-90 {R + 30} {R + 30})" /></svg>')
    mid = (f'<div style="position:absolute;left:{px(cx - R)};top:{px(cy - 120)};width:{px(2 * R)};text-align:center">'
           f'<div class=mv style="font-weight:700;font-size:{px(size)};line-height:1">{E(pre)}{E(s)}</div>'
           f'<div style="font-family:\'Be Vietnam Pro\';font-weight:700;font-size:{px(46)};margin-top:{px(10)};color:var(--acc)">{E(unit)}</div></div>')
    lab = (f'<div class=ml style="position:absolute;left:0;right:0;top:{px(cy + R + 70)};text-align:center"><span class=pill style="font-size:{px(40)}">{E(sc.get("title", ""))}</span>'
           + (f'<div style="font-family:\'Be Vietnam Pro\';font-weight:600;font-size:{px(40)};margin-top:{px(20)};opacity:.75">{E(sc.get("sub"))}</div>' if sc.get("sub") else "") + '</div>') if sc.get("title") or sc.get("sub") else ""
    html = _sf(P, ring + mid + lab, panel)
    C = 2 * 3.14159 * R
    loc = "en-US" if sc.get("locale") == "en" else "vi-VN"
    js = (f"const g=q('.rg');g.style.strokeDasharray={C:.0f};g.style.strokeDashoffset={C:.0f};"
          f"tl.from(q('svg'),{{scale:.85,opacity:0,filter:'blur(14px)',transformOrigin:'50% 50%',duration:.7,ease:'power2.out'}},0);"
          f"tl.to(g,{{strokeDashoffset:{C * 0.08:.0f},duration:{h - .2:.2f},ease:'sine.inOut'}},.2);"
          f"const o={{v:{vf}}};tl.to(o,{{v:{vt},duration:{h - .2:.2f},ease:'sine.inOut',onUpdate:()=>q('.mv').textContent={json.dumps(pre)}+o.v.toLocaleString('{loc}',{{minimumFractionDigits:{d},maximumFractionDigits:{d}}})}},.2);"
          + _soft_in(".ml", .5) + "tl.from(q('.bub'),{scale:0,duration:1.4,ease:'power2.out',stagger:.15},0);")
    return html, js, SOFT_CSS


def sf_chart(sc, V, P, panel=None):
    vt, vf = float(sc.get("value_to", 0)), float(sc.get("value_from", 0))
    sfx = str(sc.get("suffix", "%"))
    return sf_money(dict(sc, value_to=vt, value_from=vf, unit=sc.get("label", "") or sfx, prefix="",
                         decimals=1 if vt != int(vt) else 0, title=sc.get("title", ""), sub=sc.get("sub", "")), V, P, panel)


def sf_compare(sc, V, P, panel=None):
    a, b = sc.get("a") or {}, sc.get("b") or {}
    cw, ch = (820, 400) if V else (680, 520)
    pos = [((130, 470), (130, 1010)) if V else ((220, 280), (1020, 280))][0]
    cards = ""
    for i, it in enumerate((a, b)):
        x, y = pos[i]
        val = str(it.get("value", ""))
        cards += (f'<div class="cd sc{i}" style="left:{px(x)};top:{px(y)};width:{px(cw)};height:{px(ch)};text-align:center">'
                  f'<div style="margin-top:{px(46)}"><span class=pill style="font-size:{px(34)};{"background:var(--ink)" if not i else ""}">{E(it.get("label", "TRƯỚC" if not i else "SAU"))}</span></div>'
                  f'<div style="margin-top:{px(30)};font-weight:700;font-size:{px(_fit(val, 150, 8))};line-height:1;{"color:var(--acc)" if i else ""}">{E(val)}</div>'
                  + (f'<div style="font-family:\'Be Vietnam Pro\';font-weight:600;font-size:{px(36)};margin-top:{px(18)};opacity:.7">{E(it.get("sub"))}</div>' if it.get("sub") else "")
                  + '</div>')
    ax, ay = ((540, 900) if V else (950, 540))
    arrow = (f'<svg style="position:absolute;left:{px(ax - 60)};top:{px(ay - 60)};overflow:visible" width="{px(120)}" height="{px(120)}" viewBox="0 0 120 120">'
             f'<path class=sa d="{"M20,10 C80,30 80,80 60,110 M40,95 L60,112 L78,92" if V else "M10,80 C40,10 90,10 110,60 M92,50 L110,62 L118,42"}" fill=none stroke="var(--acc)" stroke-width=9 stroke-linecap=round stroke-linejoin=round /></svg>')
    html = _sf(P, cards + arrow, panel)
    t0, t1 = _at(sc, 0, .1), _at(sc, 1, .9)
    js = (_soft_in(".sc0", t0) + f"{{const a=q('.sa'),L=a.getTotalLength();a.style.strokeDasharray=L;a.style.strokeDashoffset=L;"
          f"tl.to(a,{{strokeDashoffset:0,duration:.6,ease:'power2.inOut'}},{max(t0 + .4, t1 - .45)})}}" + _soft_in(".sc1", t1)
          + "tl.from(q('.bub'),{scale:0,duration:1.4,ease:'power2.out',stagger:.15},0);")
    return html, js, SOFT_CSS


def sf_checklist(sc, V, P, panel=None):
    items = [(t if isinstance(t, str) else t.get("text", "")) for t in (sc.get("items") or [])[:5]]
    W = 880 if V else 1200
    x0, y0 = (100, 500) if V else (360, 240)
    rows = ""
    for i, t in enumerate(items):
        rows += (f'<div class="cd sr sr{i}" style="position:relative;display:flex;align-items:center;gap:{px(30)};padding:{px(28)} {px(36)};margin-bottom:{px(26)};border-radius:999px">'
                 f'<svg width="{px(76)}" height="{px(76)}" viewBox="0 0 76 76" style="flex:none"><circle cx=38 cy=38 r=34 fill=none stroke="var(--acc)" stroke-width=5 />'
                 f'<circle class=sk{i} cx=38 cy=38 r=34 fill="var(--acc)" /><path class=sp{i} d="M22,39 L34,51 L55,27" fill=none stroke="#fff" stroke-width=7 stroke-linecap=round stroke-linejoin=round /></svg>'
                 f'<div style="font-family:\'Be Vietnam Pro\';font-weight:700;font-size:{px(_fit(t, 48, 22 if V else 32))}">{E(t)}</div></div>')
    title = sc.get("title", "")
    head = f'<div class=st style="font-weight:700;font-size:{px(_fit(title, 88, 16))};margin-bottom:{px(36)};text-align:center">{E(title)}</div>' if title else ""
    html = _sf(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">{head}{rows}</div>', panel)
    js = (_soft_in(".st", 0) if title else "") + "tl.from(q('.bub'),{scale:0,duration:1.4,ease:'power2.out',stagger:.15},0);"
    for i in range(len(items)):
        t = _at(sc, i, .4 + i * .45)
        js += (_soft_in(f".sr{i}", t, .6) + f"tl.from(q('.sk{i}'),{{scale:0,transformOrigin:'50% 50%',duration:.4,ease:'back.out(2)'}},{t + .35});"
               f"{{const c=q('.sp{i}'),L=c.getTotalLength();c.style.strokeDasharray=L;c.style.strokeDashoffset=L;tl.to(c,{{strokeDashoffset:0,duration:.3}},{t + .55})}}")
    return html, js, SOFT_CSS


def sf_headline(sc, V, P, panel=None):
    text, sub = str(sc.get("text", "")), sc.get("sub", "")
    t = _at(sc, 0, .15)
    html = _sf(P, f'<div style="position:absolute;left:{px(80)};right:{px(80)};top:{px(720 if V else 380)};text-align:center">'
                  f'<div style="position:relative;display:inline-block"><div class=hm style="position:absolute;left:-4%;right:-4%;top:46%;bottom:2%;background:var(--acc);opacity:.25;border-radius:999px;transform-origin:0 50%"></div>'
                  f'<div class=ht style="position:relative;font-weight:700;font-size:{px(_fit(text, 130, 12 if V else 20))};line-height:1.1">{E(text)}</div></div>'
                  + (f'<div class=hs style="font-family:\'Be Vietnam Pro\';font-weight:600;font-size:{px(48)};margin-top:{px(26)};opacity:.75">{E(sub)}</div>' if sub else "") + '</div>', panel)
    js = (_soft_in(".ht", t, .9) + f"tl.from(q('.hm'),{{scaleX:0,duration:.7,ease:'power2.inOut'}},{t + .4});" + (_soft_in(".hs", t + .6) if sub else "")
          + "tl.from(q('.bub'),{scale:0,duration:1.4,ease:'power2.out',stagger:.15},0);")
    return html, js, SOFT_CSS


# ------------------------------------------------------------------ POP (F&B / Giáo dục) — nhãn dán, đập nghiêng, nảy đàn hồi
POP_CSS = SWISS_CSS + """
.pp{text-transform:uppercase}
.pp .stk{position:absolute;background:#fff;color:#111;border:calc(7px*var(--s)) solid #111;border-radius:calc(22px*var(--s));box-shadow:calc(14px*var(--s)) calc(14px*var(--s)) 0 #111}
.pp .tag{display:inline-block;padding:.12em .45em;background:var(--acc);color:#111;border:calc(6px*var(--s)) solid #111;border-radius:calc(14px*var(--s));box-shadow:calc(8px*var(--s)) calc(8px*var(--s)) 0 #111}
.pp .out{color:#fff;-webkit-text-stroke:calc(7px*var(--s)) #111;paint-order:stroke fill;text-shadow:calc(8px*var(--s)) calc(8px*var(--s)) 0 #111}
"""


def _pp(P, inner, panel=None):
    return _wrap(P, f'<div class=pp style="position:absolute;inset:0">{inner}</div>', panel)


def _slam(sel, t, rot=-8):
    return f"tl.from(q('{sel}'),{{scale:2.4,rotation:{rot},opacity:0,duration:.45,ease:'elastic.out(1,.55)'}},{t});"


def pp_kinetic(sc, V, P):
    lines = [x if isinstance(x, dict) else {"text": str(x)} for x in (sc.get("lines") or [])][:4]
    rows, js = "", ""
    for i, L in enumerate(lines):
        t = round(float(L.get("at", .2 + i * .9)), 3)
        hlw = {x.strip("?!.,") for x in str(L.get("hl") or "").upper().split()}
        ws = ""
        for j, w in enumerate(str(L["text"]).split()):
            hi = w.upper().strip("?!.,") in hlw
            r = ((i * 3 + j * 5) % 7 - 3) * 1.6
            ws += f'<span class="{"tag" if hi else "out"} pw{i}" style="display:inline-block;margin:.08em .12em;transform:rotate({r:.1f}deg)">{E(w)}</span>'
        rows += f'<div style="font-weight:400;font-size:{px(_fit(L["text"], 150 if V else 130, 11 if V else 20))};line-height:1.1">{ws}</div>'
        js += f"tl.from(q('.pw{i}'),{{scale:2.2,rotation:-12,opacity:0,duration:.5,ease:'elastic.out(1,.55)',stagger:.08}},{t});"
    W, H = (1080, 1920) if V else (1920, 1080)
    html = _pp(P, f'<div style="position:absolute;left:{px(60)};right:{px(60)};top:{px(560 if V else 260)};text-align:center">{rows}</div>', (0, 0, W, H))
    return html, js, POP_CSS


def pp_money(sc, V, P, panel=None):
    h = max(float(sc.get("hit_at", 1.5)), .9)
    vt, vf, d = float(sc.get("value_to", 0)), float(sc.get("value_from", 0)), int(sc.get("decimals", 0))
    pre, unit = str(sc.get("prefix", "") or ""), str(sc.get("unit", "") or "")
    s = _num(sc)
    cx, cy = (540, 880) if V else (960, 500)
    R = 380
    import math
    pts = " ".join(f"{R + (R if k % 2 == 0 else R * .84) * math.cos(k * math.pi / 14):.0f},{R + (R if k % 2 == 0 else R * .84) * math.sin(k * math.pi / 14):.0f}" for k in range(28))
    burst = (f'<svg class=bs style="position:absolute;left:{px(cx - R)};top:{px(cy - R)}" width="{px(2 * R)}" height="{px(2 * R)}" viewBox="0 0 {2 * R} {2 * R}">'
             f'<polygon points="{pts}" fill="var(--acc)" stroke="#111" stroke-width=10 /></svg>')
    size = min(190, int(620 / (0.5 * max(1, len(pre + s)))))
    mid = (f'<div class=bm style="position:absolute;left:{px(cx - R)};top:{px(cy - 110)};width:{px(2 * R)};text-align:center;transform:rotate(-6deg)">'
           f'<div class="out mv" style="font-size:{px(size)};line-height:1">{E(pre)}{E(s)}</div>'
           f'<div style="font-size:{px(60)};color:#111;margin-top:{px(6)}">{E(unit)}</div></div>')
    lab = (f'<div style="position:absolute;left:0;right:0;top:{px(cy + R + 40)};text-align:center"><span class="tag ml" style="font-size:{px(52)};background:#fff">{E(sc.get("title") or sc.get("sub"))}</span></div>'
           if sc.get("title") or sc.get("sub") else "")
    loc = "en-US" if sc.get("locale") == "en" else "vi-VN"
    html = _pp(P, burst + mid + lab, panel)
    js = (f"tl.from(q('.bs'),{{scale:0,rotation:-90,duration:.6,ease:'back.out(2)'}},0).to(q('.bs'),{{rotation:20,duration:{h + 2},ease:'none'}},.6);"
          + _slam(".bm", .25, 10) + (_slam(".ml", .55, -6) if lab else "")
          + f"const o={{v:{vf}}};tl.to(o,{{v:{vt},duration:{max(.5, h - .3):.2f},ease:'power3.out',onUpdate:()=>q('.mv').textContent={json.dumps(pre)}+o.v.toLocaleString('{loc}',{{minimumFractionDigits:{d},maximumFractionDigits:{d}}})}},.3);"
          f"tl.fromTo(q('.bm'),{{scale:1}},{{scale:1.18,duration:.12,yoyo:true,repeat:1,ease:'power2.out',immediateRender:false}},{h});")
    return html, js, POP_CSS


def pp_chart(sc, V, P, panel=None):
    vf, vt = float(sc.get("value_from", 0)), float(sc.get("value_to", 0))
    h = max(float(sc.get("hit_at", 2.0)), 1.0)
    W, H = (900, 600) if V else (1200, 500)
    x0, y0 = (90, 560) if V else (360, 260)
    hs = [0.3, 0.55, 0.95] if vt >= vf else [0.95, 0.6, 0.3]
    bw = W / 3 * 0.7
    sfx = str(sc.get("suffix", "%"))
    bars = "".join(f'<div class="stk pb pb{k}" style="bottom:0;left:{px(k * W / 3)};width:{px(bw)};height:{px(H * v)};{"background:var(--acc)" if k == 2 else ""}"></div>' for k, v in enumerate(hs))
    html = _pp(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">'
                  f'<div style="text-align:center;margin-bottom:{px(40)}"><span class="tag pt" style="font-size:{px(120)};line-height:1"><span class=pv>{E(vf)}{E(sfx)}</span></span>'
                  f'<div class="out pl" style="font-size:{px(52)};margin-top:{px(20)}">{E(sc.get("label", ""))}</div></div>'
                  f'<div style="position:relative;height:{px(H)}">{bars}</div></div>', panel)
    js = (_slam(".pt", .1, -10) + _slam(".pl", .3, 6)
          + f"tl.from(q('.pb'),{{y:-1600,duration:.6,ease:'bounce.out',stagger:{max(.15, (h - .9) / 3):.2f}}},.3);"
          f"const o={{v:{vf}}};tl.to(o,{{v:{vt},duration:{h - .3:.2f},ease:'power2.inOut',onUpdate:()=>q('.pv').textContent=Math.round(o.v)+{json.dumps(sfx)}}},.3);")
    return html, js, POP_CSS


def pp_compare(sc, V, P, panel=None):
    a, b = sc.get("a") or {}, sc.get("b") or {}
    cw, ch = (760, 420) if V else (640, 520)
    pos = ((110, 440), (210, 1000)) if V else ((260, 270), (1020, 270))
    cards = ""
    for i, it in enumerate((a, b)):
        x, y = pos[i]
        val = str(it.get("value", ""))
        cards += (f'<div class="stk pc{i}" style="left:{px(x)};top:{px(y)};width:{px(cw)};height:{px(ch)};text-align:center;transform:rotate({-4 if not i else 3}deg);{"background:var(--acc)" if i else ""}">'
                  f'<div style="margin-top:{px(40)};font-size:{px(48)}">{E(it.get("label", "TRƯỚC" if not i else "SAU"))}</div>'
                  f'<div class=out style="margin-top:{px(20)};font-size:{px(_fit(val, 170, 7))};line-height:1">{E(val)}</div>'
                  + (f'<div style="font-size:{px(36)};margin-top:{px(16)}">{E(it.get("sub"))}</div>' if it.get("sub") else "") + '</div>')
    vx, vy = (540, 905) if V else (960, 540)
    vs = f'<div class="tag pv" style="position:absolute;left:{px(vx - 90)};top:{px(vy - 70)};font-size:{px(90)};background:#fff;transform:rotate(-8deg)">VS</div>'
    html = _pp(P, cards + vs, panel)
    t0, t1 = _at(sc, 0, .1), _at(sc, 1, .9)
    js = _slam(".pc0", t0, -14) + _slam(".pv", max(t0 + .3, t1 - .3), 20) + _slam(".pc1", t1, 14)
    return html, js, POP_CSS


def pp_checklist(sc, V, P, panel=None):
    items = [(t if isinstance(t, str) else t.get("text", "")) for t in (sc.get("items") or [])[:4]]
    W = 860 if V else 1200
    x0, y0 = (110, 460) if V else (360, 220)
    title = sc.get("title", "")
    head = f'<div style="text-align:center;margin-bottom:{px(40)}"><span class="tag pt" style="font-size:{px(_fit(title, 84, 14))}">{E(title)}</span></div>' if title else ""
    rows = "".join(f'<div class="stk pr pr{i}" style="position:relative;display:block;padding:{px(26)} {px(40)};margin-bottom:{px(36)};font-size:{px(_fit(t, 60, 18 if V else 28))};'
                   f'transform:rotate({(-2 if i % 2 else 2)}deg)">{E(t)}<span class="ps ps{i}" data-layout-allow-overflow data-layout-allow-overlap style="position:absolute;right:{px(-30)};top:{px(-34)};font-size:{px(86)};color:var(--acc);'
                   f'-webkit-text-stroke:{px(6)} #111;paint-order:stroke fill">✓</span></div>' for i, t in enumerate(items))
    html = _pp(P, f'<div style="position:absolute;left:{px(x0)};top:{px(y0)};width:{px(W)}">{head}{rows}</div>', panel)
    js = _slam(".pt", 0, -10) if title else ""
    for i in range(len(items)):
        t = _at(sc, i, .4 + i * .45)
        js += f"tl.from(q('.pr{i}'),{{x:{-1200 if i % 2 == 0 else 1200},rotation:{-20 if i % 2 == 0 else 20},duration:.5,ease:'back.out(1.6)'}},{t});" + _slam(f".ps{i}", t + .35, 25)
    return html, js, POP_CSS


def pp_headline(sc, V, P, panel=None):
    text, sub = str(sc.get("text", "")), sc.get("sub", "")
    t = _at(sc, 0, .15)
    chars = "".join(f'<span class=pch style="display:inline-block">{"&nbsp;" if c == " " else E(c)}</span>' for c in text)
    html = _pp(P, f'<div style="position:absolute;left:{px(60)};right:{px(60)};top:{px(700 if V else 380)};text-align:center">'
                  f'<div class=out style="font-size:{px(_fit(text, 160, 10 if V else 18))};line-height:1.05">{chars}</div>'
                  + (f'<div style="margin-top:{px(34)}"><span class="tag hs" style="font-size:{px(52)}">{E(sub)}</span></div>' if sub else "") + '</div>', panel)
    js = (f"tl.from(q('.pch'),{{y:-900,rotation:(i)=>(i*37)%80-40,duration:.7,ease:'bounce.out',stagger:.04}},{t});"
          + (_slam(".hs", t + .6, -8) if sub else ""))
    return html, js, POP_CSS


PACKS = {
    "swiss": _adapters({"kinetic": sw_kinetic, "money": sw_money, "chart": sw_chart, "compare": sw_compare,
                        "checklist": sw_checklist, "headline": sw_headline}),
    "news": _adapters({"kinetic": nw_kinetic, "money": nw_money, "chart": nw_chart, "compare": nw_compare,
                       "checklist": nw_checklist, "headline": nw_headline}),
    "soft": _adapters({"kinetic": sf_kinetic, "money": sf_money, "chart": sf_chart, "compare": sf_compare,
                       "checklist": sf_checklist, "headline": sf_headline}),
    "pop": _adapters({"kinetic": pp_kinetic, "money": pp_money, "chart": pp_chart, "compare": pp_compare,
                      "checklist": pp_checklist, "headline": pp_headline}),
}
FULL_KINDS = {"kinetic", "drum", "flipstack", "pipeline"}          # pack tự vẽ nền toàn khung


def has(pack: str | None, kind: str) -> bool:
    return bool(pack) and kind in PACKS.get(pack, {})


def layer(pack: str, sc: dict, W: int, H: int, D: float, P: dict) -> dict:
    V = H > W
    fn = PACKS[pack][sc["kind"]]
    panel = None
    if sc.get("_onmedia") and sc["kind"] not in FULL_KINDS:      # cảnh có ảnh/video phía sau → tấm giấy đặc che sau chữ
        panel = (40, 360, 1000, 1000) if V else (110, 160, 1700, 760)
    html, js, css = fn(sc, V, P) if sc["kind"] in FULL_KINDS else fn(sc, V, P, panel)
    root = f'<div class="root" style="--s:{min(W, H) / 1080}"><div class=content style="position:absolute;inset:0">{html}</div></div>'
    fit = ""
    if panel:
        fit = ("{const R=document.querySelector(sel+' .sw');let a=1e9,b=1e9,c=-1e9,d=-1e9;R.querySelectorAll(':scope>div').forEach(e=>{"
               "const r=e.getBoundingClientRect();if(r.width<2)return;a=Math.min(a,r.left);b=Math.min(b,r.top);c=Math.max(c,r.right);d=Math.max(d,r.bottom)});"
               "const o=R.getBoundingClientRect(),p=48;if(c>a)R.style.backgroundPosition=(a-o.left-p)+'px '+(b-o.top-p)+'px',"
               "R.style.backgroundSize=(c-a+2*p)+'px '+(d-b+2*p)+'px'}")
    fade = f"tl.to(q('.content'),{{opacity:0,duration:.25}},{max(0.5, D - 0.25)});" if sc["kind"] not in FULL_KINDS else ""
    return {"id": "mg", "type": "html", "start": 0, "duration": D, "x": 0, "y": 0, "anchor": "top-left", "w": W, "h": H,
            "html": root, "css": css + ".root{position:absolute;inset:0}",
            "js": "const q=s=>{const n=document.querySelectorAll(sel+' '+s);return n.length>1?n:n[0]};" + fit + js + fade}
