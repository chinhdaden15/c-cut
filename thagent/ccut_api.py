"""API cho giao diện C-Cut: cài đặt, chọn file/thư mục (hộp thoại hệ thống), style, hàng chờ,
chạy dựng theo hàng chờ, tiến trình có %, tóm tắt dự án (ảnh tĩnh, dòng thời gian, nguồn, xác nhận)."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import traceback
import unicodedata
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import pipeline as P
from . import license as L
from . import schemadocs as SD

APP_VERSION = "1.8.1"
ROOT = P.ROOT
SETTINGS = ROOT / "ccut_settings.json"
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}   # style Voice to Motion nhận cả file âm thanh
V2M = "voice-to-motion"
REVIEW = "review-editor"
REF_DIRS = {"tham_khao", "tham khao", "thamkhao", "reference", "references", "ref", "refs"}   # thư mục con = video tham khảo phong cách
router = APIRouter(prefix="/api/ccut")
WINDOW = None   # cửa sổ webview của bản cài đặt (app_main gán) → dùng hộp thoại gốc của nó

# trọng số % cho 6 bước hiển thị
STAGES = [("ingest", "Nhập", 8), ("transcribe", "Chép lời", 22), ("matting", "Tách nền", 25),
          ("plan", "Kế hoạch", 10), ("preflight", "Kiểm tra", 5), ("render", "Xuất", 30)]
# Voice to Motion: voice (âm thanh, hoặc tiếng tách từ video) → motion graphic, xuất cả dọc lẫn ngang
STAGES_REVIEW = [("analyze", "Phân tích", 22), ("select", "Chọn cảnh", 28), ("build", "Dựng", 22), ("finish", "Hoàn thiện", 20),
                 ("check", "Kiểm tra", 4), ("export", "Xuất", 4)]
STAGES_V2M = [("ingest", "Nhập", 3), ("transcribe", "Chép lời", 20), ("clean", "Làm sạch voice", 5),
              ("plan", "Kế hoạch", 25), ("render", "Xuất dọc + ngang", 47)]
# TH2 (nhiều đoạn → 1 video): thêm 2 bước đầu
STAGES_MULTI = [("analyze", "Phân tích đoạn", 15), ("edl", "Ghép", 10), ("ingest", "Nhập", 5),
                ("transcribe", "Chép lời", 2), ("matting", "Tách nền", 20), ("plan", "Kế hoạch", 10),
                ("preflight", "Kiểm tra", 3), ("render", "Xuất", 35)]

DEFAULTS = {"project_name": "", "project_dir": str(ROOT / "projects"),
            "export_dir": str(Path.home() / "Videos" / "C-Cut"), "style": "talking-head-style",
            "build_model": "sonnet",
            "notify_sound": True, "notify_system": True,
            "review": {"category": "san_pham", "style": "truc_tiep", "intensity": "can_bang", "formats": ["9x16", "16x9"],
                       "duration": "", "subtitles": True, "notes": "", "keep": "", "remove": ""}}

STATE = {"queue": [], "job": None, "notifications": []}
WS: dict = {}     # dự án đang mở trong lần chạy app này: {"name", "dir"}; mở app lại = dự án mới


def _qfile() -> Path:
    return Path(load_settings()["project_dir"]).expanduser() / "queue.json"


def save_queue():
    try:
        _qfile().write_text(json.dumps(STATE["queue"], ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def load_queue():
    try:
        STATE["queue"] = json.loads(_qfile().read_text(encoding="utf-8"))
        for q in STATE["queue"]:
            if q["status"] == "running":
                q["status"] = "wait"        # app bị tắt giữa chừng → chạy lại từ checkpoint
    except Exception:
        STATE["queue"] = []
LOCK = threading.Lock()


# ---------------- cài đặt ----------------
def load_settings() -> dict:
    s = dict(DEFAULTS)
    if SETTINGS.exists():
        s.update(json.loads(SETTINGS.read_text(encoding="utf-8")))
    P.PROJECTS = Path(WS["dir"]) if WS else Path(s["project_dir"])
    return s


class SettingsIn(BaseModel):
    project_name: str | None = None
    project_dir: str | None = None
    export_dir: str | None = None
    style: str | None = None
    build_model: str | None = None
    notify_sound: bool | None = None
    notify_system: bool | None = None
    review: dict | None = None


@router.put("/settings")
def put_settings(body: SettingsIn):
    s = load_settings()
    s.update({k: v for k, v in body.model_dump().items() if v is not None})
    for k in ("project_dir", "export_dir"):
        Path(s[k]).expanduser().mkdir(parents=True, exist_ok=True)
    old = load_settings().get("build_model")
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    load_settings()
    if body.build_model and body.build_model != old:      # đổi model → phiên đang rảnh khởi động lại với model mới
        from . import agent as A
        for x in A.SESSIONS.values():
            if not x.busy:
                x.stop()
    return s


# ---------------- dự án (mỗi lần mở app) ----------------
def _ws_name(parent: Path, base="Dự Án Mới") -> str:
    n, name = 1, base
    while (parent / name).exists():
        n += 1; name = f"{base} {n}"
    return name


@router.get("/workspace")
def ws_get(parent: str | None = None):
    s = load_settings()
    par = Path(parent or s["project_dir"]).expanduser()
    return {"current": WS or None, "parent": str(par), "suggest": _ws_name(par)}


class WsIn(BaseModel):
    name: str
    parent: str


@router.post("/workspace")
def ws_create(body: WsIn):
    from . import agent as A
    if STATE["job"] and STATE["job"]["state"] == "running":
        raise HTTPException(409, "Đang dựng — dừng trước khi đổi dự án")
    par = Path(body.parent).expanduser()
    base = re.sub(r'[<>:"/\\|?*]', "", body.name).strip().rstrip(".") or "Dự Án Mới"
    try:
        par.mkdir(parents=True, exist_ok=True)
        name = base if not (par / base).exists() else _ws_name(par, base)
        d = par / name
        d.mkdir()
    except OSError as e:
        raise HTTPException(400, f"Không tạo được thư mục: {e}")
    A.reset_all()
    WS.update(name=name, dir=str(d))
    os.environ["CCUT_PROJECTS"] = str(d)          # các lệnh Claude chạy (design, preflight, tools…) tìm đúng dự án
    STATE.update(queue=[], job=None, notifications=[])
    s = load_settings()
    s.update(project_dir=str(par), project_name=name)
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    load_settings()
    (d / "project_info.json").write_text(json.dumps({"name": name, "created": time.strftime("%Y-%m-%d %H:%M"),
                                                     "app": APP_VERSION}, ensure_ascii=False, indent=1), encoding="utf-8")
    save_queue()
    return {"current": WS}


class RenameIn(BaseModel):
    name: str


@router.put("/workspace/name")
def ws_rename(body: RenameIn):
    """đổi tên dự án đang mở = đổi tên thư mục + sửa đường dẫn cũ ghi trong các file json/py của dự án."""
    from . import agent as A
    if not WS:
        raise HTTPException(400, "Chưa mở dự án")
    if (STATE["job"] and STATE["job"]["state"] == "running") or any(x.busy for x in A.SESSIONS.values()):
        raise HTTPException(409, "Đang dựng hoặc Claude đang làm — chờ xong rồi đổi tên")
    name = re.sub(r'[<>:"/\\|?*]', "", body.name).strip().rstrip(".")
    if not name:
        raise HTTPException(400, "Tên không hợp lệ")
    old = Path(WS["dir"])
    new = old.parent / name
    if new == old:
        return {"current": WS}
    if new.exists() and new.resolve() != old.resolve():     # cho phép chỉ đổi hoa/thường trên ổ không phân biệt
        raise HTTPException(409, f"Đã có thư mục “{name}” — chọn tên khác")
    A.reset_all()                                 # Claude giữ đường dẫn cũ → mở lại phiên (lịch sử chat vẫn còn)
    try:
        old.rename(new)
    except OSError as e:
        raise HTTPException(400, f"Không đổi được tên thư mục (có file đang mở?): {e}")
    pairs = {json.dumps(str(old), ensure_ascii=a)[1:-1]: json.dumps(str(new), ensure_ascii=a)[1:-1] for a in (False, True)}
    pairs[str(old)] = str(new)
    for f in [*new.rglob("*.json"), *new.rglob("*.py")]:
        try:
            t = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        t2 = t
        for a, b in pairs.items():
            t2 = t2.replace(a, b)
        if t2 != t:
            f.write_text(t2, encoding="utf-8")
    pj = new / "project_info.json"
    if pj.exists():
        info = json.loads(pj.read_text(encoding="utf-8"))
        info["name"] = name
        pj.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    for q in STATE["queue"]:
        for k in ("path", "output", "final"):
            if isinstance(q.get(k), str) and q[k].startswith(str(old)):
                q[k] = str(new) + q[k][len(str(old)):]
        if q.get("clips"):
            q["clips"] = [str(new) + c[len(str(old)):] if c.startswith(str(old)) else c for c in q["clips"]]
    WS.update(name=name, dir=str(new))
    os.environ["CCUT_PROJECTS"] = str(new)
    s = load_settings()
    s["project_name"] = name
    SETTINGS.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    load_settings()
    save_queue()
    return {"current": WS}


# ---------------- hộp thoại chọn file/thư mục của hệ điều hành ----------------
class PickIn(BaseModel):
    kind: str = "folder"     # folder | video | zip


@router.post("/usage/refresh")
def usage_refresh():
    from . import agent as A
    A.refresh_limits()
    return A.claude_status()


@router.post("/pick")
def pick(body: PickIn):
    if WINDOW is not None:
        import webview
        if body.kind == "folder":
            r = WINDOW.create_file_dialog(webview.FileDialog.FOLDER)
        else:
            types = {"zip": ("Zip (*.zip)",), "script": ("Kịch bản (*.txt;*.srt;*.docx;*.md)",)}.get(
                body.kind, ("Video và âm thanh (*.mov;*.mp4;*.m4v;*.mkv;*.avi;*.mts;*.MOV;*.MP4;*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg)",)
                if load_settings().get("style") in (V2M, REVIEW) else ("Video (*.mov;*.mp4;*.m4v;*.mkv;*.avi;*.mts;*.MOV;*.MP4)",))
            r = WINDOW.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
        return {"path": (r[0] if isinstance(r, (list, tuple)) else r) if r else None}
    if sys.platform == "darwin":
        if body.kind == "folder":
            script = 'POSIX path of (choose folder with prompt "Chọn thư mục")'
        else:
            types = {"zip": '{"zip"}', "script": '{"txt","srt","docx","md"}'}.get(
                body.kind, '{"public.movie","public.audio"}' if load_settings().get("style") in (V2M, REVIEW) else '{"public.movie"}')
            script = f'POSIX path of (choose file with prompt "Chọn file" of type {types})'
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    elif os.name == "nt":
        if body.kind == "folder":
            ps = ("Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "if($d.ShowDialog() -eq 'OK'){$d.SelectedPath}")
        else:
            flt = {"zip": "Zip (*.zip)|*.zip", "script": "Kịch bản|*.txt;*.srt;*.docx;*.md"}.get(
                body.kind, "Video/âm thanh|*.mov;*.mp4;*.m4v;*.mkv;*.avi;*.mts;*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg"
                if load_settings().get("style") in (V2M, REVIEW) else "Video|*.mov;*.mp4;*.m4v;*.mkv;*.avi;*.mts")
            ps = (f"Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.OpenFileDialog;"
                  f"$d.Filter='{flt}';if($d.ShowDialog() -eq 'OK'){{$d.FileName}}")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True)
    else:
        raise HTTPException(501, "Hệ điều hành chưa hỗ trợ hộp thoại")
    path = r.stdout.strip()
    return {"path": path or None}


# ---------------- video đã xuất: lưu về / mở thư mục (giống nhau trên Mac và Windows) ----------------
class OutIn(BaseModel):
    path: str


def _video_path(raw: str) -> Path:
    p = Path(raw).expanduser()
    if not p.is_file() or p.suffix.lower() not in VIDEO_EXT:
        raise HTTPException(404, "Không thấy file video")
    return p


@router.post("/output/save")
def output_save(body: OutIn):
    src = _video_path(body.path)
    dest = None
    if WINDOW is not None:
        import webview
        r = WINDOW.create_file_dialog(webview.FileDialog.SAVE, save_filename=src.name,
                                      directory=str(Path(load_settings()["export_dir"]).expanduser()))
        dest = (r[0] if isinstance(r, (list, tuple)) else r) if r else None
    elif sys.platform == "darwin":
        r = subprocess.run(["osascript", "-e", f'POSIX path of (choose file name with prompt "Lưu video" default name "{src.name}")'],
                           capture_output=True, text=True)
        dest = r.stdout.strip() or None
    elif os.name == "nt":
        ps = ("Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.SaveFileDialog;"
              f"$d.FileName='{src.name}';$d.Filter='Video|*.mp4';if($d.ShowDialog() -eq 'OK'){{$d.FileName}}")
        dest = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True).stdout.strip() or None
    if not dest:
        return {"saved": None}
    dest = Path(dest)
    if dest.suffix.lower() != src.suffix.lower():
        dest = dest.with_name(dest.name + src.suffix)
    if dest.resolve() != src.resolve():
        shutil.copy2(src, dest)
    return {"saved": str(dest)}


@router.post("/output/reveal")
def output_reveal(body: OutIn):
    p = _video_path(body.path)
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(p)])
    elif os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent)])
    return {"ok": True}


# ---------------- trạng thái công cụ ----------------
def frozen_check():
    """bản cài đặt: python/thư viện/ffmpeg/font/SFX đã nhúng sẵn — chỉ kiểm phần cần có trên máy."""
    from .paths import RES
    items = []
    add = lambda item, ok, detail="", miss="missing": items.append({"item": item, "status": "ok" if ok else miss, "detail": detail})
    ff = shutil.which("ffmpeg")
    add("ffmpeg (đi kèm)", bool(ff), ff or "")
    add("model tách nền RVM", (ROOT / "models" / "rvm_mobilenetv3_fp32.onnx").exists())
    add("font Montserrat", (ROOT / "assets" / "fonts" / "Montserrat-VF.ttf").exists())
    add("bộ SFX", any((ROOT / "assets" / "sfx").glob("*")))
    hf = Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub"
    add("model chép lời Whisper", any(hf.glob("models--Systran--faster-whisper-large-v3/snapshots/*/model.bin")),
        "tải ~3 GB ở lần chép lời đầu tiên", miss="warn")
    cl = shutil.which("claude")
    add("Claude Code", bool(cl), cl or "chưa cài — xem Hướng dẫn sử dụng")
    if os.name == "nt":
        add("Git for Windows (Claude Code cần)", bool(shutil.which("bash") or Path(r"C:\Program Files\Git\bin\bash.exe").exists()))
    (ROOT / "kit").mkdir(exist_ok=True)
    (ROOT / "kit" / ".installed.json").write_text(json.dumps(
        {"ok": all(i["status"] != "missing" for i in items), "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")


@router.post("/syscheck")
def syscheck():
    from .paths import FROZEN
    if FROZEN:
        frozen_check()
        return system_status()
    py = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(py if py.exists() else sys.executable), str(ROOT / "kit" / "install.py"), "--check"],
                   capture_output=True, text=True, cwd=ROOT)
    return system_status()


def system_status() -> dict:
    f = ROOT / "kit" / ".installed.json"
    if not f.exists():
        return {"level": "warn", "label": "Chưa kiểm tra công cụ", "items": []}
    d = json.loads(f.read_text(encoding="utf-8"))
    missing = [i for i in d["items"] if i["status"] == "missing"]
    warn = [i for i in d["items"] if i["status"] == "warn"]
    if missing:
        return {"level": "error", "label": f"Thiếu {len(missing)} công cụ", "items": d["items"]}
    if warn:
        return {"level": "warn", "label": f"{len(warn)} mục cần chú ý", "items": d["items"]}
    return {"level": "ok", "label": "Công cụ đủ", "items": d["items"]}


# ---------------- style ----------------
def list_styles() -> list[dict]:
    reg = json.loads((ROOT / "styles.json").read_text(encoding="utf-8")) if (ROOT / "styles.json").exists() else {}
    out = []
    for skill in sorted((ROOT / ".claude" / "skills").glob("*/style.json")):
        st = json.loads(skill.read_text(encoding="utf-8"))
        slug = skill.parent.name
        md = (skill.parent / "SKILL.md").read_text(encoding="utf-8")
        desc = re.search(r"description:\s*(.+)", md)
        out.append({"slug": slug, "name": reg.get(slug, {}).get("name", st.get("name", slug)),
                    "version": reg.get(slug, {}).get("version", st.get("version", "?")),
                    "summary": st.get("summary") or (desc.group(1)[:90] + "…" if desc else "")})
    return out


class PathIn(BaseModel):
    path: str


@router.post("/styles/import")
def import_style(body: PathIn):
    from .stylepack import install
    p = Path(body.path).expanduser()
    if not p.exists() or p.suffix.lower() != ".zip":
        raise HTTPException(400, "Chọn file style dạng .zip")
    try:
        res = install(p, ROOT, run_installer=True)
    except Exception as e:
        raise HTTPException(400, f"Không cài được style: {e}")
    notify("ok", f"Đã thêm {res['name']} v{res['version']}")
    return {"result": res, "styles": list_styles()}


# ---------------- hàng chờ ----------------
class PathsIn(BaseModel):
    paths: list[str]


def _media_ext() -> set:
    st = load_settings().get("style")
    return VIDEO_EXT | (AUDIO_EXT if st in (V2M, REVIEW) else set()) | (IMG_EXT if st == REVIEW else set())


def _review_files(paths: list[Path]) -> tuple[list[str], list[str]]:
    """Review: cả thư mục = MỘT review. Tư liệu dựng = mọi video/ảnh/âm thanh; thư mục con tham_khao/reference/ref = chỉ tham khảo."""
    clips, refs = [], []
    ext = VIDEO_EXT | AUDIO_EXT | IMG_EXT
    for p in paths:
        if p.is_dir():
            for x in sorted(p.rglob("*")):
                if x.is_file() and x.suffix.lower() in ext and not x.name.startswith("."):
                    (refs if any(part.lower() in REF_DIRS for part in x.relative_to(p).parts[:-1]) else clips).append(str(x))
        elif p.is_file() and p.suffix.lower() in ext:
            clips.append(str(p))
    return clips, refs


def _add_review(paths: list[Path], script: str | None = None) -> list[str]:
    clips, refs = _review_files(paths)
    if not clips:
        return []
    root = paths[0] if paths[0].is_dir() else paths[0].parent
    name = root.name if paths[0].is_dir() else Path(clips[0]).stem
    item = next((q for q in STATE["queue"] if q.get("kind") == "review" and q["path"] == str(root) and q["status"] == "wait"), None)
    if item:     # thêm tư liệu vào review đang chờ
        item["clips"] = sorted(set(item["clips"]) | set(clips)); item["refs"] = sorted(set(item.get("refs", [])) | set(refs))
        item["script"] = script or item.get("script")
    else:
        item = {"path": str(root), "name": name, "kind": "review", "clips": clips, "refs": refs, "status": "wait", "project": None, "script": script}
        STATE["queue"].append(item)
    item["meta"] = f"{len(item['clips'])} tư liệu" + (f" · {len(item['refs'])} tham khảo" if item.get("refs") else "")
    return [name]


def _add_video(f: Path, script: str | None = None) -> bool:
    if f.suffix.lower() not in _media_ext() or not f.exists() or str(f) in [q["path"] for q in STATE["queue"]]:
        return False
    try:
        if f.suffix.lower() in AUDIO_EXT:
            d = float(json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(f)],
                                                capture_output=True, text=True).stdout)["format"]["duration"])
            meta = f"{int(d // 60)}:{int(d % 60):02d} · âm thanh"
        else:
            info = P.probe_source(str(f))
            meta = f"{int(info.duration // 60)}:{int(info.duration % 60):02d} · {min(info.width, info.height)}p" + \
                (" · chỉ lấy tiếng" if load_settings().get("style") == V2M else "")
    except Exception:
        meta = "không đọc được"
    STATE["queue"].append({"path": str(f), "name": f.name, "meta": meta, "status": "wait", "project": None,
                           "script": script or None})
    return True


@router.post("/queue/add")
def queue_add(body: PathsIn):
    if load_settings().get("style") == REVIEW:     # mọi file/thư mục thả cùng lúc = một review
        added = _add_review([Path(x).expanduser() for x in body.paths]); save_queue()
        return {"added": added, "queue": STATE["queue"]}
    added = []
    for raw in body.paths:
        p = Path(raw).expanduser()
        mats = _materials(p) if p.is_dir() and load_settings().get("style") == V2M else []
        for f in (_videos(p) if p.is_dir() else [p]):
            if _add_video(f):
                if mats:
                    STATE["queue"][-1]["materials"] = mats
                added.append(f.name)
    save_queue()
    return {"added": added, "queue": STATE["queue"]}


# ---------------- thư mục: đoán loại + gán kịch bản ----------------
SCRIPT_EXT = {".txt", ".docx", ".srt", ".md"}
CAMERA_NAME = re.compile(r"^(img|dsc|dscf|mvi|vid|pxl|gx|gopr|c)[_-]?\d+$", re.I)


def _videos(d: Path) -> list[Path]:
    return sorted((x for x in d.iterdir() if x.suffix.lower() in _media_ext() and not x.name.startswith(".")),
                  key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", x.name)])


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower()).replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _materials(d: Path) -> list[str]:
    """tư liệu dùng chung cho Voice to Motion: ảnh ở thư mục gốc + mọi ảnh/video trong thư mục con (b-roll, ảnh trám)."""
    out = [x for x in d.iterdir() if x.is_file() and x.suffix.lower() in IMG_EXT and not x.name.startswith(".")]
    for sub in (x for x in d.iterdir() if x.is_dir() and not x.name.startswith(".")):
        out += [x for x in sub.rglob("*") if x.is_file() and not x.name.startswith(".")
                and x.suffix.lower() in IMG_EXT | VIDEO_EXT]
    return [str(x) for x in sorted(out)]


def _guess_mode(vids: list[Path]) -> tuple[str, str]:
    if load_settings().get("style") == REVIEW:
        return "review", "Review: cả thư mục là MỘT video review (thư mục con tham_khao/ = video tham khảo)"
    if load_settings().get("style") == V2M:
        return "separate", "Voice to Motion: mỗi file âm thanh/video là một video riêng"
    if len(vids) < 2:
        return "separate", "chỉ có 1 video"
    stems = [v.stem for v in vids]
    if all(CAMERA_NAME.match(s) for s in stems):
        return "one", "tên file mặc định của máy quay — thường là các đoạn quay cho 1 video"
    bases = {re.sub(r"(take|tk|part|phan|doan|clip|cut)?\d+$", "", _norm(s)) for s in stems}
    if len(bases) == 1 and next(iter(bases)):
        return "one", f"các file cùng tên “{stems[0]}…” đánh số liên tiếp"
    return "separate", "tên các file khác nhau"


HEADING = re.compile(r"^\s*(#+\s*.+|(video|clip|kịch bản|kich ban|kb|phần|phan|bài|bai)\s*\d+.*|\d+\s*[.)]\s*\S.{0,60})$", re.I)


def _split_shared(text: str, vids: list[Path]) -> dict[str, tuple[str, str]]:
    """Tách 1 kịch bản chung thành từng mục theo dòng tiêu đề → {tên video: (nội dung, nhãn mục)}."""
    lines = text.splitlines()
    keys = {v.name: _norm(v.stem) for v in vids}
    heads = [i for i, l in enumerate(lines) if l.strip() and (HEADING.match(l) or any(k and k in _norm(l) for k in keys.values()))
             and len(l.strip()) <= 80]
    if not heads:
        return {}
    secs = []
    for a, b in zip(heads, heads[1:] + [len(lines)]):
        body = "\n".join(lines[a + 1:b]).strip()
        if body:
            secs.append((lines[a].strip().lstrip("#").strip(), body))
    out, rest = {}, []
    for title, body in secs:
        hit = next((n for n, k in keys.items() if k and k in _norm(title) and n not in out), None)
        (out.__setitem__(hit, (body, title)) if hit else rest.append((title, body)))
    for v in vids:                       # mục không nêu tên video → gán theo thứ tự
        if v.name not in out and rest:
            title, body = rest.pop(0)
            out[v.name] = (body, title + " (theo thứ tự)")
    return out


class FolderIn(BaseModel):
    path: str


@router.post("/folder/inspect")
def folder_inspect(body: FolderIn):
    d = Path(body.path).expanduser()
    if not d.is_dir():
        raise HTTPException(400, "Không phải thư mục")
    vids = _videos(d)
    if not vids:
        raise HTTPException(400, "Thư mục không có video")
    scripts = sorted(x for x in d.iterdir() if x.suffix.lower() in SCRIPT_EXT and not x.name.startswith((".", "~$")))
    mode, reason = _guess_mode(vids)
    assign, used = {}, set()
    for v in vids:                       # 1) trùng tên file
        k = _norm(v.stem)
        sc = next((x for x in scripts if _norm(x.stem) == k), None) or \
             next((x for x in scripts if x not in used and k and (k in _norm(x.stem) or _norm(x.stem) in k)
                   and len(_norm(x.stem)) >= 3), None)
        if sc:
            used.add(sc)
            assign[v.name] = {"text": read_script(str(sc)), "source": f"theo tên file · {sc.name}"}
    shared = [x for x in scripts if x not in used]
    left = [v for v in vids if v.name not in assign]
    if left and len(shared) == 1:        # 2) một file kịch bản chung
        full = read_script(str(shared[0]))
        parts = _split_shared(full, left) if len(left) > 1 or len(vids) > 1 else {}
        for n, (txt, title) in parts.items():
            assign[n] = {"text": txt, "source": f"tách từ {shared[0].name} · mục “{title}”"}
        if not parts and len(left) == 1:
            assign[left[0].name] = {"text": full, "source": f"theo file {shared[0].name}"}
    return {"folder": str(d), "mode": mode, "reason": reason, "scripts": [x.name for x in scripts],
            "materials": len(_materials(d)) if load_settings().get("style") == V2M else 0,
            "whole_script": read_script(str(scripts[0])) if len(scripts) == 1 else None,
            "videos": [{"name": v.name, "path": str(v), "script": assign.get(v.name, {}).get("text"),
                        "source": assign.get(v.name, {}).get("source")} for v in vids]}


class FolderAddIn(BaseModel):
    path: str
    mode: str                     # separate | one
    scripts: dict[str, str | None] = {}


@router.post("/folder/add")
def folder_add(body: FolderAddIn):
    d = Path(body.path).expanduser()
    if load_settings().get("style") == REVIEW:
        if body.mode == "one":           # cả thư mục = 1 video review
            added = _add_review([d], body.scripts.get("__whole__") or next((v for v in body.scripts.values() if v), None))
        else:                            # mỗi file video = 1 video review riêng (tham_khao/ dùng chung)
            _, refs = _review_files([d])
            added = []
            for f in _videos(d):
                if f.suffix.lower() not in VIDEO_EXT or any(q["path"] == str(f) for q in STATE["queue"]):
                    continue
                STATE["queue"].append({"path": str(f), "name": f.stem, "kind": "review", "clips": [str(f)], "refs": refs,
                                       "status": "wait", "project": None, "script": body.scripts.get(f.name),
                                       "meta": "1 tư liệu" + (f" · {len(refs)} tham khảo" if refs else "")})
                added.append(f.name)
        save_queue()
        return {"added": added}
    if load_settings().get("style") == V2M:      # không có trường hợp nhiều file = 1 nội dung
        mats = _materials(d)
        added = []
        for f in _videos(d):
            if _add_video(f, body.scripts.get(f.name)):
                STATE["queue"][-1]["materials"] = mats
                added.append(f.name)
        save_queue()
        return {"added": added}
    if body.mode == "one":
        vids = _videos(d)
        if not vids or str(d) in [q["path"] for q in STATE["queue"]]:
            return {"added": []}
        dur = 0.0
        for f in vids:
            try:
                dur += P.probe_source(str(f)).duration
            except Exception:
                pass
        script = body.scripts.get("__whole__") or next((v for v in body.scripts.values() if v), None)
        STATE["queue"].append({"path": str(d), "name": d.name, "kind": "multi", "clips": [str(f) for f in vids],
                               "meta": f"{len(vids)} đoạn · {int(dur // 60)}:{int(dur % 60):02d}",
                               "status": "wait", "project": None, "script": script})
        save_queue()
        return {"added": [d.name]}
    added = [f.name for f in _videos(d) if _add_video(f, body.scripts.get(f.name))]
    save_queue()
    return {"added": added}


def read_script(path: str) -> str:
    f = Path(path).expanduser()
    if f.suffix.lower() == ".docx":
        import zipfile
        xml = zipfile.ZipFile(f).read("word/document.xml").decode("utf-8")
        xml = re.sub(r"</w:p>", "\n", xml)
        import html
        return html.unescape(re.sub(r"<[^>]+>", "", xml)).strip()
    t = f.read_text(encoding="utf-8-sig", errors="replace")
    if f.suffix.lower() == ".srt":
        t = "\n".join(l for l in t.splitlines() if l.strip() and not l.strip().isdigit() and "-->" not in l)
    return t.strip()


class ScriptIn(BaseModel):
    text: str | None = None
    path: str | None = None


@router.post("/queue/{idx}/script")
def queue_script(idx: int, body: ScriptIn):
    if not 0 <= idx < len(STATE["queue"]):
        raise HTTPException(404, "Không có video này")
    text = read_script(body.path) if body.path else (body.text or "").strip()
    item = STATE["queue"][idx]
    item["script"] = text or None
    if item.get("project"):
        _write_script(item["project"], text)
    save_queue()
    return {"chars": len(text)}


def _write_script(pid: str, text: str | None):
    f = P.PROJECTS / pid / "script.txt"
    if text:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")
    elif f.exists():
        f.unlink()


class ChannelIn(BaseModel):
    channel: str = ""      # "" = Claude tự nhận, "none" = không kênh (nền xanh), còn lại = id kênh


@router.put("/queue/{idx}/channel")
def queue_channel(idx: int, body: ChannelIn):
    from . import channels as CH
    if not 0 <= idx < len(STATE["queue"]):
        raise HTTPException(404, "Không có video này")
    item = STATE["queue"][idx]
    item["channel"] = body.channel if body.channel in CH.NAMES or body.channel == "none" else ""
    if item.get("project"):
        _apply_channel(item)
    save_queue()
    return {"ok": True}


def _apply_channel(item: dict):
    """lựa chọn của người dùng → <dự án>/channel.json (nền khóa lúc gán)."""
    from . import channels as CH
    pdir = P.PROJECTS / item["project"]
    if item.get("channel"):
        CH.assign(pdir, item["channel"], "user")
    else:
        CH.release(pdir)


@router.delete("/queue/{idx}")
def queue_remove(idx: int):
    if 0 <= idx < len(STATE["queue"]) and STATE["queue"][idx]["status"] != "running":
        STATE["queue"].pop(idx)
        save_queue()
    return {"queue": STATE["queue"]}


# ---------------- chạy dựng theo hàng chờ ----------------
def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower() or "video"


def notify(level: str, text: str):
    STATE["notifications"].append({"t": time.time(), "level": level, "text": text})
    STATE["notifications"] = STATE["notifications"][-50:]


def _progress(job: dict) -> None:
    """Cập nhật % và thời gian còn lại từ bước hiện tại + log thật của engine."""
    stages = job.get("stages") or STAGES
    done_w = sum(w for k, _, w in stages if k in job["done"])
    cur = next((x for x in stages if x[0] == job["stage"]), None)
    frac = 0.0
    if cur:
        for line in reversed(job["log"][-20:]):
            m = re.search(rf"{job['stage']} frame (\d+)(?:/(\d+))?", line)   # chỉ log của bước hiện tại
            if m:
                tot = int(m.group(2)) if m.group(2) else job.get("frames", 0)
                frac = min(int(m.group(1)) / tot, 1) if tot else 0
                break
            m = re.search(r"ASR ([\d.]+)s / ([\d.]+)s", line)
            if m:
                frac = float(m.group(1)) / float(m.group(2))
                break
    now = time.time()
    if job.get("_st") != job["stage"]:      # đổi bước → ghi thời gian bước trước vào timing.log
        if job.get("_st"):
            try:
                from . import agent as A
                with open(ROOT / "timing.log", "a", encoding="utf-8") as f:
                    f.write(f"{time.strftime('%Y-%m-%d %H:%M')}\t{job.get('project')}\t{job['_st']}\t"
                            f"{now - job['_st_t0']:.0f}s\t{load_settings().get('build_model')}\n")
            except Exception:
                pass
        job["_st"], job["_st_t0"] = job["stage"], now
    job["stage_s"] = round(now - job["_st_t0"])
    pct = done_w + (cur[2] * frac if cur else 0)
    job["percent"] = round(pct, 1)
    el = time.time() - job["t0"]
    job["eta_s"] = round(el / pct * (100 - pct)) if pct > 3 else None


def _run_multi(item: dict, pid: str, job: dict, settings: dict, log) -> Path:
    """TH2: phân tích các đoạn → Claude viết edl.json → app kiểm tra (lỗi gửi lại Claude) → ghép bản thô."""
    from . import agent as A, clips as CL
    pdir = P.PROJECTS / pid
    asm = pdir / "work" / "assembled.mov"
    CL.analyze(pid, item["clips"], log); job["done"].append("analyze")
    job["stage"] = "edl"
    _write_script(pid, item.get("script"))
    sess = A.get(pid, settings["style"])
    edl = CL.load_edl(pid)
    if edl is None:
        if not sess.messages:
            sess._add("claude", f"Đã nhận {len(item['clips'])} đoạn của {item['name']}. Mình chọn take và ghép theo kịch bản.", kind="text")
        sess.send(f"Dự án `{pid}` gồm {len(item['clips'])} đoạn quay của MỘT video (style `{settings['style']}`). "
                  "Đọc skill, clips/index.json, ảnh clips/*_sheet.jpg, clips/<đoạn>.json"
                  + (", và script.txt (kịch bản gốc — là chuẩn thứ tự + chính tả)" if item.get("script") else "")
                  + ". Viết edl.json (bước GHÉP NHIỀU ĐOẠN trong hướng dẫn hệ thống), đặt \"ready\": true khi xong. Không dừng chờ duyệt.\n"
                  "ĐỊNH DẠNG edl.json (đầy đủ, không cần tìm thêm):\n" + SD.text("edl.md"), show=False)
    tries = 0
    while True:
        item["status"] = "claude"
        while (edl := CL.load_edl(pid)) is None:
            if job["cancel"]:
                sess.stop(); raise RuntimeError("cancelled")
            job["activity"] = sess.activity
            time.sleep(2)
        item["status"] = "running"
        errs = CL.validate(pid, edl)
        if not errs:
            break
        tries += 1
        if tries > 3:
            raise RuntimeError("edl.json vẫn lỗi sau 3 lần sửa: " + "; ".join(errs[:3]))
        (pdir / "edl.json").write_text(json.dumps({**edl, "ready": False}, ensure_ascii=False, indent=1))
        sess.send("edl.json có lỗi, sửa rồi đặt lại ready=true:\n- " + "\n- ".join(errs), show=False)
    # ghép lại → bỏ kết quả cũ phụ thuộc bản thô
    if not asm.exists() or asm.stat().st_mtime < (pdir / "edl.json").stat().st_mtime:
        shutil.rmtree(pdir / "proxy", ignore_errors=True)
        for f in ("work/alpha.mp4", "work/anchors.json", "work/transcript.json", "project.json", "plan_ready.json"):
            (pdir / f).unlink(missing_ok=True)
        CL.assemble(pid, edl, log)
    job["done"].append("edl")
    return asm


def _final_path(item: dict, out_dir: Path, multi: bool) -> Path:
    """thư mục xuất chỉ nhận video thành phẩm, đặt theo tên dự án (nhiều video → thêm tên video).
    Xuất lại cùng video → ghi đè bản cũ; trùng tên file khác → thêm (2), (3)…"""
    old = Path(item["output"]) if item.get("output") else None
    if old and old.parent == out_dir:
        return old
    stem = Path(item["path"]).name if multi else Path(item["path"]).stem
    base = WS.get("name") or stem
    if len(STATE["queue"]) > 1:
        base = f"{base} - {stem}"
    base = re.sub(r'[<>:"/\\|?*]', "", base).strip().rstrip(".") or "video"
    f, n = out_dir / f"{base}.mp4", 2
    while f.exists():
        f, n = out_dir / f"{base} ({n}).mp4", n + 1
    return f


def _wait_plan(sess, item, job):
    item["status"] = "claude"
    while not sess.plan_ready():
        if job["cancel"]:
            sess.stop(); raise RuntimeError("cancelled")
        job["activity"] = sess.activity
        if not sess.busy and not sess.plan_ready():
            time.sleep(5)
            if not sess.busy and not sess.plan_ready():
                if sess.restarts >= 3:
                    raise RuntimeError("Claude dừng nhiều lần chưa xong kế hoạch — xem khung chat")
                sess.restarts += 1
                sess.send("Tiếp tục việc đang dở theo quy trình cho tới khi ghi plan_ready.json.", show=False)
        sess.watchdog()
        time.sleep(2)
    item["status"] = "running"


def _run_review(item: dict, pid: str, job: dict, settings: dict, log):
    """Review Editor: kiểm kê + phân tích → Claude chọn take/cảnh, viết review/edit.json → dựng dọc/ngang → kiểm file xuất → xuất."""
    from . import agent as A
    from .review import inventory as RI, render as RR
    L.can_start(REVIEW, pid)                    # skill bán: hết lượt thử → báo ngay, không tốn công phân tích/Claude
    _log = log

    def log(m):                 # mọi bước (phân tích, chép lời, dựng) đều báo tiến độ qua đây → bấm Dừng là dừng ngay
        if job["cancel"]:
            raise RuntimeError("cancelled")
        _log(m)
    job["stage"] = "analyze"
    pdir = P.PROJECTS / pid
    pdir.mkdir(parents=True, exist_ok=True)
    rv = {**DEFAULTS["review"], **(settings.get("review") or {})}
    (pdir / "review").mkdir(exist_ok=True)
    (pdir / "review" / "options.json").write_text(json.dumps(rv, ensure_ascii=False, indent=1), encoding="utf-8")
    sess = A.get(pid, REVIEW)
    try:
        sess.warm()
    except Exception as e:
        log(f"Không mở được Claude: {e}")
    clips = item.get("clips") or [item["path"]]
    n = len(clips)
    done = [0]

    def alog(m):
        m = str(m)
        if m.startswith("Phân tích F"):
            done[0] += 1
        log(f"analyze frame {min(done[0], n)}/{n} · {m}" if m.startswith("Phân tích") else m)
    RI.inventory(pdir, clips, alog, item.get("refs") or [], cancel=lambda: job["cancel"])
    job["done"].append("analyze"); job["stage"] = "select"
    _write_script(pid, item.get("script"))
    if not sess.plan_ready():
        if not sess.messages:
            sess._add("claude", f"Đã nhận {n} tư liệu của {item['name']}. Mình xem tư liệu, chọn take và dựng mạch review.", kind="text")
        sess.send(f"Dựng video review `{item['name']}` (dự án `{pid}`, thư mục {pdir}) theo skill review-editor. Tư liệu đã kiểm kê + phân tích "
                  f"({pdir}/review/inventory.json, ảnh tổng hợp review/sheets/). Tuỳ chọn của người dùng: {pdir}/review/options.json "
                  + (f"(lĩnh vực {rv['category']}, phong cách {rv['style']}, mức {rv['intensity']}, tỷ lệ {'+'.join(rv['formats'])}, "
                     f"thời lượng {rv['duration'] or 'tự chọn'}, phụ đề {'bật' if rv['subtitles'] else 'tắt'}). ")
                  + (f"Video tham khảo phong cách: {len(item.get('refs') or [])} file (CHỈ học cách dựng). " if item.get("refs") else "")
                  + (f"Có kịch bản người dùng: {pdir}/script.txt — bám mạch, thứ tự và chính tả theo kịch bản. " if item.get("script")
                     else "KHÔNG có kịch bản — tự dựng mạch review từ lời nói và tư liệu (chọn take tốt nhất, sắp thứ tự hợp lý). ")
                  + "Làm theo workflow rồi ghi plan_ready.json.", show=False)
        _wait_plan(sess, item, job)
    job["done"].append("select"); job["stage"] = "build"
    fmts = (sess.plan_ready() or {}).get("formats") or rv.get("formats") or ["9x16", "16x9"]

    def rlog(m):
        m = str(m)
        if m.startswith("build frame"):
            job["stage"] = "build"
        elif m.startswith("finish frame"):
            if "build" not in job["done"]:
                job["done"].append("build")
            job["stage"] = "finish"
        log(m)
    try:
        res = RR.render(pdir, fmts, rlog)
    except SystemExit as e:              # bản dựng còn lỗi → giao Claude sửa (tối đa 3 lần), không dựng lại liên tục
        (pdir / "plan_ready.json").replace(pdir / "plan_ready.rejected.json")
        item["pf_tries"] = item.get("pf_tries", 0) + 1
        if item["pf_tries"] <= 3:
            sess.send(f"App chưa dựng được, sửa review/edit.json rồi chạy check và ghi lại plan_ready.json:\n{e}", show=False)
        raise RuntimeError(f"Kiểm tra bản dựng có lỗi (lần {item['pf_tries']}/3): {str(e)[:200]}")
    for x in ("build", "finish"):
        if x not in job["done"]:
            job["done"].append(x)
    job["stage"] = "check"
    bad = [q for q in res if not q["ok"]]
    if bad:
        (pdir / "plan_ready.json").replace(pdir / "plan_ready.rejected.json")
        item["pf_tries"] = item.get("pf_tries", 0) + 1
        msg = "; ".join(f"[{q['format']}] " + " | ".join(q["errors"][:4]) for q in bad)
        if item["pf_tries"] <= 3:
            sess.send(f"File xuất chưa đạt kiểm tra — sửa edit.json, check + stills, ghi lại plan_ready.json:\n{msg}", show=False)
        raise RuntimeError(f"File xuất chưa đạt (lần {item['pf_tries']}/3): {msg[:200]}")
    item["pf_tries"] = 0
    job["done"].append("check"); job["stage"] = "export"
    out_dir = Path(settings["export_dir"]).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    base = _final_path(item, out_dir, True)
    outs = []
    for q in res:
        f = base.with_name(f"{base.stem}_{q['format']}.mp4")
        shutil.copy2(q["file"], f); outs.append(f)
    job["done"].append("export"); job["percent"] = 100
    item.update(status="done", output=str(outs[0]), outputs=[str(o) for o in outs])
    pr = pdir / "plan_ready.json"
    if pr.exists():
        pr.replace(pdir / "plan_ready.used.json")
    sess.send("Đã xuất xong. Viết review/report.md (đã làm gì, đã kiểm gì kèm kết quả qa_<tỷ lệ>.json, còn thiếu gì, âm thanh chưa nghe kiểm chứng) "
              "và tóm tắt ngắn cho người dùng.", show=False)
    notify("ok", f"Xong {item['name']} → " + ", ".join(o.name for o in outs))
    save_queue()


@router.post("/review/refs")
def review_refs(body: PathsIn):
    """thêm video tham khảo phong cách cho review đang chờ (không dùng để dựng)."""
    item = next((q for q in reversed(STATE["queue"]) if q.get("kind") == "review" and q["status"] in ("wait", "failed")), None)
    if not item:
        raise HTTPException(400, "Thêm tư liệu review trước")
    refs = [str(x) for p in body.paths for x in ([Path(p)] if Path(p).is_file() else sorted(Path(p).rglob("*")))
            if Path(x).suffix.lower() in VIDEO_EXT]
    item["refs"] = sorted(set(item.get("refs", [])) | set(refs))
    item["meta"] = f"{len(item['clips'])} tư liệu · {len(item['refs'])} tham khảo"
    save_queue()
    return {"refs": item["refs"]}


def _run_v2m(item: dict, pid: str, job: dict, settings: dict, log):
    """Voice to Motion: voice (âm thanh / tiếng của video) → chép lời → làm sạch → Claude viết timeline dọc+ngang → xuất cả hai."""
    from . import agent as A
    from .v2m import __main__ as V
    L.can_start(V2M, pid)
    pdir = P.PROJECTS / pid
    sess = A.get(pid, V2M)
    try:
        sess.warm()
    except Exception as e:
        log(f"Không mở được Claude: {e}")
    if not (pdir / "transcript.json").exists():
        log("Nhập voice" + (" (chỉ lấy tiếng của video)" if Path(item["path"]).suffix.lower() in VIDEO_EXT else ""))
        job["done"].append("ingest"); job["stage"] = "transcribe"
        V.init(item["path"], pdir, progress=log)   # "ASR x s / y s" → thanh % bước Chép lời chạy
    else:
        job["done"].append("ingest")
    job["done"].append("transcribe"); job["stage"] = "clean"
    if not (pdir / "voice_edit.json").exists():
        from .v2m import voiceprep as VP
        r = VP.clean(pdir, log=log)
        log(f"Làm sạch voice: {r['source_s']:.1f}s → {r['clean_s']:.1f}s")
    job["done"].append("clean"); job["stage"] = "plan"
    _write_script(pid, item.get("script"))
    mats = [Path(m) for m in item.get("materials") or [] if Path(m).exists()]
    if mats:   # tư liệu người dùng gửi kèm (b-roll, ảnh trám) → tu_lieu/ + ảnh xem trước cho Claude chọn đúng nội dung
        tl_dir = pdir / "tu_lieu"
        (tl_dir / "_xem").mkdir(parents=True, exist_ok=True)
        for m in mats:
            dst = tl_dir / m.name
            if not dst.exists():
                shutil.copy2(m, dst)
            if m.suffix.lower() in VIDEO_EXT and not (tl_dir / "_xem" / f"{m.stem}.jpg").exists():
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(dst), "-vf", "fps=1/2,scale=320:-1,tile=4x1",
                                "-frames:v", "1", str(tl_dir / "_xem" / f"{m.stem}.jpg")], capture_output=True)
    if not sess.plan_ready():
        if not sess.messages:
            sess._add("claude", f"Đã nhận {item['name']}. Mình dựng Motion Graphic từ voice, xuất cả dọc lẫn ngang.", kind="text")
        sess.send(f"Dựng Motion Graphic cho `{item['name']}` (dự án `{pid}`, thư mục {pdir}) theo skill voice-to-motion. "
                  "Voice đã chép lời và làm sạch. "
                  + (f"Người dùng gửi kèm {len(mats)} tư liệu (b-roll, ảnh trám) ở {pdir}/tu_lieu/ — xem trước ở tu_lieu/_xem/*.jpg "
                     "(video: 4 khung cách 2s), ưu tiên dùng khi ĐÚNG nội dung đang nói. " if mats else "")
                  + "Làm theo quy trình rồi ghi plan_ready.json.", show=False)
        _wait_plan(sess, item, job)
    job["done"].append("plan"); job["stage"] = "render"
    out_dir = Path(settings["export_dir"]).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
    fmts = [f for f in ("9x16", "16x9") if (pdir / f"timeline_{f}.json").exists()]
    want = (sess.plan_ready() or {}).get("formats")       # người dùng dặn “chỉ dọc”/“chỉ ngang” → Claude ghi vào plan_ready.json
    if want:
        fmts = [f for f in fmts if f in want]
    if not fmts:
        raise RuntimeError("Claude chưa ghi timeline_9x16.json / timeline_16x9.json")
    dur = json.loads((pdir / fmts[0].join(("timeline_", ".json"))).read_text(encoding="utf-8")).get("duration") or 60
    job["frames"] = int(float(dur) * 30)
    try:
        res = V.render(pdir, *fmts, progress=lambda m: log(str(m).replace("v2m frame", "render frame")))
    except SystemExit as e:              # lỗi timeline/QA → giao Claude sửa (tối đa 3 lần), không xuất lại liên tục
        (pdir / "plan_ready.json").replace(pdir / "plan_ready.rejected.json")
        item["pf_tries"] = item.get("pf_tries", 0) + 1
        if item["pf_tries"] <= 3:
            sess.send(f"App chưa xuất được, sửa rồi chạy lại check và ghi lại plan_ready.json:\n{e}", show=False)
        raise RuntimeError(f"Kiểm tra trước khi xuất có lỗi (lần {item['pf_tries']}/3): {str(e)[:200]}")
    item["pf_tries"] = 0
    base = _final_path(item, out_dir, False)
    outs = []
    for (video, qa), fmt in zip(res, fmts):
        f = base.with_name(f"{base.stem}_{fmt}.mp4")
        shutil.copy2(video, f); outs.append(f)
        if not qa.get("ok"):
            log(f"QA {fmt}: " + "; ".join(qa.get("errors", [])[:3]))
    job["done"].append("render"); job["percent"] = 100
    item.update(status="done", output=str(outs[0]), outputs=[str(o) for o in outs])
    pr = pdir / "plan_ready.json"
    if pr.exists():
        pr.replace(pdir / "plan_ready.used.json")
    notify("ok", f"Xong {item['name']} → " + ", ".join(o.name for o in outs))
    save_queue()


def _run_queue(settings: dict):
    job = STATE["job"]

    def log(m):
        job["log"].append(str(m)); job["log"] = job["log"][-300:]; _progress(job)
        if job["cancel"]:
            raise RuntimeError("cancelled")

    for item in STATE["queue"]:
        if item["status"] not in ("wait", "failed"):
            continue
        if job["cancel"]:
            break
        multi = item.get("kind") == "multi"
        pid = _slug(Path(item["path"]).stem if not multi else Path(item["path"]).name)
        item.update(status="running", project=pid); save_queue()
        _apply_channel(item)
        job.update(project=pid, video=item["name"], stage="analyze" if multi else "ingest", done=[], t0=time.time(),
                   percent=0, eta_s=None, stages=STAGES_MULTI if multi else STAGES)
        if settings.get("style") == REVIEW or item.get("kind") == "review":
            job["stages"] = STAGES_REVIEW
            try:
                _run_review(item, pid, job, settings, log)
            except Exception as e:
                cancelled = str(e) == "cancelled" or job["cancel"]
                item["status"] = "cancelled" if cancelled else "failed"
                item["error"] = None if cancelled else str(e)[:300]
                job["log"].append(traceback.format_exc()[-1200:])
                notify("error" if not cancelled else "warn", f"{item['name']}: {'đã hủy' if cancelled else 'lỗi ở bước ' + job['stage']}")
                if cancelled:
                    break
            continue
        if settings.get("style") == V2M and not multi:
            job["stages"] = STAGES_V2M
            try:
                _run_v2m(item, pid, job, settings, log)
            except Exception as e:
                cancelled = str(e) == "cancelled" or job["cancel"]
                item["status"] = "cancelled" if cancelled else "failed"
                item["error"] = None if cancelled else str(e)[:300]
                job["log"].append(traceback.format_exc()[-1200:])
                notify("error" if not cancelled else "warn", f"{item['name']}: {'đã hủy' if cancelled else 'lỗi ở bước ' + job['stage']}")
                if cancelled:
                    break
            continue
        c = P.Ctx(pid, log, cancel=lambda: job["cancel"])
        try:
            from . import agent as A
            L.can_start(settings.get("style") or "talking-head-style", pid)    # skill bán: hết lượt thử → báo ngay
            src = item["path"]
            if multi:
                src = str(_run_multi(item, pid, job, settings, log))
                c = P.Ctx(pid, log, cancel=lambda: job["cancel"])
                job["stage"] = "ingest"
            try:
                A.get(pid, settings["style"]).warm()     # mở sẵn Claude trong lúc app chép lời/tách nền
            except Exception as e:
                log(f"Không mở được Claude: {e}")
            P.step_ingest(c, src); job["done"].append("ingest")
            job["stage"] = "transcribe"; P.step_transcribe(c); job["done"].append("transcribe")
            job["frames"] = int(c.project.source.duration * 30)
            job["stage"] = "matting"; P.step_matting(c); job["done"].append("matting")
            if not multi:   # clip đơn: dò đoạn nhìn điện thoại/quay đi để agent che bằng MG
                from . import gaze as GZ, pointing as PT   # hướng nhìn + cử chỉ chỉ tay (để highlight vật)
                GZ.run(c); PT.run(c)
            job["stage"] = "plan"
            _write_script(pid, item.get("script"))
            sess = A.get(pid, settings["style"])
            if not sess.plan_ready():
                if multi:
                    sess.send("Bản thô đã ghép xong (work/assembled.mov, transcript đã ánh xạ). Đọc covers.json: "
                              "đoạn kind=broll/mg chỉ dùng lớp chữ front_of_subject; kind=mg và audio_only BẮT BUỘC có "
                              "Motion Graphics minh họa phủ kín. Giờ lập kế hoạch như thường, preflight, ảnh tĩnh, "
                              "rồi ghi plan_ready.json.", show=False)
                elif not sess.messages:
                    sess.send(f"Dựng video `{item['name']}` (dự án `{pid}`) theo style `{settings['style']}`. "
                              + ("Có kịch bản gốc ở script.txt — đối chiếu transcript với kịch bản trước. " if item.get("script") else "")
                              + "Bắt đầu: đọc skill + transcript, sửa lỗi chép lời (tự quyết, ghi nhật ký confirm.json — không chờ duyệt), lập kế hoạch, "
                              "preflight, ảnh tĩnh, rồi ghi plan_ready.json.", show=False)
                    sess._add("claude", f"Đã nhận video {item['name']}. Mình bắt đầu lập kế hoạch theo style.", kind="text")
                item["status"] = "claude"
                while not sess.plan_ready():          # chờ Claude; người dùng vẫn chat/góp ý trong lúc này
                    if job["cancel"]:
                        sess.stop(); raise RuntimeError("cancelled")
                    job["activity"] = sess.activity
                    if sess.denied and not sess.busy and not sess.plan_ready():
                        # bị chặn 1 lệnh không phải lỗi chết: nhắc Claude dùng đúng dạng lệnh rồi làm tiếp
                        cmd = sess.denied
                        log(f"lệnh bị chặn quyền: {cmd}")
                        if sess.denials >= 3:
                            raise RuntimeError(f"Claude bị chặn quyền nhiều lần, lệnh cuối: {cmd} — báo lỗi này cho nhà phát triển")
                        sess.denials += 1
                        sess.send(f"Lệnh vừa rồi bị chặn quyền: `{cmd}`. Chỉ dùng đúng dạng `.venv/bin/python ...` (tải ảnh: "
                                  f".venv/bin/python -m thagent.tools img {pid} <url> i_ten.jpg [nguồn]), không cd, không nối lệnh "
                                  "bằng && ; |, không tiền tố biến môi trường. Làm tiếp việc đang dở cho tới khi ghi plan_ready.json.",
                                  show=False)
                        continue
                    if not sess.busy and not sess.plan_ready():   # Claude đã dừng giữa chừng mà chưa xong → giao lại việc
                        time.sleep(5)
                        if not sess.busy and not sess.plan_ready():
                            if sess.restarts >= 3:
                                raise RuntimeError("Claude dừng nhiều lần chưa xong kế hoạch — xem khung chat")
                            sess.restarts += 1
                            sess.send("Tiếp tục việc đang dở theo quy trình cho tới khi ghi plan_ready.json.", show=False)
                    sess.watchdog()
                    time.sleep(2)
                item["status"] = "running"
            c = P.Ctx(pid, log, cancel=lambda: job["cancel"])
            job["done"].append("plan")
            job["stage"] = "preflight"
            from .preflight import check
            res = check(pid)
            errs = [m for s, m in res if s == "error"]
            job["preflight"] = res
            if errs:
                # bỏ plan_ready → không tự xuất lại liên tục; giao lỗi cho Claude sửa (tối đa 3 lần), Claude ghi lại plan_ready thì mới xuất lại
                (c.dir / "plan_ready.json").replace(c.dir / "plan_ready.rejected.json")
                item["pf_tries"] = item.get("pf_tries", 0) + 1
                if item["pf_tries"] <= 3:
                    sess.send("Preflight còn lỗi, app chưa xuất. Sửa kế hoạch cho hết lỗi, chạy lại preflight rồi ghi lại plan_ready.json:\n- "
                              + "\n- ".join(errs[:8]), show=False)
                    raise RuntimeError(f"Kiểm tra trước khi xuất có lỗi — đã gửi Claude sửa (lần {item['pf_tries']}/3): " + "; ".join(errs[:2]))
                raise RuntimeError("Kiểm tra trước khi xuất vẫn lỗi sau 3 lần Claude sửa — xem khung chat: " + "; ".join(errs[:3]))
            item["pf_tries"] = 0
            job["done"].append("preflight")
            job["stage"] = "render"
            rec = P.step_render(c, None, "ccut")
            out_dir = Path(settings["export_dir"]).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
            final = _final_path(item, out_dir, multi)
            shutil.copy2(ROOT / rec["file"], final)
            job["done"].append("render"); job["percent"] = 100
            item.update(status="done", output=str(final))
            from . import channels as CH
            CH.exported(c.dir)             # lần xuất đầu → +1 video cho kênh (15 video đổi nền)
            pr = c.dir / "plan_ready.json"
            if pr.exists():
                pr.replace(c.dir / "plan_ready.used.json")
            notify("ok", f"Xong {item['name']} → {final.name}")
        except Exception as e:
            cancelled = str(e) == "cancelled" or job["cancel"]
            item["status"] = "cancelled" if cancelled else "failed"
            item["error"] = None if cancelled else str(e)[:300]
            job["log"].append(traceback.format_exc()[-1200:])   # ghi thẳng, không qua log() (log() ném lệnh dừng)
            try:
                with open(ROOT / "error.log", "a", encoding="utf-8") as f:
                    f.write(f"\n=== {time.strftime('%Y-%m-%d %H:%M:%S')} · {item['name']} · {job['stage']}\n{traceback.format_exc()}")
            except Exception:
                pass
            for part in c.dir.rglob("*.part*"):                 # dọn file tạm dở dang
                part.unlink(missing_ok=True)
            notify("error" if not cancelled else "warn", f"{item['name']}: {'đã hủy' if cancelled else 'lỗi ở bước ' + job['stage']}")
            if cancelled:
                break
    job["state"] = "cancelled" if job["cancel"] else "done"
    save_queue()


@router.post("/start")
def start():
    with LOCK:
        if STATE["job"] and STATE["job"]["state"] == "running":
            raise HTTPException(409, "Đang dựng")
        if not WS:
            raise HTTPException(400, "Tạo dự án trước")
        if not any(q["status"] in ("wait", "failed") for q in STATE["queue"]):
            raise HTTPException(400, "Thêm video gốc trước")
        s = load_settings()
        STATE["job"] = {"state": "running", "stage": "", "done": [], "log": [], "cancel": False, "percent": 0,
                        "eta_s": None, "t0": time.time(), "confirm": []}
        threading.Thread(target=_run_queue, args=(s,), daemon=True).start()
    _ensure_watcher()
    return {"ok": True}


def _kill_children():
    """dừng ffmpeg/Claude/lệnh phụ — KHÔNG đụng tới tiến trình hiển thị cửa sổ (WebView2) kẻo trắng màn hình."""
    import psutil
    from . import agent as A
    A.stop_all()
    keep = ("webview", "msedge", "webkit", "crashpad", "conhost")
    for ch in psutil.Process().children(recursive=True):
        try:
            if not any(k in ch.name().lower() for k in keep):
                ch.kill()
        except Exception:
            pass


@router.post("/cancel")
def cancel():
    j = STATE["job"]
    if j and j["state"] == "running":
        j["cancel"] = True
        j["stage_label"] = "Đang dừng…"
        _kill_children()          # ffmpeg/ghi file đang chạy dừng ngay; bước kế tiếp sẽ thấy cờ hủy
    return {"ok": True}


# ---------------- tóm tắt dự án ----------------
def _v2m_summary(pid: str) -> dict:
    """dự án Voice to Motion (không có project.json): bản đã xuất dọc/ngang + ảnh tổng hợp cảnh của lần xuất gần nhất."""
    pdir = P.PROJECTS / pid
    q = next((q for q in reversed(STATE["queue"]) if q.get("project") == pid and q.get("outputs")), None)
    outs = [Path(o) for o in (q or {}).get("outputs", []) if Path(o).exists()]
    if not outs:
        outs = [f for f in (pdir / f"{pid}_{fmt}.mp4" for fmt in ("9x16", "16x9")) if f.exists()]
    vs = sorted((d for d in (pdir / "versions").glob("v[0-9][0-9][0-9]") if d.is_dir()), key=lambda d: d.name)
    stills = next((sorted(d.glob("sheet*.jpg")) for d in reversed(vs) if any(d.glob("sheet*.jpg"))), [])
    if not stills:
        stills = sorted(pdir.glob("stills*.jpg")) + sorted((pdir / "review").glob("stills_*.jpg"))
    lab = lambda f: "Ngang" if "16x9" in f.name else "Dọc"
    return {"id": pid, "stills": [str(f) for f in stills], "timeline": [], "counts": {}, "credits": {},
            "output": str(outs[0]) if outs else None, "final": str(outs[0]) if outs else None,
            "outputs": [{"label": lab(f), "path": str(f)} for f in outs]}


def project_summary(pid: str | None) -> dict | None:
    if pid and not (P.PROJECTS / pid / "project.json").exists() and (any((P.PROJECTS / pid).glob("timeline*.json"))
                                                                   or (P.PROJECTS / pid / "review" / "inventory.json").exists()):
        return _v2m_summary(pid)
    if not pid or not (P.PROJECTS / pid / "project.json").exists():
        return None
    c = P.Ctx(pid)
    pl = c.project.plan
    out = {"id": pid, "stills": [], "timeline": [], "counts": {}, "credits": {}, "output": None}
    if c.project.renders:
        last = c.project.renders[-1]
        vdir = (ROOT / last["file"]).parent
        for r in reversed(c.project.renders):   # lần xuất gần nhất có ảnh tĩnh (bản chỉ trộn lại tiếng không có)
            snaps = sorted((ROOT / r["file"]).parent.glob("snap_*.jpg"))
            if snaps:
                out["stills"] = [str(p) for p in snaps][:14]
                break
        out["output"] = str(ROOT / last["file"]) if not Path(last["file"]).is_absolute() else last["file"]
    # bản đã chép ra thư mục xuất (lưu về / mở thư mục dùng bản này)
    out["final"] = next((q["output"] for q in reversed(STATE["queue"]) if q.get("project") == pid and q.get("output")
                         and Path(q["output"]).exists()), None)
    if pl and pl.duration_frames:
        segs = sorted((m["start"], m["end"]) for m in pl.mg)
        prev, tl = 0, []
        for a, b in segs:
            if a > prev:
                tl.append({"kind": "talk", "len": a - prev})
            tl.append({"kind": "graphic", "len": b - a}); prev = b
        if prev < pl.duration_frames:
            tl.append({"kind": "talk", "len": pl.duration_frames - prev})
        out["timeline"] = tl
        talks = [x["len"] for x in tl if x["kind"] == "talk"]
        out["counts"] = {"text": sum(1 for g in pl.text_groups if g.enabled), "sfx": len({x.asset for x in pl.sounds}),
                         "graphic": len(pl.mg), "longest_talk_s": round(max(talks) / 30, 1) if talks else 0}
        proj = [v for v in pl.visuals if v.file]
        mg_photos = {el["file"] for m in pl.mg for sc in m["scenes"] for el in sc["elements"] if el["type"] == "photo"}
        out["credits"] = {"project_photos": len(proj), "illustrations": len([f for f in mg_photos if "assets_mg" in f or "assets_web" in f]),
                          "icons": "Uicons by Flaticon", "sfx": len({s.asset for s in pl.sounds}),
                          "lines": [f"{v.label}: {v.source}" for v in proj] + ["Icons: Uicons by Flaticon"]}
    return out


@router.get("/channels")
def channels_get():
    from . import channels as CH
    return {"every": CH.EVERY, "channels": CH.summary()}


# ---------------- bản quyền skill ----------------
_LIC = {"products": None, "at": 0.0, "syncing": False}


def _lic_sync_bg(force: bool = False):
    """đồng bộ nền (mã đã mua, lượt thử) — tối đa 10 phút/lần, không chặn giao diện."""
    if _LIC["syncing"] or (not force and time.time() - (L._load().get("synced") or 0) < 600):
        return

    def run():
        _LIC["syncing"] = True
        try:
            L.sync()
            _LIC.update(products=L.products(), at=time.time())
        except Exception:
            pass
        finally:
            _LIC["syncing"] = False
    threading.Thread(target=run, daemon=True).start()


@router.get("/license")
def license_get():
    _lic_sync_bg()
    if _LIC["products"] is None or time.time() - _LIC["at"] > 600:
        try:
            _LIC.update(products=L.products(), at=time.time())
        except Exception:
            pass
    return {**L.summary(), "products": _LIC["products"] or []}


@router.post("/license/sync")
def license_sync():
    try:
        L.sync()
    except L.LicenseError as e:
        raise HTTPException(400, str(e).replace("BẢN QUYỀN: ", ""))
    return license_get()


class LicKeyIn(BaseModel):
    key: str


@router.post("/license/activate")
def license_activate(body: LicKeyIn):
    try:
        r = L.activate(body.key)
    except L.LicenseError as e:
        raise HTTPException(400, str(e).replace("BẢN QUYỀN: ", ""))
    notify("ok", f"Đã kích hoạt {r['name']}")
    return {"result": r, **license_get()}


class LicOrderIn(BaseModel):
    product: str
    contact: str = ""


@router.post("/license/order")
def license_order(body: LicOrderIn):
    try:
        return L.order(body.product, body.contact)
    except L.LicenseError as e:
        raise HTTPException(400, str(e).replace("BẢN QUYỀN: ", ""))


@router.get("/license/order/{oid}")
def license_order_status(oid: str):
    try:
        r = L.order_status(oid)
    except L.LicenseError as e:
        raise HTTPException(400, str(e).replace("BẢN QUYỀN: ", ""))
    if r["activated"]:
        notify("ok", "Đã nhận tiền — skill đã mở khoá")
    return r


@router.get("/state")
def state(project: str | None = None):
    s = load_settings()
    if not STATE.get("_loaded"):
        STATE["_loaded"] = True; _ensure_watcher()      # mở app = phiên mới: không nạp lại hàng chờ/lịch sử cũ
    job = STATE["job"]
    pub_job = None
    if job:
        _progress(job) if job["state"] == "running" else None
        pub_job = {k: job.get(k) for k in ("state", "stage", "done", "percent", "eta_s", "stage_s", "video", "project", "activity")}
        pub_job["stages"] = [{"key": k, "label": l} for k, l, _ in (job.get("stages") or STAGES)]
        pub_job["log_tail"] = job["log"][-4:]
    pid = project or (job or {}).get("project") or next((q["project"] for q in reversed(STATE["queue"]) if q["project"]), None)
    confirms, activity, busy = [], "", False
    from . import agent as A
    usage = A.claude_status()
    if pid:
        if pid in A.SESSIONS or (P.PROJECTS / pid / "chat.json").exists():
            sess = A.get(pid, s["style"]); confirms, activity, busy = sess.confirms(), sess.activity, sess.busy
    alive = bool(pid and pid in A.SESSIONS and A.SESSIONS[pid].alive())
    from . import channels as CH
    for q in STATE["queue"]:           # kênh thực tế của video (người dùng chọn hoặc Claude tự nhận)
        q["ch_now"] = CH.info(P.PROJECTS / q["project"]).get("channel") if q.get("project") else None
    return {"app": {"name": "C-Cut", "version": APP_VERSION}, "workspace": WS or None, "settings": s,
            "claude": {"project": pid, "confirms": confirms, "activity": activity, "busy": busy, "usage": usage,
                       "alive": alive, "model": s.get("build_model") or "sonnet"}, "system": system_status(),
            "styles": list_styles(), "license": L.summary(), "queue": STATE["queue"], "job": pub_job, "project": project_summary(pid),
            "notifications": STATE["notifications"][-10:]}


# ---------------- kéo thả: nhận file (trình duyệt không cho biết đường dẫn) ----------------
from fastapi import File, UploadFile  # noqa: E402


@router.post("/upload")
async def upload(kind: str = "video", file: UploadFile = File(...)):
    s = load_settings()
    inc = P.PROJECTS / "_video_goc"
    inc.mkdir(parents=True, exist_ok=True)
    rel = Path(*[x for x in Path(file.filename).parts if x not in ("..", "/", "\\")])
    dest = inc / (rel if kind == "folder" else rel.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f, length=8 << 20)
    if kind == "style":
        return import_style(PathIn(path=str(dest)))
    if kind == "folder":
        return {"saved": str(dest)}
    return queue_add(PathsIn(paths=[str(dest)]))


# ---------------- Claude: chat, xác nhận ----------------
class ChatIn(BaseModel):
    project: str
    text: str


@router.get("/chat")
def chat_get(project: str):
    from . import agent as A
    s = load_settings()
    sess = A.get(project, s["style"])
    return {"messages": sess.messages[-200:], "busy": sess.busy, "activity": sess.activity, "confirms": sess.confirms()}


@router.post("/chat")
def chat_post(body: ChatIn):
    from . import agent as A
    s = load_settings()
    try:
        A.get(body.project, s["style"]).send(body.text)
    except Exception as e:
        raise HTTPException(400, str(e))
    _ensure_watcher()
    return {"ok": True}


class ConfirmIn(BaseModel):
    project: str
    id: str
    answer: str          # "ok" | text sửa


@router.post("/confirm")
def confirm(body: ConfirmIn):
    from . import agent as A
    s = load_settings()
    sess = A.get(body.project, s["style"])
    item = next((c for c in sess.confirms() if c["id"] == body.id), None)
    if not item:
        raise HTTPException(404)
    sess.set_confirm(body.id, "ok" if body.answer == "ok" else "edited")
    msg = (f"Mình xác nhận đúng: {item['text']}" if body.answer == "ok"
           else f"Sửa mục “{item['text']}”: {body.answer}")
    sess.send(msg)
    _ensure_watcher()
    return {"ok": True}


_WATCH = {"on": False}


def _ensure_watcher():
    """Sau khi Claude sửa theo góp ý và ghi lại plan_ready.json → app tự kiểm tra + xuất lại."""
    if _WATCH["on"]:
        return
    _WATCH["on"] = True

    def loop():
        while True:
            time.sleep(3)
            j = STATE["job"]
            if j and j["state"] == "running":
                continue
            for q in STATE["queue"]:
                if q.get("project") and (P.PROJECTS / q["project"] / "plan_ready.json").exists() and q["status"] in ("done", "failed", "claude"):
                    q["status"] = "wait"
                    notify("ok", f"Claude đã sửa xong {q['name']} — đang xuất lại")
                    start()
                    break
    threading.Thread(target=loop, daemon=True).start()
