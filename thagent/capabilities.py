"""Registry CÔNG CỤ DỰNG DÙNG CHUNG của app — mọi skill video tự nhận, không cần sửa từng skill.

- Skill = thư mục .claude/skills/<slug>/ có style.json. Skill là video trừ khi style.json ghi "video": false.
  Skill có thể khai "shared_tools": ["hyperframes"] (giới hạn) hoặc "shared_tools": false (không dùng); mặc định: tất cả.
  Ghi chú riêng cho skill (cách dùng phù hợp skill đó): style.json → "tool_notes": {"hyperframes": "…"}.
- agent.Session gắn prompt_block(style) vào system prompt của MỌI phiên agent → skill mới tạo sau này tự có.
- Thêm công cụ dùng chung mới: thêm một mục vào TOOLS (id, mô tả, lệnh, tài liệu, nên dùng/không dùng, hàm kiểm sẵn sàng).

python -m thagent.capabilities                 bảng skill × công cụ (JSON)
python -m thagent.capabilities <slug>          đoạn hướng dẫn agent của skill đó nhận được
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .paths import ROOT

SKILLS = ROOT / ".claude" / "skills"
SHARED_DOC = ROOT / ".claude" / "shared"


def _hf_status() -> dict:
    from .hyper.runtime import doctor
    return doctor()


TOOLS = {
    "hyperframes": {
        "name": "HyperFrames (HTML → video, GSAP)",
        "version": lambda: __import__("thagent.hyper.runtime", fromlist=["pinned"]).pinned()["hyperframes"],
        "command": "python -m thagent.hyper",
        "doc": ".claude/shared/hyperframes.md",
        "use_for": ["text motion, tiêu đề, phụ đề thiết kế, callout, nhãn, overlay", "sơ đồ, biểu đồ, bảng so sánh, motion minh hoạ",
                    "composition ghép ảnh + video + đồ hoạ", "đoạn đồ hoạ tái sử dụng (spec JSON)",
                    "spotlight/callout bám vật — CHỈ với dữ liệu vị trí/tracking thật"],
        "not_for": ["nhận dạng/căn thời gian lời nói (dùng ASR của app)", "cắt lời, khoảng nghỉ, xử lý âm thanh (bộ cắt của app)",
                    "tracking sản phẩm, tách nền nhân vật (công cụ của app)", "tạo voice/ảnh/video AI", "xử lý dữ liệu địa lý (v2m geo)"],
        "status": _hf_status,
    },
}
_CACHE: dict = {}


def status(tool: str, ttl: float = 300) -> dict:
    c = _CACHE.get(tool)
    if c and time.time() - c[0] < ttl:
        return c[1]
    try:
        st = TOOLS[tool]["status"]()
    except Exception as e:
        st = {"ok": False, "problems": [f"không kiểm được: {e}"]}
    _CACHE[tool] = (time.time(), st)
    return st


def skills() -> dict:
    out = {}
    for d in sorted(SKILLS.glob("*/style.json")):
        try:
            st = json.loads(d.read_text(encoding="utf-8"))
        except Exception:
            st = {}
        out[d.parent.name] = st
    return out


def tools_for(slug: str) -> list[str]:
    st = skills().get(slug, {})
    if st.get("video") is False or st.get("shared_tools") is False:
        return []
    allow = st.get("shared_tools")
    return [t for t in TOOLS if not isinstance(allow, list) or t in allow]


def prompt_block(slug: str) -> str:
    """đoạn gắn vào system prompt của agent cho skill `slug` (không chứa bản sao tài liệu — chỉ trỏ tới nguồn chung)."""
    ts = tools_for(slug)
    if not ts:
        return ""
    notes = skills().get(slug, {}).get("tool_notes", {})
    lines = ["", "CÔNG CỤ DỰNG DÙNG CHUNG CỦA APP (tự cấp cho mọi skill video — xem `python -m thagent.capabilities " + slug + "`):"]
    for t in ts:
        T = TOOLS[t]
        st = status(t)
        ok = "SẴN SÀNG" if st.get("ok") else "CHƯA SẴN SÀNG: " + "; ".join(st.get("problems", []))[:300]
        lines += [f"- {T['name']} {T['version']()} — {ok}",
                  f"  Gọi: `.venv/bin/python -m thagent.hyper validate|render|stills <spec.json>` (chuẩn spec: docstring thagent/hyper/spec.py; "
                  f"hướng dẫn: {T['doc']}).",
                  "  Nên cân nhắc cho: " + "; ".join(T["use_for"]) + ".",
                  "  KHÔNG dùng cho: " + "; ".join(T["not_for"]) + " — HyperFrames nhận KẾT QUẢ của các bước đó để dựng.",
                  "  Bộ dựng của skill SỞ HỮU timeline cuối; HyperFrames chỉ render đúng lớp/đoạn cần (mov có alpha), không render cả video 2 lần. "
                  "Spotlight/callout bám vật phải lấy vị trí từ tracking thật. Công cụ chưa sẵn sàng → dùng phương án tương đương của skill, "
                  "không có thì BÁO RÕ phần bị chặn; không âm thầm bỏ hiệu ứng. Không tự nâng phiên bản."]
        if notes.get(t):
            lines.append("  Với skill này: " + notes[t])
    return "\n".join(lines)


def table() -> dict:
    return {slug: {"video": st.get("video", True), "tools": tools_for(slug), "version": st.get("version")} for slug, st in skills().items()}


if __name__ == "__main__":
    a = sys.argv[1:]
    if a:
        print(prompt_block(a[0]) or f"(skill {a[0]} không dùng công cụ dựng chung)")
    else:
        print(json.dumps({"tools": {k: {"name": v["name"], "version": v["version"](), "command": v["command"], "doc": v["doc"],
                                        "ready": status(k).get("ok")} for k, v in TOOLS.items()},
                          "skills": table()}, ensure_ascii=False, indent=1))
