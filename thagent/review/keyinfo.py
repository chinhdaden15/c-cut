"""Review Editor — tìm SỐ LIỆU / THÔNG TIN THEN CHỐT trong lời (để làm nổi bật trên hình, không chỉ nằm trong phụ đề).

detect(edit, pdir) → [{t, t_end, text, value, unit, seg}] trên timeline xuất:
số (chữ số hoặc số đọc thành chữ) + đơn vị đi kèm (năm, tỷ, triệu, đô la, USD, %, m², tầng, phòng ngủ, ha, lần, tháng, phút…),
khoảng “từ 3 đến 5 lần”. Kiểm (check) cảnh báo số liệu được nói mà không có khối stat/info/emph chứa số đó lúc nói.
"""
from __future__ import annotations

import re
import unicodedata

from .edit import layout, words_out

NUMW = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5, "sáu": 6, "bảy": 7, "tám": 8, "chín": 9, "mười": 10, "trăm": 100}
UNITS = ["tỷ", "triệu", "nghìn", "ngàn", "đô", "la", "mỹ", "usd", "đồng", "vnđ", "%", "phần", "trăm", "năm", "tháng", "ngày", "tuần",
         "m2", "m²", "mét", "vuông", "km", "ha", "hecta", "héc", "ta", "tầng", "lầu", "phòng", "ngủ", "wc", "căn", "lần", "người", "dự", "án",
         "sản", "phẩm", "giờ", "phút", "giây", "gb", "tb", "mah", "inch", "ml", "kg", "gram", "lít", "chiếc", "sao", "điểm"]


def _n(s):
    return unicodedata.normalize("NFC", s.lower()).strip(".,!?;:…“”\"()")


def _num(tok: str):
    t = _n(tok).replace(",", ".")
    if re.fullmatch(r"\d+(\.\d+)?", t):
        return float(t)
    return None


def detect(edit: dict, pdir) -> list[dict]:
    ws = words_out(edit, pdir)
    out, i = [], 0
    while i < len(ws):
        v = _num(ws[i]["text"])
        if v is None:
            i += 1; continue
        j = i + 1
        # khoảng “3 đến 5”, “3-5”
        if j + 1 < len(ws) and _n(ws[j]["text"]) in ("đến", "tới", "-", "–") and _num(ws[j + 1]["text"]) is not None:
            j += 2
        units = []
        while j < len(ws) and _n(ws[j]["text"]) in UNITS and len(units) < 4 and ws[j]["seg"] == ws[i]["seg"]:
            units.append(ws[j]["text"].strip(".,")); j += 1
        if units or v >= 10:
            text = " ".join(w["text"].strip(".,") for w in ws[i:j])
            lead = ws[i - 1]["text"] if i and _n(ws[i - 1]["text"]) in ("từ", "khoảng", "hơn", "gần", "trên", "dưới", "chỉ") else ""
            out.append({"t": ws[i]["t"], "t_end": ws[j - 1]["t_end"], "text": (lead + " " + text).strip(), "value": v,
                        "unit": " ".join(units), "seg": ws[i]["seg"]})
        i = max(j, i + 1)
    return out


def _vals(txt: str, unit: str = "") -> set:
    """giá trị số kiểu Việt: “6,7” = 6.7; “350.000” = 350000 (và 350); “350 nghìn” = 350000."""
    out = set()
    for tok in re.findall(r"\d+(?:[.,]\d+)*", txt):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", tok):
            v = float(tok.replace(".", "")); out |= {v, float(tok.split(".")[0])}
        else:
            v = float(tok.replace(",", ".")) if tok.count(",") + tok.count(".") <= 1 else float(re.sub(r"[.,]", "", tok))
            out.add(round(v, 4))
            if re.search(r"nghìn|ngàn", unit): out.add(v * 1000)
    return out


def coverage(edit: dict, pdir) -> list[tuple[str, str]]:
    """số liệu được nói mà hình không làm nổi bật (khối stat/info/emph có chữ số đó trong khoảng nói)."""
    segs = layout(edit)
    shown = []
    for s in segs:
        for t in s.get("texts", []):
            if t.get("role") in ("stat", "info", "emph", "compare"):
                txt = " ".join(str(t.get(k, "")) for k in ("text", "value", "unit", "label", "sub")) + " " + \
                      " ".join(str(x) for r in t.get("rows", []) for x in r)
                a = s["t0"] + float(t["at"])
                shown.append((a, a + float(t.get("dur", 2.5)), _vals(txt, str(t.get("unit", "")))))
    out = []
    for k in detect(edit, pdir):
        digits = _vals(k["text"], k.get("unit", ""))
        if not any(a - 0.6 <= k["t"] <= b and digits & ds for a, b, ds in shown):
            out.append(("warn", f"số liệu “{k['text']}” ở {k['t']:.1f}s chỉ có trong phụ đề — làm nổi bật (role stat/info) nếu là thông tin then chốt"))
    return out
