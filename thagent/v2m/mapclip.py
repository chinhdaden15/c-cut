"""Clip BẢN ĐỒ ĐƯỜNG PHỐ dựng sẵn (mp4) — dùng chung cho Talking Head, Review (chèn như b-roll) và mọi skill khác.

  python -m thagent.v2m mapclip <dự-án> "<điểm đi>" "<điểm đến>" [giây=6] [9x16|16x9] [dark|light] [tên]
      điểm = tên địa điểm (tra Photon) hoặc "lon,lat"; ra assets_web/v_map_<tên>.mp4 (+ ảnh xem trước _xem/v_map_<tên>.jpg)

Diễn tiến (học từ map-route-video, MIT): khung khu vực → camera đẩy vào điểm đi (ghim rơi + nhãn) → tuyến OSRM tự vẽ, camera bám
→ điểm đến bật nhãn "~km · ~phút (ước tính)" → giữ. Nguồn bản đồ + ghi chú "ước tính" luôn hiện ở chân khung.
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

from . import streetmap as SM


def _pt(s: str):
    if "," in s:
        try:
            a, b = (float(x) for x in s.split(","))
            return [a, b], None
        except ValueError:
            pass
    r = SM.geocode(s)
    if not r:
        raise SystemExit(f"không tìm được toạ độ “{s}” — thử thêm quận / thành phố hoặc đưa lon,lat")
    return r[0]["lonlat"], r[0]["name"]


def _ease(u):
    u = min(max(u, 0.0), 1.0)
    return 4 * u ** 3 if u < .5 else 1 - (-2 * u + 2) ** 3 / 2


def mapclip(pdir, a: str, b: str, dur: float = 6.0, fmt: str = "9x16", style: str = "dark", name: str = "tuyen",
            label_a: str | None = None, label_b: str | None = None) -> Path:
    from PIL import Image, ImageDraw
    from . import draw as D
    pdir = Path(pdir)
    W, H = (1080, 1920) if fmt == "9x16" else (1920, 1080)
    fps = 30
    pa, na = _pt(a)
    pb, nb = _pt(b)
    label_a = label_a or (a if "," not in a else na or "Điểm đi")
    label_b = label_b or (b if "," not in b else nb or "Điểm đến")
    r = SM.osrm(pdir, pa, pb, name)
    coords = json.loads(Path(r["file"]).read_text())["features"][0]["geometry"]["coordinates"]
    box = r["box"]
    padx, pady = (box[2] - box[0]) * 0.6, (box[3] - box[1]) * 0.6
    mb = [box[0] - padx, box[1] - pady, box[2] + padx, box[3] + pady]
    img, places = SM.render(mb if fmt == "16x9" else SM._portrait(mb, 2.1), style, 3000)
    img = SM._labels(img, places, style, 3000)
    mbb = mb if fmt == "16x9" else SM._portrait(mb, 2.1)
    ih, iw = img.shape[:2]
    z0 = 0
    fx0, fy0 = SM._tile_xy(mbb[0], mbb[3], z0)
    fx1, fy1 = SM._tile_xy(mbb[2], mbb[1], z0)
    def px(ll):
        x, y = SM._tile_xy(ll[0], ll[1], z0)
        return (x - fx0) / (fx1 - fx0) * iw, (y - fy0) / (fy1 - fy0) * ih
    route = np.array([px(c) for c in coords], np.float64)
    A, B = route[0], route[-1]
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(route, axis=0).T))]
    L = seg[-1] or 1
    rx0, ry0 = route.min(0)
    rx1, ry1 = route.max(0)
    fit = min(W * 0.56 / max(rx1 - rx0, 1), H * 0.45 / max(ry1 - ry0, 1))      # chừa lề cho nhãn hai đầu
    cam_all = ((rx0 + rx1) / 2, (ry0 + ry1) / 2, fit)
    cam_a = (A[0], A[1], fit * 1.9)
    acc = (0, 176, 255) if style == "dark" else (232, 115, 26)            # BGR: vàng cam / xanh
    t_in, t_draw0, t_draw1 = 0.25, 1.4, max(2.6, dur - 1.6)
    tmp = Path(tempfile.mkdtemp())
    S = W / 1080

    def cam_at(t):
        if t < t_draw0:
            u = _ease((t - t_in) / (t_draw0 - t_in))
            c0 = (cam_all[0], cam_all[1], cam_all[2] * 0.82)
            return tuple(c0[i] + (cam_a[i] - c0[i]) * u for i in range(3))
        u = _ease((t - t_draw0) / (t_draw1 - t_draw0 + 0.6))
        return tuple(cam_a[i] + (cam_all[i] - cam_a[i]) * u for i in range(3))

    def tag(canvas, x, y, title, sub, k):
        if k <= 0:
            return canvas
        pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        dr = ImageDraw.Draw(pil, "RGBA")
        f1, f2 = D.font("black", int(46 * S)), D.font("semi", int(30 * S))
        tw = max(dr.textlength(title, font=f1), dr.textlength(sub or "", font=f2)) + 48 * S
        th = (64 + (40 if sub else 0)) * S
        cxl = min(max(x, tw / 2 + 24 * S), W - tw / 2 - 24 * S)          # nhãn không ra ngoài khung
        bx, by = cxl - tw / 2, y - 150 * S - th
        dr.line([(x, y - 14 * S), (cxl, by + th)], fill=(255, 255, 255, int(220 * k)), width=int(3 * S))
        dr.rounded_rectangle([bx, by, bx + tw, by + th], radius=int(16 * S), fill=(10, 16, 28, int(230 * k)),
                             outline=(acc[2], acc[1], acc[0], int(255 * k)), width=int(3 * S))
        dr.text((cxl, by + 34 * S), title, font=f1, fill=(255, 255, 255, int(255 * k)), anchor="mm")
        if sub:
            dr.text((cxl, by + 84 * S), sub, font=f2, fill=(acc[2], acc[1], acc[0], int(255 * k)), anchor="mm")
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    sub_b = f"~{str(r['km']).replace('.', ',')} km · ~{r['phut']} phút (ước tính)"
    n = int(dur * fps)
    proc = subprocess.Popen([SM_ffmpeg(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(fps),
                             "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-preset", "veryfast",
                             str(pdir / "assets_web" / f"v_map_{name}.mp4")], stdin=subprocess.PIPE)
    foot = None
    for i in range(n):
        t = i / fps
        cx, cy, s = cam_at(t)
        M = np.float32([[s, 0, W / 2 - s * cx], [0, s, H / 2 - s * cy]])
        fr = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=tuple(int(v) for v in img[0, 0]))
        if t < t_in + 0.3:
            fr = (fr * min(1, (t / (t_in + 0.3)))).astype(np.uint8)
        P = lambda p: (int(round(s * p[0] + M[0, 2])), int(round(s * p[1] + M[1, 2])))
        k = _ease((t - t_draw0) / (t_draw1 - t_draw0))
        if k > 0:
            cut = np.searchsorted(seg, k * L)
            head = (float(np.interp(k * L, seg, route[:, 0])), float(np.interp(k * L, seg, route[:, 1])))
            pts = np.array([P(p) for p in route[:max(cut, 1)]] + [P(head)], np.int32)
            glow = fr.copy()
            cv2.polylines(glow, [pts], False, acc, int(22 * S), cv2.LINE_AA)
            fr = cv2.addWeighted(cv2.GaussianBlur(glow, (0, 0), 10 * S), 0.55, fr, 0.45, 0)
            cv2.polylines(fr, [pts], False, acc, int(9 * S), cv2.LINE_AA)
            cv2.polylines(fr, [pts], False, (255, 255, 255), int(3 * S), cv2.LINE_AA)
            cv2.circle(fr, tuple(pts[-1]), int(12 * S), (255, 255, 255), -1, cv2.LINE_AA)
        for p, tt in ((A, 0.7), (B, t_draw1 - 0.1)):
            if t >= tt:
                u = min(1, (t - tt) / 0.35)
                rr = int((16 + 10 * (1 - u)) * S)
                cv2.circle(fr, P(p), rr + int(6 * S), (255, 255, 255), -1, cv2.LINE_AA)
                cv2.circle(fr, P(p), rr, acc, -1, cv2.LINE_AA)
        fr = tag(fr, *P(A), label_a, None, min(1, (t - 0.9) / 0.35))
        fr = tag(fr, *P(B), label_b, sub_b, min(1, (t - t_draw1) / 0.35))
        if foot is None:
            fpil = Image.new("RGBA", (W, int(70 * S)), (0, 0, 0, 0))
            dr = ImageDraw.Draw(fpil)
            dr.text((W / 2, 35 * S), "© OpenStreetMap · OpenFreeMap · OSRM · thời gian ước tính", font=D.font("medium", int(20 * S)),
                    fill=(190, 200, 214, 230), anchor="mm")
            foot = np.array(fpil)
        y0 = H - int((150 if fmt == "9x16" else 70) * S)
        a_ = foot[..., 3:4] / 255.0
        reg = fr[y0:y0 + foot.shape[0]]
        reg[:] = (reg * (1 - a_) + cv2.cvtColor(foot[..., :3], cv2.COLOR_RGB2BGR) * a_).astype(np.uint8)
        proc.stdin.write(fr.tobytes())
        if abs(t - (dur - 0.6)) < 0.5 / fps:
            prev = pdir / "assets_web" / "_xem" / f"v_map_{name}.jpg"
            prev.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(prev), cv2.resize(fr, (W // 3, H // 3)))
    proc.stdin.close()
    proc.wait()
    out = pdir / "assets_web" / f"v_map_{name}.mp4"
    srcs_f = pdir / "assets_web" / "illus_sources.json"
    srcs = json.loads(srcs_f.read_text(encoding="utf-8")) if srcs_f.exists() else {}
    srcs[out.name] = "OpenStreetMap contributors · OpenFreeMap · OSRM"
    srcs_f.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}\n~{str(r['km']).replace('.', ',')} km · ~{r['phut']} phút · xem trước: {pdir}/assets_web/_xem/v_map_{name}.jpg")
    return out


def SM_ffmpeg() -> str:
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"
