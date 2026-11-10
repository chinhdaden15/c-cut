"""Gu người dùng: mỗi lần người dùng góp ý một quyết định dựng ("bớt zoom", "SFX nghe chán", "đừng ghi nhãn ảnh"…),
Claude sửa video ĐỒNG THỜI ghi góp ý đó thành luật — đúng lời người dùng — để MỌI video sau (cùng skill hoặc mọi skill) đọc trước khi dựng.
Ý tưởng từ ghost-editor (taste.py, MIT). Lưu <dữ liệu app>/taste.json, chỉ trên máy này.

  python -m thagent.tools taste add "<lời người dùng>" [skill|all]     ghi một góp ý (mặc định áp cho mọi skill)
  python -m thagent.tools taste list [skill]                           xem
  python -m thagent.tools taste forget <id>                            bỏ một góp ý (người dùng đổi ý)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .paths import ROOT

FILE = ROOT / "taste.json"


def _load() -> list[dict]:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def add(text: str, style: str = "all", project: str = "") -> dict:
    text = " ".join(str(text).split())[:300]
    if not text:
        raise ValueError("góp ý trống")
    items = _load()
    for it in items:                                   # cùng câu, cùng phạm vi → chỉ làm mới, không trùng
        if it["text"].lower() == text.lower() and it["style"] == style and it.get("active", True):
            it["t"] = time.time()
            _save(items)
            return it
    it = {"id": f"g{len(items) + 1:03d}", "text": text, "style": style or "all", "project": project, "t": time.time(), "active": True}
    items.append(it)
    _save(items)
    return it


def forget(gid: str) -> bool:
    items = _load()
    hit = False
    for it in items:
        if it["id"] == gid:
            it["active"] = False
            hit = True
    _save(items)
    return hit


def active(style: str = "") -> list[dict]:
    return [it for it in _load() if it.get("active", True) and (not style or it["style"] in ("all", style))]


def prompt_block(style: str) -> str:
    """khối đưa vào lời dặn Claude: góp ý cũ của người dùng (mới nhất trước, tối đa 25)."""
    items = sorted(active(style), key=lambda x: -x["t"])[:25]
    head = ("\n\nGU NGƯỜI DÙNG — góp ý từ các video trước (ĐÚNG lời người dùng; áp cho video này, trừ khi người dùng dặn khác lần này):\n"
            if items else "\n\nGU NGƯỜI DÙNG: chưa có góp ý nào.\n")
    body = "".join(f"- [{it['id']}] “{it['text']}”" + ("" if it["style"] == "all" else f" ({it['style']})") + "\n" for it in items)
    rule = ("Khi người dùng góp ý một quyết định dựng (chê / sửa / dặn cách làm), sửa video VÀ ghi lại đúng lời họ: "
            ".venv/bin/python -m thagent.tools taste add \"<lời người dùng>\" [<skill>|all]. Chỉ ghi lời của người dùng, không tự bịa luật; "
            "người dùng đổi ý → taste forget <id>.\n")
    return head + body + rule
