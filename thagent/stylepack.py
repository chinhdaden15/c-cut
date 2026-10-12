"""Gói phong cách (style pack): 1 file .zip chứa toàn bộ những gì cần để app dựng theo một style.

Cấu trúc trong gói:
  style_pack.json            tên, phiên bản, danh sách file, sha256
  skill/                     → .claude/skills/<slug>/   (SKILL.md, style.json, reference/)
  kit/                       → kit/                     (tools.json, resources.json, install.py, sfx/)

python -m thagent.stylepack build "Style Talking Head"     # tạo dist/Style Talking Head.zip
python -m thagent.stylepack import "dist/Style Talking Head.zip"   # cài vào app (rồi chạy kit/install.py)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

from .paths import ROOT
SLUG = "talking-head-style"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def build(name: str = "Style Talking Head", out_dir: Path = ROOT / "dist") -> Path:
    skill = ROOT / ".claude" / "skills" / SLUG
    kit = ROOT / "kit"
    files: list[tuple[str, Path]] = []
    for p in sorted(skill.rglob("*")):
        if p.is_file():
            files.append((f"skill/{p.relative_to(skill).as_posix()}", p))
    for p in sorted(kit.rglob("*")):
        if p.is_file() and p.name != ".installed.json":
            files.append((f"kit/{p.relative_to(kit).as_posix()}", p))
    style = json.loads((skill / "style.json").read_text(encoding="utf-8"))
    meta = {"name": name, "slug": SLUG, "version": style.get("version", "1.0.0"), "built": str(date.today()),
            "approved_reference": style.get("approved_reference"),
            "install": {"skill": f".claude/skills/{SLUG}", "kit": "kit", "post": "python kit/install.py"},
            "files": {}}
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{name}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, p in files:
            b = p.read_bytes()
            meta["files"][arc] = _sha(b)
            z.writestr(f"{name}/{arc}", b)
        z.writestr(f"{name}/style_pack.json", json.dumps(meta, ensure_ascii=False, indent=1))
    return out


def install(pack: Path, root: Path = ROOT, run_installer: bool = True) -> dict:
    """Giải nén gói vào app, kiểm sha256 từng file, rồi chạy kit/install.py."""
    with zipfile.ZipFile(pack) as z:
        top = z.namelist()[0].split("/")[0]
        meta = json.loads(z.read(f"{top}/style_pack.json"))
        bad = []
        for arc, sha in meta["files"].items():
            b = z.read(f"{top}/{arc}")
            if _sha(b) != sha:
                bad.append(arc); continue
            if arc.startswith("skill/"):
                dest = root / meta["install"]["skill"] / arc[len("skill/"):]
            else:
                dest = root / meta["install"]["kit"] / arc[len("kit/"):]
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b)
    if bad:
        raise RuntimeError(f"Gói hỏng, sai sha256: {bad}")
    styles = root / "styles.json"
    reg = json.loads(styles.read_text(encoding="utf-8")) if styles.exists() else {}
    reg[meta["slug"]] = {"name": meta["name"], "version": meta["version"], "skill": meta["install"]["skill"]}
    styles.write_text(json.dumps(reg, ensure_ascii=False, indent=1), encoding="utf-8")
    result = {"name": meta["name"], "version": meta["version"], "files": len(meta["files"])}
    if run_installer:
        r = subprocess.run([sys.executable, str(root / "kit" / "install.py"), *sys.argv[3:]], cwd=root)
        result["installer_exit"] = r.returncode
    return result


def main():
    cmd, arg = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "Style Talking Head"
    if cmd == "build":
        p = build(arg)
        print(p, f"{p.stat().st_size / 1e6:.1f} MB")
    elif cmd == "import":
        print(install(Path(arg)))


if __name__ == "__main__":
    main()
