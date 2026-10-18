"""Review Editor — bản dựng (edit.json): mạch review tham chiếu tới nguồn, không đụng file gốc.

{
 "category": "bds" | "san_pham",  "style": "tour" | "truc_tiep" | "tinh_te",  "intensity": "nhe" | "can_bang" | "nang_dong",
 "formats": ["9x16", "16x9"],  "fps": 30,  "subtitles": true,  "target_s": null,
 "music": {"src": "assets/…mp3", "gain_db": -20}            (tuỳ chọn; tự giảm khi có lời)
 "segments": [
   {"id": "S01", "src": "F05", "in": 12.30, "out": 18.70, "role": "talk" | "broll" | "action",
    "say": "ý đang nói", "why": "lý do chọn", "take": "G03/T2",           (nhóm take + take được chọn)
    "j": 0.0, "l": 0.0,                       J-cut: tiếng đoạn này vào sớm j giây; L-cut: tiếng đoạn TRƯỚC kéo dài l giây sang đoạn này
    "audio": "voice" | "nat" | "mute",  "nat_db": -14,
    "crop": {"9x16": {"cx": 0.5, "cy": 0.42, "zoom": 1.0, "fit": "crop" | "blur"}, "16x9": {…}},   (thiếu → tự tính theo mặt/giữa)
    "cutaways": [{"src": "F02", "in": 3.0, "at": 1.2, "dur": 2.5, "kind": "full" | "pip", "why": "nói đầu nối → cận đầu nối",
                  "crop": {…}, "nat_db": null}],
    "texts": [{"role": "info" | "emph", "text": "…", "sub": "dòng nhỏ", "at": 0.4, "dur": 3.0, "hl": "cụm tô màu"}]}
 ],
 "replace": {"Seacatch": "C-Cut"},  "fixes": [{"src": "F05", "t": 3.04, "to": "C-Cut"}],   (sửa chữ chép sai trên PHỤ ĐỀ)
 "missing": ["thiếu cảnh mặt tiền", …],  "notes": "…"
}
- in/out: giây trong file nguồn.  at: giây tính từ đầu đoạn (segment).  Phụ đề tự sinh từ lời của đoạn talk (subtitles=true).
"""
from __future__ import annotations

import json
import re

import numpy as np
from pathlib import Path

from .inventory import load as load_media

FORMATS = {"9x16": (1080, 1920), "16x9": (1920, 1080)}


def load(pdir) -> dict:
    from .niche import apply
    return apply(auto_zoom(json.loads((Path(pdir) / "review" / "edit.json").read_text(encoding="utf-8"))))


def auto_zoom(edit: dict) -> dict:
    """zoom in–out có chủ đích (cuốn mắt): tại khối stat / emph của đoạn chưa có reframe riêng → đẩy vào ×push (0,5s) lúc khối hiện,
    lùi ra khi khối tắt. Bật bằng "auto_zoom": true (hoặc số = hệ số, mặc định 1.12). Không áp cho đoạn bố cục nền mờ (app tự bỏ qua)."""
    z = edit.get("auto_zoom")
    if not z:
        return edit
    f = 1.12 if z is True else float(z)
    for s in edit["segments"]:
        if s.get("role", "talk") != "talk" or s.get("reframe"):
            continue
        keys = []
        for t in sorted(s.get("texts", []), key=lambda t: float(t["at"])):
            if t.get("role") not in ("stat", "emph"):
                continue
            a = max(float(t["at"]) - 0.1, 0.0)
            b = a + float(t.get("dur", 2.5))
            if keys and a < keys[-1]["at"] + 0.8:
                continue
            keys += [{"at": round(a, 3), "dur": 0.5, "to": f"push:{f}"}, {"at": round(b, 3), "dur": 0.6, "to": "base"}]
        if keys:
            s["reframe"] = {fmt: [dict(k) for k in keys] for fmt in edit.get("formats", ["9x16", "16x9"])}
            s["_auto_zoom"] = True
    return edit


def media(pdir, cache={}) -> dict:
    key = str(pdir)
    if key not in cache:
        inv = json.loads((Path(pdir) / "review" / "inventory.json").read_text(encoding="utf-8"))
        from .restart import load as _rs, patch_words
        cache[key] = {}
        for it in inv["media"]:
            m = _tight(load_media(pdir, it["id"]))
            rs = _rs(pdir, it["id"])
            if rs and m.get("words"):
                m["words"] = patch_words(m["words"], rs)      # nói hỏng rồi nói lại (restart.py): bỏ mẩu hỏng, vá lời nghe lại
                m["restarts"] = [r["cut"] for r in rs]
            cache[key][it["id"]] = m
    return cache[key]


def _tight(m: dict) -> dict:
    """siết mốc từ theo khoảng lặng THẬT của clip (cleancut._tighten của Talking Head): máy chép lời hay kéo 1 từ trùm qua chỗ ngập ngừng
    → điểm cắt/phụ đề lệch. Giữ mốc gốc ở start_asr/end_asr."""
    if not m.get("words") or m.get("_tight"):
        return m
    try:
        from ..cleancut import _tighten, silences
        from ..schema import TranscriptWord
        tw = [TranscriptWord(id=f"w{i}", text=w["text"], source_start=w["start"], source_end=w["end"], confidence=w.get("conf", 1.0))
              for i, w in enumerate(m["words"])]
        for w, t in zip(m["words"], _tighten(tw, silences(m["path"]))):
            if abs(t.source_start - w["start"]) > 1e-3 or abs(t.source_end - w["end"]) > 1e-3:
                w["start_asr"], w["end_asr"] = w["start"], w["end"]
                w["start"], w["end"] = round(t.source_start, 3), round(t.source_end, 3)
        m["_tight"] = True
    except Exception:
        pass
    try:
        _snap_energy(m)
    except Exception:
        pass
    return m


def _snap_energy(m: dict, quiet_s: float = 0.12):
    """mốc từ trùm qua khoảng LẶNG thật (đo năng lượng, nền ồn ngoài trời vẫn đúng) → dời đầu từ tới chỗ tiếng bắt đầu,
    đuôi từ về chỗ tiếng tắt. Vd ASR ghi “Và” 24,34s nhưng tiếng thật 24,85s (trước đó là lặng sau câu)."""
    import numpy as np
    from .audiocut import _env
    db, fl = _env(m["path"])
    if len(db) < 10:
        return
    sm = np.convolve(db, np.ones(5) / 5, mode="same")
    q = sm < fl + 4
    v = sm > fl + 6                 # tiếng nhỏ (“và” nói khẽ) vẫn tính là có tiếng
    n = len(sm)
    qn = int(quiet_s * 100)
    for w in m["words"]:
        a, b = int(w["start"] * 100), min(int(w["end"] * 100), n - 1)
        if b - a < 4:
            continue
        # từ MỞ ĐẦU bằng khoảng lặng ≥ quiet_s (lặng bắt đầu trong 0,1s đầu của mốc) → mốc ASR bắt đầu sớm
        k, best = a, None
        while k < b:
            if q[k]:
                j = k
                while j < n - 1 and q[j]:
                    j += 1
                if j - k >= qn and k <= a + 10:
                    best = (k, j)
                k = j + 1
            else:
                k += 1
        if best:
            j = best[1]
            while j < min(n - 3, b + 60) and not (v[j] and v[j + 1] and v[j + 2]):
                j += 1
            if j < n - 3 and v[j]:
                w.setdefault("start_asr", w["start"]); w.setdefault("end_asr", w["end"])
                w["start"] = round(j / 100 - 0.02, 3)
                w["end"] = round(max(w["end"], w["start"] + 0.12), 3)
                w["_snap"] = True
    ws = m["words"]
    snapped = [w.pop("_snap", False) for w in ws]
    for i in range(len(ws) - 2, -1, -1):          # hai từ cùng bị dời về một chỗ → từ trước không thuộc chỗ đó: giữ mốc gốc
        if snapped[i] and snapped[i + 1] and ws[i]["start"] >= ws[i + 1]["start"] - 0.05:
            ws[i]["start"], ws[i]["end"] = ws[i]["start_asr"], min(ws[i]["end_asr"], ws[i + 1]["start"])
        elif snapped[i] and ws[i]["end"] > ws[i + 1]["start"]:
            ws[i + 1]["start"] = ws[i]["end"]     # từ kế (mốc ASR) bắt đầu sau từ vừa dời


def layout(edit: dict) -> list[dict]:
    """vị trí từng đoạn trên timeline xuất (t0, t1)."""
    t, out = 0.0, []
    for s in edit["segments"]:
        d = float(s["out"]) - float(s["in"])
        out.append({**s, "t0": round(t, 4), "t1": round(t + d, 4), "dur": round(d, 4)})
        t += d
    return out


def duration(edit: dict) -> float:
    return sum(float(s["out"]) - float(s["in"]) for s in edit["segments"])


def keep_ratio(sw: int, sh: int, fmt: str) -> float:
    """phần diện tích nguồn còn lại khi crop kín khung (1 = vừa khít)."""
    tw, th = FORMATS[fmt]
    return min(sw / sh, tw / th) / max(sw / sh, tw / th)


def auto_crop(m: dict, a: float, b: float, fmt: str, role: str) -> dict:
    """crop mặc định: lệch tỷ lệ quá nhiều (dọc → ngang hoặc ngược lại, giữ < 50%) → bố cục chứa trọn footage (nền mờ cùng hình);
    đoạn có mặt → khung bám mặt (mặt ở 1/3 trên); không có → giữa khung. Không crop giữa cố định khi có mặt."""
    if keep_ratio(m["w"], m["h"], fmt) < 0.5:
        return {"cx": 0.5, "cy": 0.5, "zoom": 1.0, "fit": "blur"}
    faces = [s["face"] for s in m.get("samples", []) if a - 0.3 <= s["t"] <= b + 0.3 and s.get("face")]
    if faces and role != "broll":
        fx = sorted(f[0] for f in faces)[len(faces) // 2]
        fy = sorted(f[1] for f in faces)[len(faces) // 2]
        return {"cx": round(fx, 3), "cy": round(min(max(fy + (0.18 if fmt == "9x16" else 0.12), 0.0), 1.0), 3), "zoom": 1.0, "fit": "crop"}
    return {"cx": 0.5, "cy": 0.5, "zoom": 1.0, "fit": "crop"}


def crop_box(sw: int, sh: int, fmt: str, c: dict) -> tuple[int, int, int, int, float]:
    """(x, y, w, h, tỷ lệ giữ lại bề rộng nguồn) của vùng cắt trong khung nguồn."""
    tw, th = FORMATS[fmt]
    asp = tw / th
    z = max(float(c.get("zoom", 1.0)), 1.0)
    if sw / sh > asp:
        ch = sh / z; cw = ch * asp
    else:
        cw = sw / z; ch = cw / asp
    x = min(max(c.get("cx", 0.5) * sw - cw / 2, 0), sw - cw)
    y = min(max(c.get("cy", 0.5) * sh - ch / 2, 0), sh - ch)
    return int(x) // 2 * 2, int(y) // 2 * 2, int(cw) // 2 * 2, int(ch) // 2 * 2, cw / sw


def crop_for(seg: dict, m: dict, fmt: str, a=None, b=None, role=None) -> dict:
    c = (seg.get("crop") or {}).get(fmt)
    c = {"fit": "crop", "zoom": 1.0, **c} if c else \
        auto_crop(m, seg["in"] if a is None else a, seg["out"] if b is None else b, fmt, role or seg.get("role", "talk"))
    if seg.get("punch") and c.get("fit", "crop") == "crop":     # punch-in che điểm cắt giữa câu (Cắt sạch)
        c = {**c, "zoom": c.get("zoom", 1.0) * float(seg["punch"])}
    return c


def seg_at(edit: dict, t: float, group: str | None = None) -> dict | None:
    """đoạn (đã layout) chứa giây xuất t; nếu cho group thì chỉ trong cùng nhóm đoạn con."""
    for s in layout(edit):
        if s["t0"] - 1e-6 <= t < s["t1"] + 1e-6 and (group is None or s.get("group", s["id"]) == group):
            return s
    return None


def _fix(edit: dict, src: str, w: dict) -> dict:
    """sửa chữ chép sai trong phụ đề: "replace": {"Seacatch": "C-Cut"} (mọi nơi) hoặc
    "fixes": [{"src": "F05", "t": 3.04, "to": "C-Cut"}] (đúng một từ theo giây nguồn). Tiếng không đổi."""
    for f in edit.get("fixes", []):
        if f.get("src") == src and abs(float(f["t"]) - w["start"]) < 0.08:
            return {**w, "text": f["to"]}
    core = w["text"].strip(".,!?;:…")
    rep = edit.get("replace", {})
    if core in rep:
        return {**w, "text": w["text"].replace(core, rep[core])}
    return w


def words_out(edit: dict, pdir) -> list[dict]:
    """lời của các đoạn talk, đổi sang giây trên timeline xuất (theo J-cut)."""
    M = media(pdir)
    out = []
    for s in layout(edit):
        if s.get("role", "talk") != "talk" or s.get("audio", "voice") != "voice":
            continue
        m = M[s["src"]]
        a = float(s["in"]) - float(s.get("j", 0))
        b = float(s["out"])
        sib = [(float(x["in"]), float(x["out"])) for x in edit["segments"]
               if s.get("inner") and x.get("group") == s.get("group") and x["src"] == s["src"]]
        for w in m.get("words", []):
            if sib:
                # đoạn con của Cắt sạch: mốc ASR có thể lấn vào chỗ đã cắt (lặng thật) → giao chữ cho đoạn con trùng nhiều nhất,
                # chữ nằm trọn trong chỗ cắt → đoạn con kế sau; mốc kẹp vào trong đoạn con (không rơi chữ khỏi phụ đề)
                ov = [max(0.0, min(w["end"], y) - max(w["start"], x)) for x, y in sib]
                if max(ov) > 0:
                    mine = sib[ov.index(max(ov))] == (float(s["in"]), b)
                else:
                    nxt = [(x, y) for x, y in sib if x >= w["end"]]
                    prv = [(x, y) for x, y in sib if y <= w["start"]]
                    mine = bool(nxt and prv) and nxt[0] == (float(s["in"]), b)
                if not mine:
                    continue
                w = dict(w, start=min(max(w["start"], float(s["in"])), b), end=max(min(w["end"], b), float(s["in"])))
            elif not (w["start"] >= a - 1e-3 and w["end"] <= b + 0.05):
                continue
            w = _fix(edit, s["src"], w)
            if out and out[-1]["seg"] == s["id"] and re.fullmatch(r"[.,]\d+[.,]?", w["text"]) and re.search(r"\d$", out[-1]["text"]):
                out[-1] = {**out[-1], "text": out[-1]["text"] + w["text"],          # máy chép lời tách số: “6” “,7” → “6,7”; “350” “.000” → “350.000”
                           "t_end": round(s["t0"] + w["end"] - float(s["in"]), 3), "end": w["end"]}
                continue
            if not w["text"].strip():
                continue
            out.append({**w, "t": round(s["t0"] + w["start"] - float(s["in"]), 3), "t_end": round(s["t0"] + w["end"] - float(s["in"]), 3),
                        "seg": s["id"], "grp": s.get("group") or s["id"]})
    return out


def validate(pdir, edit: dict) -> list[tuple[str, str]]:
    """kiểm bản dựng trước khi render (không cần dựng)."""
    M = media(pdir)
    out = []
    ids = set()
    if not edit.get("segments"):
        return [("error", "edit.json chưa có đoạn nào")]
    for s in edit["segments"]:
        sid = s.get("id", "?")
        if sid in ids:
            out.append(("error", f"{sid}: trùng id đoạn"))
        ids.add(sid)
        m = M.get(s.get("src"))
        if not m:
            out.append(("error", f"{sid}: nguồn {s.get('src')} không có trong kiểm kê")); continue
        if not m.get("usable", True):
            out.append(("error", f"{sid}: {s['src']} không dùng được ({m.get('error') or 'trùng ' + str(m.get('duplicate_of'))})"))
        a, b = float(s["in"]), float(s["out"])
        if not (0 <= a < b <= m.get("duration", 0) + 0.01):
            out.append(("error", f"{sid}: {a}–{b}s nằm ngoài {s['src']} (dài {m.get('duration')}s)"))
        for x, y in m.get("black", []):
            if min(b, y) - max(a, x) > 0.2:
                out.append(("error", f"{sid}: dùng đoạn đen {x}–{y}s của {s['src']}"))
        if m.get("outro") and b > m["outro"][0] + 0.1:
            out.append(("error", f"{sid}: dùng vào đoạn outro/đứng hình cuối {m['outro'][0]}s của {s['src']}"))
        # cắt giữa từ → mất chữ / tiếng bật (điểm cắt bên trong câu do Cắt sạch: chỉ cắt trong khoảng lặng đo bằng sóng âm → bỏ qua)
        if s.get("role", "talk") == "talk" and not s.get("inner"):
            for w in m.get("words", []):
                for cut, name in ((a, "đầu"), (b, "cuối")):
                    if w["start"] + 0.04 < cut < w["end"] - 0.04:
                        out.append(("error", f"{sid}: điểm cắt {name} {cut:.2f}s rơi giữa từ “{w['text']}” ({w['start']}–{w['end']}s)"))
            if b - a < 0.6:
                out.append(("warn", f"{sid}: đoạn nói quá ngắn {b - a:.2f}s"))
        for c in s.get("cutaways", []):
            mc = M.get(c.get("src"))
            if not mc:
                out.append(("error", f"{sid}: cutaway nguồn {c.get('src')} không có")); continue
            if c["at"] < 0 or c["at"] + c["dur"] > b - a + 0.01:
                out.append(("error", f"{sid}: cutaway {c['src']} ({c['at']}+{c['dur']}s) vượt khỏi đoạn ({b - a:.2f}s)"))
            if float(c.get("in", 0)) + c["dur"] > mc.get("duration", 0) + 0.01:
                out.append(("error", f"{sid}: cutaway {c['src']} lấy quá thời lượng nguồn"))
            if mc.get("outro") and float(c.get("in", 0)) + c["dur"] > mc["outro"][0]:
                out.append(("error", f"{sid}: cutaway dùng đoạn outro của {c['src']}"))
            if c["dur"] < 1.0:
                out.append(("warn", f"{sid}: cutaway {c['src']} chỉ {c['dur']}s — người xem chưa kịp thấy"))
            if not c.get("why"):
                out.append(("warn", f"{sid}: cutaway {c['src']} chưa ghi lý do khớp lời"))
    # take lặp: cùng một câu nguồn dùng 2 lần
    seen = {}
    for s in edit["segments"]:
        if s.get("role", "talk") != "talk":
            continue
        for x in seen.get(s["src"], []):
            if min(x[1], s["out"]) - max(x[0], s["in"]) > 0.3:
                out.append(("error", f"{s['id']}: dùng lại đoạn {s['src']} {max(x[0], s['in']):.1f}–{min(x[1], s['out']):.1f}s đã có ở {x[2]}"))
        seen.setdefault(s["src"], []).append((s["in"], s["out"], s["id"]))
        if s.get("take") and str(s["take"]).split("/")[0] in [str(t.get("take", "")).split("/")[0] for t in edit["segments"]
                                                                if t is not s and t.get("take")]:
            out.append(("error", f"{s['id']}: nhóm take {str(s['take']).split('/')[0]} được dùng hơn 1 lần (lặp ý)"))
    # crop mất chủ thể
    for fmt in edit.get("formats", ["9x16"]):
        for s in layout(edit):
            m = M.get(s.get("src"))
            if not m or "w" not in m:
                continue
            c = crop_for(s, m, fmt)
            if c.get("fit", "crop") != "crop":
                continue
            x, y, w, h, keep = crop_box(m["w"], m["h"], fmt, c)
            faces = [f["face"] for f in m.get("samples", []) if s["in"] <= f["t"] <= s["out"] and f.get("face")]
            def inside(f):   # cả khung mặt (không chỉ tâm) phải nằm trong vùng cắt; phần mặt đã ra ngoài khung NGUỒN thì không tính lỗi crop
                fx0, fx1 = max((f[0] - f[2] / 2) * m["w"], 0), min((f[0] + f[2] / 2) * m["w"], m["w"])
                fy0, fy1 = max((f[1] - f[3] / 2) * m["h"], 0), min((f[1] + f[3] / 2) * m["h"], m["h"])
                return fx0 >= x - 2 and fx1 <= x + w + 2 and fy0 >= y - 2 and fy1 <= y + h + 2
            lost = [f for f in faces if not inside(f)]
            if faces and len(lost) > 0.2 * len(faces):
                out.append(("error", f"{s['id']} [{fmt}]: crop làm mất mặt người ở {len(lost)}/{len(faces)} mẫu — chỉnh crop.cx/cy hoặc fit=blur"))
            if keep < 0.4 and not faces and s.get("role") != "talk":
                out.append(("warn", f"{s['id']} [{fmt}]: crop chỉ giữ {keep:.0%} bề rộng nguồn — kiểm sản phẩm/chi tiết còn trong khung, "
                                    "hoặc dùng cảnh khác / fit=blur"))
    # chữ
    from ..v2m import vtext as VT
    for s in edit["segments"]:
        for t in s.get("texts", []):
            if t["at"] + t.get("dur", 2) > float(s["out"]) - float(s["in"]) + 0.01 and not s.get("inner"):
                out.append(("warn", f"{s['id']}: chữ “{str(t.get('text') or t.get('value', ''))[:24]}” kéo qua đoạn sau (sẽ bị cắt ở cuối đoạn)"))
            if not t.get("text"):
                continue
            need = max(1.2, len(t["text"]) / 14)
            if t.get("dur", 2) < need - 0.05:
                out.append(("warn", f"{s['id']}: chữ “{t['text'][:24]}” chỉ {t.get('dur', 2)}s (cần ≈ {need:.1f}s để đọc)"))
    last = layout(edit)[-1]
    for t in last.get("texts", []):
        if t.get("text") and last["dur"] - t["at"] < max(1.6, len(t["text"]) / 14):
            out.append(("error", f"câu kết “{t['text'][:24]}” không đủ thời gian đọc trước khi hết video"))
    # nhãn/vòng nhấn bám vật: phải có track phủ suốt thời gian hiện
    from pathlib import Path as _P
    for s_ in layout(edit):
        for t in s_.get("texts", []):
            if t.get("role") in ("label", "focus"):
                if not t.get("track"):
                    out.append(("error", f"{s_['id']}: {t['role']} “{t.get('text', '')[:20]}” thiếu track (bám vật bằng lệnh track trước)")); continue
                f = _P(pdir) / "review" / "tracks" / f"{t['track']}.json"
                if not f.exists():
                    out.append(("error", f"{s_['id']}: chưa có track “{t['track']}” — chạy lệnh track")); continue
                from .objects import box_at, load_track
                tr = load_track(pdir, t["track"])
                a0 = float(s_["in"]) + float(t["at"])
                d = float(t.get("dur", 2.5))
                hit = [box_at(tr, a0 + k * d / 10) is not None for k in range(11)]
                if sum(hit) < 9:
                    out.append(("error", f"{s_['id']}: track “{t['track']}” không phủ {a0:.1f}–{a0 + d:.1f}s nguồn (mất dấu/ngoài khoảng bám) — nhãn sẽ trôi sai vật"))
    # đoạn nhòe / chuyển động mạnh trong lúc dùng hình người nói (thao tác chuẩn bị lộ)
    for s_ in edit["segments"]:
        m = M.get(s_.get("src"))
        if not m or not m.get("sharp_track"):
            continue
        st = m["sharp_track"]
        med = float(np.median([x[1] for x in st])) if st else 0
        covered = [(c["at"], c["at"] + c["dur"]) for c in s_.get("cutaways", []) if c.get("kind", "full") == "full"]
        run = []
        for t_, sh, mo in st:
            loc = t_ - float(s_["in"])
            if not (float(s_["in"]) <= t_ <= float(s_["out"])) or any(a <= loc <= b for a, b in covered):
                run = []; continue
            if sh < 0.4 * med or mo > 0.12:
                run.append(t_)
                if len(run) == 3:
                    out.append(("warn", f"{s_['id']}: hình nhòe/chuyển động mạnh từ {run[0]:.1f}s ({s_['src']}) — cắt gọn thao tác chuẩn bị "
                                        "(giữ lời: dùng cutaway che, hoặc dời in/out ra ranh giới từ)"))
            else:
                run = []
    # nhịp cắt hình: mỗi cảnh (giữa hai lần cắt — đổi đoạn, vào/ra cutaway) phải đủ lâu để mắt bắt kịp; cắt dồn liên tục gây giật
    cuts = set()
    for s_ in layout(edit):
        if s_["t0"] > 0.01:
            cuts.add(round(s_["t0"], 2))
        for c in s_.get("cutaways", []):
            a_ = s_["t0"] + float(c["at"]); b_ = a_ + float(c["dur"])
            if a_ > 0.01: cuts.add(round(a_, 2))
            if b_ < s_["t1"] - 0.01: cuts.add(round(b_, 2))
    cuts = sorted(cuts)
    for x, y in zip(cuts, cuts[1:]):
        if y - x < 0.8:
            out.append(("error" if y - x < 0.3 else "warn",
                        f"cắt dồn: cảnh {x:.2f}–{y:.2f}s chỉ {y - x:.2f}s giữa hai lần cắt — kéo dài cutaway tới hết đoạn / bỏ cảnh chen giữa (mỗi cảnh ≥ 0,8–1,5s)"))
    # kết: hình phải giữ một nhịp sau khi lời + động tác xong
    lastseg = edit["segments"][-1]
    ml = M.get(lastseg.get("src"))
    if ml and lastseg.get("role", "talk") == "talk":
        ws = [w for w in ml.get("words", []) if float(lastseg["in"]) <= w["start"] < float(lastseg["out"])]
        if ws and float(lastseg["out"]) - ws[-1]["end"] < 0.4:
            out.append(("error", f"kết hụt: đoạn cuối {lastseg['id']} dừng {float(lastseg['out']) - ws[-1]['end']:.2f}s sau từ cuối “{ws[-1]['text']}” "
                                 "— giữ hình ≥ 0,4–0,8s sau khi ý nói/động tác xong"))
    # reframe tay: phóng quá giới hạn nét
    for s_ in edit["segments"]:
        for fmt_, keys in (s_.get("reframe") or {}).items():
            for k in keys:
                if isinstance(k.get("to"), dict) and float(k["to"].get("zoom", 1)) > 1.6:
                    out.append(("warn", f"{s_['id']} [{fmt_}]: reframe zoom {k['to']['zoom']} có thể vỡ nét — dùng 'face+<track>' (tự giới hạn) hoặc chú thích"))
    # điểm nối theo nhịp nói tự nhiên (audio gốc + transcript + năng lượng)
    from .audiocut import junctions
    for j in junctions(edit, pdir):
        out += j["flags"]
    # lời nhắc sản phẩm phải trùng lúc sản phẩm được nhấn (spotlight / viền / nhãn) — không thay bằng chữ
    terms = [x.lower() for x in edit.get("product_terms", [])]
    if terms:
        segs_ = layout(edit)
        spans = [(s_["t0"] + float(t["at"]), s_["t0"] + float(t["at"]) + float(t.get("dur", 2))) for s_ in segs_ for t in s_.get("texts", [])
                 if t.get("role") in ("spotlight", "focus", "label")]
        for w in words_out(edit, pdir):
            if any(x in w["text"].lower() for x in terms) and not any(a - 0.3 <= w["t"] <= b + 0.3 for a, b in spans):
                out.append(("warn", f"lời nhắc “{w['text']}” ở {w['t']:.1f}s nhưng sản phẩm không được nhấn (spotlight/viền/nhãn) lúc đó"))
    # reframe phải giữ trọn mặt + vật trong suốt khoảng giữ khung
    for s_ in layout(edit):
        m = M.get(s_.get("src"))
        for fmt_, keys in (s_.get("reframe") or {}).items():
            for i, k in enumerate(sorted(keys, key=lambda k: k["at"])):
                if not isinstance(k.get("to"), str) or k["to"] == "base":
                    continue
                end = sorted(keys, key=lambda k: k["at"])[i + 1]["at"] if i + 1 < len(keys) else s_["dur"]
                W_, H_ = FORMATS[fmt_]
                for tt in np.arange(k["at"] + k.get("dur", 0.6), end, 0.5):
                    c = crop_at(pdir, s_, m, fmt_, float(tt))
                    chk = []
                    if "face" in k["to"].split("+"):
                        f = _faces_at(m, float(s_["in"]) + float(tt), 0.3)
                        if f:
                            f = f[0]; chk.append(("mặt", [f[0] - f[2] / 2, f[1] - f[3] / 2, f[2], f[3]]))
                    for part in k["to"].split("+"):
                        if part not in ("face", ""):
                            from .objects import box_at, load_track
                            try:
                                b = box_at(load_track(pdir, part), float(s_["in"]) + float(tt))
                            except FileNotFoundError:
                                b = None
                            if b:
                                chk.append((part, b))
                    for name, b in chk:
                        ax, ay = src_to_out(m, fmt_, c, b[0], b[1]); bx, by = src_to_out(m, fmt_, c, b[0] + b[2], b[1] + b[3])
                        if ax < -8 or ay < -8 or bx > W_ + 8 or by > H_ + 8:
                            out.append(("error", f"{s_['id']} [{fmt_}]: reframe làm {name} ra ngoài khung ở {float(s_['in']) + tt:.1f}s nguồn"))
                            break
    # chữ nhấn trong lúc spotlight/sơ đồ đã thể hiện ý → lặp
    for s_ in layout(edit):
        busy = [(float(t["at"]), float(t["at"]) + float(t.get("dur", 2))) for t in s_.get("texts", []) if t.get("role") in ("spotlight", "diagram")]
        for t in s_.get("texts", []):
            if t.get("role") == "emph" and any(a < float(t["at"]) + float(t.get("dur", 2)) and float(t["at"]) < b for a, b in busy):
                out.append(("warn", f"{s_['id']}: chữ nhấn “{t['text'][:20]}” trùng lúc spotlight/sơ đồ — hình đã thể hiện ý, bớt chữ"))
    # số liệu then chốt phải được làm nổi bật (không chỉ trong phụ đề)
    from .keyinfo import coverage
    out += coverage(edit, pdir)
    from .niche import apply, check as niche_check
    out += niche_check(apply(edit), pdir)        # quy tắc riêng lĩnh vực (mỹ phẩm: hứa hẹn công dụng)
    tgt = edit.get("target_s")
    if tgt and abs(duration(edit) - tgt) > max(5, 0.15 * tgt):
        out.append(("warn", f"thời lượng {duration(edit):.1f}s lệch yêu cầu {tgt}s"))
    return out


# ---------------- reframe động + đổi toạ độ nguồn → khung xuất ----------------
ZMAX_UPSCALE = 1.45      # không phóng quá 1,45× so với độ phân giải cần (giữ nét); vượt → giữ khung, dùng chú thích


def _smooth01(u: float) -> float:
    u = min(max(u, 0.0), 1.0)
    return u * u * (3 - 2 * u)


def _faces_at(m: dict, t: float, win: float = 0.6) -> list:
    return [s["face"] for s in m.get("samples", []) if abs(s["t"] - t) <= win and s.get("face")]


def focus_crop(pdir, m: dict, fmt: str, src_t: float, spec: str, until: float | None = None, sub_room: bool = True) -> dict:
    """crop (cx, cy, zoom) ôm vùng cần thấy SUỐT khoảng giữ khung [src_t, until]: "face", "<track>", "face+<track>"
    — hợp các hộp lấy mẫu mỗi 0,5s (vật/mặt di chuyển vẫn nằm trong khung), chừa lề 14%, giới hạn phóng để giữ nét."""
    from .objects import box_at, load_track
    boxes = []
    ts = [src_t] if until is None or until <= src_t else [src_t + k * 0.5 for k in range(int((until - src_t) / 0.5) + 1)] + [until]
    for part in spec.split("+"):
        if part == "face":
            for tt in ts:
                fs = _faces_at(m, tt, 0.3)
                if fs:
                    f = sorted(fs, key=lambda f: abs(f[0] - 0.5))[0]
                    boxes.append([f[0] - f[2] / 2, f[1] - f[3] * 0.65, f[2], f[3] * 1.25])   # chừa tóc/cằm
        elif part:
            tr = load_track(pdir, part)
            for tt in ts:
                b = box_at(tr, min(max(tt, tr["t0"]), tr["t1"]))    # ngoài khoảng bám → lấy vị trí gần nhất đã bám
                if b:
                    boxes.append(b)
    if not boxes:
        return {"cx": 0.5, "cy": 0.5, "zoom": 1.0, "fit": "crop"}
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
    pw, ph = (x1 - x0) * 0.14 + 0.02, (y1 - y0) * 0.14 + 0.02
    x0, y0, x1, y1 = x0 - pw, y0 - ph, x1 + pw, y1 + ph
    tw, th = FORMATS[fmt]
    asp = tw / th
    sw, sh = m["w"], m["h"]
    need_w = max((x1 - x0) * sw, (y1 - y0) * sh * asp)          # bề rộng vùng cắt (px nguồn) đủ chứa hộp
    full_w = min(sw, sh * asp)
    zoom = max(1.0, full_w / need_w)
    zoom = min(zoom, max(1.0, full_w / (tw / ZMAX_UPSCALE)))     # giới hạn phóng (giữ nét)
    cy = (y0 + y1) / 2
    if sub_room:   # chừa dải phụ đề phía dưới: GIỮ mức phóng, dịch khung để đáy chủ thể nằm ở ~72% khung (trần thừa ra ngoài mép trên)
        ch = (full_w / zoom) / asp / sh                              # chiều cao vùng cắt (chuẩn hoá nguồn)
        if (y1 - y0) <= 0.69 * ch:                                    # đủ chỗ → dịch khung; không đủ thì giữ mức phóng (phụ đề sẽ chọn dải trên)
            cy = y1 - 0.72 * ch + ch / 2
    return {"cx": round((x0 + x1) / 2, 4), "cy": round(cy, 4), "zoom": round(zoom, 3), "fit": "crop"}


def crop_at(pdir, s: dict, m: dict, fmt: str, local_t: float, base: dict | None = None) -> dict:
    """crop của đoạn tại giây cục bộ (từ đầu đoạn) — base, rồi lần lượt các khoá reframe (chuyển mượt trong dur)."""
    base = base or crop_for(s, m, fmt)
    keys = sorted(((s.get("reframe") or {}).get(fmt) or []), key=lambda k: k["at"])
    cur = dict(base)
    for i, k in enumerate(keys):
        if local_t < k["at"]:
            break
        hold_end = keys[i + 1]["at"] if i + 1 < len(keys) else float(s["out"]) - float(s["in"])
        if k["to"] == "base":
            tgt = base
        elif isinstance(k["to"], str) and k["to"].startswith("push"):           # đẩy vào quanh khung gốc (giữ tâm), giới hạn nét
            f_ = float(k["to"].split(":")[1]) if ":" in k["to"] else 1.12
            tw = FORMATS[fmt][0]
            zmax = max(1.0, min(m["w"], m["h"] * tw / FORMATS[fmt][1]) / (tw / ZMAX_UPSCALE))
            tgt = {**base, "zoom": min(base.get("zoom", 1.0) * f_, zmax)}
        elif isinstance(k["to"], str):
            tgt = focus_crop(pdir, m, fmt, float(s["in"]) + k["at"], k["to"], float(s["in"]) + hold_end)
        else:
            tgt = {"fit": "crop", "zoom": 1.0, **k["to"]}
        u = _smooth01((local_t - k["at"]) / max(k.get("dur", 0.6), 1e-3))
        cur = {"cx": cur["cx"] + (tgt["cx"] - cur["cx"]) * u, "cy": cur["cy"] + (tgt["cy"] - cur["cy"]) * u,
               "zoom": cur.get("zoom", 1) * (tgt.get("zoom", 1) / max(cur.get("zoom", 1), 1e-6)) ** u, "fit": cur.get("fit", "crop")}
    return cur


def src_to_out(m: dict, fmt: str, c: dict, x: float, y: float) -> tuple[float, float]:
    """toạ độ chuẩn hoá nguồn → px khung xuất, theo crop c (crop thường hoặc bố cục nền mờ)."""
    W, H = FORMATS[fmt]
    if c.get("fit") == "blur":
        s = min(W / m["w"], H / m["h"])
        return (W - m["w"] * s) / 2 + x * m["w"] * s, (H - m["h"] * s) / 2 + y * m["h"] * s
    bx, by, bw, bh, _ = crop_box(m["w"], m["h"], fmt, c)
    return (x * m["w"] - bx) * W / bw, (y * m["h"] - by) * H / bh


def face_out(pdir, edit: dict, fmt: str, t: float):
    """khung mặt + tóc (px khung xuất) tại giây xuất t; None khi đang cutaway/đồ họa phủ hoặc không thấy mặt."""
    M = media(pdir)
    for s in layout(edit):
        if s["t0"] <= t < s["t1"] + 1e-6:
            loc = t - s["t0"]
            if any(c["at"] <= loc < c["at"] + c["dur"] and c.get("kind", "full") == "full" for c in s.get("cutaways", [])):
                return None
            m = M[s["src"]]
            fs = _faces_at(m, float(s["in"]) + loc, 0.3)
            if not fs:
                return None
            f = max(fs, key=lambda f: f[2] * f[3])
            c = crop_at(pdir, s, m, fmt, loc)
            x0, y0 = src_to_out(m, fmt, c, f[0] - f[2] / 2, f[1] - f[3] * 0.85)      # chừa tóc
            x1, y1 = src_to_out(m, fmt, c, f[0] + f[2] / 2, f[1] + f[3] / 2)
            return (x0, y0, x1, y1)
    return None
