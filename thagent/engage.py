"""Luật "cuốn hút" của Talking Head (preflight — LỖI chặn xuất). Người dùng chốt 2026-10-27:
mọi đoạn nói đều phải có thứ gì đó trên hình, cứ ~5s có một hiệu ứng mới.

1. Phủ kín lời nói: đang nói mà trên hình không có chữ nhấn / callout / hiệu ứng sân khấu / MG quá 1.5s → lỗi.
2. Nhịp 5s: khoảng giữa hai lần có thứ MỚI xuất hiện (nhóm chữ, callout, hiệu ứng sân khấu, cảnh MG, từng mục trong cảnh MG) ≤ 5s.
3. Hiệu ứng quanh / sau lưng (plan.stage): ≥ 1 lần mỗi 15s nói (ngoài cảnh MG che kín).
4. Callout có icon (plan.callouts, tính cả MG2 chồng cạnh người: chips / iconrow): ≥ 1 cái mỗi 10s nói (ngoài cảnh MG che kín).
5. Liệt kê — từ liệt kê (first/second/tip/thứ nhất…) phải là CHỮ CHÍNH to; và ("first / second", "thứ nhất / thứ hai", "một là / hai là"…) → phải có đồ hoạ liệt kê đúng lúc đó
   (MG2 checklist / notif / chips / iconrow / compare hoặc callout checklist / trio / step / stat_pair / dos_donts / photo_strip).
"""
from __future__ import annotations

import re

LIST_MG2 = {"checklist", "notif", "chips", "iconrow", "compare", "photos"}
LIST_CO = {"checklist", "trio", "step", "stat_pair", "dos_donts", "photo_strip", "before_after"}
ENUM = re.compile(r"^(first(ly)?|second(ly)?|third(ly)?|fourth|fifth|lastly|"
                  r"thứ\s+(nhất|hai|ba|tư|năm)|một\s+là|hai\s+là|ba\s+là|bốn\s+là|"
                  r"number\s+(one|two|three|four|five)|step\s+(one|two|three)|[1-9][.)])$", re.I)


def _spans(plan, fps):
    from . import mg as M, stage as ST, mg2 as MG2
    M.chain(plan.mg)
    sp = [(g.start, g.end) for g in plan.text_groups if g.enabled]
    sp += [(int(c["start"]), int(c["end"])) for c in plan.callouts if c.get("enabled", True)]
    sp += [ST.span(s) for s in plan.stage if s.get("enabled", True)]
    sp += [(int(m["start"]), int(m["end"])) for m in plan.mg2 if m.get("enabled", True)]
    sp += [M.covered_range(m) for m in plan.mg]
    sp += [(int(h["start"]), int(h["end"])) for h in plan.hf if h.get("enabled", True)]
    return sp


def _entries(plan, fps):
    from . import mg as M, mg2 as MG2
    e = [g.hit for g in plan.text_groups if g.enabled]
    e += [int(c["start"]) for c in plan.callouts if c.get("enabled", True)]
    e += [int(c["start"]) + int(round(t)) - int(c["start"]) for c in plan.callouts if c.get("enabled", True) for t in c.get("at") or []
          if int(c["start"]) < int(t) < int(c["end"])]
    e += [int(s["start"]) for s in plan.stage if s.get("enabled", True)]
    e += [int(h["start"]) for h in plan.hf if h.get("enabled", True)]
    for m in plan.mg2:
        if not m.get("enabled", True):
            continue
        a, b = int(m["start"]), int(m["end"])
        n = len(m.get("items") or m.get("icons") or m.get("images") or [])
        ts = MG2.at_seconds(m, fps) if m.get("at") else (MG2.delays(m, n, .3, .35) if n else [])
        e += [a] + [a + int(t * fps) for t in ts if a + t * fps < b]
    for seg in plan.mg:
        e += [int(s["start"]) for s in seg.get("scenes", [])]
        e += [int(el["t"]) for s in seg.get("scenes", []) for el in s.get("elements", []) if el.get("t") is not None]   # từng chi tiết MG hiện ra
    return sorted(set(e))


def _key(t: str) -> str:
    t = re.sub(r"[^\w ]", "", str(t).lower())
    return {"firstly": "first", "secondly": "second", "thirdly": "third"}.get(t.strip(), t.strip())


def check(plan, words, fps: int) -> list[tuple[str, str]]:
    from . import timeline as T, mg2 as MG2
    T.build_mapping(plan)
    out = []
    D = plan.duration_frames
    speech = []
    for w in words or []:
        a, b = T.src_to_tl(plan, w.source_start), T.src_to_tl(plan, w.source_end)
        if a is not None:
            speech.append((a, b if b is not None else a + 6, w.text))
    spans = _spans(plan, fps)
    full = MG2.covers(plan)
    from . import mg as M
    full += [M.covered_range(m) for m in plan.mg]
    covered = bytearray(D + 1)
    for a, b in spans:
        for f in range(max(0, a), min(D, b)):
            covered[f] = 1
    # 1) đang nói mà trên hình trống (bật phụ đề → lời nói luôn có chữ trên hình, khỏi kiểm)
    run = None
    if getattr(plan, "captions", False):
        talk_ = []
    else:
        talk_ = None
    talk = sorted(speech) if talk_ is None else talk_
    holes = []
    for a, b, _ in talk:
        for f in range(max(0, a), min(D, b)):
            if covered[f]:
                if run and run[1] - run[0] >= 1.5 * fps:
                    holes.append(tuple(run))
                run = None
            else:
                if run and f - run[1] <= 0.3 * fps:
                    run[1] = f + 1
                else:
                    if run and run[1] - run[0] >= 1.5 * fps:
                        holes.append(tuple(run))
                    run = [f, f + 1]
    if run and run[1] - run[0] >= 1.5 * fps:
        holes.append(tuple(run))
    for a, b in holes:
        out.append(("error", f"{T.tc(a)}→{T.tc(b)}: đang nói {(b - a) / fps:.1f}s mà trên hình trống — thêm chữ nhấn / callout / "
                             "hiệu ứng sân khấu / MG (mọi đoạn nói đều phải có thứ gì đó)"))
    # 2) nhịp ~5s có thứ mới xuất hiện
    prev = 0
    for e in _entries(plan, fps) + [D]:
        if e - prev > 5 * fps:
            out.append(("error", f"{T.tc(prev)}→{T.tc(e)}: {(e - prev) / fps:.1f}s không có hiệu ứng / chữ / callout MỚI nào xuất hiện — "
                                 "cứ ~5s phải có một thứ mới (callout, hiệu ứng sân khấu, chữ nhấn, mục MG…)"))
        prev = max(prev, e)
    # 3, 4) đủ hiệu ứng sân khấu và callout theo thời gian nói (ngoài MG che kín)
    talk_f = sum(1 for a, b, _ in talk for f in range(max(0, a), min(D, b)) if not any(x <= f < y for x, y in full))
    ts = talk_f / fps
    n_stage = len([s for s in plan.stage if s.get("enabled", True)])
    n_co = len([c for c in plan.callouts if c.get("enabled", True)]) + \
        len([m for m in plan.mg2 if m.get("enabled", True) and not MG2.full(m)])   # MG chồng cạnh người (chips / iconrow) = callout
    need_st, need_co = int(ts // 15), int(ts // 10)
    if n_stage < need_st:
        out.append(("error", f"chỉ {n_stage} hiệu ứng quanh / sau lưng (plan.stage) cho {ts:.0f}s nói — cần ≥ {need_st} (1 mỗi 15s): "
                             "chữ / số khổng lồ, băng chữ, icon 3D bay quanh, bokeh, đèn rọi"))
    if n_co < need_co:
        out.append(("error", f"chỉ {n_co} callout cho {ts:.0f}s nói — cần ≥ {need_co} (1 mỗi 10s): chữ + icon 3D, trước/sau, cảnh báo, "
                             "số lớn, checklist…"))
    # 2b) 10s đầu (hook): MỖI câu phải có chữ nhấn / callout / MG RIÊNG xuất hiện trong lúc nói câu đó
    ents = _entries(plan, fps)
    sent = []
    for a, b, t in talk:
        if a >= 10 * fps:
            break
        if not sent or sent[-1][2]:
            sent.append([a, b, False, t])
        else:
            sent[-1][1] = b; sent[-1][3] += " " + t
        sent[-1][2] = t[-1:] in ".!?…,"
    for a, b, _, t in sent:
        if b - a >= fps and not any(a - 6 <= e <= b for e in ents):
            out.append(("error", f"{T.tc(a)}: câu mở đầu “{t[:50]}” chưa có chữ nhấn riêng — 10s đầu mỗi câu khẳng định / đối lập "
                                 "phải có CHỮ CHÍNH to của chính nó (phụ đề làm dòng dẫn), không để một nhóm chữ phủ hai câu"))
    # 5) liệt kê phải có đồ hoạ liệt kê
    marks, marks_w = [], []
    for i, (a, b, t) in enumerate(talk):
        one = re.sub(r"[^\w\s.)]", "", t.lower()).strip()
        two = (one + " " + re.sub(r"[^\w\s]", "", talk[i + 1][2].lower())).strip() if i + 1 < len(talk) else one
        if ENUM.match(one) or ENUM.match(two):
            marks.append(a)
            marks_w.append((a, one if ENUM.match(one) else two))
    # 5b) từ liệt kê ("Second", "Tip", "Thứ hai"…) phải là CHỮ CHÍNH to, nổi bật — không chỉ dòng dẫn nhỏ
    for f, word in marks_w:
        big = False
        for g in plan.text_groups:
            if g.enabled and g.start - fps <= f < g.end:
                for sp in g.spans:
                    if sp.style in ("neon", "outline", "pill") and sp.size >= 80 and _key(word) in _key(sp.text):
                        big = True
        for c in plan.callouts:
            if c.get("enabled", True) and int(c["start"]) - fps <= f < int(c["end"]) and c.get("kind") in ("step", "big_number", "two_tier", "icon_keyword") \
                    and _key(word) in _key(" ".join(str(c.get(k, "")) for k in ("text", "step"))):
                big = True
        for m in plan.mg2:                                   # tiêu đề / chữ chính lớn của cảnh MG chứa từ liệt kê
            if m.get("enabled", True) and int(m["start"]) - fps <= f < int(m["end"]) \
                    and _key(word) in _key(" ".join(str(m.get(k, "")) for k in ("title", "text"))):
                big = True
        for seg in plan.mg:                                  # MG cũ: cảnh có chữ "big" là số / từ liệt kê (vd "ĐIỀU 1", "THỨ HAI")
            for sc in seg.get("scenes", []):
                if int(sc["start"]) - fps <= f < int(sc["end"]) and any(
                        el.get("type") == "big" and (re.search(r"\d", str(el.get("text", ""))) or _key(word) in _key(el.get("text", "")))
                        for el in sc.get("elements", [])):
                    big = True
        if not big:
            out.append(("error", f"{T.tc(f)}: từ liệt kê “{word}” chưa làm nổi bật — đặt thành CHỮ CHÍNH to (vd “SECOND”, “TIP #2”, “THỨ HAI”) "
                                 "đúng lúc nói, không để ở dòng dẫn nhỏ"))
    if len(marks) >= 2:
        lists = [(int(m["start"]), int(m["end"])) for m in plan.mg2 if m.get("enabled", True) and m.get("kind") in LIST_MG2]
        lists += [(int(c["start"]), int(c["end"])) for c in plan.callouts if c.get("enabled", True) and c.get("kind") in LIST_CO]
        miss = [f for f in marks if not any(x - 2 * fps <= f < y for x, y in lists)]
        if miss:
            out.append(("error", f"người nói đang LIỆT KÊ (mốc {', '.join(T.tc(f) for f in miss[:5])}) mà chưa hiện danh sách — thêm MG2 "
                                 "checklist / notif / chips / iconrow hoặc callout checklist / trio / step, từng mục hiện đúng lúc nói"))
    return out
