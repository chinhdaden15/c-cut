"""Review Editor — lớp đồ họa đè lên footage (dựng bằng renderer của Voice to Motion, xuất RGBA).

Ba vai trò chữ tách riêng + hai lớp hướng chú ý:
- phụ đề (caption): cụm NGHĨA tiếng Việt (dấu câu, chỗ ngừng, trước liên từ, độ dài đọc được), không tách thuật ngữ (“motion graphic”),
  sửa dấu câu/viết hoa giữa câu của máy chép lời; cả cụm hiện, từ đang đọc đổi màu; đủ thời gian đọc.
- chữ nhấn (emph): vài ý chính, hai tầng; tự chọn vị trí KHÔNG chạm mặt/tóc.
- nhãn sản phẩm (label): sát vật, chấm neo + đường dẫn, đi theo vật (track).
- spotlight: tối vùng ngoài sản phẩm (lớp đen 25–40%), ô bo góc mềm ôm vật có đệm, giữ nguyên màu sản phẩm, theo đúng vị trí/kích thước vật
  từng khung, fade vào/ra ~0,24s; mất dấu → tắt (không chiếu nhầm mặt/tay/nền). Nhãn/chữ nằm TRÊN lớp tối.
- diagram: sơ đồ minh họa ý (vd Video nguồn → Nhận diện → Chèn minh họa) phủ hình trong lúc lời vẫn chạy.
Alpha thật: dựng mỗi khung 2 lần trên nền đen và nền trắng → alpha = 1 − (trắng − đen).
"""
from __future__ import annotations

import re
import unicodedata

import cv2
import numpy as np

from ..v2m import render as R
from . import hfx
from .edit import FORMATS, crop_at, face_out, layout, media, seg_at, src_to_out, words_out

REVEAL = {"nhe": ("fade", 0.45), "can_bang": ("up", 0.4), "nang_dong": ("pop", 0.35)}
ACCENT = {"bds": "#FFD34D", "san_pham": "#FFFFFF"}
SAFE = {"9x16": (70, 170, 1010, 1600), "16x9": (100, 70, 1820, 990)}
CONJ = {"và", "nhưng", "thì", "rồi", "để", "khi", "vì", "nên", "còn", "mà", "hoặc", "nếu", "sau", "thay"}   # ngắt TRƯỚC các từ này
PROTECT = ["motion graphic", "khăn giấy ướt"]
NO_END = {"một", "những", "các", "cái", "của", "cho", "vào", "với", "từ", "ở", "trong", "là", "rất", "đã", "sẽ", "đang", "này", "tại", "dọc", "trên", "dưới", "về", "theo", "quý", "nhà"}   # không kết cụm bằng các từ này (trừ “này” cuối câu)                 # cụm không tách (+ edit.keep_terms)
SUB_RATIO = 0.58     # chữ phụ (nhãn trên số / dòng nhỏ trên chữ nhấn) so với chữ chính
UNIT = re.compile(r"^(m2|m²|mét|tỷ|triệu|tr|k|đồng|%|gb|tb|ml|g|kg|inch|tháng|năm|phút|giây)$", re.I)


def _n(s):
    return unicodedata.normalize("NFC", s.lower()).strip(".,!?;:…“”\"")


def _normalize(ws: list[dict], edit: dict) -> list[dict]:
    """máy chép lời hay thiếu dấu chấm và viết hoa từ đầu câu giữa dòng (“vào Sau đó”, “tôi Thay thế”) → thêm dấu chấm cho từ trước."""
    proper = {_n(x) for x in edit.get("keep_terms", [])} | {_n(v) for v in edit.get("replace", {}).values()} \
        | {_n(f["to"]) for f in edit.get("fixes", [])}
    out = [dict(w) for w in ws]
    for i in range(1, len(out)):
        w, p = out[i], out[i - 1]
        txt = w["text"]
        # đầu câu thật: từ mở câu quen thuộc (Và, Thì, Sau, Thay…) hoặc sau chỗ ngừng rõ — KHÔNG phải tên riêng (Việt Nam, Mỹ, Nhà Bè…)
        nxt_cap = i + 1 < len(out) and out[i + 1]["text"][:1].isupper()
        gap = w["t"] - p["t_end"]
        starter = _n(txt) in STARTERS or (gap >= 0.3 and not nxt_cap and _n(txt) not in proper)
        if txt[:1].isupper() and not txt.isupper() and starter and _n(txt) not in proper \
                and not re.search(r"[.?!…:]$", p["text"]):
            p["text"] = p["text"].rstrip(",") + "."
    if out and not re.search(r"[.?!…]$", out[-1]["text"]):
        out[-1]["text"] += "."                     # câu cuối video
    return out


COMMON_CP = {tuple(x.split()) for x in """quản lý|kinh nghiệm|bất động|động sản|nghỉ dưỡng|thị trường|sản phẩm|dự án|khu vực|tiêu chuẩn|triển khai|
khách hàng|thông tin|đầu tư|chủ đầu|việt nam|đô la|bàn giao|đô thị|chu kỳ|bình luận|đội ngũ|hấp dẫn|cửa hàng|văn phòng|doanh nghiệp|hoàn thiện|
nhận diện|minh họa|khuôn mặt|nổi bật|diện tích|phòng ngủ|mặt tiền|tiện ích|chất lượng|giá trị|lợi nhuận|thiết kế|công năng""".replace("\n", "").split("|")}
STARTERS = set("và thì sau thay tôi đây đó nhưng còn khi nếu vì hãy bây mình em anh chị chúng các những một có không rồi nên vậy".split())


def _protected(a: str, b: str, terms) -> bool:
    pair = f"{_n(a)} {_n(b)}"
    from ..v2m.vtext import COMPOUNDS
    if re.fullmatch(r"[A-ZĐ]{1,2}\d{0,3}[,.]?", b.strip()):        # tên ngắn: “đường D”, “khu A”, “block B2”
        return True
    return any(pair in t for t in terms) or (bool(re.search(r"\d", a)) and bool(UNIT.match(_n(b)))) \
        or (_n(a), _n(b)) in COMMON_CP or any((_n(a), _n(b)) == c[i:i + 2] for c in COMPOUNDS for i in range(len(c) - 1))


def captions(edit: dict, pdir, fmt: str) -> list[list[dict]]:
    """chia lời thành cụm phụ đề theo NGHĨA (không theo số từ cố định)."""
    V = fmt == "9x16"
    maxc = 34 if V else 52          # ~2 dòng đọc được; ngắt ở điểm nghĩa, không cắt cụm danh từ cuối câu
    ws = _normalize(words_out(edit, pdir), edit)
    terms = [_n(t) for t in PROTECT + list(edit.get("keep_terms", []))]
    sents, cur = [], []
    for i, w in enumerate(ws):                      # câu: dấu kết câu, đổi đoạn, ngừng ≥ 0,35s
        if cur and (w["grp"] != cur[-1]["grp"] or (w["t"] - cur[-1]["t_end"] >= 0.35 and _n(cur[-1]["text"]) not in NO_END)):    # đoạn con của Cắt sạch vẫn chung câu
            sents.append(cur); cur = []
        cur.append(w)
        if re.search(r"[.?!…]$", w["text"]):
            sents.append(cur); cur = []
    if cur:
        sents.append(cur)
    out = []
    for s in sents:
        while s:
            text = " ".join(w["text"] for w in s)
            if len(text) <= maxc or (len(text) <= maxc + 8 and len(s) <= 9):    # câu ngắn hơi dài vẫn để nguyên, không bẻ vụn
                out.append(s); break
            best, best_c, ln = None, None, 0
            for k in range(1, len(s)):
                ln = len(" ".join(w["text"] for w in s[:k]))
                if ln > maxc:
                    break
                if k >= 2 and not _protected(s[k - 1]["text"], s[k]["text"], terms) and _n(s[k - 1]["text"]) not in NO_END and \
                        (s[k - 1]["text"].endswith(",") or _n(s[k]["text"]) in CONJ or s[k]["t"] - s[k - 1]["t_end"] >= 0.2):
                    best = k                         # điểm ngắt theo nghĩa xa nhất còn vừa
                    if s[k - 1]["text"].endswith(","):
                        best_c = k                   # dấu phẩy là ranh giới nghĩa rõ nhất
            if best_c is not None and len(" ".join(w["text"] for w in s[:best_c])) >= maxc * 0.45:
                best = best_c
            if best is None:
                k = max(1, min(range(1, len(s)), key=lambda k: abs(len(" ".join(w["text"] for w in s[:k])) - maxc * 0.75)))
                while k > 1 and (_n(s[k - 1]["text"]) in NO_END or _protected(s[k - 1]["text"], s[k]["text"], terms)):
                    k -= 1                                  # lùi điểm ngắt ra trước cụm “một đoạn…”, “cái khăn…”
                best = k
            rest = s[best:]
            if len(rest) <= 2 and len(" ".join(w["text"] for w in rest)) <= 10 and len(text) <= maxc + 12:   # không để 1–2 từ lẻ cụm sau
                out.append(s); break
            out.append(s[:best]); s = rest
    # cụm hiện < 1s (nói nhanh) → gộp với cụm sau cùng câu nếu vẫn đọc được (≤ maxc + 8)
    k = 0
    while k < len(out) - 1:
        a, b = out[k], out[k + 1]
        if b[0]["t"] - a[0]["t"] < 1.0 and a[-1]["grp"] == b[0]["grp"] and not re.search(r"[.?!…]$", a[-1]["text"]) and \
                len(" ".join(w["text"] for w in a + b)) <= maxc + 8:
            out[k:k + 2] = [a + b]; continue
        k += 1
    return out


def _ov(a, b, pad=0):
    return max(0, min(a[2], b[2] + pad) - max(a[0], b[0] - pad)) * max(0, min(a[3], b[3] + pad) - max(a[1], b[1] - pad))


def _obstacles(edit, pdir, fmt, s, t0, t1, step=0.25):
    """vật cản trên khung xuất trong [t0, t1]: mặt + tóc, và vật đang được nhấn (track của label/spotlight/focus trong đoạn)."""
    from .objects import box_at, load_track
    out = []
    m = media(pdir)[s["src"]]
    tracks = {t["track"] for t in s.get("texts", []) if t.get("track")}
    tt = t0
    while tt <= t1 + 1e-6:
        f = face_out(pdir, edit, fmt, tt)
        if f:
            out.append(f)
        loc = tt - s["t0"]
        for name in tracks:
            try:
                b = box_at(load_track(pdir, name), float(s["in"]) + loc)
            except FileNotFoundError:
                b = None
            if b:
                c = crop_at(pdir, s, m, fmt, loc)
                x0, y0 = src_to_out(m, fmt, c, b[0], b[1]); x1, y1 = src_to_out(m, fmt, c, b[0] + b[2], b[1] + b[3])
                out.append((x0 - 24, y0 - 24, x1 + 24, y1 + 24))
        tt += step
    return out


def _emph_pos(edit, pdir, fmt, s, at, d, w_txt, h_txt, cap_band=None, min_w=0):
    """vị trí chữ nhấn (x, y, max_w): thử trên đầu → dưới mặt (dọc) / hai bên khung (ngang); chọn chỗ không chạm mặt/tóc/vật đang nhấn."""
    W, H = FORMATS[fmt]
    if fmt == "9x16":
        cands = [(W / 2, H * 0.14, W * 0.88), (W / 2, H * 0.2, W * 0.88), (W / 2, H * 0.6, W * 0.88), (W / 2, H * 0.69, W * 0.88)]
    else:
        cands = [(W / 2, H * 0.16, W * 0.8), (W * 0.195, H * 0.42, W * 0.27), (W * 0.805, H * 0.42, W * 0.27), (W / 2, H * 0.7, W * 0.8)]   # ô bên nằm trọn trong vùng an toàn (6–33%)
    if min_w:                                    # khối bảng (so sánh): ô bên rộng hơn ở bản ngang; chỉ xét chỗ co ≤ 25%; không nằm dải phụ đề
        if fmt != "9x16":
            cands = [(W * 0.21, H * 0.40, W * 0.30), (W * 0.79, H * 0.40, W * 0.30), (W / 2, H * 0.2, W * 0.8)]
        cands = [c for c in cands if c[2] >= min_w * 0.75] or cands
    obs = _obstacles(edit, pdir, fmt, s, at, at + d)
    x0s, y0s, x1s, y1s = SAFE[fmt]
    best, score = (cands[0][0], cands[0][1], cands[0][2], 1.0), 1e18
    for sc in (1.0, 0.82, 0.68):                 # không còn chỗ trống → thu nhỏ chữ nhấn tới khi vừa khoảng trống
        for x, y, mw in cands:
            ww = min(w_txt * sc, mw)
            hh = h_txt * sc * (1 if w_txt * sc <= mw else 2)
            y = min(max(y, y0s + hh / 2), y1s - hh / 2)          # khối cao (bảng) vẫn nằm trong vùng an toàn
            box = (x - ww / 2 - 10, y - hh / 2 - 10, x + ww / 2 + 10, y + hh / 2 + 10)
            ov = sum(_ov(box, o) for o in obs)
            if cap_band and _ov(box, cap_band) > 0:
                ov += 1e9                        # dải phụ đề là vùng CẤM (cả hai do app đặt) — chỉ chọn khi không còn chỗ nào khác
            if ov < score - 1e-6:
                best, score = (x, y, mw, sc), ov
            if ov == 0:
                return best
    return best


def _caption_y(edit, pdir, fmt, s, h_cap):
    """một vị trí phụ đề cho CẢ đoạn (ổn định): mặc định dưới; né vật đang nhấn + mặt nếu chạm."""
    W, H = FORMATS[fmt]
    cands = [0.78, 0.70, 0.17] if fmt == "9x16" else [0.86, 0.74, 0.14]   # trong vùng an toàn; hết chỗ dưới → dải trên (cả đoạn, không nhảy)
    obs = _obstacles(edit, pdir, fmt, s, s["t0"], s["t1"], 0.5) if any(t.get("track") for t in s.get("texts", [])) else []
    if not obs:
        return H * cands[0]
    best, score = cands[0], 1e18
    for c in cands:
        box = (W * 0.08, H * c - h_cap / 2, W * 0.92, H * c + h_cap / 2)
        ov = sum(_ov(box, o) for o in obs)
        if ov < score - 1e-6:
            best, score = c, ov
        if ov == 0:
            break
    return H * best


def objects(edit: dict, pdir, fmt: str) -> tuple[list[dict], list[dict]]:
    W, H = FORMATS[fmt]
    V = fmt == "9x16"
    x0, y0, x1, y1 = SAFE[fmt]
    objs, evs = [], []
    n = [0]

    def oid(p):
        n[0] += 1
        return f"{p}{n[0]}"

    def show(o, t, d, style="fade", sd=0.25):
        objs.append(o)
        evs.append({"object_id": o["id"], "action": "reveal", "start_s": round(t, 3), "end_s": round(t + sd, 3), "style": style})
        evs.append({"object_id": o["id"], "action": "hide", "start_s": round(t + d - 0.18, 3), "end_s": round(t + d, 3), "style": "fade"})

    acc_sub = edit.get("subtitle_active") or "#FFD34D"
    cap_h = (54 if V else 46) * 1.15 * 2 + 20
    seg_y = {sg["id"]: _caption_y(edit, pdir, fmt, sg, cap_h) for sg in layout(edit)} if edit.get("subtitles", True) else {}
    if edit.get("subtitles", True):
        phs = captions(edit, pdir, fmt)
        for k, ph in enumerate(phs):
            txt = " ".join(w["text"] for w in ph)
            a = ph[0]["t"] - 0.05
            nxt = phs[k + 1][0]["t"] - 0.05 if k + 1 < len(phs) else 1e9
            end = max(ph[-1]["t_end"] + 0.25, a + max(0.8, len(txt) / 17))      # đủ thời gian đọc
            end = max(min(end, nxt - 0.1), min(a + 0.6, nxt - 0.1))
            show({"id": oid("cap"), "type": "text", "role": "caption", "text": txt, "font": "bold",
                  "size": 54 if V else 46, "color": "#FFFFFF", "space": "screen", "x": W / 2, "y": seg_y.get(ph[0]["seg"], H * 0.78), "max_w": (x1 - x0) * 0.92,
                  "stroke": 5, "stroke_color": "#000000", "shadow": 0.5, "line_h": 1.15, "layer": 30,
                  "keep": [t for t in PROTECT + list(edit.get("keep_terms", []))],
                  "active_times": [round(w["t"], 3) for w in ph], "active_color": acc_sub}, a, end - a, "fade", 0.08)
    style, sd = REVEAL.get(edit.get("intensity", "can_bang"), REVEAL["can_bang"])
    acc = edit.get("accent") or ACCENT.get(edit.get("category", "san_pham"), "#FFFFFF")
    segs = layout(edit)
    for s in segs:
        grp = s.get("group", s["id"])
        g_end = max(x["t1"] for x in segs if x.get("group", x["id"]) == grp)       # chữ được kéo qua các đoạn con cùng nhóm
        for t in s.get("texts", []):
            if hfx.uses(edit, t):           # dựng bằng HyperFrames (công cụ chung) — ghép ở render, không vẽ lại ở đây
                continue
            at = s["t0"] + float(t["at"])
            d = min(float(t.get("dur", 2.5)), g_end - at + (0.0 if g_end < segs[-1]["t1"] - 1e-6 else 99))
            role = t["role"]
            if role == "label" and t.get("track"):
                cy_ = seg_y.get(s["id"]) if seg_y else None
                band = (0, cy_ - cap_h / 2, W, cy_ + cap_h / 2) if cy_ else None      # dải phụ đề của đoạn = vật cản cho nhãn
                _label(objs, evs, oid, t, s, edit, pdir, fmt, at, d, acc, style, sd, band)
            elif role == "focus" and t.get("track"):
                _focus(objs, evs, oid, t, s, edit, pdir, fmt, at, d, acc)
            elif role == "spotlight":
                if t.get("frame", True) and t.get("track"):   # viền mảnh theo đúng vùng sáng (không thêm glow/rung)
                    _focus(objs, evs, oid, {**t, "color": t.get("frame_color", "#FFFFFF")}, s, edit, pdir, fmt, at, d, acc, width=3, pad=t.get("pad", 22))
            elif role == "stat":     # SỐ LIỆU then chốt: số chạy + đơn vị (màu nhấn), nhãn nhỏ; tự né mặt/vật/phụ đề
                from ..v2m import draw as D
                size = 104 if V else 94       # chữ nhỏ ≈ 0,58 chữ lớn — hai tầng cân nhau, không chênh quá
                val = float(t["value"])
                dec = int(t.get("decimals", 0 if val == int(val) else 1))
                unit = (" " + t["unit"]) if t.get("unit") else ""
                from ..v2m.render import _fmt_num
                shown = f"{t.get('prefix', '')}{_fmt_num(val, dec)}{unit}"      # đúng chữ hiển thị (5.000 / 6,7) để đo bề rộng
                w_txt = D.font("black", size).getlength(shown)
                cy_ = seg_y.get(s["id"]) if seg_y else None
                band = (0, cy_ - cap_h / 2, W, cy_ + cap_h / 2) if cy_ else None
                lab = int(size * SUB_RATIO) if t.get("label") else 0
                ex, cy, mw, sc = _emph_pos(edit, pdir, fmt, s, at, d, w_txt, size * 1.05 + lab * 1.55, band)
                k_ = sc * (min(1.0, mw / (w_txt * sc)) if w_txt * sc > mw else 1.0)
                size, lab = int(size * k_), int(lab * max(k_, 0.85))
                top = cy - (size * 1.05 + lab * 1.55) / 2
                num = {"id": oid("stat"), "type": "counter", "value": 0, "decimals": dec, "prefix": t.get("prefix", ""), "suffix": unit,
                       "font": "black", "size": size, "color": t.get("color", "#FFD34D"), "space": "screen", "x": ex, "y": top + lab * 1.55 + size * 0.525,
                       "stroke": 6, "stroke_color": "#000000", "shadow": 0.6, "layer": 26}
                show(num, at, d, "pop" if style != "fade" else "fade", 0.3)
                evs.append({"object_id": num["id"], "action": "count", "start_s": round(at + 0.05, 3), "end_s": round(at + min(0.9, d * 0.4), 3),
                            "to": {"value": val}, "ease": "out"})
                if t.get("label"):
                    show({"id": oid("statl"), "type": "text", "text": t["label"], "font": "bold", "size": lab,
                          "color": "#FFFFFF", "space": "screen", "x": ex, "y": top + lab * 0.6, "max_w": mw, "stroke": 5, "stroke_color": "#000000",
                          "shadow": 0.5, "layer": 26}, at, d, "fade", 0.25)
            elif role == "diagram":
                _diagram(objs, evs, oid, t, s, fmt, at, d, acc)
            elif role == "compare":   # công nghệ: so sánh 2 cột (thông số có trong lời/brief) — {"title","cols":[A,B],"rows":[[nhãn,a,b],…],"win":[1|2|0…]}
                from ..v2m import draw as D
                fs = 52 if V else 36
                F_ = D.font("bold", fs)
                rows = t["rows"]
                cols = t.get("cols", ["", ""])
                wl = max(F_.getlength(str(r[0])) for r in rows) + 30
                wc = max([F_.getlength(str(x)) for r in rows for x in r[1:3]] + [F_.getlength(str(c)) for c in cols]) + 36
                w_box = wl + 2 * wc + 56                           # bề rộng tự nhiên; co CẢ khối (hộp + chữ + cột) cùng tỷ lệ k_
                lim = (x1 - x0) * (0.94 if V else 0.42)
                rh = fs * 1.55
                h_box = 40 + (fs * 1.4 if t.get("title") else 0) + rh * (len(rows) + 1) + 20
                cy_ = seg_y.get(s["id"]) if seg_y else None
                band = (0, cy_ - cap_h / 2, W, cy_ + cap_h / 2) if cy_ else None
                ex, cy, mw, sc = _emph_pos(edit, pdir, fmt, s, at, d, w_box, h_box, band, min_w=w_box)
                k_ = min(1.0, mw / w_box, lim / w_box)
                cy = min(max(cy, y0 + h_box * k_ / 2), y1 - h_box * k_ / 2)        # trọn trong vùng an toàn
                card = {"id": oid("cmp"), "type": "rect", "w": w_box * k_, "h": h_box * k_, "r": 22, "fill": "#0E1116", "opacity": 0.84,
                        "space": "screen", "layer": 24, "x": ex, "y": cy}
                show(card, at, d, "pop" if style != "fade" else "fade", 0.3)
                f2 = int(fs * k_)
                y = -h_box * k_ / 2 + 20 * k_
                xl, xa, xb = -w_box * k_ / 2 + 28 * k_, -w_box * k_ / 2 + (28 + wl + wc / 2) * k_, -w_box * k_ / 2 + (28 + wl + wc * 1.5) * k_
                def tx(text, x, y_, color="#FFFFFF", anchor="center", font="bold", size=f2):
                    objs.append({"id": oid("cmpt"), "type": "text", "text": str(text), "font": font, "size": size, "color": color, "parent": card["id"],
                                 "x": x, "y": y_, "anchor": anchor, "align": "left" if anchor == "left" else "center", "shadow": 0})
                if t.get("title"):
                    tx(t["title"], 0, y + fs * 0.7 * k_, "#A9B4C8"); y += fs * 1.4 * k_
                y += rh * k_ / 2
                tx(cols[0], xa, y, acc, font="black"); tx(cols[1] if len(cols) > 1 else "", xb, y, "#FFFFFF", font="black")
                win = t.get("win", [])
                for i, r in enumerate(rows):
                    y += rh * k_
                    w_ = win[i] if i < len(win) else 0
                    tx(r[0], xl, y, "#C9D1DD", "left")
                    tx(r[1], xa, y, acc if w_ == 1 else "#FFFFFF", font="black" if w_ == 1 else "bold")
                    tx(r[2], xb, y, acc if w_ == 2 else "#FFFFFF", font="black" if w_ == 2 else "bold")
            elif role == "info":
                from ..v2m import draw as D
                lines = t["text"]
                fs = 40 if V else 34
                tw_ = max(D.font("bold", fs).getlength(x) for x in ((t.get("sub") + "\n" if t.get("sub") else "") + lines).split("\n"))
                w_box = min(tw_ + 56, (x1 - x0) * (0.9 if V else 0.5))
                card = {"id": oid("info"), "type": "rect", "w": w_box, "h": 70 + 52 * (lines.count("\n") + (1 if t.get("sub") else 0)),
                        "r": 18, "fill": "#101010", "opacity": 0.78, "space": "screen", "layer": 20,
                        "x": x0 + w_box / 2, "y": y0 + 120 if V else y1 - 150}
                show(card, at, d, "left" if style != "fade" else "fade", sd)
                txt = (t["sub"] + "\n" if t.get("sub") else "") + lines
                objs.append({"id": oid("infot"), "type": "text", "text": txt, "font": "bold", "size": fs, "color": "#FFFFFF",
                             "parent": card["id"], "x": -w_box / 2 + 28, "y": 0, "anchor": "left", "align": "left", "max_w": w_box - 56,
                             "line_h": 1.25, "shadow": 0, **({"highlight": {"match": t["hl"], "color": acc}} if t.get("hl") else {})})
            else:   # chữ nhấn hai tầng — vị trí tránh mặt/tóc
                from ..v2m import draw as D
                size = 88 if V else 80
                w_txt = D.font("black", size).getlength(t["text"])
                cy_ = seg_y.get(s["id"]) if seg_y else None
                band = (0, cy_ - cap_h / 2, W, cy_ + cap_h / 2) if cy_ else None
                sub = int(size * SUB_RATIO) if t.get("sub") else 0
                ex, cy, mw, sc = _emph_pos(edit, pdir, fmt, s, at, d, w_txt, size * 1.05 + sub * 1.55, band)
                k_ = sc * (max(0.6, mw / (w_txt * sc)) if w_txt * sc > mw else 1.0)
                size, sub = int(size * k_), int(sub * max(k_, 0.85))
                top = cy - (size * 1.05 + sub * 1.55) / 2
                o = {"id": oid("emph"), "type": "text", "text": t["text"], "font": "black", "size": size, "color": "#FFFFFF",
                     "space": "screen", "x": ex, "y": top + sub * 1.55 + size * 0.525, "max_w": mw, "stroke": 6,
                     "stroke_color": "#000000", "shadow": 0.6, "line_h": 1.02, "layer": 25}
                if t.get("hl"):
                    o["highlight"] = {"match": t["hl"], "color": acc}
                show(o, at, d, style, sd)
                if t.get("sub"):
                    show({"id": oid("emphs"), "type": "text", "text": t["sub"], "font": "bold", "size": sub, "color": "#FFFFFF",
                          "space": "screen", "x": ex, "y": top + sub * 0.6, "max_w": mw, "stroke": 5, "stroke_color": "#000000",
                          "shadow": 0.5, "layer": 25}, at - 0.1, d + 0.1, "fade", 0.25)
    return objs, evs


def _diagram(objs, evs, oid, t, s, fmt, at, d, acc):
    """sơ đồ minh họa ý: nền phủ + các nút (icon + chữ) hiện theo lời, mũi tên vẽ dần; lời vẫn chạy bên dưới."""
    W, H = FORMATS[fmt]
    V = fmt == "9x16"
    items = t.get("items", [])
    bg = {"id": oid("dgbg"), "type": "rect", "w": W + 40, "h": H + 40, "r": 0, "fill": "#0E1420", "opacity": 0.93, "space": "screen",
          "x": W / 2, "y": H / 2, "layer": 10}
    objs.append(bg)
    evs.append({"object_id": bg["id"], "action": "reveal", "start_s": round(at, 3), "end_s": round(at + 0.3, 3), "style": "fade"})
    evs.append({"object_id": bg["id"], "action": "hide", "start_s": round(at + d - 0.3, 3), "end_s": round(at + d, 3), "style": "fade"})
    if t.get("title"):
        tt = {"id": oid("dgt"), "type": "text", "text": t["title"], "font": "bold", "size": 46 if V else 44, "color": "#A9B4C8",
              "space": "screen", "x": W / 2, "y": H * (0.2 if V else 0.16), "layer": 12, "shadow": 0, "max_w": W * 0.84}
        objs.append(tt)
        evs.append({"object_id": tt["id"], "action": "reveal", "start_s": round(at + 0.1, 3), "end_s": round(at + 0.45, 3), "style": "up"})
        evs.append({"object_id": tt["id"], "action": "hide", "start_s": round(at + d - 0.3, 3), "end_s": round(at + d, 3), "style": "fade"})
    k = len(items)
    prev = None
    for i, it in enumerate(items):
        ta = s["t0"] + float(it["at"])
        if V:
            x, y = W * 0.27, H * (0.33 + i * (0.36 / max(k - 1, 1)))
            lab = {"x": W * 0.39, "y": y, "anchor": "left", "align": "left", "max_w": W * 0.55}
        else:
            x, y = W * (0.2 + i * (0.6 / max(k - 1, 1))), H * 0.45
            lab = {"x": x, "y": y + 150, "max_w": W * 0.26}
        ic = {"id": oid("dgi"), "type": "icon", "name": it.get("icon", "circle"), "size": 84, "color": "#0E1420", "bg": acc if acc != "#FFFFFF" else "#FFD34D",
              "bg_r": 92, "space": "screen", "x": x, "y": y, "layer": 13, "shadow": 0.3}
        tx = {"id": oid("dgl"), "type": "text", "text": it["text"], "font": "bold", "size": 48 if V else 42, "color": "#FFFFFF", "space": "screen",
              "layer": 13, "shadow": 0, "line_h": 1.1, **lab}
        objs += [ic, tx]
        for o, st in ((ic, "pop"), (tx, "up")):
            evs.append({"object_id": o["id"], "action": "reveal", "start_s": round(ta, 3), "end_s": round(ta + 0.35, 3), "style": st})
            evs.append({"object_id": o["id"], "action": "hide", "start_s": round(at + d - 0.3, 3), "end_s": round(at + d, 3), "style": "fade"})
        if prev:
            ln = {"id": oid("dga"), "type": "line", "from": prev, "to": ic["id"], "width": 6, "color": "#A9B4C8", "arrow": True, "space": "screen",
                  "trim_start": 104, "trim_end": 112, "layer": 12, "progress": 0}
            objs.append(ln)
            evs.append({"object_id": ln["id"], "action": "draw", "start_s": round(ta - 0.35, 3), "end_s": round(ta, 3), "ease": "out"})
            evs.append({"object_id": ln["id"], "action": "hide", "start_s": round(at + d - 0.3, 3), "end_s": round(at + d, 3), "style": "fade"})
        prev = ic["id"]


def _track_boxes(t, s, edit, pdir, fmt, at, d, step=0.2):
    """box vật (px khung xuất) theo thời gian xuất trong [at, at+d] — theo track + crop/reframe của đoạn."""
    from .objects import box_at, load_track
    tr = load_track(pdir, t["track"])
    out = []
    n = max(1, int(round(d / step)))
    for k in range(n + 1):
        tt = at + k * d / n
        sg = seg_at(edit, tt, s.get("group", s["id"])) or s          # đoạn con đang chạy (Cắt sạch chia nhỏ)
        m = media(pdir)[sg["src"]]
        loc = tt - sg["t0"]
        b = box_at(tr, float(sg["in"]) + loc)
        if b is None:
            continue
        c = crop_at(pdir, sg, m, fmt, loc)
        bx0, by0 = src_to_out(m, fmt, c, b[0], b[1])
        bx1, by1 = src_to_out(m, fmt, c, b[0] + b[2], b[1] + b[3])
        out.append((round(tt, 3), bx0, by0, bx1, by1))
    return out


def _follow(evs, oid_, pts, f):
    for (ta, *ba), (tb, *bb) in zip(pts, pts[1:]):
        evs.append({"object_id": oid_, "action": "animate", "start_s": ta, "end_s": tb, "to": f(bb), "ease": "linear"})


def _label(objs, evs, oid, t, s, edit, pdir, fmt, at, d, acc, style, sd, cap_band=None):
    """nhãn sản phẩm SÁT vật: phía trên vật nếu còn chỗ, không thì dưới; chấm neo trên mép vật + đường dẫn ngắn; khung ôm chữ."""
    from ..v2m import draw as D
    x0s, y0s, x1s, y1s = SAFE[fmt]
    pts = _track_boxes(t, s, edit, pdir, fmt, at, d, 0.1)
    if not pts:
        return
    fs = 40 if fmt == "9x16" else 36
    tw_ = D.font("bold", fs).getlength(t["text"]) + 44
    th_ = fs * 1.7

    faces = [f for f in (face_out(pdir, edit, fmt, p[0]) for p in pts[::3]) if f]

    def place_side(b, side):
        bx0, by0, bx1, by1 = b
        mx, my = (bx0 + bx1) / 2, (by0 + by1) / 2
        if side == "tren":
            lx, ly, ax, ay = mx, by0 - 80, mx, by0 + 6
        elif side == "duoi":
            lx, ly, ax, ay = mx, by1 + 80, mx, by1 - 6
        elif side == "phai":
            lx, ly, ax, ay = bx1 + 60 + tw_ / 2, my - 40, bx1 - 6, my - 40
        else:
            lx, ly, ax, ay = bx0 - 60 - tw_ / 2, my - 40, bx0 + 6, my - 40
        lx = min(max(lx, x0s + tw_ / 2), x1s - tw_ / 2)
        ly = min(max(ly, y0s + th_ / 2), y1s - th_ / 2)
        return {"x": round(lx, 1), "y": round(ly, 1)}, {"x": round(ax, 1), "y": round(ay, 1)}

    def cost(side):             # chạm mặt/tóc hoặc che chính vật → không chọn; giữ MỘT hướng suốt thời gian hiện (không nhảy)
        c = 0.0
        for p in pts[::3]:
            l, _ = place_side(p[1:], side)
            box = (l["x"] - tw_ / 2, l["y"] - th_ / 2, l["x"] + tw_ / 2, l["y"] + th_ / 2)
            c += sum(_ov(box, f, 10) for f in faces) + 0.5 * _ov(box, p[1:]) + 3 * (_ov(box, cap_band) if cap_band else 0)
        return c
    side = min(("tren", "duoi", "phai", "trai"), key=lambda sd_: (cost(sd_), ("tren", "duoi", "phai", "trai").index(sd_)))

    def place(b):
        return place_side(b, side)
    l0, a0 = place(pts[0][1:])
    card = {"id": oid("lab"), "type": "rect", "w": tw_, "h": th_, "r": th_ / 2, "fill": "#111111", "opacity": 0.85, "space": "screen",
            "layer": 22, **l0}
    anc = {"id": oid("anc"), "type": "circle", "r": 9, "fill": acc, "stroke": "#FFFFFF", "stroke_w": 3, "space": "screen", "layer": 23, **a0}
    line = {"id": oid("leader"), "type": "line", "from": card["id"], "to": anc["id"], "width": 3, "color": "#FFFFFF", "space": "screen",
            "trim_start": th_ / 2 + 2, "trim_end": 10, "layer": 21, "progress": 0}
    txt = {"id": oid("labt"), "type": "text", "text": t["text"], "font": "bold", "size": fs, "color": "#FFFFFF", "parent": card["id"],
           "x": 0, "y": 0, "shadow": 0}
    objs += [card, anc, line, txt]
    for o, st in ((anc, "pop"), (card, style)):
        evs.append({"object_id": o["id"], "action": "reveal", "start_s": round(at, 3), "end_s": round(at + sd, 3), "style": st})
        evs.append({"object_id": o["id"], "action": "hide", "start_s": round(at + d - 0.24, 3), "end_s": round(at + d, 3), "style": "fade"})
    evs.append({"object_id": line["id"], "action": "draw", "start_s": round(at + 0.05, 3), "end_s": round(at + 0.35, 3), "ease": "out"})
    evs.append({"object_id": line["id"], "action": "hide", "start_s": round(at + d - 0.24, 3), "end_s": round(at + d, 3), "style": "fade"})
    _follow(evs, card["id"], pts, lambda b: place(b)[0])
    _follow(evs, anc["id"], pts, lambda b: place(b)[1])


def _focus(objs, evs, oid, t, s, edit, pdir, fmt, at, d, acc, width=5, pad=18):
    """viền mềm ôm vật đúng lúc chỉ tay (dùng kèm spotlight hoặc riêng)."""
    pts = _track_boxes(t, s, edit, pdir, fmt, at, d, 0.1)
    if not pts:
        return

    def geo(b):
        bx0, by0, bx1, by1 = b
        return {"x": round((bx0 + bx1) / 2, 1), "y": round((by0 + by1) / 2, 1), "w": round(bx1 - bx0 + 2 * pad, 1), "h": round(by1 - by0 + 2 * pad, 1)}
    ring = {"id": oid("ring"), "type": "rect", "r": 28, "fill": None, "stroke": t.get("color", acc), "stroke_w": width, "shadow": 0.3,
            "space": "screen", "layer": 19, **geo(pts[0][1:])}
    objs.append(ring)
    evs.append({"object_id": ring["id"], "action": "reveal", "start_s": round(at, 3), "end_s": round(at + 0.3, 3), "style": "fade"})
    evs.append({"object_id": ring["id"], "action": "hide", "start_s": round(at + d - 0.24, 3), "end_s": round(at + d, 3), "style": "fade"})
    _follow(evs, ring["id"], pts, geo)


def timeline(edit: dict, pdir, fmt: str, bg: str) -> R.Timeline:
    from pathlib import Path
    from .edit import duration
    W, H = FORMATS[fmt]
    objs, evs = objects(edit, pdir, fmt)
    T = duration(edit)
    d = {"project_id": "review", "audio": {"path": "", "duration_s": T}, "canvas": {"width": W, "height": H, "fps": edit.get("fps", 30), "format": fmt},
         "theme": {"bg": bg, "bg2": bg, "glow": bg, "text": "#FFFFFF", "muted": "#CCCCCC", "accent": "#FFD34D", "alt": "#FFFFFF",
                   "deco": [], "idle": False, "sfx_auto": False, "map_fixed": False},
         "scenes": [{"id": "S01", "start_s": 0, "end_s": T, "objects": objs, "events": evs}]}
    return R.Timeline(d, Path(pdir))


class Spot:
    """spotlight: lớp đen opacity `dim` ngoài ô bo góc mềm ôm vật; fade vào/ra; mất dấu → tắt."""
    FADE = 0.24

    def __init__(self, t, s, edit, pdir, fmt):
        self.at = s["t0"] + float(t["at"])
        self.d = float(t.get("dur", 2.0))
        self.dim = float(t.get("dim", 0.32))
        self.pad = float(t.get("pad", 22))
        self.pts = _track_boxes(t, s, edit, pdir, fmt, self.at, self.d, 1 / 30)
        self.W, self.H = FORMATS[fmt]
        self.miss = 0

    def box(self, t):
        if not self.pts or t < self.pts[0][0] - 0.02 or t > self.pts[-1][0] + 0.02:
            return None
        i = min(range(len(self.pts)), key=lambda k: abs(self.pts[k][0] - t))
        if abs(self.pts[i][0] - t) > 0.08:          # lỗ hổng do mất dấu
            return None
        return self.pts[i][1:]

    def alpha(self, t) -> np.ndarray | None:
        if not (self.at <= t <= self.at + self.d):
            return None
        b = self.box(t)
        if b is None:
            self.miss += 1
            return None
        k = min((t - self.at) / self.FADE, (self.at + self.d - t) / self.FADE, 1.0)
        q = 4
        m = np.zeros((self.H // q, self.W // q), np.float32)
        x0, y0, x1, y1 = [(v + (-self.pad if j < 2 else self.pad)) / q for j, v in enumerate(b)]
        r = 26 / q
        xi0, yi0, xi1, yi1 = int(x0), int(y0), int(x1), int(y1)
        cv2.rectangle(m, (int(xi0 + r), yi0), (int(xi1 - r), yi1), 1.0, -1)
        cv2.rectangle(m, (xi0, int(yi0 + r)), (xi1, int(yi1 - r)), 1.0, -1)
        for cx, cy in ((xi0 + r, yi0 + r), (xi1 - r, yi0 + r), (xi0 + r, yi1 - r), (xi1 - r, yi1 - r)):
            cv2.circle(m, (int(cx), int(cy)), int(r), 1.0, -1)
        m = cv2.GaussianBlur(m, (0, 0), 3.0)
        m = cv2.resize(m, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        return (self.dim * max(k, 0.0)) * (1.0 - m)


class Layer:
    """khung RGBA lớp đồ họa tại thời điểm t: spotlight (dưới) + chữ/nhãn/sơ đồ (trên)."""

    def __init__(self, edit, pdir, fmt):
        self.tb, self.tw = timeline(edit, pdir, fmt, "#000000"), timeline(edit, pdir, fmt, "#FFFFFF")
        self.Rb, self.Rw = R.Renderer(self.tb), R.Renderer(self.tw)
        self.W, self.H = FORMATS[fmt]
        self.spans = [o["_vis"] for o in self.tb.objs.values()]
        self.spots = [Spot(t, s, edit, pdir, fmt) for s in layout(edit) for t in s.get("texts", [])
                      if t["role"] == "spotlight" and t.get("track") and not hfx.uses(edit, t)]
        self.spans += [(sp.at, sp.at + sp.d) for sp in self.spots]
        self.boxes = []

    def active(self, t) -> bool:
        return any(a - 0.02 <= t <= b + 0.02 for a, b in self.spans)

    def rgba(self, t, prev=None) -> np.ndarray | None:
        if not self.active(t):
            self.boxes = []
            return None
        dim = None
        for sp in self.spots:
            a = sp.alpha(t)
            if a is not None:
                dim = a if dim is None else 1 - (1 - dim) * (1 - a)
        if any(x <= t <= y for x, y in self.spans[:len(self.spans) - len(self.spots)]):
            b = np.clip(self.Rb.frame(t, prev), 0, 1)
            w = np.clip(self.Rw.frame(t, prev), 0, 1)
            self.boxes = list(self.Rb.boxes)
            ta = np.clip(1.0 - (w - b).mean(axis=2, keepdims=True), 0, 1)
            col = np.where(ta > 1e-3, b / np.maximum(ta, 1e-3), 0)
        else:
            self.boxes = []
            ta = np.zeros((self.H, self.W, 1), np.float32)
            col = np.zeros((self.H, self.W, 3), np.float32)
        if dim is not None:                    # chữ/nhãn đè lên lớp tối
            da = dim[..., None]
            oa = ta + da * (1 - ta)
            col = np.where(oa > 1e-4, col * ta / np.maximum(oa, 1e-4), 0)
            ta = oa
        return np.concatenate([np.clip(col, 0, 1), ta], axis=2).astype(np.float32)
