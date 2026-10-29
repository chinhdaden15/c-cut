"""Tự cập nhật app: hỏi GitHub Releases (gồm cả bản pre-release), có bản mới thì hỏi người dùng →
tải file cài đúng máy → cài im lặng → mở lại app. Dữ liệu, dự án, model giữ nguyên."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/ccut/update")
REPO = "chinhdaden15/c-cut-releases"
IS_WIN = os.name == "nt"
ST = {"checked": 0, "latest": None, "running": False, "pct": 0, "error": None, "stage": ""}


def _ver(v: str) -> tuple:
    return tuple(int(x) for x in "".join(ch for ch in v if ch.isdigit() or ch == ".").split(".") if x)


def _asset_name() -> str:
    if IS_WIN:
        return "C-Cut-Setup.exe"
    return "C-Cut-mac-arm64.dmg" if platform.machine() == "arm64" else "C-Cut-mac-intel.dmg"


def _get(url: str, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "C-Cut", "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def _latest_web() -> dict | None:
    """bản mới nhất qua trang release (không qua API → không dính giới hạn 60 lần/giờ mỗi mạng)."""
    r = _get(f"https://github.com/{REPO}/releases/latest")
    tag = r.geturl().rstrip("/").rsplit("/", 1)[-1]
    if not tag.startswith("v"):
        return None
    url = f"https://github.com/{REPO}/releases/download/{tag}/{_asset_name()}"
    h = urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers={"User-Agent": "C-Cut"}), timeout=15)
    return {"version": tag.lstrip("v"), "notes": "", "url": url, "size": int(h.headers.get("Content-Length") or 0)}


def _latest_api() -> dict | None:
    rels = json.load(_get(f"https://api.github.com/repos/{REPO}/releases?per_page=10"))
    rels = [r for r in rels if not r.get("draft")]
    best = max(rels, key=lambda r: _ver(r["tag_name"]), default=None)
    if not best:
        return None
    a = next((x for x in best.get("assets", []) if x["name"] == _asset_name()), None)
    return {"version": best["tag_name"].lstrip("v"), "notes": (best.get("body") or "")[:1500],
            "url": a and a["browser_download_url"], "size": a and a["size"]}


def check(force=False) -> dict:
    from .ccut_api import APP_VERSION
    if force or time.time() - ST["checked"] > 1800:
        err = None
        for f in (_latest_web, _latest_api):
            try:
                L = f()
                if L:
                    ST["latest"], err = L, None
                    break
            except Exception as e:
                err = f"Không kiểm tra được bản mới: {e}"[:200]
        ST["checked"], ST["error"] = (time.time() if err is None else ST["checked"]), err
    L = ST["latest"]
    avail = bool(L and L["url"] and _ver(L["version"]) > _ver(APP_VERSION))
    return {"current": APP_VERSION, "available": avail, "latest": L, "running": ST["running"], "pct": ST["pct"],
            "stage": ST["stage"], "error": ST["error"]}


def _download(url: str, size: int) -> Path:
    out = Path(tempfile.gettempdir()) / ("ccut_update_" + url.rsplit("/", 1)[-1])
    part = out.with_suffix(out.suffix + ".part")
    got = 0
    with _get(url, timeout=60) as r, open(part, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk); got += len(chunk)
            ST["pct"] = min(99, int(100 * got / max(size or 1, 1)))
    if size and got != size:
        raise RuntimeError(f"tải thiếu ({got}/{size} byte)")
    part.replace(out)
    return out


def _quit_app():
    from . import ccut_api
    time.sleep(1.0)
    try:
        ccut_api.WINDOW.destroy()
    except Exception:
        pass
    os._exit(0)


def _install(path: Path):
    if IS_WIN:
        # chạy qua `start` để bộ cài không là tiến trình con (bộ cài sẽ taskkill cây C-Cut.exe)
        subprocess.Popen(f'cmd /c start "" "{path}" /SILENT /SUPPRESSMSGBOXES /NORESTART',
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    else:
        exe = Path(sys.executable).resolve()
        app = next((p for p in exe.parents if p.suffix == ".app"), Path("/Applications/C-Cut.app"))
        sh = Path(tempfile.gettempdir()) / "ccut_update.sh"
        sh.write_text(f"""#!/bin/zsh
while kill -0 {os.getpid()} 2>/dev/null; do sleep 0.5; done
MNT=$(mktemp -d)
hdiutil attach -nobrowse -quiet -mountpoint "$MNT" "{path}" || exit 1
SRC=$(ls -d "$MNT"/*.app | head -1)
rm -rf "{app}.old"; mv "{app}" "{app}.old" && ditto "$SRC" "{app}" && rm -rf "{app}.old" || mv "{app}.old" "{app}"
hdiutil detach -quiet "$MNT"
xattr -dr com.apple.quarantine "{app}" 2>/dev/null
rm -f "{path}"
open "{app}"
""", encoding="utf-8")
        sh.chmod(0o755)
        subprocess.Popen(["/bin/zsh", str(sh)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _quit_app()


def _run():
    try:
        L = ST["latest"]
        ST.update(stage="Đang tải bản " + L["version"], pct=0)
        path = _download(L["url"], L["size"])
        ST.update(stage="Đang cài — app sẽ tự mở lại", pct=100)
        _install(path)
    except Exception as e:
        ST.update(error=f"Cập nhật lỗi: {e}"[:300], running=False, stage="")


@router.get("")
def status(force: bool = False):
    return check(force)


@router.post("")
def start():
    from .paths import FROZEN
    st = check()
    if not st["available"]:
        raise HTTPException(400, "Đang dùng bản mới nhất")
    if not FROZEN:
        raise HTTPException(400, "Bản chạy từ mã nguồn — không tự cập nhật")
    if not ST["running"]:
        ST.update(running=True, error=None)
        threading.Thread(target=_run, daemon=True).start()
    return check()
