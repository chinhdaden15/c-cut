"""Motion Graphics thế hệ 2 cho Talking Head — cảnh có BỐ CỤC + CHUYỂN ĐỘNG (HyperFrames), nền đơn giản tinh tế.

plan.mg2 = [{"id", "kind", "start", "end" (frame timeline), "bg", "tone": "gold"|"blue"|"red", "colors": [c1, c2] (tuỳ chọn), …tham số}]
Cảnh 2.5–8s. App render mỗi cảnh một lần (HyperFrames, lưu đệm), ghép vào video; khổ dọc/ngang tự bố trí theo khung dự án.

Nền ("bg") — chỉ 6 kiểu đã duyệt (đơn giản, chữ dễ đọc; chọn 1–2 kiểu cho cả video, đổi màu theo chủ đề bằng "colors"):
  blur      video gốc làm mờ + tối (liền mạch với cảnh quay)      gradient  2 mảng màu loang trôi chậm + hạt grain
  cream     nền kem sáng, chữ tối (sạch, sang)                    charcoal  than chì tối + vignette + vệt sáng rất nhẹ
  dots      lưới chấm mờ dần ra mép                               spot      một màu chủ đạo + đèn rọi mềm sau nội dung
  none      không nền — CHỒNG lên người nói (chỉ cho iconrow, chips, custom kiểu chồng)

Kind (tham số):
  chart      value_from, value_to, suffix "%", label, title, sub, icon        — đồ thị tự vẽ, số chạy
  money      value_from, value_to, decimals, unit "tỷ" | prefix "$", title, sub, badge, icon — số tiền chạy + thẻ phụ
  notif      items [{icon, title, text}] (2–4)                                 — chồng thông báo trượt xuống
  question   lead "Câu hỏi:", text, sub, icon                                  — thẻ câu hỏi, icon 3D lật vào
  photos     title, images [{src, label}] (1–3), note "Hình ảnh minh họa"      — ảnh xếp nghiêng có nhãn
  doc        title, heading, highlight, icon                                   — tài liệu, dòng quan trọng tô sáng
  iconrow    icons [3d:…] (3–5), lead, text                                    — hàng huy hiệu tròn bật lên trên đầu (bg none)
  chips      items [{icon, text}] (2–4), side "left"|"right"                   — chip nhãn cạnh người nói (bg none)
  compare    a {label, value, sub}, b {label, value, sub}                      — trước / sau
  checklist  title, items [text…] (2–5)                                         — tích từng mục
  ("at": [giây từ đầu cảnh…] cho notif / iconrow / chips / checklist / photos — mỗi mục hiện đúng lúc nói)
  custom     html, css, js (GSAP: biến `tl`, `sel`) — Claude TỰ THIẾT KẾ theo chủ đề; dùng lớp sẵn .card .t1 .gold .blue .red .sub
             .chip .ic .sweep, biến --s (tỉ lệ khung), {{icon:3d:id}} → ảnh icon 3D. Giữ luật: nền đơn giản, ≤ 3 khối, chữ ≥ 34px×s.
Icon: "3d:<id>" từ kho chung (tra: python -m thagent.tools icon3d <từ khoá>) — chọn icon NHẬN RA NGAY đúng vật (giá nhà → nhà /
tiền giấy, không dùng túi tiền premium nhìn như quả bom). Ảnh: assets_web/ (luật ảnh như cảnh MG: đúng vật, nhãn minh hoạ, ≥1.8s).
Nhịp: video KHÔNG phải trình diễn vật → có MG khoảng mỗi 10s (preflight lỗi nếu nói > 12s không có MG, trừ đoạn trình diễn);
cảnh nền (≠ none) không nằm trong đoạn mở đầu / kết; mỗi video dùng ít nhất 4 kind khác nhau, không lặp kind liền nhau.
"""
from __future__ import annotations

import base64
import html as _h
import json
from functools import lru_cache
from pathlib import Path

import numpy as np

KINDS = {"chart", "money", "notif", "question", "photos", "doc", "iconrow", "chips", "compare", "checklist", "custom"}
BGS = {"blur", "gradient", "cream", "charcoal", "dots", "spot", "none"}
OVERLAY_KINDS = {"iconrow", "chips"}
TONES = {"gold": ("#FFE47A", "#FF9A1F", "#FFB000"), "blue": ("#A6EEFF", "#1E86FF", "#1E86FF"), "red": ("#FF9A86", "#FF2B3A", "#FF2B3A")}
GAP_S = 12.0

GRAIN = ("url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='300'><filter id='n'>"
         "<feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2'/></filter><rect width='100%' height='100%' filter='url(%23n)'"
         " opacity='0.55'/></svg>\")")


def _bgcss(bg: str, colors) -> str:
    c1, c2 = (colors or [None, None])[:2] if colors else (None, None)
    return {
        "gradient": f"background:radial-gradient(60% 40% at 20% 20%,{c1 or '#2B3F8F'} 0%,transparent 70%),"
                    f"radial-gradient(70% 45% at 85% 80%,{c2 or '#6B3A8F'} 0%,transparent 70%),#0E1424;",
        "cream": f"background:radial-gradient(80% 50% at 70% 15%,#FFFFFF 0%,transparent 70%),{c1 or '#F4EDE2'};",
        "charcoal": f"background:radial-gradient(45% 25% at 50% 15%,{c1 or 'rgba(255,176,0,.14)'} 0%,transparent 70%),"
                    "radial-gradient(120% 90% at 50% 50%,#1b1b1e 40%,#070708 100%);",
        "dots": f"background:radial-gradient(circle,{c1 or 'rgba(70,105,160,.55)'} 2.5px,transparent 3px) 0 0/48px 48px,{c2 or '#0F1A2E'};",
        "spot": f"background:radial-gradient(38% 24% at 50% 46%,{c1 or 'rgba(123,75,255,.6)'} 0%,transparent 70%),"
                f"radial-gradient(120% 90% at 50% 50%,{c2 or '#1A0F2E'} 40%,#0a0614 100%);",
    }.get(bg, "")


BASE_CSS = """
.root{position:absolute;inset:0;font-family:Montserrat,sans-serif;color:#fff}
.bg{position:absolute;inset:-4%}
.grain{position:absolute;inset:0;background-image:GRAIN;opacity:.10;mix-blend-mode:overlay}
.vig{position:absolute;inset:0;background:radial-gradient(120% 90% at 50% 50%,transparent 55%,rgba(0,0,0,.45))}
.card{position:absolute;border-radius:calc(40px*var(--s));background:rgba(12,14,24,.58);backdrop-filter:blur(26px);
  border:2px solid rgba(255,255,255,.14);box-shadow:0 calc(30px*var(--s)) calc(70px*var(--s)) rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.25);overflow:hidden}
.card>*{z-index:2}
.card:after{content:'';position:absolute;inset:0;z-index:1;background:linear-gradient(135deg,rgba(255,255,255,.16),transparent 40%);pointer-events:none}
.light .card{background:rgba(255,255,255,.94);color:#2a2320;border-color:rgba(0,0,0,.06)}
.sweep{position:absolute;z-index:1!important;top:0;bottom:0;width:30%;left:0;background:linear-gradient(100deg,transparent,rgba(255,255,255,.35),transparent);transform:skewX(-18deg)}
.t1{font-weight:900;letter-spacing:-.01em;line-height:1.02}
.gold{background:linear-gradient(#FFE47A,#FF9A1F);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 0 calc(18px*var(--s)) rgba(255,154,0,.55))}
.blue{background:linear-gradient(#A6EEFF,#1E86FF);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 0 calc(18px*var(--s)) rgba(30,144,255,.55))}
.red{background:linear-gradient(#FF9A86,#FF2B3A);-webkit-background-clip:text;color:transparent;filter:drop-shadow(0 0 calc(18px*var(--s)) rgba(255,43,58,.5))}
.light .gold{background:none;color:#D27A00;filter:none}.light .blue{background:none;color:#1767D8;filter:none}.light .red{background:none;color:#D61F2C;filter:none}
.sub{font-weight:600;opacity:.85}
.ic{position:absolute;filter:drop-shadow(0 calc(16px*var(--s)) calc(18px*var(--s)) rgba(0,0,0,.45))}
.chip{position:absolute;display:flex;align-items:center;gap:calc(14px*var(--s));padding:calc(14px*var(--s)) calc(28px*var(--s)) calc(14px*var(--s)) calc(14px*var(--s));
  border-radius:999px;background:rgba(12,14,24,.62);backdrop-filter:blur(18px);border:2px solid rgba(255,255,255,.2);font-weight:800;font-size:calc(46px*var(--s));white-space:nowrap}
.chip img{width:calc(74px*var(--s))}
""".replace("GRAIN", GRAIN)


@lru_cache(maxsize=256)
def _uri(path: str) -> str:
    p = Path(path)
    ext = p.suffix.lower().lstrip(".")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "png")
    return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()


def icon_uri(name: str | None) -> str:
    if not name:
        return ""
    from . import icons3d as K
    return _uri(str(K.path(name.removeprefix("3d:"), "color" if name.removeprefix("3d:") in _PREMIUM_BAD else "premium")))


_PREMIUM_BAD = {"money-bag", "bag", "money", "3d-coin", "wallet", "gift", "clock"}      # kiểu premium (ánh kim đen) khó nhận ra → dùng kiểu màu


def E(s) -> str:
    return _h.escape(str(s or ""))


def delays(sc: dict, n: int, first: float, gap: float) -> list[float]:
    """mốc hiện từng mục (giây từ đầu cảnh): "at" [giây…] đặt đúng lúc nói từng mục, thiếu thì lần lượt cách `gap`."""
    at = list(sc.get("at") or [])
    return [round(max(0.0, float(at[i])) if i < len(at) else first + i * gap, 3) for i in range(n)]


def fit(text, size: float, max_chars: int) -> float:
    """cỡ chữ vừa ô theo số ký tự (không cắt chữ — bộ kiểm HyperFrames chặn chữ bị cắt)."""
    n = len(str(text or ""))
    return size if n <= max_chars else max(size * 0.55, size * max_chars / n)


def _px(v) -> str:
    return f"calc({v}px*var(--s))"


# ---------------- mẫu: trả (html, js) ----------------
def _t_chart(sc, V, tone):
    w, h = (860, 760) if V else (980, 620)
    sfx = E(sc.get("suffix", "%"))
    html = f"""<div class=card style="left:calc(50% - {w/2}px*var(--s));top:calc(50% - {h/2}px*var(--s));width:{_px(w)};height:{_px(h)}">
<div style="position:absolute;left:{_px(50)};top:{_px(44)};display:flex;align-items:baseline;gap:{_px(14)}">
<span class="t1 {tone} pct" style="font-size:{_px(130)}">{E(sc.get('value_from', 0))}{sfx}</span><span class=sub style="font-size:{_px(46)}">{E(sc.get('label', ''))}</span></div>
<svg viewBox="0 0 100 60" preserveAspectRatio="none" style="position:absolute;left:8%;top:38%;width:84%;height:42%;z-index:2">
<path class=ln d="M0,55 C18,52 25,40 38,38 S58,30 68,20 S88,8 100,4" fill="none" stroke="{TONES[tone][1]}" stroke-width="1.6" stroke-linecap="round"/></svg>
<div class=sub style="position:absolute;left:{_px(50)};bottom:{_px(40)};font-size:{_px(38)}"><b>{E(sc.get('title', ''))}</b> {('· ' + E(sc['sub'])) if sc.get('sub') else ''}</div>
<div class=sweep></div></div>{f'<img class=ic src="{icon_uri(sc.get("icon"))}" style="width:{_px(210)};left:calc(50% + {w/2-150}px*var(--s));top:calc(50% - {h/2+90}px*var(--s))">' if sc.get('icon') else ''}"""
    vt, vf = float(sc.get("value_to", 0)), float(sc.get("value_from", 0))
    js = f"""const p=q('.ln');const L=p.getTotalLength();p.style.strokeDasharray=L;p.style.strokeDashoffset=L;
tl.from(q('.card'),{{y:80,scale:.9,opacity:0,duration:.5,ease:'back.out(1.6)'}},0.05).to(p,{{strokeDashoffset:0,duration:1.6,ease:'power2.inOut'}},.4);
if(q('.ic'))tl.from(q('.ic'),{{scale:0,rotation:-25,duration:.5,ease:'back.out(2)'}},.35);
const o={{v:{vf}}};tl.to(o,{{v:{vt},duration:1.6,ease:'power2.inOut',onUpdate:()=>q('.pct').textContent=Math.round(o.v)+'{sfx}'}},.4)
.fromTo(q('.sweep'),{{xPercent:-150}},{{xPercent:480,duration:.8,ease:'power1.inOut'}},2.1)"""
    return html, js


def _t_money(sc, V, tone):
    d = int(sc.get("decimals", 2))
    unit = E(sc.get("unit", ""))
    pre_ = E(sc.get("prefix", ""))
    vf, vt = float(sc.get("value_from", 0)), float(sc.get("value_to", 0))
    fmt = lambda v: f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    ic = f'<img class=ic src="{icon_uri(sc.get("icon"))}" style="width:{_px(280)};left:calc(50% - 140px*var(--s));top:calc(50% - 460px*var(--s))">' if sc.get("icon") else ""
    badge = f"""<div style="position:absolute;right:{_px(40)};top:{_px(48)};padding:{_px(12)} {_px(22)};border-radius:14px;background:{TONES[tone][2]};color:#1a1200;font-weight:900;font-size:{_px(38)}">{E(sc['badge'])}</div>""" if sc.get("badge") else ""
    html = f"""{ic}<div class="t1 {tone} num" style="position:absolute;width:100%;text-align:center;top:calc(50% - 150px*var(--s));font-size:{_px(170)}">{pre_}{fmt(vf)} {unit}</div>
<div class=card style="left:calc(50% - 420px*var(--s));top:calc(50% + 70px*var(--s));width:{_px(840)};height:{_px(190)}">
<div style="position:absolute;left:{_px(46)};top:{_px(36)};font-weight:800;font-size:{_px(fit(sc.get('title'), 54, 20 if sc.get('badge') else 26))};white-space:nowrap">{E(sc.get('title', ''))}</div>
<div class=sub style="position:absolute;left:{_px(46)};top:{_px(108)};font-size:{_px(36)}">{E(sc.get('sub', ''))}</div>{badge}<div class=sweep></div></div>"""
    js = f"""const o={{v:{vf}}};const f=v=>v.toLocaleString('vi-VN',{{minimumFractionDigits:{d},maximumFractionDigits:{d}}});
if(q('.ic'))tl.from(q('.ic'),{{y:-120,scale:.3,rotation:30,opacity:0,duration:.6,ease:'back.out(1.8)'}},0).to(q('.ic'),{{y:'-=18',duration:1.2,yoyo:true,repeat:1,ease:'sine.inOut'}},1.0);
tl.from(q('.num'),{{scale:1.5,opacity:0,duration:.4,ease:'power3.out'}},.2)
.to(o,{{v:{vt},duration:1.3,ease:'power3.out',onUpdate:()=>q('.num').textContent='{pre_}'+f(o.v)+' {unit}'}},.25)
.from(q('.card'),{{y:100,opacity:0,duration:.5,ease:'back.out(1.5)'}},.55).fromTo(q('.sweep'),{{xPercent:-150}},{{xPercent:480,duration:.8}},1.6)"""
    return html, js


def _t_notif(sc, V, tone):
    rows = (sc.get("items") or [])[:4]
    w = 900 if V else 860
    x = f"calc(50% - {w/2}px*var(--s))" if V else "calc(52%)"
    y0 = 260 if V else 170
    out = ""
    for i, it in enumerate(rows):
        out += f"""<div class="card n n{i}" style="left:{x};top:{_px(y0 + i*190)};width:{_px(w)};height:{_px(160)};border-radius:{_px(34)}">
{f'<img src="{icon_uri(it.get("icon"))}" style="position:absolute;left:{_px(26)};top:{_px(24)};width:{_px(112)}">' if it.get('icon') else ''}
<div style="position:absolute;left:{_px(160)};top:{_px(30)};font-weight:800;font-size:{_px(44)}">{E(it.get('title'))}</div>
<div class=sub style="position:absolute;left:{_px(160)};top:{_px(88)};font-size:{_px(fit(it.get('text'), 34, 36))};white-space:nowrap">{E(it.get('text'))}</div></div>"""
    js = "".join(f"tl.from(q('.n{i}'),{{y:-160,opacity:0,scale:.92,duration:.5,ease:'back.out(1.6)'}},{t});" for i, t in enumerate(delays(sc, len(rows), .15, .45)))
    return out, js


def _t_question(sc, V, tone):
    w = 860 if V else 900
    h = 860 if V else 760
    g = {"gold": "#FFB000,#FF6B3D", "blue": "#2E7BFF,#7B4BFF", "red": "#FF4B6B,#FF9A3D"}[tone]
    html = f"""<div class=card style="left:calc(50% - {w/2}px*var(--s));top:calc(50% - {h/2}px*var(--s));width:{_px(w)};height:{_px(h)}">
<div class=pnl style="position:absolute;left:{_px(40)};right:{_px(40)};top:{_px(40)};height:52%;border-radius:{_px(28)};background:linear-gradient(135deg,{g} 60%,#FFB86B)"></div>
{f'<img class=q src="{icon_uri(sc.get("icon") or "3d:f-red-question-mark")}" style="position:absolute;width:{_px(300)};left:calc(50% - 150px*var(--s));top:{_px(70)}">'}
<div style="position:absolute;left:{_px(50)};right:{_px(40)};bottom:{_px(36)};display:flex;flex-direction:column;gap:{_px(10)}">
<div style="font-style:italic;font-weight:600;font-size:{_px(52)};opacity:.9">{E(sc.get('lead', 'Câu hỏi:'))}</div>
<div class="t1 {tone}" style="font-size:{_px(fit(sc.get('text'), 64, 22))}">{E(sc.get('text'))}</div>
<div class=sub style="font-size:{_px(34)}">{E(sc.get('sub', ''))}</div></div></div></div>"""
    js = """tl.from(q('.card'),{y:90,opacity:0,scale:.92,duration:.55,ease:'back.out(1.5)'},0)
.from(q('.pnl'),{scaleY:0,transformOrigin:'50% 0',duration:.5,ease:'power3.out'},.25).from(q('.q'),{scale:0,rotationY:180,duration:.8,ease:'back.out(1.8)'},.45)
.to(q('.q'),{rotation:8,duration:.9,yoyo:true,repeat:2,ease:'sine.inOut'},1.25)"""
    return html, js


def _t_photos(sc, V, tone):
    ims = (sc.get("images") or [])[:3]
    out = ""
    n = len(ims)
    for i, im in enumerate(ims):
        rot = (-8, 6, -4)[i]
        if V:
            lx, ty, w = f"calc(50% - {330 - (i % 2)*80}px*var(--s))", 400 + i*(1100 // max(n, 1)) - (0 if n < 3 else 120), 560
        else:
            lx, ty, w = f"calc({30 + i*(40 // max(n - 1, 1)) - (10 if n == 1 else 0)}%)", 230 + (i % 2)*60, 620 if n < 3 else 520
        out += f"""<div class="ph ph{i}" style="position:absolute;left:{lx};top:{_px(ty)};width:{_px(w)};padding:{_px(18)} {_px(18)} {_px(80)};
background:#fff;border-radius:{_px(18)};box-shadow:0 {_px(30)} {_px(60)} rgba(60,40,20,.25);transform:rotate({rot}deg)">
<img src="{_uri(im['src'])}" style="width:100%;display:block;border-radius:{_px(10)};aspect-ratio:4/3;object-fit:cover">
<div style="position:absolute;left:0;right:0;bottom:{_px(18)};text-align:center;color:#3a2e25;font-weight:800;font-size:{_px(40)}">{E(im.get('label'))}</div></div>"""
    out += f"""<div class="t1 tt" style="position:absolute;width:100%;text-align:center;top:{_px(190 if V else 80)};color:#2a2320;font-size:{_px(fit(sc.get('title'), 96, 16 if V else 28))}">{E(sc.get('title', ''))}</div>
<div class=sub style="position:absolute;right:{_px(70)};bottom:{_px(60)};color:#6b5a48;font-size:{_px(26)}">{E(sc.get('note') or _label())}</div>"""
    js = "tl.from(q('.tt'),{y:-40,opacity:0,duration:.45,ease:'power3.out'},0);" + "".join(
        f"tl.from(q('.ph{i}'),{{x:{-500 if i % 2 == 0 else 500},rotation:{-30 if i % 2 == 0 else 30},opacity:0,duration:.65,ease:'back.out(1.3)'}},{t})"
        f".to(q('.ph{i}'),{{y:'{'-' if i % 2 == 0 else '+'}=14',duration:1.4,yoyo:true,repeat:1,ease:'sine.inOut'}},{t + .8});" for i, t in enumerate(delays(sc, n, .2, .35)))
    return out, js


def _label():
    from . import fonts as FT
    return FT.label()


def _t_doc(sc, V, tone):
    w, h = (840, 1000) if V else (820, 880)
    lines = lambda xs: "".join(f"<div style='height:{_px(22)};margin:{_px(22)} 0;border-radius:8px;background:#d9dde5;width:{x}%'></div>" for x in xs)
    html = f"""<div class=card style="left:calc(50% - {w/2}px*var(--s));top:calc(50% - {h/2}px*var(--s));width:{_px(w)};height:{_px(h)};background:#fff;color:#1d2330">
<div style="height:{_px(150)};background:{TONES[tone][2]};color:#1a1200;font-weight:900;font-size:{_px(fit(sc.get('title'), 54, 24))};display:flex;align-items:center;padding-left:{_px(50)}">{E(sc.get('title'))}</div>
<div style="padding:{_px(40)} {_px(50)}"><div style="font-weight:900;font-size:{_px(44)};margin-bottom:{_px(18)}">{E(sc.get('heading', ''))}</div>{lines((92, 80, 88))}
<div style="position:relative;font-weight:800;font-size:{_px(42)};margin:{_px(26)} 0"><span class=hl style="position:absolute;left:-2%;top:6%;height:88%;width:104%;background:#FFD54A;transform-origin:0 50%;z-index:0;border-radius:6px"></span>
<span style="position:relative;font-size:{_px(fit(sc.get('highlight'), 42, 30))}">{E(sc.get('highlight'))}</span></div>{lines((92, 80, 88, 70, 86))}</div></div>
{f'<img class=ic src="{icon_uri(sc.get("icon"))}" style="width:{_px(190)};left:calc(50% + {w/2-140}px*var(--s));top:calc(50% - {h/2+70}px*var(--s))">' if sc.get('icon') else ''}"""
    js = """tl.from(q('.card'),{y:140,rotation:-4,opacity:0,duration:.6,ease:'back.out(1.4)'},0).from(q('.hl'),{scaleX:0,duration:.6,ease:'power2.inOut'},.9);
if(q('.ic'))tl.from(q('.ic'),{scale:0,rotation:20,duration:.5,ease:'back.out(2)'},.5)"""
    return html, js


def _t_iconrow(sc, V, tone, face=None):
    ics = (sc.get("icons") or [])[:5]
    n = len(ics)
    W = 1080 if V else 1920
    cxs = [W / 2 + (i - (n - 1) / 2) * (210 if V else 200) for i in range(n)]
    top = (face[1] - 210) if face else (250 if V else 70)
    out = ""
    for i, (cx, ic) in enumerate(zip(cxs, ics)):
        out += f"""<div class="bd b{i}" style="position:absolute;left:{_px(cx - 85)};top:{_px(max(40, top))};width:{_px(170)};height:{_px(170)};border-radius:50%;
background:radial-gradient(circle at 35% 30%,{TONES[tone][0]},{TONES[tone][2]} 60%,#5a3a00);box-shadow:0 0 {_px(30)} {TONES[tone][2]}99,inset 0 -6px 12px rgba(0,0,0,.25);display:flex;align-items:center;justify-content:center">
<img src="{icon_uri(ic)}" style="width:66%"></div>"""
    ty = (face[3] + 40) if face else (1330 if V else 820)
    out += f"""<div style="position:absolute;width:100%;text-align:center;top:{_px(ty)}"><div class=sub style="font-size:{_px(50)};text-shadow:0 2px 12px #000">{E(sc.get('lead', ''))}</div>
<div class="t1 {tone} kk" style="font-size:{_px(fit(sc.get('text'), 104, 14 if V else 24))}">{E(sc.get('text', ''))}</div></div>"""
    ds = delays(sc, n, .1, .14)
    js = "".join(f"tl.from(q('.b{i}'),{{y:60,scale:0,duration:.45,ease:'back.out(2.2)'}},{t}).to(q('.b{i}'),{{y:-10,duration:.9,yoyo:true,repeat:2,ease:'sine.inOut'}},{t + .9});"
                 for i, t in enumerate(ds)) + f"tl.from(q('.kk'),{{scale:1.4,opacity:0,duration:.35,ease:'power3.out'}},{(ds[-1] if ds else 0) + .3});"
    return out, js


def _t_chips(sc, V, tone, face=None):
    its = (sc.get("items") or [])[:4]
    side = sc.get("side") or "left"
    W, H = (1080, 1920) if V else (1920, 1080)
    if face:
        y0 = face[3] + (40 if V else -260)
        x = 70 if side == "left" and V else (face[2] + 60 if not V and side == "right" else (70 if side == "left" else W - 520))
        if not V and side == "left":
            x = max(120, face[0] - 520)
    else:
        y0, x = (980, 70) if V else (380, 1280)
    out = "".join(f"""<div class="chip c{i}" style="left:{_px(x)};top:{_px(y0 + i*130)};border-color:{TONES[('gold', 'blue', 'red', 'gold')[i]][2]}88;font-size:{_px(fit(it.get('text'), 46, 18))}">
{f'<img src="{icon_uri(it.get("icon"))}">' if it.get('icon') else ''}{E(it.get('text'))}</div>""" for i, it in enumerate(its))
    d = -260 if (side == "left") else 260
    js = "".join(f"tl.from(q('.c{i}'),{{x:{d},opacity:0,duration:.5,ease:'back.out(1.6)'}},{t});" for i, t in enumerate(delays(sc, len(its), .15, .3)))
    return out, js


def _t_compare(sc, V, tone):
    cw, ch = (440, 520) if V else (520, 520)
    gap = 40 if V else 120
    out = ""
    for i, (k, col, bgc) in enumerate((("a", "red", "#FF2B3A"), ("b", "blue", "#1E86FF"))):
        it = sc.get(k) or {}
        left = f"calc(50% + {(-cw - gap/2) if i == 0 else gap/2}px*var(--s))"
        out += f"""<div class="card k{i}" style="left:{left};top:calc(50% - {ch/2}px*var(--s));width:{_px(cw)};height:{_px(ch)};text-align:center">
<div style="margin-top:{_px(60)};display:inline-block;padding:{_px(10)} {_px(30)};border-radius:999px;font-weight:900;font-size:{_px(40)};background:{bgc}">{E(it.get('label', 'TRƯỚC' if i == 0 else 'SAU'))}</div>
<div class="t1 {col}" style="margin-top:{_px(70)};font-size:{_px(fit(it.get('value'), 104, 7))};white-space:nowrap">{E(it.get('value'))}</div><div class=sub style="margin-top:{_px(30)};font-size:{_px(40)}">{E(it.get('sub', ''))}</div></div>"""
    out += f"""<div class=ar style="position:absolute;left:calc(50% - 50px*var(--s));top:calc(50% - 50px*var(--s));width:{_px(100)};height:{_px(100)};border-radius:50%;background:#FFB000;color:#000;
font-weight:900;font-size:{_px(64)};display:flex;align-items:center;justify-content:center;box-shadow:0 0 30px rgba(255,176,0,.6)">→</div>"""
    js = """tl.from(q('.k0'),{x:-200,opacity:0,duration:.5,ease:'back.out(1.5)'},.05).from(q('.ar'),{scale:0,duration:.4,ease:'back.out(2.5)'},.45)
.from(q('.k1'),{x:200,opacity:0,duration:.5,ease:'back.out(1.5)'},.7)"""
    return out, js


def _t_checklist(sc, V, tone):
    items = (sc.get("items") or [])[:5]
    w = 880 if V else 980
    h = 260 + len(items) * 130
    tk = icon_uri("3d:tick")
    rows = "".join(f"""<div class="r r{i}" style="display:flex;align-items:center;gap:{_px(26)};margin:{_px(30)} 0">
<div style="position:relative;flex:none;width:{_px(84)};height:{_px(84)};border-radius:{_px(22)};border:3px solid rgba(255,255,255,.35)">
<img class="tk tk{i}" src="{tk}" style="position:absolute;width:150%;left:-20%;top:-35%"></div>
<div style="font-weight:800;font-size:{_px(fit(t if isinstance(t, str) else t.get('text'), 52, 26 if V else 30))}">{E(t if isinstance(t, str) else t.get('text'))}</div></div>""" for i, t in enumerate(items))
    html = f"""<div class=card style="left:calc(50% - {w/2}px*var(--s));top:calc(50% - {h/2}px*var(--s));width:{_px(w)};height:{_px(h)};padding:{_px(50)} {_px(60)};box-sizing:border-box">
<div class="t1 {tone}" style="font-size:{_px(fit(sc.get('title'), 78, 18 if V else 22))};margin-bottom:{_px(10)}">{E(sc.get('title', ''))}</div>{rows}</div>"""
    js = "tl.from(q('.card'),{y:80,opacity:0,duration:.5,ease:'back.out(1.5)'},0);" + "".join(
        f"tl.from(q('.r{i}'),{{x:-80,opacity:0,duration:.35,ease:'power3.out'}},{t}).from(q('.tk{i}'),{{scale:0,rotation:-40,duration:.35,ease:'back.out(3)'}},{t + .2});"
        for i, t in enumerate(delays(sc, len(items), .35, .35)))
    return html, js


def _t_custom(sc, V, tone):
    import re
    html = re.sub(r"\{\{icon:(3d:[\w-]+)\}\}", lambda m: icon_uri(m.group(1)), sc.get("html", ""))
    return html, sc.get("js", "")


T = {"chart": _t_chart, "money": _t_money, "notif": _t_notif, "question": _t_question, "photos": _t_photos, "doc": _t_doc,
     "iconrow": _t_iconrow, "chips": _t_chips, "compare": _t_compare, "checklist": _t_checklist, "custom": _t_custom}


def beats(sc: dict, D: float) -> list[float]:
    """mốc có chuyển động bên trong cảnh (giây từ đầu) — cho bộ kiểm nhịp của Voice to Motion."""
    n = len(sc.get("items") or sc.get("icons") or sc.get("images") or [])
    out = [0.0, 0.5, 1.6] + (delays(sc, n, .3, .35) if n else [])
    return sorted({round(x, 2) for x in out if x < D})


def sfx(sc: dict, D: float) -> list[tuple[float, str, float]]:
    """SFX hợp từng mẫu (giây từ đầu cảnh, tên âm trong assets/sfx, dB): vào cảnh + từng mục + số chạy. Không whoosh."""
    k = sc.get("kind")
    out = [(0.0, "mgtrans_01" if full(sc) else "card_01", -14.0)]
    n = len(sc.get("items") or sc.get("icons") or sc.get("images") or [])
    if k in ("checklist",):
        out += [(t + 0.2, f"check_0{i % 6}", -15.0) for i, t in enumerate(delays(sc, n, .35, .35))]
    elif k in ("notif", "chips", "iconrow", "photos"):
        first, gap = {"notif": (.15, .45), "chips": (.15, .3), "iconrow": (.1, .14), "photos": (.2, .35)}[k]
        out += [(t + 0.05, f"pop_0{(i * 3) % 10}", -16.0) for i, t in enumerate(delays(sc, n, first, gap))]
    elif k == "money":
        out += [(0.3, "u_money", -15.0)]
    elif k == "chart":
        out += [(0.45, "tick_01", -16.0), (2.1, "soft_01", -17.0)]
    elif k == "compare":
        out += [(0.05, "pop_02", -16.0), (0.7, "pop_05", -16.0)]
    elif k in ("question", "doc"):
        out += [(0.5, "soft_00", -16.0)]
    return [(t, a, g) for t, a, g in out if t < D - 0.2]


def sound_events(plan) -> list:
    from .schema import SoundEvent
    out = []
    for sc in getattr(plan, "mg2", None) or []:
        if not sc.get("enabled", True):
            continue
        a0 = int(sc["start"])
        D = (int(sc["end"]) - a0) / plan.fps
        for i, (t, asset, g) in enumerate(sfx(sc, D)):
            out.append(SoundEvent(id=f"mg2_{sc['id']}_{i}", asset=asset, linked_event=sc["id"], hit=a0 + int(round(t * plan.fps)),
                                  gain_db=g, priority=5 if i == 0 else 3))
    return out


def bg_of(sc: dict) -> str:
    return sc.get("bg") or ("none" if sc.get("kind") in OVERLAY_KINDS else "charcoal")


def full(sc: dict) -> bool:
    return bg_of(sc) != "none"


def layer(sc: dict, W: int, H: int, D: float, face=None) -> dict:
    """một cảnh → lớp html HyperFrames (dùng chung: Talking Head plan.mg2, Voice to Motion Kit.mg)."""
    V = H > W
    tone = sc.get("tone") if sc.get("tone") in TONES else "gold"
    fn = T[sc["kind"]]
    html, js = fn(sc, V, tone, face) if sc["kind"] in ("iconrow", "chips") else fn(sc, V, tone)
    bg = bg_of(sc)
    bgcss = _bgcss(bg, sc.get("colors"))
    light = " light" if bg == "cream" or sc.get("light") else ""
    root = (f'<div class="root{light}" style="--s:{min(W, H) / 1080}">'
            + (f'<div class=bg style="{bgcss}"></div>' if bgcss else "")
            + ('<div class=grain></div><div class=vig></div>' if bgcss and bg != "cream" else "")
            + f'<div class=content style="position:absolute;inset:0">{html}</div></div>')
    pre = "const q=s=>document.querySelector(sel+' '+s);"
    if sc.get("box"):                    # căn + co cả cụm nội dung vào vùng (Voice to Motion: vùng minh hoạ của khung, không có người)
        bx0, by0, bx1, by1 = [float(v) for v in sc["box"]]
        pre += ("{const C=q('.content');let a=1e9,b=1e9,c=-1e9,d=-1e9;[...C.children].forEach(e=>{let r=e.getBoundingClientRect();"
                "if(r.width>innerWidth*0.9){const g=document.createRange();g.selectNodeContents(e);r=g.getBoundingClientRect()}"
                "if(r.width<1)return;a=Math.min(a,r.left);b=Math.min(b,r.top);c=Math.max(c,r.right);d=Math.max(d,r.bottom)});"
                f"if(c>a){{const k=Math.min(1.6,{bx1 - bx0}/(c-a),{by1 - by0}/(d-b));"
                f"gsap.set(C,{{transformOrigin:'0 0',x:{(bx0 + bx1) / 2}-(a+c)/2*k,y:{(by0 + by1) / 2}-(b+d)/2*k,scale:k}})}}}}")
    drift = f"tl.to(q('.bg'),{{x:-30,y:-20,scale:1.04,duration:{D},ease:'none'}},0);" if bgcss else ""
    fade = (f"tl.from(q('.root'),{{opacity:0,duration:.25}},0);" if bgcss else "") + \
           (f"tl.to(q('{'.root' if bgcss else '.content'}'),{{opacity:0,duration:.3}},{max(0.5, D - 0.3)});" if sc.get("fade_out", True) else "")
    return {"id": "mg", "type": "html", "start": 0, "duration": D, "x": 0, "y": 0, "anchor": "top-left", "w": W, "h": H,
            "html": root, "css": BASE_CSS + ((sc.get("css") or "") if sc["kind"] == "custom" else ""), "js": pre + drift + js + ";\n" + fade}


def spec(plan, sc: dict, out: Path, face=None) -> dict:
    W, H, fps = plan.width, plan.height, plan.fps
    D = round((int(sc["end"]) - int(sc["start"])) / fps, 3)
    return {"job_id": f"mg2-{sc['id']}", "width": W, "height": H, "fps": fps, "duration": D, "background": "transparent",
            "output": {"path": str(out), "format": "mov"}, "layers": [layer(sc, W, H, D, face)]}


def _face_px(plan, anchors_tl, sc):
    if not anchors_tl:
        return None
    from .callouts import face_box
    return [int(v) for v in face_box(anchors_tl, int(sc["start"]), int(sc["end"]), plan.width, plan.height)]


def prerender(plan, work: Path, anchors_tl=None, log=print) -> list[dict]:
    """render mỗi cảnh một lần (lưu đệm theo mã băm) → mục lớp phủ cho render.composite (như plan.hf)."""
    from .hyper.job import Job
    items = []
    for sc in [s for s in getattr(plan, "mg2", None) or [] if s.get("enabled", True)]:
        out = Path(work) / "mg2" / f"{sc['id']}.mov"
        st = Job(spec(plan, sc, out, _face_px(plan, anchors_tl, sc)), Path(work) / "mg2_jobs").run(progress=log)
        items.append({"path": st["output"], "start": int(sc["start"]) / plan.fps, "dur": (int(sc["end"]) - int(sc["start"])) / plan.fps,
                      "layer": "front", "id": "mg2-" + sc["id"]})
    return items


def blur_bg(out: np.ndarray, plan, f: int) -> np.ndarray:
    """cảnh bg "blur": cả khung thành video gốc làm mờ + tối (vào / ra 8 frame) — lớp HyperFrames vẽ nội dung lên trên."""
    import cv2
    for sc in getattr(plan, "mg2", None) or []:
        if not sc.get("enabled", True) or bg_of(sc) != "blur":
            continue
        a, b = int(sc["start"]), int(sc["end"])
        if not (a <= f < b):
            continue
        k = min(1.0, (f - a + 1) / 8, (b - f) / 8)
        H, W = out.shape[:2]
        sm = cv2.GaussianBlur(cv2.resize(out, (W // 8, H // 8), interpolation=cv2.INTER_AREA), (0, 0), 5)
        bl = cv2.resize(sm, (W, H), interpolation=cv2.INTER_LINEAR) * 0.42
        return out * (1 - k) + bl * k
    return out


def covers(plan) -> list[tuple[int, int]]:
    """khoảng timeline cảnh MG2 che toàn khung (không thấy người)."""
    return [(int(s["start"]), int(s["end"])) for s in getattr(plan, "mg2", None) or [] if s.get("enabled", True) and full(s)]


def check(plan, fps: int, open_close: tuple[int, int] | None = None, demo: list[tuple[int, int]] | None = None,
          need_rhythm: bool = True) -> list[tuple[str, str]]:
    from . import icons3d as K, timeline as Tm
    out = []
    scs = sorted([s for s in getattr(plan, "mg2", None) or [] if s.get("enabled", True)], key=lambda s: int(s["start"]))
    for s in scs:
        tag = f"mg2 {s.get('id')} ({s.get('kind')}) {Tm.tc(int(s['start']))}"
        if s.get("kind") not in KINDS:
            out.append(("error", f"{tag}: không có kiểu này (có: {', '.join(sorted(KINDS))})")); continue
        if bg_of(s) not in BGS:
            out.append(("error", f"{tag}: nền “{s.get('bg')}” không có — chỉ {', '.join(sorted(BGS))}")); continue
        d = (int(s["end"]) - int(s["start"])) / fps
        if not 2.5 <= d <= 8.0:
            out.append(("error", f"{tag}: dài {d:.1f}s — mỗi cảnh 2.5–8s"))
        for n in _icons(s):
            if not K.exists(n.removeprefix("3d:")):
                out.append(("error", f"{tag}: không có icon 3D {n} — tra: python -m thagent.tools icon3d <từ khoá>"))
        for im in s.get("images") or []:
            if not Path(im.get("src", "")).is_file():
                out.append(("error", f"{tag}: không có ảnh {im.get('src')}"))
        if s["kind"] == "custom" and not s.get("html"):
            out.append(("error", f"{tag}: custom thiếu html"))
        if open_close and full(s) and (int(s["start"]) < open_close[0] or int(s["end"]) > open_close[1]):
            out.append(("error", f"{tag}: cảnh MG che toàn khung trong đoạn mở đầu / kết — hai đoạn này chỉ hình người + chữ"))
    for x, y in zip(scs, scs[1:]):
        if int(y["start"]) < int(x["end"]):
            out.append(("error", f"mg2 {x['id']} và {y['id']} chồng nhau"))
        elif x["kind"] == y["kind"]:
            out.append(("warn", f"mg2 {x['id']} và {y['id']}: cùng kiểu “{x['kind']}” liền nhau — đổi kiểu cho đỡ nhàm"))
    if need_rhythm:
        out += rhythm(plan, fps, open_close, demo)
    return out


def _icons(s):
    xs = [s.get("icon")] + list(s.get("icons") or []) + [it.get("icon") for it in s.get("items") or [] if isinstance(it, dict)]
    import re
    xs += re.findall(r"\{\{icon:(3d:[\w-]+)\}\}", s.get("html", "") or "")
    return [x for x in xs if x and str(x).startswith("3d:")]


def rhythm(plan, fps: int, open_close=None, demo=None) -> list[tuple[str, str]]:
    """nói > GAP_S giây (ngoài đoạn mở đầu / kết và đoạn trình diễn vật) mà không có MG nào → lỗi."""
    from . import timeline as Tm
    from . import mg as M
    M.chain(plan.mg)
    marks = sorted([(int(s["start"]), int(s["end"])) for s in getattr(plan, "mg2", None) or [] if s.get("enabled", True)] +
                   [M.covered_range(m) for m in plan.mg])
    a0, a1 = open_close or (0, plan.duration_frames)
    demo = demo or []
    out, prev = [], a0
    for s, e in marks + [(a1, a1)]:
        if s - prev > GAP_S * fps:
            span = range(prev, s)
            dm = sum(1 for f in span if any(x <= f < y for x, y in demo))
            if dm < 0.5 * len(span):
                out.append(("error", f"{Tm.tc(prev)}→{Tm.tc(s)}: {(s - prev) / fps:.1f}s nói không có Motion Graphics — thêm cảnh plan.mg2 "
                                     f"(khoảng mỗi 10s, đúng lúc lời mô tả / liệt kê / nêu số liệu)"))
        prev = max(prev, e)
    return out
