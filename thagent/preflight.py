"""Kiểm tra TRƯỚC khi render (vài giây, không encode video). Render chỉ là bước cuối.

python -m thagent.preflight <project> [--stills]
Trả về danh sách lỗi (error) / cảnh báo (warn); error > 0 → không render.
"""
from __future__ import annotations

import json
from pathlib import Path
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


def trim_tail_gaze(c) -> str | None:
    """Đuôi video: người cúi nhìn điện thoại / quay đi (vd lúc bấm dừng quay) và khúc đó IM LẶNG → app tự cắt thay vì bắt che MG
    (không có lời để che). Còn tiếng nói trong khúc đó → giữ, quy tắc nhìn máy vẫn áp (Claude kéo MG cuối phủ tới hết video)."""
    pl = c.project.plan
    gf = c.path("work", "gaze.json")
    if pl is None or not gf.exists():
        return None
    ks = T.kept(pl)
    if not ks:
        return None
    last = ks[-1]
    gz = sorted((g for g in json.loads(gf.read_text()) if last.source_in <= g["t"] <= last.source_out + 0.01), key=lambda g: g["t"])
    t0 = None
    for g in reversed(gz):                      # chuỗi mẫu cuối liên tiếp không nhìn máy
        if g.get("cam"):
            break
        t0 = g["t"]
    if t0 is None or last.source_out - t0 < 0.4 or last.source_out - t0 > 3.0:
        return None
    try:                                         # khúc nhìn đi phải IM LẶNG (nghe tiếng thật, không tin mốc chữ — câu ảo giác Whisper)
        from .cleancut import silences
        sil = silences(c.project.proxy)
    except Exception:
        return None
    span = last.source_out - t0
    quiet = sum(max(0.0, min(b, last.source_out) - max(a, t0)) for a, b in sil)
    if quiet < 0.8 * span:
        return None                              # vẫn còn nói trong khúc nhìn đi → giữ, quy tắc nhìn máy áp (MG che)
    real = [w for w in c.project.words or [] if w.confidence > 0 and last.source_in <= w.source_start < t0]
    new = max(t0 - 0.1, max((w.source_end for w in real), default=last.source_in) + 0.15)
    hush = next((x for x, y in sil if x <= t0 + 0.1 < y), None)     # giọng dứt lúc khoảng lặng bắt đầu → cắt sau đó, không xén âm cuối
    if hush is not None:
        new = max(new, hush + 0.1)
    if new <= last.source_in + 0.3 or new >= last.source_out - 0.05:
        return None
    old = last.source_out
    last.source_out = round(new, 3)
    T.build_mapping(pl)
    D = pl.duration_frames
    for g in pl.text_groups:                     # phần tử nằm quá đuôi mới → rút về
        if g.start >= D - 3:
            g.enabled = False
        elif g.end > D:
            g.end = D
    for e in [*pl.visuals, *pl.fx]:
        if e.start >= D - 3:
            e.enabled = False
        elif e.end > D:
            e.end = D
    for sd in pl.sounds:
        if sd.hit >= D:
            sd.enabled = False
    for m in pl.mg:
        if m["end"] > D:
            m["end"] = D
            for sc in m.get("scenes", []):
                sc["end"] = min(sc["end"], D)
    c.save()
    return f"app tự cắt đuôi {old - new:.1f}s cuối (nguồn {new:.2f}→{old:.2f}s): người nhìn đi chỗ khác, không còn lời — không cần MG che"


def check(pid: str, stills: bool = False) -> list[tuple[str, str]]:
    c = P.Ctx(pid)
    trimmed = trim_tail_gaze(c)
    pl = c.project.plan
    T.build_mapping(pl)
    R.use_frame(pl.width, pl.height)
    fps, out = pl.fps, []
    add = lambda sev, msg: out.append((sev, msg))
    if trimmed:
        add("info", trimmed)

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
    segs = sorted([(m["start"], m["end"]) for m in pl.mg] +             # callout (chữ + icon / ảnh) cũng là graphic
                  [(int(x["start"]), int(x["end"])) for x in getattr(pl, "callouts", None) or [] if x.get("enabled", True)] +
                  [(int(x["start"]), int(x["end"])) for x in getattr(pl, "mg2", None) or [] if x.get("enabled", True)])
    prev = 0
    for a, b in segs + [(pl.duration_frames, pl.duration_frames)]:
        if (a - prev) / fps > GAP_RULE_S:
            add("warn", f"nói liên tục {(a - prev) / fps:.1f}s ({T.tc(prev)}→{T.tc(a)}) > {GAP_RULE_S}s, cần thêm graphic")
        prev = b
    # 4) bố cục + thời gian đọc + chồng nhóm cùng lớp
    anchors = json.loads(c.path("work", "anchors.json").read_text())
    from . import callouts as _CO
    _CO.attach_objects(anchors, c.path("work", "gaze.json"), pl.fps)
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
    # 4a) callout / chữ + icon / ảnh kẹp: không chạm mặt, trong khung an toàn; chữ nổi bật dày ~4s/lần (≤5s)
    from . import callouts as CO
    out.extend(CO.check(pl, atl, pl.width, pl.height, fps, open_close(pl, c.project.words, fps)))
    out.extend(CO.density(pl, fps))
    from . import stage as STG
    out.extend(STG.check(pl, fps))
    from . import mg2 as MG2                     # Motion Graphics thế hệ 2: mẫu / nền / ảnh / nhịp ~10s (trừ đoạn trình diễn vật)
    out.extend(MG2.check(pl, fps, open_close(pl, c.project.words, fps), demo_runs(pl, c.path("work", "gaze.json"), fps)))
    # 4b) không cắt khi người còn đang nói ở cuối video
    try:
        from .cleancut import silences
        last = max(T.kept(pl), key=lambda s: s.order)
        dur = (P.probe_source(c.project.proxy).duration if c.project.proxy else 0) or 0
        t = last.source_out
        if dur - t > 0.3 and not any(a <= t + 0.05 and b > t for a, b in silences(c.project.proxy)):
            add("error", f"cuối video cắt ở {t:.2f}s (nguồn) khi người còn đang nói — kéo đoạn cuối tới lúc giọng dứt hẳn")
    except Exception as e:
        add("info", f"không kiểm được đuôi video: {e}")
    # 4c) chữ trên màn hình lấy từ câu ảo giác của Whisper (tên kênh bịa)
    blob = json.dumps(pl.model_dump(include={"text_groups", "mg", "fx", "hf"}), ensure_ascii=False).lower()
    for name in ("ghiền mì gõ", "la la school", "lalaschool"):
        if name in blob:
            add("error", f"chữ trên màn hình có “{name}” — tên kênh do bộ chép lời tự bịa (câu ảo giác Whisper), không có trong clip → bỏ/đổi câu chung")
    # 5) quy tắc nội dung chữ + Motion Graphics
    out.extend(text_rules(pl, c.project.words, fps))
    out.extend(gaze_rules(pl, c.project.words, c.path("work", "gaze.json"), fps))
    out.extend(entity_rules(pl, c.project.words, c.dir, fps))
    out.extend(open_close_rules(pl, c.project.words, fps))
    out.extend(point_rules(pl, c.path("work", "pointing.json"), fps))
    # 5b) lớp HyperFrames (công cụ dựng chung): spec hợp lệ, công cụ sẵn sàng (không có → bị chặn, báo rõ)
    from .th_hf import check as hf_check
    out += hf_check(pl)
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
    from . import fonts as FT
    if FT.current() in FT.NOSPACE:                 # Trung/Nhật/Thái: so chuỗi liền, bỏ cách chữ
        return any("".join(_tok(k)) in txt.replace(" ", "") for k in kw.split("|"))
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
    for co in getattr(pl, "callouts", None) or []:            # chữ trong callout cũng là chữ nổi bật
        if co.get("enabled", True):
            txt = " ".join(str(v) for k, v in co.items() if k in ("text", "sub", "lead", "a", "b", "label", "title", "bad", "good"))
            txt += " ".join(str(it.get("text", "")) + " " + str(it.get("value", "")) for it in co.get("items") or [])
            shown.append((int(co["start"]), int(co["end"]), txt))
    for fl in sorted({p[1] for p in photos} | {v.file for v in pl.visuals if getattr(v, "file", None)}):
        if imgio.imread(fl) is None:
            add("error", f"ảnh {fl.split('/')[-1]} không đọc được (thiếu file / hỏng / không phải ảnh) — tải ảnh khác bằng tools img")
        elif fl.split("/")[-1].startswith("c_") and _has_face(fl):
            add("error", f"ảnh {fl.split('/')[-1]}: khung cắt từ clip có mặt người nói — minh hoạ phải là cận cảnh VẬT; đoạn người đang cầm/"
                         "trình diễn vật thì giữ hình gốc + callout, không đưa vào MG")
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


def _has_face(path: str) -> bool:
    """ảnh có mặt người rõ (≥ 3% bề ngang) — dò bằng MediaPipe."""
    try:
        import cv2
        import mediapipe as mp
        from . import imgio
        im = imgio.imread(path)
        with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.6) as fd:
            det = fd.process(cv2.cvtColor(im, cv2.COLOR_BGR2RGB)).detections or []
        return any(d.location_data.relative_bounding_box.width > 0.03 for d in det)
    except Exception:
        return False


def demo_runs(pl, gaze_file, fps: int) -> list[tuple[int, int]]:
    """đoạn TRÌNH DIỄN vật (timeline) từ gaze.json + gaze_override.json."""
    if not Path(gaze_file).exists():
        return []
    from .clips import load_gaze
    runs = []
    for g in load_gaze(gaze_file):
        if not g.get("demo"):
            continue
        f = T.src_to_tl(pl, g["t"])
        if f is None:
            continue
        if runs and f - runs[-1][1] <= fps:
            runs[-1][1] = f + fps // 2
        else:
            runs.append([f, f + fps // 2])
    return [tuple(r) for r in runs]


def gaze_rules(pl, words, gaze_file, fps: int) -> list[tuple[str, str]]:
    """đoạn đang NÓI mà không nhìn máy ≥1s phải được MG / ảnh phủ kín.
    Có cúi nhìn điện thoại/kịch bản (down) → lỗi; chỉ quay đi (giới thiệu không gian) → cảnh báo để tự xem."""
    if not gaze_file.exists():
        return [("warn", "chưa dò hướng nhìn (work/gaze.json) — chạy python -m thagent.gaze <id>")]
    from .clips import load_gaze
    gaze = load_gaze(gaze_file)
    from . import mg as M, neon
    M.chain(pl.mg)
    from . import mg2 as MG2
    covers = [M.covered_range(m) for m in pl.mg] + [(v.start, v.end) for v in pl.visuals
                                                        if getattr(v, "enabled", True) and getattr(v, "fullscreen", True)] + MG2.covers(pl)
    talk = [(w.source_start, w.source_end) for w in words or []]
    runs = []   # [đầu, cuối, số mẫu cúi]
    demo = []    # [đầu, cuối] đoạn trình diễn vật (timeline)
    for g in gaze:
        if g.get("demo"):
            f = T.src_to_tl(pl, g["t"])
            if f is not None:
                if demo and f - demo[-1][1] <= fps:
                    demo[-1][1] = f + fps // 2
                else:
                    demo.append([f, f + fps // 2])
            continue
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
    for a, b in demo:            # đang trình diễn vật (cúi xem sách, cầm sản phẩm) → giữ hình, không che MG
        if b - a < int(1.5 * fps):
            continue
        for m in list(pl.mg) + [{"id": "mg2 " + x["id"], "start": x["start"], "end": x["end"]} for x in pl.mg2
                                 if x.get("enabled", True) and MG2.full(x)]:
            ov = min(b, m["end"]) - max(a, m["start"])
            if ov > fps:
                out.append(("error", f"{m['id']}: MG che {ov / fps:.1f}s đoạn đang TRÌNH DIỄN vật {T.tc(a)}→{T.tc(b)} (tay cầm vật trong "
                                     "khung) — giữ hình nhân vật, dùng chữ nổi bật / callout (pointer, arrow_label…); không phải trình "
                                     "diễn (đọc kịch bản/điện thoại) → ghi work/gaze_override.json kind \"away\""))
                break
    h, e = open_close(pl, words, fps)
    for a, b, nd in runs:
        if b - a < fps:
            continue
        if a < h or b > e:
            out.append(("warn", f"không nhìn máy {T.tc(a)}→{T.tc(b)} nằm trong đoạn mở đầu/kết — giữ hình nhân vật (không che MG); "
                                "nếu cúi đọc kịch bản thì chọn take/câu khác cho hook/kết hoặc cắt bỏ khúc đó"))
            continue
        if nd >= 2:
            out.append(("error", f"cúi nhìn điện thoại/kịch bản {T.tc(a)}→{T.tc(b)} ({(b - a) / fps:.1f}s) chưa được MG/ảnh che — chỉ lấy tiếng"))
        else:
            out.append(("warn", f"quay đi, không nhìn máy {T.tc(a)}→{T.tc(b)} ({(b - a) / fps:.1f}s) — xem ảnh: giới thiệu không gian thì giữ, còn lại che MG"))
    return out


def open_close(pl, words, fps: int) -> tuple[int, int]:
    """(cuối đoạn mở đầu, đầu đoạn kết) theo frame timeline. Mở đầu = câu nói đầu (2–6s). Kết = khoảng CTA 5s cuối
    (câu cuối bắt đầu sớm hơn chút thì tính từ đầu câu, tối đa 6s) — không cắt đôi câu CTA giữa MG và hình người."""
    D = pl.duration_frames
    tl = sorted((f, T.src_to_tl(pl, w.source_end) or f, w.text) for w in words or [] if (f := T.src_to_tl(pl, w.source_start)) is not None)
    if not tl:
        return min(D, 3 * fps), max(0, D - 3 * fps)
    lo, hi = 2 * fps, 6 * fps

    def sent_end(i0, step):                       # đi theo câu: dừng ở dấu kết câu hoặc khoảng ngừng > 0.5s
        i = i0
        while 0 <= i + step < len(tl):
            a, b = (tl[i], tl[i + step]) if step > 0 else (tl[i + step], tl[i])
            if a[2].rstrip()[-1:] in ".!?" or b[0] - a[1] > fps // 2:
                break
            i += step
        return i
    h = tl[sent_end(0, 1)][1]
    e = tl[sent_end(len(tl) - 1, -1)][0]
    h = min(max(h, tl[0][0] + lo), tl[0][0] + hi, D)
    e = max(min(e, D - 5 * fps), D - hi, 0)
    return int(h), int(e)


def open_close_rules(pl, words, fps: int) -> list[tuple[str, str]]:
    """Talking Head: đoạn mở đầu (hook) và đoạn kết LUÔN là hình nhân vật + chữ — không Motion Graphics / b-roll toàn khung."""
    from . import mg as M
    h, e = open_close(pl, words, fps)
    out = []
    M.chain(pl.mg)
    from . import mg2 as MG2
    covers = [(m["id"], *M.covered_range(m)) for m in pl.mg] + [(v.id, v.start, v.end) for v in pl.visuals if v.enabled] + \
             [("mg2 " + x["id"], int(x["start"]), int(x["end"])) for x in pl.mg2 if x.get("enabled", True) and MG2.full(x)]   # MG, ảnh, b-roll
    for cid, a, b in covers:
        if a < h:
            out.append(("error", f"{cid} ({T.tc(a)}→{T.tc(b)}) che đoạn mở đầu (hook, tới {T.tc(h)}) — hook chỉ có hình nhân vật + chữ hook (không MG/ảnh), "
                                 f"dời MG bắt đầu từ {T.tc(h)} trở đi"))
        if b > e:
            out.append(("error", f"{cid} ({T.tc(a)}→{T.tc(b)}) che đoạn kết (từ {T.tc(e)}) — đoạn kết (CTA ~5s cuối) chỉ có hình nhân vật + chữ CTA nổi bật (không MG/ảnh), "
                                 f"cho MG kết thúc trước {T.tc(e)}"))
    spans = [(g.start, g.end) for g in pl.text_groups if g.enabled] + \
            [(int(it["start"]), int(it["end"])) for it in (getattr(pl, "hf", None) or [])        # chữ dựng bằng HyperFrames cũng tính
             if any(L.get("type") == "text" for L in (it.get("spec") or {}).get("layers", []))] + \
            [(int(co["start"]), int(co["end"])) for co in (getattr(pl, "callouts", None) or [])       # callout chữ cũng tính
             if co.get("enabled", True) and not co.get("image") and not co.get("images")]
    if not any(a <= fps and b > a for a, b in spans):
        out.append(("error", f"đoạn mở đầu chưa có chữ hook trong 1s đầu — thêm tiêu đề/con số hook trên hình nhân vật (tới {T.tc(h)})"))
    if not any(b > e and a < pl.duration_frames for a, b in spans):
        out.append(("error", f"đoạn kết ({T.tc(e)}→hết) chưa có chữ kết — thêm chữ kết/CTA trên hình nhân vật"))
    return out


def entity_rules(pl, words, pdir, fps: int) -> list[tuple[str, str]]:
    """nói tên dự án/địa danh/thương hiệu trong cảnh MG có ảnh → phải có ảnh THẬT của đúng chủ thể (w_*) — thagent/entities.py"""
    from . import entities as E, mg as M
    ws = []
    for w in words or []:
        f = T.src_to_tl(pl, w.source_start)
        if f is not None:
            ws.append((w.text, f / fps))
    scenes = []
    for seg in pl.mg:
        for k, sc in enumerate(seg["scenes"]):
            ims = []
            for e in M.layout_scene(sc)["elements"]:
                for it in (e["items"] if e["type"] == "photos" else [e] if e["type"] == "photo" else []):
                    ims.append({"file": Path(it["file"]).name, "label": it.get("label", ""), "real": Path(it["file"]).name.startswith(("w_", "c_"))})
            txt = " · ".join(str(e.get("text", "")) for e in M.layout_scene(sc)["elements"] if e["type"] in ("big", "words", "tag") and e.get("text"))
            scenes.append({"id": f"{seg['id']}/cảnh {k + 1}", "t0": sc["start"] / fps, "t1": sc["end"] / fps, "images": ims, "text": txt})
    for co in getattr(pl, "callouts", None) or []:               # callout kẹp ảnh: cùng luật đúng vật như cảnh MG
        if not co.get("enabled", True):
            continue
        fs = [co.get(k) for k in ("image", "a_image", "b_image") if co.get(k)] + list(co.get("images") or [])
        if fs:
            ims = [{"file": Path(f).name, "label": "", "real": Path(f).name.startswith(("w_", "c_"))} for f in fs]
            txt = " · ".join(str(co.get(k)) for k in ("text", "lead", "label", "title", "script", "a_label", "b_label") if co.get(k))
            scenes.append({"id": f"callout {co.get('id')}", "t0": co["start"] / fps, "t1": co["end"] / fps, "images": ims, "text": txt})
    for m in getattr(pl, "mg2", None) or []:                     # cảnh MG2 có ảnh: cùng luật đúng vật
        if m.get("enabled", True) and m.get("images"):
            ims = [{"file": Path(i["src"]).name, "label": i.get("label", ""), "real": Path(i["src"]).name.startswith(("w_", "c_"))} for i in m["images"]]
            scenes.append({"id": f"mg2 {m['id']}", "t0": m["start"] / fps, "t1": m["end"] / fps, "images": ims,
                           "text": " · ".join(str(m.get(k)) for k in ("title", "text") if m.get(k))})
    return E.check(pdir, ws, scenes, lambda im: im["real"])


def point_rules(pl, point_file, fps: int) -> list[tuple[str, str]]:
    """cử chỉ tay chưa highlight → chỉ GHI CHÚ (info): khoanh vật CHỈ khi người thật sự chỉ vào một vật nhìn thấy rõ.
    Giơ tay/khua tay khi nói KHÔNG phải chỉ vật → bỏ qua; mặc định không khoanh."""
    if not point_file.exists():
        return []
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
        out.append(("info", f"cử chỉ tay {T.tc(a)}→{T.tc(b)} (“{r['said'][:40]}”): chỉ khoanh nếu xem ảnh thấy người CHỈ vào một vật "
                            "nhìn thấy rõ và lời nói gọi đúng vật đó (nhãn = tên vật); giơ tay khi nói → bỏ qua"))
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
