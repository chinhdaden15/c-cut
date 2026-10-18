"""Review Editor — phát hiện các lần nói lại cùng một ý (take) trên mọi file, chấm điểm để Claude chọn (KHÔNG tự chọn take cuối/ngắn nhất).

Điểm take = độ tin cậy chép lời + trọn ý (đủ từ so với take dài nhất) − nói vấp/lặp từ − ngập ngừng + có mặt trong khung + hình nét.
"""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from .edit import media

FILLER = {"ừ", "ờ", "à", "ừm", "ờm", "ơ", "thì", "kiểu", "là", "nha"}


def _norm(s: str) -> list[str]:
    s = unicodedata.normalize("NFC", s.lower())
    return [w for w in re.sub(r"[^\w\s]", " ", s).split() if w]


def _stutter(ws: list[str]) -> int:
    return sum(1 for a, b in zip(ws, ws[1:]) if a == b) + sum(1 for w in ws if w in FILLER and len(ws) > 3) // 2


def groups(pdir, min_sim: float = 0.62) -> list[dict]:
    M = media(pdir)
    sents = []
    for fid, m in M.items():
        for k, s in enumerate(m.get("sentences", [])):
            ws = _norm(s["text"])
            if len(ws) < 3:
                continue
            shot = next((x for x in m.get("shots", []) if x["start"] <= s["start"] < x["end"]), {})
            face = sum(1 for f in m.get("samples", []) if s["start"] <= f["t"] <= s["end"] and f.get("face"))
            n_s = max(1, int((s["end"] - s["start"]) / 0.5))
            sents.append({"src": fid, "in": s["start"], "out": s["end"], "text": s["text"], "w": ws, "conf": s["conf"],
                          "face": round(min(face / n_s, 1), 2), "sharp": shot.get("sharp", 0), "flags": shot.get("flags", [])})
    used, out = set(), []
    for i, a in enumerate(sents):
        if i in used:
            continue
        grp = [i]
        for j in range(i + 1, len(sents)):
            if j in used:
                continue
            b = sents[j]
            r = SequenceMatcher(None, a["w"], b["w"]).ratio()
            if r >= min_sim:
                grp.append(j)
        if len(grp) < 2:
            continue
        used.update(grp)
        mx = max(len(sents[g]["w"]) for g in grp)
        takes = []
        for g in grp:
            s = sents[g]
            st = _stutter(s["w"])
            score = 0.45 * s["conf"] + 0.25 * len(s["w"]) / mx + 0.15 * s["face"] + 0.1 * min(s["sharp"] / 120, 1) - 0.08 * st \
                - 0.1 * ("mờ" in s["flags"] or "rung" in s["flags"])
            takes.append({**{k: s[k] for k in ("src", "in", "out", "text", "conf", "face", "flags")}, "stutter": st, "score": round(score, 3)})
        takes.sort(key=lambda t: (t["src"], t["in"]))
        best = max(range(len(takes)), key=lambda k: takes[k]["score"])
        for k, t in enumerate(takes):
            t["take"] = f"T{k + 1}"
        out.append({"group": f"G{len(out) + 1:02d}", "idea": takes[best]["text"][:80], "suggest": takes[best]["take"], "takes": takes})
    (Path(pdir) / "review" / "takes.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
