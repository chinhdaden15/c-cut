"""Cắt sạch: bỏ đầu/đuôi thừa, rút khoảng lặng (0.3s giữa câu, 0.15s giữa từ), bỏ hiệu lệnh đếm
("1 2 3 diễn", "2 3 nói", "3 2 1"...), từ đệm ừ/à/ờ, lắp bắp lặp liền kề. Mọi chỗ cắt ghi lại kèm lý do
để Claude duyệt; người dùng muốn giữ chỗ nào thì bỏ cut đó. Biên lặng đo bằng sóng âm (chính xác hơn ASR)."""
from __future__ import annotations

import re
import subprocess

from .schema import EditSegment, VideoFxEvent

SENT_GAP, WORD_GAP = 0.30, 0.15     # khoảng lặng giữ lại
TAIL = 0.40                         # dừng sau chữ cuối câu kết
FILLERS = {"ừ", "à", "ờ", "ừm", "ờm", "ơ", "ầm", "ừa", "hử", "ưm", "um", "uh"}
NUM = {"một": "1", "hai": "2", "ba": "3"}
CUE_RE = [r"(1 )?2 3 (diễn|nói|bắt đầu|quay)", r"3 2 1( (diễn|nói|bắt đầu))?", r"1 2 3"]
END_PUNCT = ".?!…"


def _n(t: str) -> str:
    t = re.sub(r"[^\w]", "", t.lower())
    return NUM.get(t, t)


def silences(media: str, db=-35, min_d=0.12) -> list[tuple[float, float]]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", media, "-af", f"silencedetect=n={db}dB:d={min_d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    st, out = None, []
    for ln in r.stderr.splitlines():
        if "silence_start" in ln:
            st = float(ln.split("silence_start:")[1].split()[0])
        elif "silence_end" in ln and st is not None:
            out.append((max(st, 0.0), float(ln.split("silence_end:")[1].split()[0]))); st = None
    return out


def _drops(words) -> list[tuple[int, int, str]]:
    """các cụm từ [i, j) cần bỏ, kèm lý do."""
    toks = [_n(w.text) for w in words]
    out = []
    # hiệu lệnh đếm: chỉ nhận khi đứng tách khỏi lời (có nghỉ trước/sau hoặc ở đầu clip)
    s = " ".join(toks)
    for pat in CUE_RE:
        for m in re.finditer(r"(?:^| )(" + pat + r")(?= |$)", s):
            i = s[:m.start(1)].count(" ")
            j = i + m.group(1).count(" ") + 1
            pre = words[i].source_start - words[i - 1].source_end if i else 9
            post = words[j].source_start - words[j - 1].source_end if j < len(words) else 9
            if pre > 0.35 or post > 0.35 or i == 0:
                k = i
                if i:   # bỏ luôn câu hỏng ngay trước hiệu lệnh (từ đầu câu/khoảng nghỉ lớn gần nhất)
                    k = i - 1
                    while k > 0 and words[k - 1].text[-1:] not in END_PUNCT and words[k].source_start - words[k - 1].source_end < 0.6:
                        k -= 1
                    if i - k > 25:     # quá dài → chỉ bỏ hiệu lệnh, để Claude xem
                        k = i
                out.append((k, j, "hiệu lệnh đếm “" + " ".join(w.text for w in words[i:j]) + "”" +
                            (f" + câu hỏng trước đó ({i - k} từ)" if k < i else "")))
    for i, t in enumerate(toks):
        if t in FILLERS:
            out.append((i, i + 1, f"từ đệm “{words[i].text}”"))
    for n in (4, 3, 2):   # lắp bắp: cụm ≥2 từ lặp liền kề → bỏ lần đầu (1 từ lặp hay là 2 câu: “bữa ăn. Ăn theo”)
        for i in range(len(words) - 2 * n + 1):
            if toks[i:i + n] == toks[i + n:i + 2 * n] and all(toks[i:i + n]) and not any(a <= i < b for a, b, _ in out):
                out.append((i, i + n, "lắp bắp “" + " ".join(w.text for w in words[i:i + n]) + "”"))
    return sorted(out)


def clean_cut(words, src_dur: float, media: str, zoom=1.08, fps=30):
    """→ (segments keep theo order, cuts keep=False, zoom fx xen kẽ theo timeline)."""
    drops = _drops(words)
    gone = set()
    for a, b, _ in drops:
        gone.update(range(a, b))
    keep_w = [w for i, w in enumerate(words) if i not in gone]
    sil = silences(media)

    def voice_end(t):        # kéo biên tới hết tiếng thật (ASR hay cắt sớm đuôi từ)
        for a, b in sil:
            if a <= t + 0.6 and b > t:
                return max(t, a)
        return t

    def voice_start(t):
        for a, b in sil:
            if a < t < b:
                return b
        return t

    cuts = [EditSegment(id=f"cut_d{k}", source_in=words[a].source_start, source_out=words[b - 1].source_end,
                        keep=False, reason=r, confidence=0.7) for k, (a, b, r) in enumerate(drops)]
    head = max(0.0, voice_start(keep_w[0].source_start) - 0.10)
    if head > 0.05:
        cuts.append(EditSegment(id="cut_head", source_in=0, source_out=head, keep=False, reason="đầu clip chưa nói", confidence=0.95))
    spans, a = [], head
    for p, w in zip(keep_w, keep_w[1:]):
        e, s = voice_end(p.source_end), voice_start(w.source_start)
        jumped = words.index(w) - words.index(p) > 1
        keep_gap = SENT_GAP if p.text[-1:] in END_PUNCT + "," or s - e > 0.6 or jumped else WORD_GAP
        if s - e > keep_gap + 0.04 or jumped:
            g = max(0.0, s - e)
            k = min(g, keep_gap)
            x, y = e + k * 0.5, s - k * 0.5
            spans.append((a, x)); a = y
            cuts.append(EditSegment(id=f"cut_g{len(cuts)}", source_in=round(x, 3), source_out=round(y, 3), keep=False,
                                    reason=f"lặng {g:.2f}s → giữ {k:.2f}s" if not jumped else "nối qua đoạn bỏ", confidence=0.9))
    end = min(src_dur, voice_end(keep_w[-1].source_end) + TAIL)
    spans.append((a, end))
    if src_dur - end > 0.1:
        cuts.append(EditSegment(id="cut_tail", source_in=round(end, 3), source_out=src_dur, keep=False,
                                reason="sau câu kết (đoạn tắt máy)", confidence=0.9))
    segs = [EditSegment(id=f"s{i:03d}", source_in=round(x, 3), source_out=round(y, 3), order=i, reason="giữ lời nói")
            for i, (x, y) in enumerate(spans) if y - x > 0.08]
    fx, t = [], 0
    for i, s in enumerate(segs):     # phóng nhẹ xen kẽ để giấu jump cut
        n = int(round(s.source_out * fps)) - int(round(s.source_in * fps))
        if i % 2 and zoom > 1:
            fx.append(VideoFxEvent(id=f"jz_{i}", type="zoom", start=t, end=t + n,
                                   params={"scale": zoom, "cx": 0.5, "cy": 0.35, "mode": "cut"}))
        t += n
    return segs, cuts, fx


def report(segs, cuts) -> str:
    kept_d = sum(s.source_out - s.source_in for s in segs)
    lines = [f"{len(segs)} đoạn giữ, tổng {kept_d:.1f}s; {len(cuts)} chỗ cắt:"]
    for c in sorted(cuts, key=lambda c: c.source_in):
        lines.append(f"  {c.source_in:7.2f}–{c.source_out:7.2f}  ({c.source_out - c.source_in:.2f}s)  {c.reason}")
    return "\n".join(lines)
