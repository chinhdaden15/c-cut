"""Thiết lập lần đầu: kiểm Claude Code (đã cài / đã đăng nhập), Git for Windows, tải model chép lời Whisper.
Các nút cài/đăng nhập mở cửa sổ terminal hiện rõ lệnh để người dùng thấy và làm theo."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/ccut/setup")
IS_WIN = os.name == "nt"
WHISPER_REPO = "Systran/faster-whisper-large-v3"
WHISPER_BYTES = 3_090_835_702          # tổng dung lượng các file của model
DL = {"running": False, "error": None}

CMDS = {
    "claude_install": "irm https://claude.ai/install.ps1 | iex" if IS_WIN else "curl -fsSL https://claude.ai/install.sh | bash",
    "claude_login": "claude auth login",
    "git_install": "winget install --id Git.Git -e --source winget",
    # HyperFrames (công cụ dựng dùng chung, tuỳ chọn) cần Node.js ≥ 22
    "node_install": "winget install --id OpenJS.NodeJS.LTS -e --source winget" if IS_WIN else "brew install node@22 && brew link --overwrite --force node@22",
}


def _hub() -> Path:
    return Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"


def _whisper_dir() -> Path:
    return _hub() / ("models--" + WHISPER_REPO.replace("/", "--"))


def whisper_ready() -> bool:
    return any(_whisper_dir().glob("snapshots/*/model.bin"))


def _claude() -> dict:
    exe = shutil.which("claude")
    if not exe:
        return {"installed": False, "logged_in": False}
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, timeout=20)
        js = json.loads(r.stdout)
        logged, email = bool(js.get("loggedIn")), js.get("email")
    except Exception:
        logged, email = False, None
    return {"installed": True, "logged_in": logged, "email": email, "path": exe}


def _git_ok() -> bool:
    return not IS_WIN or bool(shutil.which("bash") or Path(r"C:\Program Files\Git\bin\bash.exe").exists())


@router.get("")
def status():
    from .paths import FROZEN
    d = _whisper_dir()
    have = sum(f.lstat().st_size for f in (d / "blobs").glob("*")) if (d / "blobs").exists() else 0
    cl = _claude()
    st = {"frozen": FROZEN, "os": "windows" if IS_WIN else "mac", "claude": cl, "git": _git_ok(),
          "whisper": {"ready": whisper_ready(), "running": DL["running"], "error": DL["error"],
                      "pct": 100 if whisper_ready() else min(99, round(100 * have / WHISPER_BYTES))},
          "cmds": CMDS, "hyperframes": _hf_status()}
    st["done"] = cl["installed"] and cl["logged_in"] and st["git"] and st["whisper"]["ready"]
    return st


def _download():
    try:
        from huggingface_hub import snapshot_download
        snapshot_download(WHISPER_REPO)
        DL["error"] = None
    except Exception as e:
        DL["error"] = f"Tải lỗi: {e}"[:300]
    finally:
        DL["running"] = False


def _hf_status() -> dict:
    """công cụ dựng dùng chung HyperFrames — TUỲ CHỌN (không chặn thiết lập lần đầu)."""
    try:
        from .hyper.runtime import doctor
        d = doctor()
    except Exception as e:
        d = {"ok": False, "problems": [str(e)]}
    from .hyper.autoinstall import STATE
    return {"ok": d.get("ok"), "version": d.get("hyperframes"), "pinned": (d.get("pinned") or {}).get("hyperframes"),
            "node": d.get("node"), "problems": d.get("problems", []), "running": STATE["running"], "stage": STATE["stage"],
            "pct": STATE["pct"], "error": STATE["error"]}


@router.post("/hyperframes")
def start_hyperframes():
    """cài ngay (như lúc mở app): Node portable nếu thiếu → HyperFrames bản ghim → trình duyệt. Không nâng phiên bản."""
    from .hyper.autoinstall import STATE, run
    if not STATE["running"]:
        STATE["running"] = True
        threading.Thread(target=run, daemon=True, name="hyperframes-manual").start()
    return status()


@router.post("/whisper")
def start_whisper():
    if not DL["running"] and not whisper_ready():
        DL.update(running=True, error=None)
        threading.Thread(target=_download, daemon=True).start()
    return status()


@router.post("/claude_logout")
def claude_logout():
    """đổi tài khoản Claude: đăng xuất tài khoản hiện tại, dừng mọi phiên Claude của app, mở cửa sổ đăng nhập tài khoản khác."""
    from . import agent as A
    exe = shutil.which("claude")
    if not exe:
        raise HTTPException(400, "Chưa cài Claude")
    A.reset_all()
    subprocess.run([exe, "auth", "logout"], capture_output=True, text=True, timeout=30,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    run_in_terminal("claude_login")
    return status()


@router.post("/run/{key}")
def run_in_terminal(key: str):
    """mở terminal của hệ điều hành chạy lệnh cài/đăng nhập để người dùng thấy và trả lời."""
    cmd = CMDS.get(key)
    if not cmd:
        raise HTTPException(404)
    if IS_WIN:
        if key == "claude_install":
            subprocess.Popen(["powershell", "-NoExit", "-Command", cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            subprocess.Popen(["cmd", "/k", cmd], creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif sys.platform == "darwin":
        sh = Path(tempfile.gettempdir()) / f"ccut_{key}.command"
        path = os.environ.get("PATH", "")
        sh.write_text(f'#!/bin/zsh\nexport PATH="$HOME/.local/bin:{path}"\necho "C-Cut › {cmd}"\n{cmd}\n'
                      'echo\necho "Xong — quay lại C-Cut bấm Kiểm tra lại. Có thể đóng cửa sổ này."\n')
        sh.chmod(0o755)
        subprocess.Popen(["open", "-a", "Terminal", str(sh)])
    else:
        raise HTTPException(501)
    return {"ok": True}
