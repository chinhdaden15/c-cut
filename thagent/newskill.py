"""Tạo skill video mới từ template chung (.claude/skill-template) — skill tự kế thừa công cụ dựng dùng chung của app
(thagent.capabilities gắn vào phiên agent theo style.json, không cần sửa app hay chép tài liệu công cụ vào skill).

python -m thagent.newskill <slug> "<Tên hiển thị>" "<mô tả một câu>"
"""
from __future__ import annotations

import re
import sys

from .paths import ROOT

TPL = ROOT / ".claude" / "skill-template"


def create(slug: str, name: str, description: str):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", slug):
        raise SystemExit("slug chỉ gồm a-z, 0-9, dấu gạch ngang")
    dst = ROOT / ".claude" / "skills" / slug
    if dst.exists():
        raise SystemExit(f"đã có skill {slug}")
    dst.mkdir(parents=True)
    for f in TPL.iterdir():
        txt = f.read_text(encoding="utf-8").replace("{{slug}}", slug).replace("{{name}}", name).replace("{{description}}", description)
        (dst / f.name).write_text(txt, encoding="utf-8")
    from .capabilities import tools_for
    print(f"đã tạo {dst} — công cụ dùng chung tự nhận: {', '.join(tools_for(slug)) or '(không)'}")
    return dst


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__); sys.exit(1)
    create(*a[:3])
