"""Thư viện SFX. Mặc định sinh ÂM TỔNG HỢP TẠM (procedural, không trích từ video mẫu)
để kiểm tra kỹ thuật đồng bộ; người dùng thay bằng WAV/MP3 có quyền dùng trong
assets/sfx/ + cập nhật manifest. Mỗi asset lưu peak_offset_ms đo trực tiếp từ file."""
from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np

SR = 48000
from .paths import ROOT
SFX_DIR = ROOT / "assets" / "sfx"


def _write(path: Path, x: np.ndarray):
    x = x / (np.abs(x).max() + 1e-9) * 0.89
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def _bandnoise(n, lo, hi, rng):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    return np.fft.irfft(spec, n)


def _whoosh(dur=0.42, peak=0.30, seed=1):
    rng = np.random.default_rng(seed)
    n = int(dur * SR); t = np.arange(n) / SR
    # quét dải lọc: chồng nhiều dải theo thời gian
    out = np.zeros(n)
    for k, (lo, hi) in enumerate([(300, 1200), (800, 2500), (1500, 5000), (2500, 8000)]):
        c = (k + 1) / 5 * peak
        env = np.exp(-((t - c) ** 2) / (2 * 0.06 ** 2))
        out += _bandnoise(n, lo, hi, rng) * env
    env = np.minimum(t / peak, 1) ** 2 * np.exp(-np.maximum(t - peak, 0) / 0.07)
    return out * env


def _pop(dur=0.16):
    n = int(dur * SR); t = np.arange(n) / SR
    f = 900 * np.exp(-t / 0.03) + 380
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.minimum(t / 0.002, 1) * np.exp(-t / 0.035)
    return np.sin(ph) * env


def _impact(dur=0.6, seed=2):
    rng = np.random.default_rng(seed)
    n = int(dur * SR); t = np.arange(n) / SR
    f = 120 * np.exp(-t / 0.08) + 45
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.18)
    click = _bandnoise(n, 1500, 7000, rng) * np.exp(-t / 0.012) * 0.35
    return (body + click) * np.minimum(t / 0.003, 1)


def _shimmer(dur=0.7, seed=3):
    rng = np.random.default_rng(seed)
    n = int(dur * SR); t = np.arange(n) / SR
    tone = sum(np.sin(2 * np.pi * fr * t) / (i + 1) for i, fr in enumerate([1760, 2637, 3520]))
    air = _bandnoise(n, 4000, 12000, rng) * 0.4
    env = np.minimum(t / 0.12, 1) ** 2 * np.exp(-np.maximum(t - 0.12, 0) / 0.18)
    return (tone * 0.3 + air) * env


LIB = {
    "whoosh_short": (_whoosh, "lướt/whoosh ngắn"),
    "pop_soft": (_pop, "pop/tap nhẹ"),
    "impact_soft": (_impact, "impact mềm"),
    "shimmer_light": (_shimmer, "transition nhẹ / lóe sáng"),
}


def measure_peak_ms(path: Path) -> float:
    with wave.open(str(path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
        sr = w.getframerate()
    win = int(sr * 0.005)
    e = np.convolve(x ** 2, np.ones(win) / win, "same")
    return round(float(np.argmax(e)) / sr * 1000, 1)


def ensure_library() -> dict:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    man_path = SFX_DIR / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    for name, (fn, desc) in LIB.items():
        p = SFX_DIR / f"{name}.wav"
        if not p.exists():
            _write(p, fn())
        man.setdefault(name, {"file": p.name, "category": desc,
                              "source": "procedural synth (thagent/sfx.py) — ÂM TẠM để kiểm tra kỹ thuật",
                              "license": "tự sinh, không giới hạn"})
        man[name]["peak_offset_ms"] = measure_peak_ms(SFX_DIR / man[name]["file"])
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    return man


def import_user_sfx(name: str, src: str, max_len: float = 1.6, category: str = "") -> dict:
    """Nhập SFX của người dùng: chuyển WAV 48k mono, cắt độ dài tối đa + fade đuôi, đo đỉnh."""
    import subprocess
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    out = SFX_DIR / f"{name}.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-t", str(max_len), "-ac", "1", "-ar", str(SR),
                    "-af", f"afade=t=out:st={max(max_len - 0.25, 0)}:d=0.25", str(out)], check=True)
    man_path = SFX_DIR / "manifest.json"
    man = json.loads(man_path.read_text()) if man_path.exists() else {}
    man[name] = {"file": out.name, "category": category, "source": src, "license": "thư viện SFX của người dùng",
                 "peak_offset_ms": measure_peak_ms(out)}
    man_path.write_text(json.dumps(man, ensure_ascii=False, indent=1))
    return man[name]
