"""Orchestrator: project trên đĩa + các bước có checkpoint. Dùng chung cho CLI và web UI.

projects/<id>/
  project.json         transcript, plan hiện tại, danh sách render
  proxy/               proxy SDR 1080x1920@30 + wav ASR (nguồn gốc không bị sửa)
  work/                alpha.mp4, anchors.json, rough cut
  renders/vNNN/        mp4 + plan.json + qa.json của từng lần render (giữ mọi version)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from . import render as R, timeline as T
from .planner import make_plan
from .qa import check_output
from .schema import MediaInfo, Plan, Project, Sentence, TranscriptWord
from .sfx import SFX_DIR, ensure_library

from .paths import ROOT
PROJECTS = Path(os.environ.get("CCUT_PROJECTS") or ROOT / "projects")   # app đặt CCUT_PROJECTS = thư mục dự án đang mở


class Ctx:
    def __init__(self, pid: str, log=print, cancel=None):
        self.dir = PROJECTS / pid
        from . import fonts as FT
        FT.use_project(self.dir)                  # font + cách vẽ chữ theo ngôn ngữ của dự án
        self.log = log
        self.cancel = cancel or (lambda: False)
        p = self.dir / "project.json"
        self.project = Project.model_validate_json(p.read_text(encoding="utf-8")) if p.exists() else Project(id=pid, name=pid)

    def save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "project.json.tmp"
        tmp.write_text(self.project.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(self.dir / "project.json")

    def path(self, *a) -> Path:
        q = self.dir.joinpath(*a)
        q.parent.mkdir(parents=True, exist_ok=True)
        return q


def probe_source(path: str) -> MediaInfo:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", path],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"Không đọc được media: {r.stderr[:300]}")
    j = json.loads(r.stdout)
    v = next((s for s in j["streams"] if s["codec_type"] == "video"), None)
    if not v:
        raise RuntimeError("Tệp không có video stream")
    rot = 0
    for sd in v.get("side_data_list", []):
        rot = int(sd.get("rotation", rot))
    num, den = map(int, v["r_frame_rate"].split("/"))
    return MediaInfo(path=path, duration=float(j["format"]["duration"]), width=v["width"], height=v["height"],
                     fps=num / den, rotation=rot, hdr=v.get("color_transfer") in ("arib-std-b67", "smpte2084"),
                     has_audio=any(s["codec_type"] == "audio" for s in j["streams"]),
                     size_bytes=int(j["format"].get("size", 0)))


def step_ingest(c: Ctx, source: str):
    info = probe_source(source)
    c.project.source = info
    if not info.has_audio:
        raise RuntimeError("Video nguồn không có audio — không thể phân tích lời nói")
    proxy = c.path("proxy", "proxy.mov")
    if not proxy.exists():
        c.log(f"Tạo proxy 1080x1920@30 (nguồn {info.width}x{info.height}@{info.fps:.2f}, HDR={info.hdr})")
        # scale trước rồi tonemap → nhanh hơn nhiều so với tonemap ở 4K
        tm = ("zscale=w=1080:h=1920:f=lanczos,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,"
              "tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,") if info.hdr else "scale=1080:1920:flags=lanczos,"
        R.run(["ffmpeg", "-v", "error", "-y", "-i", source, "-map", "0:v:0", "-map", "0:a:0",
               "-vf", tm + "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-g", "30",
               "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "1", str(proxy) + ".part.mov"])
        R.run(["ffmpeg", "-v", "error", "-y", "-i", str(proxy) + ".part.mov", "-vn", "-ar", "16000", "-ac", "1",
               str(c.path("proxy", "asr16k.wav"))])
        Path(str(proxy) + ".part.mov").replace(proxy)   # chỉ thành file chính khi đã tạo xong (dừng giữa chừng không để lại proxy hỏng)
    c.project.proxy = str(proxy)
    c.project.status = "uploaded"
    c.save()


def step_transcribe(c: Ctx, vocab=None, model="large-v3"):
    from .transcribe import transcribe
    tj = c.path("work", "transcript.json")
    d = None
    if tj.exists():
        try:
            d = json.loads(tj.read_text(encoding="utf-8"))
        except ValueError:          # file dở dang từ lần chạy lỗi trước → chép lời lại
            tj.unlink()
    if d:
        words = [TranscriptWord(**w) for w in d["words"]]
        sents = [Sentence(**s) for s in d["sentences"]]
    else:
        words, sents = transcribe(str(c.path("proxy", "asr16k.wav")), model, vocab, progress=c.log)
        tmp = tj.with_suffix(".json.part")
        tmp.write_text(json.dumps({"words": [w.model_dump() for w in words],
                                   "sentences": [s.model_dump() for s in sents]}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(tj)
        from .transcribe import LAST
        from . import fonts as FT
        FT.set_language(c.path(), LAST["language"])
    if not c.project.words:
        from .transcribe import fix_numbers
        for m in fix_numbers(words):
            c.log(f"sửa số ASR {m}")
        c.project.words, c.project.sentences = words, sents
    c.project.status = "analyzed"
    c.save()


def step_matting(c: Ctx):
    from .matting import run_matting
    if not c.path("work", "anchors.json").exists():
        run_matting(c.project.proxy, str(c.path("work", "alpha.mp4")), str(c.path("work", "anchors.json")),
                    progress=c.log)


def step_plan(c: Ctx, force=False):
    if c.project.plan is None or force:
        c.project.plan = make_plan(c.project.words, c.project.sentences, c.project.source.duration, media=c.project.proxy)
    c.project.status = "designed"
    c.save()


def denoise_voice(src: str, out: str, log=print, sr=48000):
    """khử ồn theo CHÍNH clip: lấy mẫu ồn từ 15% khung yên nhất → noisereduce (stationary) → nâng giọng về ~−20 dB
    → gate nhẹ ở chỗ nghỉ. Bộ lọc cố định cũ (afftdn nf=−46) gần như không ăn với clip thu nhỏ / ồn phòng."""
    import wave
    import numpy as np
    import noisereduce as nr
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-vn", "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)
    h = int(sr * 0.02)
    n = len(x) // h
    fr = x[:n * h].reshape(n, h)
    lv = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    speech, noise = float(np.percentile(lv, 90)), float(np.percentile(lv, 10))
    y = nr.reduce_noise(y=x, sr=sr, y_noise=fr[lv <= np.percentile(lv, 15)].ravel(), stationary=True,
                        prop_decrease=0.9, n_fft=2048)
    ly = 20 * np.log10(np.sqrt((y[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)
    gain = max(0.0, min(24.0, -20.0 - float(np.percentile(ly, 90))))
    thr = min(-36.0, float(np.percentile(ly, 10)) + gain + 8)
    log(f"Khử tạp âm giọng theo clip (giọng {speech:.0f} dB, ồn nền {noise:.0f} dB → nâng {gain:.0f} dB)")
    tmp = out + ".nr.wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
    R.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
           f"highpass=f=80,volume={gain:.1f}dB,agate=threshold={10 ** (thr / 20):.4f}:ratio=3:range=0.1:attack=5:release=200",
           "-ar", str(sr), "-ac", "1", out])
    Path(tmp).unlink(missing_ok=True)


def step_render(c: Ctx, frame_range=None, label="full", plan: Plan | None = None) -> dict:
    from .license import require
    require("talking-head-style", c.dir, c.log)          # skill bán: đã mua hoặc còn lượt thử (1 lượt = 1 dự án)
    plan = plan or c.project.plan
    T.build_mapping(plan)
    from .channels import theme
    theme(plan.mg, c.dir)          # nền + màu thẻ MG theo kênh của video
    man = ensure_library()
    n = len(c.project.renders) + 1
    vdir = c.path("renders", f"v{n:03d}_{label}", "x").parent
    c.project.status = "rendering"; c.save()
    t0 = time.time()
    c.log("Dựng thô (ghép đoạn giữ, alpha và voice cùng mapping)")
    clean = c.path("work", "voice_clean2.wav")
    if c.project.style.get("voice_preprocessed"):
        c.log("Giọng đã được người dùng lọc sẵn — giữ nguyên, không khử tạp âm thêm")
        clean = Path(c.project.proxy)
    elif not clean.exists():
        denoise_voice(c.project.proxy, str(clean), c.log)
    rc = R.rough_cut(plan, c.project.proxy, str(c.path("work", "alpha.mp4")), vdir, str(clean))
    if c.project.style.get("hf_denoise"):
        from .declean import reduce_hf_noise
        c.log("Giảm tiếng máy/nhiễu tần cao trong giọng (giữ nguyên dải < 3.5 kHz)")
        reduce_hf_noise(rc["voice"], rc["voice"] + ".clean.wav")
        rc["voice"] = rc["voice"] + ".clean.wav"
    anchors = json.loads(c.path("work", "anchors.json").read_text())
    fr = frame_range or (0, plan.duration_frames)
    fr = (max(0, fr[0]), min(plan.duration_frames, fr[1]))
    snaps = sorted({g.hit + 3 for g in plan.text_groups if g.enabled and fr[0] <= g.hit < fr[1]})
    hf_items = []
    if plan.hf:
        from .th_hf import prerender
        c.log(f"HyperFrames: {len(plan.hf)} lớp (render 1 lần, lưu đệm)")
        hf_items = prerender(plan, c.path("work", "x").parent, c.log)
    c.log(f"Compositing frame {fr[0]}–{fr[1]}")
    layout = R.composite(plan, rc, anchors, str(vdir / "video_noaudio.mp4"), fr, progress=c.log,
                         snapshots=snaps, snap_dir=vdir, cancel=c.cancel, hf_items=hf_items)
    c.log("Phối âm voice + SFX, chuẩn loudness")
    rep = R.mix_audio(plan, rc["voice"], SFX_DIR, man, str(vdir / "mix.wav"), fr)
    out = vdir / f"{c.project.id}_{label}.mp4"
    R.mux(str(vdir / "video_noaudio.mp4"), str(vdir / "mix.wav"), str(out), (fr[1] - fr[0]) / plan.fps)
    issues, meta = check_output(plan, str(out), fr[1] - fr[0], rep, layout)
    sp = min(1.5, max(0.8, plan.speed or 1.0))
    if abs(sp - 1) > 0.005:
        c.log(f"Đổi tốc độ video ×{sp:g} (giọng giữ cao độ)")
        R.change_speed(str(out), sp, plan.fps)
    for f in ("rc_video.mp4", "rc_alpha.mp4", "video_noaudio.mp4"):
        (vdir / f).unlink(missing_ok=True)
    (vdir / "plan.json").write_text(plan.model_dump_json(indent=1))
    (vdir / "qa.json").write_text(json.dumps({"issues": [i.model_dump() for i in issues], "sound_report": rep,
                                              "layout_px": layout, **meta}, ensure_ascii=False, indent=1))
    rec = {"version": n, "label": label, "file": str(out.relative_to(ROOT)) if out.is_relative_to(ROOT) else str(out), "frames": list(fr),
           "seconds": round(time.time() - t0, 1), "status": "rendered_preview" if label != "final" else "exported",
           "approved": False, "issues": len([i for i in issues if i.severity != "info"])}
    c.project.renders.append(rec)
    c.project.status = "ready"
    c.save()
    return rec


def run_all(pid: str, source: str, frame_range=None, label="test", log=print, vocab=None):
    c = Ctx(pid, log)
    step_ingest(c, source)
    step_transcribe(c, vocab)
    step_matting(c)
    step_plan(c)
    return step_render(c, frame_range, label)
