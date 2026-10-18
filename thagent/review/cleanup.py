"""Review Editor — làm sạch lời TRONG đoạn nói bằng bộ “Cắt sạch” của Talking Head (thagent.cleancut):
khoảng lặng thừa, từ đệm (ừ/à/ờ), nói vấp/lắp bắp, câu nói lại, chữ kéo dài, âm đệm không thành lời. Biên lặng đo bằng sóng âm thật.

split(edit, pdir) → edit mới: mỗi đoạn nói được chia thành các đoạn con theo phần GIỮ của Cắt sạch (bỏ phần cắt bên trong đoạn).
- chữ/cutaway/reframe được phân về đúng đoạn con (giữ đúng khoảnh khắc nguồn); reframe đang hiệu lực được nối sang đoạn con sau;
- điểm cắt giữa câu che bằng punch-in xen kẽ (×1,06) như Talking Head; đoạn con khoá biên (lock_cut) để fixjoins không nới lại phần đã cắt;
- đoạn có "clean": false → giữ nguyên. Báo cáo từng chỗ cắt + lý do → review/cleanup.json.
"""
from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path

from .edit import media

MIN_SUB = 0.35       # đoạn con ngắn hơn → gộp (tránh nháy hình)
PUNCH = 1.06


@lru_cache(maxsize=16)
def _keep(path: str, words_key: str, dur: float):
    from ..cleancut import clean_cut
    from ..schema import TranscriptWord
    ws = json.loads(words_key)
    tw = [TranscriptWord(id=f"w{i:04d}", text=w["text"], source_start=w["start"], source_end=w["end"], confidence=w.get("conf", 1.0))
          for i, w in enumerate(ws)]
    segs, cuts, _ = clean_cut(tw, dur, path, zoom=1.0)
    return [(s.source_in, s.source_out) for s in segs], [(c.source_in, c.source_out, c.reason) for c in cuts]


def keep_spans(m: dict):
    ws = [{"text": w["text"], "start": w["start"], "end": w["end"], "conf": w.get("conf", 1.0)} for w in m.get("words", [])]
    if not ws:
        return [(0.0, m["duration"])], []
    keep, cuts = _keep(m["path"], json.dumps(ws, ensure_ascii=False), float(m["duration"]))
    for a, b in m.get("restarts", []):          # nói hỏng rồi nói lại (restart.py) → bỏ mẩu hỏng
        nk = []
        for x, y in keep:
            if y <= a or x >= b:
                nk.append((x, y))
            else:
                if x < a: nk.append((x, a))
                if y > b: nk.append((b, y))
        keep = nk
        cuts = cuts + [(a, b, "nói hỏng rồi nói lại")]
    return keep, cuts


def split(edit: dict, pdir) -> tuple[dict, list[dict]]:
    M = media(pdir)
    e = copy.deepcopy(edit)
    out_segs, report = [], []
    for s in e["segments"]:
        if s.get("_auto_zoom"):                     # reframe tự sinh: không chép vào file, render tự sinh lại sau khi chia
            s.pop("reframe", None); s.pop("_auto_zoom", None)
        if s.get("role", "talk") != "talk" or s.get("clean") is False or s.get("inner"):
            out_segs.append(s); continue
        m = M[s["src"]]
        keep, cuts = keep_spans(m)
        a, b = float(s["in"]), float(s["out"])
        subs = [(max(a, x), min(b, y)) for x, y in keep if min(b, y) - max(a, x) > 0.02]
        # gộp đoạn con quá ngắn / khoảng bỏ quá nhỏ (< 0,12s không đáng cắt)
        merged = []
        for x, y in subs:
            if merged and (x - merged[-1][1] < 0.12 or y - x < MIN_SUB):
                merged[-1] = (merged[-1][0], y)
            else:
                merged.append((x, y))
        if len(merged) > 1 and merged[0][1] - merged[0][0] < MIN_SUB:
            merged.pop(0)                          # mẩu đầu quá ngắn (âm đệm/hơi thở) → bỏ, không nháy hình
        if merged and merged[0][0] > a + 1e-3 and (merged[0][0] - a < 0.3 or s.get("lock_cut")):
            merged[0] = (a, merged[0][1])          # giữ biên ngoài người dựng đã đặt (nhịp nói / giữ hình kết)
        if merged:
            merged[-1] = (merged[-1][0], b)
        if len(merged) <= 1:
            out_segs.append(s); continue
        for x, y, why in cuts:
            if x >= a - 0.01 and y <= b + 0.01 and not any(p <= x and y <= q for p, q in merged):
                report.append({"seg": s["id"], "from": round(x, 3), "to": round(y, 3), "s": round(y - x, 3), "reason": why})
        keys = sorted(((s.get("reframe") or {}).items()), key=lambda kv: kv[0])
        for k, (x, y) in enumerate(merged):
            sub = {kk: copy.deepcopy(v) for kk, v in s.items() if kk not in ("texts", "cutaways", "reframe", "take")}
            sub.update(id=f"{s['id']}{chr(97 + k)}", **{"in": round(x, 3), "out": round(y, 3)}, inner=True, group=s["id"], lock_cut=True)
            if k == 0 and s.get("take"):
                sub["take"] = s["take"]
            if k % 2 == 1:
                sub["punch"] = PUNCH             # che điểm cắt giữa câu (như Talking Head)
            if k > 0:
                sub["j"] = 0.0
            # chữ: theo khoảnh khắc nguồn; kéo dài qua đoạn con sau thì giữ nhóm (graphics nối theo group)
            sub["texts"] = []
            for t in s.get("texts", []):
                st = a + float(t["at"])
                lo = merged[k - 1][1] if k else -1e9      # mốc rơi vào chỗ đã cắt → sang đoạn con kế (hiện ngay đầu đoạn)
                if lo - 1e-3 <= st < y or (k == len(merged) - 1 and st >= y):
                    nt = copy.deepcopy(t)
                    nt["at"] = round(max(st - x, 0.0), 3)
                    for it in nt.get("items", []):
                        it["at"] = round(a + float(it["at"]) - x, 3)
                    sub["texts"].append(nt)
            sub["cutaways"] = []
            for c in s.get("cutaways", []):
                st = a + float(c["at"])
                lo = merged[k - 1][1] if k else -1e9
                if lo - 1e-3 <= st < y:
                    nc = copy.deepcopy(c); nc["at"] = round(max(st - x, 0.0), 3); nc["dur"] = round(min(float(c["dur"]), y - max(st, x)), 3)
                    sub["cutaways"].append(nc)
            rf = {}
            for fmt, ks in keys:
                cur = [kk for kk in ks if a + float(kk["at"]) < x]
                mine = [dict(kk, at=round(a + float(kk["at"]) - x, 3)) for kk in ks if x <= a + float(kk["at"]) < y]
                if cur and cur[-1]["to"] != "base":
                    mine = [dict(cur[-1], at=0.0, dur=0.0)] + mine      # khung đang hiệu lực từ đoạn trước → giữ nguyên ngay từ đầu
                if mine:
                    rf[fmt] = mine
            if rf:
                sub["reframe"] = rf
                sub.pop("punch", None)              # đã reframe → không punch thêm
            out_segs.append(sub)
    e["segments"] = out_segs
    return e, report
