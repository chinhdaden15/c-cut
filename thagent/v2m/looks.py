"""BỘ NHÌN (look) cho mỗi video Text to Video / Voice to Motion — app tự chọn, xoay vòng giữa các video.

Trước đây Claude tự đặt nền (gần như luôn xanh than + vàng) → mọi video trông y hệt nhau. Giờ mỗi video nhận một look:
bảng màu nền (3 biến thể đổi theo đoạn), màu nhấn chữ / phụ đề / thẻ, tông Motion Graphics (gold | blue | red).
Look được chọn khác các video gần nhất (lịch sử ~/.ccut/looks.json) và ghi vào <dự-án>/look.json để dựng lại vẫn giữ nguyên.
Claude không cần (và không nên) tự đặt màu nền: bg={"style": …} vẫn được, màu sẽ lấy theo look."""
from __future__ import annotations

import json
import random
from pathlib import Path

LOOKS = {
    "dem_vang": dict(name="Đêm vàng", tone="gold", accent="#F2C14E", alt="#F0504A", ink="#3A2805",
                     bgs=[("gradient", "#1d3557", "#0b1424"), ("spot", "#2f4a7a", "#0f1626"), ("charcoal", "#F2C14E", None)],
                     panel="#1A2232", border="#33445C", glow="#1E2A44"),
    "dai_duong": dict(name="Đại dương", tone="blue", accent="#38E1FF", alt="#FF7A59", ink="#022430",
                      bgs=[("gradient", "#0d6b78", "#031c24"), ("spot", "#127a8a", "#04151c"), ("dots", "#1c6f7d", "#05222b")],
                      panel="#0B2A33", border="#1F5563", glow="#0E3A45"),
    "hoang_hon": dict(name="Hoàng hôn", tone="red", accent="#FF6B5A", alt="#FFC24A", ink="#FFFFFF",
                      bgs=[("gradient", "#7a1f3a", "#1a0810"), ("spot", "#8a2440", "#150709"), ("charcoal", "#FF6B5A", None)],
                      panel="#2A1219", border="#5A2A36", glow="#3A1622"),
    "than_cam": dict(name="Than cam", tone="gold", accent="#FF8A1F", alt="#38E1FF", ink="#2A1400",
                     bgs=[("charcoal", "#FF8A1F", None), ("dots", "#5a4630", "#121110"), ("spot", "#6a4418", "#0e0c0a")],
                     panel="#1C1915", border="#3E352B", glow="#2A2118"),
    "cham_tim": dict(name="Chàm tím", tone="blue", accent="#7FD4FF", alt="#FF5FA2", ink="#06142A",
                     bgs=[("gradient", "#4a2a9a", "#0c0820"), ("spot", "#5b35b5", "#0a0718"), ("dots", "#3d2f7a", "#0d0a22")],
                     panel="#181233", border="#3A2F6B", glow="#22184A"),
    "luc_bao": dict(name="Lục bảo", tone="gold", accent="#3DDC97", alt="#FFC24A", ink="#032818",
                    bgs=[("gradient", "#11624a", "#03140f"), ("spot", "#167556", "#03110c"), ("dots", "#1d5c48", "#05170f")],
                    panel="#0E2219", border="#24503D", glow="#103224"),
}
HIST = Path.home() / ".ccut" / "looks.json"


def choose(pdir, want: str | None = None) -> str:
    """look của dự án: giữ look đã ghi (dựng lại không đổi màu); chưa có → chọn look khác 3 video gần nhất."""
    pdir = Path(pdir)
    f = pdir / "look.json"
    ch = for_channel(pdir)                       # video đã gán kênh → luôn theo phong cách cố định của kênh
    if ch and want not in LOOKS:
        want = ch
    if want in LOOKS:
        name = want
    else:
        try:
            name = json.loads(f.read_text(encoding="utf-8")).get("look")
        except Exception:
            name = None
        if name in LOOKS:
            return name
        try:
            hist = json.loads(HIST.read_text(encoding="utf-8"))
        except Exception:
            hist = []
        if want not in LOOKS:
            recent = [h for h in hist[-3:]]
            used = {LOOKS[h].get("skin", "neon") for h in recent if h in LOOKS}
            cands = [k for k in LOOKS if k not in recent and LOOKS[k].get("skin", "neon") not in used] \
                or [k for k in LOOKS if k not in recent] or list(LOOKS)
            name = random.Random(str(pdir)).choice(cands)
        try:
            HIST.parent.mkdir(parents=True, exist_ok=True)
            HIST.write_text(json.dumps((hist + [name])[-12:]), encoding="utf-8")
        except Exception:
            pass
    try:
        f.write_text(json.dumps({"look": name, "name": LOOKS[name]["name"]}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return name


def apply_theme(th: dict, name: str) -> dict:
    L = LOOKS[name]
    th = dict(th)
    c1, c2 = L["bgs"][0][1], L["bgs"][0][2] or "#121212"
    if L.get("caption"):
        th["caption_fx"] = dict(L["caption"])
    if L.get("caption_media"):
        th["caption_fx_media"] = dict(L["caption_media"])
    if L.get("light"):
        th["text"] = L.get("ink_text", "#16130F")
    th.update(accent=L["accent"], alt=L["alt"], ink_on_accent=L["ink"], caption_active=L["accent"], panel=L["panel"],
              border=L["border"], glow=L["glow"], bg=c2, bg2=c2, look=name, mg_tone=L["tone"])
    return th


def scene_bg(name: str, bg: dict | None, idx: int) -> dict | None:
    """nền cảnh theo look: kiểu nền Claude chọn vẫn giữ nếu có trong look, còn màu luôn theo look; đổi biến thể theo đoạn
    (mỗi ~3 cảnh) để video không một nền suốt. Nền sáng (cream) / ảnh / bản đồ giữ nguyên."""
    if bg and bg.get("keep"):
        return bg
    if bg and bg.get("style") == "cream" and not LOOKS[name].get("skin"):
        return bg
    L = LOOKS[name]["bgs"]
    st, c1, c2 = L[(idx // 3) % len(L)]
    if bg and bg.get("style"):
        hit = [x for x in L if x[0] == bg["style"]]
        if hit and (idx // 3) % 2 == 0:
            st, c1, c2 = hit[0]
    out = {"style": st, "color": c1}
    if c2:
        out["color2"] = c2
    return out


# skill Giá Trị (video câu ngẫm): nền tối dịu, phụ đề trắng bóng nhẹ — không khung, không motion graphic
LOOKS["gia_tri"] = dict(name="Giá Trị", tone="gold", accent="#FFE2A8", alt="#9FB7D6", ink="#14110D",
                        bgs=[("solid", "#0D1117", None), ("solid", "#0F141B", None), ("solid", "#0B1015", None)],
                        panel="#141B24", border="#FFE2A8", glow="#0D1117",
                        caption=dict(font="body_bold", color="#FFFFFF", stroke=0, shadow=0.7, active_color="#FFE2A8"),
                        caption_media=dict(font="body_bold", color="#FFFFFF", stroke=0, shadow=0.7, active_color="#FFE2A8"))

# ---------------- PHONG CÁCH KÊNH (skin): đổi tận gốc font, phụ đề, nền, khung thẻ MG — không chỉ đổi màu ----------------
# look có "skin" ≠ neon → font chữ nhấn riêng, phụ đề riêng, CSS đè lên mọi Motion Graphics (mg2 + fx).
LOOKS.update({
    "bao_chi": dict(name="Báo chí", skin="bao_chi", light=True, tone="red", accent="#C8102E", alt="#1B4D8C", ink="#FFFFFF",
                    font="PlusJakartaSans-ExtraBold.ttf", ink_text="#16130F",
                    bgs=[("paper", "#F3ECE0", None), ("paper", "#EFE6D6", None), ("paper", "#F6F1E7", None)],
                    panel="#FFFDF8", border="#16130F", glow="#F3ECE0",
                    caption=dict(font="body_bold", plate="#111111", plate_pad=14, color="#FFFFFF", stroke=0, shadow=0,
                                 active_color="#FF6A5C")),
    "ban_tin": dict(name="Bản tin", skin="ban_tin", pack="news", pal=dict(ink="#FFFFFF", paper="#0E1A2B", strip="#18294A"), tone="gold", accent="#E8B04B", alt="#4FA3FF", ink="#0E1A2B",
                    font="Oswald-Bold.ttf",
                    bgs=[("solid", "#0E1A2B", None), ("solid", "#122036", None), ("solid", "#0B1522", None)],
                    panel="#132338", border="#E8B04B", glow="#0E1A2B",
                    caption=dict(upper=True, plate="#E8B04B", plate_pad=14, color="#0E1A2B", stroke=0, shadow=0,
                                 active_color="#8A1C00")),
    "pastel_xanh": dict(name="Pastel xanh", skin="pastel", pack="soft", light=True, tone="blue", accent="#1F8A70", alt="#3B6FD8", ink="#FFFFFF",
                        font="Lexend-Bold.ttf", ink_text="#1E2B3A", p1="#EAF7F2", p2="#DDEBFA",
                        bgs=[("cream", "#E6F4EE", None), ("cream", "#E3ECF9", None), ("cream", "#EEF6EA", None)],
                        panel="#FFFFFF", border="#D5E3EC", glow="#E6F4EE",
                        caption=dict(plate="#FFFFFF", plate_pad=16, color="#1E2B3A", stroke=0, shadow=0.15, active_color="#1F8A70")),
    "pastel_hong": dict(name="Pastel hồng", skin="pastel", pack="soft", light=True, tone="red", accent="#D6457A", alt="#7A5CD6", ink="#FFFFFF",
                        font="Lexend-Bold.ttf", ink_text="#3A1E2B", p1="#FCEDF2", p2="#F1E8FB",
                        bgs=[("cream", "#FBEAF0", None), ("cream", "#F2EAFB", None), ("cream", "#FDF0EA", None)],
                        panel="#FFFFFF", border="#F0D5E0", glow="#FBEAF0",
                        caption=dict(plate="#FFFFFF", plate_pad=16, color="#3A1E2B", stroke=0, shadow=0.15, active_color="#D6457A")),
    "pop_cam": dict(name="Pop cam", skin="pop", pack="pop", pal=dict(acc="#FF3D7F", ink="#111111"), light=True, tone="red", accent="#111111", alt="#FFFFFF", ink="#FFE600",
                    font="Anton-Regular.ttf", ink_text="#111111", p1="#FFC83D", p2="#FF7A2F",
                    bgs=[("diag", "#FFC83D", "#FF7A2F"), ("diag", "#FFD95A", "#FF5A3C"), ("diag", "#FFE07A", "#FF8A1F")],
                    panel="#FFFFFF", border="#111111", glow="#FFC83D",
                    caption=dict(upper=True, color="#FFFFFF", stroke=9, stroke_color="#111111", shadow=0, active_color="#FFE600")),
    "pop_xanh": dict(name="Pop xanh", skin="pop", pack="pop", pal=dict(acc="#FFE600", ink="#111111"), light=True, tone="blue", accent="#111111", alt="#FFFFFF", ink="#FFE600",
                     font="Anton-Regular.ttf", ink_text="#111111", p1="#7FD8FF", p2="#3D6BFF",
                     bgs=[("diag", "#7FD8FF", "#3D6BFF"), ("diag", "#9BE8D8", "#2E8BFF"), ("diag", "#8FD0FF", "#5A4DFF")],
                     panel="#FFFFFF", border="#111111", glow="#7FD8FF",
                     caption=dict(upper=True, color="#FFFFFF", stroke=9, stroke_color="#111111", shadow=0, active_color="#FFE600")),
})
LOOKS["swiss"] = dict(name="Swiss", skin="bao_chi", pack="swiss", light=True, tone="red", accent="#FF4D1F", alt="#1F3BFF", ink="#FFFFFF",
                     font="Archivo-ExtraBold.ttf", ink_text="#111111",
                     bgs=[("solid", "#F2F0EB", None), ("solid", "#ECE9E2", None), ("solid", "#F5F3EE", None)],
                     panel="#FFFFFF", border="#111111", glow="#F2F0EB",
                     caption=dict(font="body_bold", color="#111111", stroke=0, shadow=0, active_color="#FF4D1F"),
                     caption_media=dict(font="body_bold", color="#FFFFFF", stroke=6, stroke_color="#111111", shadow=0.4, active_color="#FFB199"))
NEON = ["dem_vang", "dai_duong", "hoang_hon", "than_cam", "cham_tim", "luc_bao"]
CHANNEL = {"bat-dong-san": "ban_tin", "chia-se": "swiss", "suc-khoe": "pastel_xanh", "lam-dep": "pastel_hong",
           "giao-duc": "pop_xanh", "fnb": "pop_cam"}


def for_channel(pdir) -> str | None:
    """kênh của video (channel.json) → phong cách cố định của kênh."""
    try:
        ch = json.loads((Path(pdir) / "channel.json").read_text(encoding="utf-8")).get("channel")
    except Exception:
        ch = None
    return CHANNEL.get(ch)


_COMMON = """.root,.fxroot,.kt{font-family:'CCut Display','Be Vietnam Pro',sans-serif!important;font-synthesis:none}
.sub,.pn,.hud,.msub{font-family:'Be Vietnam Pro',sans-serif!important}
.glow{filter:none!important}.sweep,.card:after,.grain,.vig{display:none!important}
.grad,.gold,.blue,.red{background:none!important;-webkit-background-clip:border-box!important;filter:none!important;color:var(--sk-acc)!important}"""
_LIGHT = """.fxgrid{display:none!important}.fxroot,.root,.kt{color:var(--sk-ink)!important;--ink:var(--sk-ink)!important}
.kt-glass{background:rgba(255,255,255,.92)!important;backdrop-filter:none!important;border-color:rgba(0,0,0,.08)!important;box-shadow:0 calc(18px*var(--s)) calc(40px*var(--s)) rgba(0,0,0,.14)!important}.fxroot *,.root *{text-shadow:none!important}
.fxroot [style*="color:#fff"],.fxroot [style*="color:#FFF"],.fxroot [style*="color:white"],.root .tt{color:var(--sk-ink)!important}
.pn{color:var(--sk-ink)!important;opacity:.7}
.kt-line,.kt-ch,.kt-mi,.fxroot .w:not(.hw){color:var(--sk-ink)!important;filter:none!important}"""
SKIN_CSS = {
    "bao_chi": _COMMON + _LIGHT + """.fxbg{background:var(--sk-p1)!important}
.card{background:#FFFDF8!important;backdrop-filter:none!important;border:calc(3px*var(--s)) solid #16130F!important;border-radius:calc(4px*var(--s))!important;
 box-shadow:calc(10px*var(--s)) calc(10px*var(--s)) 0 #16130F!important;color:#16130F!important}
.lbl,.chip{background:#16130F!important;color:#FFF!important;border:none!important;border-radius:calc(2px*var(--s))!important;box-shadow:none!important;backdrop-filter:none!important}
.big,.t1{letter-spacing:-.015em!important}""",
    "ban_tin": _COMMON + """.fxbg{background:#0E1A2B!important}.fxgrid{opacity:.10!important}
.card{background:#132338!important;backdrop-filter:none!important;border:none!important;border-left:calc(12px*var(--s)) solid #E8B04B!important;
 border-radius:0!important;box-shadow:0 calc(18px*var(--s)) calc(40px*var(--s)) rgba(0,0,0,.45)!important}
.lbl,.chip{background:#E8B04B!important;color:#0E1A2B!important;border:none!important;border-radius:0!important;box-shadow:none!important;backdrop-filter:none!important}
.big,.t1{text-transform:uppercase;letter-spacing:.01em!important}""",
    "pastel": _COMMON + _LIGHT + """.fxbg{background:linear-gradient(165deg,var(--sk-p1),var(--sk-p2))!important}
.card{background:#FFFFFF!important;backdrop-filter:none!important;border:none!important;border-radius:calc(56px*var(--s))!important;
 box-shadow:0 calc(24px*var(--s)) calc(60px*var(--s)) rgba(40,60,90,.16)!important;color:var(--sk-ink)!important}
.lbl,.chip{background:#FFFFFF!important;color:var(--sk-ink)!important;border:none!important;box-shadow:0 calc(10px*var(--s)) calc(26px*var(--s)) rgba(40,60,90,.16)!important;backdrop-filter:none!important}""",
    "pop": _COMMON + _LIGHT + """.fxbg{background:linear-gradient(160deg,var(--sk-p1) 0 58%,var(--sk-p2) 58%)!important}
.card{background:#FFFFFF!important;backdrop-filter:none!important;border:calc(6px*var(--s)) solid #111!important;border-radius:calc(20px*var(--s))!important;
 box-shadow:calc(14px*var(--s)) calc(14px*var(--s)) 0 #111!important;color:#111!important}
.lbl,.chip{background:#FFE600!important;color:#111!important;border:calc(4px*var(--s)) solid #111!important;box-shadow:calc(6px*var(--s)) calc(6px*var(--s)) 0 #111!important;backdrop-filter:none!important}
.big,.t1{text-transform:uppercase;letter-spacing:.01em!important}
.grad,.gold,.blue,.red{color:#FFFFFF!important;-webkit-text-stroke:calc(4px*var(--s)) #111;paint-order:stroke fill}""",
}


def skin_css(name: str | None) -> str:
    L = LOOKS.get(name or "") or {}
    css = SKIN_CSS.get(L.get("skin", ""), "")
    if not css:
        return ""
    v = (f"--sk-acc:{L['accent']};--sk-ink:{L.get('ink_text', '#FFFFFF')};--sk-p1:{L.get('p1', L['bgs'][0][1])};"
         f"--sk-p2:{L.get('p2', L['bgs'][0][2] or L['bgs'][0][1])}")
    return f"<style>.root,.fxroot{{{v}}}\n{css}</style>"


def font_file(name: str | None):
    from ..paths import ROOT
    f = (LOOKS.get(name or "") or {}).get("font")
    p = ROOT / "assets" / "fonts" / f if f else None
    return p if p and p.exists() else None
