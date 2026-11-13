"""Text to Video — phần 1: kịch bản → giọng đọc có mốc thời gian từng từ (đầu vào cho bước dựng hình).

Đầu vào:
- file kịch bản .txt / .md / .docx / .srt (1 video hoặc NHIỀU video trong 1 file — split() tách theo tiêu đề);
- hoặc yêu cầu sơ sài + số giây → Claude viết kịch bản trước (khoảng 3,2 từ/giây ở tốc độ 1.1), rồi chạy prepare.
prepare(): chia câu → đọc từng câu bằng thagent.voice → ghép (nghỉ giữa câu/đoạn) → tốc độ mặc định 1.1 →
chép lời lại để lấy mốc từng từ và KIỂM câu đọc sai (đọc lại tối đa 2 lần) → ghi vào thư mục dự án:
  voice.wav          giọng hoàn chỉnh (48 kHz)
  transcript.json    cùng định dạng Voice to Motion (words/sentences, chữ lấy theo KỊCH BẢN, không theo bản chép lời)
  script.json        {"voice", "speed", "sentences": [{"i", "text", "para", "start", "end", "match"}]}

  python -m thagent.t2v split <file kịch bản>                       danh sách video trong file
  python -m thagent.t2v prepare <thư-mục-dự-án> <file|"chữ"> <giọng> [tốc_độ=1.1]
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import numpy as np

SPEED = 1.1                   # mặc định cho mọi video: dễ nghe, không bị chán
GAP_SENT, GAP_PARA = 0.22, 0.45
WPS = 3.2                     # từ/giây ở tốc độ 1.1 — để Claude viết kịch bản đúng độ dài yêu cầu


class T2VError(RuntimeError):
    pass


# ---------------- đọc + tách kịch bản ----------------
def read_text(src: str) -> str:
    p = Path(str(src)).expanduser()
    if len(str(src)) < 400 and p.suffix and p.exists():
        if p.suffix.lower() == ".pdf":
            r = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True)
            if r.returncode:
                raise T2VError("chưa đọc được PDF — lưu kịch bản dạng .docx hoặc .txt")
            return r.stdout.strip()
        from .ccut_api import read_script
        return read_script(str(p))
    return str(src).strip()


_HEAD = re.compile(r"^\s*(?:#{1,3}\s*)?(?:(?:video|kịch bản|kich ban|clip|tập|tap|bài|bai|script)\s*(?:số\s*)?\d+\b.*|#{1,3}\s+\S.*)$", re.I)
_RULE = re.compile(r"^\s*(?:-{3,}|={3,}|\*{3,}|_{3,})\s*$")
_META = re.compile(r"^\s*(?:tiêu đề|tieu de|title|chủ đề|chu de|thời lượng|thoi luong|ghi chú|ghi chu|hashtag|caption|mô tả|mo ta)\s*:", re.I)


def _title_line(ln: str, nxt: str) -> bool:
    """dòng tiêu đề tự do: ngắn, không dấu kết câu, theo sau là đoạn lời dài (vd “Bất động sản ngáo giá”)."""
    t = ln.strip()
    return bool(t) and len(t.split()) <= 12 and not re.search(r"[.!?…,;]$", t) and len(nxt.split()) >= 12


def split(text: str) -> list[dict]:
    """1 file nhiều kịch bản → [{"title", "text"}]. Tách theo dòng tiêu đề (Video 1…, Kịch bản 2…, # …) hoặc dòng kẻ ---.
    Dòng đầu ngắn kiểu tiêu đề (không dấu câu, sau đó là lời) cũng là tiêu đề — không đọc thành lời."""
    lines = text.replace("\r", "").split("\n")
    first = next((i for i, l in enumerate(lines) if l.strip()), None)
    if first is not None and not (_RULE.match(lines[first]) or _HEAD.match(lines[first])):
        nxt = next((l for l in lines[first + 1:] if l.strip()), "")
        if _title_line(lines[first], nxt):
            lines[first] = "# " + lines[first].strip()
    blocks, cur, title = [], [], None
    for ln in lines:
        if _RULE.match(ln) or _HEAD.match(ln):
            if any(x.strip() for x in cur):
                blocks.append((title, cur))
            cur, title = [], (None if _RULE.match(ln) else ln.strip().lstrip("#").strip())
            continue
        cur.append(ln)
    if any(x.strip() for x in cur):
        blocks.append((title, cur))
    out = []
    for i, (t, ls) in enumerate(blocks):
        body = "\n".join(l for l in ls if not _META.match(l)).strip()
        if len(body.split()) >= 8:
            out.append({"title": t or f"Video {i + 1}", "text": body})
    return out or [{"title": "Video 1", "text": text.strip()}]


_LINK = re.compile(r"!?\[([^\]]*)\]\((?:https?://|www\.)[^)]*\)")         # [nhãn](url) — chú thích nguồn, không đọc
_URL = re.compile(r"(?:https?://|www\.)\S+")
_NOTE = re.compile(r"^\s*(?:[-•>]\s*)?(?:\*{1,2}|_)?\s*(?:hình ảnh(?: gợi ý)?|hinh anh(?: goi y)?|gợi ý hình|cảnh|canh|b-?roll|hình|visual|"
                   r"âm thanh|am thanh|sfx|nhạc(?: nền)?|nhac(?: nen)?|music|ghi chú|ghi chu|lưu ý|luu y|chú thích|chu thich|"
                   r"nguồn|nguon|source|tham khảo|tham khao|text trên màn hình|chữ trên màn hình|on-?screen(?: text)?|ctas?|hashtag)\s*:", re.I)
_TIME = re.compile(r"(?:\d{1,2}:\d{2}|\d+\s*[–—-]\s*\d+\s*(?:giây|giay|s\b|sec)|\d+\s*(?:giây|giay)\b)", re.I)
_QUOTE = re.compile(r"[“\"]([^”\"]{8,})[”\"]")


def spoken(text: str) -> str:
    """CHỈ lời đọc trong kịch bản: bỏ dòng ghi chú (*…*), tiêu đề mốc giờ (**0–8 giây · Mở đầu**), hướng dẫn hình / âm,
    link nguồn [..](url) + url trần, dấu markdown. Kịch bản đặt lời trong ngoặc kép “…” → chỉ đọc phần trong ngoặc.
    (Kịch bản từ CN.AI / ChatGPT hay kèm các phần này — đọc thành tiếng làm giọng dài, phụ đề chứa link, bộ kiểm chặn.)"""
    out = []
    for raw in text.replace("\r", "").split("\n"):
        ln = _URL.sub("", _LINK.sub("", raw)).strip()
        if not ln:
            out.append("")
            continue
        core = ln.strip("*_ ").strip()
        if _NOTE.match(ln) or _NOTE.match(core):
            continue
        if re.fullmatch(r"\*[^*].*[^*]\*|_[^_].*[^_]_", ln) and not core.startswith(("“", '"')):   # cả dòng in nghiêng = ghi chú
            continue
        if re.fullmatch(r"\*\*.+\*\*", ln) and (_TIME.search(ln) or len(core.split()) <= 12) and not core.startswith(("“", '"')):
            continue                                                                           # tiêu đề đậm / mốc giờ
        if re.fullmatch(r"[\[(].*[\])]", ln):                                                 # [chỉ dẫn] / (chỉ dẫn)
            continue
        if _TIME.match(core) and len(core.split()) <= 12 and not _QUOTE.search(ln):
            continue
        ln = re.sub(r"^\s*(?:\*\*|__)?\s*(?:hook|mở đầu|mo dau|mở bài|thân bài|than bai|kết bài|kết|ket|cta|kêu gọi|lời dẫn|loi dan|"
                    r"lời đọc|loi doc|voice ?over|vo|phần \d+|phan \d+|đoạn \d+|doan \d+|ý \d+)\s*(?:\*\*|__)?\s*[:：]\s*(?:\*\*|__)?\s*", "", ln, flags=re.I)
        if ln.strip():
            out.append(ln)
    body = "\n".join(out)
    quotes = [m.group(1).strip() for m in _QUOTE.finditer(body)]
    if len(quotes) >= 2 and sum(len(q.split()) for q in quotes) >= 0.5 * len(re.sub(r"[“”\"*_#>`]", " ", body).split()):
        paras = []
        for para in re.split(r"\n\s*\n", body):
            qs = [m.group(1).strip() for m in _QUOTE.finditer(para)]
            if qs:
                paras.append(" ".join(qs))
        body = "\n\n".join(paras)
    body = re.sub(r"[*_`#>]+", "", body)                 # dấu markdown còn sót
    body = re.sub(r"\[[^\]]*\]", "", body)               # [chú thích] trong câu
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return "\n".join(l.strip() for l in body.split("\n")).strip()


def sentences(text: str) -> list[dict]:
    """[{"text", "para"}] — câu kết bằng . ! ? … hoặc xuống dòng; câu quá dài (>36 từ) cắt ở dấu phẩy."""
    out = []
    for pi, para in enumerate(x for x in re.split(r"\n\s*\n|\n", text) if x.strip()):
        para = re.sub(r"^\s*(?:[-•*]|\d+[.)])\s+", "", para.strip())
        for s in re.split(r"(?<=[.!?…])\s+(?=\S)", para):
            s = s.strip()
            if not s:
                continue
            ws = s.split()
            while len(ws) > 36:
                cut = max((i for i, w in enumerate(ws[:30]) if w.endswith((",", ";", ":"))), default=24)
                out.append({"text": " ".join(ws[:cut + 1]), "para": pi})
                ws = ws[cut + 1:]
            out.append({"text": " ".join(ws), "para": pi})
    return out


# ---------------- so khớp chép lời ↔ kịch bản ----------------
def _tok(t: str) -> list[str]:
    t = unicodedata.normalize("NFC", t).lower()
    return [x for x in re.split(r"[^\w%]+", t) if x]


_DIG = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_SAME = {"mốt": "một", "tư": "bốn", "lăm": "năm", "nhăm": "năm", "ngàn": "nghìn", "lẻ": "linh", "tỉ": "tỷ"}


def _say3(n: int, full: bool) -> list[str]:
    """0–999 đọc kiểu Việt; full = có hàng nghìn phía trước (đọc cả “không trăm”, “linh”)."""
    h, t, u = n // 100, n // 10 % 10, n % 10
    out = []
    if h or full:
        out += [_DIG[h], "trăm"]
    if t == 0:
        if u and (h or full):
            out += ["linh", _DIG[u]]
        elif u:
            out += [_DIG[u]]
    elif t == 1:
        out += ["mười"] + ([{5: "năm"}.get(u, _DIG[u])] if u else [])
    else:
        out += [_DIG[t], "mươi"] + ([{1: "một", 5: "năm"}.get(u, _DIG[u])] if u else [])
    return out


def _say_int(n: int) -> list[str]:
    if n == 0:
        return ["không"]
    out, units, first = [], ["", "nghìn", "triệu", "tỷ"], True
    groups = []
    while n:
        groups.append(n % 1000)
        n //= 1000
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0 and i not in (0, 3):
            continue
        if g or i == 3:
            out += _say3(g, not first) if g else []
            if units[i % 4] and (g or i == 3):
                out.append(units[i % 4] if i < 4 else "tỷ")
            first = False
    return [w for w in out if w]


def _say_num(tok: str) -> list[str] | None:
    """“42%”, “1.000.000”, “3,6”, “2026” (chữ số Whisper chép) → các từ tiếng Việt như kịch bản viết số bằng chữ."""
    m = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(%?)", tok)
    if not m:
        return None
    words = _say_int(int(m.group(1).replace(".", "")))
    if m.group(2):
        words += ["phẩy"] + [_DIG[int(c)] for c in m.group(2)]
    if m.group(3):
        words += ["phần", "trăm"]
    return words


def _norm_word(w: str) -> str:
    t = _tok(w)
    t = t[0] if t else ""
    return _SAME.get(t, t)


def _asr_words(asr: list[tuple[str, float, float]]) -> list[tuple[str, float, float]]:
    """tách từng từ Whisper ra từ đơn đã chuẩn hoá; số viết bằng chữ số → đọc ra chữ (chia đều thời gian cho các từ)."""
    out = []
    for w, a, b in asr:
        raw = unicodedata.normalize("NFC", w).strip().strip(".,;:!?…“”\"()").lower()
        spoken = _say_num(raw)
        if spoken:
            d = (b - a) / len(spoken)
            out += [(x, a + k * d, a + (k + 1) * d) for k, x in enumerate(spoken)]
        else:
            out.append((_norm_word(w), a, b))
    return out


def _align(script_words: list[str], asr: list[tuple[str, float, float]]) -> tuple[list[tuple[float, float] | None], float]:
    """mốc thời gian cho từng từ KỊCH BẢN theo bản chép lời; trả (mốc, tỷ lệ khớp).
    Whisper chép số bằng chữ số (“42%”, “2026”) còn kịch bản thường viết bằng chữ (“bốn mươi hai phần trăm”) → đổi số
    của Whisper ra chữ trước khi so; không thì câu nhiều số bị coi là đọc sai và bị đọc lại vô ích."""
    asr = _asr_words(asr)
    a = [_norm_word(w) for w in script_words]
    b = [w for w, _, _ in asr]
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    times: list = [None] * len(a)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = asr[blk.b + k][1:]
    ratio = sum(t is not None for t in times) / max(1, len(a))
    return times, ratio


def _fill(times: list, t0: float, t1: float) -> list[tuple[float, float]]:
    """từ chưa khớp (số đọc thành chữ, tiếng Anh…) → nội suy giữa 2 từ đã khớp."""
    n = len(times)
    known = [(i, t) for i, t in enumerate(times) if t]
    out = []
    for i in range(n):
        if times[i]:
            out.append(times[i])
            continue
        lo = max((k for k in known if k[0] < i), default=(-1, (t0, t0)), key=lambda k: k[0])
        hi = min((k for k in known if k[0] > i), default=(n, (t1, t1)), key=lambda k: k[0])
        a, b = lo[1][1], hi[1][0]
        span = (b - a) / (hi[0] - lo[0])
        s = a + span * (i - lo[0] - 1)
        out.append((round(s, 3), round(s + span, 3)))
    return out


def _align_rel(sw: list[str], seg: list[tuple[str, float, float]], a: float, b: float):
    """mốc từng từ của MỘT câu (đang nằm ở [a, b] trong voice) → (từ, mốc tương đối đầu câu, tỷ lệ khớp)."""
    times, ratio = _align(sw, seg)
    return sw, [(x - a, y - a) for x, y in _fill(times, a, b)], ratio


def retext(pdir, script: str, min_ratio: float = 0.5, log=print) -> float:
    """Voice to Motion CÓ kịch bản: chữ trong transcript.json lấy theo KỊCH BẢN (đúng chính tả, tên riêng như C-Cut),
    chỉ giữ mốc thời gian của bản chép lời. Kịch bản lệch quá nhiều so với lời nói (< min_ratio) → giữ bản chép lời.
    Trả tỷ lệ khớp."""
    pdir = Path(pdir)
    f = pdir / "transcript.json"
    tr = json.loads(f.read_text(encoding="utf-8"))
    sents = sentences(script or "")
    sw = [w for s in sents for w in s["text"].split()]
    asr = [(w["text"], w["start"], w["end"]) for w in tr.get("words", [])]
    if not sw or not asr:
        return 0.0
    times, ratio = _align(sw, asr)
    if ratio < min_ratio:
        log(f"Kịch bản chỉ khớp {ratio:.0%} lời nói → giữ chữ chép lời")
        return ratio
    tm = _fill(times, asr[0][1], asr[-1][2])
    conf = {round(w["start"], 3): w.get("conf", 1.0) for w in tr["words"]}
    wl, sl, k = [], [], 0
    for s in sents:
        n = len(s["text"].split())
        seg = tm[k:k + n]
        for j, w in enumerate(s["text"].split()):
            a, b = seg[j]
            wl.append({"i": k + j, "text": w, "start": round(a, 3), "end": round(max(b, a + 0.02), 3),
                       "conf": conf.get(round(a, 3), 1.0) if times[k + j] else 0.5})
        sl.append({"text": s["text"], "start": round(seg[0][0], 3), "end": round(seg[-1][1], 3)})
        k += n
    (pdir / "transcript_asr.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    tr.update(words=wl, sentences=sl, text_from="script")
    f.write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Phụ đề theo kịch bản (khớp {ratio:.0%} lời nói)")
    return ratio


# ---------------- dựng giọng ----------------
def prepare(pdir, src: str, voice_id: str, speed: float = SPEED, progress=print) -> dict:
    import soundfile as sf
    from . import voice as V
    from .transcribe import transcribe
    pdir = Path(pdir)
    work = pdir / "work_t2v"
    work.mkdir(parents=True, exist_ok=True)
    raw = read_text(src)
    text = spoken(raw)                                   # chỉ lời đọc — bỏ ghi chú, mốc giờ, link nguồn
    if text != raw.strip():
        (pdir / "script_goc.txt").write_text(raw, encoding="utf-8")   # bản gốc (có link nguồn) để ghi nguồn
    sents = sentences(text)
    if not sents:
        raise T2VError("kịch bản trống")
    (pdir / "script.txt").write_text(text, encoding="utf-8")
    sr = V.SR

    def synth(i):
        f = work / f"s{i:03d}.wav"
        V.say(sents[i]["text"], voice_id, f, 1.0)
        return f

    files = [None] * len(sents)
    for i in range(len(sents)):
        progress(f"Đọc câu {i + 1}/{len(sents)}")
        files[i] = synth(i)
    rel: dict[int, tuple] = {}     # câu → (từ, mốc từng từ TƯƠNG ĐỐI đầu câu, tỷ lệ khớp) — đọc lại câu nào chỉ nghe lại câu đó
    vocab = sorted({w for s in sents for w in s["text"].split() if w[:1].isupper()})[:40]
    redo = list(range(len(sents)))
    for attempt in range(3):
        # ghép (nghỉ ngắn giữa câu, dài hơn giữa đoạn) → tốc độ → chép lời (lần đầu cả bài, lần sau chỉ câu đọc lại)
        parts, marks, t = [], [], 0.0
        for i, f in enumerate(files):
            x, _ = sf.read(str(f), dtype="float32")
            marks.append((t, t + len(x) / sr))
            parts.append(x)
            t += len(x) / sr
            if i + 1 < len(files):
                g = GAP_PARA if sents[i + 1]["para"] != sents[i]["para"] else GAP_SENT
                parts.append(np.zeros(int(g * sr), dtype=np.float32))
                t += g
        raw = work / "voice_raw.wav"
        sf.write(str(raw), np.concatenate(parts), sr)
        out = pdir / "voice.wav"
        k = max(0.8, min(1.3, float(speed)))
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", f"atempo={k:.3f}" if abs(k - 1) > 0.01 else "anull",
                        "-ar", str(sr), str(out)], check=True)
        marks = [(a / k, b / k) for a, b in marks]
        wav16 = work / "asr16.wav"
        if len(redo) == len(sents):
            progress("Kiểm tra giọng đọc (chép lời lại)")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "16000", str(wav16)], check=True)
            words, _ = transcribe(str(wav16), vocab=vocab)
            asr = [(w.text, w.source_start, w.source_end) for w in words]
            for i in redo:
                a, b = marks[i]
                rel[i] = (*_align_rel(sents[i]["text"].split(), [w for w in asr if a - 0.15 <= (w[1] + w[2]) / 2 <= b + 0.15], a, b),)
        else:
            # chỉ nghe lại đúng các câu vừa đọc lại (cả bài mất nhiều phút trên máy yếu): ghép các câu đó (cách nhau 1.5 s im)
            # thành một file → Whisper một lần → trả mốc về đúng vị trí trong voice
            progress(f"Kiểm tra lại câu {', '.join(str(i + 1) for i in redo)}")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "16000", str(wav16)], check=True)
            full, sr16 = sf.read(str(wav16), dtype="float32")
            chunks, offs, pos = [], [], 0.0
            for i in redo:
                a, b = marks[i]
                a0, b0 = max(0.0, a - 0.15), b + 0.15
                x = full[int(a0 * sr16):int(b0 * sr16)]
                offs.append((i, pos, a0, pos + len(x) / sr16))
                chunks += [x, np.zeros(int(1.5 * sr16), np.float32)]
                pos += len(x) / sr16 + 1.5
            part = work / "asr16_redo.wav"
            sf.write(str(part), np.concatenate(chunks), sr16)
            words, _ = transcribe(str(part), vocab=vocab)
            for i, p0, a0, p1 in offs:
                asr = [(w.text, w.source_start - p0 + a0, w.source_end - p0 + a0) for w in words
                       if p0 - 0.1 <= (w.source_start + w.source_end) / 2 <= p1 + 0.1]
                a, b = marks[i]
                rel[i] = _align_rel(sents[i]["text"].split(), asr, a, b)
        rows = []
        bad = []
        for i, s in enumerate(sents):
            sw, rtm, ratio = rel[i]
            a = marks[i][0]
            rows.append((sw, [(a + x, a + y) for x, y in rtm], ratio))
            if ratio < 0.6 and len(sw) >= 3:
                bad.append(i)
        if not bad or attempt == 2:
            break
        redo = bad
        for i in bad:                                 # đọc lại đúng những câu lệch nhiều (giọng nhân bản đôi khi đọc vấp)
            progress(f"Đọc lại câu {i + 1} (lần {attempt + 2})")
            files[i] = synth(i)
    dur = len(sf.read(str(pdir / "voice.wav"))[0]) / sr
    wl, sl, k = [], [], 0
    for i, (sw, tm, ratio) in enumerate(rows):
        for w, (a, b) in zip(sw, tm):
            wl.append({"i": k, "text": w, "start": round(a, 3), "end": round(b, 3), "conf": 1.0})
            k += 1
        sl.append({"text": sents[i]["text"], "start": round(marks[i][0], 3), "end": round(marks[i][1], 3)})
    tr = {"voice": "voice.wav", "duration_s": round(dur, 3), "channels": 1, "codec": "pcm_s16le", "sample_rate": sr,
          "source": "t2v", "words": wl, "sentences": sl}
    (pdir / "transcript.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    meta = {"voice": voice_id, "speed": k_round(speed), "duration_s": round(dur, 3),
            "sentences": [{"i": i, "text": s["text"], "para": s["para"], "start": sl[i]["start"], "end": sl[i]["end"],
                           "match": round(rows[i][2], 2)} for i, s in enumerate(sents)]}
    (pdir / "script.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    weak = [m["i"] + 1 for m in meta["sentences"] if m["match"] < 0.6 and len(m["text"].split()) >= 3]
    progress(f"Giọng đọc {dur:.1f}s · {len(sents)} câu" + (f" · câu cần nghe lại: {weak}" if weak else ""))
    return meta


def k_round(x) -> float:
    return round(max(0.8, min(1.3, float(x))), 2)


def main():
    a = sys.argv[1:]
    if a[:1] == ["split"]:
        for i, v in enumerate(split(read_text(a[1]))):
            print(f"[{i + 1}] {v['title']} · {len(v['text'].split())} từ · ~{len(v['text'].split()) / WPS:.0f}s")
    elif a[:1] == ["prepare"]:
        m = prepare(a[1], a[2], a[3], float(a[4]) if len(a) > 4 else SPEED)
        print(json.dumps({k: m[k] for k in ("voice", "speed", "duration_s")}, ensure_ascii=False))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
