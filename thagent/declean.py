"""Giảm tiếng máy/nhiễu tần cao lẫn trong giọng (vd. máy cắt ở hiện trường).
Giữ nguyên dải giọng < split_hz; chỉ lọc nhiễu thích ứng (noisereduce, non-stationary) ở dải cao."""
from __future__ import annotations

import subprocess
import wave

import numpy as np


def reduce_hf_noise(src: str, dst: str, split_hz: float = 3500, prop: float = 0.9, sr: int = 48000):
    import noisereduce as nr
    from scipy.signal import butter, sosfiltfilt
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", src, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).astype(np.float64)
    lo = sosfiltfilt(butter(8, split_hz, "lowpass", fs=sr, output="sos"), x)
    hi = nr.reduce_noise(y=x - lo, sr=sr, stationary=False, prop_decrease=prop, time_constant_s=1.5,
                         freq_mask_smooth_hz=300, time_mask_smooth_ms=40, n_fft=2048)
    y = lo + hi
    y = y / max(1.0, np.abs(y).max() / 0.98)
    with wave.open(dst, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((y * 32767).astype(np.int16).tobytes())
