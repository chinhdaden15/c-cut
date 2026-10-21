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


def _align(script_words: list[str], asr: list[tuple[str, float, float]]) -> tuple[list[tuple[float, float] | None], float]:
    """mốc thời gian cho từng từ KỊCH BẢN theo bản chép lời; trả (mốc, tỷ lệ khớp)."""
    a = [_tok(w)[0] if _tok(w) else "" for w in script_words]
    b = [_tok(w)[0] if _tok(w) else "" for w, _, _ in asr]
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


# ---------------- dựng giọng ----------------
def prepare(pdir, src: str, voice_id: str, speed: float = SPEED, progress=print) -> dict:
    import soundfile as sf
    from . import voice as V
    from .transcribe import transcribe
    pdir = Path(pdir)
    work = pdir / "work_t2v"
    work.mkdir(parents=True, exist_ok=True)
    text = read_text(src)
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
    for attempt in range(3):
        # ghép (nghỉ ngắn giữa câu, dài hơn giữa đoạn) → tốc độ → chép lời một lần cho cả bài
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
        progress("Kiểm tra giọng đọc (chép lời lại)")
        wav16 = work / "asr16.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-ac", "1", "-ar", "16000", str(wav16)], check=True)
        words, _ = transcribe(str(wav16), vocab=sorted({w for s in sents for w in s["text"].split() if w[:1].isupper()})[:40])
        asr = [(w.text, w.source_start, w.source_end) for w in words]
        bad, rows = [], []
        for i, s in enumerate(sents):
            a, b = marks[i]
            seg = [w for w in asr if a - 0.15 <= (w[1] + w[2]) / 2 <= b + 0.15]
            sw = s["text"].split()
            times, ratio = _align(sw, seg)
            rows.append((sw, _fill(times, a, b), ratio))
            if ratio < 0.6 and len(sw) >= 3:
                bad.append(i)
        if not bad or attempt == 2:
            break
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
