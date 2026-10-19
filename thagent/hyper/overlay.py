"""Ghép lớp HyperFrames (clip có alpha) vào bộ dựng của skill — bộ dựng của skill SỞ HỮU timeline cuối, HyperFrames chỉ
render đúng đoạn/lớp cần (một lần), không render lại cả video.

- Overlays(items, W, H, fps): mỗi item {"path": clip.mov, "start": giây trên timeline, "dur": giây, "layer": "front"|"behind"|…}
  .rgba(t) → (H, W, 4) float32 0–1 premultiplied=False, hoặc None khi không có lớp nào ở t. Đọc tuần tự bằng ffmpeg (rgba).
- prerender(jobs, workdir): chạy các job còn thiếu/đã đổi (mã băm), trả {job_id: output}.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np


class _Reader:
    def __init__(self, path: str, W: int, H: int, fps: float):
        self.path, self.W, self.H, self.fps = path, W, H, fps
        self.proc = None
        self.idx = -1
        self.cur = None

    def _open(self):
        self.proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", self.path, "-vf", f"fps={self.fps},scale={self.W}:{self.H}",
                                      "-f", "rawvideo", "-pix_fmt", "rgba", "-"], stdout=subprocess.PIPE)
        self.idx = -1

    def frame(self, i: int):
        if self.proc is None or i < self.idx:
            self.close(); self._open()
        n = self.W * self.H * 4
        while self.idx < i:
            buf = self.proc.stdout.read(n)
            if len(buf) < n:
                return self.cur
            self.cur = np.frombuffer(buf, np.uint8).reshape(self.H, self.W, 4)
            self.idx += 1
        return self.cur

    def close(self):
        if self.proc:
            self.proc.kill(); self.proc = None


class Overlays:
    def __init__(self, items: list[dict], W: int, H: int, fps: float):
        self.items = [dict(it) for it in items if it.get("path") and Path(it["path"]).exists()]
        for it in self.items:
            it["_r"] = _Reader(str(it["path"]), W, H, fps)
        self.W, self.H, self.fps = W, H, fps

    def __bool__(self):
        return bool(self.items)

    def rgba(self, t: float, layer: str | None = None):
        out = None
        for it in self.items:
            if layer is not None and it.get("layer", "front") != layer:
                continue
            a = float(it["start"])
            if not (a - 1e-6 <= t < a + float(it["dur"])):
                continue
            fr = it["_r"].frame(int(round((t - a) * self.fps)))
            if fr is None:
                continue
            g = fr.astype(np.float32) / 255.0
            if out is None:
                out = g
            else:                                       # chồng các lớp HyperFrames theo thứ tự danh sách
                aa = g[..., 3:4]
                out = np.concatenate([out[..., :3] * (1 - aa) + g[..., :3] * aa, 1 - (1 - out[..., 3:4]) * (1 - aa)], axis=-1)
        return out

    def close(self):
        for it in self.items:
            it["_r"].close()


def over(base: np.ndarray, g: np.ndarray | None) -> np.ndarray:
    """base float 0–1 (H,W,3) ← lớp RGBA."""
    if g is None:
        return base
    a = g[..., 3:4]
    return base * (1 - a) + g[..., :3] * a


def prerender(jobs: list[dict], workdir: Path, base: Path | None = None, progress=print, **kw) -> dict:
    from .job import Job
    res = {}
    for sp in jobs:
        j = Job(sp, workdir, base)
        st = j.run(progress=progress, **kw)
        res[j.spec["job_id"]] = st["output"]
    return res
