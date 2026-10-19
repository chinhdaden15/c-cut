"""HyperFrames — công cụ dựng dùng chung của app (runtime ghim phiên bản + chuẩn job + chạy job + ghép lớp).

API: from thagent.hyper import run_job, doctor, Overlays
  run_job(spec, workdir, base=None, progress=print, timeout=None, check=True, force=False) -> state
  doctor() -> {ok, node, hyperframes, pinned, ffmpeg, chrome, problems}
CLI: python -m thagent.hyper (xem __main__.py). Chuẩn spec: thagent/hyper/spec.py.
"""
from .runtime import doctor  # noqa: F401


def run_job(spec, workdir, base=None, **kw):
    from .job import Job
    return Job(spec, workdir, base).run(**kw)


def __getattr__(name):
    if name == "Overlays":
        from .overlay import Overlays
        return Overlays
    raise AttributeError(name)
