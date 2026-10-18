"""Review Editor — hiểu hành động: dò tay (giơ sản phẩm / chỉ tay) và BÁM vật thể (sản phẩm) qua các khung hình.

- hands(pdir, fid, t0, t1): mỗi 0,25s trong khoảng → bàn tay (MediaPipe), cử chỉ chỉ tay/giơ lên, đầu ngón, hướng, vùng vật gợi ý (saliency trên tia chỉ).
  → review/hands_<ID>.json  (toạ độ chuẩn hoá 0–1 theo khung NGUỒN)
- track(pdir, name, fid, t, box, t0, t1): bám vật từ khung t (box = x,y,w,h chuẩn hoá) xuôi + ngược trong [t0, t1] bằng CSRT (OpenCV),
  10 mẫu/giây, làm mượt, đánh dấu đoạn mất dấu. → review/tracks/<name>.json
Vị trí vật dùng cho: nhãn sản phẩm đặt sát vật (có đường dẫn ngắn), vòng nhấn đúng lúc chỉ tay, reframe ưu tiên mặt + sản phẩm.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .edit import media

STEP_H = 0.25
STEP_T = 0.1
TW = 480       # bề rộng khung khi bám (nhanh, đủ chi tiết)


def _grab(path: str, t0: float, t1: float, fps: float, w: int, h: int):
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", f"{max(t0, 0):.3f}", "-t", f"{t1 - t0:.3f}", "-i", path, "-vf",
                          f"fps={fps:g},scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    n, i = w * h * 3, 0
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield round(t0 + i / fps, 3), np.frombuffer(buf, np.uint8).reshape(h, w, 3)
        i += 1
    p.wait()


def _target(img, tip, d):
    """vùng vật nổi bật cắt tia chỉ (bỏ bàn tay) — gợi ý, Claude xác nhận bằng ảnh."""
    H, W = img.shape[:2]
    sal = cv2.saliency.StaticSaliencySpectralResidual_create()
    ok, m = sal.computeSaliency(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    m = (m * 255).astype(np.uint8) if ok else np.zeros((H, W), np.uint8)
    m = cv2.GaussianBlur(m, (0, 0), 6)
    _, b = cv2.threshold(m, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    tx, ty = tip[0] * W, tip[1] * H
    cv2.circle(b, (int(tx), int(ty)), int(0.1 * W), 0, -1)
    n, lab, st, _ = cv2.connectedComponentsWithStats(b)
    for r in range(int(0.05 * H), int(0.7 * H), 8):
        x, y = int(tx + d[0] * r), int(ty + d[1] * r)
        if not (0 <= x < W and 0 <= y < H):
            break
        k = lab[y, x]
        if k and st[k, cv2.CC_STAT_AREA] > 0.004 * W * H:
            x0, y0, w, h = st[k, :4]
            return [round(x0 / W, 3), round(y0 / H, 3), round(w / W, 3), round(h / H, 3)]
    return None


def hands(pdir, fid: str, t0: float = 0.0, t1: float | None = None) -> list[dict]:
    import mediapipe as mp
    m = media(pdir)[fid]
    t1 = min(m["duration"], t1 if t1 is not None else m["duration"])
    w = 540
    h = int(round(w * m["h"] / m["w"] / 2) * 2)
    out = []
    with mp.solutions.hands.Hands(static_image_mode=True, max_num_hands=2, min_detection_confidence=0.5) as hd:
        for t, img in _grab(m["path"], t0, t1, 1 / STEP_H, w, h):
            r = hd.process(img)
            rec = {"t": t, "hands": 0}
            for lm in r.multi_hand_landmarks or []:
                L = [(q.x, q.y) for q in lm.landmark]
                rec["hands"] += 1
                wr, mcp, itip, mtip = L[0], L[5], L[8], L[12]
                ext = math.dist(itip, wr) / (math.dist(mcp, wr) + 1e-6)
                curled = math.dist(L[16], wr) / (math.dist(L[13], wr) + 1e-6)
                if ext > 1.9 and curled < 1.4:
                    d = np.array([itip[0] - mcp[0], itip[1] - mcp[1]]); d = d / (np.linalg.norm(d) + 1e-6)
                    rec.update(point=True, tip=[round(itip[0], 3), round(itip[1], 3)], dir=[round(d[0], 3), round(d[1], 3)])
                    tg = _target(img, itip, d)
                    if tg:
                        rec["target"] = tg
                xs, ys = [q[0] for q in L], [q[1] for q in L]
                rec.setdefault("hand_boxes", []).append([round(min(xs), 3), round(min(ys), 3), round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)])
            out.append(rec)
    # gom thành các lần chỉ tay liên tục
    runs, cur = [], None
    for r in out:
        if r.get("point"):
            if cur and r["t"] - cur["t1"] <= 2 * STEP_H + 1e-6:
                cur["t1"] = r["t"]; cur["n"] += 1
                if r.get("target"): cur["targets"].append(r["target"])
            else:
                cur = {"t0": r["t"], "t1": r["t"], "n": 1, "tip": r["tip"], "targets": [r["target"]] if r.get("target") else []}
                runs.append(cur)
    for c in runs:
        c["t1"] = round(c["t1"] + STEP_H, 2)
        tg = c.pop("targets")
        c["target"] = [round(float(np.median([x[k] for x in tg])), 3) for k in range(4)] if tg else None
    res = {"src": fid, "t0": t0, "t1": t1, "pointing": [c for c in runs if c["n"] >= 2], "samples": out}
    (Path(pdir) / "review" / f"hands_{fid}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res["pointing"]


def _smooth(vals: list[list[float]], k: int = 5) -> list[list[float]]:
    a = np.array(vals, float)
    if len(a) < k:
        return a.tolist()
    ker = np.ones(k) / k
    pad = np.pad(a, ((k // 2, k // 2), (0, 0)), mode="edge")
    return np.stack([np.convolve(pad[:, j], ker, mode="valid") for j in range(a.shape[1])], 1).tolist()


def track(pdir, name: str, fid: str, t: float, box: list[float], t0: float, t1: float) -> dict:
    """bám vật (CSRT) xuôi từ t tới t1 và ngược từ t về t0. box = [x, y, w, h] chuẩn hoá theo khung nguồn."""
    m = media(pdir)[fid]
    w = TW
    h = int(round(w * m["h"] / m["w"] / 2) * 2)

    def run(a, b, forward):
        frames = list(_grab(m["path"], a, b, 1 / STEP_T, w, h))
        if not forward:
            frames = frames[::-1]
        if not frames:
            return []
        tr = cv2.TrackerCSRT_create()
        bb = (int(box[0] * w), int(box[1] * h), max(int(box[2] * w), 4), max(int(box[3] * h), 4))
        tr.init(cv2.cvtColor(frames[0][1], cv2.COLOR_RGB2BGR), bb)
        res, area0 = [], bb[2] * bb[3]
        for tt, img in frames:
            ok, r = tr.update(cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            lost = (not ok) or r[2] * r[3] < 0.25 * area0 or r[2] * r[3] > 4 * area0
            res.append({"t": tt, "box": [r[0] / w, r[1] / h, r[2] / w, r[3] / h], "lost": bool(lost)})
        return res if forward else res[::-1]
    back = run(max(t0, 0), t + STEP_T, False) if t > t0 + 1e-3 else []
    fwd = run(t, min(t1, m["duration"]), True)
    pts = [p for p in back if p["t"] < t - 1e-3] + fwd
    if not pts:
        raise SystemExit("không bám được — kiểm box/giây")
    sm = _smooth([p["box"] for p in pts])
    for p, b in zip(pts, sm):
        p["box"] = [round(x, 4) for x in b]
    lost = [p["t"] for p in pts if p["lost"]]
    res = {"name": name, "src": fid, "t0": pts[0]["t"], "t1": pts[-1]["t"], "seed": {"t": t, "box": box}, "points": pts,
           "lost_s": round(len(lost) * STEP_T, 1), "lost_from": lost[0] if lost else None}
    d = Path(pdir) / "review" / "tracks"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    return res


def load_track(pdir, name: str) -> dict:
    return json.loads((Path(pdir) / "review" / "tracks" / f"{name}.json").read_text(encoding="utf-8"))


def box_at(tr: dict, t: float) -> list[float] | None:
    """box (nguồn, chuẩn hoá) của vật tại giây nguồn t — nội suy; ngoài khoảng bám / mất dấu → None."""
    pts = tr["points"]
    if not pts or t < pts[0]["t"] - 0.05 or t > pts[-1]["t"] + 0.05:
        return None
    i = min(range(len(pts)), key=lambda k: abs(pts[k]["t"] - t))
    if pts[i]["lost"]:
        return None
    j = i + 1 if pts[i]["t"] <= t and i + 1 < len(pts) else i
    if j == i or pts[j]["lost"]:
        return pts[i]["box"]
    k = (t - pts[i]["t"]) / max(pts[j]["t"] - pts[i]["t"], 1e-6)
    return [a + (b - a) * k for a, b in zip(pts[i]["box"], pts[j]["box"])]
