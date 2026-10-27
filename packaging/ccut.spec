# PyInstaller spec — C-Cut (macOS .app / Windows thư mục cài đặt). Chạy: pyinstaller packaging/ccut.spec
# thagent đã biên dịch thành mô-đun gốc bằng Nuitka (build/nuitka) → không kèm mã nguồn .py.
import os, sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
NK = os.path.join(ROOT, "build", "nuitka")
RES = os.path.join(ROOT, "build", "res")
VERSION = os.environ.get("CCUT_VERSION", "1.1")

datas, binaries, hidden = [], [], []
for pkg in ("faster_whisper", "ctranslate2", "onnxruntime", "mediapipe", "webview", "tokenizers", "av",
            "vieneu", "vieneu_utils", "sea_g2p", "kaldi_native_fbank", "soxr", "soundfile", "arabic_reshaper",
            "pyvi", "sklearn_crfsuite", "pycrfsuite"):     # pyvi: tách từ tiếng Việt cho phụ đề từng từ (mô hình đi kèm gói)
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
if sys.platform == "win32":
    for pkg in ("pythonnet", "clr_loader"):
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hidden += h
    hidden += ["clr"]
for pkg in ("fastapi", "starlette", "uvicorn", "pydantic", "pydantic_core", "anyio", "multipart", "huggingface_hub",
            "noisereduce", "scipy.signal", "PIL", "psutil", "h11", "httpx", "cv2", "yt_dlp"):
    hidden += collect_submodules(pkg)
# stdlib mà design.py / script do Claude viết hay dùng
hidden += ["json", "re", "math", "random", "statistics", "itertools", "functools", "collections", "dataclasses",
           "datetime", "bisect", "copy", "csv", "glob", "html", "textwrap", "string", "unicodedata", "wave", "zipfile",
           "tarfile", "urllib.request", "urllib.parse", "argparse", "pprint", "tempfile", "uuid", "hashlib", "base64",
           "difflib", "fractions", "decimal", "shlex", "runpy", "importlib", "typing", "enum", "struct", "colorsys",
           "concurrent.futures", "subprocess", "sqlite3", "xml.etree.ElementTree", "email", "logging"]
nk = [f for f in os.listdir(NK) if f.startswith("thagent.") and f.endswith((".so", ".pyd"))]
assert nk, "chưa biên dịch thagent bằng Nuitka"
binaries += [(os.path.join(NK, nk[0]), ".")]
datas += [(os.path.join(RES, "web"), "web"), (os.path.join(RES, "seed"), "seed"), (os.path.join(RES, "bin"), "bin")]

a = Analysis([os.path.join(SPECPATH, "launch.py")], pathex=[NK], binaries=binaries, datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "jax", "jaxlib", "IPython", "pytest", "thagent.anthropic"],
             noarchive=False)
pyz = PYZ(a.pure)
UTF8 = [("X utf8_mode=1", None, "OPTION")]   # đọc/ghi file + subprocess luôn UTF-8 (Windows mặc định cp1252)
app_exe = EXE(pyz, a.scripts, UTF8, exclude_binaries=True, name="C-Cut", console=False,
              icon=os.path.join(SPECPATH, "icon.icns" if sys.platform == "darwin" else "icon.ico"))
py_exe = EXE(pyz, a.scripts, UTF8, exclude_binaries=True, name="ccut-py", console=True)
coll = COLLECT(app_exe, py_exe, a.binaries, a.datas, name="C-Cut")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="C-Cut.app", icon=os.path.join(SPECPATH, "icon.icns"), bundle_identifier="vn.ccut.app",
                 info_plist={"CFBundleShortVersionString": VERSION, "CFBundleVersion": VERSION,
                             "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0"})
