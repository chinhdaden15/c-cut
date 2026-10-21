"""Dựng 3 video hướng dẫn cài C-Cut (Windows / Mac chip M / Mac Intel) bằng HyperFrames: màn hình mô phỏng + giao diện C-Cut thật
(ảnh chụp shots/) + con trỏ + phóng to + phụ đề theo giọng (mốc từ bản chép lời voice16k.wav).
  python out/hdsd/build.py [win|m|intel ...] [--stills]"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
from thagent.hyper import runtime  # noqa: E402

VOICE = Path("/Users/myatm/Downloads/HDSD Ccut.mp3")
VOICES = {"mac": Path("/Users/myatm/Downloads/Ap C-Cut/HDSD máy Macos.mp3")}       # video macOS gộp (chip M + Intel) — giọng riêng
WORDS = {"mac": "words_mac.json"}
BOX = json.loads((HERE / "shots" / "boxes.json").read_text())
W, H = 1920, 1080
SC = 0.875                        # màn hình mô phỏng thu nhỏ, chừa dải dưới cho phụ đề
SX, SY = (W - W * SC) / 2, 16
FONT = "'Be Vietnam Pro','Segoe UI',-apple-system,sans-serif"


class TL:
    """tween GSAP. Toạ độ: số (px khung desktop 1920×1080) hoặc điểm đo trong trình duyệt tl.p("#id") (đo TRƯỚC khi tạo tween)."""
    def __init__(self):
        self.js = []
        self.q = []

    def p(self, sel, dy=0, ax=0.5, ay=0.5):
        self.q.append(f'pt("{sel}",{dy},{ax},{ay})')
        return f"Q[{len(self.q) - 1}]"

    def b(self, sel, dy=0):
        self.q.append(f'bx("{sel}",{dy})')
        return f"Q[{len(self.q) - 1}]"

    @staticmethod
    def xy(x, y=None):
        if isinstance(x, str) and y is None:
            return f"{x}.x", f"{x}.y"
        if isinstance(x, (tuple, list)):
            return str(round(x[0], 1)), str(round(x[1], 1))
        return str(round(x, 1)), str(round(y, 1))

    def add(self, s):
        self.js.append(s)

    def show(self, t, sel, d=0.35, frm=None):
        frm = frm or {}
        self.add(f'tl.set("{sel}",{json.dumps({"opacity": 0, **frm})},{t:.3f});')
        self.add(f'tl.to("{sel}",{json.dumps({"opacity": 1, **({"x": 0} if "x" in frm else {}), **({"y": 0} if "y" in frm else {}), **({"scale": 1} if "scale" in frm else {}), "duration": d, "ease": "power2.out"})},{t:.3f});')

    def hide(self, t, sel, d=0.3):
        self.add(f'tl.to("{sel}",{{opacity:0,duration:{d},ease:"power1.in"}},{t:.3f});')

    def set(self, t, sel, props):
        self.add(f'tl.set("{sel}",{json.dumps(props)},{t:.3f});')

    def to(self, t, sel, props, d=0.5, ease="power2.inOut"):
        self.add(f'tl.to("{sel}",{json.dumps({**props, "duration": d, "ease": ease})},{t:.3f});')

    # con trỏ
    def move(self, t, x, y=None, d=0.6):
        X, Y = self.xy(x, y)
        self.add(f'tl.to("#cur",{{x:{X},y:{Y},duration:{d},ease:"power2.inOut"}},{t:.3f});')

    def click(self, t, x=None, y=None):
        if x is not None:
            self.move(t - 0.65, x, y, 0.6)
            X, Y = self.xy(x, y)
            self.add(f'tl.set("#rip",{{x:{X}-30,y:{Y}-30}},{t:.3f});')
        self.add(f'tl.to("#cur svg",{{scale:0.82,duration:0.08,yoyo:true,repeat:1,transformOrigin:"0 0"}},{t:.3f});')
        self.add(f'tl.set("#rip",{{opacity:0.75,scale:0.3}},{t:.3f});')
        self.add(f'tl.to("#rip",{{opacity:0,scale:1.4,duration:0.5,ease:"power2.out"}},{t:.3f});')

    def zoom(self, t, cx, cy=None, s=1.4, d=0.8):
        X, Y = self.xy(cx, cy)
        self.add(f'tl.to("#cam",Object.assign(zm({X},{Y},{s}),{{duration:{d},ease:"power2.inOut"}}),{t:.3f});')

    def unzoom(self, t, d=0.8):
        self.to(t, "#cam", {"x": 0, "y": 0, "scale": 1}, d)

    def ring(self, t, idx, box, dur=2.2):
        if isinstance(box, str):
            self.add(f'tl.set("#ring{idx}",{{x:{box}.x-8,y:{box}.y-8,width:{box}.w+16,height:{box}.h+16}},{t:.3f});')
        else:
            x, y, w, h = box
            self.set(t, f"#ring{idx}", {"x": x - 8, "y": y - 8, "width": w + 16, "height": h + 16})
        self.add(f'tl.set("#ring{idx}",{{opacity:0,scale:1.15}},{t:.3f});')
        self.add(f'tl.to("#ring{idx}",{{opacity:1,scale:1,duration:0.35,ease:"back.out(2)"}},{t:.3f});')
        self.hide(t + dur, f"#ring{idx}")

    def typing(self, t, prefix, n, cps=18):
        for i in range(n):
            self.set(t + i / cps, f"#{prefix}{i}", {"opacity": 1})


def chars(prefix, text, cls=""):
    return "".join(f'<span id="{prefix}{i}" class="ch {cls}">{escape(c) if c != " " else "&nbsp;"}</span>' for i, c in enumerate(text))


# ---------------- linh kiện giao diện ----------------
CSS = f"""
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:{FONT};background:#0b0f1a}}
#root{{position:relative;width:{W}px;height:{H}px;overflow:hidden;background:radial-gradient(1200px 700px at 20% 0%,#1d2b55 0%,#0b0f1a 60%),#0b0f1a}}
#screen{{position:absolute;left:{SX}px;top:{SY}px;width:{W}px;height:{H}px;transform:scale({SC});transform-origin:0 0;overflow:hidden;border-radius:18px;
  box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 0 2px rgba(255,255,255,.08)}}
#cam{{position:absolute;inset:0;transform-origin:0 0}}
.abs{{position:absolute}} .hid{{opacity:0}} .ch{{opacity:0}}
#band{{position:absolute;left:0;right:0;top:{SY + H * SC + 6}px;bottom:0;display:flex;align-items:center;justify-content:center}}
.sub{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);max-width:1380px;width:max-content;text-align:center;color:#fff;font-size:33px;font-weight:600;
  line-height:1.3;text-shadow:0 2px 8px rgba(0,0,0,.6)}}
#chip{{position:absolute;left:{SX}px;top:{SY + H * SC + 24}px;color:#fff;font-size:24px;font-weight:700}}
.chipt{{position:absolute;left:0;top:0;white-space:nowrap;padding:8px 18px;background:#2b6cff;border-radius:999px}}
#cur{{position:absolute;left:0;top:0;z-index:900}} #cur svg{{display:block}}
#rip{{position:absolute;left:0;top:0;width:60px;height:60px;border-radius:50%;background:rgba(43,108,255,.55);z-index:899;opacity:0}}
.ring{{position:absolute;left:0;top:0;border:4px solid #ffb020;border-radius:12px;box-shadow:0 0 0 6px rgba(255,176,32,.25);z-index:850;opacity:0}}
.card{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#fff;opacity:0;z-index:950}}
.logo{{width:150px;height:150px;border-radius:36px;background:linear-gradient(140deg,#4f8cff,#2b5bd8);display:flex;align-items:center;justify-content:center;
  font:800 92px Montserrat,sans-serif;color:#fff;box-shadow:0 20px 60px rgba(43,108,255,.45)}}
.ttl{{font:800 68px Montserrat,{FONT};margin-top:36px;letter-spacing:-1px}} .st{{font-size:34px;color:#b8c4e6;margin-top:14px}}
.req{{display:flex;gap:22px;margin-top:40px;flex-wrap:wrap;justify-content:center;max-width:1500px}}
.ri{{width:330px;padding:28px 24px;border-radius:22px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);text-align:center;opacity:0}}
.ri .ic{{font-size:58px}} .ri b{{display:block;font-size:30px;margin-top:12px}} .ri span{{display:block;font-size:22px;color:#b8c4e6;margin-top:6px}}
/* cửa sổ */
.win{{position:absolute;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.45),0 0 0 1px rgba(0,0,0,.15);opacity:0}}
.wt{{height:34px;display:flex;align-items:center;padding:0 12px;font-size:14px;color:#222;background:#f3f3f3;border-bottom:1px solid #ddd}}
.wt.dark{{background:#1f1f1f;color:#ddd;border-color:#000}}
.wctl{{margin-left:auto;display:flex;gap:22px;color:#444;font-size:15px}} .wt.dark .wctl{{color:#bbb}}
.tl3{{display:flex;gap:8px;margin-right:14px}} .tl3 i{{width:13px;height:13px;border-radius:50%;display:block}}
.btn{{display:inline-flex;align-items:center;justify-content:center;padding:0 22px;height:38px;border-radius:6px;font-size:15px;font-weight:600}}
.bp{{background:#0067c0;color:#fff}} .bg{{background:#fff;color:#222;border:1px solid #bbb}} .mbp{{background:#2f7bf6;color:#fff;border-radius:8px}}
.mbg{{background:#e9e9ed;color:#111;border-radius:8px}}
"""

CURSOR_WIN = '<svg width="34" height="46" viewBox="0 0 17 23"><path d="M1 1 L1 18 L5.2 14 L8.2 21 L11 19.8 L8 13 L14 13 Z" fill="#fff" stroke="#000" stroke-width="1.2"/></svg>'
CURSOR_MAC = '<svg width="34" height="46" viewBox="0 0 17 23"><path d="M1 1 L1 18 L5.2 14 L8.2 21 L11 19.8 L8 13 L14 13 Z" fill="#000" stroke="#fff" stroke-width="1.4"/></svg>'
APPLE = '<svg width="16" height="19" viewBox="0 0 16 19"><path fill="#111" d="M13.2 10.1c0-2.2 1.8-3.3 1.9-3.3-1-1.5-2.6-1.7-3.2-1.7-1.4-.1-2.6.8-3.3.8-.7 0-1.7-.8-2.9-.8C4.2 5.1 2.8 6 2 7.4c-1.6 2.8-.4 6.9 1.1 9.2.8 1.1 1.7 2.3 2.8 2.3 1.1 0 1.6-.7 2.9-.7s1.7.7 2.9.7c1.2 0 2-1.1 2.7-2.2.9-1.3 1.2-2.5 1.2-2.6 0 0-2.4-.9-2.4-4zM11 3.6c.6-.8 1-1.8.9-2.9-.9 0-2 .6-2.6 1.4-.6.7-1.1 1.7-1 2.8 1 .1 2-.5 2.7-1.3z"/></svg>'


GUIDE_TABS = [("win", "Windows", [("win", "Tải C-Cut cho Windows")], "Windows 10 / 11 · 64-bit", "windows"),
              ("mac", "macOS", [("m", "Tải cho Mac chip M"), ("intel", "Tải cho Mac chip Intel")], "Chip Apple M1–M4 hoặc Intel", "macos")]


def guide_page(default):
    """bản mô phỏng trang ccut-license…/huong-dan (trang tải chính thức) — tab hệ điều hành + video + nút tải."""
    tabs = "".join(f'<div id="gt_{k}" class="gtab"><span id="gton_{k}" class="gton{"" if k == default else " hid"}"></span><span style="position:relative">{escape(n)}</span></div>'
                   for k, n, *_ in GUIDE_TABS)
    panes = "".join(f'<div id="gp_{k}" class="gpane{"" if k == default else " hid"}"><img src="assets/poster_{f}.jpg" class="gvid">'
                    f'<div class="gplay">▶</div><div class="gdl">' + "".join(f'<div id="gb_{bid}" class="gbtn">⬇ {escape(bt)}</div>' for bid, bt in bs)
                    + f'<span>{escape(c)}</span></div></div>'
                    for k, n, bs, c, f in GUIDE_TABS)
    return f"""<div class="gp"><div class="gh1">Hướng dẫn cài đặt C-Cut</div>
<div class="gdim">Xem video hướng dẫn đúng máy của bạn, rồi tải file cài ngay bên dưới.</div><div class="gtabs">{tabs}</div>
<div style="position:relative;height:900px">{panes}</div></div>"""


GP_CSS = """
.gp{background:#0f1012;color:#ececee;padding:34px 120px;min-height:1500px;font-family:-apple-system,'Be Vietnam Pro',sans-serif}
.gh1{font:800 40px Montserrat,sans-serif}.gdim{color:#a0a1a8;font-size:20px;margin-top:8px}
.gtabs{display:flex;gap:12px;margin:26px 0 18px}.gtab{position:relative;padding:12px 22px;border-radius:10px;background:#1f2024;font-size:21px;font-weight:600}
.gton{position:absolute;inset:0;border-radius:10px;background:#4f8cff}
.gpane{position:absolute;left:0;top:0;width:1380px}.gvid{width:1380px;height:776px;object-fit:cover;border-radius:14px;display:block;background:#000}
.gplay{position:absolute;left:640px;top:338px;width:100px;height:100px;border-radius:50%;background:rgba(0,0,0,.55);color:#fff;font-size:44px;display:flex;align-items:center;justify-content:center}
.gdl{display:flex;align-items:center;gap:18px;margin-top:20px}.gdl span{color:#a0a1a8;font-size:20px}
.gbtn{background:#4f8cff;color:#fff;font-weight:700;font-size:23px;padding:16px 28px;border-radius:10px}
"""


def release_page(files):
    rows = "".join(f'<div class="rr" id="as{i}"><span>📦</span><b>{escape(n)}</b><em>{s}</em></div>' for i, (n, s) in enumerate(files))
    intro = "".join(f'<p>{escape(t)}</p>' for t in [
        "Bạn quay video nói chuyện, review sản phẩm hay giới thiệu nhà đất, nhưng phần dựng mới là thứ ngốn thời gian nhất.",
        "C-Cut làm phần đó thay bạn. Bạn chỉ cần đưa clip vào — trợ lý dựng AI sẽ xem, nghe và dựng thành video hoàn chỉnh.",
        "✂️ Tự cắt gọn như editor thật · ✨ Chữ nổi bật, hình minh hoạ đúng nội dung · 💬 Sửa video bằng cách nhắn tin",
        "🎯 3 phong cách dựng: Talking Head, Review, Voice to Motion · 💻 Chạy trên Windows và Mac"])
    return f"""<div class="rp">
<div class="rph">chinhdaden15 / <b>c-cut-releases</b></div>
<div class="rpt">C-Cut 1.7.1 <span>Latest</span></div>
<h3>🎬 C-Cut – Quay xong là có video, khỏi ngồi dựng hàng giờ</h3>{intro}
<div class="rpa">Tải về / Download</div>
<div class="rpb">Assets <span>{len(files)}</span></div>{rows}</div>"""


RP_CSS = """
.rp{padding:30px 120px;color:#1f2328;font-size:18px}.rph{font-size:20px;color:#59636e;padding-bottom:22px;border-bottom:1px solid #d1d9e0}
.rpt{font:800 42px Montserrat,sans-serif;margin:28px 0 18px}.rpt span{font:600 16px sans-serif;color:#1a7f37;border:1px solid #1a7f37;border-radius:999px;padding:3px 12px;vertical-align:middle;margin-left:12px}
.rp h3{font-size:28px;margin:24px 0 14px}.rp p{line-height:1.7;margin:10px 0;color:#333;height:92px}
.rpa{font-size:26px;font-weight:700;margin-top:40px;height:60px}.rpb{font-size:22px;font-weight:700;padding:14px 0;border-bottom:1px solid #d1d9e0;height:62px}
.rpb span{background:#eff2f5;border-radius:999px;padding:2px 10px;font-size:15px;margin-left:8px}
.rr{display:flex;align-items:center;gap:14px;height:58px;border-bottom:1px solid #eef1f4;font-size:19px}.rr b{color:#0969da;font-weight:600}.rr em{margin-left:auto;color:#59636e;font-style:normal}
"""
FILES = [("C-Cut-mac-arm64.dmg", "362 MB"), ("C-Cut-mac-intel.dmg", "392 MB"), ("C-Cut-Setup.exe", "301 MB"),
         ("Huong.dan.su.dung.C-Cut.pdf", "224 KB"), ("Source code (zip)", "")]


def asset_y(i, scroll):          # toạ độ y (trong vùng nội dung trình duyệt) của dòng tải thứ i sau khi cuộn
    top = 30 + 43 + 22 + 28 + 60 + 18 + 62 + 4 * 112 + 40 + 60 + 62   # khối trên (ước lượng theo CSS cố định) — kiểm bằng stills
    return top + i * 58 + 29 - scroll


def browser(id_, x, y, w, h, url, inner, dark=False, mac=False):
    bar = (f'<div class="tl3"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>' if mac else "")
    ctl = "" if mac else '<div class="wctl"><span>—</span><span>▢</span><span>✕</span></div>'
    return f"""<div id="{id_}" class="win" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px">
<div class="wt" style="height:40px;background:#e8eaed;border:0">{bar}<div style="background:#fff;border-radius:8px 8px 0 0;padding:9px 18px;margin-top:6px;font-size:14px">C-Cut · Releases</div>{ctl}</div>
<div style="height:46px;display:flex;align-items:center;gap:14px;padding:0 14px;background:#fff;border-bottom:1px solid #ddd;color:#555">
<span>←</span><span>→</span><span>⟳</span><div style="flex:1;background:#f1f3f4;border-radius:999px;padding:9px 18px;font-size:16px;color:#202124">🔒 {escape(url)}</div></div>
<div style="position:absolute;left:0;right:0;top:86px;bottom:0;overflow:hidden;background:#fff"><div id="{id_}_sc">{inner}</div></div></div>"""


def app_window(os_, shots, x, y):
    imgs = "".join(f'<img id="app_{k}" class="abs hid" src="assets/{os_}_{k}.png" style="left:0;top:0;width:1600px;height:900px">' for k in shots)
    if os_ == "windows":
        bar = '<div class="wt dark" style="height:32px"><span style="color:#4f8cff;font-weight:800;margin-right:8px">C</span>C-Cut<div class="wctl"><span>—</span><span>▢</span><span>✕</span></div></div>'
    else:
        bar = '<div class="wt dark" style="height:28px;justify-content:center;position:relative"><div class="tl3" style="position:absolute;left:12px"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>C-Cut</div>'
    th = 32 if os_ == "windows" else 28
    return f'<div id="appw" class="win" style="left:{x}px;top:{y}px;width:1600px;height:{900 + th}px;background:#111">{bar}<div style="position:relative;width:1600px;height:900px">{imgs}</div></div>', (x, y + th)


def console(id_, x, y, w, h, title, lines, dark_bg, mac=False):
    """lines: [(prefix_id or None, text, color)] — dòng có prefix gõ từng chữ; còn lại hiện cả dòng (id {id_}_l{i})"""
    out = []
    for i, (typ, text, col) in enumerate(lines):
        if typ:
            out.append(f'<div style="color:{col}">{escape(typ)}{chars(f"{id_}c{i}_", text)}</div>')
        else:
            out.append(f'<div id="{id_}_l{i}" class="hid" style="color:{col}">{escape(text)}</div>')
    bar = (f'<div class="wt" style="justify-content:center;position:relative;background:#e8e8e8"><div class="tl3" style="position:absolute;left:12px"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>{escape(title)}</div>'
           if mac else f'<div class="wt dark">{escape(title)}<div class="wctl"><span>—</span><span>▢</span><span>✕</span></div></div>')
    return f"""<div id="{id_}" class="win" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{dark_bg}">{bar}
<div style="padding:16px 20px;font:19px/1.6 Menlo,Consolas,monospace;color:#eee">{''.join(out)}</div></div>"""


def login_page(id_, x, y, mac):
    inner = f"""<div style="display:flex;justify-content:center;padding-top:90px;background:#faf9f5;height:900px">
<div style="width:520px;text-align:center;color:#222">
<div style="font:700 40px Georgia,serif">Claude</div>
<div id="{id_}_p1"><div style="font-size:24px;margin:34px 0 22px">Đăng nhập để tiếp tục</div>
<div style="border:1px solid #ccc;border-radius:10px;padding:14px 16px;text-align:left;font-size:19px;background:#fff;height:56px">{chars(id_ + "e", "ban@gmail.com")}</div>
<div id="{id_}_go" class="btn" style="background:#222;color:#fff;width:100%;height:52px;margin-top:16px;border-radius:10px;font-size:18px">Tiếp tục</div></div>
<div id="{id_}_p2" class="hid" style="margin-top:-170px"><div style="font-size:26px;margin:34px 0 14px;font-weight:600">Kết nối C-Cut với tài khoản Claude?</div>
<div style="font-size:18px;color:#555;line-height:1.6">C-Cut sẽ dùng tài khoản Claude của bạn để lên kế hoạch dựng video.</div>
<div id="{id_}_ok" class="btn" style="background:#c96442;color:#fff;width:100%;height:52px;margin-top:26px;border-radius:10px;font-size:18px">Cho phép</div></div>
</div></div>"""
    return browser(id_, x, y, 1300, 820, "claude.ai/oauth/authorize", inner, mac=mac)


# ---------------- video ----------------
SUB_FIX = [("C -Cut", "C-Cut"), ("Cloud", "Claude"), ("Cloth", "Claude"), ("chống", "trống"), ("Get for", "Git for"), ("Mark", "Mac"),
           ("ccutsetup.exe", "C-Cut-Setup.exe"), ("C-Cut-Mark-Arm64.dmg", "C-Cut-mac-arm64.dmg"), ("C-Cut-Mac-Arm64.dmg", "C-Cut-mac-arm64.dmg"),
           ("C-Cut-Mac-Intel.dmg", "C-Cut-mac-intel.dmg"), ("chip mở", "chip M"), ("mô đồ", "model"),
           ("tiến chỉnh", "tiến trình"), ("Store. ", ""), ("More Info", "More info"), ("Run Anyway", "Run anyway"),
           ("10GB", "10 GB"), ("8GB", "8 GB"), ("3GB", "3 GB"), ("mở C-Cut", "Mở C-Cut"), ("Mac OS", "macOS"), ("Seacut", "C-Cut"),
           ("Bấm vào, chọn", "chọn")]


def subs(a, b, wfile="words.json"):
    """câu phụ đề (đã sửa chính tả) trong [a, b) của file giọng → [(t0, t1, text)] giây tương đối"""
    words = json.loads((HERE / wfile).read_text())
    out, cur = [], []
    raw = [dict(w) for w in words if a - 0.8 <= w["s"] < b - 0.2 and w["e"] > a - 0.3]
    ws = []                                  # ghép mảnh: "C" "-Cut" → "C-Cut"; "Arm64" ".dmg"; "X gạch nối Y" → "X-Y"
    i = 0
    while i < len(raw):
        w = raw[i]
        if ws and w["t"][:1] in "-." and len(w["t"]) > 1:
            ws[-1]["t"] += w["t"]; ws[-1]["e"] = w["e"]
        elif ws and w["t"].lower() == "gạch" and i + 2 < len(raw) and raw[i + 1]["t"].lower().startswith("nối"):
            ws[-1]["t"] += "-" + raw[i + 2]["t"]; ws[-1]["e"] = raw[i + 2]["e"]; i += 2
        else:
            ws.append(w)
        i += 1
    for i, w in enumerate(ws):
        cur.append(w)
        gap = ws[i + 1]["s"] - w["e"] if i + 1 < len(ws) else 9
        end = w["t"].rstrip()[-1:]
        nxt = ws[i + 1]["t"] if i + 1 < len(ws) else ""
        starter = nxt in ("Các", "Chúc", "Đây", "Và", "Bước", "Nếu", "Khi", "Làm", "Riêng", "Vậy", "Ở", "Một", "Trình", "Bây", "Tiếp",
                          "Lần", "Máy", "Rồi", "Kéo", "Dung", "Hẹn", "Tải") and nxt != w["t"]
        if end in ".!?" or (end == "," and len(cur) >= 7) or (gap > 0.32 and len(cur) >= 3) or (starter and len(cur) >= 2 and end not in ",") or len(cur) >= 16:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    merged = []                              # mảnh lẻ 1–2 chữ → nối vào câu trước (câu trước chưa kết thúc)
    for g in out:
        if merged and len(g) <= 2 and len(merged[-1]) <= 13 and merged[-1][-1]["t"].rstrip()[-1:] not in ".!?":
            merged[-1] = merged[-1] + g
        else:
            merged.append(g)
    out = merged
    res = []
    for g in out:
        t = " ".join(x["t"] for x in g).replace(" ,", ",")
        for x, y in SUB_FIX:
            t = t.replace(x, y)
        res.append((max(0, g[0]["s"] - a), g[-1]["e"] - a, t.strip(" ,")))
    for i in range(len(res) - 1):          # nối liền, không nháy trống giữa 2 câu gần nhau
        if res[i + 1][0] - res[i][1] < 0.6:
            res[i] = (res[i][0], res[i + 1][0], res[i][2])
    return res


def build(kind):
    cfg = {"win": dict(os="windows", a=0.0, b=142.64, title="trên Windows", sub="Windows 10 / 11 · 64-bit"),
           "m": dict(os="mac", a=143.08, b=286.58, title="trên Mac chip M", sub="Apple M1 · M2 · M3 · M4"),
           "intel": dict(os="mac", a=286.78, b=430.37, title="trên Mac chip Intel", sub="Mac Intel"),
           "mac": dict(os="mac", a=0.0, b=151.45, title="trên Mac", sub="Chip Apple M hoặc Intel")}[kind]
    os_, a, b = cfg["os"], cfg["a"], cfg["b"]
    T = round(b - a + 1.6, 2)
    W_ = os_ == "windows"
    tl = TL()
    body, css = [], [CSS, RP_CSS, GP_CSS]
    R = lambda s: s - a                      # giây trong file giọng → giây trong video

    # nền màn hình
    if W_:
        body.append('<div class="abs" style="inset:0;background:radial-gradient(900px 600px at 70% 40%,#3d7bf0 0%,#1b4fb8 45%,#0b2a6b 100%)"></div>')
        body.append('<div class="abs" style="left:0;right:0;bottom:0;height:48px;background:rgba(28,28,30,.92);display:flex;align-items:center;justify-content:center;gap:26px;z-index:600">'
                    '<div style="display:grid;grid-template-columns:11px 11px;gap:2px"><i style="width:11px;height:11px;background:#4cc2ff"></i><i style="width:11px;height:11px;background:#4cc2ff"></i><i style="width:11px;height:11px;background:#4cc2ff"></i><i style="width:11px;height:11px;background:#4cc2ff"></i></div>'
                    '<div style="width:200px;height:30px;border-radius:999px;background:#2d2d30;color:#999;font-size:14px;display:flex;align-items:center;padding-left:14px">🔍 Tìm kiếm</div>'
                    '<span style="font-size:24px">📁</span><span style="font-size:24px">🌐</span><span id="tb_app" class="hid" style="width:28px;height:28px;border-radius:7px;background:#3b82f6;color:#fff;font:800 17px Montserrat;display:flex;align-items:center;justify-content:center">C</span>'
                    '<span style="position:absolute;right:18px;color:#fff;font-size:14px">10:30</span></div>')
    else:
        body.append('<div class="abs" style="inset:0;background:linear-gradient(160deg,#5b3fa8 0%,#c4507a 45%,#f2a65a 100%)"></div>')
        body.append(f'<div class="abs" style="left:0;right:0;top:0;height:30px;background:rgba(255,255,255,.72);backdrop-filter:blur(10px);display:flex;align-items:center;gap:22px;padding:0 18px;font-size:15px;color:#111;z-index:600">'
                    f'<span id="apple">{APPLE}</span><b>Finder</b><span>Tệp</span><span>Sửa</span><span>Xem</span><span>Đi</span><span>Cửa sổ</span><span>Trợ giúp</span><span style="margin-left:auto">Th 3 10:30</span></div>')
        body.append('<div class="abs" style="left:50%;bottom:10px;transform:translateX(-50%);height:76px;padding:8px 14px;border-radius:22px;background:rgba(255,255,255,.35);display:flex;gap:14px;z-index:600">'
                    + "".join(f'<span{" id=dock_set" if e == "⚙️" else ""} style="width:58px;height:58px;border-radius:14px;background:{c};display:flex;align-items:center;justify-content:center;font-size:30px">{e}</span>'
                              for c, e in [("#fff", "😀"), ("#e8f0ff", "🧭"), ("#fff", "📁"), ("#ddd", "⚙️"), ("#222", "⌨️")])
                    + '<span id="dock_app" class="hid" style="width:58px;height:58px;border-radius:14px;background:#3b82f6;color:#fff;font:800 32px Montserrat;display:flex;align-items:center;justify-content:center">C</span></div>')

    # trình duyệt trang tải
    bx, by, bw, bh = 150, 60 if W_ else 70, 1620, 900
    default = "win" if W_ else "mac"               # trang tự chọn tab theo máy người xem
    body.append(browser("br", bx, by, bw, bh, "ccut-license.dvchinh155.workers.dev/huong-dan", guide_page(default), mac=not W_))
    for _, _, _, _, f in GUIDE_TABS:              # ảnh đại diện video trên trang = giao diện app (không logo hệ điều hành)
        shutil.copy2(HERE / "shots" / f"{'windows' if f == 'windows' else 'mac'}_s5.png", PROJ[kind] / "assets" / f"poster_{f}.jpg")
    scroll = 430
    pick = 2 if W_ else (1 if kind == "intel" else 0)
    fname = FILES[pick][0]
    ay = by + 86 + asset_y(pick, scroll)
    # cửa sổ app C-Cut
    shots = (["s0", "s1", "s2", "s3", "s4", "s5", "main", "queue"] if W_ else ["s0", "s1", "s3", "s4", "s5", "main", "queue"])
    for k in shots:
        shutil.copy2(HERE / "shots" / f"{os_}_{k}.png", PROJ[kind] / "assets" / f"{os_}_{k}.png")
    awx, awy = 160, 50 if W_ else 66
    html, (ox, oy) = app_window(os_, shots, awx, awy)
    body.append(html)
    P = lambda st, k: (ox + BOX[f"{os_}_{st}"][k][0] + BOX[f"{os_}_{st}"][k][2] / 2, oy + BOX[f"{os_}_{st}"][k][1] + BOX[f"{os_}_{st}"][k][3] / 2)
    Bx = lambda st, k: [ox + BOX[f"{os_}_{st}"][k][0], oy + BOX[f"{os_}_{st}"][k][1], BOX[f"{os_}_{st}"][k][2], BOX[f"{os_}_{st}"][k][3]]

    def app_state(t, k, prev=None):
        if prev:
            tl.hide(t, f"#app_{prev}", 0.25)
        tl.show(t, f"#app_{k}", 0.25)

    body += [f'<div id="ring{i}" class="ring"></div>' for i in range(4)]

    # ===== Mở đầu + yêu cầu (thẻ toàn khung, ngoài màn hình) =====
    cards = []
    cards.append(f'<div id="intro" class="card"><div class="logo">C</div><div class="ttl">Hướng dẫn cài đặt C-Cut</div><div class="st">{cfg["title"][0].upper() + cfg["title"][1:]} · {cfg["sub"]}</div></div>')
    req = ([("💻", "Windows 10 / 11", "bản 64-bit")] if W_ else []) + [("💾", "Trống ≥ 10 GB", "ổ đĩa"), ("🧠", "RAM ≥ 8 GB", "khuyên dùng"),
                                                                    ("🔑", "Tài khoản Claude", "gói Pro hoặc Max")]
    cards.append('<div id="req" class="card"><div class="ttl" style="font-size:54px;margin:0">Cần chuẩn bị</div><div class="req">'
                 + "".join(f'<div id="ri{i}" class="ri"><div class="ic">{e}</div><b>{escape(t1)}</b><span>{escape(t2)}</span></div>' for i, (e, t1, t2) in enumerate(req))
                 + '</div></div>')
    cards.append('<div id="outro" class="card" style="background:radial-gradient(1200px 700px at 50% 30%,#1d2b55 0%,#0b0f1a 70%)"><div class="logo">C</div><div class="ttl" style="font-size:58px">Chúc bạn dựng thật nhiều video đẹp!</div>'
                 '<div class="st">💬 Cần hỗ trợ? Nhắn tin fanpage C-Cut</div></div>')

    # ================= kịch bản hình theo giọng =================
    S = json.loads((HERE / WORDS.get(kind, "words.json")).read_text())

    def at(phrase, after=0.0):
        """giây (trong video) lúc bắt đầu cụm từ `phrase` (so khớp chữ thường) sau mốc `after` (giây video)"""
        ws = [w for w in S if a - 0.05 <= w["s"] < b]
        toks = [w["t"].lower().strip(".,!?") for w in ws]
        ph = phrase.lower().split()
        for i in range(len(toks) - len(ph) + 1):
            if R(ws[i]["s"]) >= after - 0.02 and all(toks[i + j].startswith(ph[j]) for j in range(len(ph))):
                return round(R(ws[i]["s"]), 2)
        raise KeyError(f"{kind}: không thấy “{phrase}” sau {after}")

    t_req = at("trước khi bắt đầu") if W_ else at("máy cần ổ")
    tl.show(0.05, "#intro", 0.6, {"scale": 0.94})
    if W_:
        tl.hide(t_req - 0.4, "#intro", 0.4)
        tl.show(t_req, "#req", 0.4)
        for i, ph in enumerate(["windows 10", "ổ đĩa", "nên có ram", "ngoài ra"]):
            tl.show(at(ph, t_req), f"#ri{i}", 0.4, {"y": 30})
        t_dl = at("các bạn mở link")
        tl.hide(t_dl - 0.4, "#req", 0.4)
    else:
        t_chip = at("để biết") if kind == "mac" else at("nếu chưa biết")
        tl.hide(t_chip - 0.4, "#intro", 0.4)
        # menu táo → Giới thiệu về máy Mac này
        body.append('<div id="amenu" class="abs hid" style="left:10px;top:32px;width:300px;background:rgba(246,246,246,.97);border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.35);padding:6px;font-size:15px;z-index:700">'
                    '<div id="am1" style="padding:7px 12px;border-radius:6px">Giới thiệu về máy Mac này</div><hr style="border:0;border-top:1px solid #ddd;margin:5px 8px">'
                    + "".join(f'<div style="padding:7px 12px">{x}</div>' for x in ["Cài đặt hệ thống…", "App Store…", "Mục gần đây", "Buộc thoát…", "Ngủ", "Khởi động lại…", "Tắt máy…"]) + '</div>')
        for sfx, ck in ([("", "m"), ("2", "intel")] if kind == "mac" else [("", kind)]):      # macOS: chip M rồi chip Intel cùng một chỗ
            chip = ("Chip", "Apple M2") if ck == "m" else ("Bộ xử lý", "2,3 GHz Intel Core i5 4 nhân")
            model = "MacBook Air" if ck == "m" else "MacBook Pro"
            body.append(f'<div id="about{sfx}" class="win" style="left:760px;top:220px;width:400px;height:520px;background:#ececec;text-align:center;font-size:15px;color:#222">'
                        f'<div class="wt" style="background:#ececec;border:0"><div class="tl3"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div></div>'
                        f'<div style="margin:24px auto 0;width:200px;height:126px;border-radius:10px;background:linear-gradient(160deg,#5b3fa8,#f2a65a);border:8px solid #222"></div>'
                        f'<div style="font:700 30px -apple-system,sans-serif;margin-top:22px">{model}</div><div style="color:#777;margin-top:4px">13 inch</div>'
                        f'<div style="margin-top:24px;line-height:2.1;display:inline-block;text-align:left"><div id="chiprow{sfx}" style="padding:0 10px;border-radius:6px{";background:#ffe08a" if sfx else ""}"><b>{chip[0]}</b>&nbsp;&nbsp;{chip[1]}</div>'
                        f'<div style="padding:0 10px"><b>Bộ nhớ</b>&nbsp;&nbsp;8 GB</div><div style="padding:0 10px"><b>macOS</b>&nbsp;&nbsp;Sequoia 15</div></div></div>')
        t_menu = at("các bạn bấm vào biểu")
        tl.move(t_chip, 700, 500, 0.1)
        tl.click(t_menu + 1.6, tl.p("#apple"))
        tl.show(t_menu + 1.65, "#amenu", 0.15)
        t_ab = at("chọn giới thiệu")
        tl.set(t_ab + 0.5, "#am1", {"backgroundColor": "#2f7bf6", "color": "#fff"})
        tl.click(t_ab + 0.9, tl.p("#am1"))
        tl.hide(t_ab + 1.0, "#amenu", 0.1)
        tl.show(t_ab + 1.05, "#about", 0.35, {"scale": 0.96})
        t_see = at("nếu thấy dòng")
        tl.zoom(t_see, tl.p("#chiprow"), s=1.7)
        tl.set(t_see + 0.6, "#chiprow", {"backgroundColor": "#ffe08a"})
        if kind == "mac":
            t_int = at("còn nếu thấy", t_see)
            tl.hide(t_int + 0.9, "#about", 0.2); tl.show(t_int + 0.9, "#about2", 0.2)
            tl.unzoom(t_req - 0.6)
            tl.hide(t_req - 0.4, "#about2", 0.3)
        else:
            tl.unzoom(at("các bạn làm theo", t_see) + 1.2)
        tl.hide(t_req - 0.4, "#about", 0.3)
        tl.show(t_req, "#req", 0.4)
        for i, ph in enumerate(["máy cần ổ", "nên có ram", "và các bạn cần"]):
            tl.show(at(ph, t_req), f"#ri{i}", 0.4, {"y": 30})
        t_dl = at("các bạn mở trang") if kind == "mac" else at("các bạn mở link")
        tl.hide(t_dl - 0.4, "#req", 0.4)

    # ===== trang tải về =====
    tl.move(0, 960, 600, 0.01)
    tl.show(t_dl, "#br", 0.45, {"scale": 0.97})
    t_scroll = at("kéo xuống", t_dl)
    tab = "win" if W_ else "mac"
    tl.click(at("chọn tab", t_dl) + 0.6 if kind == "mac" else t_scroll - 0.2 if t_scroll - t_dl > 1.4 else t_dl + 1.2, tl.p(f"#gt_{tab}"))       # chọn đúng tab máy mình
    if tab != default:
        t_tab = (t_scroll - 0.2 if t_scroll - t_dl > 1.4 else t_dl + 1.2)
        tl.hide(t_tab + 0.05, f"#gton_{default}", 0.15); tl.show(t_tab + 0.05, f"#gton_{tab}", 0.15)
        tl.hide(t_tab + 0.05, f"#gp_{default}", 0.15); tl.show(t_tab + 0.05, f"#gp_{tab}", 0.2)
    tl.to(t_scroll + 0.6, "#br_sc", {"y": -scroll}, 1.2)
    if kind == "mac":                    # 2 nút: chip M rồi chip Intel, bấm thử nút chip M
        t_file = at("máy chip m", t_dl)
        t_i = at("máy chip intel", t_file)
        bm, bi = tl.p("#gb_m", -scroll), tl.p("#gb_intel", -scroll)
        tl.zoom(t_file, bm, s=1.4)
        tl.ring(t_file + 0.3, 0, tl.b("#gb_m", -scroll), 2.6)
        tl.move(t_file + 0.4, bm, d=0.6)
        tl.ring(t_i + 0.3, 1, tl.b("#gb_intel", -scroll), 2.0)
        tl.move(t_i + 0.4, bi, d=0.6)
        t_clk = t_i + 1.6
        tl.click(t_clk, bm)
        tl.unzoom(t_clk + 0.2)
    else:
        t_file = at("rồi bấm vào file", t_dl)
        bid = "win" if W_ else ("intel" if kind == "intel" else "m")
        btn = tl.p(f"#gb_{bid}", -scroll)
        tl.zoom(t_file, btn, s=1.6)
        tl.ring(t_file + 0.6, 0, tl.b(f"#gb_{bid}", -scroll), 2.6)
        t_clk = t_file + (2.6 if W_ else 3.4)
        tl.click(t_clk, btn)
        tl.unzoom(t_file + (4.0 if W_ else 5.2))

    # tải xuống (bảng tải của trình duyệt)
    keep = W_
    dl_html = (f'<div id="dlp" class="win" style="left:{bx + bw - 470}px;top:{by + 92}px;width:440px;height:{190 if keep else 120}px;padding:18px;font-size:16px;color:#222">'
               f'<b>Tải xuống</b><div style="display:flex;gap:12px;align-items:center;margin-top:14px"><span style="font-size:30px">{"🧩" if W_ else "💿"}</span>'
               f'<div style="flex:1"><div style="font-weight:600">{fname}</div>'
               + (f'<div id="dlwarn" style="color:#b3261e;font-size:14px;margin-top:4px">Tệp này thường không được tải xuống. Hãy chắc chắn bạn tin tưởng tệp trước khi mở.</div>' if keep else "")
               + f'<div style="height:6px;background:#e3e3e3;border-radius:3px;margin-top:8px"><div id="dlbar" style="height:6px;width:100%;background:#0b57d0;border-radius:3px;transform-origin:0 0;transform:scaleX(0)"></div></div></div></div>'
               + (f'<div id="dlkeep" class="btn bp" style="position:absolute;right:120px;bottom:16px;height:34px">Giữ lại</div><div class="btn bg" style="position:absolute;right:18px;bottom:16px;height:34px">Xoá</div>' if keep else "")
               + f'<div id="dlopen" class="hid" style="position:absolute;right:18px;bottom:{16 if keep else 14}px;color:#0b57d0;font-weight:700">Mở tệp</div></div>')
    body.append(dl_html)
    t_open = at("tải xong", t_file)
    if W_:
        t_keep = at("nếu trình duyệt")
        tl.show(t_keep + 0.2, "#dlp", 0.3, {"y": -10})
        tl.zoom(t_keep + 0.5, tl.p("#dlp"), s=1.6)
        tl.click(at("chọn giữ", t_keep) + 0.4, tl.p("#dlkeep"))
        tl.hide(at("chọn giữ", t_keep) + 0.5, "#dlkeep", 0.2)
        tl.hide(at("chọn giữ", t_keep) + 0.5, "#dlwarn", 0.2)
        tl.to(at("chọn giữ", t_keep) + 0.6, "#dlbar", {"scaleX": 1}, 1.4, "power1.inOut")
    else:
        tl.show(t_clk + 0.2, "#dlp", 0.3, {"y": -10})
        tl.to(t_clk + 0.4, "#dlbar", {"scaleX": 1}, 1.6 if kind != "mac" else 0.9, "power1.inOut")
        tl.zoom(t_open - 0.2, tl.p("#dlp"), s=1.6)
    tl.show(t_open + 0.4, "#dlopen", 0.2)
    tl.click(t_open + 1.4, tl.p("#dlopen"))
    tl.unzoom(t_open + 1.8)
    tl.hide(t_open + 1.7, "#dlp", 0.2)

    if W_:
        # ===== SmartScreen =====
        body.append(f"""<div id="ss" class="win" style="left:560px;top:250px;width:800px;height:470px;background:#0f63b6;color:#fff;border-radius:6px">
<div style="padding:46px 50px"><div style="font-size:40px;font-weight:300">Windows protected your PC</div>
<div style="font-size:18px;margin-top:24px;line-height:1.6">Microsoft Defender SmartScreen prevented an unrecognized app from starting. Running this app might put your PC at risk.</div>
<div id="ssmore" style="font-size:18px;margin-top:16px;text-decoration:underline">More info</div>
<div id="ssinfo" class="hid" style="font-size:18px;margin-top:-26px;line-height:1.8">App: &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;C-Cut-Setup.exe<br>Publisher: &nbsp;Unknown publisher</div></div>
<div style="position:absolute;left:0;right:0;bottom:0;height:86px;border-top:1px solid rgba(255,255,255,.3);display:flex;justify-content:flex-end;align-items:center;gap:14px;padding:0 30px">
<div id="ssrun" class="btn hid" style="border:2px solid #fff;height:42px;width:150px">Run anyway</div><div class="btn" style="border:2px solid #fff;height:42px;width:150px">Don't run</div></div></div>""")
        t_ss = at("lần đầu chạy")
        tl.hide(t_ss - 0.2, "#br", 0.3)
        tl.show(t_ss + 0.3, "#ss", 0.35, {"scale": 0.97})
        t_more = at("more", t_ss)
        tl.zoom(t_more - 0.3, tl.p("#ssmore"), s=1.5)
        tl.click(t_more + 0.5, tl.p("#ssmore"))
        tl.hide(t_more + 0.55, "#ssmore", 0.1)
        tl.show(t_more + 0.6, "#ssinfo", 0.2)
        tl.show(t_more + 0.6, "#ssrun", 0.2)
        t_run = at("run", t_more + 0.5)
        tl.zoom(t_run - 0.4, tl.p("#ssrun"), s=1.5)
        tl.click(t_run + 0.6, tl.p("#ssrun"))
        tl.unzoom(t_run + 1.2)
        tl.hide(t_run + 0.9, "#ss", 0.25)
        # ===== trình cài đặt =====
        pages = {
            "w1": ("Select Additional Tasks", "Which additional tasks should be performed?",
                   '<div style="margin-top:30px;font-size:17px;display:flex;gap:12px;align-items:center"><span id="ck1" style="width:20px;height:20px;border:2px solid #555;border-radius:3px;display:inline-flex;align-items:center;justify-content:center;font-size:15px"><i id="ck1v" class="hid" style="font-style:normal">✔</i></span>Tạo biểu tượng ngoài màn hình</div>', "Next >"),
            "w2": ("Ready to Install", "Setup is now ready to begin installing C-Cut on your computer.",
                   '<div style="margin-top:26px;font-size:16px;color:#333;line-height:1.7">Destination location:<br>&nbsp;&nbsp;C:\\Users\\Ban\\AppData\\Local\\Programs\\C-Cut<br><br>Additional tasks:<br>&nbsp;&nbsp;Tạo biểu tượng ngoài màn hình</div>', "Install"),
            "w3": ("Installing", "Please wait while Setup installs C-Cut on your computer.",
                   '<div style="margin-top:40px;font-size:15px;color:#333">Extracting files...</div><div style="height:22px;border:1px solid #aaa;margin-top:10px"><div id="wbar" style="height:20px;width:100%;background:#06b025;transform-origin:0 0;transform:scaleX(0)"></div></div>', "Next >"),
            "w4": ("Completing the C-Cut Setup Wizard", "Setup has finished installing C-Cut on your computer.",
                   '<div style="margin-top:30px;font-size:17px;display:flex;gap:12px;align-items:center"><span style="width:20px;height:20px;border:2px solid #0067c0;background:#0067c0;color:#fff;border-radius:3px;display:inline-flex;align-items:center;justify-content:center;font-size:15px">✔</span>Mở C-Cut</div>', "Finish"),
        }
        pg = "".join(f'<div id="{k}" class="abs hid" style="inset:34px 0 0 0;background:#fff"><div style="padding:22px 30px;border-bottom:1px solid #ddd"><b style="font-size:18px">{escape(t1)}</b>'
                     f'<div style="font-size:15px;color:#555;margin-top:6px">{escape(t2)}</div></div><div style="padding:0 40px">{inner}</div>'
                     f'<div style="position:absolute;left:0;right:0;bottom:0;height:64px;border-top:1px solid #ddd;display:flex;justify-content:flex-end;align-items:center;gap:10px;padding:0 20px;background:#f3f3f3">'
                     f'<div class="btn bg" style="width:100px">&lt; Back</div><div id="nb_{k}" class="btn bp" style="width:110px">{nb}</div><div class="btn bg" style="width:100px">Cancel</div></div></div>'
                     for k, (t1, t2, inner, nb) in pages.items())
        body.append(f'<div id="wiz" class="win" style="left:610px;top:230px;width:700px;height:520px"><div class="wt">Setup - C-Cut<div class="wctl"><span>—</span><span>✕</span></div></div>{pg}</div>')
        t_w = at("trình cài đặt")
        tl.show(t_w + 0.2, "#wiz", 0.35, {"scale": 0.97})
        tl.show(t_w + 0.2, "#w1", 0.01)
        tl.zoom(t_w + 1.0, tl.p("#wiz"), s=1.4)
        tl.click(at("tích chọn", t_w) + 0.8, tl.p("#ck1"))
        tl.show(at("tích chọn", t_w) + 0.85, "#ck1v", 0.05)
        t_next = at("bấm next", t_w)
        tl.unzoom(t_next - 0.3)
        tl.click(t_next + 0.5, tl.p("#nb_w1"))
        tl.hide(t_next + 0.55, "#w1", 0.05); tl.show(t_next + 0.55, "#w2", 0.05)
        t_ins = at("install", t_next)
        tl.click(t_ins + 0.3, tl.p("#nb_w2"))
        tl.hide(t_ins + 0.35, "#w2", 0.05); tl.show(t_ins + 0.35, "#w3", 0.05)
        t_fin_v = at("cài xong", t_ins)
        tl.to(t_ins + 0.4, "#wbar", {"scaleX": 1}, max(1.0, t_fin_v - t_ins - 0.8), "power1.inOut")
        tl.hide(t_fin_v, "#w3", 0.05); tl.show(t_fin_v, "#w4", 0.05)
        tl.click(at("finish", t_fin_v) + 0.5, tl.p("#nb_w4"))
        t_app = at("lần đầu mở")
        tl.hide(at("finish", t_fin_v) + 0.6, "#wiz", 0.25)
    else:
        # ===== DMG: kéo vào Applications =====
        body.append(f"""<div id="dmg" class="win" style="left:620px;top:260px;width:680px;height:420px;background:#fff">
<div class="wt" style="justify-content:center;position:relative;background:#f6f6f6"><div class="tl3" style="position:absolute;left:12px"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>C-Cut</div>
<div style="display:flex;justify-content:space-around;align-items:center;height:330px;font-size:16px;color:#222">
<div style="text-align:center"><div id="dmg_app" style="width:128px;height:128px;border-radius:28px;background:linear-gradient(140deg,#4f8cff,#2b5bd8);color:#fff;font:800 76px Montserrat;display:flex;align-items:center;justify-content:center;margin:auto">C</div><div style="margin-top:12px">C-Cut</div></div>
<div style="font-size:60px;color:#bbb">➜</div>
<div style="text-align:center"><div id="dmg_apps" style="width:128px;height:110px;border-radius:14px;background:linear-gradient(#6ab0ff,#2f7bf6);display:flex;align-items:center;justify-content:center;font-size:56px;color:#fff;margin:auto">A</div><div style="margin-top:12px">Applications</div></div></div></div>
<div id="ghost" class="abs hid" style="left:0;top:0;width:110px;height:110px;border-radius:24px;background:linear-gradient(140deg,#4f8cff,#2b5bd8);color:#fff;font:800 64px Montserrat;display:flex;align-items:center;justify-content:center;z-index:880"></div>
<div id="copy" class="win" style="left:720px;top:720px;width:480px;height:120px;padding:20px;font-size:15px;color:#222;background:#f6f6f6">Đang sao chép “C-Cut” vào “Applications”
<div style="height:8px;background:#ddd;border-radius:4px;margin-top:18px"><div id="cbar" style="height:8px;width:100%;background:#2f7bf6;border-radius:4px;transform-origin:0 0;transform:scaleX(0)"></div></div></div>""")
        t_dmg = at("tải xong", t_file)
        tl.hide(t_dmg + 2.0, "#br", 0.3)
        tl.show(t_dmg + 2.1, "#dmg", 0.35, {"scale": 0.97})
        t_drag = at("các bạn chỉ cần kéo", t_dmg)
        A_, B_ = tl.p("#dmg_app"), tl.p("#dmg_apps")
        tl.zoom(t_drag - 0.6, tl.p("#dmg"), s=1.35)
        tl.move(t_drag, A_, d=0.7)
        tl.add(f'tl.set("#ghost",{{x:{A_}.x-55,y:{A_}.y-55,opacity:0.75}},{t_drag + 0.8:.3f});')
        tl.add(f'tl.to("#ghost",{{x:{B_}.x-55,y:{B_}.y-55,duration:1.6,ease:"power2.inOut"}},{t_drag + 0.9:.3f});')
        tl.move(t_drag + 0.9, B_, d=1.6)
        tl.hide(t_drag + 2.6, "#ghost", 0.15)
        t_cp = at("chờ sao chép", t_drag)
        tl.unzoom(t_cp - 0.3)
        tl.show(t_cp, "#copy", 0.25)
        tl.to(t_cp + 0.2, "#cbar", {"scaleX": 1}, 1.2, "power1.inOut")
        tl.hide(t_cp + 1.6, "#copy", 0.2)
        # Mở app trong Ứng dụng → bị chặn
        body.append("""<div id="apps" class="win" style="left:520px;top:200px;width:880px;height:560px;background:#fff">
<div class="wt" style="background:#f6f6f6;justify-content:center;position:relative"><div class="tl3" style="position:absolute;left:12px"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>Ứng dụng</div>
<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:26px;padding:34px;font-size:14px;color:#222;text-align:center">"""
                    + "".join(f'<div><div{" id=apps_cc" if n == "C-Cut" else ""} style="width:84px;height:84px;margin:auto;border-radius:20px;background:{c};display:flex;align-items:center;justify-content:center;font-size:44px">{e}</div><div style="margin-top:8px">{n}</div></div>'
                              for c, e, n in [("#e8f0ff", "🧭", "Safari"), ("#fff3d6", "📝", "Ghi chú"), ("#e9f9ee", "🗺️", "Bản đồ"), ("#eee", "🧮", "Máy tính"),
                                              ("linear-gradient(140deg,#4f8cff,#2b5bd8);color:#fff;font:800 50px Montserrat", "C", "C-Cut"), ("#ffe9ec", "🎵", "Nhạc"),
                                              ("#eef", "📷", "Ảnh"), ("#efe", "💬", "Tin nhắn"), ("#fef", "📅", "Lịch"), ("#ffe", "⚙️", "Cài đặt hệ thống")])
                    + "</div></div>")
        body.append("""<div id="gk" class="win" style="left:770px;top:300px;width:380px;height:400px;background:#f2f2f2;text-align:center;color:#111;border-radius:16px">
<div style="width:74px;height:74px;margin:30px auto 0;border-radius:18px;background:linear-gradient(140deg,#4f8cff,#2b5bd8);color:#fff;font:800 44px Montserrat;display:flex;align-items:center;justify-content:center">C</div>
<div style="font-weight:700;font-size:18px;margin-top:18px">Không mở được “C-Cut”</div>
<div style="font-size:14px;line-height:1.5;margin:10px 26px;color:#333">Apple không thể xác minh “C-Cut” không chứa phần mềm độc hại có thể gây hại cho máy Mac hoặc xâm phạm quyền riêng tư của bạn.</div>
<div id="gkx" class="btn mbp" style="display:flex;margin:18px 26px 0;height:34px">Xong</div><div class="btn mbg" style="display:flex;margin:10px 26px 0;height:34px">Chuyển vào Thùng rác</div></div>""")
        t_apps = at("bây giờ")
        tl.hide(t_apps - 0.3, "#dmg", 0.25)
        tl.show(t_apps, "#apps", 0.3, {"scale": 0.97})
        tl.click(at("trong thư mục", t_apps) + 0.4, tl.p("#apps_cc"))
        tl.click(at("trong thư mục", t_apps) + 0.62)
        t_gk = at("lần đầu mở", t_apps)
        tl.show(t_gk + 0.2, "#gk", 0.3, {"scale": 0.95})
        tl.zoom(t_gk + 0.6, tl.p("#gk"), s=1.45)
        t_x = at("xong để", t_gk)
        tl.click(t_x + 0.3, tl.p("#gkx"))
        tl.hide(t_x + 0.4, "#gk", 0.2)
        tl.unzoom(t_x + 0.5)
        tl.hide(t_x + 0.6, "#apps", 0.25)
        # Cài đặt hệ thống → Quyền riêng tư & Bảo mật → Vẫn mở → mật khẩu → Mở
        side = ["Wi-Fi", "Bluetooth", "Mạng", "Thông báo", "Âm thanh", "Tập trung", "Thời gian sử dụng", "Cài đặt chung", "Giao diện",
                "Trợ năng", "Trung tâm điều khiển", "Siri", "Quyền riêng tư & Bảo mật", "Màn hình nền & Dock", "Màn hình"]
        body.append(f"""<div id="sset" class="win" style="left:430px;top:150px;width:1060px;height:720px;background:#f5f5f5;color:#111">
<div style="position:absolute;left:0;top:0;bottom:0;width:280px;background:#e9e7ea;padding:44px 12px 0;font-size:15px">
<div class="tl3" style="position:absolute;left:14px;top:12px"><i style="background:#ff5f57"></i><i style="background:#febc2e"></i><i style="background:#28c840"></i></div>
<div style="background:#dcdadd;border-radius:8px;padding:7px 10px;color:#777;margin-bottom:12px">🔍 Tìm kiếm</div>"""
                    + "".join(f'<div id="sd{i}" style="padding:7px 10px;border-radius:7px">{"🔒 " if "Bảo mật" in n else "◽ "}{n}</div>' for i, n in enumerate(side))
                    + """</div><div style="position:absolute;left:280px;right:0;top:0;bottom:0;overflow:hidden">
<div style="height:52px;display:flex;align-items:center;padding:0 24px;font-weight:700;font-size:17px;background:#f5f5f5;position:relative;z-index:2">Quyền riêng tư & Bảo mật</div>
<div id="ssc" style="padding:6px 24px">"""
                    + "".join(f'<div style="background:#fff;border-radius:10px;padding:14px 16px;margin-bottom:10px;font-size:15px;display:flex">{n}<span style="margin-left:auto;color:#999">›</span></div>'
                              for n in ["📍 Dịch vụ định vị", "👥 Danh bạ", "📅 Lịch", "✅ Lời nhắc", "🖼️ Ảnh", "🎙️ Micrô", "📷 Camera", "🖥️ Ghi màn hình & âm thanh", "♿ Trợ năng", "💽 Toàn quyền truy cập ổ đĩa"])
                    + """<div style="font-weight:700;font-size:16px;margin:22px 4px 10px">Bảo mật</div>
<div id="secrow" style="background:#fff;border-radius:10px;padding:16px;font-size:15px;line-height:1.5;display:flex;align-items:center;gap:16px">
<div style="flex:1">“C-Cut” đã bị chặn để bảo vệ máy Mac của bạn.</div><div id="openany" class="btn mbg" style="height:32px;padding:0 16px">Vẫn mở</div></div></div></div></div>""")
        body.append("""<div id="pw" class="win" style="left:780px;top:330px;width:360px;height:330px;background:#f2f2f2;border-radius:16px;text-align:center;color:#111;padding:26px">
<div style="font-size:40px">🔒</div><div style="font-weight:700;margin-top:8px">Quyền riêng tư & Bảo mật</div>
<div style="font-size:13px;color:#444;margin:8px 0 14px">Bạn đang cố sửa đổi cài đặt hệ thống. Nhập mật khẩu để cho phép điều này.</div>
<div style="background:#fff;border-radius:7px;padding:8px 10px;text-align:left;font-size:14px;margin-bottom:8px">Bạn</div>
<div style="background:#fff;border-radius:7px;padding:8px 10px;text-align:left;font-size:14px;height:34px">""" + chars("pwd", "●●●●●●●●") + """</div>
<div id="pwok" class="btn mbp" style="display:flex;margin-top:14px;height:32px">Sửa đổi cài đặt</div></div>
<div id="opn" class="win" style="left:790px;top:340px;width:340px;height:300px;background:#f2f2f2;border-radius:16px;text-align:center;color:#111;padding:24px">
<div style="width:64px;height:64px;margin:0 auto;border-radius:16px;background:linear-gradient(140deg,#4f8cff,#2b5bd8);color:#fff;font:800 38px Montserrat;display:flex;align-items:center;justify-content:center">C</div>
<div style="font-weight:700;margin-top:14px">Mở “C-Cut”?</div><div style="font-size:13px;color:#444;margin:8px 0 18px">Bạn chỉ nên mở ứng dụng từ nguồn bạn tin tưởng.</div>
<div id="opnok" class="btn mbp" style="display:flex;height:32px">Mở</div><div class="btn mbg" style="display:flex;margin-top:8px;height:32px">Huỷ</div></div>""")
        t_set = at("tiếp theo")
        tl.click(t_set + 0.2, tl.p("#dock_set"))
        tl.show(t_set + 0.4, "#sset", 0.35, {"scale": 0.97})
        si = side.index("Quyền riêng tư & Bảo mật")
        t_pr = at("chọn mục", t_set)
        tl.click(t_pr + 0.5, tl.p(f"#sd{si}"))
        tl.set(t_pr + 0.55, f"#sd{si}", {"backgroundColor": "#2f7bf6", "color": "#fff"})
        t_down = at("kéo xuống dưới", t_pr)
        tl.to(t_down, "#ssc", {"y": -260}, 1.0)
        tl.zoom(t_down + 0.8, tl.p("#secrow", -260), s=1.45)
        tl.ring(t_down + 1.2, 1, tl.b("#secrow", -260), 2.4)
        t_any = at("vẫn mở", t_down)
        tl.click(t_any + 0.4, tl.p("#openany", -260))
        tl.unzoom(t_any + 0.8)
        tl.show(t_any + 0.7, "#pw", 0.25, {"scale": 0.95})
        tl.typing(at("nhập mật khẩu", t_any) + 0.3, "pwd", 8, 10)
        tl.click(at("nhập mật khẩu", t_any) + 1.3, tl.p("#pwok"))
        tl.hide(at("nhập mật khẩu", t_any) + 1.4, "#pw", 0.15)
        tl.show(at("nhập mật khẩu", t_any) + 1.45, "#opn", 0.2, {"scale": 0.95})
        t_mo = at("rồi bấm mở", t_any)
        tl.click(t_mo + 0.9, tl.p("#opnok"))
        tl.hide(t_mo + 1.0, "#opn", 0.2)
        tl.hide(t_mo + 1.1, "#sset", 0.25)
        t_app = at("mở lên và")

    # ===== app C-Cut: thiết lập lần đầu =====
    tl.show(t_app - 0.3, "#appw", 0.4, {"scale": 0.97})
    tl.show(t_app - 0.3, "#app_s0", 0.01)
    tl.show(t_app - 0.3, "#tb_app" if W_ else "#dock_app", 0.2)
    tl.zoom(t_app + 1.4, P("s0", "steps"), s=1.25)
    steps = [("Cài Claude", "claude_install"), ("Cài Git for Windows", "git_install"), ("Đăng nhập Claude", "claude_login"),
             ("Tải model chép lời", "dl")] if W_ else [("Cài Claude", "claude_install"), ("Đăng nhập Claude", "claude_login"), ("Tải model chép lời", "dl")]
    n = len(steps)
    chips = "".join(f'<div id="chip{i}" class="chipt hid">Bước {i + 1}/{n} · {t}</div>' for i, (t, _) in enumerate(steps))
    # console cài Claude / Git
    if W_:
        body.append(console("ps1", 460, 300, 1000, 380, "Windows PowerShell", [
            ("PS C:\\Users\\Ban> ", "irm https://claude.ai/install.ps1 | iex", "#fff"), (None, "Installing Claude...", "#9cdcfe"),
            (None, "Downloading ████████████████████ 100%", "#9cdcfe"), (None, "✔ Claude installed successfully.", "#6ee77a")], "#0c0c0c"))
        body.append(console("ps2", 460, 300, 1000, 420, "Windows PowerShell", [
            ("PS C:\\Users\\Ban> ", "winget install --id Git.Git -e --source winget", "#fff"), (None, "Found Git [Git.Git]", "#ddd"),
            (None, "Do you agree to all the source agreements terms? [Y] Yes  [N] No: Y", "#ffd866"),
            (None, "Downloading ████████████████████ 100%", "#9cdcfe"), (None, "Successfully installed", "#6ee77a")], "#0c0c0c"))
    else:
        body.append(console("ps1", 460, 300, 1000, 380, "Terminal — zsh", [
            ("ban@MacBook ~ % ", "curl -fsSL https://claude.ai/install.sh | bash", "#111"), (None, "Installing Claude...", "#2b5bd8"),
            (None, "Downloading ████████████████████ 100%", "#2b5bd8"), (None, "✔ Claude installed successfully.", "#1a7f37")], "#fff", mac=True))
        css.append("#ps1 div[style*='Menlo']{color:#111!important}")
    body.append(login_page("lg", 310, 120, not W_))

    prev = "s0"
    for i, (name, key) in enumerate(steps):
        t_s = at(f"bước {['một', '1', 'hai', '2', 'ba', '3', 'bốn', '4'][i * 2 + 1]}") if True else 0
        tl.show(t_s, f"#chip{i}", 0.25, {"y": 10})
        if i:
            tl.hide(t_s, f"#chip{i - 1}", 0.15)
        if key in ("claude_install", "git_install"):
            cid = "ps1" if key == "claude_install" else "ps2"
            t_c = at("mở cửa sổ", t_s)
            tl.click(t_c + 0.6, P(prev, key))
            tl.unzoom(t_c + 0.8)
            tl.show(t_c + 1.0, f"#{cid}", 0.3, {"scale": 0.97})
            ln = 4 if cid == "ps1" else 5
            cmdlen = len("irm https://claude.ai/install.ps1 | iex" if cid == "ps1" and W_ else "curl -fsSL https://claude.ai/install.sh | bash" if cid == "ps1" else "winget install --id Git.Git -e --source winget")
            tl.typing(t_c + 1.3, f"{cid}c0_", cmdlen, 40)
            t_end = at("báo xong", t_c) if cid == "ps1" else at("chờ chạy xong", t_c)
            span = t_end - (t_c + 2.4)
            for k in range(1, ln):
                tl.show(t_c + 2.4 + span * k / (ln - 1), f"#{cid}_l{k}", 0.1)
            tl.hide(t_end + 1.0, f"#{cid}", 0.25)
            nxt = "s1" if key == "claude_install" else "s2"
            app_state(t_end + 1.1, nxt, prev); prev = nxt
            nz = steps[i + 1][1] if i + 1 < n else "dl"
            tl.zoom(t_end + 1.3, P(prev, nz), s=1.25)
        elif key == "claude_login":
            t_c = at("bấm đăng nhập", t_s)
            tl.click(t_c + 0.5, P(prev, key))
            tl.unzoom(t_c + 0.7)
            tl.show(t_c + 1.0, "#lg", 0.35, {"scale": 0.97})
            t_acc = at("đăng nhập tài khoản", t_c)
            tl.typing(t_acc + 0.2, "lge", 13, 14)
            tl.click(t_acc + 1.4, tl.p("#lg_go"))
            tl.hide(t_acc + 1.5, "#lg_p1", 0.15)
            tl.show(t_acc + 1.6, "#lg_p2", 0.2)
            t_ok = at("cho phép", t_acc)
            tl.click(t_ok + 0.5, tl.p("#lg_ok"))
            tl.hide(t_ok + 1.2, "#lg", 0.25)
            app_state(t_ok + 1.3, "s3", prev); prev = "s3"
            tl.zoom(t_ok + 1.5, P("s3", "dl"), s=1.25)
        else:
            t_c = at("bấm tải ngay", t_s)
            tl.click(t_c + 0.5, P(prev, "dl"))
            app_state(t_c + 0.6, "s4", prev); prev = "s4"
            t_hf = at("riêng công cụ")
            app_state(t_hf - 0.4, "s5", prev); prev = "s5"
            hfb = Bx("s5", "steps")
            tl.ring(t_hf + 0.3, 2, [hfb[0], hfb[1] + hfb[3] - 66, hfb[2], 66], 3.0)
    t_chk = at("làm xong")
    tl.hide(t_chk, f"#chip{n - 1}", 0.2)
    tl.zoom(t_chk, P("s5", "recheck"), s=1.35)
    tl.click(t_chk + 1.6, P("s5", "recheck"))
    t_go = at("khi tất cả", t_chk)
    tl.ring(t_go + 0.3, 3, Bx("s5", "steps"), 2.4)
    tl.click(at("bắt đầu dùng", t_go) + 0.6, P("s5", "done"))
    app_state(at("bắt đầu dùng", t_go) + 0.8, "main", "s5")
    tl.unzoom(at("bắt đầu dùng", t_go) + 0.9)
    # màn hình chính: kéo video vào → chọn style → bắt đầu dựng
    body.append('<div id="vfile" class="abs hid" style="left:0;top:0;padding:10px 14px;border-radius:10px;background:#fff;color:#222;font-size:15px;box-shadow:0 8px 24px rgba(0,0,0,.3);z-index:880">🎬 Gioi-thieu-du-an.mp4</div>')
    t_main = at("ở màn hình chính")
    t_drag = at("kéo thả", t_main)
    dx, dy = P("main", "drop")
    tl.set(t_drag, "#vfile", {"x": 1500, "y": 760, "opacity": 1})
    tl.move(t_drag, 1520, 780, 0.3)
    tl.to(t_drag + 0.35, "#vfile", {"x": dx - 90, "y": dy - 20}, 1.3)
    tl.move(t_drag + 0.35, dx - 70, dy, 1.3)
    tl.hide(t_drag + 1.7, "#vfile", 0.15)
    app_state(t_drag + 1.75, "queue", "main")
    tl.zoom(t_drag + 1.8, 400, 500, s=1.6)
    t_sty = max(at("chọn phong cách", t_drag) + 0.2, t_drag + 2.0)     # sau khi màn hình đã có video trong hàng chờ
    tl.ring(t_sty, 0, Bx("queue", "style"), 1.8)
    tl.move(t_sty, P("queue", "style"), d=0.6)
    t_go2 = max(at("rồi bấm bắt đầu dựng", t_drag), t_sty + 1.0)
    tl.click(t_go2 + 1.4, P("queue", "start"))
    tl.ring(t_go2 + 1.2, 1, Bx("queue", "start"), 1.8)
    tl.unzoom(at("tự cắt gọn", t_go2) - 0.6 if True else 0)
    t_out = at("chúc các bạn")
    tl.show(t_out, "#outro", 0.6, {"scale": 0.96})

    # phụ đề
    sub_html = []
    for i, (s0, s1, text) in enumerate(subs(a, b, WORDS.get(kind, "words.json"))):
        sub_html.append(f'<div id="sb{i}" class="sub hid">{escape(text)}</div>')
        tl.set(s0, f"#sb{i}", {"opacity": 1})
        tl.set(s1, f"#sb{i}", {"opacity": 0})
    cur = CURSOR_WIN if W_ else CURSOR_MAC
    doc = f"""<!doctype html><html lang="vi"><head><meta charset="UTF-8"><meta name="viewport" content="width={W}, height={H}">
<script src="assets/gsap.min.js"></script><style>
@font-face{{font-family:'Montserrat';src:url('assets/fonts/Montserrat-VF.ttf');font-weight:100 900}}
@font-face{{font-family:'Be Vietnam Pro';src:url('assets/fonts/BeVietnamPro-Regular.ttf');font-weight:400}}
@font-face{{font-family:'Be Vietnam Pro';src:url('assets/fonts/BeVietnamPro-SemiBold.ttf');font-weight:600}}
@font-face{{font-family:'Be Vietnam Pro';src:url('assets/fonts/BeVietnamPro-Bold.ttf');font-weight:700 900}}
{''.join(css)}</style></head><body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{T}" data-width="{W}" data-height="{H}" data-fps="30">
<div id="all" class="clip" data-start="0" data-duration="{T}" data-track-index="1" style="position:absolute;inset:0">
<div id="screen"><div id="cam">{''.join(body)}<div id="rip"></div><div id="cur">{cur}</div></div></div>
{''.join(cards)}
<div id="chip">{chips}</div>
<div id="band">{''.join(sub_html)}</div>
</div></div>
<script>
const SCALE={SC},OX={SX},OY={SY};
function pt(s,dy,ax,ay){{const r=document.querySelector(s).getBoundingClientRect();return {{x:(r.left-OX)/SCALE+r.width/SCALE*ax,y:(r.top-OY)/SCALE+r.height/SCALE*ay+dy}}}}
function bx(s,dy){{const r=document.querySelector(s).getBoundingClientRect();return {{x:(r.left-OX)/SCALE,y:(r.top-OY)/SCALE+dy,w:r.width/SCALE,h:r.height/SCALE}}}}
function zm(cx,cy,s){{return {{x:Math.round(Math.min(0,Math.max({W}-{W}*s,{W}/2-cx*s))),y:Math.round(Math.min(0,Math.max({H}-{H}*s,{H}/2-cy*s))),scale:s}}}}
const Q=[{','.join(tl.q)}];
const tl = gsap.timeline({{paused:true}});
{chr(10).join(tl.js)}
tl.set({{}},{{}},{T});
window.__timelines = window.__timelines || {{}};
window.__timelines["main"] = tl;
tl.seek(0);
</script></body></html>"""
    (PROJ[kind] / "index.html").write_text(doc, encoding="utf-8")
    return T


PROJ = {k: HERE / "proj" / k for k in ("win", "m", "intel", "mac")}


def prep(kind):
    p = PROJ[kind]
    (p / "assets" / "fonts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(runtime.gsap_js(), p / "assets" / "gsap.min.js")
    for f in ["Montserrat-VF.ttf", "BeVietnamPro-Regular.ttf", "BeVietnamPro-SemiBold.ttf", "BeVietnamPro-Bold.ttf"]:
        src = ROOT / "assets" / "fonts" / f
        if src.exists():
            shutil.copy2(src, p / "assets" / "fonts" / f)


def render(kind, T):
    p = PROJ[kind]
    silent = HERE / f"{kind}_silent.mp4"
    r = subprocess.run([*runtime.cli_cmd(), "render", "--format", "mp4", "--fps", "30", "--quality", "looks", "--output", str(silent), "."],
                       cwd=p, env=runtime.env(), capture_output=True, text=True, timeout=7200)
    if r.returncode:
        raise SystemExit(r.stdout[-2000:] + r.stderr[-2000:])
    cfg = {"win": (0.0, 142.64), "m": (143.08, 286.58), "intel": (286.78, 430.37), "mac": (0.0, 151.56)}[kind]
    out = HERE / {"win": "C-Cut_HuongDan_Windows.mp4", "m": "C-Cut_HuongDan_Mac_chipM.mp4", "intel": "C-Cut_HuongDan_Mac_Intel.mp4",
                  "mac": "C-Cut_HuongDan_macOS.mp4"}[kind]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(silent), "-ss", str(cfg[0]), "-to", str(cfg[1]), "-i", str(VOICES.get(kind, VOICE)),
                    "-filter_complex", "[1:a]apad,loudnorm=I=-16:TP=-1.5:LRA=11[a]", "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    return out


if __name__ == "__main__":
    kinds = [k for k in sys.argv[1:] if not k.startswith("-")] or ["win", "m", "intel"]
    for k in kinds:
        prep(k)
        T = build(k)
        print(k, "T =", T, flush=True)
        if "--render" in sys.argv:
            print("→", render(k, T), flush=True)
