"""Review Editor — quy tắc RIÊNG từng lĩnh vực (references/niches.md). Lĩnh vực đặt ở edit["category"], đoạn có thể ghi đè bằng s["category"]
(một video nhiều ngành). apply() chạy khi nạp edit.json; người dựng ghi rõ giá trị trong edit thì giữ nguyên.

- bds        Bất động sản: như cũ (ngược sáng → nâng vùng tối nhẹ).
- cong_nghe  Công nghệ: thông số → stat; so sánh → khối "compare" (2 cột); quay màn hình → cutaway/PiP; không tự bịa kết quả đo.
- my_pham    Mỹ phẩm – skincare: KHOÁ MÀU (không nâng sáng, không chỉnh ấm — giữ đúng tông da, màu son/kem);
             check: chữ trên hình hứa hẹn công dụng mà lời không nói → lỗi; lời có khẳng định công dụng mạnh → cảnh báo.
- am_thuc    Ẩm thực: tiếng hiện trường của cảnh minh hoạ (xèo xèo, rót, cắn giòn) giữ nhỏ dưới lời (−18 dB);
             màu ấm nhẹ trung thực (không đổi màu món).
- san_pham   Sản phẩm / đồ dùng khác: mặc định chung.
"""
from __future__ import annotations

import re
import unicodedata

NAMES = {"bds": "Bất động sản", "cong_nghe": "Công nghệ", "my_pham": "Mỹ phẩm – skincare", "am_thuc": "Ẩm thực", "san_pham": "Sản phẩm khác"}
FOOD_NAT_DB = -18.0
FOOD_WARM = 0.04

# cụm hứa hẹn công dụng (quảng cáo mỹ phẩm có quy định) — chỉ được lên hình khi chính người nói nói ra, và vẫn cảnh báo để kiểm căn cứ
CLAIMS = [r"trị (dứt điểm |hết )?mụn", r"hết mụn", r"sạch mụn", r"trắng (da|sáng)", r"làm trắng", r"đặc trị", r"điều trị", r"chữa",
          r"xoá nám", r"xóa nám", r"trị nám", r"hết nám", r"mờ nám", r"trẻ hoá|trẻ hóa", r"xoá nhăn|xóa nhăn", r"hết thâm", r"cam kết",
          r"hiệu quả 100", r"100 ?%", r"sau \d+ ngày", r"vĩnh viễn", r"tái tạo da", r"thần kỳ|thần thánh", r"an toàn tuyệt đối"]


def _n(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower())


def cat(edit: dict, s: dict) -> str:
    c = s.get("category") or edit.get("category") or "san_pham"
    return c if c in NAMES else "san_pham"


def apply(edit: dict) -> dict:
    for s in edit.get("segments", []):
        c = cat(edit, s)
        if c == "my_pham":
            s.setdefault("tone", {}).setdefault("lift", 0)
            s["tone"].setdefault("warm", 0)
            for cw in s.get("cutaways", []):
                cw.setdefault("tone", {}).setdefault("lift", 0)
                cw["tone"].setdefault("warm", 0)
        elif c == "am_thuc":
            s.setdefault("tone", {}).setdefault("warm", FOOD_WARM)
            for cw in s.get("cutaways", []):
                cw.setdefault("tone", {}).setdefault("warm", FOOD_WARM)
                if cw.get("audio") != "mute":
                    cw.setdefault("nat_db", FOOD_NAT_DB)
    return edit


def claims(text: str) -> list[str]:
    t = _n(text)
    return [m.group(0) for p in CLAIMS for m in [re.search(p, t)] if m]


def check(edit: dict, pdir) -> list[tuple[str, str]]:
    from .edit import layout, words_out
    out = []
    ws = words_out(edit, pdir)
    for s in layout(edit):
        if cat(edit, s) != "my_pham":
            continue
        said = _n(" ".join(w["text"] for w in ws if s["t0"] - 0.01 <= w["t"] < s["t1"]))
        for t in s.get("texts", []):
            txt = " ".join(str(t.get(k, "")) for k in ("text", "sub", "label", "unit", "title"))
            for c in claims(txt):
                if c not in said:
                    out.append(("error", f"{s['id']}: chữ trên hình “{c}” là hứa hẹn công dụng mà người nói KHÔNG nói — bỏ (mỹ phẩm không tự thêm công dụng)"))
        for c in sorted(set(claims(said))):
            out.append(("warn", f"{s['id']}: lời có khẳng định công dụng “{c}” — cần căn cứ (giấy phép/công bố); ghi vào báo cáo, không nhấn thêm trên hình"))
    return out
