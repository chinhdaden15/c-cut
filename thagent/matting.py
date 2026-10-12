"""Tách nhân vật động + neo đầu/ngực.

Backend mặc định: Robust Video Matting (ONNX, mobilenetv3) — có trạng thái hồi quy
theo thời gian nên alpha ổn định giữa các frame, không phải PNG tách nền tĩnh.
Alpha được lưu thành video xám cùng frame-rate/kích thước với proxy, nên mọi
crop/zoom áp cùng transform lên hình và mask (xem render.py).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .paths import ROOT
RVM_MODEL = ROOT / "models" / "rvm_mobilenetv3_fp32.onnx"


def _reader(path: str, w: int, h: int):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    p.wait()


def run_matting(proxy: str, out_alpha: str, out_anchors: str, w=1080, h=1920, progress=None,
                downsample_ratio=0.25):
    import onnxruntime as ort
    import mediapipe as mp

    sess = ort.InferenceSession(str(RVM_MODEL), providers=["CPUExecutionProvider"])
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    dsr = np.array([downsample_ratio], np.float32)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
                            "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "8",
                            "-pix_fmt", "yuv420p", out_alpha], stdin=subprocess.PIPE)
    fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
    anchors = []
    for i, frame in enumerate(_reader(proxy, w, h)):
        src = (frame.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        fgr, pha, *rec = sess.run(None, {"src": src, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2],
                                         "r4i": rec[3], "downsample_ratio": dsr})
        a = pha[0, 0]
        enc.stdin.write((np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes())
        # neo: hộp mặt (MediaPipe) + đỉnh đầu từ alpha
        res = fd.process(frame[::2, ::2].copy())
        face = None
        if res.detections:
            d = max(res.detections, key=lambda d: d.score[0]).location_data.relative_bounding_box
            face = [d.xmin, d.ymin, d.width, d.height]
        rows = np.where((a > 0.5).sum(1) > 6)[0]
        top = float(rows[0]) / h if len(rows) else None
        cols = np.where((a > 0.5).sum(0) > 6)[0]
        body = [float(cols[0]) / w, float(cols[-1]) / w] if len(cols) else None
        anchors.append({"f": i, "face": face, "head_top": top, "body_x": body,
                        "coverage": float((a > 0.5).mean())})
        if progress and i % 30 == 0:
            progress(f"matting frame {i}")
    enc.stdin.close()
    enc.wait()
    Path(out_anchors).write_text(json.dumps(anchors))
    return anchors


def smooth_anchors(anchors: list[dict], win: int = 15) -> list[dict]:
    """Làm mượt neo (median + trung bình trượt) để text không rung theo chuyển động nhỏ.
    Trả về mỗi frame: head_top, face_cx, face_cy, face_h, chest_y (tỉ lệ khung)."""
    n = len(anchors)
    def series(fn):
        v = np.array([fn(a) if fn(a) is not None else np.nan for a in anchors], float)
        idx = np.arange(n); ok = ~np.isnan(v)
        if ok.sum() == 0:
            return np.full(n, np.nan)
        v = np.interp(idx, idx[ok], v[ok])
        pad = np.pad(v, win, mode="edge")
        med = np.array([np.median(pad[i:i + 2 * win + 1]) for i in range(n)])
        k = np.ones(win) / win
        return np.convolve(np.pad(med, win, mode="edge"), k, "same")[win:-win]
    fx = series(lambda a: a["face"][0] + a["face"][2] / 2 if a["face"] else None)
    fy = series(lambda a: a["face"][1] + a["face"][3] / 2 if a["face"] else None)
    fh = series(lambda a: a["face"][3] if a["face"] else None)
    ht = series(lambda a: a["head_top"])
    out = []
    for i in range(n):
        out.append({"head_top": ht[i], "face_cx": fx[i], "face_cy": fy[i], "face_h": fh[i],
                    "face_bottom": fy[i] + fh[i] * 0.6, "chest_y": fy[i] + fh[i] * 2.2})
    return out
