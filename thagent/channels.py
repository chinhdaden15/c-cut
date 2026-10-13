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


# ---------------- kênh của từng video (<dự án>/channel.json) ----------------
SWAP = {"lam-dep", "fnb"}     # nền hồng/cam làm thẻ vàng chìm → đổi vàng ↔ xanh lúc vẽ MG
CFG = "channel.json"


def info(pdir) -> dict:
    """{"channel": id|"", "bg": "<id>/nen-n.png"|"", "source": "user"|"claude"|"", "counted": id}"""
    try:
        return json.loads((pdir / CFG).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write(pdir, d: dict):
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / CFG).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def assign(pdir, ch: str, source: str) -> dict:
    """Gán kênh cho video. Nền khóa ngay lúc gán (xuất lại vẫn giữ nền đó); đổi sang kênh khác thì khóa nền mới.
    Claude không ghi đè kênh người dùng đã chọn."""
    d = info(pdir)
    if source == "claude" and d.get("source") == "user":
        return d
    ch = ch if ch in NAMES else ""
    if d.get("channel") != ch or "bg" not in d:
        n = current(ch) if ch else 0
        d.update(channel=ch, bg=f"{ch}/nen-{n}.png" if ch and bg_path(ch, n) else "")
    d["source"] = source
    _write(pdir, d)
    return d


def release(pdir):
    """người dùng chuyển về “Tự nhận” → Claude được gán lại (giữ kênh/nền đang có nếu Claude không đổi)."""
    d = info(pdir)
    if d.get("source") == "user":
        d["source"] = ""
        _write(pdir, d)


def theme(mg_segments: list[dict], pdir):
    """áp nền + màu thẻ theo kênh vào các đoạn MG (không có kênh → nền xanh mặc định)."""
    d = info(pdir)
    for s in mg_segments:
        s["bg"] = d.get("bg") or None
        s["swap"] = d.get("channel") in SWAP


def exported(pdir):
    """gọi sau khi xuất xong: lần xuất đầu của video → +1 bộ đếm kênh (xuất lại không đếm)."""
    d = info(pdir)
    ch = d.get("channel")
    if ch and not d.get("counted"):          # đổi kênh rồi xuất lại cũng không đếm thêm
        bump(ch)
        d["counted"] = ch
        _write(pdir, d)
