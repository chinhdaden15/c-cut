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


def _ver() -> str:
    try:
        from thagent.ccut_api import APP_VERSION
        return APP_VERSION
    except Exception:
        return ""


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
        if hasattr(m, "__path__"):   # gói (vd thagent.v2m): chạy <gói>.__main__.main() — runpy cần get_code mà mô-đun Nuitka không có
            try:
                mm = importlib.import_module(mod + ".__main__")
            except ModuleNotFoundError:
                mm = None
            if mm is not None and hasattr(mm, "main"):
                return mm.main()
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


def _hide_consoles():
    """app không có cửa sổ console → mỗi tiến trình con (claude, ffmpeg, git…) sẽ bật một cửa sổ đen; ẩn đi."""
    import subprocess
    orig = subprocess.Popen.__init__

    def init(self, *a, **kw):
        if not kw.get("creationflags"):
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        orig(self, *a, **kw)
    subprocess.Popen.__init__ = init


_LOCK_FH = None


def _applog(home: Path, msg: str):
    """nhật ký mở/tắt app (Application Support/C-Cut/app.log) — để biết vì sao app tắt giữa phiên."""
    try:
        f = home / "app.log"
        if f.exists() and f.stat().st_size > 512_000:
            f.replace(home / "app.log.1")
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S") + f" [{os.getpid()}] {msg}\n")
    except Exception:
        pass


def _busy_reason() -> str:
    """C-Cut đang làm việc cho ai đó → lý do (rỗng = rảnh, thoát được)."""
    try:
        from thagent import ccut_api as C
        job = C.STATE.get("job")
        if job and job.get("state") in ("running", "paused"):
            return "đang dựng video"
        if any(q.get("status") in ("running", "claude", "waiting_claude", "limit") for q in C.STATE["queue"]):
            return "Claude đang làm video trong hàng chờ"
        if C.client_active(300):
            return f"{C.CLIENT['name']} đang điều khiển C-Cut qua API"
    except Exception:
        pass
    return ""


def _single_instance(home: Path) -> bool:
    """chỉ 1 cửa sổ C-Cut: đã có bản đang chạy → False (khóa tự nhả khi app tắt, kể cả bị tắt ngang)."""
    global _LOCK_FH
    try:
        _LOCK_FH = open(home / ".app.lock", "a+")
        if IS_WIN:
            import msvcrt
            _LOCK_FH.seek(0)
            msvcrt.locking(_LOCK_FH.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(_LOCK_FH.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False
    except Exception:
        return True


def run_app():
    if IS_WIN:
        _hide_consoles()
    res, home = setup_env()
    if not _single_instance(home):
        _applog(home, "đã có C-Cut khác đang chạy → thoát bản mới mở")
        sys.exit(0)
    _applog(home, f"mở app (python {sys.version.split()[0]})")
    try:                                        # app chết ngang (lỗi C) → vẫn có dấu vết
        import faulthandler
        faulthandler.enable(open(home / "crash.log", "a"))
    except Exception:
        pass
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
    if port != 8765:
        _applog(home, f"cổng 8765 bận → dùng {port}")
    try:                                        # app khác (CN.AI…) đọc file này để biết C-Cut đang ở cổng nào
        (home / "api.json").write_text(json.dumps({"url": f"http://127.0.0.1:{port}/api/ccut", "port": port, "pid": os.getpid(),
                                                   "started": time.strftime("%Y-%m-%d %H:%M:%S"),
                                                   "auth_header": "X-CCut-Key", "version": _ver()}), encoding="utf-8")
    except Exception:
        pass
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(200):
        if srv.started:
            break
        time.sleep(0.05)
    if sys.platform == "win32":              # mã nhận diện cố định = lối tắt Start/ghim → taskbar luôn lấy biểu tượng của bản cài mới nhất
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("vn.ccut.app")
        except Exception:
            pass
    win = webview.create_window(APP_NAME, f"http://127.0.0.1:{port}", width=1440, height=900, min_size=(1100, 700),
                                text_select=True)
    ccut_api.WINDOW = win

    def _on_closing():
        why = _busy_reason()
        if not why:
            _applog(home, "người dùng đóng cửa sổ")
            return True
        try:
            ok = win.create_confirmation_dialog("Thoát C-Cut?", f"C-Cut {why}. Thoát bây giờ sẽ làm dở việc đó. Vẫn thoát?")
        except Exception:
            ok = True
        _applog(home, f"đóng cửa sổ khi {why} → {'thoát' if ok else 'ở lại'}")
        return bool(ok)
    try:
        win.events.closing += _on_closing
    except Exception:
        pass
    threading.Thread(target=lambda: ccut_api.reap_orphans(lambda m: _applog(home, m)), daemon=True).start()
    try:                                        # công cụ dựng dùng chung: chưa sẵn sàng → tự cài nền (Node portable + HyperFrames)
        from thagent.hyper.autoinstall import start_background
        start_background()
    except Exception:
        pass
    from thagent import agent
    agent.limits_loop()   # làm mới giới hạn Claude khi mở app + mỗi 15 phút
    try:
        webview.start()
    except BaseException as e:
        _applog(home, f"cửa sổ lỗi: {e!r}")
        raise
    finally:
        _applog(home, "tắt app")
        try:
            (home / "api.json").unlink(missing_ok=True)
        except Exception:
            pass
        try:                                    # Claude / ffmpeg / dựng hình đang chạy dừng theo app (không chạy mồ côi)
            ccut_api._kill_children()
        except Exception:
            pass
    srv.should_exit = True


def _mp_child(args: list[str]) -> bool:
    """thư viện (tqdm…) bật tiến trình phụ của multiprocessing bằng chính file chạy của app
    (`C-Cut -B -s -c "from multiprocessing.resource_tracker import main…"`) → không được mở cửa sổ app."""
    return "--multiprocessing-fork" in args or ("-c" in args and any("multiprocessing" in a for a in args))


def main():
    import multiprocessing
    multiprocessing.freeze_support()
    if (Path(sys.executable).stem.lower() == "ccut-py" or (len(sys.argv) > 1 and sys.argv[1] == "--py")
            or _mp_child(sys.argv[1:])):
        setup_env()
        args = sys.argv[1:]
        if args and args[0] == "--py":
            args = args[1:]
        run_py(args)
    else:
        run_app()


if __name__ == "__main__":
    main()
