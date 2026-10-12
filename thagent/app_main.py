"""Điểm vào của bản cài đặt C-Cut (đã biên dịch).

  C-Cut                 → mở cửa sổ app (server cục bộ 127.0.0.1 + webview)
  ccut-py <args>        → thay cho `python` để Claude chạy design.py / -m thagent.preflight … bằng runtime đi kèm
"""
from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import shutil
import socket
import sys
import threading
import time
import zipfile
from pathlib import Path

APP_NAME = "C-Cut"
IS_WIN = os.name == "nt"
_K = b"c-cut/talking-head/\x9a\x17\xe4\x03pack"


def _xor(data: bytes) -> bytes:
    """mã hóa/giải mã gói skill (dòng khóa sha256 theo bộ đếm)."""
    out = bytearray(len(data))
    for i in range(0, len(data), 32):
        ks = hashlib.sha256(_K + i.to_bytes(8, "little")).digest()
        chunk = data[i:i + 32]
        out[i:i + len(chunk)] = bytes(a ^ b for a, b in zip(chunk, ks))
    return bytes(out)


def res_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def home_dir() -> Path:
    if IS_WIN:
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return base / APP_NAME


def setup_env():
    res, home = res_dir(), Path(os.environ.get("CCUT_HOME") or home_dir())
    home.mkdir(parents=True, exist_ok=True)
    os.environ["CCUT_RES"], os.environ["CCUT_HOME"] = str(res), str(home)
    extra = [str(res / "bin"), str(home / "bin")]
    hm = Path.home()
    if IS_WIN:
        extra += [str(hm / ".local" / "bin"), os.path.expandvars(r"%APPDATA%\npm"), r"C:\Program Files\nodejs",
                  r"C:\Program Files\Git\bin"]
    else:
        extra += [str(hm / ".local" / "bin"), str(hm / ".claude" / "local"), str(hm / ".npm-global" / "bin"),
                  "/opt/homebrew/bin", "/usr/local/bin"]
    os.environ["PATH"] = os.pathsep.join(extra + [os.environ.get("PATH", "")])
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    return res, home


def seed(res: Path, home: Path):
    """chép tài nguyên đi kèm vào thư mục dữ liệu (lần đầu hoặc khi đổi phiên bản); không động vào dự án/cài đặt."""
    src = res / "seed"
    ver = (src / "VERSION").read_text().strip()
    mark = home / ".seed_version"
    if not (mark.exists() and mark.read_text().strip() == ver):
        for name in ("assets", "models", "kit"):
            if (src / name).exists():
                shutil.copytree(src / name, home / name, dirs_exist_ok=True)
        shutil.copy2(src / "styles.json", home / "styles.json")
        with zipfile.ZipFile(io.BytesIO(_xor((src / "skill.bin").read_bytes()))) as z:
            for n in z.namelist():
                dst = home / n
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(z.read(n))
        mark.write_text(ver)
    (home / "projects").mkdir(exist_ok=True)
    # `.venv/bin/python` cho Claude → trỏ về runtime đi kèm (sh chạy được cả macOS lẫn Git Bash trên Windows)
    exe = Path(sys.executable).with_name("ccut-py.exe" if IS_WIN else "ccut-py")
    shim = home / ".venv" / "bin" / "python"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(f'#!/bin/sh\nexec "{exe.as_posix()}" "$@"\n', newline="\n")
    shim.chmod(0o755)


def run_py(argv: list[str]):
    """mô phỏng `python [-u] (-m mod | -c code | script) args…`."""
    while argv and argv[0] in ("-u", "-I", "-B", "-X", "-E", "-s"):
        argv = argv[1:]
    for p in reversed([p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]):
        sys.path.insert(0, os.path.abspath(p))
    sys.path.insert(0, os.getcwd())
    if not argv:
        sys.exit("ccut-py: cần script hoặc -m module")
    if argv[0] == "-m":
        mod = argv[1]
        sys.argv = [mod, *argv[2:]]
        m = importlib.import_module(mod)
        if hasattr(m, "main"):
            return m.main()
        import runpy
        return runpy.run_module(mod, run_name="__main__", alter_sys=True)
    if argv[0] == "-c":
        sys.argv = ["-c", *argv[2:]]
        return exec(compile(argv[1], "<string>", "exec"), {"__name__": "__main__"})
    import runpy
    sys.argv = list(argv)
    sys.path.insert(0, os.path.dirname(os.path.abspath(argv[0])))
    runpy.run_path(argv[0], run_name="__main__")


def _free_port(start=8765) -> int:
    for port in range(start, start + 50):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("không còn cổng trống")


def _force_utf8():
    """Windows mặc định cp1252 → lỗi khi ghi chữ tiếng Việt. Ép UTF-8 cho đọc/ghi file và subprocess."""
    import builtins
    import pathlib
    import subprocess
    if sys.flags.utf8_mode:
        return
    rt, wt, op = pathlib.Path.read_text, pathlib.Path.write_text, builtins.open

    def read_text(self, encoding=None, errors=None, *a, **kw):
        return rt(self, encoding or "utf-8", errors, *a, **kw)

    def write_text(self, data, encoding=None, errors=None, *a, **kw):
        return wt(self, data, encoding or "utf-8", errors, *a, **kw)

    def open_(file, mode="r", buffering=-1, encoding=None, *a, **kw):
        if "b" not in mode and encoding is None:
            encoding = "utf-8"
        return op(file, mode, buffering, encoding, *a, **kw)
    pathlib.Path.read_text, pathlib.Path.write_text, builtins.open = read_text, write_text, open_
    orig = subprocess.Popen.__init__

    def init(self, *a, **kw):
        if (kw.get("text") or kw.get("universal_newlines")) and not kw.get("encoding"):
            kw["encoding"] = "utf-8"
            kw.setdefault("errors", "replace")
        orig(self, *a, **kw)
    subprocess.Popen.__init__ = init
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _hide_consoles():
    """app không có cửa sổ console → mỗi tiến trình con (claude, ffmpeg, git…) sẽ bật một cửa sổ đen; ẩn đi."""
    import subprocess
    orig = subprocess.Popen.__init__

    def init(self, *a, **kw):
        if not kw.get("creationflags"):
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        orig(self, *a, **kw)
    subprocess.Popen.__init__ = init


def run_app():
    if IS_WIN:
        _hide_consoles()
    res, home = setup_env()
    seed(res, home)
    os.chdir(home)
    import uvicorn
    import webview
    from thagent import ccut_api, server
    try:
        ccut_api.frozen_check()
    except Exception:
        pass

    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        if srv.started:
            break
        time.sleep(0.05)
    win = webview.create_window(APP_NAME, f"http://127.0.0.1:{port}", width=1440, height=900, min_size=(1100, 700),
                                text_select=True)
    ccut_api.WINDOW = win
    webview.start()
    srv.should_exit = True


def main():
    if IS_WIN:
        _force_utf8()
    if Path(sys.executable).stem.lower() == "ccut-py" or (len(sys.argv) > 1 and sys.argv[1] == "--py"):
        setup_env()
        args = sys.argv[1:]
        if args and args[0] == "--py":
            args = args[1:]
        run_py(args)
    else:
        run_app()


if __name__ == "__main__":
    main()
