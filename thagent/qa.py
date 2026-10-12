"""QA tự động: chỉ đo những gì đo được; phần nghe/nhìn để người dùng kiểm tra."""
from __future__ import annotations

import json
import re
import subprocess

from . import timeline as T
from .schema import Plan, QaIssue


def probe(path: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height,r_frame_rate,sample_rate,duration,nb_frames",
                        "-of", "json", path], capture_output=True, text=True)
    return json.loads(r.stdout)


def loudness(path: str) -> dict:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    s = r.stderr[r.stderr.rfind("Summary:"):]
    I = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    P = re.search(r"Peak:\s+(-?[\d.]+) dBFS", s)
    return {"integrated_lufs": float(I.group(1)) if I else None, "true_peak_dbtp": float(P.group(1)) if P else None}


def check_output(plan: Plan, out: str, expect_frames: int, sound_report: list[dict], layout: dict) -> list[QaIssue]:
    issues: list[QaIssue] = []
    p = probe(out)
    v = next(s for s in p["streams"] if s["codec_type"] == "video")
    a = [s for s in p["streams"] if s["codec_type"] == "audio"]
    n = 0
    def add(sev, kind, detail, tcode=""):
        nonlocal n
        n += 1
        issues.append(QaIssue(id=f"qa{n:02d}", severity=sev, kind=kind, detail=detail, timecode=tcode))
    if (v["width"], v["height"]) != (plan.width, plan.height):
        add("error", "size", f"kích thước {v['width']}x{v['height']}")
    if v["r_frame_rate"] != f"{plan.fps}/1":
        add("error", "fps", f"fps {v['r_frame_rate']}")
    if not a:
        add("error", "audio", "không có audio track")
    else:
        dv, da = float(v["duration"]), float(a[0]["duration"])
        if abs(dv - da) > 2 / plan.fps:
            add("warn", "av_duration", f"video {dv:.3f}s vs audio {da:.3f}s lệch {abs(dv - da) * 1000:.0f}ms")
        if abs(dv - expect_frames / plan.fps) > 1 / plan.fps:
            add("warn", "duration", f"thời lượng {dv:.3f}s, kỳ vọng {expect_frames / plan.fps:.3f}s")
    ld = loudness(out)
    if ld["integrated_lufs"] is not None and abs(ld["integrated_lufs"] + 16) > 1.0:
        add("warn", "loudness", f"{ld['integrated_lufs']} LUFS (mục tiêu -16)")
    if ld["true_peak_dbtp"] is not None and ld["true_peak_dbtp"] > -1.0:
        add("warn", "true_peak", f"{ld['true_peak_dbtp']} dBTP > -1")
    for g in plan.text_groups:
        if g.enabled and (g.end - g.start) < 30:
            add("warn", "read_time", f"{g.id} chỉ hiển thị {(g.end - g.start) / plan.fps:.2f}s", T.tc(g.start))
    for s in sound_report:
        if s.get("status") == "skipped_cooldown":
            add("info", "sfx_cooldown", f"{s['id']} bị bỏ do quá gần SFX ưu tiên cao hơn")
    for vis in plan.visuals:
        if vis.status == "missing_asset":
            add("warn", "missing_asset", f"{vis.illustrates} — chưa có tư liệu thật, giữ talking head", T.tc(vis.start))
    add("info", "needs_human", "Cần NGHE kiểm tra mức SFX so với giọng và NHÌN viền mask (tóc/tay) — chưa thể tự đánh giá cảm nhận.")
    issues_meta = {"loudness": ld, "probe": p}
    return issues, issues_meta
