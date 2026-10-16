"""Làm sạch voice cho Voice to Motion — dùng lại bộ “Cắt sạch” của Talking Head (thagent.cleancut):
cắt nói vấp/lắp bắp lặp liền kề, từ đệm (ừ/à/ờ), âm đệm không thành lời, chữ kéo dài, hiệu lệnh đếm,
khoảng lặng thừa (giữ 0,3s giữa câu, 0,15s giữa từ), đầu/đuôi thừa. Biên lặng đo bằng sóng âm thật.

- Voice gốc giữ nguyên (voice.*); bản đã cắt: voice_clean.wav; transcript gốc → transcript_raw.json.
- Mốc từng từ được dời theo các đoạn giữ → timeline dựng trên voice đã cắt vẫn khớp lời.
- Báo cáo từng chỗ cắt + lý do: voice_edit.json (người dùng muốn giữ chỗ nào thì bỏ cut đó rồi chạy lại).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from ..cleancut import clean_cut, report
from ..schema import TranscriptWord


def _words(tr: dict) -> list[TranscriptWord]:
    return [TranscriptWord(id=f"w{w['i']:04d}", text=w["text"], source_start=w["start"], source_end=w["end"],
                           confidence=w.get("conf", 1.0)) for w in tr["words"]]


def clean(pdir: Path, denoise: bool = True, log=print) -> dict:
    pdir = Path(pdir)
    raw = pdir / "transcript_raw.json"
    if not raw.exists():                        # lần đầu: lưu transcript gốc
        shutil.copy2(pdir / "transcript.json", raw)
    tr = json.loads(raw.read_text(encoding="utf-8"))
    src = pdir / tr["voice"]
    dur = float(tr["duration_s"])
    segs, cuts, _fx = clean_cut(_words(tr), dur, str(src), zoom=1.0)
    spans = [(s.source_in, s.source_out) for s in segs]
    # từ viết tắt in hoa (IPC, FED, USD…) đọc từng chữ cái → dài là đúng, KHÔNG phải “kéo dài chữ”: nối lại đoạn đã tách
    import re as _re
    keep_back = [c for c in cuts if c.reason.startswith("kéo dài chữ") and
                 _re.search(r"“([A-ZĐ0-9]{2,})”", c.reason)]
    for c in keep_back:
        for k in range(len(spans) - 1):
            if abs(spans[k][1] - c.source_in) < 0.002 and abs(spans[k + 1][0] - c.source_out) < 0.002:
                spans[k:k + 2] = [(spans[k][0], spans[k + 1][1])]
                break
    cuts = [c for c in cuts if c not in keep_back]
    # ghép các đoạn giữ, mỗi mối nối có fade 8ms để không “tách” tiếng
    work = pdir / "work_clean"
    work.mkdir(exist_ok=True)
    base = work / "src.wav"
    if denoise:
        from ..pipeline import denoise_voice   # lọc ồn theo độ to của chính clip (như Talking Head)
        denoise_voice(str(src), str(base), log)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "48000", str(base)], check=True)
    parts = []
    for i, (a, b) in enumerate(spans):
        p = work / f"p{i:03d}.wav"
        d = b - a
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", str(base), "-af",
                        f"afade=t=in:d=0.008,afade=t=out:st={max(d - 0.008, 0):.3f}:d=0.008", "-ar", "48000", "-ac", "1", str(p)],
                       check=True)
        parts.append(p)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    out = pdir / "voice_clean.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)], check=True,
                   cwd=work)
    shutil.rmtree(work, ignore_errors=True)
    # dời mốc từ: chỉ giữ từ nằm trong đoạn giữ
    shift, kept, t_acc = [], [], 0.0
    for a, b in spans:
        shift.append((a, b, t_acc - a))
        t_acc += b - a
    def home(w):
        """đoạn giữ chứa phần lớn thời lượng của từ (ASR hay đặt mốc đầu câu sớm hơn điểm cắt theo sóng âm)."""
        d = max(w["end"] - w["start"], 0.02)
        best = max(shift, key=lambda s_: min(w["end"], s_[1]) - max(w["start"], s_[0]))
        ov = min(w["end"], best[1]) - max(w["start"], best[0])
        if ov >= 0.5 * d:
            return best
        mid = (w["start"] + w["end"]) / 2
        if any(c.id.startswith("cut_d") and c.source_in - 0.02 <= mid <= c.source_out + 0.02 for c in cuts):
            return None                                   # vấp/lặp/từ đệm/hiệu lệnh đếm: bộ Cắt sạch đã bỏ thật
        # ASR kéo từ trùm lên khoảng lặng: gắn vào đoạn giữ có phần tiếng của từ (đoạn chạm từ, gần nhất)
        touch = [s_ for s_ in shift if s_[1] > w["start"] - 0.05 and s_[0] < w["end"] + 0.05]
        return min(touch or shift, key=lambda s_: abs((s_[0] + s_[1]) / 2 - mid))
    for w in tr["words"]:
        h = home(w)
        if h:
            a, b, off = h
            kept.append({**w, "start": round(max(w["start"], a) + off, 3), "end": round(min(w["end"], b) + off, 3)})
    for i, w in enumerate(kept):
        w["i"] = i
    new = {**tr, "voice": out.name, "duration_s": round(t_acc, 3), "words": kept, "cleaned_from": tr["voice"],
           "sentences": []}
    (pdir / "transcript.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
    rep = {"source": tr["voice"], "source_s": dur, "clean_s": round(t_acc, 3), "removed_s": round(dur - t_acc, 3),
           "denoise": denoise, "kept_spans": spans,
           "cuts": [{"from": c.source_in, "to": c.source_out, "s": round(c.source_out - c.source_in, 3), "reason": c.reason}
                    for c in sorted(cuts, key=lambda c: c.source_in)],
           "dropped_words": [w["text"] for w in tr["words"] if not home(w)]}
    (pdir / "voice_edit.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    from ..schema import EditSegment
    log(report([EditSegment(id=f"s{i}", source_in=a, source_out=b) for i, (a, b) in enumerate(spans)], cuts))
    return rep


def restore(pdir: Path):
    """bỏ làm sạch: dùng lại voice + transcript gốc (người dùng nói “giữ nguyên voice”)."""
    pdir = Path(pdir)
    raw = pdir / "transcript_raw.json"
    if raw.exists():
        shutil.copy2(raw, pdir / "transcript.json")
    (pdir / "voice_clean.wav").unlink(missing_ok=True)
    (pdir / "voice_edit.json").unlink(missing_ok=True)
