"""Web UI cục bộ (chỉ bind 127.0.0.1). Job chạy trong thread nền, có hủy/retry từ checkpoint."""
from __future__ import annotations

import shutil
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import pipeline as P
from .schema import Plan, VisualAsset

app = FastAPI(title="C-Cut")


@app.middleware("http")
async def _api_client(request, call_next):
    """app khác (vd CN.AI) điều khiển C-Cut: gửi header X-CCut-Client: <tên>.
    Ghi nhận lần gọi gần nhất (giữ app không thoát ngang) và gắn tên nguồn vào việc mới thêm vào hàng chờ."""
    from . import ccut_api as C
    who = (request.headers.get("x-ccut-client") or "").strip()[:40]
    path = request.url.path
    track = bool(who) and path.startswith("/api/ccut") and request.method == "POST" and "/workspace" not in path
    before = list(C.STATE["queue"]) if track else None
    resp = await call_next(request)
    if who and path.startswith("/api/ccut"):
        import time as _t
        C.CLIENT.update(name=who, at=_t.time())
        if track:
            ids = {id(x) for x in before}
            new = [x for x in C.STATE["queue"] if id(x) not in ids]
            for x in new:
                x.setdefault("source", who)
            if new:
                C.save_queue()
    return resp
from .ccut_api import router as ccut_router, load_settings
app.include_router(ccut_router)
from .setup_api import router as setup_router
app.include_router(setup_router)
from .updater import router as update_router
app.include_router(update_router)
load_settings()
from .paths import RES
WEB = RES / "web"
JOBS: dict[str, dict] = {}


class RunReq(BaseModel):
    steps: list[str] = ["ingest", "transcribe", "matting", "plan", "render"]
    source: str | None = None
    frame_start: int | None = None
    frame_end: int | None = None
    label: str = "preview"
    replan: bool = False


def _job(pid: str, req: RunReq):
    jid = uuid.uuid4().hex[:8]
    job = {"id": jid, "project": pid, "state": "running", "stage": "", "log": [], "cancel": False, "result": None}
    JOBS[jid] = job

    def log(m):
        job["log"].append(str(m)); job["log"] = job["log"][-200:]

    def work():
        c = P.Ctx(pid, log, cancel=lambda: job["cancel"])
        try:
            for st in req.steps:
                job["stage"] = st
                if job["cancel"]:
                    raise RuntimeError("cancelled")
                if st == "ingest":
                    P.step_ingest(c, req.source or c.project.source.path)
                elif st == "transcribe":
                    P.step_transcribe(c)
                elif st == "matting":
                    P.step_matting(c)
                elif st == "plan":
                    P.step_plan(c, force=req.replan)
                elif st == "render":
                    fr = (req.frame_start, req.frame_end) if req.frame_end else None
                    job["result"] = P.step_render(c, fr, req.label)
            job["state"] = "done"
        except Exception as e:
            job["state"] = "cancelled" if str(e) == "cancelled" else "failed"
            log(traceback.format_exc()[-1500:])
            c.project.status = "cancelled" if job["state"] == "cancelled" else "failed"
            c.save()

    threading.Thread(target=work, daemon=True).start()
    return job


@app.get("/api/projects")
def projects():
    return sorted(p.name for p in P.PROJECTS.glob("*") if (p / "project.json").exists())


@app.post("/api/projects/{pid}/upload")
async def upload(pid: str, role: str = "source", file: UploadFile = File(...)):
    c = P.Ctx(pid)
    dest = c.path("uploads", role, Path(file.filename).name)
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    if role == "source":
        c.project.source = P.probe_source(str(dest))
    elif role == "reference":
        c.project.reference = str(dest)
    else:
        c.project.assets.append(VisualAsset(id=uuid.uuid4().hex[:6], file=str(dest), role=role))
    c.save()
    return {"path": str(dest)}


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    c = P.Ctx(pid)
    if not (c.dir / "project.json").exists():
        raise HTTPException(404)
    return c.project.model_dump()


@app.put("/api/projects/{pid}/plan")
def put_plan(pid: str, plan: Plan):
    c = P.Ctx(pid)
    c.project.plan = plan
    c.save()
    return {"ok": True}


class WordEdit(BaseModel):
    id: str
    text: str


@app.put("/api/projects/{pid}/words")
def edit_words(pid: str, edits: list[WordEdit]):
    c = P.Ctx(pid)
    m = {w.id: w for w in c.project.words}
    for e in edits:
        m[e.id].text = e.text
        m[e.id].needs_review = False
    c.save()
    return {"ok": True}


@app.post("/api/projects/{pid}/run")
def run(pid: str, req: RunReq):
    if any(j["project"] == pid and j["state"] == "running" for j in JOBS.values()):
        raise HTTPException(409, "Project đang có job chạy")
    return {k: v for k, v in _job(pid, req).items() if k != "cancel"}


@app.get("/api/jobs/{jid}")
def job(jid: str):
    return {k: v for k, v in JOBS[jid].items() if k != "cancel"}


@app.post("/api/jobs/{jid}/cancel")
def cancel(jid: str):
    JOBS[jid]["cancel"] = True
    return {"ok": True}


@app.get("/files/{path:path}")
def files(path: str):
    p = (P.ROOT / path).resolve()
    if not str(p).startswith(str(P.PROJECTS.resolve())) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/ccut/file")
def ccut_file(p: str):
    """File xem trước/kết quả: chỉ trong thư mục dự án hoặc thư mục xuất."""
    s = load_settings()
    f = Path(p).expanduser().resolve()
    from .ccut_api import export_dir
    ex = export_dir(s)
    allowed = [Path(s["project_dir"]).expanduser().resolve(), ex.resolve(), ex.parent.resolve(), P.ROOT.resolve(),
               Path(str(s.get("export_dir_global") or s["export_dir"]).replace("{date}", "")).expanduser().resolve()]
    if not f.exists() or not any(str(f).startswith(str(a)) for a in allowed):
        raise HTTPException(404)
    return FileResponse(f)


(P.ROOT / "assets" / "backgrounds").mkdir(parents=True, exist_ok=True)
app.mount("/backgrounds", StaticFiles(directory=P.ROOT / "assets" / "backgrounds"), name="backgrounds")
app.mount("/fonts", StaticFiles(directory=P.ROOT / "assets" / "fonts"), name="fonts")
app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
