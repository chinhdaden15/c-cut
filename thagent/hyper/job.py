"""Chạy một job HyperFrames: spec → kiểm → dựng dự án → lint → check (trình duyệt) → render → kiểm file xuất.

Mỗi job một thư mục làm việc riêng <workdir>/<job_id>/ với state.json (trạng thái, bước, tiến độ, số lần thử, mã băm, lỗi,
log). Đã render thành công với CÙNG mã băm nội dung → trả kết quả cũ, không render lại. Thử lại tối đa MAX_ATTEMPTS lần
chỉ với lỗi render tạm thời (không thử lại lỗi spec/lint). Có timeout và huỷ (file CANCEL hoặc `python -m thagent.hyper cancel`).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from . import compose, runtime, spec as S

MAX_ATTEMPTS = 2
CHECK_TIMEOUT = 240


class HyperError(RuntimeError):
    def __init__(self, msg: str, state: dict | None = None):
        super().__init__(msg)
        self.state = state or {}


def _probe(p: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,pix_fmt,width,height,r_frame_rate"
                        ":format=duration", "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        d = json.loads(r.stdout)
    except Exception:
        return {}
    v = next((x for x in d.get("streams", []) if x.get("codec_type") == "video"), {})
    a = next((x for x in d.get("streams", []) if x.get("codec_type") == "audio"), None)
    num, _, den = (v.get("r_frame_rate") or "0/1").partition("/")
    return {"width": v.get("width"), "height": v.get("height"), "codec": v.get("codec_name"), "pix_fmt": v.get("pix_fmt"),
            "fps": round(float(num) / float(den or 1), 3) if num else None, "duration": float(d.get("format", {}).get("duration", 0) or 0),
            "audio": a.get("codec_name") if a else None}


class Job:
    def __init__(self, spec: dict, workdir: Path, base: Path | None = None):
        self.spec = S.normalize(spec, base)
        self.dir = Path(workdir) / re.sub(r"[^A-Za-z0-9_.-]", "_", self.spec["job_id"])
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.dir / "state.json"
        self.log_path = self.dir / "render.log"
        self.proc: subprocess.Popen | None = None

    # ---------- trạng thái ----------
    def state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}

    def _save(self, **kw):
        st = self.state()
        st.update(kw, job_id=self.spec["job_id"], updated=time.time())
        self.state_path.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        return st

    def cancelled(self) -> bool:
        return (self.dir / "CANCEL").exists()

    # ---------- chạy ----------
    def run(self, progress=print, timeout: float | None = None, check: bool = True, force: bool = False) -> dict:
        s = self.spec
        out = Path(s["output"]["path"])
        h = S.content_hash(s)
        st = self.state()
        if not force and st.get("status") == "done" and st.get("hash") == h and out.exists():
            progress(f"hyperframes {s['job_id']}: dùng lại kết quả đã render ({out.name})")
            return st
        (self.dir / "CANCEL").unlink(missing_ok=True)
        self._save(status="running", stage="validate", progress=0, hash=h, output=str(out), error=None, attempts=0,
                   started=time.time(), log=str(self.log_path), spec=str(self.dir / "project" / "job.spec.json"))
        probs = S.validate(s)
        errs = [m for lv, m in probs if lv == "error"]
        if errs:
            raise HyperError("spec lỗi: " + " | ".join(errs), self._save(status="failed", stage="validate", error=errs,
                                                                          warnings=[m for lv, m in probs if lv == "warn"]))
        doc = runtime.doctor()
        if not doc["ok"]:
            raise HyperError("HyperFrames chưa sẵn sàng: " + "; ".join(doc["problems"]),
                             self._save(status="blocked", stage="doctor", error=doc["problems"]))
        proj = self.dir / "project"
        self._save(stage="compose")
        compose.build(s, proj)
        self._save(stage="lint")
        r = runtime.run_cli(["lint", "--json", "."], cwd=proj, timeout=120)
        lint = _json(r.stdout)
        (self.dir / "lint.json").write_text(json.dumps(lint, ensure_ascii=False, indent=1), encoding="utf-8")
        if not lint or lint.get("errorCount", 1) > 0:
            raise HyperError("lint lỗi: " + json.dumps((lint or {}).get("findings", r.stderr[-500:]), ensure_ascii=False)[:800],
                             self._save(status="failed", stage="lint", error=lint))
        if check:
            self._save(stage="check")
            args = ["check", "--json", "--no-contrast", "--samples", "7", "."]
            if s["background"] != "transparent":
                args.remove("--no-contrast")
            r = runtime.run_cli(args, cwd=proj, timeout=CHECK_TIMEOUT)
            chk = _json(r.stdout) or {"ok": False, "raw": (r.stdout + r.stderr)[-1500:]}
            (self.dir / "check.json").write_text(json.dumps(chk, ensure_ascii=False, indent=1), encoding="utf-8")
            if not chk.get("ok"):
                raise HyperError("check (trình duyệt) báo lỗi — xem " + str(self.dir / "check.json") + ": " + _brief(chk),
                                 self._save(status="failed", stage="check", error=_brief(chk)))
        T = float(s["duration"])
        tmo = timeout or max(180.0, T * 40 + 120)
        last = None
        for k in range(1, MAX_ATTEMPTS + 1):
            if self.cancelled():
                raise HyperError("đã huỷ", self._save(status="cancelled", stage="render"))
            self._save(stage="render", attempts=k)
            try:
                self._render(proj, out, tmo, progress)
                break
            except HyperError as e:
                last = e
                if "huỷ" in str(e) or k == MAX_ATTEMPTS:
                    raise HyperError(str(e), self._save(status="cancelled" if "huỷ" in str(e) else "failed", stage="render",
                                                        error=str(e)))
                progress(f"hyperframes {s['job_id']}: render lỗi, thử lại lần {k + 1}: {e}")
        self._save(stage="verify")
        info = _probe(out) if out.is_file() else {"frames": len(list(out.glob("*.png"))) if out.exists() else 0}
        problems = []
        if out.is_file():
            if info.get("width") != int(s["width"]) or info.get("height") != int(s["height"]):
                problems.append(f"kích thước ra {info.get('width')}x{info.get('height')} ≠ {s['width']}x{s['height']}")
            if info.get("fps") and abs(info["fps"] - float(s["fps"])) > 0.01:
                problems.append(f"fps ra {info['fps']} ≠ {s['fps']}")
            if abs(info.get("duration", 0) - T) > 1.5 / float(s["fps"]) + 0.05:
                problems.append(f"thời lượng ra {info.get('duration'):.3f}s ≠ {T:.3f}s")
            if s["output"]["format"] == "mov" and "a" not in str(info.get("pix_fmt", ""))[:5]:
                problems.append(f"mov không có kênh alpha ({info.get('pix_fmt')})")
            if s.get("audio") and s["output"]["format"] == "mp4" and not info.get("audio"):
                problems.append("có audio đầu vào nhưng file ra không có tiếng")
        if problems:
            raise HyperError("file xuất không đạt: " + "; ".join(problems), self._save(status="failed", stage="verify", error=problems, probe=info))
        return self._save(status="done", stage="done", progress=100, probe=info, finished=time.time())

    def _render(self, proj: Path, out: Path, tmo: float, progress):
        s = self.spec
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(out.stem + ".part" + (out.suffix or ""))
        if tmp.exists():
            shutil.rmtree(tmp) if tmp.is_dir() else tmp.unlink()
        args = [*runtime.cli_cmd(), "render", "--format", s["output"]["format"], "--fps", str(int(s["fps"])),
                "--quality", s["output"].get("quality", "looks"), "--output", str(tmp), "--strict", "."]
        if s["output"].get("workers"):
            args[2:2] = ["--workers", str(int(s["output"]["workers"]))]
        n_frames = int(round(float(s["duration"]) * float(s["fps"])))
        t0 = time.time()
        with open(self.log_path, "a", encoding="utf-8") as log:
            log.write(f"\n=== render {time.ctime()} ===\n{' '.join(args)}\n")
            self.proc = subprocess.Popen(args, cwd=proj, env=runtime.env(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0,
                                         text=True, bufsize=1, start_new_session=os.name != "nt", encoding="utf-8", errors="replace")
            self._save(pid=self.proc.pid)
            killer = threading.Timer(tmo, self._kill)
            killer.start()
            try:
                for line in self.proc.stdout:
                    log.write(line)
                    pct = None
                    if line.startswith("@hf-progress"):          # dòng tiến độ máy đọc của HyperFrames
                        try:
                            pct = float(json.loads(line.split(" ", 1)[1]).get("pct"))
                        except Exception:
                            pct = None
                    if pct is not None:
                        pct = min(99.0, pct)
                        self._save(progress=round(pct, 1))
                        progress(f"hyperframes frame {int(pct * n_frames / 100)}/{n_frames}")
                    if self.cancelled():
                        self._kill()
                rc = self.proc.wait()
            finally:
                killer.cancel()
        if self.cancelled():
            raise HyperError("đã huỷ")
        if time.time() - t0 >= tmo - 1:
            raise HyperError(f"quá thời gian {tmo:.0f}s")
        if rc != 0 or not tmp.exists():
            tail = self.log_path.read_text(encoding="utf-8", errors="ignore")[-1200:]
            raise HyperError(f"render thoát mã {rc}: {tail}")
        if out.exists():
            shutil.rmtree(out) if out.is_dir() else out.unlink()
        tmp.rename(out)

    def _kill(self):
        if self.proc and self.proc.poll() is None:
            _kill_tree(self.proc.pid)


def _json(txt: str):
    try:
        return json.loads(txt[txt.index("{"):])
    except Exception:
        return None


def _brief(chk: dict) -> str:
    out = []
    for sec in ("lint", "runtime", "layout", "motion", "contrast"):
        v = chk.get(sec)
        items = v.get("findings", []) if isinstance(v, dict) else (v if isinstance(v, list) else [])
        for f in items[:6]:
            if f.get("severity", "error") == "error":
                out.append(f"{sec}:{f.get('code')}:{(f.get('message') or '')[:140]}")
    return " | ".join(out)[:1200] or json.dumps(chk, ensure_ascii=False)[:600]


def run(spec: dict, workdir: Path, base: Path | None = None, **kw) -> dict:
    return Job(spec, workdir, base).run(**kw)


def _kill_tree(pid: int):
    """dừng cả cây tiến trình (node + các Chrome render). Windows: taskkill /T; mac/Linux: nhóm tiến trình."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, timeout=30)
        else:
            os.killpg(pid, signal.SIGTERM)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception:
            pass


def cancel(job_dir: Path) -> bool:
    jd = Path(job_dir)
    (jd / "CANCEL").write_text("1")
    st = json.loads((jd / "state.json").read_text()) if (jd / "state.json").exists() else {}
    if st.get("pid") and st.get("status") == "running":
        _kill_tree(int(st["pid"]))
    return True
