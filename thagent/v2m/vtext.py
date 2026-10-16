"""Ngắt dòng theo ngữ nghĩa tiếng Việt (chốt MỘT lần ở cỡ chữ gốc, trước khi animate).

Không giao cho cơ chế tự xuống dòng theo chiều rộng: chọn điểm ngắt bằng quy hoạch động với
- ràng buộc: mỗi dòng ≤ max_w (đo bằng font thật, có tính khoảng cách chữ);
- phạt nặng: ngắt trong cụm cần giữ liền (keep, từ khoá highlight, tên riêng viết hoa liên tiếp, số + đơn vị),
  ngắt ngay SAU từ chỉ quan hệ/định lượng (của, các, những, một, mỗi, từng, với, và, cho, về, …);
- phạt: dòng cuối chỉ một từ ngắn (mồ côi), chênh lệch độ dài các dòng;
- thưởng nhẹ: ngắt TRƯỚC giới từ/liên từ (về, cho, với, để, khi, nếu, nhưng, …).
"\\n" trong chữ = ngắt chủ động của người dựng (giữ nguyên, chỉ chia tiếp nếu dòng đó vẫn quá dài).
"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from . import draw as D

# từ gắn với phần đứng SAU nó → không ngắt ngay sau
BIND_NEXT = {"của", "các", "những", "một", "mỗi", "từng", "mọi", "cái", "con", "chiếc", "với", "và", "cho", "về", "để", "từ",
             "khi", "nếu", "mà", "thì", "là", "nhưng", "hoặc", "trong", "ở", "đến", "sang", "qua", "tại", "theo", "bởi", "vì",
             "nên", "rồi", "hay", "bằng", "như", "rất", "quá", "không", "chưa", "đã", "đang", "sẽ", "được", "bị", "có", "nhà", "thành",
             "cao", "đường", "cầu", "nút", "quốc", "tỉnh", "lãi", "giá", "tỷ", "nhu", "thói", "sức", "chăm", "giáo", "cuộc", "dưỡng"}
# từ mở đầu một cụm mới → ngắt TRƯỚC nó là tự nhiên
BREAK_BEFORE = {"về", "cho", "với", "để", "khi", "nếu", "nhưng", "hoặc", "mà", "thì", "vì", "nên", "rồi", "trong", "tại", "sang",
                "qua", "đến", "từ", "theo", "bởi", "và", "hay", "là"}
# “sẽ/đã/đang/không” đứng cuối dòng trước động từ vẫn chấp nhận được (vd “Hôm nay chúng ta sẽ / nói về tích phân”)
SOFT_BIND = {"sẽ", "đã", "đang", "không", "chưa", "được", "có", "là", "rất"}
# từ ghép 2–3 âm tiết hay gặp — không ngắt bên trong (planner bổ sung thuật ngữ riêng qua `keep`)
COMPOUNDS = {tuple(x.split()) for x in """chúng ta|chúng tôi|chúng mình|các bạn|hôm nay|ngày mai|hôm qua|bây giờ|hiện nay|thời gian|thời điểm|
thành phố|việt nam|trung quốc|ấn độ|hoa kỳ|nước mỹ|châu á|thế giới|toàn cầu|kinh tế|thị trường|giá vàng|lãi suất|lợi suất|tỷ giá|
cung cầu|lạm phát|chính sách|đô la|đồng đô la|nhà đầu tư|người mua|người bán|cao tốc|đường bộ|giao thông|nút giao|quốc lộ|tuyến đường|
cửa ngõ|trung tâm|miền tây|miền đông|đồng bằng|sông cửu long|kết nối|mạng lưới|hành trình|tích phân|đạo hàm|bất động sản|căn hộ|
không gian|ánh sáng|thông thoáng|sinh hoạt|chi phí|giá mua|phí quản lý|nội thất|trả góp|nhu cầu|lựa chọn|quyết định|vị trí|
sức khỏe|sức khoẻ|cơ thể|bản thân|chính mình|gia đình|công việc|yêu thương|vận động|nhẹ nhàng|thả lỏng|lắng nghe|nhịp thở|động tác|
thói quen|chăm sóc|dưỡng sinh|đông phương|giáo viên|hướng dẫn|đồng hành|tập luyện|chứng nhận|hoàn thành|tích lũy|quà tặng|
thân khỏe|tâm an|an vui|khỏe mạnh|cá độ|nhà cái|người chơi|pháp luật|vi phạm|vòng lặp|nợ nần|vay nóng|vận may|người trẻ|điện thoại""".replace("\n", "").split("|")}
UNIT = re.compile(r"^(%|‰|tỷ|tỉ|triệu|nghìn|ngàn|km|m|m2|m²|ha|kg|g|usd|đ|đồng|năm|tháng|ngày|giờ|phút|giây|lần|người|căn|tầng|"
                  r"phòng|điểm|bậc|độ|°c?)[.,;:!?]?$", re.I)
NUM = re.compile(r"^[+\-−~≈]?\d[\d.,]*%?$")


def _norm(w: str) -> str:
    return unicodedata.normalize("NFC", w).lower().strip(".,;:!?“”\"'()…–-")


def _protected_pairs(words: list[str], keep: tuple[str, ...]) -> set[int]:
    """chỉ số i: KHÔNG ngắt giữa words[i] và words[i+1]."""
    no = set()
    lw = [_norm(w) for w in words]
    letters = [c for w in words for c in w if c.isalpha()]
    all_caps = letters and sum(c.isupper() for c in letters) / len(letters) > 0.8   # chữ in hoa toàn bộ: không suy tên riêng từ chữ hoa
    for ph in keep:
        k = [_norm(x) for x in ph.split()]
        for i in range(len(lw) - len(k) + 1):
            if lw[i:i + len(k)] == k:
                no.update(range(i, i + len(k) - 1))
    for i in range(len(lw)):
        for L in (3, 2):
            if tuple(lw[i:i + L]) in COMPOUNDS:
                no.update(range(i, i + L - 1))
    for i in range(len(words) - 1):
        a, b = words[i], words[i + 1]
        if NUM.match(a.strip(".,;:")) and (UNIT.match(_norm(b)) or NUM.match(b)):
            no.add(i)                                   # 4 tỷ · 10,4 % · 15 tháng 10
        if not all_caps and a[:1].isupper() and b[:1].isupper() and not a.endswith((".", ",", ":", ";", "?", "!")) and i > 0 \
                and b not in ("–", "-", "—") and a not in ("–", "-", "—"):
            no.add(i)                                   # tên riêng: Hồ Chí Minh, Long Thành (bỏ chữ hoa đầu câu)
        if b in ("–", "-", "—"):
            no.add(i)                                   # không mở dòng mới bằng gạch nối; ngắt SAU gạch nối thì được
    return no


@lru_cache(maxsize=2048)
def break_lines(text: str, role: str, size: int, max_w: float, keep: tuple[str, ...] = (), allow_orphan: bool = False) -> tuple[str, ...]:
    """→ các dòng đã chốt. max_w ≤ 0 → chỉ theo “\\n” chủ động."""
    text = unicodedata.normalize("NFC", text)
    out: list[str] = []
    for para in text.split("\n"):
        words = para.split()
        if not words:
            continue
        if max_w <= 0:
            out.append(" ".join(words))
            continue
        out += _dp(words, role, size, max_w, keep, allow_orphan)
    return tuple(out)


def _dp(words, role, size, max_w, keep, allow_orphan):
    f = D.font(role, size)
    sp = f.getlength(" ")
    wl = [f.getlength(w) for w in words]
    n = len(words)
    no = _protected_pairs(words, keep)
    lw = [_norm(w) for w in words]
    INF = float("inf")
    best = [INF] * (n + 1)
    prev = [0] * (n + 1)
    best[0] = 0.0
    total = sum(wl) + sp * (n - 1)
    nlines_min = max(1, int(total // max_w) + 1)
    target = min(max_w, total / nlines_min + sp)
    for j in range(1, n + 1):           # dòng = words[i:j]
        width = -sp
        for i in range(j - 1, -1, -1):
            width += wl[i] + sp
            if width > max_w and j - i > 1:
                break
            if best[i] == INF:
                continue
            cost = 60.0                                   # mỗi dòng thêm có giá → ít dòng nhất có thể
            last = j == n
            slack = (target - width) / max(target, 1)
            cost += (slack ** 2) * (30 if not last else 12)
            if width > max_w:
                cost += 1e6                               # một từ dài hơn khung: buộc chấp nhận
            if j < n:                                     # điểm ngắt sau words[j-1]
                if (j - 1) in no:
                    cost += 400
                a, b = lw[j - 1], lw[j]
                if a in BIND_NEXT and a not in SOFT_BIND:
                    cost += 45
                elif a in SOFT_BIND:
                    cost += 8
                if b in BREAK_BEFORE:
                    cost -= 6
                if b in ("sẽ", "đã", "đang", "được", "bị"):
                    cost += 20                            # trợ từ gắn với động từ sau, nhưng tách khỏi chủ ngữ trước thì gượng
                if a in ("–", "-", "—"):
                    cost -= 10                            # ngắt sau gạch nối giữa hai tên
                if words[j - 1].endswith((",", ";", ":")):
                    cost -= 14                            # ngắt sau dấu phẩy là tự nhiên
                if words[j - 1].endswith((".", "?", "!")):
                    cost -= 20
            if not last and j - i == 1 and n > 2 and not allow_orphan:
                cost += 70                                # dòng giữa chỉ một từ (vd “PHẢI”) cũng là lẻ
            if last and i > 0 and j - i == 1 and not allow_orphan:
                cost += 250 if len(lw[i]) <= 5 else 120  # dòng cuối mồ côi một từ
            if best[i] + cost < best[j]:
                best[j], prev[j] = best[i] + cost, i
    lines, j = [], n
    while j > 0:
        i = prev[j]
        lines.append(" ".join(words[i:j]))
        j = i
    return lines[::-1]


def layout_issues(text: str, role: str, size: int, max_w: float, keep=()) -> list[str]:
    """cảnh báo sau khi đã ngắt: mồ côi, vỡ cụm bắt buộc (khi không còn cách khác)."""
    lines = break_lines(text, role, int(size), float(max_w or 0), tuple(keep))
    issues = []
    if len(lines) > 1 and len(lines[-1].split()) == 1 and len(_norm(lines[-1])) <= 5 and "\n" not in text:
        issues.append(f"dòng cuối mồ côi “{lines[-1]}”")
    f = D.font(role, int(size))
    if max_w and any(f.getlength(l) > max_w + 1 for l in lines):
        issues.append("có dòng dài hơn max_w (từ quá dài)")
    words = " ".join(lines).split()
    no, off = set(), 0                        # xét cụm cần giữ theo TỪNG đoạn (in hoa/thường riêng)
    for para in unicodedata.normalize("NFC", text).split("\n"):
        pw = para.split()
        no |= {off + i for i in _protected_pairs(pw, tuple(keep))}
        off += len(pw)
    idx, cuts = 0, set()
    manual, k = set(), 0                      # chỗ xuống dòng chủ động (\n) là quyết định của người dựng → không báo
    for para in text.split("\n")[:-1]:
        k += len(para.split()); manual.add(k - 1)
    for l in lines[:-1]:
        idx += len(l.split())
        if idx - 1 not in manual:
            cuts.add(idx - 1)
    bad = sorted(no & cuts)
    if bad:
        issues.append("ngắt giữa cụm cần giữ liền: " + ", ".join(f"“{words[i]} / {words[i + 1]}”" for i in bad))
    return issues
