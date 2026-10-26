"""Dò cử chỉ CHỈ TAY / giơ tay giới thiệu vật → work/pointing.json.

Mỗi đoạn: {t0, t1, tip:[x,y], dir:[dx,dy], box:[x,y,w,h], said}  (toạ độ chuẩn hoá 0–1 theo khung dọc đầu ra)
- MediaPipe Hands: bàn tay giơ cao (cổ tay trên ngực) hoặc ngón trỏ duỗi thẳng → đang chỉ.
- hướng chỉ = cổ tay → đầu ngón giữa/ngón trỏ; vùng vật = khối nổi bật (saliency) nằm trên tia chỉ.
Agent xem ảnh tĩnh để duyệt/chỉnh box rồi mới đặt hiệu ứng highlight. Không chắc → vòng sáng tại đầu ngón tay.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys

import cv2
import numpy as np

from . import clips as C, pipeline as P

STEP = 0.25
SW, SH = 720, 1280


def _target_box(img: np.ndarray, tip, d) -> list[float]:
    """khối nổi bật lớn nhất cắt tia chỉ (bỏ vùng quanh bàn tay); không tìm được → ô vuông trên tia."""
    sal = cv2.saliency.StaticSaliencySpectralResidual_create()
    ok, m = sal.computeSaliency(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    m = (m * 255).astype(np.uint8) if ok else np.zeros(img.shape[:2], np.uint8)
    m = cv2.GaussianBlur(m, (0, 0), 6)
    _, b = cv2.threshold(m, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    tx, ty = tip[0] * SW, tip[1] * SH
    cv2.circle(b, (int(tx), int(ty)), int(0.12 * SW), 0, -1)     # bỏ chính bàn tay
    n, lab, st, _ = cv2.connectedComponentsWithStats(b)
    best, score = None, 0
    for r in range(80, int(0.8 * SH), 20):   # đi dọc tia
        x, y = int(tx + d[0] * r), int(ty + d[1] * r)
        if not (0 <= x < SW and 0 <= y < SH):
            break
        k = lab[y, x]
        if k and st[k, cv2.CC_STAT_AREA] > 0.004 * SW * SH:
            s = st[k, cv2.CC_STAT_AREA] / (1 + r / SW)
            if s > score:
                best, score = k, s
    if best is not None:
        x, y, w, h = st[best, :4]
        if w * h < 0.35 * SW * SH:
            return [x / SW, y / SH, w / SW, h / SH]
    s = 0.3 * SW
    cx = min(max(tx + d[0] * 0.22 * SW, s / 2), SW - s / 2)
    cy = min(max(ty + d[1] * 0.22 * SW, s / 2), SH - s / 2)
    return [(cx - s / 2) / SW, (cy - s / 2) / SH, s / SW, s / SH]


def detect(path: str, words=None, log=print) -> list[dict]:
    import mediapipe as mp
    global SW, SH
    info = P.probe_source(path)
    fw, fh = P.frame_of(info)
    SW, SH = (720, 1280) if fh > fw else (1280, 720)
    vf = C._vf(info, 1.0, SW, SH).replace(f"fps={C.FPS}", f"fps={1 / STEP:g}").replace("format=yuv420p", "format=rgb24")
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-vf", vf, "-f", "rawvideo", "-"], stdout=subprocess.PIPE)
    hits, i = [], 0
    with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=2, min_detection_confidence=0.5) as hd:
        while True:
            buf = p.stdout.read(SW * SH * 3)
            if len(buf) < SW * SH * 3:
                break
            img = np.frombuffer(buf, np.uint8).reshape(SH, SW, 3)
            t = round(i * STEP, 2); i += 1
            r = hd.process(img)
            for lm in r.multi_hand_landmarks or []:
                L = [(q.x, q.y) for q in lm.landmark]
                wr, mcp, itip, mtip = L[0], L[5], L[8], L[12]
                ext = math.dist(itip, wr) / (math.dist(mcp, wr) + 1e-6)       # ngón trỏ duỗi
                curled = math.dist(L[16], wr) / (math.dist(L[13], wr) + 1e-6)  # ngón áp út co
                raised = wr[1] < 0.55 and mtip[1] < wr[1]                       # giơ tay lên ngang vai
                index_point = ext > 1.9 and curled < 1.4
                mext = math.dist(mtip, wr) / (math.dist(L[9], wr) + 1e-6)
                present = wr[1] < 0.6 and mext > 1.6 and abs(mtip[0] - wr[0]) > 0.6 * math.dist(mtip, wr)   # xoè tay ngang giới thiệu
                if not (raised or index_point or present):
                    continue
                tip = itip if index_point else mtip
                d = np.array([tip[0] - wr[0], tip[1] - wr[1]]); d = d / (np.linalg.norm(d) + 1e-6)
                hits.append({"t": t, "tip": [round(tip[0], 3), round(tip[1], 3)], "dir": [round(d[0], 3), round(d[1], 3)],
                             "kind": "index" if index_point else "palm", "img": img})
                break
            if i % 40 == 0:
                log(f"dò chỉ tay {t:.0f}s")
    p.wait()
    runs = []
    for h in hits:
        if runs and h["t"] - runs[-1][-1]["t"] <= 2 * STEP + 1e-6:
            runs[-1].append(h)
        else:
            runs.append([h])
    out = []
    for r in runs:
        if r[-1]["t"] - r[0]["t"] < 0.5:
            continue
        mid = r[len(r) // 2]
        tip = np.median([h["tip"] for h in r], 0).tolist()
        d = np.mean([h["dir"] for h in r], 0); d = (d / (np.linalg.norm(d) + 1e-6)).tolist()
        t0, t1 = r[0]["t"], r[-1]["t"] + STEP
        said = " ".join(w.text for w in words or [] if t0 - 1.0 <= w.source_start <= t1 + 0.5)
        out.append({"t0": t0, "t1": round(t1, 2), "tip": [round(x, 3) for x in tip], "dir": [round(x, 3) for x in d],
                    "kind": mid["kind"], "box": [round(x, 3) for x in _target_box(mid["img"], tip, d)], "said": said})
    return out


def run(c: "P.Ctx", force: bool = False):
    dst = c.path("work", "pointing.json")
    if dst.exists() and not force:
        return dst
    res = detect(c.project.source.path, c.project.words, c.log if hasattr(c, "log") else print)
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    return dst


def main():
    print(run(P.Ctx(sys.argv[1]), "--force" in sys.argv))


if __name__ == "__main__":
    main()
