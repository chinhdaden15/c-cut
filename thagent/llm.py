"""Adapter Claude (tùy chọn). Chỉ gửi transcript văn bản. Key đọc từ env phía backend."""
from __future__ import annotations

import json
import os

from .schema import Plan, TextGroup

MODEL = os.environ.get("THAGENT_CLAUDE_MODEL", "claude-sonnet-5-5")

PROMPT = """Bạn là editor video Talking Head bất động sản tiếng Việt. Dưới đây là transcript (id từ, text).
Các nhóm text nhấn hiện tại do heuristic chọn. Hãy trả về JSON {"groups":[{"word_ids":[...],"lead":"...","key":"...","preset":"staggered_phrase|keyword_pop|number_callout|behind_head_title"}]}
Quy tắc: key/lead phải là NGUYÊN VĂN các từ trong word_ids (liên tiếp), không viết lại, giữ số/đơn vị/điều kiện
("dự kiến","từ","tối đa","chưa","không"). Tối đa 1 nhóm mỗi câu, nhóm đầu là behind_head_title. Chỉ trả JSON."""


def refine_with_claude(plan: Plan, words, sentences, retries: int = 2):
    import anthropic

    client = anthropic.Anthropic()
    tx = "\n".join(f"{w.id}\t{w.text}" for w in words)
    cur = json.dumps([{"word_ids": g.word_ids, "preset": g.preset} for g in plan.text_groups], ensure_ascii=False)
    wmap = {w.id: w for w in words}
    for attempt in range(retries + 1):
        msg = client.messages.create(model=MODEL, max_tokens=4000,
                                     messages=[{"role": "user", "content": f"{PROMPT}\n\nTRANSCRIPT:\n{tx}\n\nHIỆN TẠI:\n{cur}"}])
        text = msg.content[0].text
        try:
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])
            for g in data["groups"]:
                joined = " ".join(wmap[i].text for i in g["word_ids"])
                if g["key"] not in joined:
                    raise ValueError(f"key không nguyên văn: {g['key']}")
            plan.notes.append(f"Claude ({MODEL}) đã duyệt {len(data['groups'])} nhóm text.")
            plan.planner = f"claude:{MODEL}"
            plan.llm_raw = data  # type: ignore[attr-defined]
            return data
        except Exception as e:
            err = e
    raise RuntimeError(f"LLM trả dữ liệu không hợp lệ sau {retries + 1} lần: {err}")
