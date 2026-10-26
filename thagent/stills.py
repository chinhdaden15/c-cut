"""Ảnh tĩnh xem trước (không render video): vẽ đúng như renderer tại các frame chỉ định.

python -m thagent.stills <project> [frame ...]     # không truyền frame → tự lấy điểm nhấn + đầu mỗi cảnh MG
Ghi: projects/<id>/stills/f_<frame>.jpg và contact sheet projects/<id>/stills/sheet.jpg
"""
from __future__ import annotations

import json
import subprocess
import sys

import cv2
import numpy as np

from . import imgio
from . import mg as MG, pipeline as P, render as R, timeline as T
from .typography import draw_group

W, H = 1080, 1920


def _grab(path: str, src_frame: int, gray=False) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{src_frame / 30:.4f}", "-i", path, "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "gray" if gray else "rgb24", "-"], capture_output=True).stdout
    shape = (H, W) if gray else (H, W, 3)
    return np.frombuffer(raw, np.uint8).reshape(shape).astype(np.float32) / 255


def render_stills(pid: str, frames: list[int] | None = None) -> list[str]:
    c = P.Ctx(pid)
    pl = c.project.plan
    T.build_mapping(pl)
    from .channels import theme
    theme(pl.mg, c.dir)
    anchors = json.loads(c.path("work", "anchors.json").read_text())
    from . import callouts as _CO
    _CO.attach_objects(anchors, c.path("work", "gaze.json"), pl.fps)
    atl = R.timeline_anchors(pl, anchors)
    pos = R.resolve_layout(pl, atl, W, H)
    cards = [v for v in pl.visuals if v.enabled and v.status == "ready" and v.file]
    cpos = {v.id: R.card_layout(pl, v, atl, W, H) for v in cards}
    from . import callouts as CO
    cos = [x for x in pl.callouts if x.get("enabled", True)]
    colay = CO.layout_all(pl, atl, W, H)
    if not frames:
        frames = sorted({g.hit + 4 for g in pl.text_groups if g.enabled} |
                        {int(x["end"]) - CO.EXIT - 4 for x in cos} |
                        {sc["start"] + 25 for m in pl.mg for sc in m["scenes"]})
    out_dir = c.path("stills", "x").parent
    for old in out_dir.glob("*.jpg"):
        old.unlink()
    files, thumbs = [], []
    for f in frames:
        f = max(0, min(f, pl.duration_frames - 1))
        sf = T.tl_to_src_frame(pl, f)
        base = _grab(c.project.proxy, sf)
        a = _grab(str(c.path("work", "alpha.mp4")), sf, gray=True)[..., None]
        z, zcx, zcy = R.zoom_at(pl, f)
        if z > 1.0005:
            M = np.float32([[z, 0, (1 - z) * zcx * W], [0, z, (1 - z) * zcy * H]])
            base = cv2.warpAffine(base, M, (W, H), borderMode=cv2.BORDER_REFLECT)
            a = cv2.warpAffine(a[..., 0], M, (W, H))[..., None]
        bh = np.zeros((H, W, 4), np.float32); fr = bh.copy()
        for v in cards:
            R.draw_card(bh if v.zone == "above_head" else fr, v, f, *cpos[v.id])
        for g in pl.text_groups:
            if g.enabled and g.start <= f < g.end:
                draw_group(bh if R.layer_of(g) == "behind_subject" else fr, g, f, *pos[g.id])
        for x in cos:
            L = colay.get(x["id"], {})
            CO.draw(bh if L.get("layer") == "behind" else fr, x, L, f)
        o = base * (1 - bh[..., 3:4]) + bh[..., :3]
        o = o * (1 - a) + base * a
        o = R.draw_highlights(o, pl, f, z, zcx, zcy)
        o = o * (1 - fr[..., 3:4]) + fr[..., :3]
        MG.chain(pl.mg)
        o = R.overlay_mg(o, pl, f)
        fl = R.flash_at(pl, f)
        if fl > 0:
            o = o + (1 - o) * fl
        img = cv2.cvtColor((np.clip(o, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2BGR)
        p = out_dir / f"f_{f:05d}.jpg"
        imgio.imwrite(str(p), img)
        files.append(str(p))
        t = cv2.resize(img, (270, 480))
        cv2.putText(t, T.tc(f), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        thumbs.append(t)
    if thumbs:
        cols = 6
        rows = [thumbs[i:i + cols] for i in range(0, len(thumbs), cols)]
        rows[-1] += [np.zeros_like(thumbs[0])] * (cols - len(rows[-1]))
        imgio.imwrite(str(out_dir / "sheet.jpg"), np.vstack([np.hstack(r) for r in rows]))
    return files


def main():
    fs = render_stills(sys.argv[1], [int(x) for x in sys.argv[2:]] or None)
    print(f"{len(fs)} ảnh tĩnh → projects/{sys.argv[1]}/stills/ (xem sheet.jpg)")


if __name__ == "__main__":
    main()
