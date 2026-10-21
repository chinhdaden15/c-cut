"""Giọng đọc của C-Cut (dùng chung mọi skill, trước hết là Text to Video): giọng có sẵn (assets/voices) + giọng người dùng tự nhân bản.

Công cụ: VieNeu-TTS v3 Turbo (Apache-2.0, dùng thương mại được; giọng có sẵn đã được người nói đồng ý) chạy ONNX trên CPU —
không cần card đồ hoạ, chạy được cả Mac Intel. Đọc được tiếng Việt lẫn tiếng Anh trong cùng câu.
- Model tải 1 lần (~310 MB) về models/vieneu, GHIM đúng phiên bản (REV) → nhà phát triển đổi model cũng không làm app hỏng.
- Bước nhận chất giọng (x-vector) viết lại bằng numpy + kaldi-native-fbank (bản gốc cần torch, không có trong app).
- Nhân bản: file thu âm / video bất kỳ ≥ 5 giây giọng nói → chất giọng lấy từ tối đa 30s, mẫu đọc 4–8s đoạn liền mạch nhất;
  ghi voices/<id>/voice.json. Người dùng phải xác nhận có quyền dùng giọng đó (consent).

  python -m thagent.voice list
  python -m thagent.voice download
  python -m thagent.voice say <giọng> "<câu>" out.wav [tốc_độ]
  python -m thagent.voice clone <file thu âm> "<tên giọng>"        (dùng cho bộ kiểm — app hỏi xác nhận quyền trên giao diện)
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

import numpy as np

from .paths import ROOT

REPO, REV = "pnnbao-ump/VieNeu-TTS-v3-Turbo", "61b85e3d937fbbacb387714180e8182823512523"
CODEC, CODEC_REV = "OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano-ONNX", "ceff0d0749bfb3fa2d61149794ec6feef0d1e1ae"
MODEL_DIR = ROOT / "models" / "vieneu"
VOICES = ROOT / "voices"
SR = 48_000
SIZE_MB = 320

# giọng có sẵn của app = giọng chủ app tự chọn, đóng gói ở assets/voices/<id>.json
#   {"name", "gender", "speaker_emb", "codes", "temperature", "eq": [[Hz, dB], …]}  (eq: cân âm sắc sau khi đọc, cho giống giọng gốc)
BUILTIN = ROOT / "assets" / "voices"
DEFAULT = "nam_huong_dan"


def _builtin() -> dict:
    out = {}
    for f in sorted(BUILTIN.glob("*.json")):
        try:
            out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
    return out


PRESETS = _builtin()
SAMPLE_TEXT = ("Xin chào, đây là giọng đọc của C-Cut. Chỉ cần dán kịch bản, app sẽ tự dựng thành video hoàn chỉnh. "
               "Welcome to C-Cut, the easiest way to turn your script into a video.")

_LOCK = threading.Lock()
_ENGINE = None
_DL = {"busy": False, "error": None, "done_mb": 0}


class VoiceError(RuntimeError):
    """thông báo cho người dùng (tiếng Việt)."""


# ---------------- model ----------------
def _model_paths() -> tuple[Path, Path]:
    return MODEL_DIR / REV[:12], MODEL_DIR / ("codec_" + CODEC_REV[:12])


def ready() -> bool:
    m, c = _model_paths()
    return (m / "onnx_int8" / "vieneu_prefill.onnx").exists() and (m / "speaker_encoder.onnx").exists() \
        and (c / "moss_audio_tokenizer_encode.onnx").exists()


def download(progress=None) -> None:
    """tải model đúng phiên bản đã ghim (bỏ bản fp32 onnx_update cho nhẹ)."""
    from huggingface_hub import snapshot_download
    m, c = _model_paths()
    _DL.update(busy=True, error=None)
    try:
        snapshot_download(REPO, revision=REV, local_dir=str(m),
                          allow_patterns=["config.json", "speaker_encoder.onnx", "denoiser.onnx", "onnx_int8/*"])
        if progress:
            progress(0.8)
        snapshot_download(CODEC, revision=CODEC_REV, local_dir=str(c))
        if progress:
            progress(1.0)
    except Exception as e:
        _DL["error"] = f"không tải được bộ giọng đọc ({type(e).__name__}) — kiểm tra mạng rồi thử lại"
        raise VoiceError(_DL["error"]) from e
    finally:
        _DL["busy"] = False


def download_bg() -> dict:
    if not _DL["busy"] and not ready():
        threading.Thread(target=lambda: _safe(download), daemon=True).start()
        _DL["busy"] = True
    return status()


def _safe(fn):
    try:
        fn()
    except Exception:
        pass


def status() -> dict:
    return {"ready": ready(), "downloading": _DL["busy"], "error": _DL["error"], "size_mb": SIZE_MB}


class _NpSpeakerEncoder:
    """x-vector 192 chiều: fbank Kaldi 80 kênh @16 kHz (trừ trung bình) → speaker_encoder.onnx. Thay bản torch của VieNeu."""

    def __init__(self, onnx_path: str, max_seconds: float = 30.0):
        import onnxruntime as ort
        self.s = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        self.i, self.o = self.s.get_inputs()[0].name, self.s.get_outputs()[0].name
        self.max_seconds = max_seconds

    def embed(self, wav, sr: int) -> np.ndarray:
        import kaldi_native_fbank as knf
        import soxr
        w = np.asarray(wav, dtype=np.float32)
        if w.ndim == 2:
            w = w.mean(1) if w.shape[0] > w.shape[1] else w.mean(0)
        w = w[: int(sr * self.max_seconds)]
        if sr != 16000:
            w = soxr.resample(w, sr, 16000, quality="VHQ").astype(np.float32)
        o = knf.FbankOptions()
        o.frame_opts.dither = 0.0
        o.frame_opts.samp_freq = 16000
        o.mel_opts.num_bins = 80
        f = knf.OnlineFbank(o)
        f.accept_waveform(16000, w.tolist())
        f.input_finished()
        F = np.stack([f.get_frame(k) for k in range(f.num_frames_ready)]).astype(np.float32)
        F -= F.mean(0, keepdims=True)
        return self.s.run([self.o], {self.i: F[None]})[0][0].astype(np.float32)

    __call__ = embed


def engine():
    """VieNeu v3 Turbo (ONNX/CPU) dựng từ file đã ghim phiên bản — nạp 1 lần."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE
    if not ready():
        raise VoiceError("chưa tải bộ giọng đọc — bấm “Tải bộ giọng đọc” (khoảng 320 MB, chỉ tải 1 lần)")
    from vieneu.v3turbo import V3TurboVieNeuTTS
    from vieneu._v3_turbo_engine.onnx_runtime_lite import OnnxV3LiteEngine
    m, c = _model_paths()
    eng = OnnxV3LiteEngine(checkpoint_path=str(m), onnx_dir=str(m / "onnx_int8"), codec_dir=str(c))
    eng.speaker_encoder = _NpSpeakerEncoder(str(m / "speaker_encoder.onnx"))
    from vieneu.base import BaseVieneuTTS
    tts = V3TurboVieNeuTTS.__new__(V3TurboVieNeuTTS)          # bỏ qua __init__ riêng (tự tải model mới nhất từ mạng)
    BaseVieneuTTS.__init__(tts)                               # phần chung: chuẩn hoá chữ, dấu nước…
    for k, v in {"sample_rate": SR, "engine": eng, "backend": "onnx", "default_style": "tu_nhien"}.items():
        setattr(tts, k, v)
    tts._load_v3_voices()
    _ENGINE = tts
    return tts


# ---------------- giọng ----------------
def _slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:40] or "giong"


def voices() -> list[dict]:
    out = [{"id": k, "name": d["name"], "gender": d.get("gender", ""), "kind": "preset"} for k, d in PRESETS.items()]
    for f in sorted(VOICES.glob("*/voice.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": f.parent.name, "name": d["name"], "kind": "clone", "created": d.get("created")})
        except Exception:
            continue
    return out


def _voice_data(voice_id: str) -> dict:
    if voice_id in PRESETS:
        return PRESETS[voice_id]
    f = VOICES / voice_id / "voice.json"
    if not re.fullmatch(r"[a-z0-9_]+", voice_id or "") or not f.exists():
        raise VoiceError(f"không có giọng “{voice_id}”")
    return json.loads(f.read_text(encoding="utf-8"))


def _eq(wav: np.ndarray, pts) -> np.ndarray:
    """cân âm sắc theo đường cong [[Hz, dB], …] (giữ nguyên độ to)."""
    from scipy.signal import firwin2, fftconvolve
    fx, gx = [p[0] for p in pts], [p[1] for p in pts]
    F = np.linspace(0, SR / 2, 2049)
    h = firwin2(2049, F / (SR / 2), 10 ** (np.interp(F, fx, gx, right=gx[-1]) / 20))
    y = fftconvolve(wav, h, mode="same")
    return (y * np.sqrt((wav ** 2).mean() / ((y ** 2).mean() + 1e-12))).astype(np.float32)


def _ffmpeg() -> str:
    return "ffmpeg"                                      # app đã đưa ffmpeg đi kèm vào PATH (như các mô-đun khác)


def say(text: str, voice_id: str, out: Path | str, speed: float = 1.0) -> Path:
    """đọc `text` (Việt / Anh / lẫn) bằng giọng `voice_id` → wav 48 kHz. speed 0.8–1.3 (giữ cao độ)."""
    import soundfile as sf
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        raise VoiceError("chưa có chữ để đọc")
    d = _voice_data(voice_id)
    ref = {"speaker_emb": np.asarray(d["speaker_emb"], dtype=np.float32), "codes": np.asarray(d["codes"], dtype=np.int64)}
    with _LOCK:
        tts = engine()
        wav = np.asarray(tts.infer(text, voice=ref, temperature=float(d.get("temperature", 0.7))), dtype=np.float32)
    if d.get("eq"):
        wav = _eq(wav, d["eq"])
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), wav, SR)
    speed = max(0.8, min(1.3, float(speed or 1.0)))
    if abs(speed - 1.0) > 0.01:
        tmp = out.with_suffix(".tmp.wav")
        subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(out), "-af", f"atempo={speed:.3f}", str(tmp)], check=True)
        tmp.replace(out)
    return out


def sample(voice_id: str) -> Path:
    """câu nghe thử (đệm sẵn)."""
    f = VOICES / "_cache" / f"sample_{voice_id}.wav"
    if not f.exists():
        say(SAMPLE_TEXT, voice_id, f)
    return f


# ---------------- nhân bản ----------------
def _load_audio(src: Path, max_s: float = 90.0) -> np.ndarray:
    """mọi file âm thanh / video → mono 48 kHz float32 (tối đa 90s)."""
    r = subprocess.run([_ffmpeg(), "-v", "error", "-i", str(src), "-t", str(max_s), "-vn", "-ac", "1", "-ar", str(SR),
                        "-f", "f32le", "-"], capture_output=True)
    if r.returncode or not r.stdout:
        raise VoiceError("không đọc được file thu âm — dùng file mp3, m4a, wav hoặc video có tiếng")
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def _speech_mask(w: np.ndarray, hop: int) -> tuple[np.ndarray, float]:
    """khung 20ms có tiếng nói (theo năng lượng so với nền) + SNR ước lượng (dB)."""
    n = len(w) // hop
    rms = np.sqrt((w[: n * hop].reshape(n, hop) ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms)
    floor, peak = np.percentile(db, 10), np.percentile(db, 95)
    return db > max(floor + 12, peak - 35), float(peak - floor)


def _best_window(mask: np.ndarray, hop_s: float, lo: float = 4.0, hi: float = 8.0) -> tuple[int, int]:
    """đoạn 4–8s nhiều tiếng nói nhất, bắt đầu/kết thúc ở khoảng nghỉ (không cắt giữa từ)."""
    n = len(mask)
    quiet = [i for i in range(n) if not mask[i]] or [0, n - 1]
    best, bi = -1.0, (0, min(n, int(hi / hop_s)))
    qs = quiet[:: max(1, len(quiet) // 400)]
    for a in qs:
        for b in qs:
            d = (b - a) * hop_s
            if lo <= d <= hi:
                sc = mask[a:b].mean() + d / hi * 0.15
                if sc > best:
                    best, bi = sc, (a, b)
    return bi


def clone(src: Path | str, name: str, consent: bool) -> dict:
    """file thu âm / video có giọng người nói → giọng mới trong thư viện. Cần xác nhận có quyền dùng giọng."""
    import soundfile as sf
    if not consent:
        raise VoiceError("cần xác nhận đây là giọng của bạn hoặc bạn được người đó cho phép dùng")
    name = re.sub(r"\s+", " ", str(name or "")).strip()[:40]
    if not name:
        raise VoiceError("đặt tên cho giọng (vd: Giọng của Chính)")
    w = _load_audio(Path(src))
    hop = int(SR * 0.02)
    mask, snr = _speech_mask(w, hop)
    if mask.sum() * 0.02 < 5.0:
        raise VoiceError("file cần ít nhất 5 giây giọng nói rõ (thu nơi yên tĩnh, nói tự nhiên 5–30 giây)")
    a, b = _best_window(mask, 0.02)
    ref = w[a * hop: b * hop]
    speech = w[np.repeat(mask, hop)[: len(w)]] if len(w) >= len(mask) * hop else w
    with _LOCK:
        tts = engine()
        denoise = snr < 35                                   # thu bằng micro thường có tiếng nền → lọc; file sạch thì giữ nguyên chất giọng
        vid = _slug(name)
        k, base = 1, vid
        while (VOICES / vid).exists():
            k += 1
            vid = f"{base}_{k}"
        d = VOICES / vid
        d.mkdir(parents=True)
        sf.write(str(d / "ref.wav"), ref, SR)
        _, codes = tts.engine.prepare_reference(str(d / "ref.wav"), denoise=denoise, use_ref_codes=True)
        emb = tts.engine.speaker_encoder.embed(speech[: SR * 30], SR)
    meta = {"name": name, "created": int(time.time()), "consent": True, "source": Path(src).name, "denoised": denoise,
            "ref_seconds": round(len(ref) / SR, 2), "speaker_emb": [round(float(x), 6) for x in emb],
            "codes": np.asarray(codes, dtype=int).tolist()}
    (d / "voice.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return {"id": vid, "name": name, "kind": "clone", "ref_seconds": meta["ref_seconds"], "denoised": denoise}


def remove(voice_id: str) -> None:
    if voice_id in PRESETS:
        raise VoiceError("không xoá được giọng có sẵn")
    d = VOICES / voice_id
    if re.fullmatch(r"[a-z0-9_]+", voice_id or "") and (d / "voice.json").exists():
        shutil.rmtree(d)
    (VOICES / "_cache" / f"sample_{voice_id}.wav").unlink(missing_ok=True)


def main():
    a = sys.argv[1:]
    if not a or a[0] == "list":
        print(json.dumps({"status": status(), "voices": voices()}, ensure_ascii=False, indent=1))
    elif a[0] == "download":
        download(lambda p: print(f"{p:.0%}", flush=True))
        print("xong:", ready())
    elif a[0] == "say":
        print(say(a[2], a[1], a[3], float(a[4]) if len(a) > 4 else 1.0))
    elif a[0] == "clone":
        print(json.dumps(clone(a[1], a[2], consent=True), ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
