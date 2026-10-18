"""Review Editor — dò NÓI HỎNG RỒI NÓI LẠI mà máy chép lời bỏ sót (vd “Đến… Đến bây giờ mà…”: lần nói thứ hai bị gộp vào từ kế).

Cách làm: mẩu lời ngắn (≤ 3 từ, ≤ 1,2s) đứng trước một chỗ ngừng ≥ 0,45s → nghe lại (faster-whisper) đoạn ngay sau chỗ ngừng;
câu sau mở đầu bằng đúng mẩu đó → mẩu trước là câu hỏng: cắt từ đầu mẩu tới ngay trước lần nói lại (giữ đệm ~0,1s theo năng lượng tiếng),
và vá lời của đoạn nghe lại vào danh sách từ (phụ đề có đủ chữ, không lặp chữ đã cắt).
Kết quả lưu đệm review/restarts_<ID>.json (theo chữ ký file) — Cắt sạch (`clean`) tự áp; edit.media() tự vá lời.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unicodedata
from pathlib import Path

GAP = 0.45
FRAG_MAX_W, FRAG_MAX_S = 3, 1.2
_MODEL = {}


def _n(s):
    return unicodedata.normalize("NFC", s.lower()).strip(".,!?;:…“”\"()")


def _asr(path: str, a: float, b: float) -> list[dict]:
    if "m" not in _MODEL:
        from faster_whisper import WhisperModel
        _MODEL["m"] = WhisperModel("large-v3", device="cpu", compute_type="int8")
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "w.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", path, "-vn", "-ar", "16000", "-ac", "1",
                        str(wav)], check=True)
        segs, _ = _MODEL["m"].transcribe(str(wav), language="vi", word_timestamps=True, vad_filter=False, beam_size=5,
                                         condition_on_previous_text=False)
        return [{"text": w.word.strip(), "start": round(a + w.start, 3), "end": round(a + w.end, 3), "conf": round(w.probability, 3)}
                for s in segs for w in (s.words or []) if w.word.strip()]


def _onset(db, fl, t: float, until: float) -> float:
    """đầu khối tiếng MẠNH NHẤT trong [t, until] (tiếng thở/chép môi nhỏ trước đó không tính)."""
    a, e = int(t * 100), min(int(until * 100), len(db) - 1)
    if e <= a:
        return t
    k = a + int(db[a:e].argmax())
    while k > a and db[k - 1] > fl + 10:
        k -= 1
    return k / 100


def detect(pdir, m: dict, spans=None, log=print) -> list[dict]:
    """→ [{cut: [a, b], frag, words: [...vá...], replace: [a, b]}] (lưu đệm theo chữ ký file)."""
    cache = Path(pdir) / "review" / f"restarts_{m['id']}.json"
    sig = m.get("signature") or m.get("sig") or f"{m['path']}:{m.get('duration')}"
    if cache.exists():
        c = json.loads(cache.read_text(encoding="utf-8"))
        if c.get("sig") == sig:
            return c["items"]
    from .audiocut import _env
    ws = [w for w in m.get("words", [])]
    db, fl = _env(m["path"])
    items, i = [], 0
    while i < len(ws):
        # mẩu: các từ liền nhau từ sau một chỗ ngừng (hoặc đầu file) tới chỗ ngừng ≥ GAP kế tiếp
        j = i
        while j + 1 < len(ws) and ws[j + 1]["start"] - ws[j]["end"] < GAP:
            j += 1
        frag = ws[i:j + 1]
        used = spans is None or any(x - 0.3 <= frag[0]["start"] < y for x, y in spans)
        if used and j + 1 < len(ws) and len(frag) <= FRAG_MAX_W and frag[-1]["end"] - frag[0]["start"] <= FRAG_MAX_S:
            nxt = ws[j + 1]
            a = max(frag[-1]["end"] + 0.05, nxt["start"] - 0.6)
            b = min(nxt["start"] + 1.4, float(m["duration"]))
            heard = [w for w in _asr(m["path"], a, b) if w["end"] <= b - 0.15]   # bỏ từ bị cắt cụt ở mép cửa sổ
            ft = [_n(w["text"]) for w in frag]
            ht = [_n(w["text"]) for w in heard[:len(ft)]]
            if heard and ht == ft:
                on = _onset(db, fl, max(heard[0]["start"], a), heard[0]["end"] + 0.3)
                heard[0]["start"] = round(max(on, heard[0]["start"]), 3)
                cut = [round(max(frag[0]["start"] - 0.02, 0.0), 3), round(max(on - 0.1, frag[-1]["end"] + 0.05), 3)]
                items.append({"cut": cut, "frag": " ".join(w["text"] for w in frag), "words": heard, "replace": [a, b],
                              "reason": f"nói hỏng rồi nói lại “{' '.join(w['text'] for w in frag)}”"})
                log(f"  {m['id']} {cut[0]:.2f}–{cut[1]:.2f}s: nói lại “{items[-1]['frag']}”")
        i = j + 1
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"sig": sig, "items": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def load(pdir, fid: str) -> list[dict]:
    p = Path(pdir) / "review" / f"restarts_{fid}.json"
    return json.loads(p.read_text(encoding="utf-8"))["items"] if p.exists() else []


def patch_words(words: list[dict], items: list[dict]) -> list[dict]:
    """bỏ từ của mẩu đã cắt + thay lời trong đoạn nghe lại bằng lời nghe lại (đủ chữ)."""
    for it in items:
        a, b = it["replace"]
        hb = it["words"][-1]["end"] if it["words"] else b
        c0, c1 = it["cut"]
        keep = [w for w in words if not (w["start"] >= c0 - 0.01 and w["end"] <= c1 + 0.05)
                and not (w["start"] < hb and w["end"] > a and w["start"] >= c1 - 0.05)]
        words = sorted(keep + [dict(w, restart=True) for w in it["words"]], key=lambda w: w["start"])
    return words
