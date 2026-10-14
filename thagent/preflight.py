"""Kiểm tra TRƯỚC khi render (vài giây, không encode video). Render chỉ là bước cuối.

python -m thagent.preflight <project> [--stills]
Trả về danh sách lỗi (error) / cảnh báo (warn); error > 0 → không render.
"""
from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter

import numpy as np

from . import pipeline as P, render as R, timeline as T
from .sfx import SFX_DIR
from .typography import group_extent

import re

GAP_RULE_S = 15.5      # quy tắc: ~15s nhân vật nói → 1 đoạn graphic
COOLDOWN = 4           # giống render.mix_audio


def _frames(path: str) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-select_streams", "v:0",
                        "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", path], capture_output=True, text=True)
    tok = r.stdout.strip().strip(",").split(",")[0]   # một số nguồn trả "1807," (có stream kèm)
    return int(tok or 0)


def check(pid: str, stills: bool = False) -> list[tuple[str, str]]:
    c = P.Ctx(pid)
    pl = c.project.plan
    T.build_mapping(pl)
    fps, out = pl.fps, []
    add = lambda sev, msg: out.append((sev, msg))

    # 1) độ dài nguồn: proxy/alpha phải đủ frame cho mọi đoạn giữ
    need = max(T.sec_to_frame(s.source_out, fps) for s in T.kept(pl))
    for name, path in (("proxy", c.project.proxy), ("alpha", str(c.path("work", "alpha.mp4")))):
        n = _frames(path)
        if n < need:
            add("error", f"{name} chỉ có {n} frame < cần {need}")
    # 2) âm thanh: mô phỏng đúng thuật toán cooldown của mix_audio
    man = json.loads((SFX_DIR / "manifest.json").read_text())
    chosen, dropped = [], []
    for s in sorted([s for s in pl.sounds if s.enabled], key=lambda s: -s.priority):
        if s.asset not in man:
            add("error", f"SFX {s.id}: thiếu asset {s.asset}")
            continue
        (dropped if any(abs(s.hit - x.hit) < COOLDOWN for x in chosen) else chosen).append(s)
    for s in dropped:
        if s.asset != "u_tick" and not s.asset.startswith("tick"):
            add("warn", f"SFX {s.id} ({s.asset}) @ {T.tc(s.hit)} sẽ bị loại vì quá sát âm khác")
    ticks = [x.hit for x in chosen if x.asset == "u_tick"]
    for s in chosen:
        if s.asset != "u_tick" and any(abs(s.hit - t) < 6 for t in ticks) and s.priority < 9:
            add("warn", f"SFX {s.id} ({s.asset}) đè lên tiếng chữ rơi @ {T.tc(s.hit)}")
    per_sec = Counter(x.hit // fps for x in chosen if x.asset != "u_tick")
    for sec, n in per_sec.items():
        if n > 2:
            add("warn", f"giây {sec}: {n} âm (không tính tick) — có thể rối tai")
    # 3) thời lượng graphic theo quy tắc
    segs = sorted((m["start"], m["end"]) for m in pl.mg)
    prev = 0
    for a, b in segs + [(pl.duration_frames, pl.duration_frames)]:
        if (a - prev) / fps > GAP_RULE_S:
            add("warn", f"nói liên tục {(a - prev) / fps:.1f}s ({T.tc(prev)}→{T.tc(a)}) > {GAP_RULE_S}s, cần thêm graphic")
        prev = b
    # 4) bố cục + thời gian đọc + chồng nhóm cùng lớp
    anchors = json.loads(c.path("work", "anchors.json").read_text())
    atl = R.timeline_anchors(pl, anchors)
    pos = R.resolve_layout(pl, atl, pl.width, pl.height)
    for g in pl.text_groups:
        if not g.enabled:
            continue
        ax, ay = pos[g.id]
        x0, y0, x1, y1 = group_extent(g)
        if ax + x0 < 0 or ax + x1 > pl.width or ay + y0 < 0 or ay + y1 > pl.height:
            add("error", f"{g.id}: tràn khung ({ax + x0:.0f},{ay + y0:.0f})–({ax + x1:.0f},{ay + y1:.0f})")
        last = max(g.start + (max(s.word_delays) if s.word_delays else s.delay_frames) + 9
                   for s in g.spans if s.style != "icon")
        if (g.end - g.exit_frames - last) / fps < 1.5:   # chữ chính giữ ≥1.5s
            add("warn", f"{g.id}: chỉ giữ {(g.end - g.exit_frames - last) / fps:.2f}s sau khi hiện đủ")
        # element (icon) không được đè chữ
        texts = [s for s in g.spans if s.style != "icon"]
        from . import neon
        def ink(sp):   # kích thước nét thật (không quầng sáng)
            if sp.style == "icon":
                return sp.size * 0.8, sp.size * 0.8
            if sp.style == "pill":
                h, w = neon.pill_sprite(sp.text, sp.size, sp.palette).shape[:2]
                return h * 0.6, w * 0.8
            m = neon._mask(sp.text, sp.neon_role, sp.size) if sp.style in ("neon", "outline") else None
            if m is None:
                return sp.size, sp.size * len(sp.text) * 0.5
            ys, xs = (m > 0.05).nonzero()
            return ys.max() - ys.min(), xs.max() - xs.min()
        for ic in (s for s in g.spans if s.style == "icon"):
            if not neon.icon_exists(ic.text):
                add("error", f"{g.id}: icon '{ic.text}' không có — dùng tên Uicons solid-rounded (vd heart, syringe, pills; xem assets/uicons/solid.css)")
            for t in texts:
                th, tw = ink(t)
                ih, iw = ink(ic)
                if abs(ic.dx - t.dx) < (tw + iw) / 2 and abs(ic.dy - t.dy) < (th + ih) / 2:
                    add("warn", f"{g.id}: element '{ic.text}' có thể đè chữ '{t.text}'")
    for layer in ("front_of_subject", "behind_subject"):
        gs = sorted([g for g in pl.text_groups if g.enabled and g.layer == layer and g.id not in R.MOVED_DOWN],
                    key=lambda g: g.start)
        for a, b in zip(gs, gs[1:]):
            if a.end > b.start:
                add("error", f"{a.id} chồng {b.id} cùng lớp {(a.end - b.start)} frame")
    for gid in sorted(R.MOVED_DOWN):
        add("info", f"{gid}: đầu sát mép trên, không đủ chỗ cho chữ sau đầu → app tự đưa xuống trước ngực (xem stills)")
    # 5) quy tắc nội dung chữ + Motion Graphics
    out.extend(text_rules(pl, c.project.words, fps))
    out.extend(gaze_rules(pl, c.project.words, c.path("work", "gaze.json"), fps))
    out.extend(point_rules(pl, c.path("work", "pointing.json"), fps))
    # 6) ảnh xem trước tại các điểm nhấn (xem bằng mắt trước khi render)
    if stills:
        frames = sorted({g.hit + 4 for g in pl.text_groups if g.enabled} |
                        {sc["start"] + 25 for m in pl.mg for sc in m["scenes"]})
        add("info", f"stills: {len(frames)} frame — dùng scripts xem nhanh")
    return out


_tok = lambda t: [w for w in re.sub(r"[^\w\s]", " ", t.lower()).split() if w]
LIST_MAIN = re.compile(r"^(ĐIỀU|LÝ DO|BƯỚC|CÁCH|MẸO|BÍ QUYẾT|SAI LẦM|LƯU Ý)\s+\d+$")
ONLY_NUM = re.compile(r"^[\d.,]+\s*(%|M2|M²|M|KM|TỶ|TRIỆU|NGHÌN|USD|ĐỒNG|NĂM|THÁNG|PHÚT)?$")
VISUAL = {"photo", "icon", "arrow", "circle", "checks"}


def _repeat(main: str, lead: str) -> bool:
    """chữ chính chép lại dòng dẫn: trùng nguyên cụm, hoặc ≥60% số từ của chữ chính đã có trong dòng dẫn
    (vd “hãy liên hệ với Tuấn Anh” + LIÊN HỆ TUẤN ANH — chen chữ “với” vẫn là lặp)"""
    m, l = _tok(main), _tok(lead)
    if not m:
        return False
    if any(l[i:i + len(m)] == m for i in range(len(l) - len(m) + 1)):
        return True
    return len(m) >= 2 and sum(w in l for w in m) / len(m) >= 0.6


def _said(words, pl, kw: str, t: int, fps: int, win: float = 4.0) -> bool:
    """từ khóa của ảnh có được nói trong ±win giây quanh lúc ảnh hiện không (cho phép nhiều lựa chọn “a|b”)"""
    near = []
    for w in words or []:
        f = T.src_to_tl(pl, w.source_start)
        if f is not None and abs(f - t) <= win * fps:
            near.append(w.text)
    txt = " ".join(_tok(" ".join(near)))
    return any(" ".join(_tok(k)) in txt for k in kw.split("|"))


def _pair_rules(where: str, main: str, lead: str | None, add):
    if lead and _repeat(main, lead):
        add("error", f"{where}: chữ chính “{main}” lặp lại chữ trong dòng dẫn “{lead}” — bỏ phần trùng hoặc đổi ý")
    if lead and LIST_MAIN.match(main.upper()):
        add("error", f"{where}: liệt kê “{main}” — bỏ dòng dẫn “{lead}”, chỉ để chữ chính")
    if ONLY_NUM.match(main.upper().strip()):
        add("warn", f"{where}: “{main}” chỉ có con số — phải đi cùng cụm đủ nghĩa (vd DIỆN TÍCH 30M², 9 MÁY LẠNH)")


def text_rules(pl, words, fps: int) -> list[tuple[str, str]]:
    from . import mg as M, neon
    out = []
    add = lambda sev, msg: out.append((sev, msg))
    shown = []   # (start, end, text) mọi chữ chính/chữ lớn đang hiện
    photos = []  # (t, file, nơi) — kiểm tra lặp ảnh
    for g in pl.text_groups:
        if not g.enabled:
            continue
        main = next((x for x in g.spans if x.motion == "pop"), None)
        lead = next((x for x in g.spans if x.motion == "words"), None)
        if main:
            _pair_rules(g.id, main.text, lead.text if lead else None, add)
            shown.append((g.start, g.end, main.text))
    for seg in pl.mg:
        for k, sc in enumerate(seg["scenes"]):
            where = f"{seg['id']}/cảnh {k + 1}"
            els = M.layout_scene(sc)["elements"]
            if not any(e["type"] in ("photo", "photos") for e in els):
                add("error", f"{where}: chưa có ảnh dự án / ảnh minh họa (icon chỉ là phụ, không đủ)")
            for e in els:
                if e["type"] == "icon" and not neon.icon_exists(e["name"]):
                    add("error", f"{where}: icon '{e['name']}' không có — dùng tên Uicons solid-rounded (vd heart, syringe, pills)")
                for it in (e["items"] if e["type"] == "photos" else [e] if e["type"] == "photo" else []):
                    photos.append((it["t"], it["file"], where))
                    if it.get("kw") and not _said(words, pl, it["kw"], it["t"], fps):
                        add("error", f"{where}: ảnh {it['file'].split('/')[-1]} gắn “{it['kw']}” nhưng quanh {T.tc(it['t'])} không nói tới — ảnh không khớp lời")
                    elif not it.get("kw"):
                        add("warn", f"{where}: ảnh {it['file'].split('/')[-1]} chưa gắn từ khóa (kw) để đối chiếu lời nói")
            ts = sorted(it["t"] for e in els if e["type"] == "photos" for it in e["items"])
            for a, b in zip(ts, ts[1:] + [sc["end"]]):
                if b - a < 1.8 * fps:
                    add("error", f"{where}: ảnh @ {T.tc(a)} chỉ hiện {(b - a) / fps:.1f}s (<1.8s) — chưa kịp nhìn, bớt ảnh hoặc giãn")
            if sc["end"] - sc["start"] < 2.5 * fps:
                add("warn", f"{where}: cảnh MG chỉ {(sc['end'] - sc['start']) / fps:.1f}s (<2.5s) — đổi câu quá nhanh, nên gộp")
            leads = [e["text"] for e in els if e["type"] == "words"]
            for e in els:
                if e["type"] == "big":
                    _pair_rules(where, e["text"], " ".join(leads) or None, add)
                    shown.append((sc["start"], sc["end"], e["text"]))
                elif e["type"] == "tag":
                    tw = M.tag(e["text"], e.get("tone", "gold"), e.get("size", 64)).shape[1] - 60
                    x0, x1 = e["x"] - tw / 2, e["x"] + tw / 2
                    if x0 < 70 or x1 > 1010:
                        add("error", f"{where}: thẻ “{e['text']}” ra ngoài vùng an toàn ({x0:.0f}–{x1:.0f}px)")
                elif e["type"] == "words" and any(len(c) == 0 for c in M.word_chunks(e)):
                    add("error", f"{where}: dòng dẫn không cắt được")
    photos.sort()
    from . import imgio
    for fl in sorted({p[1] for p in photos} | {v.file for v in pl.visuals if getattr(v, "file", None)}):
        if imgio.imread(fl) is None:
            add("error", f"ảnh {fl.split('/')[-1]} không đọc được (thiếu file / hỏng / không phải ảnh) — tải ảnh khác bằng tools img")
    for i, (t, fl, where) in enumerate(photos):
        prev = next((p for p in reversed(photos[:i]) if p[1] == fl and t - p[0] < 30 * fps), None)
        if prev:
            add("error", f"{where}: ảnh {fl.split('/')[-1]} lặp lại (đã dùng ở {prev[2]} cách {(t - prev[0]) / fps:.0f}s < 30s)")
    # số liệu được nói ra → phải có chữ chính chứa con số đó quanh thời điểm nói
    for i, w in enumerate(words or []):
        nums = re.findall(r"\d+", w.text)
        prev = _tok(words[i - 1].text) if i else []
        if not nums or prev[-1:] in (["thứ"], ["số"]):      # số thứ tự (thứ 2) thuộc quy tắc liệt kê
            continue
        t = T.src_to_tl(pl, w.source_start)
        if t is None:
            continue
        if not any(a - 30 <= t <= b + 15 and nums[0] in re.findall(r"\d+", txt) for a, b, txt in shown):
            add("warn", f"số “{w.text}” @ {T.tc(t)} chưa được làm nổi bật (chữ chính cả cụm, vd DIỆN TÍCH 30M²)")
    return out


def gaze_rules(pl, words, gaze_file, fps: int) -> list[tuple[str, str]]:
    """đoạn đang NÓI mà không nhìn máy ≥1s phải được MG / ảnh phủ kín.
    Có cúi nhìn điện thoại/kịch bản (down) → lỗi; chỉ quay đi (giới thiệu không gian) → cảnh báo để tự xem."""
    if not gaze_file.exists():
        return [("warn", "chưa dò hướng nhìn (work/gaze.json) — chạy python -m thagent.gaze <id>")]
    gaze = json.loads(gaze_file.read_text())
    from . import mg as M, neon
    M.chain(pl.mg)
    covers = [M.covered_range(m) for m in pl.mg] + [(v.start, v.end) for v in pl.visuals
                                                        if getattr(v, "enabled", True) and getattr(v, "fullscreen", True)]
    talk = [(w.source_start, w.source_end) for w in words or []]
    runs = []   # [đầu, cuối, số mẫu cúi]
    for g in gaze:
        if g.get("cam") or not g.get("face") or not any(a - 0.3 <= g["t"] <= b + 0.3 for a, b in talk):
            continue
        f = T.src_to_tl(pl, g["t"])
        if f is None or any(a <= f < b for a, b in covers):
            continue
        if runs and f - runs[-1][1] <= fps:
            runs[-1][1] = f + fps // 2; runs[-1][2] += g.get("down", False)
        else:
            runs.append([f, f + fps // 2, int(g.get("down", False))])
    out = []
    # lúc MG đang trượt vào/ra, video cũ còn lộ một phần → không được có cảnh cúi nhìn trong cửa sổ đó
    for m in pl.mg:
        wins = []
        if not m.get("chain_in"):
            wins.append(("vào", m["start"] - fps // 2, m["start"] + M.SLIDE_IN))
        if not m.get("chain_out"):
            wins.append(("ra", m["end"] - M.SLIDE_OUT, m["end"] + fps // 2))
        for name, a, b in wins:
            for g in gaze:
                f = T.src_to_tl(pl, g["t"])
                if f is not None and a <= f < b and g.get("down") and not any(x <= f < y for x, y in covers):
                    out.append(("error", f"{m['id']}: chuyển cảnh {name} @ {T.tc(f)} lộ cảnh cúi nhìn điện thoại — dời mốc MG"))
                    break
    for a, b, nd in runs:
        if b - a < fps:
            continue
        if nd >= 2:
            out.append(("error", f"cúi nhìn điện thoại/kịch bản {T.tc(a)}→{T.tc(b)} ({(b - a) / fps:.1f}s) chưa được MG/ảnh che — chỉ lấy tiếng"))
        else:
            out.append(("warn", f"quay đi, không nhìn máy {T.tc(a)}→{T.tc(b)} ({(b - a) / fps:.1f}s) — xem ảnh: giới thiệu không gian thì giữ, còn lại che MG"))
    return out


def point_rules(pl, point_file, fps: int) -> list[tuple[str, str]]:
    """nhân vật chỉ tay/giơ tay giới thiệu vật mà chưa có highlight (hoặc MG che) → cảnh báo để agent xem ảnh và đặt."""
    if not point_file.exists():
        return [("warn", "chưa dò cử chỉ chỉ tay (work/pointing.json) — chạy python -m thagent.pointing <id>")]
    from . import mg as M, neon
    M.chain(pl.mg)
    covers = [M.covered_range(m) for m in pl.mg]
    hls = [(e.start, e.end) for e in pl.fx if e.type == "highlight" and e.enabled]
    out = []
    for r in json.loads(point_file.read_text()):
        a, b = T.src_to_tl(pl, r["t0"]), T.src_to_tl(pl, r["t1"])
        if a is None or b is None or b - a < fps * 0.5:
            continue
        mid = (a + b) // 2
        if any(x <= mid < y for x, y in covers) or any(x < b and y > a for x, y in hls):
            continue
        out.append(("warn", f"chỉ tay {T.tc(a)}→{T.tc(b)} (“{r['said'][:40]}”) chưa làm nổi bật — xem ảnh, đặt fx highlight box=…"))
    return out


def main():
    res = check(sys.argv[1], "--stills" in sys.argv)
    for sev, msg in res:
        print(f"[{sev}] {msg}")
    errs = sum(1 for s, _ in res if s == "error")
    print(f"== {errs} lỗi, {sum(1 for s, _ in res if s == 'warn')} cảnh báo")
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
