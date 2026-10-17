"""Tra icon trong kho Uicons của app (≈3.500 icon solid-rounded) — tìm theo từ khóa tiếng Anh hoặc tiếng Việt.

    .venv/bin/python -m thagent.v2m icons yoga thiền      → danh sách tên icon dùng được
"""
from __future__ import annotations

import re
import unicodedata

# từ khóa tiếng Việt thường gặp → từ khóa tiếng Anh trong tên icon
VI = {
    "yoga": ["yoga", "meditation"], "thiền": ["meditation", "yoga"], "dưỡng sinh": ["meditation", "yoga", "leaf"],
    "sức khỏe": ["heart", "health", "medical"], "tập": ["gym", "running", "dumbbell"], "thể dục": ["gym", "running"],
    "nhà": ["house", "home"], "căn hộ": ["building", "apartment"], "đất": ["land", "map"], "bất động sản": ["house", "building", "key"],
    "tiền": ["money", "coins", "dollar", "wallet"], "giá": ["tags", "price", "dollar"], "lãi": ["percentage", "chart"],
    "ngân hàng": ["bank"], "vàng": ["coins", "gold"], "đầu tư": ["chart-line-up", "sack-dollar"], "thuê": ["key", "handshake"],
    "hợp đồng": ["file-signature", "handshake", "document"], "khách": ["users", "user"], "người": ["user", "users", "person"],
    "doanh nghiệp": ["briefcase", "building"], "văn phòng": ["briefcase", "building"], "cửa hàng": ["shop", "store"],
    "cà phê": ["coffee"], "ăn": ["utensils", "restaurant"], "đường": ["road"], "xe": ["car", "bus"], "cầu": ["bridge"],
    "trường": ["school", "graduation-cap"], "học": ["book", "graduation-cap", "school"], "bệnh viện": ["hospital"],
    "thuốc": ["medicine", "pills", "capsules"], "bác sĩ": ["doctor", "user-md", "stethoscope"], "làm đẹp": ["spa", "lipstick", "sparkles"],
    "da": ["face", "spa"], "thời gian": ["clock", "hourglass", "calendar"], "lịch": ["calendar"], "tăng": ["arrow-trend-up", "chart-line-up"],
    "giảm": ["arrow-trend-down"], "an toàn": ["shield-check"], "vị trí": ["marker", "map-marker", "location"],
    "bản đồ": ["map"], "thế giới": ["globe", "earth"], "điện thoại": ["mobile", "phone"], "máy tính": ["computer", "laptop"],
}


def _all() -> list[str]:
    from ..neon import _uicons_map
    return sorted(_uicons_map())


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.lower().strip())


def search(*queries: str, limit: int = 24) -> list[str]:
    """tên icon khớp từ khóa (tiếng Anh hoặc tiếng Việt), ưu tiên khớp nguyên từ, tên ngắn."""
    names = _all()
    terms = []
    q = _norm(" ".join(queries))
    for vi, en in sorted(VI.items(), key=lambda kv: -len(kv[0])):
        if vi in q:
            terms += en
            q = q.replace(vi, " ")
    terms += [t for t in re.split(r"[\s,]+", q) if t]
    out = []
    for t in terms:
        hit = [n for n in names if t in n.split("-")] + [n for n in names if t in n and t not in n.split("-")]
        for n in sorted(hit[:60], key=lambda n: (t not in n.split("-"), len(n))):
            if n not in out:
                out.append(n)
    return out[:limit]


def suggest(name: str, limit: int = 6) -> list[str]:
    """gợi ý tên đúng cho một tên icon không có trong kho."""
    parts = [p for p in re.split(r"[-_\s]+", _norm(name)) if p]
    return search(*parts, limit=limit) if parts else []
