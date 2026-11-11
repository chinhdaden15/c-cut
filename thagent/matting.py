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


def _reader(path: str, w: int, h: int, scale: tuple[int, int] | None = None):
    vf = ["-vf", f"scale={scale[0]}:{scale[1]}:flags=area"] if scale else []
    if scale:
        w, h = scale
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, *vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         stdout=subprocess.PIPE)
    n = w * h * 3
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w, 3)
    p.wait()


def _session(ort, progress=None):
    """Windows: thử GPU qua DirectML (onnxruntime-directml, có ở bản cài Windows) — nhanh hơn CPU nhiều lần trên laptop có GPU
    tích hợp; chạy thử 1 lượt, lỗi thì quay về CPU. Máy khác: CPU."""
    if "DmlExecutionProvider" in ort.get_available_providers():
        try:
            so = ort.SessionOptions()
            so.enable_mem_pattern = False
            so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            s = ort.InferenceSession(str(RVM_MODEL), so, providers=["DmlExecutionProvider", "CPUExecutionProvider"])
            z = [np.zeros((1, 1, 1, 1), np.float32)] * 4
            s.run(None, {"src": np.zeros((1, 3, 256, 144), np.float32), "r1i": z[0], "r2i": z[1], "r3i": z[2], "r4i": z[3],
                         "downsample_ratio": np.array([0.5], np.float32)})
            if progress:
                progress("tách nền: dùng GPU (DirectML)")
            return s
        except Exception as e:
            if progress:
                progress(f"tách nền: GPU không dùng được ({str(e)[:80]}) — chạy CPU")
    return ort.InferenceSession(str(RVM_MODEL), providers=["CPUExecutionProvider"])


def run_matting(proxy: str, out_alpha: str, out_anchors: str, w=1080, h=1920, progress=None,
                downsample_ratio=0.25):
    import onnxruntime as ort
    import mediapipe as mp

    import os as _os
    sess = _session(ort, progress)
    rec = [np.zeros((1, 1, 1, 1), np.float32)] * 4
    # chạy mô hình ở NỬA độ phân giải (RVM vốn thu nhỏ còn 1/4 bên trong) rồi phóng mask lên khung — nhanh ~3–4×, mask gần như y hệt
    dsr = np.array([min(1.0, downsample_ratio * 2)], np.float32)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
                            "-r", "30", "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "8",
                            "-pix_fmt", "yuv420p", out_alpha], stdin=subprocess.PIPE)
    fd = mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
    anchors = []
    import time as _t, threading, faulthandler, sys, os
    pw, ph = _probe_wh(proxy)
    if (pw, ph) != (w, h):                                   # proxy khác khung dựng → đọc lệch byte, treo / rác
        raise RuntimeError(f"proxy {pw}x{ph} khác khung dựng {w}x{h} — tạo lại proxy (xoá work/proxy) rồi chạy lại")
    total = _probe_frames(proxy)
    t0 = _t.monotonic()
    last = [t0, -1]
    stack = Path(out_anchors).with_name("matting_treo.txt")
    sf = open(stack, "w", encoding="utf-8")
    faulthandler.dump_traceback_later(300, repeat=True, file=sf)   # 5 phút không qua khung mới → ghi chỗ đang kẹt (gửi log để sửa)
    def watchdog():
        while last[1] != -2:
            _t.sleep(30)
            if last[1] != -2 and _t.monotonic() - last[0] > 600 and progress:
                progress(f"tách nền ĐỨNG ở khung {last[1] + 1} đã {int((_t.monotonic() - last[0]) / 60)} phút — máy quá tải / "
                         f"thiếu RAM hoặc bị treo; gửi file {stack.name} + app.log cho hỗ trợ")
    threading.Thread(target=watchdog, daemon=True).start()
    try:
        anchors = _matting_loop(sess, rec, dsr, enc, fd, proxy, w, h, progress, total, t0, last)
    finally:
        last[1] = -2
        faulthandler.cancel_dump_traceback_later()
        sf.close()
    enc.stdin.close()
    enc.wait()
    Path(out_anchors).write_text(json.dumps(anchors))
    return anchors


def _probe_wh(path: str) -> tuple[int, int]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        a, b = r.stdout.strip().split("\n")[0].split(",")[:2]
        return int(a), int(b)
    except Exception:
        return 0, 0


def _probe_frames(path: str) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=duration",
                        "-of", "csv=p=0", path], capture_output=True, text=True)
    try:
        return int(float(r.stdout.strip()) * 30)
    except Exception:
        return 0


def _matting_loop(sess, rec, dsr, enc, fd, proxy, w, h, progress, total, t0, last):
    import time as _t
    anchors = []
    hw, hh = (w // 2) // 2 * 2, (h // 2) // 2 * 2
    for i, frame in enumerate(_reader(proxy, w, h, (hw, hh))):
        src = (frame.astype(np.float32) / 255.0).transpose(2, 0, 1)[None]
        fgr, pha, *rec = sess.run(None, {"src": src, "r1i": rec[0], "r2i": rec[1], "r3i": rec[2],
                                         "r4i": rec[3], "downsample_ratio": dsr})
        a = cv2.resize(pha[0, 0], (w, h), interpolation=cv2.INTER_LINEAR)
        enc.stdin.write((np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes())
        # neo: hộp mặt (MediaPipe) + đỉnh đầu từ alpha
        res = fd.process(frame.copy())
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
        now = _t.monotonic()
        last[0], last[1] = now, i
        if progress and (i < 3 or i % 15 == 0):
            spf = (now - t0) / (i + 1)
            rest = f" · còn ~{max(1, int(spf * max(total - i - 1, 0) / 60))} phút" if total else ""
            progress(f"matting frame {i + 1}" + (f"/{total}" if total else "") + f" · {spf:.1f}s/khung{rest}")
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
