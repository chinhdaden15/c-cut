"""Trộn âm: voice gốc giữ nguyên (không đổi tốc độ/cao độ/âm lượng), SFX theo sự kiện, nhạc nền tự hạ dưới voice."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from ..paths import ROOT

SFX_DIR = ROOT / "assets" / "sfx"


def probe(path: str) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,codec_name,channels,sample_rate,width,height,r_frame_rate",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"không đọc được file: {path}")
    return json.loads(r.stdout)


def sfx_path(name: str) -> Path:
    p = Path(name)
    if p.is_absolute() and p.exists():
        return p
    for cand in (SFX_DIR / name, SFX_DIR / f"{name}.wav"):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"không có SFX “{name}” trong assets/sfx")


def sfx_names() -> list[str]:
    return sorted(p.stem for p in SFX_DIR.glob("*.wav"))


def mix(tl, voice: str, out: Path, music: dict | None = None) -> dict:
    """→ out (m4a AAC 48 kHz stereo). Trả báo cáo đỉnh âm."""
    dur = tl.duration
    ins = ["-i", voice]
    parts = ["[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad=whole_dur=%.3f[v0]" % dur]
    labels = ["[v]"]
    events = []
    for sc in tl.scenes:
        for e in sc.get("audio_events", []):
            events.append(dict(e))
    if tl.theme.get("sfx_auto", True):          # SFX tự động theo chuyển động thật của bản này (kho sfx_v2m)
        from .sfxkit import auto_events
        events += auto_events(tl)
    from .sfxkit import pick
    rk: dict = {}
    for e in events:   # vai trò → âm cụ thể trong kho (xoay vòng); đỉnh âm đặt đúng thời điểm hành động
        role = e.get("role") or (e["sfx"][5:] if str(e.get("sfx", "")).startswith("role:") else None)
        if role:
            k = e.get("k", rk.get(role, 0))
            rk[role] = k + 1
            it = pick(role, k)
            if it is None:
                e["_skip"] = True
                continue
            e["_path"], e["_peak"] = it["path"], it["peak_ms"] / 1000
            e.setdefault("gain_db", it["gain_db"])
        else:
            e["_path"], e["_peak"] = str(sfx_path(e["sfx"])), 0.0
    events = [e for e in events if not e.get("_skip")]
    for i, e in enumerate(events, start=1):
        ins += ["-i", e["_path"]]
        ms = max(int((float(e["t"]) - e["_peak"]) * 1000), 0)
        fade = float(e.get("fade", 0))
        f = f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={float(e.get('gain_db', -12))}dB"
        if fade:
            f += f",afade=t=out:st=0:d={fade}"
        parts.append(f + f",adelay={ms}|{ms}[s{i}]")
        labels.append(f"[s{i}]")
    if music and music.get("path"):
        k = len(events) + 1
        ins += ["-stream_loop", "-1", "-i", tl.path(music["path"])]
        parts.append(f"[{k}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,"
                     f"volume={float(music.get('gain_db', -20))}dB,atrim=0:{dur:.3f}[m0]")
        if music.get("duck", True):
            parts.append("[v0]asplit=2[v][vk]")
            parts.append("[m0][vk]sidechaincompress=threshold=0.03:ratio=6:attack=20:release=350[m]")
        else:
            parts.append("[m0]anull[m]")
        labels.append("[m]")
    if not (music and music.get("path") and music.get("duck", True)):
        parts.insert(1, "[v0]anull[v]")
    if len(labels) > 1:
        parts.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0:duration=first[mx]")
    else:
        parts.append("[v]anull[mx]")
    parts.append(f"[mx]atrim=0:{dur:.3f}[o]")
    tmp = out.with_suffix(".raw.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", ";".join(parts), "-map", "[o]", str(tmp)],
                   check=True)
    peak = peak_db(tmp)
    lim = peak > -1.0
    af = ["-af", "alimiter=limit=0.89:level=false"] if lim else []   # chỉ chặn đỉnh khi vượt −1 dBFS
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), *af, "-c:a", "aac", "-b:a", "192k", str(out)], check=True)
    tmp.unlink(missing_ok=True)
    return {"sfx": len(events), "music": bool(music and music.get("path")), "peak_db": round(peak, 2), "limited": lim}


def peak_db(path) -> float:
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else 0.0


def mux(video: Path, audio: Path, out: Path, dur: float):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-i", str(audio), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "copy", "-t", f"{dur:.3f}", "-movflags", "+faststart", str(out)], check=True)
