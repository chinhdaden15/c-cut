"""Gom tài nguyên đi kèm bản cài đặt → build/res/{web, seed/…, bin/}. Skill được mã hóa thành seed/skill.bin.
    python packaging/build_seed.py [--ffmpeg-dir DIR]"""
import hashlib, io, shutil, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from thagent.app_main import _xor
from thagent.ccut_api import APP_VERSION

OUT = ROOT / "build" / "res"
IGN = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", ".installed.json")


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    seed = OUT / "seed"
    shutil.copytree(ROOT / "web", OUT / "web", ignore=IGN)
    shutil.copytree(ROOT / "assets", seed / "assets", ignore=IGN)
    shutil.copytree(ROOT / "models", seed / "models", ignore=IGN)
    shutil.copytree(ROOT / "kit", seed / "kit", ignore=IGN)
    for junk in (seed / "kit").rglob("*"):
        if junk.name in ("install.py", ".installed.json", ".DS_Store") or "__pycache__" in junk.parts:
            shutil.rmtree(junk) if junk.is_dir() else junk.unlink(missing_ok=True)
    shutil.copy2(ROOT / "styles.json", seed / "styles.json")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted((ROOT / ".claude" / "skills").rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.name != ".DS_Store":
                z.write(f, f.relative_to(ROOT).as_posix())
    (seed / "skill.bin").write_bytes(_xor(buf.getvalue()))
    (seed / "VERSION").write_text(f"{APP_VERSION}+{hashlib.sha256(buf.getvalue()).hexdigest()[:12]}")
    ff = Path(sys.argv[sys.argv.index("--ffmpeg-dir") + 1]) if "--ffmpeg-dir" in sys.argv else None
    (OUT / "bin").mkdir()
    for b in ("ffmpeg", "ffprobe"):
        name = b + (".exe" if sys.platform == "win32" else "")
        src = (ff / name) if ff else Path(shutil.which(b) or "")
        if not src.is_file():
            sys.exit(f"thiếu {name} — truyền --ffmpeg-dir")
        shutil.copy2(src, OUT / "bin" / name)
    print("seed ok →", OUT)


if __name__ == "__main__":
    main()
