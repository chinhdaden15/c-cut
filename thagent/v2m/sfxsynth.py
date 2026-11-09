"""Bộ SFX hiện đại cho video ngắn (tự tổng hợp, không bản quyền) + âm số/glitch chọn từ thư viện người dùng.

    .venv/bin/python -m thagent.v2m.sfxsynth      → ghi assets/sfx_v2m/{boom,riser,swoosh,blip,glitch,data}_NN.wav + bổ sung manifest

Vai trò:
  boom    sub drop + lực đập (hook, chữ lớn, thẻ kết)          riser   tiếng dâng lên ngay TRƯỚC cú đập (đỉnh ở cuối)
  swoosh  gió lướt nhanh, sạch (chuyển cảnh, khối lớn vào)       blip    tiếng số ngắn, sáng (thẻ, mục, nhãn bật ra)
  glitch  nhiễu số (cảnh công nghệ, đổi cảnh mạnh)               data    xử lý dữ liệu (bản đồ, mạch, tiến trình)
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

from .sfxkit import KIT_DIR, SRC_ROOT, _peak_ms

SR = 48000
RNG = np.random.default_rng(7)


def _bp_sweep(x, f0, f1, q=1.2, curve=None):
    """lọc dải thông có tâm quét f0→f1 (theo khối 10 ms, nối mượt)."""
    from scipy.signal import butter, sosfilt
    n = len(x)
    blk = int(SR * 0.01)
    out = np.zeros(n)
    nb = max(1, n // blk)
    for i in range(nb + 1):
        a, b = i * blk, min(n, (i + 1) * blk + blk)        # chồng 1 khối, cửa sổ tam giác
        if a >= n:
            break
        k = i / max(1, nb)
        k = curve(k) if curve else k
        fc = f0 * (f1 / f0) ** k
        lo, hi = max(30, fc / (1 + 1 / q)), min(SR / 2 - 100, fc * (1 + 1 / q))
        sos = butter(2, [lo, hi], "band", fs=SR, output="sos")
        seg = sosfilt(sos, x[max(0, a - blk * 4):b])[-(b - a):]
        w = np.bartlett(len(seg)) if len(seg) > 2 else np.ones(len(seg))
        out[a:b] += seg * w
    return out


def _env(n, attack, release_pow=2.0, peak=None):
    t = np.linspace(0, 1, n)
    p = peak if peak is not None else attack
    e = np.where(t < p, (t / max(p, 1e-6)) ** 1.5, ((1 - t) / max(1 - p, 1e-6)) ** release_pow)
    return e


def _norm(x, db=-3.0):
    return x / (np.abs(x).max() + 1e-9) * 10 ** (db / 20)


def boom(dur=1.3, f0=95, f1=36, punch=1.0):
    n = int(SR * dur)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    sub = np.sin(ph) * np.exp(-t * 2.6)
    click = RNG.standard_normal(n) * np.exp(-t * 90) * 0.6 * punch       # lực đập đầu
    from scipy.signal import butter, sosfilt
    click = sosfilt(butter(2, 2500, "low", fs=SR, output="sos"), click)
    body = _bp_sweep(RNG.standard_normal(n), 900, 120, 0.8) * np.exp(-t * 7) * 0.5
    x = np.tanh((sub * 1.6 + click + body) * 1.4)
    x[: int(SR * 0.002)] *= np.linspace(0, 1, int(SR * 0.002))
    return _norm(x * np.minimum(1, (dur - t) / 0.25))


def riser(dur=1.4):
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = _bp_sweep(RNG.standard_normal(n), 250, 7000, 1.6, curve=lambda k: k ** 1.6)
    tone = np.sin(2 * np.pi * np.cumsum(180 * (4.5 ** (t / dur) ** 1.8)) / SR) * 0.25
    e = (t / dur) ** 2.4
    x = (noise * 0.9 + tone) * e
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return _norm(x)


def swoosh(dur=0.55, f0=500, f1=3800, peak=0.55):
    n = int(SR * dur)
    x = _bp_sweep(RNG.standard_normal(n), f0, f1, 1.4, curve=lambda k: np.sin(k * np.pi / 2))
    x2 = _bp_sweep(RNG.standard_normal(n), f0 * 0.5, f1 * 0.4, 1.0) * 0.6
    return _norm((x + x2) * _env(n, 0, 2.2, peak))


def blip(f=1700, f2=2550, dur=0.16):
    n = int(SR * dur)
    t = np.arange(n) / SR
    a = np.sin(2 * np.pi * f * t) * np.exp(-t * 38)
    b = np.sin(2 * np.pi * f2 * t) * np.exp(-np.maximum(t - 0.045, 0) * 40) * (t > 0.045)
    x = a + 0.8 * b + 0.15 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 60)
    x[: int(SR * 0.002)] *= np.linspace(0, 1, int(SR * 0.002))
    return _norm(x, -4)


def glitch(dur=0.42, seed=1):
    r = np.random.default_rng(seed)
    n = int(SR * dur)
    x = np.zeros(n)
    i = 0
    while i < n:
        L = int(SR * r.uniform(0.012, 0.05))
        kind = r.integers(0, 3)
        t = np.arange(min(L, n - i)) / SR
        if kind == 0:
            seg = np.sign(np.sin(2 * np.pi * r.uniform(200, 2400) * t))
        elif kind == 1:
            seg = r.standard_normal(len(t))
        else:
            seg = np.sin(2 * np.pi * r.uniform(60, 140) * t)
        x[i:i + len(t)] = seg * r.uniform(0.3, 1.0) * (r.random() > 0.2)
        i += L
    x = np.round(x * 6) / 6                                     # bitcrush
    from scipy.signal import butter, sosfilt
    x = sosfilt(butter(4, 5000, "low", fs=SR, output="sos"), x)   # bớt chói
    return _norm(x * _env(n, 0.02, 1.2))


def _write(name, x):
    out = KIT_DIR / name
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
    return {"file": name, "source": "C-Cut tự tổng hợp (sfxsynth)", "peak_ms": _peak_ms(out), "dur_s": round(len(x) / SR, 3)}


def _lib(name, rel, maxlen):
    src = SRC_ROOT / rel
    if not src.exists():
        return None
    out = KIT_DIR / name
    af = (f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.005,atrim=0:{maxlen},"
          f"afade=t=out:st={max(maxlen - 0.2, 0):.2f}:d=0.2")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", str(SR), "-af", af, str(out)], check=True)
    with wave.open(str(out)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
    it = _write(name, _norm(x))
    it["source"] = f"Chính Dùng/SFX/{rel}"
    return it


MODERN = {
    "boom":   ("hook, chữ lớn, thẻ kết — sub drop có lực", -12),
    "riser":  ("dâng lên trước cú đập (đỉnh ở cuối âm)", -20),
    "swoosh": ("chuyển cảnh, khối lớn vào — gió lướt sạch", -18),
    "blip":   ("thẻ / mục / nhãn bật ra — tiếng số ngắn", -22),
    "glitch": ("cảnh công nghệ, đổi cảnh mạnh — nhiễu số", -21),
    "data":   ("bản đồ, mạch, tiến trình — xử lý dữ liệu", -22),
}


def build(log=print) -> dict:
    KIT_DIR.mkdir(parents=True, exist_ok=True)
    man = json.loads((KIT_DIR / "manifest.json").read_text(encoding="utf-8")) if (KIT_DIR / "manifest.json").exists() else {}
    items = {
        "boom": [_write("boom_00.wav", boom()), _write("boom_01.wav", boom(1.1, 110, 42, 1.3)), _write("boom_02.wav", boom(1.5, 80, 32, 0.8))],
        "riser": [_write("riser_00.wav", riser(1.2)), _write("riser_01.wav", riser(0.8))],
        "swoosh": [_write("swoosh_00.wav", swoosh()), _write("swoosh_01.wav", swoosh(0.45, 700, 5200, 0.5)),
                   _write("swoosh_02.wav", swoosh(0.6, 380, 2600, 0.6)), _write("swoosh_03.wav", swoosh(0.4, 900, 6000, 0.45))],
        "blip": [_write("blip_00.wav", blip()), _write("blip_01.wav", blip(1400, 2100)), _write("blip_02.wav", blip(2000, 3000, 0.12)),
                 _write("blip_03.wav", blip(1200, 1800))],
        "glitch": [_write("glitch_00.wav", glitch(0.4, 1)), _write("glitch_01.wav", glitch(0.3, 5))],
        "data": [],
    }
    for nm, rel, ml in (("glitch_02.wav", "User Interface/Glitch Hit Noise Burst and Metallic Tone.mp3", 0.8),
                        ("glitch_03.wav", "User Interface/Hitech GUI, Scifi, Interact, Digital, Glitch 05.mp3", 0.8),
                        ("data_01.wav", "User Interface/Computer, Futuristic, Data Processing, Loading 06.mp3", 1.4),
                        ("data_02.wav", "User Interface/Computer, Futuristic, Data Processing, Loading 13.mp3", 1.4),
                        ("blip_04.wav", "User Interface/Sci Fi Games, UI Menu, Very Short, Open 10.mp3", 0.4)):
        it = _lib(nm, rel, ml)
        if it:
            items[nm.split("_")[0]].append(it)
    for role, (desc, gain) in MODERN.items():
        man[role] = {"desc": desc, "gain_db": gain, "items": items[role], "license": "tự tổng hợp + thư viện SFX của người dùng"}
        log(f"{role:<8} {len(items[role])} âm · {desc}")
    (KIT_DIR / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


if __name__ == "__main__":
    build()
