"""Điểm khởi động (không biên dịch Nuitka) — chạy trước mọi import của thagent."""
import os


def _force_utf8():
    """Windows mặc định cp1252 → lỗi khi ghi chữ tiếng Việt. Ép UTF-8 cho đọc/ghi file và subprocess."""
    import builtins
    import pathlib
    import subprocess
    import sys
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


if os.name == "nt":
    _force_utf8()

from thagent.app_main import main

main()
