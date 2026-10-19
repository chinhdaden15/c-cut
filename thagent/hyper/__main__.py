"""HyperFrames — công cụ dựng dùng chung của app C-Cut (mọi skill video).

  python -m thagent.hyper doctor                 kiểm Node/HyperFrames (bản ghim)/ffmpeg/Chrome — JSON
  python -m thagent.hyper install                cài đúng bản ghim (npm ci theo lockfile) vào <app>/tools/hyperframes
  python -m thagent.hyper validate <spec.json>   kiểm spec (không dựng)
  python -m thagent.hyper compose  <spec.json> [workdir]        chỉ dựng dự án HTML (để xem/sửa)
  python -m thagent.hyper stills   <spec.json> t1 t2 … [--workdir D]   ảnh khung tại các giây → <job>/stills/*.png (Read để xem)
  python -m thagent.hyper render   <spec.json> [--workdir D] [--force] [--no-check] [--timeout S]
                                                 kiểm → lint → check → render → kiểm file xuất; in state JSON
  python -m thagent.hyper render-dir <dự_án_HF> --output out.mov [--format mov] [--fps 30]   dự án HyperFrames tự viết
  python -m thagent.hyper status   <job_dir>     trạng thái job
  python -m thagent.hyper cancel   <job_dir>     huỷ job đang render
  python -m thagent.hyper preview  <spec.json|dự_án>   mở Studio xem trước (cần màn hình)
  python -m thagent.hyper selftest [out_dir]     bài thử ngắn (chữ tiếng Việt, alpha, fps, thời lượng)

Spec: docstring thagent/hyper/spec.py. Workdir mặc định: thư mục chứa spec / hf_jobs.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _spec(p):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")), p.parent


def _opt(args, name, default=None, flag=False):
    if name in args:
        i = args.index(name)
        if flag:
            args.pop(i); return True
        v = args[i + 1]; del args[i:i + 2]; return v
    return default


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    if not a:
        print(__doc__); return 0
    cmd = a.pop(0)
    from . import runtime
    if cmd == "doctor":
        d = runtime.doctor(); print(json.dumps(d, ensure_ascii=False, indent=1)); return 0 if d["ok"] else 2
    if cmd == "install":
        d = runtime.install(); print(json.dumps(d, ensure_ascii=False, indent=1)); return 0 if d["ok"] else 2
    if cmd == "validate":
        from . import spec as S
        sp, base = _spec(a[0]); s = S.normalize(sp, base)
        probs = S.validate(s)
        for lv, m in probs:
            print(f"[{lv}] {m}")
        print(f"{sum(lv == 'error' for lv, _ in probs)} lỗi · job {s['job_id']} · {s['width']}x{s['height']} {s['fps']}fps {s['duration']}s")
        return 1 if any(lv == "error" for lv, _ in probs) else 0
    if cmd in ("compose", "stills", "render", "preview"):
        from .job import Job, HyperError
        wd = _opt(a, "--workdir")
        force = _opt(a, "--force", flag=True)
        nocheck = _opt(a, "--no-check", flag=True)
        tmo = _opt(a, "--timeout")
        target = Path(a.pop(0))
        if cmd == "preview" and target.is_dir():
            return runtime.run_cli(["preview", "."], cwd=target, timeout=10 ** 6).returncode
        sp, base = _spec(target)
        j = Job(sp, Path(wd) if wd else base / "hf_jobs", base)
        if cmd == "compose":
            from . import compose
            print(compose.build(j.spec, j.dir / "project")); return 0
        if cmd == "stills":
            from . import compose
            compose.build(j.spec, j.dir / "project")
            ts = ",".join(a) or "0.5"
            r = runtime.run_cli(["snapshot", "--at", ts, "."], cwd=j.dir / "project", timeout=300)
            print(r.stdout[-1500:] or r.stderr[-1500:])
            return r.returncode
        if cmd == "preview":
            from . import compose
            compose.build(j.spec, j.dir / "project")
            return runtime.run_cli(["preview", "."], cwd=j.dir / "project", timeout=10 ** 6).returncode
        try:
            st = j.run(progress=lambda m: print(m, file=sys.stderr, flush=True), timeout=float(tmo) if tmo else None,
                       check=not nocheck, force=bool(force))
        except HyperError as e:
            print(json.dumps({"ok": False, "error": str(e), **e.state}, ensure_ascii=False, indent=1)); return 1
        print(json.dumps({"ok": True, **st}, ensure_ascii=False, indent=1)); return 0
    if cmd == "render-dir":
        out = _opt(a, "--output"); fmt = _opt(a, "--format", "mov"); fps = _opt(a, "--fps", "30")
        d = Path(a.pop(0))
        lint = runtime.run_cli(["lint", "--json", "."], cwd=d, timeout=120)
        print(lint.stdout[-2000:])
        r = runtime.run_cli(["render", "--format", fmt, "--fps", fps, "--output", str(Path(out).resolve()), "--strict", "--quiet", "."],
                            cwd=d, timeout=3600)
        print((r.stdout + r.stderr)[-2000:])
        return r.returncode
    if cmd == "status":
        p = Path(a[0]) / "state.json"
        print(p.read_text(encoding="utf-8") if p.exists() else "{}"); return 0
    if cmd == "cancel":
        from .job import cancel
        cancel(Path(a[0])); print("đã gửi lệnh huỷ"); return 0
    if cmd == "selftest":
        from .selftest import run
        return run(Path(a[0]) if a else None)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
