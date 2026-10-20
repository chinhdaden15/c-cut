"""Editorial + layout/motion + sound planner.

Chế độ `heuristic` (mặc định khi chưa có ANTHROPIC_API_KEY): quy tắc xác định, gắn nhãn rõ
— KHÔNG phải AI phân tích hoàn chỉnh. Chế độ `claude`: gửi transcript (chỉ văn bản, không
gửi video) tới Claude để chọn cụm ý/Hook/CTA, kết quả phải qua schema rồi mới dùng.
Text luôn lấy nguyên văn từ transcript; planner không viết lại lời người dẫn.
"""
from __future__ import annotations

import json
import os
import re

from . import timeline as T
from .schema import (EditSegment, Plan, SoundEvent, TextGroup, TextSpan, TranscriptWord,
                     Sentence, VideoFxEvent, VisualEvent)
from .typography import hit_frame

# Từ làm thay đổi ý nghĩa — không bao giờ bị cắt khỏi cụm text chứa con số/điều kiện
MEANING_WORDS = {"dự", "kiến", "có", "thể", "từ", "tối", "đa", "chưa", "không", "khoảng", "gần", "hơn",
                 "trên", "dưới", "chỉ", "đến"}
UNITS = r"(năm|tháng|tỷ|tỉ|triệu|nghìn|ngàn|%|phần trăm|m2|m²|mét|ha|héc|km|phút|căn|dự án|chuyên gia|usd|đô|người|tầng|sản phẩm|tỉnh|thành phố)"
NUM_WORDS = r"(một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mươi|trăm|nghìn|ngàn|triệu|tỷ|\d)"
RE_KEYWORDS = ["bất động sản", "dự án", "nghỉ dưỡng", "resort", "phong cách sống", "kết nối", "đầu tư",
               "pháp lý", "sổ hồng", "vị trí", "tiện ích", "mặt bằng", "bản đồ", "chủ đầu tư", "giá",
               "ưu đãi", "thanh toán", "bàn giao", "hành trình", "thương hiệu", "trải nghiệm", "kỷ nguyên"]
CTA_WORDS = ["liên hệ", "inbox", "nhắn", "follow", "theo dõi", "đăng ký", "comment", "bình luận", "để lại"]
ILLUSTRATE = ["bản đồ", "mặt bằng", "phối cảnh", "dự án", "vị trí", "tiện ích", "resort", "việt nam"]


def _norm(s: str) -> str:
    return re.sub(r"[^\w%²\s]", "", s.lower()).strip()


def cut_plan(words: list[TranscriptWord], src_dur: float, max_gap=0.45, pad_pre=0.10, pad_post=0.16, media: str | None = None) -> list[EditSegment]:
    """Giữ vùng có lời; rút khoảng lặng dài còn ~0.26s. Biên cắt có đệm để không mất phụ âm cuối."""
    segs: list[EditSegment] = []
    cuts: list[EditSegment] = []
    # lặp liền kề (vấp): cụm n từ lặp lại ngay → cắt lần đầu, độ tin cậy vừa
    drop = set()
    toks = [_norm(w.text) for w in words]
    for n in (4, 3, 2):
        for i in range(len(words) - 2 * n + 1):
            if any(j in drop for j in range(i, i + 2 * n)):
                continue
            if toks[i:i + n] == toks[i + n:i + 2 * n] and all(toks[i:i + n]):
                gap = words[i + n].source_start - words[i + n - 1].source_end
                drop.update(range(i, i + n))
                cuts.append(EditSegment(id=f"cut_rep{i}", source_in=words[i].source_start,
                                        source_out=words[i + n].source_start, keep=False,
                                        reason=f"lặp liền kề “{' '.join(w.text for w in words[i:i+n])}” (khoảng nghỉ {gap:.2f}s) — có thể là nhấn chủ đích, cần duyệt",
                                        confidence=0.6))
    kept_words = [w for i, w in enumerate(words) if i not in drop]
    if not kept_words:
        return []
    start = max(kept_words[0].source_start - pad_pre - 0.1, 0)
    prev = kept_words[0]
    for w in kept_words[1:]:
        gap = w.source_start - prev.source_end
        if gap > max_gap:
            a, b = prev.source_end + pad_post, w.source_start - pad_pre
            segs.append(EditSegment(id=f"s{len(segs):03d}", source_in=round(start, 3), source_out=round(a, 3),
                                    reason="giữ lời nói", confidence=0.9))
            cuts.append(EditSegment(id=f"cut_gap{len(cuts)}", source_in=round(a, 3), source_out=round(b, 3), keep=False,
                                    reason=f"khoảng lặng {gap:.2f}s rút còn ~{pad_pre + pad_post:.2f}s", confidence=0.85))
            start = b
        prev = w
    end = prev.source_end + pad_post + 0.15
    if media:                       # đuôi: tới lúc giọng thật dứt (mốc chữ cuối của ASR có thể sớm hơn lời thật)
        try:
            from .cleancut import silences, speech_stop
            end = max(end, speech_stop(silences(media), prev.source_end, src_dur) + 0.3)
        except Exception:
            pass
    segs.append(EditSegment(id=f"s{len(segs):03d}", source_in=round(start, 3),
                            source_out=round(min(end, src_dur), 3),
                            reason="giữ lời nói", confidence=0.9))
    # nối đoạn repeat-cut: đoạn keep chứa vùng drop phải tách
    final = []
    for s in segs:
        pieces = [(s.source_in, s.source_out)]
        for c in [c for c in cuts if c.id.startswith("cut_rep")]:
            nxt = []
            for a, b in pieces:
                if c.source_in < b and c.source_out > a:
                    if c.source_in - a > 0.05: nxt.append((a, c.source_in))
                    if b - c.source_out > 0.05: nxt.append((c.source_out, b))
                else:
                    nxt.append((a, b))
            pieces = nxt
        for a, b in pieces:
            final.append(EditSegment(id=f"s{len(final):03d}", source_in=a, source_out=b, reason=s.reason,
                                     confidence=s.confidence))
    for i, s in enumerate(final):
        s.order = i
    return final + cuts


def find_hooks(sentences: list[Sentence], words: list[TranscriptWord]) -> list[dict]:
    wmap = {w.id: w for w in words}
    out = []
    for s in sentences:
        d = s.source_end - s.source_start
        txt = s.text.lower()
        score = 0
        if re.search(r"\d", txt) or re.search(NUM_WORDS + r"\s+" + UNITS, txt): score += 2
        score += sum(k in txt for k in RE_KEYWORDS)
        if "?" in s.text: score += 1
        if 1.8 <= d <= 5.5: score += 1
        if score >= 2:
            out.append({"sentence_id": s.id, "text": s.text, "source_in": s.source_start, "source_out": s.source_end,
                        "score": score, "duration": round(d, 2)})
    return sorted(out, key=lambda h: -h["score"])[:3]


def _phrase_words(words, sent: Sentence):
    wmap = {w.id: w for w in words}
    return [wmap[i] for i in sent.word_ids]


def _match(ws: list[TranscriptWord], phrase: str) -> tuple[int, int] | None:
    toks = [_norm(w.text) for w in ws]
    ph = phrase.split()
    for i in range(len(toks) - len(ph) + 1):
        if toks[i:i + len(ph)] == ph:
            return i, i + len(ph)
    return None


def design_groups(plan: Plan, words: list[TranscriptWord], sentences: list[Sentence], accent="#C9A86A") -> None:
    """Một nhóm text nhấn cho mỗi câu có từ khóa/con số; xen kẽ bố cục; text nguyên văn."""
    fps = plan.fps
    groups = []
    for si, s in enumerate(sentences):
        ws = _phrase_words(words, s)
        tl = [T.src_to_tl(plan, w.source_start) for w in ws]
        if not ws or all(t is None for t in tl):
            continue
        low = " ".join(_norm(w.text) for w in ws)
        span = None
        kind = None
        m = re.search(r"((?:\S+\s+)?(?:" + NUM_WORDS + r"\S*\s+){1,3}" + UNITS + r")", low)
        if m:
            span = _match(ws, m.group(1).strip()); kind = "number"
        if span is None:
            for k in RE_KEYWORDS:
                span = _match(ws, k)
                if span: kind = "keyword"; break
        if span is None:
            continue
        i0, i1 = span
        # mở rộng để không bỏ rơi từ thay đổi ý nghĩa ngay trước cụm
        while i0 > 0 and _norm(ws[i0 - 1].text) in MEANING_WORDS:
            i0 -= 1
        lead = ws[max(0, i0 - 3):i0]
        key = ws[i0:i1]
        t_start = T.src_to_tl(plan, (lead or key)[0].source_start)
        t_end = T.src_to_tl(plan, key[-1].source_end - 0.01)
        if t_start is None or t_end is None:
            continue
        gid = f"g{len(groups):02d}"
        keytxt = " ".join(w.text for w in key).strip(",.?!")
        leadtxt = " ".join(w.text for w in lead).strip(",.?!")
        first = not groups
        if first:
            g = TextGroup(id=gid, preset="behind_head_title", zone="above_head", layer="behind_subject",
                          spans=[TextSpan(text=keytxt, font_role="emphasis", size=150, color="#FFFFFF")])
        elif kind == "number":
            g = TextGroup(id=gid, preset="number_callout", zone="chest", layer="front_of_subject",
                          spans=[TextSpan(text=keytxt, font_role="number", size=118, color="#FFFFFF", dy=0),
                                 *([TextSpan(text=leadtxt, font_role="body", size=46, color="#F2F2F2", dy=-92, delay_frames=3)] if leadtxt else [])])
        else:
            alt = len(groups) % 2
            g = TextGroup(id=gid, preset="staggered_phrase", zone="chest", layer="front_of_subject",
                          align="left" if alt else "right", anchor_x=0.12 if alt else 0.88,
                          spans=[*([TextSpan(text=leadtxt, font_role="body", size=46, color="#F2F2F2", dy=-78)] if leadtxt else []),
                                 TextSpan(text=keytxt, font_role="emphasis", size=104, color=accent, dy=10, delay_frames=4)])
        g.word_ids = [w.id for w in lead + key]
        g.start = t_start
        g.end = max(t_end + int(0.9 * fps), t_start + int(1.6 * fps))
        g.enter_frames = 9 if g.preset != "behind_head_title" else 12
        g.exit_frames = 6
        groups.append(g)
    # không chồng nhóm: cắt đuôi nhóm trước
    for a, b in zip(groups, groups[1:]):
        if a.end > b.start - 2:
            a.end = max(b.start - 2, a.start + a.enter_frames + 12)
    for g in groups:
        g.hit = hit_frame(g)
    plan.text_groups = groups


def design_sound_fx(plan: Plan) -> None:
    sounds, fx = [], []
    for g in plan.text_groups:
        if g.preset == "behind_head_title":
            sid = f"sfx_{g.id}"
            sounds.append(SoundEvent(id=sid, asset="impact_soft", linked_event=g.id, hit=g.hit, gain_db=-14, priority=3))
            fx.append(VideoFxEvent(id=f"fl_{g.id}", type="flash", start=g.hit - 1, end=g.hit + 6,
                                   params={"opacity": 0.16}, linked_sound=sid))
        elif g.preset in ("number_callout", "keyword_pop"):
            sounds.append(SoundEvent(id=f"sfx_{g.id}", asset="pop_soft", linked_event=g.id, hit=g.hit, gain_db=-16, priority=2))
            fx.append(VideoFxEvent(id=f"zm_{g.id}", type="zoom", start=g.start, end=g.end,
                                   params={"scale": 1.06, "cx": 0.5, "cy": 0.35}))
        else:
            sounds.append(SoundEvent(id=f"sfx_{g.id}", asset="whoosh_short", linked_event=g.id, hit=g.hit, gain_db=-18, priority=1))
        g.sfx = sounds[-1].id
    plan.sounds, plan.fx = sounds, fx


def illustration_needs(plan: Plan, sentences: list[Sentence]) -> None:
    vis = []
    for s in sentences:
        t = s.text.lower()
        hits = [k for k in ILLUSTRATE if k in t]
        if hits:
            f = T.src_to_tl(plan, s.source_start)
            if f is None:
                continue
            vis.append(VisualEvent(id=f"vis{len(vis):02d}", asset_id=None, start=f,
                                   end=T.src_to_tl(plan, s.source_end - 0.01) or f + 60,
                                   illustrates=f"“{s.text}” → cần: {', '.join(hits)}", status="missing_asset"))
    plan.visuals = vis


def make_plan(words, sentences, src_dur, fps=30, planner="auto", media: str | None = None) -> Plan:
    plan = Plan(fps=fps)
    use_claude = planner == "claude" or (planner == "auto" and os.environ.get("ANTHROPIC_API_KEY"))
    plan.planner = "heuristic (quy tắc, chưa dùng LLM)"
    plan.segments = cut_plan(words, src_dur, media=media)
    plan.hook_candidates = find_hooks(sentences, words)
    plan.notes.append("Hook: chỉ liệt kê ứng viên; heuristic không đủ tin cậy để tự di chuyển câu lên đầu.")
    last = sentences[-1].text.lower() if sentences else ""
    if not any(k in last for k in CTA_WORDS):
        plan.notes.append("CTA: không tìm thấy câu kêu gọi hành động trong nguồn — cần quay bổ sung hoặc duyệt text CTA.")
    T.build_mapping(plan)
    design_groups(plan, words, sentences)
    if use_claude:
        try:
            from .llm import refine_with_claude
            refine_with_claude(plan, words, sentences)
        except Exception as e:  # không im lặng: ghi chú lỗi
            plan.notes.append(f"Claude planner lỗi, giữ heuristic: {e}")
    design_sound_fx(plan)
    illustration_needs(plan, sentences)
    return plan
