"""Review Editor — điểm nối theo NHỊP NÓI TỰ NHIÊN (audio gốc + transcript + đường năng lượng).

Mốc từ của máy chép lời có thể lệch, nhất là âm cuối và tiếng nói nhỏ → không cắt sát mốc từ. Mỗi đoạn nói:
- đầu: giữ đệm trước tiếng nói ~80–150ms (nới thêm nếu năng lượng cho thấy phụ âm đầu bắt đầu sớm hơn mốc), không lấn từ trước;
- cuối: giữ đệm sau ~150–300ms (nới tới khi năng lượng tắt, tối đa 0,4s) để không mất đuôi từ/hơi thở, không lấn từ sau;
- khoảng nghỉ ở điểm nối = đệm cuối đoạn trước + đệm đầu đoạn sau, đều là ROOM TONE thật của nguồn (không chèn lặng số, không kéo giãn).
Mục tiêu nghỉ: giữa ý ~0,2–0,4s, chuyển ý lớn ~0,4–0,65s (đoạn ghi "pause": "lon"). Không cộng dồn máy móc.

- junctions(edit, pdir)  → báo cáo từng điểm nối (đệm, nghỉ, còn tiếng ở điểm cắt) + cờ lỗi
- refine(edit, pdir)     → edit mới với in/out đã nới theo quy tắc trên (dời theo các mốc at của chữ/cutaway/reframe)
- sheet(edit, pdir)      → review/joins.jpg: waveform 1s trước + 1s sau mỗi điểm nối, mốc từ, vạch cắt (soát bằng mắt — KHÔNG thay việc nghe)
"""
from __future__ import annotations

import copy
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np

from .edit import layout, media

PRE, PRE_MAX = 0.12, 0.20          # đệm trước tiếng nói (mục tiêu / tối đa khi năng lượng cho thấy tiếng bắt đầu sớm)
POST, POST_MAX = 0.22, 0.40        # đệm sau tiếng nói
GAP_MIN, GAP_MAX = 0.20, 0.80      # khoảng nghỉ ở điểm nối (giữa ý) — dưới: dồn câu; trên: hụt nhịp
GAP_BIG = (0.40, 0.65)             # chuyển ý lớn ("pause": "lon")


@lru_cache(maxsize=16)
def _env(path: str) -> tuple[np.ndarray, float]:
    """đường năng lượng 10ms (dB) + nền lặng (phân vị 10)."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    if a.size == 0:
        return np.zeros(1), 0.0
    db = 20 * np.log10(np.sqrt(np.convolve(a ** 2, np.ones(80) / 80, mode="same")[::80]) + 1e-6)
    return db, float(np.percentile(db, 10))


def _voiced(path: str, t: float, thr: float = 6.0) -> bool:
    db, fl = _env(path)
    k = int(round(t * 100))
    return 0 <= k < len(db) and db[k] > fl + thr


def _words_in(m: dict, a: float, b: float):
    ws = m.get("words", [])
    idx = [i for i, w in enumerate(ws) if w["end"] > a + 0.03 and w["start"] < b - 0.03]
    if not idx:
        return None, None, None, None
    i0, i1 = idx[0], idx[-1]
    return ws[i0], ws[i1], (ws[i0 - 1] if i0 > 0 else None), (ws[i1 + 1] if i1 + 1 < len(ws) else None)


def bounds(m: dict, a: float, b: float) -> tuple[float, float, dict]:
    """in/out khuyến nghị cho đoạn nói [a, b] (giây nguồn)."""
    first, last, prev, nxt = _words_in(m, a, b)
    if not first:
        return a, b, {}
    p = m["path"]
    k = first["start"]
    while k - 0.01 >= first["start"] - PRE_MAX and _voiced(p, k - 0.01):      # phụ âm đầu bắt đầu sớm hơn mốc
        k -= 0.01
    new_in = min(first["start"] - PRE, k - 0.04)
    new_in = max(new_in, (prev["end"] + 0.04) if prev else 0.0, 0.0)
    k = last["end"]
    while k + 0.01 <= last["end"] + POST_MAX and _voiced(p, k):              # đuôi từ / hơi thở còn sau mốc
        k += 0.01
    new_out = max(last["end"] + POST, k + 0.05)
    new_out = min(new_out, (nxt["start"] - 0.04) if nxt else m["duration"], m["duration"])
    db, fl = _env(p)
    if nxt and nxt["start"] - last["end"] < POST_MAX + 0.25:
        # từ kế nằm sát: cắt ở chỗ LẶNG NHẤT giữa hai từ (tránh dính đầu từ của câu bị bỏ, mốc từ có thể lệch)
        a_, b_ = int((last["end"] + 0.1) * 100), int(max(nxt["start"] - 0.02, last["end"] + 0.11) * 100)
        if b_ > a_ + 2 and b_ <= len(db):
            win = np.convolve(db[a_:b_], np.ones(5) / 5, mode="same")
            new_out = round((a_ + int(np.argmin(win))) / 100, 3)
    if prev and first["start"] - prev["end"] < PRE_MAX + 0.25:
        a_, b_ = int((prev["end"] + 0.02) * 100), int((first["start"] - 0.06) * 100)
        if b_ > a_ + 2 and b_ <= len(db):
            win = np.convolve(db[a_:b_], np.ones(5) / 5, mode="same")
            new_in = round((a_ + int(np.argmin(win))) / 100, 3)
    return round(new_in, 3), round(new_out, 3), {"first": first, "last": last, "prev": prev, "next": nxt}


def junctions(edit: dict, pdir) -> list[dict]:
    M = media(pdir)
    segs = layout(edit)
    out = []
    for i, s in enumerate(segs):
        if s.get("role", "talk") != "talk":
            continue
        m = M[s["src"]]
        first, last, _, _ = _words_in(m, float(s["in"]), float(s["out"]))
        if not first:
            continue
        head = first["start"] - float(s["in"])
        tail = float(s["out"]) - last["end"]
        prev = segs[i - 1] if i else None
        rec = {"seg": s["id"], "t_out": round(s["t0"], 2), "head": round(head, 3), "tail": round(tail, 3),
               "first": first["text"], "last": last["text"], "flags": []}
        if s.get("inner") and prev is not None and prev.get("group") == s.get("group"):
            out.append(rec); continue          # chỗ Cắt sạch bỏ khoảng lặng/từ đệm bên trong câu (đo bằng sóng âm) — không chấm theo mốc từ
        src_start = float(s["in"]) <= 0.02 and first["start"] <= 0.08      # nguồn bắt đầu ngay khi nói → giới hạn nguồn
        if s.get("inner") and prev is not None and prev.get("group") == s.get("group"):
            pass
        elif head < 0.04 or (_voiced(m["path"], float(s["in"]) + 0.01, 10) and head < 0.08):
            rec["flags"].append(("warn" if src_start else "error", f"đầu đoạn {s['id']} hụt: cắt {head * 1000:.0f}ms trước “{first['text']}” — có thể mất phụ âm đầu"))
        nxt_sib = i + 1 < len(segs) and segs[i + 1].get("group") == s.get("group") and segs[i + 1].get("inner")
        if not nxt_sib and (tail < 0.08 or (_voiced(m["path"], float(s["out"]) - 0.01, 10) and tail < 0.15)):
            rec["flags"].append(("error", f"cuối đoạn {s['id']} gấp: cắt {tail * 1000:.0f}ms sau “{last['text']}” — có thể mất đuôi từ/hơi thở"))
        if prev is not None and prev.get("role", "talk") == "talk":
            pm = M[prev["src"]]
            _, plast, _, _ = _words_in(pm, float(prev["in"]), float(prev["out"]))
            if plast:
                gap = (float(prev["out"]) - plast["end"]) + head - float(s.get("j", 0))
                rec["gap"] = round(gap, 3)
                lo, hi = GAP_BIG if s.get("pause") == "lon" else (GAP_MIN, GAP_MAX)
                if s.get("inner") and prev.get("group") == s.get("group"):
                    lo, hi = 0.08, GAP_MAX          # chỗ Cắt sạch bỏ bên trong câu: nối liền mạch, chỉ cần không dính từ
                if gap < lo - 1e-3:
                    rec["flags"].append(("warn" if gap >= 0.12 else "error",
                                         f"nối {prev['id']}→{s['id']} chỉ nghỉ {gap * 1000:.0f}ms (“{plast['text']}” → “{first['text']}”) — gấp, nên {lo * 1000:.0f}–{hi * 1000:.0f}ms"))
                elif gap > hi + 1e-3:
                    rec["flags"].append(("warn", f"nối {prev['id']}→{s['id']} nghỉ {gap * 1000:.0f}ms — hụt nhịp, rút bớt lặng dư"))
        out.append(rec)
    return out


def refine(edit: dict, pdir) -> tuple[dict, list[str]]:
    """nới in/out mọi đoạn nói theo bounds(); dời các mốc at (chữ, cutaway, reframe) để vẫn khớp cùng khoảnh khắc nguồn."""
    M = media(pdir)
    e = copy.deepcopy(edit)
    notes = []
    for s in e["segments"]:
        if s.get("role", "talk") != "talk" or s.get("lock_cut"):
            continue
        m = M[s["src"]]
        a, b, _ = bounds(m, float(s["in"]), float(s["out"]))
        _, _, info = bounds(m, float(s["in"]), float(s["out"]))
        near_next = info.get("next") and info["next"]["start"] - info["last"]["end"] < POST_MAX + 0.25
        near_prev = info.get("prev") and info["first"]["start"] - info["prev"]["end"] < PRE_MAX + 0.25
        if not near_prev:
            a = min(a, float(s["in"]))         # chỉ NỚI (giữ phần đệm đã chủ ý) — trừ khi từ kề nằm sát (cắt ở chỗ lặng nhất)
        if not near_next:
            b = max(b, float(s["out"]))
        da = float(s["in"]) - a                    # >0: đầu đoạn lùi sớm hơn → mọi mốc at tăng da
        if abs(da) > 1e-3 or abs(b - float(s["out"])) > 1e-3:
            notes.append(f"{s['id']}: {s['in']}→{a} / {s['out']}→{b}")
        s["in"], s["out"] = a, b
        for t in s.get("texts", []):
            t["at"] = round(float(t["at"]) + da, 3)
            for it in t.get("items", []):
                it["at"] = round(float(it["at"]) + da, 3)
        for c in s.get("cutaways", []):
            c["at"] = round(float(c["at"]) + da, 3)
        for keys in (s.get("reframe") or {}).values():
            for k in keys:
                k["at"] = round(max(float(k["at"]) + da, 0.0), 3)
    return e, notes


def sheet(edit: dict, pdir) -> Path:
    """ảnh soát điểm nối: mỗi dòng = 1s cuối đoạn trước + 1s đầu đoạn sau; đường năng lượng, mốc từ, vạch cắt (đỏ)."""
    from PIL import Image, ImageDraw
    from ..v2m import draw as D
    M = media(pdir)
    segs = [s for s in layout(edit) if s.get("role", "talk") == "talk"]
    rows = []
    W, H, half = 1000, 150, 1.0
    f = D.font("medium", 15)
    for i in range(len(segs) - 1):
        L, Rr = segs[i], segs[i + 1]
        img = Image.new("RGB", (W, H), (18, 20, 26))
        dr = ImageDraw.Draw(img)
        for side, s, t0, t1 in ((0, L, float(L["out"]) - half, float(L["out"])), (1, Rr, float(Rr["in"]), float(Rr["in"]) + half)):
            m = M[s["src"]]
            db, fl = _env(m["path"])
            x0 = side * W // 2
            pts = []
            for k in range(int(t0 * 100), int(t1 * 100)):
                v = db[k] if 0 <= k < len(db) else fl
                x = x0 + (k / 100 - t0) / half * (W // 2)
                y = H - 20 - max(0.0, min(1.0, (v - fl) / 40)) * (H - 50)
                pts.append((x, y))
            if len(pts) > 1:
                dr.line(pts, fill=(90, 200, 255), width=2)
            dr.line([(x0, H - 20 - 10 / 40 * (H - 50))] * 1 + [(x0 + W // 2, H - 20 - 10 / 40 * (H - 50))], fill=(70, 70, 70))
            for w in m.get("words", []):
                if w["end"] >= t0 and w["start"] <= t1:
                    xa = x0 + max(0.0, (w["start"] - t0)) / half * (W // 2)
                    xb = x0 + min(half, (w["end"] - t0)) / half * (W // 2)
                    dr.rectangle([xa, 8, xb, 26], outline=(255, 210, 80))
                    dr.text((xa + 2, 9), w["text"], font=f, fill=(255, 230, 150))
        dr.line([(W // 2, 0), (W // 2, H)], fill=(255, 60, 60), width=3)
        dr.text((6, H - 18), f"{L['id']} … {L['out']}s  |  {Rr['id']} {Rr['in']}s …", font=f, fill=(220, 220, 220))
        rows.append(img)
    out = Path(pdir) / "review" / "joins.jpg"
    if rows:
        canvas = Image.new("RGB", (W, H * len(rows)), (0, 0, 0))
        for k, r in enumerate(rows):
            canvas.paste(r, (0, k * H))
        canvas.save(out, quality=85)
    return out
