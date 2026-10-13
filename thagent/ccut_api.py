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

APP_VERSION = "1.2.2"
ROOT = P.ROOT
SETTINGS = ROOT / "ccut_settings.json"
VIDEO_EXT = {".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts"}
router = APIRouter(prefix="/api/ccut")
WINDOW = None   # cửa sổ webview của bản cài đặt (app_main gán) → dùng hộp thoại gốc của nó

# trọng số % cho 6 bước hiển thị
STAGES = [("ingest", "Nhập", 8), ("transcribe", "Chép lời", 22), ("matting", "Tách nền", 25),
          ("plan", "Kế hoạch", 10), ("preflight", "Kiểm tra", 5), ("render", "Xuất", 30)]
# TH2 (nhiều đoạn → 1 video): thêm 2 bước đầu
STAGES_MULTI = [("analyze", "Phân tích đoạn", 15), ("edl", "Ghép", 10), ("ingest", "Nhập", 5),
                ("transcribe", "Chép lời", 2), ("matting", "Tách nền", 20), ("plan", "Kế hoạch", 10),
                ("preflight", "Kiểm tra", 3), ("render", "Xuất", 35)]

DEFAULTS = {"project_name": "", "project_dir": str(ROOT / "projects"),
            "export_dir": str(Path.home() / "Videos" / "C-Cut"), "style": "talking-head-style",
            "build_model": "sonnet",
            "notify_sound": True, "notify_system": True}

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
                body.kind, ("Video (*.mov;*.mp4;*.m4v;*.mkv;*.avi;*.mts;*.MOV;*.MP4)",))
            r = WINDOW.create_file_dialog(webview.FileDialog.OPEN, file_types=types)
        return {"path": (r[0] if isinstance(r, (list, tuple)) else r) if r else None}
    if sys.platform == "darwin":
        if body.kind == "folder":
            script = 'POSIX path of (choose folder with prompt "Chọn thư mục")'
        else:
            types = {"zip": '{"zip"}', "script": '{"txt","srt","docx","md"}'}.get(body.kind, '{"public.movie"}')
            script = f'POSIX path of (choose file with prompt "Chọn file" of type {types})'
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    elif os.name == "nt":
        if body.kind == "folder":
            ps = ("Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.FolderBrowserDialog;"
                  "if($d.ShowDialog() -eq 'OK'){$d.SelectedPath}")
        else:
            flt = {"zip": "Zip (*.zip)|*.zip", "script": "Kịch bản|*.txt;*.srt;*.docx;*.md"}.get(
                body.kind, "Video|*.mov;*.mp4;*.m4v;*.mkv;*.avi;*.mts")
            ps = (f"Add-Type -AssemblyName System.Windows.Forms;$d=New-Object System.Windows.Forms.OpenFileDialog;"
                  f"$d.Filter='{flt}';if($d.ShowDialog() -eq 'OK'){{$d.FileName}}")
        r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps], capture_output=True, text=True)
    else:
        raise HTTPException(501, "Hệ điều hành chưa hỗ trợ hộp thoại")
    path = r.stdout.strip()
    return {"path": path or None}


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


def _add_video(f: Path, script: str | None = None) -> bool:
    if f.suffix.lower() not in VIDEO_EXT or not f.exists() or str(f) in [q["path"] for q in STATE["queue"]]:
        return False
    try:
        info = P.probe_source(str(f))
        meta = f"{int(info.duration // 60)}:{int(info.duration % 60):02d} · {min(info.width, info.height)}p"
    except Exception:
        meta = "không đọc được"
    STATE["queue"].append({"path": str(f), "name": f.name, "meta": meta, "status": "wait", "project": None,
                           "script": script or None})
    return True


@router.post("/queue/add")
def queue_add(body: PathsIn):
    added = []
    for raw in body.paths:
        p = Path(raw).expanduser()
        for f in (_videos(p) if p.is_dir() else [p]):
            if _add_video(f):
                added.append(f.name)
    save_queue()
    return {"added": added, "queue": STATE["queue"]}


# ---------------- thư mục: đoán loại + gán kịch bản ----------------
SCRIPT_EXT = {".txt", ".docx", ".srt", ".md"}
CAMERA_NAME = re.compile(r"^(img|dsc|dscf|mvi|vid|pxl|gx|gopr|c)[_-]?\d+$", re.I)


def _videos(d: Path) -> list[Path]:
    return sorted((x for x in d.iterdir() if x.suffix.lower() in VIDEO_EXT and not x.name.startswith(".")),
                  key=lambda x: [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", x.name)])


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower()).replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", "", "".join(c for c in t if unicodedata.category(c) != "Mn"))


def _guess_mode(vids: list[Path]) -> tuple[str, str]:
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
                  + ". Viết edl.json theo schema trong thagent/clips.py (bước GHÉP NHIỀU ĐOẠN trong hướng dẫn hệ thống), "
                  "đặt \"ready\": true khi xong. Không dừng chờ duyệt.", show=False)
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
        job.update(project=pid, video=item["name"], stage="analyze" if multi else "ingest", done=[], t0=time.time(),
                   percent=0, eta_s=None, stages=STAGES_MULTI if multi else STAGES)
        c = P.Ctx(pid, log, cancel=lambda: job["cancel"])
        try:
            from . import agent as A
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
                raise RuntimeError("Kiểm tra trước khi xuất có lỗi: " + "; ".join(errs[:3]))
            job["done"].append("preflight")
            job["stage"] = "render"
            rec = P.step_render(c, None, "ccut")
            out_dir = Path(settings["export_dir"]).expanduser(); out_dir.mkdir(parents=True, exist_ok=True)
            final = out_dir / f"{Path(item['path']).name if multi else Path(item['path']).stem}_C-Cut.mp4"
            shutil.copy2(ROOT / rec["file"], final)
            job["done"].append("render"); job["percent"] = 100
            item.update(status="done", output=str(final))
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
def project_summary(pid: str | None) -> dict | None:
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
    return {"app": {"name": "C-Cut", "version": APP_VERSION}, "workspace": WS or None, "settings": s,
            "claude": {"project": pid, "confirms": confirms, "activity": activity, "busy": busy, "usage": usage,
                       "alive": alive, "model": s.get("build_model") or "sonnet"}, "system": system_status(),
            "styles": list_styles(), "queue": STATE["queue"], "job": pub_job, "project": project_summary(pid),
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
