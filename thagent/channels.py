"""Kênh = lĩnh vực chính. Mỗi kênh 5 nền Motion Graphics (assets/backgrounds/<id>/nen-1..5.png),
cứ EVERY video xuất lần đầu thì đổi sang nền kế tiếp, xoay vòng. Bộ đếm lưu ở ccut_channels.json (riêng C-Cut)."""
from __future__ import annotations

import json
import threading

from .paths import ROOT

CHANNELS = [("bat-dong-san", "Bất động sản"), ("suc-khoe", "Sức khỏe"), ("giao-duc", "Giáo dục"),
            ("chia-se", "Chia sẻ"), ("lam-dep", "Làm đẹp"), ("fnb", "F&B")]
NAMES = dict(CHANNELS)
EVERY, N_BG = 15, 5
BG_DIR = ROOT / "assets" / "backgrounds"
COUNT_FILE = ROOT / "ccut_channels.json"
_LOCK = threading.Lock()


def counts() -> dict:
    try:
        return json.loads(COUNT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def bg_path(ch: str, n: int):
    """nền số n (1..5) của kênh ch, None nếu không có."""
    p = BG_DIR / ch / f"nen-{n}.png"
    return p if p.exists() else None


def current(ch: str) -> int:
    """số nền (1..5) kênh đang dùng theo số video đã xuất."""
    return counts().get(ch, 0) // EVERY % N_BG + 1


def bump(ch: str) -> int:
    """+1 video đã xuất cho kênh; trả về số đếm mới."""
    if ch not in NAMES:
        return 0
    with _LOCK:
        c = counts()
        c[ch] = c.get(ch, 0) + 1
        COUNT_FILE.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding="utf-8")
        return c[ch]


def summary() -> list[dict]:
    c = counts()
    out = []
    for ch, name in CHANNELS:
        n = c.get(ch, 0)
        out.append({"id": ch, "name": name, "exported": n, "current": n // EVERY % N_BG + 1,
                    "left": EVERY - n % EVERY, "bgs": [k for k in range(1, N_BG + 1) if bg_path(ch, k)]})
    return out
