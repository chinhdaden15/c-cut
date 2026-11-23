"""Giọng đọc TIẾNG ANH của C-Cut.

1. Giọng bản xứ (Kokoro-82M, Apache-2.0, ONNX/CPU): video cho khán giả nước ngoài — giọng en_* trong assets/voices.
2. Giọng Việt nói tiếng Anh chuẩn: câu TOÀN tiếng Anh → giọng bản xứ cùng giới đọc trước (phát âm + nhịp chuẩn)
   → chuyển chất giọng sang giọng Việt đang chọn (Chatterbox-Turbo speech encoder + decoder, MIT, ONNX q8).
   Câu tiếng Việt (kể cả có xen vài từ Anh) KHÔNG đi qua đây — vẫn do VieNeu đọc như cũ.

Chữ → âm: từ điển misaki (Apache-2.0, assets/en_lexicon) + đọc số + đánh vần từ lạ. KHÔNG dùng espeak-ng (GPL).
Model tải khi cần lần đầu, GHIM phiên bản: Kokoro ~350 MB, bộ chuyển giọng ~680 MB.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import threading
import unicodedata
import urllib.request
from math import gcd
from pathlib import Path

import numpy as np

from .paths import ROOT

LEX_DIR = ROOT / "assets" / "en_lexicon"
KDIR = ROOT / "models" / "kokoro"
CDIR = ROOT / "models" / "chatterbox_vc"
KOKORO = {"kokoro-v1.0.onnx": ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
                               "7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5"),
          "voices-v1.0.bin": ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
                              "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d")}
CB_REPO, CB_REV = "ResembleAI/chatterbox-turbo-ONNX", "d21799bd0354adb85e348b8a0442a8405110a2cf"
CB_FILES = [f"onnx/{n}_quantized.onnx{s}" for n in ("speech_encoder", "conditional_decoder") for s in ("", "_data")]
KSR, CSR = 24000, 24000
BASE = {"nam": "am_michael", "nữ": "af_heart"}      # giọng bản xứ làm "khuôn phát âm" khi giọng Việt đọc tiếng Anh

_LOCK = threading.Lock()
_K = {}
_C = {}
_LEX = None


class EnVoiceError(RuntimeError):
    pass


# ---------------- nhận câu tiếng Anh ----------------
_VI = re.compile(r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.I)
_VI_PLAIN = {"va", "la", "co", "cho", "nha", "anh", "em", "ban", "minh", "nay", "khi", "thi", "ma", "nhung", "voi", "cua", "mot", "hai",
             "ba", "bon", "nam", "sau", "bay", "tam", "chin", "muoi", "tram", "nghin", "trieu", "ty", "dong", "theo", "neu", "con"}


def is_english(text: str) -> bool:
    """câu TOÀN tiếng Anh (≥3 từ, không chữ có dấu tiếng Việt, phần lớn từ có trong từ điển tiếng Anh)."""
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", text or "")
    if len(words) < 3 or _VI.search(text):
        return False
    lex = _lex()
    known = sum(1 for w in words if _look(w, lex) is not None and w.lower() not in _VI_PLAIN)
    return known / len(words) >= 0.7


# ---------------- chữ → âm (misaki) ----------------
def _lex() -> dict:
    global _LEX
    if _LEX is None:
        d = {}
        for f in ("us_silver", "us_gold"):               # gold ghi đè silver
            d.update(json.loads(gzip.decompress((LEX_DIR / f"{f}.json.gz").read_bytes())))
        _LEX = d
    return _LEX


def _pick(v):
    return v.get("DEFAULT") or next(iter(v.values())) if isinstance(v, dict) else v


def _look(w: str, lex: dict) -> str | None:
    for k in (w, w.lower(), w.capitalize(), w.upper()):
        if k in lex and lex[k]:
            return _pick(lex[k])
    lw = w.lower()
    for suf, add in (("'s", "z"), ("’s", "z"), ("s", "z"), ("es", "ᵻz"), ("ed", "d"), ("ing", "ɪŋ")):
        if lw.endswith(suf) and len(lw) > len(suf) + 2:
            b = _look(lw[:-len(suf)], lex) if lw[:-len(suf)] != lw else None
            if b:
                return b + add
    return None


_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _num_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        return _ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + _num_words(n % 100))
    for v, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= v:
            return _num_words(n // v) + " " + name + ("" if n % v == 0 else " " + _num_words(n % v))
    return str(n)


def _expand(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("’", "'")
    text = re.sub(r"(\d+)%", lambda m: m.group(1) + " percent", text)
    text = re.sub(r"\$(\d[\d,]*)", lambda m: m.group(1) + " dollars", text)
    text = re.sub(r"(\d+)\.(\d+)", lambda m: _num_words(int(m.group(1))) + " point " + " ".join(_ONES[int(c)] for c in m.group(2)), text)
    text = re.sub(r"\d[\d,]*", lambda m: _num_words(int(m.group(0).replace(",", ""))), text)
    text = text.replace("&", " and ").replace("+", " plus ")
    return text


def phonemes(text: str) -> str:
    lex = _lex()
    vocab = _vocab()
    out = []
    for tok in re.findall(r"[A-Za-z][A-Za-z'-]*[A-Za-z]|[A-Za-z]|[-–—]|[.,!?;:…]", _expand(text)):
        if tok in ".,!?;:…":
            out.append(tok)
            continue
        if tok in "-–—":
            out.append("—")
            continue
        parts = [tok]
        if "-" in tok:
            parts = tok.split("-")
        for p in parts:
            ph = _look(p, lex)
            if ph is None and p.isupper() or ph is None and len(p) <= 3:     # viết tắt / từ lạ ngắn → đánh vần
                ph = " ".join(_pick(lex.get(c.upper()) or lex.get(c.lower()) or "") for c in p if c.isalpha())
            if ph is None:                                                # từ lạ dài: ghép từ các mảnh có trong từ điển
                ph, i = "", 0
                lw = p.lower()
                while i < len(lw):
                    for j in range(len(lw), i, -1):
                        q = _look(lw[i:j], lex) if j - i >= 2 else None
                        if q:
                            ph += q.replace("ˈ", "").replace("ˌ", "") if ph else q
                            i = j
                            break
                    else:
                        ph += _pick(lex.get(lw[i].upper(), ""))
                        i += 1
            out.append(ph)
    s = " ".join(out)
    s = re.sub(r" ([.,!?;:…])", r"\1", s)
    return "".join(c for c in s if c in vocab or c == " ")


# ---------------- tải model ----------------
def _get(url: str, dst: Path, sha: str | None = None):
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".part")
    h = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "C-Cut"}), timeout=60) as r, open(tmp, "wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            h.update(b)
    if sha and h.hexdigest() != sha:
        tmp.unlink(missing_ok=True)
        raise EnVoiceError(f"tải {dst.name} bị lỗi (sai mã kiểm tra) — thử lại")
    tmp.replace(dst)


def kokoro_ready() -> bool:
    return all((KDIR / n).exists() for n in KOKORO)


def vc_ready() -> bool:
    return all((CDIR / f).exists() for f in CB_FILES)


def download(vc: bool = True):
    for n, (u, sha) in KOKORO.items():
        if not (KDIR / n).exists():
            _get(u, KDIR / n, sha)
    if vc:
        for f in CB_FILES:
            if not (CDIR / f).exists():
                _get(f"https://huggingface.co/{CB_REPO}/resolve/{CB_REV}/{f}", CDIR / f)


# ---------------- Kokoro ----------------
def _vocab() -> dict:
    if "vocab" not in _K:
        _K["vocab"] = json.loads((LEX_DIR / "kokoro_vocab.json").read_text(encoding="utf-8"))["vocab"]
    return _K["vocab"]


def _kokoro():
    if "sess" not in _K:
        if not kokoro_ready():
            download(vc=False)
        import onnxruntime as ort
        _K["sess"] = ort.InferenceSession(str(KDIR / "kokoro-v1.0.onnx"), providers=["CPUExecutionProvider"])
        _K["voices"] = np.load(str(KDIR / "voices-v1.0.bin"))
        _K["in"] = {i.name: i for i in _K["sess"].get_inputs()}
    return _K


def _chunks(ph: str, limit: int = 400) -> list[str]:
    if len(ph) <= limit:
        return [ph]
    out, cur = [], ""
    for seg in re.split(r"(?<=[.!?;:,—])\s+", ph):
        if cur and len(cur) + len(seg) + 1 > limit:
            out.append(cur)
            cur = seg
        else:
            cur = (cur + " " + seg).strip()
    return out + ([cur] if cur else [])


def kokoro(text: str, voice: str, speed: float = 1.0) -> np.ndarray:
    """→ wav float32 24 kHz."""
    K = _kokoro()
    vocab = _vocab()
    style_all = K["voices"][voice]
    wavs = []
    for ph in _chunks(phonemes(text)):
        ids = [vocab[c] for c in ph if c in vocab][:510]
        if not ids:
            continue
        st = style_all[len(ids) - 1]
        name = "input_ids" if "input_ids" in K["in"] else "tokens"
        sp_t = K["in"]["speed"].type
        feed = {name: np.array([[0, *ids, 0]], dtype=np.int64), "style": np.asarray(st, dtype=np.float32),
                "speed": np.array([speed], dtype=np.int32 if "int" in sp_t else np.float32)}
        wavs.append(np.asarray(K["sess"].run(None, feed)[0], dtype=np.float32).reshape(-1))
        wavs.append(np.zeros(int(0.12 * KSR), np.float32))
    if not wavs:
        raise EnVoiceError("câu tiếng Anh không đọc được")
    return np.concatenate(wavs[:-1] or wavs)


# ---------------- chuyển giọng (Chatterbox) ----------------
def _cb():
    if "enc" not in _C:
        if not vc_ready():
            download()
        import onnxruntime as ort
        _C["enc"] = ort.InferenceSession(str(CDIR / CB_FILES[0]), providers=["CPUExecutionProvider"])
        _C["dec"] = ort.InferenceSession(str(CDIR / CB_FILES[2]), providers=["CPUExecutionProvider"])
    return _C


def resample(a: np.ndarray, sr: int, to: int) -> np.ndarray:
    if sr == to:
        return a.astype(np.float32)
    from scipy.signal import resample_poly
    g = gcd(sr, to)
    return resample_poly(a, to // g, sr // g).astype(np.float32)


def convert(src24: np.ndarray, ref: np.ndarray, ref_sr: int) -> np.ndarray:
    """giữ phát âm / nhịp của src (24 kHz), đổi chất giọng thành giọng của ref → 24 kHz."""
    C = _cb()
    _, src_tok, _, _ = C["enc"].run(None, {"audio_values": src24[None, :].astype(np.float32)})
    _, ref_tok, spk, feat = C["enc"].run(None, {"audio_values": resample(ref, ref_sr, CSR)[None, :]})
    st = np.concatenate([ref_tok, src_tok, np.full((1, 3), 4299, np.int64)], 1)
    return np.asarray(C["dec"].run(None, dict(speech_tokens=st, speaker_embeddings=spk, speaker_features=feat))[0], np.float32).reshape(-1)


def say_vi_voice(text: str, gender: str, ref: np.ndarray, ref_sr: int) -> np.ndarray:
    """giọng Việt đọc câu tiếng Anh như người bản xứ → 24 kHz."""
    with _LOCK:
        base = kokoro(text, BASE.get(gender, "am_michael"))
        return convert(base, ref, ref_sr)
