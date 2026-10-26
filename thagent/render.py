"""Dựng thô (ffmpeg) + compositor theo frame + phối âm + loudness.

Thứ tự lớp (sau → trước):
  video gốc → text/hình vùng đầu (behind_subject) → nhân vật (alpha động) → text/hình
  vùng ngực trở xuống (front_of_subject) → light wash
Nhân vật = chính pixel của video gốc nhân alpha cùng frame, cùng transform zoom
→ không thể lệch vị trí so với nền. Lớp nhân vật không mang audio.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import imgio
from . import timeline as T
from .matting import smooth_anchors
from .schema import Plan, TextGroup
from .typography import draw_group, group_extent, _blend, clamp01, ease_out_cubic, hex_rgb
from . import mg as MG

SAFE = {"top": 150, "bottom": 330, "side": 70}


def run(cmd: list[str]):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-2000:]}")
    return r


# ---------------- dựng thô ----------------
def rough_cut(plan: Plan, proxy: str, alpha: str, out_dir: Path, voice: str | None = None) -> dict:
    """Ghép các đoạn keep theo order → video, alpha, audio voice (fade 8ms ở biên, không chồng)."""
    segs = T.kept(plan)
    fps = plan.fps
    vf, af, alf = [], [], []
    for i, s in enumerate(segs):
        a, b = T.sec_to_frame(s.source_in, fps), T.sec_to_frame(s.source_out, fps)
        vf.append(f"[0:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[v{i}]")
        alf.append(f"[1:v]trim=start_frame={a}:end_frame={b},setpts=PTS-STARTPTS[m{i}]")
        dur = (b - a) / fps
        af.append(f"[2:a]atrim=start={a / fps}:end={b / fps},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.008,afade=t=out:st={max(dur - 0.008, 0)}:d=0.008[a{i}]")
    n = len(segs)
    fc = ";".join(vf + alf + af) + ";" + \
        "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vo];" + \
        "".join(f"[m{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[mo];" + \
        "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[ao]"
    out = {"video": str(out_dir / "rc_video.mp4"), "alpha": str(out_dir / "rc_alpha.mp4"),
           "voice": str(out_dir / "rc_voice.wav")}
    run(["ffmpeg", "-v", "error", "-y", "-i", proxy, "-i", alpha, "-i", voice or proxy, "-filter_complex", fc,
         "-map", "[vo]", "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-r", str(fps), out["video"],
         "-map", "[mo]", "-c:v", "libx264", "-preset", "fast", "-crf", "8", "-pix_fmt", "yuv420p", "-r", str(fps), out["alpha"],
         "-map", "[ao]", "-c:a", "pcm_s16le", "-ar", "48000", out["voice"]])
    return out


def _frames(path: str, w: int, h: int, gray=False):
    pix, ch = ("gray", 1) if gray else ("rgb24", 3)
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", path, "-f", "rawvideo", "-pix_fmt", pix, "-"],
                         stdout=subprocess.PIPE)
    n = w * h * ch
    try:
        while True:
            b = p.stdout.read(n)
            if len(b) < n:
                break
            a = np.frombuffer(b, np.uint8)
            yield a.reshape(h, w) if gray else a.reshape(h, w, 3)
    finally:                      # dừng sớm (dựng một đoạn / huỷ) → đóng ffmpeg gọn, không để nó ghi vào ống đã đóng (log "Broken pipe")
        if p.poll() is None:
            p.kill()
        p.stdout.close()
        p.wait()


# ---------------- neo theo timeline ----------------
def timeline_anchors(plan: Plan, anchors_src: list[dict]) -> list[dict]:
    sm = smooth_anchors(anchors_src)
    out = []
    for f in range(plan.duration_frames):
        sf = T.tl_to_src_frame(plan, f)
        i = min(max(sf or 0, 0), len(sm) - 1)
        a = sm[i]
        if anchors_src[min(i, len(anchors_src) - 1)].get("obj"):     # vùng vật đang cầm (callouts.attach_objects)
            a = {**a, "obj": anchors_src[min(i, len(anchors_src) - 1)]["obj"]}
        out.append(a)
    return out


def zoom_at(plan: Plan, f: int) -> tuple[float, float, float]:
    """(zoom, cx, cy). mode=punch: vào nhanh 4 frame, giữ, ra 10 frame; mode=out: bắt đầu phóng rồi lùi dần về 1."""
    z, cx, cy = 1.0, 0.5, 0.4
    from .callouts import zoom_events
    for e in list(plan.fx) + zoom_events(plan):
        if e.type != "zoom" or not e.enabled or not (e.start <= f < e.end + 10):
            continue
        tgt = e.params.get("scale", 1.06)
        if e.params.get("mode") == "cut":      # phóng tức thì đúng đoạn (giấu jump cut), không chuyển động
            if f >= e.end:
                continue
            k = 1.0
        elif e.params.get("mode") == "out":
            k = 1 - clamp01((f - e.start) / max(e.end - e.start, 1))
            k = k * k * (3 - 2 * k)
        else:
            if f < e.start + 4:
                k = 1 - (1 - (f - e.start + 1) / 4) ** 3
            elif f < e.end:
                k = 1.0
            else:
                k = 1 - (f - e.end + 1) / 10
                k = 0.5 - 0.5 * math.cos(math.pi * max(0, min(1, k)))
        z = 1 + (tgt - 1) * max(0.0, min(1.0, k))
        cx, cy = e.params.get("cx", 0.5), e.params.get("cy", 0.4)
    return z, cx, cy


def draw_highlights(out: np.ndarray, plan: Plan, f: int, z: float, zcx: float, zcy: float) -> np.ndarray:
    """Làm nổi bật vật nhân vật đang chỉ: tối nhẹ phần còn lại, viền sáng vẽ dần quanh vật, nhãn (tuỳ chọn).
    params: box=[x,y,w,h] chuẩn hoá theo khung nguồn (trước zoom), label, tone (gold/red/blue), shape=rect|ring."""
    H, W = out.shape[:2]
    for e in plan.fx:
        if e.type != "highlight" or not e.enabled or not (e.start <= f < e.end):
            continue
        k = min(clamp01((f - e.start + 1) / 6), clamp01((e.end - f) / 6))
        bx, by, bw, bh = e.params["box"]
        tx = lambda x: z * x * W + (1 - z) * zcx * W
        ty = lambda y: z * y * H + (1 - z) * zcy * H
        x0, y0, x1, y1 = tx(bx), ty(by), tx(bx + bw), ty(by + bh)
        pad = 14
        x0, y0, x1, y1 = int(x0 - pad), int(y0 - pad), int(x1 + pad), int(y1 + pad)
        r = int(min(x1 - x0, y1 - y0) * 0.12) + 8
        m = np.zeros((H, W), np.uint8)
        ring = e.params.get("shape") == "ring"
        if ring:
            cv2.ellipse(m, ((x0 + x1) // 2, (y0 + y1) // 2), ((x1 - x0) // 2, (y1 - y0) // 2), 0, 0, 360, 255, -1, cv2.LINE_AA)
        else:
            cv2.rectangle(m, (x0 + r, y0), (x1 - r, y1), 255, -1); cv2.rectangle(m, (x0, y0 + r), (x1, y1 - r), 255, -1)
            for cx, cy in [(x0 + r, y0 + r), (x1 - r, y0 + r), (x0 + r, y1 - r), (x1 - r, y1 - r)]:
                cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
        inside = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 10)[..., None]
        dim = e.params.get("dim", 0.38) * k
        out = out * (1 - dim * (1 - inside)) + np.clip(out * 1.08, 0, 1) * (0.25 * k * inside) - out * (0.25 * k * inside)
        # viền: vẽ dần theo chu vi
        cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        if cnts:
            c = cnts[0][:, 0, :]
            n = int(len(c) * ease_out_cubic(clamp01((f - e.start + 1) / 12)))
            line = np.zeros((H, W), np.uint8)
            if n > 2:
                cv2.polylines(line, [c[:n]], False, 255, 6, cv2.LINE_AA)
            ln = line.astype(np.float32) / 255
            glow = cv2.GaussianBlur(ln, (0, 0), 12) * 1.6
            col = np.array(hex_rgb({"gold": "#FFC83A", "red": "#FF6A5A", "blue": "#4FC3FF"}[e.params.get("tone", "gold")]), np.float32) / 255
            a = np.clip(glow * 0.8 * k, 0, 1)[..., None]
            out = out * (1 - a) + col * a
            a2 = (ln * k)[..., None]
            out = out * (1 - a2) + (col * 0.35 + 0.65) * a2
        if e.params.get("label") and k > 0.05:
            t = MG.tag(e.params["label"], e.params.get("tone", "gold"), 46)
            th, tw = t.shape[:2]
            cx = int(min(max((x0 + x1) / 2, tw / 2 + 10), W - tw / 2 - 10))
            cy = y0 - th // 2 + 18 if y0 - th > 60 else y1 + th // 2 - 18
            lay = np.zeros((H, W, 4), np.float32)
            MG._put(lay, t, cx, cy, o=clamp01((f - e.start - 6) / 6) * k)
            out = out * (1 - lay[..., 3:4]) + lay[..., :3]
    return out


def flash_at(plan: Plan, f: int) -> float:
    o = 0.0
    for e in plan.fx:
        if e.type != "flash" or not e.enabled:
            continue
        d = e.end - e.start
        if e.start <= f < e.end:
            t = (f - e.start + 0.5) / d
            o = max(o, e.params.get("opacity", 0.2) * (min(t / 0.3, 1) if t < 0.3 else (1 - t) / 0.7))
    return o


MOVED_DOWN: set[str] = set()   # nhóm “sau đầu” không đủ chỗ trên đầu → app đưa xuống trước ngực (lớp trước người)


def layer_of(g) -> str:
    return "front_of_subject" if g.id in MOVED_DOWN else g.layer


def resolve_layout(plan: Plan, anchors_tl: list[dict], W: int, H: int) -> dict[str, tuple[float, float]]:
    """Điểm neo (px) cố định cho mỗi nhóm, tính từ median neo trong thời gian nhóm hiển thị."""
    pos = {}
    MOVED_DOWN.clear()
    down = {}      # id → (vị trí mong muốn, y0, y1)
    for g in plan.text_groups:
        if not g.enabled:
            continue
        fr = [anchors_tl[f] for f in range(max(g.start, 0), min(g.end, len(anchors_tl)))] or [anchors_tl[0]]
        med = lambda k: float(np.nanmedian([a[k] for a in fr]))
        z, zcx, zcy = zoom_at(plan, g.start + g.enter_frames)
        zy = lambda y: ((y - zcy) * z + zcy) * H
        x0, y0, x1, y1 = group_extent(g, skip_icons=True)
        maxw = W - 2 * SAFE["side"]
        if x1 - x0 > maxw:   # tự thu nhỏ cả nhóm cho vừa khung, giữ tỉ lệ bố cục
            k = maxw / (x1 - x0)
            for sp in g.spans:
                sp.size = max(int(sp.size * k), 20); sp.dx *= k; sp.dy *= k
            x0, y0, x1, y1 = group_extent(g)
        gh = y1 - y0
        if g.anchor_y is not None:
            ay = g.anchor_y * H
        elif g.zone == "above_head":
            # đáy tiêu đề chồng ~38% xuống dưới đỉnh đầu → đầu/tóc che thật một phần chữ
            # đỉnh đầu cao nhất (pc10) trong thời gian nhóm hiển thị → không bị đầu che khi người tiến lại gần
            head_top = zy(float(np.nanpercentile([a["head_top"] for a in fr], 10)))
            # có nhãn ở dưới cùng → đặt cả cụm trên vai/đầu để nhãn không bị mặt che
            ends_with_pill = any(sp.style == "pill" for sp in g.spans)
            ay = (head_top - y1 - 22) if ends_with_pill else (head_top - y1 + gh * 0.24)
            if ends_with_pill and ay < SAFE["top"] - y0:
                # không đủ chỗ trên đầu → thu nhỏ cả nhóm cho vừa [mép trên, đỉnh đầu]
                k = max(0.55, (head_top - 22 - SAFE["top"]) / gh)
                for sp in g.spans:
                    sp.size = max(int(sp.size * k), 18); sp.dx *= k; sp.dy *= k
                x0, y0, x1, y1 = group_extent(g)
                ay = head_top - y1 - 22
            ay = max(ay, SAFE["top"] - y0)
            # đầu sát mép trên (quay cận) → chữ bị đầu che quá nửa → đưa cả cụm xuống trước ngực, không để mất chữ
            if g.layer == "behind_subject" and (ay + y1 - head_top) / max(gh, 1) > 0.5:
                MOVED_DOWN.add(g.id)
                down[g.id] = (max(zy(med("chest_y")), zy(med("face_bottom")) - y0 + 24), y0, y1)
                ay = down[g.id][0]
        elif g.zone == "chest":
            chest = zy(med("chest_y"))
            face_bottom = zy(med("face_bottom"))
            ay = max(chest, face_bottom - y0 + 24)
        else:
            ay = H * 0.76
        ay = min(ay, H - SAFE["bottom"] - y1)
        ax = g.anchor_x * W
        ax = min(max(ax, SAFE["side"] - x0), W - SAFE["side"] - x1)
        pos[g.id] = (ax, ay)
    # nhóm vừa đưa xuống: né các nhóm lớp trước đang hiện cùng lúc (xuống dưới; hết chỗ thì lên trên chúng)
    for gid, (want, y0, y1) in down.items():
        g = next(x for x in plan.text_groups if x.id == gid)
        occ = sorted((pos[o.id][1] + group_extent(o)[1], pos[o.id][1] + group_extent(o)[3])
                     for o in plan.text_groups if o.enabled and o.id != gid and o.id in pos
                     and layer_of(o) == "front_of_subject" and o.start < g.end and g.start < o.end)
        ay = want
        for a, b in occ:
            if ay + y0 < b + 20 and ay + y1 > a - 20:
                ay = b + 20 - y0
        if ay > H - SAFE["bottom"] - y1:
            ay = min([a for a, _ in occ] + [H - SAFE["bottom"]]) - 20 - y1
        pos[gid] = (pos[gid][0], ay)
    return pos


# ---------------- compositor ----------------
def overlay_mg(out: np.ndarray, plan: Plan, f: int) -> np.ndarray:
    """MG che toàn khung; lúc vào/ra tấm MG trượt ngang đè lên video, mép trước có bóng đổ."""
    for seg in plan.mg:
        m = MG.render_scene_frame(seg, f)
        if m is None:
            continue
        dx = int(round(MG.mg_slide(seg, f)))
        if dx == 0:
            out = m
            continue
        W = out.shape[1]
        x0, x1 = max(dx, 0), min(W + dx, W)
        xs = np.arange(W)
        edge = x0 - 1 if dx > 0 else x1
        sh = 1 - 0.45 * np.exp(-np.abs(xs - edge) / 40.0) * ((xs < x0) if dx > 0 else (xs >= x1))
        out = out * sh[None, :, None]
        out[:, x0:x1] = m[:, x0 - dx:x1 - dx]
    return out


WW, WH = 1920, 1080          # khổ ngang
TXT_K = 0.62                 # chữ / thẻ / lớp HyperFrames khi chuyển sang khổ ngang (giữ vị trí so với người)


class Wide:
    """khổ ngang 16:9 dựng CÙNG LÚC với khổ dọc (một lượt đọc khung hình).
    Clip quay dọc: người ở giữa (khung dọc thu 0,5625), hai bên là bản mờ của chính khung hình.
    Clip quay ngang: khung gốc (rc_wide — proxy ngang ghép theo cùng các đoạn giữ), người đúng chỗ quay.
    Chữ / thẻ / HyperFrames: lớp vẽ ở khổ dọc thu TXT_K quanh tâm, cùng tâm với người → giữ tương quan (chữ sau đầu vẫn sau đầu).
    Cảnh Motion Graphics che toàn khung: đặt giữa, nền là bản mờ của chính cảnh đó."""

    def __init__(self, out_video: str, fps: int, W: int, H: int, wide_video: str | None):
        self.W, self.H = W, H
        self.k = WH / H                                         # khung dọc → cột giữa khung ngang
        self.cw = int(round(W * self.k))
        self.x0 = (WW - self.cw) // 2
        self.src = _frames(wide_video, WW, WH) if wide_video else None
        self.enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WW}x{WH}",
                                     "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                                     "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_video], stdin=subprocess.PIPE)
        self.M = np.float32([[TXT_K, 0, WW / 2 - TXT_K * W / 2], [0, TXT_K, WH / 2 - TXT_K * H / 2]])
        self.last = None

    def _fill(self, img):
        """nền mờ: phủ kín khung ngang từ một khung dọc."""
        small = cv2.resize(img, (WW // 8, int(WW / 8 * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
        y0 = (small.shape[0] - WH // 8) // 2
        small = cv2.GaussianBlur(small[y0:y0 + WH // 8], (0, 0), 6)
        return cv2.resize(small, (WW, WH), interpolation=cv2.INTER_LINEAR) * 0.55

    def _col(self, img, interp=cv2.INTER_AREA):
        return cv2.resize(img, (self.cw, WH), interpolation=interp)

    def frame(self, base, alpha, behind, front, mg_out, mg_mask, flash, z, zcx, zcy):
        if self.src is not None:                                 # quay ngang: khung gốc + alpha kéo về đúng tỉ lệ
            try:
                wb = next(self.src).astype(np.float32) / 255.0
            except StopIteration:
                wb = self.last if self.last is not None else np.zeros((WH, WW, 3), np.float32)
            if z > 1.0005:
                Mz = np.float32([[z, 0, (1 - z) * zcx * WW], [0, z, (1 - z) * zcy * WH]])
                wb = cv2.warpAffine(wb, Mz, (WW, WH), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            wa = cv2.resize(alpha, (WW, WH), interpolation=cv2.INTER_LINEAR)
        else:                                                    # quay dọc: cột giữa + nền mờ
            wb = self._fill(base)
            wb[:, self.x0:self.x0 + self.cw] = self._col(base)
            wa = np.zeros((WH, WW), np.float32)
            wa[:, self.x0:self.x0 + self.cw] = self._col(alpha, cv2.INTER_LINEAR)
        self.last = wb
        bh = cv2.warpAffine(behind, self.M, (WW, WH), flags=cv2.INTER_LINEAR)
        fr = cv2.warpAffine(front, self.M, (WW, WH), flags=cv2.INTER_LINEAR)
        out = wb * (1 - bh[..., 3:4]) + bh[..., :3]
        if bh[..., 3].any():
            am = wa[..., None]
            out = out * (1 - am) + wb * am
        out = out * (1 - fr[..., 3:4]) + fr[..., :3]
        if mg_mask is not None:                                  # cảnh MG: đặt giữa, nền mờ của chính cảnh (đang trượt vào → che theo mép)
            cov = float(mg_mask.mean())
            col = self._col(mg_out)
            if cov > 0.98:
                out = self._fill(mg_out)
                out[:, self.x0:self.x0 + self.cw] = col
            else:
                m = self._col(mg_mask.astype(np.float32), cv2.INTER_LINEAR)[..., None]
                seg = out[:, self.x0:self.x0 + self.cw]
                out[:, self.x0:self.x0 + self.cw] = seg * (1 - m) + col * m
        if flash > 0:
            out = out + (1 - out) * flash
        fr8 = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
        self.enc.stdin.write(fr8.tobytes())
        return fr8

    def close(self):
        self.enc.stdin.close()
        self.enc.wait()
        if self.src is not None:
            self.src.close()


def composite(plan: Plan, rc: dict, anchors_src: list[dict], out_video: str, frame_range=None,
              progress=None, snapshots: list[int] | None = None, snap_dir: Path | None = None,
              cancel=None, hf_items: list[dict] | None = None, wide_out: str | None = None):
    W, H, fps = plan.width, plan.height, plan.fps
    anchors_tl = timeline_anchors(plan, anchors_src)
    pos = resolve_layout(plan, anchors_tl, W, H)
    groups = [g for g in plan.text_groups if g.enabled]
    MG.chain(plan.mg)
    cards = [v for v in plan.visuals if v.enabled and v.status == "ready" and v.file]
    cpos = {v.id: card_layout(plan, v, anchors_tl, W, H) for v in cards}
    from . import callouts as CO
    cos = [c for c in plan.callouts if c.get("enabled", True)]
    colay = CO.layout_all(plan, anchors_tl, W, H)
    a0, a1 = frame_range or (0, plan.duration_frames)
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
                            "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_video], stdin=subprocess.PIPE)
    written = 0
    last_frame = None
    vid = _frames(rc["video"], W, H)
    alp = _frames(rc["alpha"], W, H, gray=True)
    from .hyper.overlay import Overlays
    OV = Overlays(hf_items or [], W, H, fps)          # lớp HyperFrames (alpha) đã render sẵn — th_hf.prerender
    WD = Wide(wide_out, fps, W, H, rc.get("video_wide")) if wide_out else None
    wlast = None
    for f, (img, a) in enumerate(zip(vid, alp)):
        if f < a0:
            continue
        if f >= a1:
            break
        if cancel and cancel():
            enc.kill(); raise RuntimeError("cancelled")
        base = img.astype(np.float32) / 255.0
        alpha = a.astype(np.float32) / 255.0
        z, zcx, zcy = zoom_at(plan, f)
        if z > 1.0005:
            M = np.float32([[z, 0, (1 - z) * zcx * W], [0, z, (1 - z) * zcy * H]])
            base = cv2.warpAffine(base, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
            alpha = cv2.warpAffine(alpha, M, (W, H), flags=cv2.INTER_LINEAR)
        active = [g for g in groups if g.start <= f < g.end]
        behind = np.zeros((H, W, 4), np.float32)
        front = np.zeros((H, W, 4), np.float32)
        if OV:
            for buf, lay in ((behind, "behind_subject"), (front, "front")):
                hg = OV.rgba(f / fps, lay)
                if hg is not None:                     # premultiplied như các lớp chữ của Talking Head; vẽ TRƯỚC chữ/thẻ cùng lớp
                    buf[..., :3] = hg[..., :3] * hg[..., 3:4]
                    buf[..., 3] = hg[..., 3]
        for v in cards:
            if v.start <= f < v.end:
                draw_card(behind if v.zone == "above_head" else front, v, f, *cpos[v.id])
        for g in active:
            ax, ay = pos[g.id]
            draw_group(behind if layer_of(g) == "behind_subject" else front, g, f, ax, ay)
        for c in cos:
            L = colay.get(c["id"], {})
            CO.draw(behind if L.get("layer") == "behind" else front, c, L, f)
        out = base * (1 - behind[..., 3:4]) + behind[..., :3]
        if behind[..., 3].any():
            am = alpha[..., None]
            out = out * (1 - am) + base * am          # nhân vật đè lên chữ phía sau
        out = draw_highlights(out, plan, f, z, zcx, zcy)
        out = out * (1 - front[..., 3:4]) + front[..., :3]
        pre = out
        out = overlay_mg(out, plan, f)
        fl = flash_at(plan, f)
        if WD and f >= a0:
            mgm = None
            if out is not pre:
                mgm = np.abs(out - pre).max(axis=2) > 0.004
                mgm = cv2.dilate(mgm.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) if mgm.any() else None
            wlast = WD.frame(base, alpha, behind, front, out, mgm, fl, z, zcx, zcy)
        if fl > 0:
            out = out + (1 - out) * fl                 # light wash: sáng dần về trắng, không cháy
        frame = (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
        enc.stdin.write(frame.tobytes()); written += 1; last_frame = frame
        if snapshots and f in snapshots and snap_dir:
            imgio.imwrite(str(snap_dir / f"snap_{f:05d}.jpg"), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
        if progress and f % 30 == 0:
            progress(f"render frame {f - a0}/{a1 - a0}")
    while last_frame is not None and written < a1 - a0:   # nguồn đọc thiếu frame → giữ frame cuối để khớp độ dài tiếng
        enc.stdin.write(last_frame.tobytes()); written += 1
        if WD and wlast is not None:
            WD.enc.stdin.write(wlast.tobytes())
    enc.stdin.close()
    enc.wait()
    if WD:
        WD.close()
    OV.close()
    vid.close(); alp.close()
    return pos


# ---------------- âm thanh ----------------
def mix_audio(plan: Plan, voice: str, sfx_dir: Path, manifest: dict, out_wav: str, frame_range=None,
              voice_gain_db=0.0, sfx_master_db=0.0) -> list[dict]:
    fps = plan.fps
    a0, a1 = frame_range or (0, plan.duration_frames)
    t0, t1 = a0 / fps, a1 / fps
    inputs = ["-i", voice]
    parts = [f"[0:a]atrim=start={t0}:end={t1},asetpts=PTS-STARTPTS,volume={voice_gain_db}dB[v]"]
    report = []
    k = 1
    # cooldown: không đặt 2 SFX có đỉnh cách nhau < 4 frame, giữ cái ưu tiên cao hơn
    chosen = []
    # tiếng chữ rơi: nhỏ (≤ -17 dB) và thưa — dòng dẫn dài chỉ kêu ~1/2 số chữ, đỡ nhức tai
    ticks, nth = [s for s in plan.sounds if s.enabled and s.asset == "u_tick"], {}
    drop = set()
    for s in sorted(ticks, key=lambda s: s.hit):
        j = nth[s.linked_event] = nth.get(s.linked_event, -1) + 1
        if j % 2 == 1:
            drop.add(s.id)
    for s in sorted([s for s in plan.sounds if s.enabled and s.id not in drop], key=lambda s: -s.priority):
        if s.asset == "u_tick":
            s.gain_db = min(s.gain_db, -17)
        if any(abs(s.hit - c.hit) < 4 for c in chosen):
            report.append({"id": s.id, "status": "skipped_cooldown"}); continue
        chosen.append(s)
    for s in sorted(chosen, key=lambda s: s.hit):
        if not (a0 <= s.hit < a1):
            continue
        m = manifest[s.asset]
        peak = m["peak_offset_ms"] / 1000 if s.peak_offset_ms == 0 else s.peak_offset_ms / 1000
        start = s.hit / fps - t0 - peak
        trim = 0.0
        if start < 0:
            trim, start = -start, 0.0
        inputs += ["-i", str(sfx_dir / m["file"])]
        parts.append(f"[{k}:a]aresample=48000,atrim=start={trim},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.004,volume={s.gain_db + sfx_master_db + m.get('norm_db', 0)}dB,adelay={int(start * 1000)}|{int(start * 1000)}[s{k}]")
        report.append({"id": s.id, "asset": s.asset, "linked": s.linked_event, "hit_frame": s.hit,
                       "start_s": round(start + t0, 3), "peak_offset_ms": m["peak_offset_ms"],
                       "gain_db": s.gain_db, "trimmed_head_s": round(trim, 3), "status": "placed"})
        k += 1
    mix_in = "[v]" + "".join(f"[s{i}]" for i in range(1, k))
    parts.append(f"{mix_in}amix=inputs={k}:normalize=0:duration=first[mx]")
    tmp = out_wav + ".pre.wav"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(parts), "-map", "[mx]",
         "-ar", "48000", "-ac", "1", tmp])
    # loudnorm 2 pass: -16 LUFS, TP -1.5 (để sau mã hoá AAC vẫn ≤ -1 dBTP)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af",
                        "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
         f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
         f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true",
         "-ar", "48000", out_wav])
    Path(tmp).unlink(missing_ok=True)
    return report


def mux(video: str, audio: str, out: str, duration: float | None = None):
    # không dùng -shortest (ffmpeg có thể cắt hụt vài frame cuối); cắt theo đúng độ dài timeline
    t = ["-t", f"{duration:.4f}"] if duration else []
    run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-ar", "48000", *t, "-movflags", "+faststart", out])


def change_speed(path: str, speed: float, fps: int = 30):
    """đổi tốc độ file đã xuất (hình + tiếng cùng lúc → chữ/MG/âm thanh không lệch nhau); giọng giữ cao độ (atempo)."""
    tmp = path + ".speed.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", path, "-filter_complex",
         f"[0:v]setpts=PTS/{speed},fps={fps}[v];[0:a]atempo={speed}[a]", "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-movflags", "+faststart", tmp])
    os.replace(tmp, path)


# ---------------- thẻ ảnh tư liệu ----------------
_CARD_CACHE: dict = {}


def _card_sprite(v, kb: float) -> np.ndarray:
    """Thẻ ảnh bo góc + viền trắng mảnh + bóng; kb = mức Ken Burns (zoom chậm bên trong)."""
    from .typography import span_sprite
    from .schema import TextSpan
    key = (v.file, v.width)
    if key not in _CARD_CACHE:
        img = cv2.cvtColor(imgio.must_read(v.file), cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        _CARD_CACHE[key] = img
    img = _CARD_CACHE[key]
    h0, w0 = img.shape[:2]
    W = v.width
    H = int(W * h0 / w0)
    # Ken Burns: crop trung tâm thu nhỏ dần
    cw, ch = int(w0 / kb), int(h0 / kb)
    x0, y0 = (w0 - cw) // 2, (h0 - ch) // 2
    pic = cv2.resize(img[y0:y0 + ch, x0:x0 + cw], (W, H), interpolation=cv2.INTER_AREA)
    r, b, pad = 30, 5, 40
    mask = np.zeros((H, W), np.uint8)
    cv2.rectangle(mask, (r, 0), (W - r, H), 255, -1); cv2.rectangle(mask, (0, r), (W, H - r), 255, -1)
    for cx, cy in [(r, r), (W - r, r), (r, H - r), (W - r, H - r)]:
        cv2.circle(mask, (cx, cy), r, 255, -1, cv2.LINE_AA)
    m = mask.astype(np.float32) / 255.0
    inner = cv2.erode(mask, np.ones((2 * b + 1, 2 * b + 1), np.uint8)).astype(np.float32) / 255.0
    out = np.zeros((H + 2 * pad, W + 2 * pad, 4), np.float32)
    sh = cv2.GaussianBlur(m, (0, 0), 14) * 0.45
    out[pad + 10:pad + 10 + H, pad:pad + W, 3] = sh
    rgb = pic * inner[..., None] + (1 - inner[..., None])          # viền trắng
    reg = out[pad:pad + H, pad:pad + W]
    reg[..., :3] = reg[..., :3] * (1 - m[..., None]) + rgb * m[..., None]
    reg[..., 3] = reg[..., 3] * (1 - m) + m
    if v.label:
        lab = span_sprite(TextSpan(text=v.label, font_role="body_bold", size=30, color="#FFFFFF"), shadow=0.8)
        _blend(out, lab, pad + 26, pad + 18)
    return out


def card_layout(plan: Plan, v, anchors_tl, W: int, H: int) -> tuple[float, float]:
    fr = [anchors_tl[f] for f in range(max(v.start, 0), min(v.end, len(anchors_tl)))] or [anchors_tl[0]]
    head_top = float(np.nanmedian([a["head_top"] for a in fr])) * H
    face_cx = float(np.nanmedian([a["face_cx"] for a in fr])) * W
    img = imgio.must_read(v.file)
    ch = v.width * img.shape[0] / img.shape[1]
    # đáy thẻ chồng ~22% xuống dưới đỉnh đầu → đầu che thật mép dưới thẻ
    cy = head_top - ch / 2 + ch * 0.22
    cy = max(cy, SAFE["top"] + ch / 2)
    cx = min(max(face_cx, SAFE["side"] + v.width / 2), W - SAFE["side"] - v.width / 2)
    return cx, cy


def draw_card(layer: np.ndarray, v, f: int, cx: float, cy: float):
    if not (v.start <= f < v.end):
        return
    from .typography import clamp01, ease_out_quart, ease_in_cubic
    e = clamp01((f - v.start + 1) / v.enter_frames)
    x = clamp01((f - (v.end - v.exit_frames) + 1) / v.exit_frames)
    k = ease_out_quart(e)
    s = (0.86 + 0.14 * k) * (1 - 0.04 * ease_in_cubic(x))
    o = clamp01(e * 1.5) * (1 - x)
    blur = (1 - k) * 10 + ease_in_cubic(x) * 8
    dy = (1 - k) * 40 - ease_in_cubic(x) * 30
    kb = 1.0 + 0.06 * (f - v.start) / max(v.end - v.start, 1)
    spr = _card_sprite(v, kb)
    spr = cv2.resize(spr, None, fx=s, fy=s, interpolation=cv2.INTER_LINEAR)
    if blur > 0.6:
        spr = cv2.GaussianBlur(spr, (0, 0), blur / 2)
    h, w = spr.shape[:2]
    _blend(layer, spr * o, int(cx - w / 2), int(cy + dy - h / 2))
