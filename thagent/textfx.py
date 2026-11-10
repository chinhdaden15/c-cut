"""Hiệu ứng chữ động (kinetic type) — mẫu MG2 dùng chung mọi skill (Talking Head plan.mg2, Voice to Motion / Text to Video s.mg).

Học từ ghost-editor scripts/lib/kinetic.mjs (MIT, kurbaitaev) — viết lại cho C-Cut. Nguyên tắc:
- MỘT họ đường cong: vào = expo-out (bezier .16,1,.3,1), ra = đường ngược, NHANH GẤP ĐÔI lúc vào.
- Chữ TRỒI LÊN từ mặt nạ của chính nó (yPercent 118 + nghiêng 5° từ góc chân chữ) chạm ĐÚNG lúc nói; mặt nạ chừa chỗ cho DẤU tiếng Việt.
- Mọi chuyển động theo từng chữ cái / lò xo / xáo chữ là "painter": tính lại từ tl.time() mỗi frame → tua tới frame nào cũng đúng.
- Sau khi chữ đứng yên phải giữ đủ để đọc: max(1s, 0,3s / từ).

Kind (sc["kind"]) — "at" = GIÂY tính từ đầu cảnh, mỗi từ / mục một mốc (thiếu → tự rải):
  headline   lines ["dòng 1", "dòng có *từ nhấn*"], mark "under"|"marker"|"box"|"strike" (nét bút vẽ tay "sôi" dưới / sau / quanh / gạch từ nhấn),
             swap {"text": "X", "at": giây} → "không phải X → mà là Y": X hiện, bị gạch, rút lên, rồi dòng chính trồi lên đúng chỗ đó
  scramble   text "…", lead "dòng nhỏ dẫn" — ký tự xáo trộn rồi khoá dần trái → phải, khoá xong từ đúng lúc nói (+ rung khi khoá)
             CHỈ hợp video CÔNG NGHỆ (góp ý người dùng); chủ đề khác dùng headline / money / chart
  drum       items ["…", "…"], lead, tail — trống chữ 3D xoay tới từng từ đúng lúc nói (liệt kê, "vòng lặp")
  flipstack  items ["…"] — mỗi từ một thẻ lật từ trên xuống, chồng lên thẻ trước (thẻ cũ lùi, mờ, lệch nhẹ); last_accent: thẻ cuối màu nhấn
  spring     text "PHẦN 2", sub — từng chữ cái rơi xuống kiểu lò xo (vị trí + xoay + co giãn) — tiêu đề phần
Chung: y (tâm khối, 0..1 chiều cao khung; mặc định 0.62 dọc / 0.58 ngang), size (px ở khung 1080), color, accent, glass (khung kính mờ sau chữ, mặc định bật — trừ flipstack), mark mặc định "pill" (viên bo góc chuyển sắc bao trọn từ nhấn).
"""
from __future__ import annotations

import json
import re

KINDS = {"headline", "scramble", "drum", "flipstack", "spring"}
# bảng màu dịu (góp ý người dùng 2026-11-10: "phối màu chưa ổn"): chữ trắng ngà + MỘT màu nhấn nhạt, thẻ giấy ngà chữ đậm — không đỏ / vàng gắt
# + lần 2 ("chữ bị chìm, shape không bao hết chữ, cổ điển"): chữ TRẮNG đậm trên KÍNH MỜ tối, từ nhấn trong VIÊN bo góc chuyển sắc bao trọn chữ
PAL = {"gold": {"acc": "#FFD66B", "acc2": "#FFB547", "ink": "#FFFFFF", "card": "rgba(16,18,26,.72)", "card_ink": "#FFFFFF", "hl": "#FFD66B", "on": "#17130A"},
       "blue": {"acc": "#8FE3FF", "acc2": "#5AB8FF", "ink": "#FFFFFF", "card": "rgba(14,20,30,.72)", "card_ink": "#FFFFFF", "hl": "#8FE3FF", "on": "#0B1620"},
       "red": {"acc": "#FFB4A6", "acc2": "#FF8A75", "ink": "#FFFFFF", "card": "rgba(26,16,16,.72)", "card_ink": "#FFFFFF", "hl": "#FFB4A6", "on": "#1E0E0B"}}
ACC = {k: v["acc"] for k, v in PAL.items()}

RUNTIME = r"""
const KT=(()=>{const C=(v,a=0,b=1)=>v<a?a:v>b?b:v;const EO=p=>p>=1?1:p<=0?0:1-Math.pow(2,-10*p);const EI=p=>p<=0?0:p>=1?1:Math.pow(2,10*(p-1));
const spring=(u,A,f,z=1/3)=>{if(u<=0)return A;const w=2*Math.PI*f;return A*Math.exp(-z*w*u)*Math.cos(w*Math.sqrt(1-z*z)*u)};
const hash=i=>{const v=Math.sin(i*127.1+311.7)*43758.5453;return v-Math.floor(v)};return{C,EO,EI,spring,hash}})();
const qa=s=>document.querySelectorAll(sel+' '+s);
const ft=(s,a,b,at)=>{const el=q(s);if(el)tl.fromTo(el,a,Object.assign({immediateRender:false},b),Math.max(0,at))};
const OUT='expo.out',IN='power3.in';
"""

CSS = """
.kt{position:absolute;left:0;right:0;display:flex;flex-direction:column;align-items:center;text-align:center;font-family:Montserrat,sans-serif;color:var(--ink)}
.kt-glass{position:relative;display:flex;flex-direction:column;align-items:center;padding:calc(30px*var(--s)) calc(46px*var(--s)) calc(34px*var(--s));
 border-radius:calc(34px*var(--s));background:rgba(12,14,22,.56);backdrop-filter:blur(22px) saturate(140%);-webkit-backdrop-filter:blur(22px) saturate(140%);
 border:1.5px solid rgba(255,255,255,.16);box-shadow:0 calc(24px*var(--s)) calc(60px*var(--s)) rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.18)}
.kt-pk{position:absolute;left:-10%;right:-10%;background:radial-gradient(50% 50% at 50% 50%,rgba(8,8,10,.5) 0%,rgba(8,8,10,.26) 48%,rgba(8,8,10,0) 100%)}
.kt-line{display:block;white-space:nowrap;line-height:1.12;font-weight:900;letter-spacing:-.015em;text-shadow:0 2px 10px rgba(0,0,0,.35)}
.kt-m{display:inline-block;overflow:hidden;vertical-align:bottom;padding:.28em .16em .22em;margin:-.28em -.16em -.22em}
.kt-mi{display:inline-block;transform-origin:0% 100%}
.kt-mk{position:relative;display:inline-block;isolation:isolate}
.kt-mkw{position:absolute;pointer-events:none;z-index:-1}.kt-mkw svg{display:block;width:100%;height:100%;overflow:visible}
.kt-mk.pill{margin:0 .1em}.kt-mk.pill .kt-mkw{left:-.18em;right:-.18em;top:-.16em;bottom:-.12em;border-radius:.24em;
 background:linear-gradient(135deg,var(--acc),var(--acc2));box-shadow:0 .08em .3em rgba(0,0,0,.35)}
.kt-mk{white-space:nowrap}
.kt-mk.under .kt-mkw{left:0;right:0;top:100%;height:.12em;border-radius:99px;background:linear-gradient(90deg,var(--acc),var(--acc2))}
.kt-mk.strike .kt-mkw{left:-.1em;right:-.1em;top:44%;height:.14em;border-radius:99px;background:#FF6F5E;box-shadow:0 0 .25em rgba(255,111,94,.55);z-index:2}
.kt-mk.box .kt-mkw{left:-.2em;right:-.2em;top:-.14em;bottom:-.1em;border:.06em solid var(--acc);border-radius:.26em}
.kt-mk.brush-under .kt-mkw{left:-4%;right:-4%;top:90%;height:.3em}.kt-mk.brush-marker .kt-mkw{left:-5%;right:-5%;top:14%;height:.8em}
.kt-mk.brush-marker .kt-mi{color:var(--on);text-shadow:none}
.kt-sc{position:relative;display:inline-block}.kt-sc>i{font-style:normal;visibility:hidden}
.kt-sc>b{position:absolute;left:50%;top:0;transform:translateX(-50%);font-weight:inherit;white-space:pre}
.kt-drum{position:relative;display:inline-grid;align-items:center;justify-items:center;
 -webkit-mask-image:linear-gradient(to bottom,transparent 0%,rgba(0,0,0,.28) 18%,#000 40%,#000 60%,rgba(0,0,0,.28) 82%,transparent 100%);
 mask-image:linear-gradient(to bottom,transparent 0%,rgba(0,0,0,.28) 18%,#000 40%,#000 60%,rgba(0,0,0,.28) 82%,transparent 100%)}
.kt-dsz{grid-area:1/1;display:grid;visibility:hidden}.kt-dsz span{grid-area:1/1;white-space:nowrap;line-height:1;padding:0 .1em}
.kt-dax,.kt-cyl{position:absolute;inset:0;transform-style:preserve-3d}
.kt-dw{position:absolute;left:0;top:50%;width:100%;text-align:center;white-space:nowrap;line-height:1;backface-visibility:hidden;-webkit-backface-visibility:hidden}
.kt-cards{position:relative;width:100%}.kt-crow{position:absolute;left:0;right:0;top:0;display:flex;justify-content:center}
.kt-card{position:relative;display:inline-flex;align-items:center;justify-content:center;white-space:nowrap;transform-origin:50% 0%;opacity:0;font-weight:800;
 box-shadow:0 18px 44px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.16);border:1.5px solid rgba(255,255,255,.16);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}
.kt-card .kt-dim{position:absolute;inset:0;border-radius:inherit;background:#000;opacity:0}
.kt-ch{display:inline-block;transform-origin:50% 100%;opacity:0}
"""

_BOIL = ('<filter id="{i}-b" x="-10%" y="-60%" width="120%" height="220%"><feTurbulence class="kt-turb" type="fractalNoise" '
         'baseFrequency="0.045 0.3" numOctaves="2" seed="1" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="3.2" '
         'xChannelSelector="R" yChannelSelector="G"/></filter>')
_BRUSH = {
    "under": '<svg viewBox="0 0 200 20" preserveAspectRatio="none"><defs>{b}</defs><path filter="url(#{i}-b)" fill="var(--acc)" d="M2.5 9.6 C 40 6.4, 92 5.2, 140 5 C 166 4.9, 186 3.6, 197.6 1.8 C 200.2 1.6, 200.4 8.6, 197.6 9.6 C 178 12.8, 150 13.6, 116 14.4 C 78 15.2, 40 17, 6 18.8 C 0.8 19, 0 10.2, 2.5 9.6 Z"/></svg>',
    "strike": '<svg viewBox="0 0 200 20" preserveAspectRatio="none"><defs>{b}</defs><path filter="url(#{i}-b)" fill="var(--acc)" d="M2 13.6 C 50 10.8, 110 8.6, 196 4.4 C 199.6 4.4, 200 9.6, 196.6 10.2 C 120 14.2, 60 16.4, 5 18.6 C 0.8 18.6, 0 14, 2 13.6 Z"/></svg>',
    "marker": '<svg viewBox="0 0 200 20" preserveAspectRatio="none"><defs>{b}</defs><path filter="url(#{i}-b)" fill="var(--acc)" d="M4 3.4 C 60 1.6, 130 2.2, 196 1.2 C 199.4 1.4, 199 18, 195.6 18.4 C 130 19.2, 70 18.2, 5 19 C 1 19, 0.6 3.6, 4 3.4 Z"/></svg>',
    "box": '<svg viewBox="0 0 200 60" preserveAspectRatio="none"><defs>{b}</defs><path filter="url(#{i}-b)" fill="none" stroke="var(--acc)" stroke-width="3.2" stroke-linecap="round" d="M8 6 C 70 3, 140 4, 194 6 C 197 22, 197 40, 193 55 C 130 57, 60 57, 7 54 C 4 40, 4 20, 9 8"/></svg>',
}


def _e(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _r(x) -> float:
    return round(float(x), 3)


def _times(n: int, at, start: float = 0.25, step: float = 0.35) -> list[float]:
    at = [float(x) for x in (at or [])]
    out, last = [], start - step
    for i in range(n):
        t = at[i] if i < len(at) else last + step
        out.append(max(0.02, t)); last = out[-1]
    return out


def fit(text: str, size: float, V: bool, upper: bool = True) -> float:
    """co cỡ chữ để dòng không tràn khung (ước lượng bề rộng Montserrat đậm: chữ HOA ~0,68 em, thường ~0,58 em)."""
    n = max(1, len(str(text)))
    maxw = 1080 * (0.70 if V else 0.98)        # khối chữ gọn: ~70% bề ngang khung dọc, ~55% khung ngang (chừa khoảng thở)
    return round(min(size, maxw / (n * (0.68 if upper else 0.58))), 1)


def _px(v) -> str:
    return f"calc({v}px*var(--s))"


class _B:
    """bộ gom html + js cho một khối."""
    def __init__(self, D):
        self.D, self.js, self.n = D, [], 0

    def uid(self, p="k"):
        self.n += 1
        return f"{p}{self.n}"

    def mask_line(self, text: str, times: list[float], size: float, weight=800, mark=None, color=None, rise=0.6, lead=0.06):
        """dòng chữ từng từ trồi từ mặt nạ đúng mốc; *từ* = vùng nhấn (nét bút). → (html, số từ, ids, mốc từ nhấn cuối, id nét)"""
        raw = text.split()
        html, ids, in_mark, mark_t, mk_id = "", [], False, None, None
        for i, w in enumerate(raw):
            op, cl = bool(mark) and w.startswith("*"), bool(mark) and w.rstrip(".,!?:;").endswith("*")
            clean = w.strip("*") if mark else w
            if i:
                html += " "
            if op:
                in_mark, mk_id = True, self.uid("mk")
                behind = mark in ("pill", "brush-marker")
                fill = (_BRUSH["marker"].format(b=_BOIL.format(i=mk_id), i=mk_id) if mark == "brush-marker" else "")
                html += f'<span class="kt-mk {mark}">' + (f'<span class="kt-mkw {mk_id}">{fill}</span>' if behind else "")
            wid = self.uid("w")
            ids.append(wid)
            html += f'<span class="kt-m"><span class="kt-mi {wid}">{_e(clean)}</span></span>'
            t = times[i] if i < len(times) else times[-1] + 0.07 * (i - len(times) + 1)
            self.js.append(f"gsap.set(q('.{wid}'),{{yPercent:118,rotation:5}});ft('.{wid}',{{yPercent:118,rotation:5}},{{yPercent:0,rotation:0,duration:{rise},ease:OUT}},{_r(t - lead)});")
            if in_mark:
                mark_t = t
            if cl and in_mark:
                if mark not in ("pill", "brush-marker"):
                    fill = _BRUSH[mark[6:]].format(b=_BOIL.format(i=mk_id), i=mk_id) if mark.startswith("brush-") else ""
                    html += f'<span class="kt-mkw {mk_id}">{fill}</span>'
                html += "</span>"
                in_mark = False
        style = f"font-size:{_px(size)};font-weight:{weight};" + (f"color:{color};" if color else "")
        return f'<span class="kt-line" style="{style}">{html}</span>', len(raw), ids, mark_t, mk_id

    def mask_out(self, ids, at, stagger=0.03, dur=0.3):
        for i, wid in enumerate(ids):
            self.js.append(f"ft('.{wid}',{{yPercent:0,rotation:0}},{{yPercent:-118,rotation:0,duration:{dur},ease:IN}},{_r(at + i * stagger)});")

    def wipe(self, cls, at, dur=0.5):
        self.js.append(f"gsap.set(q('.{cls}'),{{clipPath:'inset(-60% 100% -60% 0%)'}});"
                       f"ft('.{cls}',{{clipPath:'inset(-60% 100% -60% 0%)'}},{{clipPath:'inset(-60% -2% -60% 0%)',duration:{dur},ease:OUT}},{_r(at)});")

    def painter(self, body: str):
        self.js.append("(()=>{const P={u:0};const paint=()=>{const t=tl.time();" + body + "};"
                       f"tl.fromTo(P,{{u:0}},{{u:1,duration:{self.D},ease:'none',onUpdate:paint,immediateRender:false}},0);paint();"
                       "if(document.fonts)document.fonts.ready.then(paint)})();")


def layer(sc: dict, V: bool, tone: str, D: float) -> tuple[str, str, list[float], list[tuple[float, str, float]]]:
    """→ (html, js, beats [giây], sfx [(giây, âm, dB)])."""
    k = sc["kind"]
    B = _B(D)
    pal = PAL.get(tone, PAL["gold"])
    acc = sc.get("accent") or pal["acc"]
    ink = sc.get("color") or pal["ink"]
    y = float(sc.get("y", 0.62 if V else 0.58))
    t_out = _r(max(0.4, D - float(sc.get("exit", 0.32))))
    beats, sfx = [0.0], []
    body, h = "", 200

    if k == "headline":
        lines = [l if isinstance(l, str) else l.get("text", "") for l in (sc.get("lines") or [sc.get("text", "")])]
        size = min(fit(l.replace("*", ""), float(sc.get("size", 86 if V else 78)), V, l.replace("*", "").isupper()) for l in lines)
        mark = {"marker": "pill"}.get(sc.get("mark"), sc.get("mark")) or ("pill" if any("*" in l for l in lines) else None)
        n_tok = sum(len(l.split()) for l in lines)
        times = _times(n_tok, sc.get("at"))
        main_start = times[0] if times else 0.25
        swap_html, ids_all = "", []
        if sc.get("swap"):
            sw = sc["swap"]
            st = float(sw.get("at", 0.2))
            stimes = [st + 0.07 * i for i in range(len(sw["text"].split()))]
            h_, n_, ids_, _, mk = B.mask_line(f'*{sw["text"]}*', stimes, size * 0.86, mark="strike", color="#FFFFFF")   # vế bị bác bỏ vẫn RÕ (góp ý người dùng); "bị gạch" thể hiện bằng thanh gạch
            strike = _r(sw.get("strike_at", stimes[-1] + 0.45))
            B.wipe(mk, strike, 0.32)
            sfx.append((strike, "whoosh_short", -12.0))
            out_at = _r(strike + 0.5)
            B.mask_out(ids_, out_at)
            B.js.append(f"ft('.{mk}',{{opacity:1}},{{opacity:0,duration:.18,ease:IN}},{out_at});")
            swap_html = f'<div style="grid-area:1/1">{h_}</div>'
            main_start = max(main_start, out_at + 0.3)
            times = [max(t, main_start + 0.07 * i) for i, t in enumerate(times)]
            beats += [st, strike]
        html, j, last_mark, mk_main = "", 0, None, None
        for li, l in enumerate(lines):
            n = len(l.split())
            h_, _, ids, mt, mk = B.mask_line(l, times[j:j + n], size, mark=mark)
            ids_all += ids
            if mt is not None:
                last_mark, mk_main = mt, mk
            html += h_
            j += n
        if mk_main and last_mark is not None:
            ma = _r(last_mark + 0.32)
            B.wipe(mk_main, ma)
            if mark == "pill":                 # chữ trong viên: trắng tới lúc viên quét tới → đổi tối (không có lúc chữ tối trên kính tối)
                B.js.append(f"qa('.kt-mk.pill .kt-mi').forEach(e=>tl.fromTo(e,{{color:'#FFFFFF',textShadow:'0 2px 10px rgba(0,0,0,.35)'}},"
                            f"{{color:'{pal['on']}',textShadow:'0 0 0 rgba(0,0,0,0)',duration:.2,ease:'none',immediateRender:false}},{ma + 0.08}));")
            B.js.append(f"ft('.{mk_main}',{{opacity:1}},{{opacity:0,duration:.2,ease:IN}},{t_out});")
            sfx.append((ma, "whoosh_short", -14.0))
            beats.append(ma)
        if mark and mark.startswith("brush-"):
            B.painter("const s=String(1+(Math.floor(t*12)%53));qa('.kt-turb').forEach(e=>e.setAttribute('seed',s));")   # nét bút "sôi" 12 hình/giây
        B.mask_out(ids_all, t_out)
        beats += times
        body = f'<div style="display:grid;justify-items:center;align-items:center">{swap_html}<div style="grid-area:1/1">{html}</div></div>'
        h = size * 1.15 * len(lines)
        sfx.append((times[0] if times else 0.2, "soft_00", -16.0))

    elif k == "spring":
        text = str(sc.get("text", "")).upper() if sc.get("upper", True) else str(sc.get("text", ""))
        size = fit(text, float(sc.get("size", 132 if V else 116)), V)
        chars = list(text)
        start = _r(float((sc.get("at") or [0.2])[0]) - 0.1)
        stg = float(sc.get("stagger", 0.045))
        A = (0.9 if sc.get("from") == "rise" else -1.15) * size
        L = [{"i": i, "t": _r(start + i * stg * (1 - 0.3 * i / max(1, len(chars)))), "r": (1 if i % 2 else -1) * 16 * (0.6 + 0.4 * ((i * 7) % 5) / 4)}
             for i, c in enumerate(chars) if c != " "]
        letters = "".join('<span class="kt-ch" style="opacity:1">&nbsp;</span>' if c == " " else f'<span class="kt-ch c{i}">{_e(c)}</span>'
                          for i, c in enumerate(chars))
        B.painter(f"const L={json.dumps(L)};for(const o of L){{const el=q('.c'+o.i);if(!el)continue;const u=t-o.t;"
                  f"if(u<0){{el.style.opacity='0';continue}}const yy=KT.spring(u,{A:.1f},1.6),"
                  f"rr=KT.spring(u,o.r,2.8),qq=KT.spring(u,-.45,2.1);const ox=t>{t_out}?KT.EI((t-{t_out}-o.i*.012)/.3):0;"
                  "el.style.opacity=String(KT.C(u/.05)*(1-KT.C(ox)));"
                  f"el.style.transform='translateY('+(yy-ox*{size * 0.9:.0f}).toFixed(1)+'px) rotate('+rr.toFixed(2)+'deg) scale('+Math.exp(qq/2).toFixed(3)+','+Math.exp(-qq/2).toFixed(3)+')'}}")
        sub = ""
        if sc.get("sub"):
            st = [start + len(chars) * stg + 0.15 + 0.07 * i for i in range(len(str(sc["sub"]).split()))]
            sh, _, sids, _, _ = B.mask_line(str(sc["sub"]), st, 54, weight=600)
            B.mask_out(sids, t_out)
            sub = sh
        body = f'<span class="kt-line" style="font-size:{_px(size)};font-weight:900;letter-spacing:-.02em;color:{sc.get("key_color", ink)}">{letters}</span>{sub}'
        h = size + (70 if sub else 0)
        beats += [start, start + len(chars) * stg]
        sfx.append((start, "whoosh_short", -12.0))

    elif k == "scramble":
        text = str(sc.get("text", ""))
        text = text.upper() if sc.get("upper", True) else text
        size = fit(text, float(sc.get("size", 92 if V else 84)), V, text.isupper())
        words = text.split()
        on = _times(len(words), sc.get("at"), start=0.75)
        start = _r(max(0.02, on[0] - 0.45))
        pool_u, pool_l, dig, sym = "ABCDEFGHKLMNOPRSTUVXYZĐ", "abcdeghklmnopqrstuvxy", "0123456789", "/*+?#<>="
        W, html_w = [], []
        for wi, w in enumerate(words):
            appear = _r(max(start, on[wi] - 0.55))
            l0, l1 = _r(max(appear + 0.18, on[wi] - 0.2)), _r(on[wi] + 0.22)
            ch = []
            for ci, c in enumerate(w):
                p = (dig if c.isdigit() else (pool_u if c.isupper() else pool_l) if c.isalpha() else "") + (sym if c.isalnum() else "")
                ch.append({"c": c, "p": p, "ci": ci})
            W.append({"k": wi, "a": appear, "l0": l0, "l1": l1, "ch": ch})
            html_w.append("".join(f'<span class="kt-sc"><i>{_e(c)}</i><b class="g{wi}-{ci}"></b></span>' for ci, c in enumerate(w)))
        last = max(x["l1"] for x in W)
        B.painter(f"const W={json.dumps(W, ensure_ascii=False)};const step=Math.floor((t-{start})*18);"
                  "for(const w of W){const n=w.ch.length;for(const o of w.ch){const el=q('.g'+w.k+'-'+o.ci);if(!el)continue;"
                  "const shown=t>=w.a+o.ci*.022;const res=(t-w.l0)/Math.max(.05,w.l1-w.l0);const locked=!o.p||(o.ci+1)/n<=res;"
                  "if(!shown){el.textContent='';continue}if(locked){el.textContent=o.c;el.style.color='';continue}"
                  "const hh=KT.hash(step*31+w.k*17+o.ci*7);el.textContent=o.p.charAt(Math.floor(hh*o.p.length));el.style.color='var(--acc)'}}"
                  f"const g=q('.sg');let x=0;const su=t-{last};if(su>0&&su<.7)x=12*Math.sin(2*Math.PI*13*su)*Math.exp(-6*su);"
                  f"const ox=t>{t_out}?KT.EI((t-{t_out})/.32):0;g.style.transform='translateX('+x.toFixed(1)+'px) translateY('+(-ox*40).toFixed(1)+'px)';g.style.opacity=String(1-ox);")
        lead = ""
        if sc.get("lead"):
            lt = _times(len(str(sc["lead"]).split()), None, start=max(0.05, start - 0.4), step=0.12)
            lh, _, lids, _, _ = B.mask_line(str(sc["lead"]), lt, 56, weight=600)
            B.mask_out(lids, t_out)
            lead = lh
        body = f'{lead}<div class="sg"><span class="kt-line" style="font-size:{_px(size)};font-weight:900;letter-spacing:-.01em">{" ".join(html_w)}</span></div>'
        h = size * 1.1 + (70 if lead else 0)
        beats += [start] + [x["l1"] for x in W]
        sfx += [(start, "u_tick", -18.0), (last, "hit_03", -13.0)]

    elif k == "drum":
        items = [str(x) for x in sc.get("items") or []]
        size = min(fit(x, float(sc.get("size", 90 if V else 80)), V, x.isupper()) for x in items) if items else 100
        N = len(items)
        S = max(6, 2 * N)
        stp = 360 / S
        import math
        R = round(1.12 * size / (2 * math.sin(stp * math.pi / 360)))
        Hh = round(size * 2.9)
        times = _times(N, sc.get("at"), start=0.6)
        slots = "".join(f'<div class="kt-dw" style="transform:translateY(-50%) rotateX({_r(-i * stp)}deg) translateZ({_px(R)})">{_e(items[i % N])}</div>'
                        for i in range(S))
        ri = 0.55
        B.js.append(f"gsap.set(q('.cyl'),{{rotationX:{_r(-2 * stp)}}});ft('.cyl',{{rotationX:{_r(-2 * stp)}}},{{rotationX:0,duration:{ri},ease:OUT}},{_r(max(0.02, times[0] - ri))});")
        for i in range(1, N):
            B.js.append(f"ft('.cyl',{{rotationX:{_r((i - 1) * stp)}}},{{rotationX:{_r(i * stp)},duration:.38,ease:'power3.inOut'}},{_r(times[i] - 0.38)});")
            sfx.append((_r(times[i] - 0.19), "u_tick", -15.0))
        B.js.append(f"gsap.set(q('.drm'),{{opacity:0,y:30}});ft('.drm',{{opacity:0,y:30}},{{opacity:1,y:0,duration:.35,ease:OUT}},{_r(max(0.02, times[0] - ri))});"
                    f"ft('.drx',{{opacity:1,y:0}},{{opacity:0,y:-40,duration:.32,ease:IN}},{t_out});")
        extra = ""
        if sc.get("lead"):
            lh, _, lids, _, _ = B.mask_line(str(sc["lead"]), _times(len(str(sc["lead"]).split()), None, start=max(0.05, times[0] - 0.6), step=0.12), 60, weight=600)
            B.mask_out(lids, t_out); extra += lh
        tail = ""
        if sc.get("tail"):
            th, _, tids, _, _ = B.mask_line(str(sc["tail"]), _times(len(str(sc["tail"]).split()), None, start=times[-1] + 0.3, step=0.12), 60, weight=700)
            B.mask_out(tids, t_out); tail = th
        sizer = "".join(f"<span>{_e(x)}</span>" for x in items)
        body = (f'{extra}<div class="drx"><div class="kt-drum drm" style="height:{_px(Hh)};perspective:{_px(round(size * 9))};font-size:{_px(size)};'
                f'font-weight:900;color:{acc};letter-spacing:-.02em"><div class="kt-dsz">{sizer}</div>'
                f'<div class="kt-dax" style="transform:translateZ({_px(-R)})"><div class="kt-cyl cyl">{slots}</div></div></div></div>{tail}')
        h = Hh + (60 if extra else 0) + (60 if tail else 0)
        beats += times
        sfx.append((_r(max(0.02, times[0] - ri)), "whoosh_short", -14.0))

    elif k == "flipstack":
        items = [str(x) for x in sc.get("items") or []]
        size = min(fit(x, float(sc.get("size", 58 if V else 52)), V, False) for x in items) if items else 70
        times = [_r(t - 0.12) for t in _times(len(items), sc.get("at"), start=0.4)]
        ch = round(size * 2.05)
        off = round(ch * 0.7)
        rows = "".join(
            f'<div class="kt-crow" style="z-index:{i + 1}"><div class="kt-card c{i}" style="min-width:{_px(440 if V else 420)};height:{_px(ch)};padding:0 {_px(46)};'
            f'border-radius:{_px(30)};background:{("linear-gradient(135deg," + acc + "," + pal["acc2"] + ")") if (i == len(items) - 1 and sc.get("last_accent", True)) else pal["card"]};color:{pal["on"] if (i == len(items) - 1 and sc.get("last_accent", True)) else pal["card_ink"]};font-size:{_px(size)};'
            f'letter-spacing:-.02em">{_e(x)}<i class="kt-dim d{i}"></i></div></div>' for i, x in enumerate(items))
        B.painter(f"const T={json.dumps(times)};const n=T.length;const s=parseFloat(getComputedStyle(q('.kt')).getPropertyValue('--s'))||1;"
                  "for(let i=0;i<n;i++){const el=q('.c'+i),dm=q('.d'+i);if(!el)continue;const u=t-T[i];if(u<0){el.style.opacity='0';continue}"
                  "const th=KT.spring(u,-100,1.25,.42);let d=0;for(let j=i+1;j<n;j++)d+=KT.EO((t-T[j]-.06)/.45);"
                  f"const ox=t>{t_out}?KT.EI((t-{t_out}-(n-1-i)*.05)/.3):0;const ty=(-d*{off}+ox*260)*s,sc=Math.pow(.94,d);"
                  "const rz=Math.min(1,d)*(KT.hash(i*7+3)-.5)*6.4;const x=Math.min(1,d)*(KT.hash(i*11+5)-.5)*30*s;"
                  f"el.style.opacity=String(1-ox);el.style.transform='translateX('+x.toFixed(1)+'px) translateY('+ty.toFixed(1)+'px) rotate('+rz.toFixed(2)+'deg) scale('+sc.toFixed(4)+') perspective('+({ch * 7}*s).toFixed(0)+'px) rotateX('+th.toFixed(2)+'deg)';"
                  "dm.style.opacity=String(Math.min(.62,d*.22))}")
        body = f'<div class="kt-cards" style="height:{_px(ch)}">{rows}</div>'
        h = ch + off * (len(items) - 1)
        beats += times
        sfx += [(_r(t + 0.08), f"pop_0{(i * 3) % 10}", -15.0) for i, t in enumerate(times)]
    else:
        raise ValueError(f"textfx: không có kind {k}")

    H = 1920 if V else 1080
    top = y * H - h / 2
    pk = ""
    glass = sc.get("glass", k != "flipstack")         # khung kính mờ sau khối chữ (chữ trắng luôn nổi trên mọi nền)
    if glass:
        body = f'<div class="kt-glass gl">{body}</div>'
        h += 64
        B.js.append(f"gsap.set(q('.gl'),{{opacity:0,scale:.92}});ft('.gl',{{opacity:0,scale:.92}},{{opacity:1,scale:1,duration:.45,ease:OUT}},0.02);"
                    f"ft('.gl',{{opacity:1,scale:1}},{{opacity:0,scale:.96,duration:.3,ease:IN}},{t_out});")
        top = y * H - h / 2
    if sc.get("pocket", False) and not glass:
        B.js.append(f"gsap.set(q('.kt-pk'),{{opacity:0}});ft('.kt-pk',{{opacity:0}},{{opacity:1,duration:.25,ease:'power2.out'}},0.02);"
                    f"ft('.kt-pk',{{opacity:1}},{{opacity:0,duration:.3,ease:IN}},{t_out});")
        pk = f'<div class="kt-pk" style="top:{_px(round(top - h * 0.6))};height:{_px(round(h * 2.2))}"></div>'
    # chữ chờ dưới mặt nạ / mặt sau trống / thẻ chưa lật là CHE CÓ CHỦ ĐÍCH → báo cho bộ kiểm bố cục HyperFrames (đã kiểm bằng ảnh tĩnh)
    html = (f'<div class="ktwrap" data-layout-allow-overflow data-layout-allow-occlusion style="--acc:{acc};--acc2:{pal["acc2"]};--on:{pal["on"]};--ink:{ink};--hl:{pal["hl"]};position:absolute;inset:0">{pk}'
            f'<div class="kt" style="top:{_px(round(top))}">{body}</div></div>')
    # cờ phải nằm trên CHÍNH phần tử chữ (bộ kiểm không xét tổ tiên): chữ dưới mặt nạ / chữ xáo / mặt trống / thẻ chưa lật
    html = re.sub(r'class="(kt-mi|kt-ch|kt-dw|kt-card|kt-line)\b', r'data-layout-allow-occlusion data-layout-allow-overflow class="\1', html)
    html = re.sub(r'<b class="g', '<b data-layout-allow-occlusion data-layout-allow-overflow data-layout-allow-overlap class="g', html)
    html = html.replace('<div class="kt" ', '<div data-layout-allow-overlap class="kt" ')
    js = RUNTIME + "".join(B.js)
    return html, js, sorted({_r(b) for b in beats if 0 <= b < D}), [(t, a, g) for t, a, g in sfx if 0 <= t < D]
