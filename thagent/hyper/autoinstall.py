"""Tự cài HyperFrames nền khi mở app — người dùng không phải thao tác.

1. Node.js: máy có Node ≥ 22 → dùng; không có → tải bản Node PORTABLE chính thức (nodejs.org, bản ghim trong
   assets/hyperframes/node.json, KIỂM sha256) giải nén vào <ROOT>/tools/node (không cài vào hệ thống, không cần quyền admin).
2. HyperFrames đúng bản ghim (npm ci theo lockfile) + trình duyệt render riêng (runtime.install).
Mỗi lần mở app chạy tối đa MỘT lần; lỗi ghi vào tools/hyperframes_auto.json, lần mở sau thử lại. Tắt: CCUT_NO_AUTO_HF=1.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from ..paths import ROOT
from . import runtime

STATE = {"running": False, "stage": "", "pct": 0, "error": None}
STATE_FILE = (ROOT / "tools" / "hyperframes_auto.json").resolve()
NODE_DIR = (ROOT / "tools" / "node").resolve()
_LOCK = threading.Lock()


def _plat() -> str:
    m = platform.machine().lower()
    arm = m in ("arm64", "aarch64")
    if os.name == "nt":
        return "win-arm64" if arm else "win-x64"
    return "darwin-arm64" if arm else "darwin-x64"


def _save(**kw):
    STATE.update(kw)
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps({**STATE, "at": time.time()}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _have_node() -> bool:
    n = runtime.node_exe()
    return bool(n) and runtime._node_version(n)[0] >= runtime.NODE_MIN


def install_node(log=print) -> str:
    """tải + kiểm sha256 + giải nén Node portable vào tools/node. Trả đường dẫn node."""
    man = json.loads((runtime.PIN_DIR / "node.json").read_text(encoding="utf-8"))
    name, sha = man["files"][_plat()]
    url = man["base"] + name
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / name
        log(f"tải Node.js {man['version']} ({name})")
        h = hashlib.sha256()
        ctx = None
        try:                                              # bản đóng gói có thể thiếu chứng chỉ hệ thống → dùng certifi
            import ssl
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "C-Cut"}), timeout=60, context=ctx) as r, \
                open(f, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                out.write(b); h.update(b); got += len(b)
                if total:
                    _save(pct=round(30 * got / total))
        if h.hexdigest() != sha:
            raise RuntimeError(f"Node.js tải về sai mã kiểm tra (sha256) — bỏ, không cài: {name}")
        ex = Path(td) / "x"
        if name.endswith(".zip"):
            with zipfile.ZipFile(f) as z:
                z.extractall(ex)
        else:
            with tarfile.open(f) as t:
                t.extractall(ex, filter="data") if hasattr(tarfile, "data_filter") else t.extractall(ex)
        root = next(ex.iterdir())                         # node-vX-<plat>/
        tmp = NODE_DIR.with_name("node.part")
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.move(str(root), tmp)
        shutil.rmtree(NODE_DIR, ignore_errors=True)
        tmp.rename(NODE_DIR)
    exe = runtime.node_exe()
    if not exe or runtime._node_version(exe)[0] < runtime.NODE_MIN:
        raise RuntimeError("giải nén Node.js xong nhưng không chạy được")
    return exe


def run(log=print, force_portable_node: bool = False) -> dict:
    """cài đủ (Node nếu thiếu → HyperFrames bản ghim → trình duyệt). Trả doctor()."""
    if not _LOCK.acquire(blocking=False):
        return {"ok": False, "problems": ["đang cài"]}
    try:
        _save(running=True, error=None, stage="kiểm tra", pct=0)
        d = runtime.doctor()
        if d["ok"]:
            _save(running=False, stage="sẵn sàng", pct=100)
            return d
        if force_portable_node or not _have_node():
            _save(stage="tải Node.js")
            install_node(log)
        _save(stage="cài HyperFrames", pct=40)
        d = runtime.install(log)
        _save(running=False, stage="sẵn sàng" if d["ok"] else "lỗi", pct=100 if d["ok"] else STATE["pct"],
              error=None if d["ok"] else "; ".join(d.get("problems", []))[:400])
        return d
    except Exception as e:
        _save(running=False, stage="lỗi", error=f"{e}"[:400])
        return {"ok": False, "problems": [str(e)]}
    finally:
        try:
            from ..capabilities import _CACHE
            _CACHE.pop("hyperframes", None)             # agent thấy ngay trạng thái mới
        except Exception:
            pass
        _LOCK.release()


def start_background(log=lambda m: None):
    """gọi khi mở app: chưa sẵn sàng thì cài nền (một lần mỗi lần mở app)."""
    if os.environ.get("CCUT_NO_AUTO_HF"):
        return
    threading.Thread(target=run, kwargs={"log": log}, daemon=True, name="hyperframes-auto").start()
