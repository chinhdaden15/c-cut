"""Trình cài tự động Talking Head Agent (macOS + Windows). Chạy được nhiều lần (idempotent).

    python kit/install.py            # kiểm tra + cài phần còn thiếu
    python kit/install.py --check    # chỉ kiểm tra, không cài
    python kit/install.py --no-whisper   # bỏ qua tải model chép lời (~3 GB) lúc này

Cài: venv + thư viện Python (bản cố định), ffmpeg (dùng sẵn nếu có), model tách nền RVM, model chép lời,
font, icon Uicons, bộ SFX đi kèm. Ghi kết quả vào kit/.installed.json.
Chỉ dùng thư viện chuẩn của Python để chạy được trước khi có venv.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "kit"
TOOLS = json.loads((KIT / "tools.json").read_text(encoding="utf-8"))
IS_WIN = os.name == "nt"
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if IS_WIN else "bin/python")
BIN = ROOT / "bin"
CHECK_ONLY = "--check" in sys.argv
report: list[tuple[str, str, str]] = []


def log(item, status, detail=""):
    report.append((item, status, detail))
    mark = {"ok": "✓", "installed": "+", "missing": "✗", "skipped": "·", "warn": "!"}.get(status, "?")
    print(f" {mark} {item:<28} {status:<9} {detail}")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "talking-head-agent-installer"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def ensure_file(item: str, dest: Path, url: str, sha: str | None):
    if dest.exists() and (not sha or sha256(dest) == sha):
        return log(item, "ok")
    if CHECK_ONLY:
        return log(item, "missing", str(dest.relative_to(ROOT)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = fetch(url)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    if sha and sha256(tmp) != sha:
        tmp.unlink()
        return log(item, "warn", "sai sha256 — không cài, kiểm tra nguồn tải")
    tmp.replace(dest)
    log(item, "installed", f"{len(data) / 1e6:.1f} MB")


# 1) Python
def step_python():
    v = sys.version_info
    lo, hi = (tuple(map(int, TOOLS["python"][k].split("."))) for k in ("min", "max"))
    if not (lo <= (v.major, v.minor) <= hi):
        hint = TOOLS["python"]["install_hint"]["windows" if IS_WIN else "macos"]
        log("python", "warn", f"{v.major}.{v.minor} ngoài {TOOLS['python']['min']}–{TOOLS['python']['max']}. Cài: {hint}")
    else:
        log("python", "ok", f"{v.major}.{v.minor}")


# 2) venv + pip
def step_venv():
    if not VPY.exists():
        if CHECK_ONLY:
            return log("venv + thư viện", "missing")
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV)])
    want = TOOLS["pip"]
    have = subprocess.run([str(VPY), "-m", "pip", "freeze"], capture_output=True, text=True).stdout.lower() if VPY.exists() else ""
    missing = [p for p in want if p.lower() not in have]
    if not missing:
        return log("venv + thư viện", "ok", f"{len(want)} gói")
    if CHECK_ONLY:
        return log("venv + thư viện", "missing", ", ".join(missing))
    subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", "--upgrade", "pip"])
    subprocess.check_call([str(VPY), "-m", "pip", "install", "-q", *missing])
    log("venv + thư viện", "installed", f"{len(missing)} gói")


# 3) ffmpeg
def _ffmpeg_ok(exe: str) -> bool:
    try:
        out = subprocess.run([exe, "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30).stdout
        return all(f in out for f in TOOLS["ffmpeg"]["needs_filters"])
    except Exception:
        return False


def step_ffmpeg():
    local = BIN / ("ffmpeg.exe" if IS_WIN else "ffmpeg")
    sys_ff = shutil.which("ffmpeg")
    if sys_ff and _ffmpeg_ok(sys_ff) and shutil.which("ffprobe"):
        return log("ffmpeg", "ok", sys_ff)
    if local.exists() and _ffmpeg_ok(str(local)):
        return log("ffmpeg", "ok", f"{local} (thêm thư mục bin/ vào PATH khi chạy — run.sh/run.bat đã làm)")
    if CHECK_ONLY:
        return log("ffmpeg", "missing", "cần ffmpeg có zscale/tonemap/loudnorm/afftdn")
    BIN.mkdir(exist_ok=True)
    dl = TOOLS["ffmpeg"]["download"]
    if IS_WIN:
        z = zipfile.ZipFile(io.BytesIO(fetch(dl["windows"]["url"])))
        for n in z.namelist():
            if Path(n).name in dl["windows"]["bins"]:
                (BIN / Path(n).name).write_bytes(z.read(n))
    elif platform.machine() == "x86_64":
        for item in dl["macos_x86_64"]:
            z = zipfile.ZipFile(io.BytesIO(fetch(item["url"])))
            (BIN / item["bin"]).write_bytes(z.read(item["bin"]))
            os.chmod(BIN / item["bin"], 0o755)
    else:
        return log("ffmpeg", "warn", dl["macos_arm64"]["hint"])
    log("ffmpeg", "installed" if _ffmpeg_ok(str(local)) else "warn", str(local))


# 4) model, font, icon
def step_assets():
    m = TOOLS["models"]["rvm"]
    ensure_file("model tách nền (RVM)", ROOT / m["path"], m["url"], m["sha256"])
    f = TOOLS["fonts"]
    for name, spec in f["files"].items():
        ensure_file(f"font {name}", ROOT / f["dir"] / name, f["base"] + spec["src"], spec["sha256"])
    ic = TOOLS["icons"]
    for name, spec in ic["files"].items():
        ensure_file(f"icon {name}", ROOT / ic["dir"] / name, ic["base"] + spec["src"], spec["sha256"])


# 5) SFX đi kèm → assets/sfx + manifest đường dẫn tương đối
def step_sfx():
    man = json.loads((KIT / "sfx" / "sfx_manifest.json").read_text(encoding="utf-8"))
    dst = ROOT / "assets" / "sfx"
    dst.mkdir(parents=True, exist_ok=True)
    mp = dst / "manifest.json"
    cur = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    n = 0
    for grp in ("approved", "alternates"):
        for key, it in man[grp].items():
            src = KIT / "sfx" / it["wav"]
            out = dst / f"{key}.wav"
            if not out.exists() and not CHECK_ONLY:
                shutil.copy2(src, out); n += 1
            cur[key] = {"file": out.name, "category": it["use"], "source": f"kit/sfx/{it['original']}",
                        "original_name": it["original_name"], "library": it["library"], "license": "thư viện SFX của người dùng",
                        "peak_offset_ms": it["peak_offset_ms"], "norm_db": it["norm_db"]}
    pools = cur.get("_pools", {})
    pools.update(man["pools"])
    cur["_pools"] = pools
    if not CHECK_ONLY:
        mp.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
    log("bộ SFX", "installed" if n else "ok", f"{len(man['approved'])} chính + {len(man['alternates'])} dự phòng")


# 6) model chép lời (lớn) — tải trước để lần dựng đầu không phải chờ
def step_whisper():
    if "--no-whisper" in sys.argv:
        return log("model chép lời large-v3", "skipped", "sẽ tự tải khi chép lời lần đầu (~3 GB)")
    if not VPY.exists():
        return log("model chép lời large-v3", "missing", "cần venv trước")
    code = ("from faster_whisper import WhisperModel;"
            "WhisperModel('large-v3', device='cpu', compute_type='int8', local_files_only=%s)" % ("True" if CHECK_ONLY else "False"))
    r = subprocess.run([str(VPY), "-c", code], capture_output=True, text=True)
    log("model chép lời large-v3", ("ok" if CHECK_ONLY else "installed") if r.returncode == 0 else ("missing" if CHECK_ONLY else "warn"),
        "" if r.returncode == 0 else r.stderr.strip().splitlines()[-1][:120])


# 7) agent (tùy chọn)
def step_agent():
    if shutil.which("claude"):
        log("Claude Code (agent)", "ok", shutil.which("claude"))
    else:
        hint = TOOLS["agent"]["claude_code"]["install_hint"]["windows" if IS_WIN else "macos"]
        log("Claude Code (agent)", "warn", f"chưa có — cài: {hint}")
    skill = ROOT / TOOLS["agent"]["skill"] / "SKILL.md"
    log("skill Talking Head Style", "ok" if skill.exists() else "missing")


def main():
    print(f"Talking Head Agent — {'KIỂM TRA' if CHECK_ONLY else 'CÀI ĐẶT'} ({platform.system()} {platform.machine()})")
    for step in (step_python, step_venv, step_ffmpeg, step_assets, step_sfx, step_whisper, step_agent):
        try:
            step()
        except Exception as e:  # không im lặng: ghi lỗi từng bước, các bước khác vẫn chạy
            log(step.__name__, "warn", f"lỗi: {e}")
    bad = [r for r in report if r[1] in ("missing", "warn")]
    (KIT / ".installed.json").write_text(json.dumps(
        {"ok": not any(r[1] == "missing" for r in report), "platform": platform.platform(),
         "items": [{"item": a, "status": b, "detail": c} for a, b, c in report]}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"== {len(report) - len(bad)} ổn, {len(bad)} cần chú ý")
    sys.exit(1 if any(r[1] == "missing" for r in report) else 0)


if __name__ == "__main__":
    main()
