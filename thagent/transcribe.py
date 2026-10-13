"""ASR adapter: faster-whisper (CPU int8) với timestamp theo từ."""
from __future__ import annotations

import re

from .schema import TranscriptWord, Sentence

LOW_CONF = 0.55


def transcribe(wav_path: str, model_name: str = "large-v3", vocab: list[str] | None = None,
               progress=None) -> tuple[list[TranscriptWord], list[Sentence]]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    prompt = ", ".join(vocab) if vocab else None
    segs, info = model.transcribe(
        wav_path, language="vi", word_timestamps=True, vad_filter=True,
        beam_size=5, initial_prompt=prompt, condition_on_previous_text=False,
    )
    words: list[TranscriptWord] = []
    sentences: list[Sentence] = []
    for si, seg in enumerate(segs):
        ids = []
        for w in seg.words or []:
            t = w.word.strip()
            if not t:
                continue
            wid = f"w{len(words):04d}"
            words.append(TranscriptWord(
                id=wid, text=t, source_start=round(w.start, 3), source_end=round(w.end, 3),
                confidence=round(w.probability, 3),
                needs_review=w.probability < LOW_CONF or bool(re.search(r"\d", t)),
                sentence_id=si,
            ))
            ids.append(wid)
        if ids:
            sentences.append(Sentence(id=si, text=seg.text.strip(), source_start=words[-len(ids)].source_start,
                                      source_end=words[-1].source_end, word_ids=ids))
        if progress:
            progress(f"ASR {seg.end:.1f}s / {info.duration:.1f}s")
    return words, sentences


# ASR tiếng Việt hay nghe nhầm số đếm thành từ đồng âm ("chín máy lạnh" → "Chính máy lạnh").
# Từ đồng âm đứng NGAY TRƯỚC danh từ đếm được → đổi thành chữ số, đánh dấu needs_review.
NUM_HOMO = {"chính": "9", "chín": "9", "bản": "8", "tấm": "8", "sáo": "6", "báo": "5", "bóng": "4", "hài": "2",
            "mười": "10", "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5", "sáu": "6", "bảy": "7", "tám": "8"}
STRICT = {"chính", "bản", "tấm", "sáo", "báo", "bóng", "hài"}   # đồng âm thật → chỉ đổi trước danh từ đếm rõ ràng
COUNT_NOUN = {"máy", "phòng", "tầng", "căn", "lầu", "thang", "toilet", "wc", "nhà", "mặt", "chỗ", "xe", "người",
              "nhân", "phút", "giây", "km", "mét", "m", "m2", "triệu", "tỷ", "tỉ", "năm", "tháng", "ngày", "lô", "sổ",
              "chiếc", "cái", "bộ", "vị", "điều", "lý", "bước", "căn,"}
NOT_AFTER = {"năm"}   # "năm" vừa là số vừa là danh từ → không đổi "năm năm"


def fix_numbers(words: list[TranscriptWord]) -> list[str]:
    """Sửa tại chỗ; trả về danh sách mô tả các chỗ đã đổi (để báo người dùng)."""
    log = []
    for i, w in enumerate(words[:-1]):
        raw = re.sub(r"[^\w]", "", w.text.lower())
        nxt = re.sub(r"[^\w]", "", words[i + 1].text.lower())
        if raw not in STRICT or nxt not in COUNT_NOUN or (raw in NOT_AFTER and nxt in NOT_AFTER):
            continue
        if nxt in ("cái", "người", "mặt", "nhà", "điều", "lý") and raw != "chín":   # “chính cái”, “bản thân”… là lời thường
            continue
        tail = re.sub(r"^[\w]+", "", w.text)
        log.append(f"{w.source_start:.2f}s: “{w.text} {words[i + 1].text}” → “{NUM_HOMO[raw]} {words[i + 1].text}”")
        w.text, w.needs_review = NUM_HOMO[raw] + tail, True
    return log
