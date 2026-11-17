"""Kịch bản → LỜI ĐỌC tiếng Việt cho bộ đọc (TTS). Phụ đề vẫn giữ chữ gốc của kịch bản.

Bộ đọc tiếng Việt đoán sai chữ số, ký hiệu, chữ viết tắt, tên hãng tiếng Anh ("1/11/2026", "1,5", "25.000đ", "60m²", "kWh",
"VAT", "PVcomBank"…) → đọc sai chữ và bị đọc lại vô ích. Ở đây đổi hết sang chữ tiếng Việt đọc tự nhiên:
  1/11/2026 → ngày một tháng mười một năm hai nghìn không trăm hai mươi sáu · 10,7 triệu → mười phẩy bảy triệu
  1.901 → một nghìn chín trăm linh một · 30–40% → ba mươi đến bốn mươi phần trăm · 25.000đ → hai mươi lăm nghìn đồng
  60m² → sáu mươi mét vuông · VAT → vê a tê · CafeF → cà phê ép
Dùng chung cho so khớp chép lời ↔ kịch bản (t2v._align) để đọc đúng không bị coi là đọc sai."""
from __future__ import annotations

import re
import unicodedata

_DIG = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]

LETTER = {"a": "a", "b": "bê", "c": "xê", "d": "đê", "e": "e", "f": "ép", "g": "gờ", "h": "hát", "i": "i", "j": "gi",
          "k": "ca", "l": "lờ", "m": "em", "n": "en", "o": "o", "p": "pê", "q": "quy", "r": "rờ", "s": "ét", "t": "tê",
          "u": "u", "v": "vê", "w": "vê kép", "x": "ích", "y": "i", "z": "dét", "đ": "đê"}

# tên riêng / chữ viết tắt hay gặp → cách người Việt đọc (khoá viết thường, bỏ dấu chấm)
WORDS = {
    "vat": "vê a tê", "gdp": "gờ đê pê", "cpi": "xê pê i", "ceo": "xi i âu", "atm": "a tê em", "usd": "u ét đê",
    "vnd": "việt nam đồng", "vnđ": "việt nam đồng", "eur": "ơ rô", "ai": "a i", "app": "áp", "online": "online",
    "bđs": "bất động sản", "tp": "thành phố", "tp.hcm": "thành phố hồ chí minh", "tphcm": "thành phố hồ chí minh",
    "hcm": "hồ chí minh", "sjc": "ét gi xê", "pnj": "pê en gi", "doji": "đô gi", "btmc": "bê tê em xê",
    "cbre": "xê bê e rờ e", "savills": "sa vin", "cafef": "cà phê ép", "vnexpress": "vi en ếch prét", "vneconomy": "vi en i cô nô mi",
    "pvcombank": "pê vê com banh", "vietcombank": "việt com banh", "techcombank": "tếch com banh", "vietinbank": "viết tin banh",
    "vpbank": "vê pê banh", "tpbank": "tê pê banh", "mbbank": "em bê banh", "mb": "em bê", "acb": "a xê bê", "bidv": "bê i đê vê",
    "agribank": "a gờ ri banh", "sacombank": "sa com banh", "hdbank": "hát đê banh", "vib": "vê i bê", "shb": "ét hát bê",
    "ocb": "o xê bê", "msb": "em ét bê", "seabank": "si banh", "shinhan": "sin han", "cake": "kếch", "timo": "ti mô",
    "momo": "mô mô", "zalopay": "da lô pây", "vnpay": "vê en pây", "mbs": "em bê ét", "ssi": "ét ét i", "vndirect": "vi en đai rếch",
    "vps": "vê pê ét", "hose": "hô xê", "hnx": "hát en ích", "vn-index": "vi en in đếch", "vnindex": "vi en in đếch",
    "grab": "gráp", "shopee": "sốp pi", "lazada": "la da đa", "tiki": "ti ki", "tiktok": "tích tốc", "youtube": "diu túp",
    "facebook": "phây búc", "zalo": "da lô", "google": "gu gồ", "iphone": "ai phôn", "samsung": "sam sung", "apple": "áp pồ",
    "vinfast": "vin phát", "vinhomes": "vin hôm", "vingroup": "vin grúp", "vinamilk": "vi na min", "viettel": "viết ten",
    "fpt": "ép pê tê", "chatgpt": "chát gi pi ti", "openai": "âu pần a i", "claude": "clốt", "canva": "can va", "capcut": "cáp cát",
    "evn": "e vê en", "ev": "i vi", "suv": "ét u vê", "toyota": "tô yô ta", "honda": "hon đa", "hyundai": "huyn đai",
    "kia": "ki a", "mazda": "mát đa", "ford": "pho", "tesla": "tét la", "byd": "bê i đi", "wifi": "wai phai", "ok": "ô kê",
}

UNIT = {  # đơn vị dính sau số (khoá viết thường)
    "%": "phần trăm", "đ": "đồng", "₫": "đồng", "vnd": "đồng", "vnđ": "đồng", "k": "nghìn", "tr": "triệu", "ty": "tỷ", "tỷ": "tỷ",
    "m²": "mét vuông", "m2": "mét vuông", "m³": "mét khối", "m3": "mét khối", "km²": "ki lô mét vuông", "km2": "ki lô mét vuông",
    "km": "ki lô mét", "m": "mét", "cm": "xen ti mét", "mm": "mi li mét", "ha": "héc ta", "kg": "ki lô gam", "g": "gam",
    "kwh": "ki lô oát giờ", "kw": "ki lô oát", "w": "oát", "mw": "mê ga oát", "km/h": "ki lô mét một giờ", "l": "lít", "ml": "mi li lít",
    "usd": "đô la", "$": "đô la", "h": "giờ", "p": "phút", "s": "giây", "x": "lần", "tuổi": "tuổi",
}


def _say3(n: int, full: bool) -> list[str]:
    h, t, u = n // 100, n // 10 % 10, n % 10
    out = []
    if h or full:
        out += [_DIG[h], "trăm"]
    if t == 0:
        if u and (h or full):
            out += ["linh", _DIG[u]]
        elif u:
            out += [_DIG[u]]
    elif t == 1:
        out += ["mười"] + ([{5: "lăm"}.get(u, _DIG[u])] if u else [])
    else:
        out += [_DIG[t], "mươi"] + ([{1: "mốt", 4: "tư", 5: "lăm"}.get(u, _DIG[u])] if u else [])
    return out


def say_int(n: int) -> str:
    """số nguyên → chữ đọc tự nhiên (2026 → hai nghìn không trăm hai mươi sáu, 25 → hai mươi lăm)."""
    if n == 0:
        return "không"
    if n < 0:
        return "âm " + say_int(-n)
    if n >= 10 ** 9:
        hi, lo = divmod(n, 10 ** 9)
        return say_int(hi) + " tỷ" + ((" " + _below_billion(lo, True)) if lo else "")
    return _below_billion(n, False)


def _below_billion(n: int, full: bool) -> str:
    out = []
    first = not full
    for div, unit in ((10 ** 6, "triệu"), (10 ** 3, "nghìn"), (1, "")):
        g = n // div % 1000
        if g:
            out += _say3(g, not first) + ([unit] if unit else [])
            first = False
        elif not first and div == 1:
            pass
    return " ".join(w for w in out if w)


def say_dec(intpart: str, frac: str | None) -> str:
    s = say_int(int(intpart.replace(".", "")))
    if frac:
        if len(frac) <= 2 and not frac.startswith("0"):
            s += " phẩy " + say_int(int(frac))
        else:
            s += " phẩy " + " ".join(_DIG[int(c)] for c in frac)
    return s


_NUM = r"\d{1,3}(?:\.\d{3})+|\d+"
_RE_DATE3 = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_RE_DATE2 = re.compile(r"^(\d{1,2})/(\d{1,2})$")
_RE_MY = re.compile(r"^(\d{1,2})/(\d{4})$")
_RE_TIME = re.compile(r"^(\d{1,2}):(\d{2})$")
_RE_RANGE = re.compile(rf"^({_NUM})(?:,(\d+))?\s*[–\-—]\s*({_NUM})(?:,(\d+))?(.*)$")
_RE_NUMU = re.compile(rf"^([$]?)({_NUM})(?:,(\d+))?(.*)$")


def _unit(u: str) -> str | None:
    u0 = u.strip()
    if not u0:
        return ""
    k = u0.lower()
    if k in UNIT:
        return UNIT[k]
    if "/" in k:                                             # "đ/kWh", "triệu/m²", "km/h"
        a, b = k.split("/", 1)
        ua = UNIT.get(a, WORDS.get(a, a)) if a else ""
        ub = UNIT.get(b, WORDS.get(b, b))
        return (ua + " " if ua else "") + "một " + ub
    return None


def _num_token(tok: str, prev: str) -> str | None:
    m = _RE_DATE3.match(tok)
    if m and 1 <= int(m.group(1)) <= 31 and 1 <= int(m.group(2)) <= 12:
        s = f"{say_int(int(m.group(1)))} tháng {say_int(int(m.group(2)))} năm {say_int(int(m.group(3)))}"
        return s if prev in ("ngày", "hôm") else "ngày " + s
    m = _RE_MY.match(tok)
    if m and 1 <= int(m.group(1)) <= 12:
        s = f"{say_int(int(m.group(1)))} năm {say_int(int(m.group(2)))}"
        return s if prev == "tháng" else "tháng " + s
    m = _RE_DATE2.match(tok)
    if m:
        d, mo = int(m.group(1)), int(m.group(2))
        if prev in ("ngày", "từ", "đến", "hôm", "tới", "trước", "sau") and 1 <= d <= 31 and 1 <= mo <= 12:
            return f"{say_int(d)} tháng {say_int(mo)}" if prev in ("ngày", "hôm") else f"ngày {say_int(d)} tháng {say_int(mo)}"
        return f"{say_int(d)} phần {say_int(mo)}"
    m = _RE_TIME.match(tok)
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return f"{say_int(int(m.group(1)))} giờ" + (f" {say_int(int(m.group(2)))}" if int(m.group(2)) else "")
    m = _RE_RANGE.match(tok)
    if m:
        u = _unit(m.group(5))
        if u is not None:
            return f"{say_dec(m.group(1), m.group(2))} đến {say_dec(m.group(3), m.group(4))}" + (f" {u}" if u else "")
    m = _RE_NUMU.match(tok)
    if m:
        cur, ip, fr, rest = m.groups()
        u = _unit(rest)
        if u is None:
            return None
        s = say_dec(ip, fr)
        if cur == "$":
            u = (u + " " if u else "") + "đô la"
        return s + (f" {u}" if u else "")
    return None


def _has_vi(w: str) -> bool:
    return any(ord(c) > 127 for c in w)


def _word(w: str) -> str | None:
    """từ chữ (không số) → cách đọc; None = giữ nguyên."""
    k = w.lower().replace(".", "") if w.count(".") and not w.lower().startswith("tp.") else w.lower()
    if k in WORDS:
        return WORDS[k]
    if len(k) >= 2 and k in UNIT and not k.isalpha() or k in ("kwh", "kw", "km", "km²", "km2", "m²", "m³", "kg", "cm", "mm", "ml", "usd", "vnd", "vnđ"):
        return UNIT[k]
    if "/" in w and not re.search(r"\d", w):               # "triệu/m²", "đ/kWh"
        a, _, b = w.partition("/")
        ra, rb = (_word(a) or a) if a else "", _unit(b) or _word(b) or b
        return (ra + " " if ra else "") + "một " + rb
    if w.lower() in WORDS:
        return WORDS[w.lower()]
    if _has_vi(w):
        return None
    if re.fullmatch(r"[A-Z]{2,5}", w):                      # chữ viết tắt in hoa → đánh vần kiểu Việt
        return " ".join(LETTER[c] for c in w.lower())
    m = re.fullmatch(r"([A-Z]{2,4})([a-z]{3,})", w)          # "VPcom" kiểu ghép: phần in hoa đánh vần
    if m:
        return " ".join(LETTER[c] for c in m.group(1).lower()) + " " + m.group(2)
    return None


_SYM = {"+": "cộng", "=": "bằng", "×": "nhân", "≈": "khoảng", "~": "khoảng", "→": "thành", "&": "và", "÷": "chia", "@": "a còng"}
_SPLIT = re.compile(r"(\s+)")


def tts_text(text: str) -> str:
    """câu kịch bản → lời đọc thuần chữ tiếng Việt cho TTS (giữ dấu câu để ngắt nghỉ)."""
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"(\d)\s*([–—])\s*(\d)", r"\1\2\3", text)          # "30 – 40%" → một token
    text = re.sub(r"(\d)\s+(%)", r"\1\2", text)
    out, prev = [], ""
    for part in _SPLIT.split(text):
        if not part or part.isspace():
            out.append(part)
            continue
        lead = re.match(r"^[\"“‘(\[«]*", part).group(0)
        trail = re.search(r"[\"”’)\]».,;:!?…]*$", part).group(0)
        core = part[len(lead):len(part) - len(trail)] if trail else part[len(lead):]
        if core.endswith(".") and _RE_NUMU.match(core[:-1] or "x"):
            core, trail = core[:-1], "." + trail
        rep = None
        if core in _SYM:
            rep = _SYM[core]
        elif re.search(r"\d", core):
            rep = _num_token(core, prev)
            if rep is None and "x" in core.lower():          # "x2", "2x"
                mm = re.fullmatch(r"[xX×](\d+(?:,\d+)?)|(\d+(?:,\d+)?)[xX×]", core)
                if mm:
                    v = mm.group(1) or mm.group(2)
                    a, _, b = v.partition(",")
                    rep = ("gấp " if mm.group(1) else "") + say_dec(a, b or None) + ("" if mm.group(1) else " lần")
            if rep is None:                                  # dãy có số lẫn chữ: đọc từng phần số
                rep = re.sub(rf"({_NUM})(?:,(\d+))?", lambda q: " " + say_dec(q.group(1), q.group(2)) + " ", core).strip()
                rep = re.sub(r"\s+", " ", rep.replace("/", " trên ").replace("-", " "))
        elif core:
            rep = _word(core)
            if rep is None and "-" in core and not _has_vi(core):
                rep = " ".join(_word(x) or x for x in core.split("-") if x)
        out.append(lead + (rep if rep is not None else core) + trail)
        prev = (core or "").lower()
    s = "".join(out)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def spoken_words(word: str) -> list[str]:
    """một từ kịch bản / chép lời → các từ đọc (chữ thường, bỏ dấu câu) — để so khớp."""
    t = tts_text(word).lower()
    return [x for x in re.split(r"[^\w]+", t) if x]
