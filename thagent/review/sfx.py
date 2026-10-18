"""Review Editor — SFX theo bộ ĐÃ DUYỆT của Talking Head (assets/sfx, style.json → sfx): tiết chế, dịu tai.

Tự sinh từ bản dựng (tắt: "sfx": false; thêm tay: "sfx_events": [{"t": giây xuất, "role": "soft"}]):
- stat (số liệu), emph (chữ nhấn), label (nhãn sản phẩm) → âm nhẹ “soft” (pluck tròn / notification mềm / nút bo tròn), xoay vòng không lặp liền;
- diagram mở → flash (như chuyển cảnh của Talking Head); KHÔNG âm cho nút sơ đồ, spotlight, vòng nhấn, zoom (Talking Head: không whoosh).
- role "money" chỉ khi thêm tay, tối đa 1 lần/video.
Lọc: âm nhẹ cách nhau ≥ 10 khung (0,33s); đỉnh âm đặt đúng khoảnh khắc hiện; đỉnh chuẩn theo norm_db của kho.
"""
from __future__ import annotations

import json

from .edit import layout
from ..paths import ROOT

KIT = ROOT / "assets" / "sfx"
POOL = {"soft": (["soft_00", "soft_01", "soft_02"], -16), "flash": (["u_flash"], -12), "money": (["u_money"], -13)}
GAIN = {"stat": -16, "emph": -17, "label": -18, "compare": -17}


def events(edit: dict) -> list[dict]:
    if edit.get("sfx") is False:
        return []
    ev = []
    for s in layout(edit):
        for t in s.get("texts", []):
            at = s["t0"] + float(t["at"])
            r = t.get("role")
            if r in GAIN:
                ev.append({"t": at + 0.06, "role": "soft", "gain_db": GAIN[r]})
            elif r == "diagram":
                ev.append({"t": at + 0.05, "role": "flash", "gain_db": -12})
    ev += [dict(e) for e in edit.get("sfx_events", [])]
    ev.sort(key=lambda e: e["t"])
    out, last, money = [], -9.0, 0
    for e in ev:
        if e["role"] == "money":
            money += 1
            if money > 1:
                continue
        if e["t"] - last < 0.33:
            continue
        out.append(e); last = e["t"]
    return out


def inputs(edit: dict) -> list[dict]:
    """sự kiện → file âm + độ trễ (đỉnh âm đúng t) + gain (kể cả norm_db của kho)."""
    man = json.loads((KIT / "manifest.json").read_text(encoding="utf-8"))
    cnt, out = {}, []
    for e in events(edit):
        names, g0 = POOL.get(e["role"], POOL["soft"])
        k = cnt.get(e["role"], 0)
        cnt[e["role"]] = k + 1
        m = man.get(names[k % len(names)])
        if not m:
            continue
        out.append({"path": str(KIT / m["file"]), "start": max(e["t"] - m.get("peak_offset_ms", 0) / 1000, 0.0),
                    "gain_db": e.get("gain_db", g0) + m.get("norm_db", 0), "role": e["role"], "t": round(e["t"], 2)})
    return out
