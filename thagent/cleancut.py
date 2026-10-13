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


def levels(media: str, hop=0.02):
    """độ to từng khung 20ms (dB) + mức giọng (p90) và mức ồn nền (p10) của chính clip."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", media, "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    h = int(16000 * hop)
    n = len(a) // h
    if n < 10:
        return np.zeros(0), -20.0, -60.0
    r = 20 * np.log10(np.sqrt((a[:n * h].reshape(n, h) ** 2).mean(1)) + 1e-9)
    return r, float(np.percentile(r, 90)), float(np.percentile(r, 10))


def silences(media: str, min_d=0.12, hop=0.02) -> list[tuple[float, float]]:
    """khoảng lặng theo độ to của CHÍNH clip (ngưỡng cố định −35 dB hỏng với clip thu nhỏ: giọng chỉ ~−30 dB)."""
    import numpy as np
    r, speech, noise = levels(media, hop)
    if not len(r):
        return []
    thr = min(speech - 10, max(noise + 6, speech - 20))
    q = np.convolve((r < thr).astype(float), np.ones(3) / 3, "same") > 0.5     # bỏ nhiễu lẻ 1 khung
    out, st = [], None
    for i, v in enumerate(np.append(q, False)):
        if v and st is None:
            st = i
        elif not v and st is not None:
            if (i - st) * hop >= min_d:
                out.append((round(st * hop, 3), round(i * hop, 3)))
            st = None
    return out


def _tighten(words, sil):
    """ASR hay kéo dài 1 từ trùm lên đoạn ngập ngừng (“đến@0.20–1.60”): từ dài bất thường mà bên trong có khoảng lặng
    → co về phần tiếng sát từ kế tiếp (hoặc sát từ trước nếu từ kế tiếp ở xa)."""
    out = [w.model_copy() for w in words]
    for k, w in enumerate(out):
        if w.source_end - w.source_start < 0.6:
            continue
        inner = [(a, b) for a, b in sil if a > w.source_start + 0.05 and b < w.source_end + 0.05 and b - a >= 0.15]
        if not inner:
            continue
        nxt = out[k + 1].source_start if k + 1 < len(out) else 1e9
        if nxt - w.source_end < 0.15:
            w.source_start = inner[-1][1]
        else:
            w.source_end = inner[0][0]
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
    for i in range(len(words) - 1):   # nói vấp rồi nói lại 1 từ, có ngập ngừng ở giữa: “Đến… Đến bây giờ”
        if toks[i] and toks[i] == toks[i + 1] and words[i + 1].source_start - words[i].source_end > 0.25 \
                and not any(a <= i < b for a, b, _ in out):
            out.append((i, i + 1, f"nói vấp “{words[i].text}… {words[i + 1].text}”"))
    for n in (4, 3, 2):   # lắp bắp: cụm ≥2 từ lặp liền kề → bỏ lần đầu (1 từ lặp hay là 2 câu: “bữa ăn. Ăn theo”)
        for i in range(len(words) - 2 * n + 1):
            if toks[i:i + n] == toks[i + n:i + 2 * n] and all(toks[i:i + n]) and not any(a <= i < b for a, b, _ in out):
                out.append((i, i + n, "lắp bắp “" + " ".join(w.text for w in words[i:i + n]) + "”"))
    return sorted(out)


def clean_cut(words, src_dur: float, media: str, zoom=1.08, fps=30):
    """→ (segments keep theo order, cuts keep=False, zoom fx xen kẽ theo timeline)."""
    sil = silences(media)
    words = _tighten(words, sil)
    drops = _drops(words)
    gone = set()
    for a, b, _ in drops:
        gone.update(range(a, b))
    keep_w = [w for i, w in enumerate(words) if i not in gone]

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
    # ậm ừ: tiếng đệm không thành lời giữa 2 từ (ASR bỏ qua “ờ/ừm”) + từ 1 âm tiết bị kéo dài (“ởờờ”, “vớiii”)
    lv, sp, no = levels(media)
    thr = min(sp - 10, max(no + 6, sp - 20))
    holes = []
    for p, w in zip(keep_w, keep_w[1:]):
        g0, g1 = p.source_end, w.source_start
        seg = lv[int(g0 / 0.02):int(g1 / 0.02)]
        if g1 - g0 >= 0.35 and len(seg) and (seg > thr).mean() > 0.5:
            holes.append((g0 + 0.12, g1 - 0.12, f"âm đệm không thành lời {g1 - g0:.2f}s"))
    for w in keep_w:
        d = w.source_end - w.source_start
        if d > 0.6 and " " not in w.text.strip() and len(re.sub(r"[^\w]", "", w.text)) <= 5 and not any(ch.isdigit() for ch in w.text):
            holes.append((w.source_start + 0.2, w.source_end - 0.15, f"kéo dài chữ “{w.text}” {d:.2f}s"))
    for x, y, why in holes:
        for k, (sa, sb) in enumerate(spans):
            if sa < x and y < sb and y - x > 0.08:
                spans[k:k + 1] = [(sa, x), (y, sb)]
                cuts.append(EditSegment(id=f"cut_h{len(cuts)}", source_in=round(x, 3), source_out=round(y, 3), keep=False,
                                        reason=why, confidence=0.75))
                break
    seen = set()
    cuts = [c for c in cuts if (c.source_in, c.source_out) not in seen and not seen.add((c.source_in, c.source_out))]
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
