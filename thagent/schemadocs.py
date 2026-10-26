"""Xuất định dạng dữ liệu (docstring đầu mô-đun) ra .claude/shared/schemas/*.md cho Claude trong app đọc.

Bản cài đã biên dịch mã nguồn → Claude không đọc được docstring trong thagent/*.py. Lời dặn Claude trỏ vào các file .md này
(đi kèm bộ cài qua skill.bin). build_seed.py chạy write() trước khi đóng gói → luôn khớp mã nguồn.

python -m thagent.schemadocs          ghi lại các file
"""
from __future__ import annotations

import ast
from pathlib import Path

from .paths import ROOT

OUT = ROOT / ".claude" / "shared" / "schemas"
DOCS = {   # file .md → (mã nguồn, tiêu đề)
    "edl.md": ("thagent/clips.py", "edl.json — ghép nhiều đoạn thành 1 video (Talking Head)"),
    "review-edit.md": ("thagent/review/edit.py", "review/edit.json — bản dựng Review"),
    "hyperframes-spec.md": ("thagent/hyper/spec.py", "Spec job HyperFrames (dùng chung mọi skill)"),
    "talking-head-hf.md": ("thagent/th_hf.py", "plan.hf — lớp HyperFrames trong Talking Head"),
    "talking-head-callouts.md": ("thagent/callouts.py", "plan.callouts — chữ nổi bật + icon / callout / ảnh kẹp (Talking Head)"),
    "talking-head-stage.md": ("thagent/stage.py", "plan.stage — hiệu ứng quanh / sau lưng nhân vật (Talking Head)"),
    "talking-head-mg2.md": ("thagent/mg2.py", "plan.mg2 — Motion Graphics bố cục + chuyển động (Talking Head, HyperFrames)"),
    "icons3d.md": ("thagent/icons3d.py", "Kho icon 3D dùng chung (mọi skill)"),
    "entities.md": ("thagent/entities.py", "entities.json — chủ thể có tên (dự án, địa danh…) + ảnh thật"),
}


def path(name: str) -> str:
    """đường dẫn tương đối (từ thư mục app) để ghi vào lời dặn Claude."""
    return f".claude/shared/schemas/{name}"


def text(name: str) -> str:
    """nội dung file định dạng (bản cài đọc file đã đóng gói; bản dev đọc thẳng docstring)."""
    f = OUT / name
    if f.exists():
        return f.read_text(encoding="utf-8")
    return _render(name)


def _render(name: str) -> str:
    src, title = DOCS[name]
    doc = ast.get_docstring(ast.parse((ROOT / src).read_text(encoding="utf-8")), clean=True) or ""
    return f"# {title}\n\n(Tự sinh từ {src} — không sửa tay.)\n\n```\n{doc}\n```\n"


def write() -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    out = []
    for name in DOCS:
        f = OUT / name
        f.write_text(_render(name), encoding="utf-8")
        out.append(f)
    return out


def main():
    for f in write():
        print(f)


if __name__ == "__main__":
    main()
