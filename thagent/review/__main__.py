"""Lệnh Review Editor.

  python -m thagent.review inventory <dự-án> <file|thư-mục…> [--ref <file…>]   kiểm kê + phân tích (lưu đệm theo file)
  python -m thagent.review media     <dự-án> [ID]          tóm tắt tư liệu / chi tiết 1 file (cảnh, câu nói, từ cần soát)
  python -m thagent.review words     <dự-án> <ID> [t0 t1]   lời từng từ + giây của 1 file
  python -m thagent.review takes     <dự-án>                nhóm các lần nói lại cùng ý + điểm từng take
  python -m thagent.review frames    <dự-án> <ID> t1 t2 …   ảnh khung nguồn tại các giây → review/frames.jpg (xem đúng vật/không gian)
  python -m thagent.review motion    <dự-án> <ID> [t0 t1]   độ nét/chuyển động mỗi 0,5s + lời → cắt bỏ thao tác chuẩn bị, khung nhòe
  python -m thagent.review hands     <dự-án> <ID> [t0 t1]   dò lúc giơ/chỉ tay vào vật (đầu ngón, vùng gợi ý)
  python -m thagent.review track     <dự-án> <tên> <ID> <t> x,y,w,h <t0> <t1>   bám vật (box chuẩn hoá đọc từ lưới của frames)
  python -m thagent.review clean     <dự-án>                Cắt sạch trong đoạn nói (lặng thừa, từ đệm, vấp, nói lại) — bộ của Talking Head
  python -m thagent.review keyinfo   <dự-án>                số liệu / thông tin then chốt trong lời → gợi ý khối "stat"
  python -m thagent.review joins     <dự-án>                điểm nối theo nhịp nói (đệm, nghỉ, cắt khi còn tiếng) + waveform review/joins.jpg
  python -m thagent.review fixjoins  <dự-án>                nới in/out theo nhịp nói tự nhiên (lưu edit.json.bak)
  python -m thagent.review check     <dự-án>                kiểm edit.json trước khi dựng
  python -m thagent.review stills    <dự-án> <9x16|16x9> t1 t2 …   ảnh khung đã dựng (crop + chữ) tại các giây → review/stills_<fmt>.jpg
  python -m thagent.review render    <dự-án> [9x16|16x9]    dựng + kiểm file xuất → review/versions/vNNN/
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np


REF_DIRS = {"tham_khao", "tham khao", "thamkhao", "reference", "references", "ref", "refs"}


def _files(args):
    from .inventory import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT
    out = []
    for a in args:
        p = Path(a).expanduser()
        if p.is_dir():   # thư mục con tham_khao/reference/ref = video tham khảo, KHÔNG phải tư liệu dựng
            out += [x for x in sorted(p.rglob("*")) if x.suffix.lower() in VIDEO_EXT | IMAGE_EXT | AUDIO_EXT and not x.name.startswith(".")
                    and not any(q.lower() in REF_DIRS for q in x.relative_to(p).parts[:-1])]
        elif p.exists():
            out.append(p)
    return [str(x) for x in out]


def inventory(pdir, *args):
    from .inventory import inventory as inv
    a = list(args)
    refs = a[a.index("--ref") + 1:] if "--ref" in a else []
    srcs = a[:a.index("--ref")] if "--ref" in a else a
    s = inv(pdir, _files(srcs), print, _files(refs))
    for m in s["media"]:
        print(f"{m['id']} {m['name']} · {m.get('kind')} · {m.get('duration')}s · {m.get('w')}x{m.get('h')} {m.get('orientation', '')} "
              f"{m.get('fps', '')}fps · {m.get('role_guess', '')} · cảnh {m.get('shots')} · câu {m.get('sentences')}"
              + (f" · TRÙNG {m['duplicate_of']}" if m.get("duplicate_of") else "") + (f" · outro {m['outro']}" if m.get("outro") else "")
              + ("" if m.get("usable", True) else " · KHÔNG DÙNG ĐƯỢC"))


def media_cmd(pdir, fid=None):
    from .edit import media
    M = media(pdir)
    if not fid:
        for k, m in M.items():
            print(k, m["name"], m.get("duration"), m.get("role_guess"), "sheet:", m.get("sheet"))
        return
    m = M[fid]
    print(json.dumps({k: m.get(k) for k in ("id", "name", "duration", "w", "h", "fps", "orientation", "role_guess", "lufs", "black", "outro",
                                             "sheet")}, ensure_ascii=False))
    for i, s in enumerate(m.get("shots", []), 1):
        print(f"  cảnh {i}: {s['start']}–{s['end']}s nét {s['sharp']} rung {s['shake']} sáng {s['luma']} mặt {s['face_ratio']} {' '.join(s['flags'])}")
    for s in m.get("sentences", []):
        print(f"  [{s['start']:.2f}–{s['end']:.2f}] ({s['conf']:.2f}) {s['text']}")
    if m.get("check_words"):
        print("  CẦN SOÁT:", "; ".join(f"{w['text']}@{w['t']:.1f} ({','.join(w['why'])})" for w in m["check_words"][:40]))


def words(pdir, fid, t0=0, t1=1e9):
    from .edit import media
    print(" ".join(f"{w['text']}@{w['start']:.2f}" for w in media(pdir)[fid].get("words", []) if float(t0) <= w["start"] <= float(t1)))


def takes(pdir):
    from .takes import groups
    for g in groups(pdir):
        print(f"{g['group']} gợi ý {g['suggest']}: {g['idea']}")
        for t in g["takes"]:
            print(f"   {t['take']} {t['src']} {t['in']:.2f}–{t['out']:.2f}s điểm {t['score']} vấp {t['stutter']} mặt {t['face']} {' '.join(t['flags'])} | {t['text'][:70]}")


def frames(pdir, fid, *ts):
    import cv2
    from .edit import media
    m = media(pdir)[fid]
    ims = []
    for t in ts:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", m["path"], "-frames:v", "1", "-vf", "scale=360:-2", "-f", "image2pipe",
                              "-vcodec", "png", "-"], capture_output=True).stdout
        im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if im is not None:
            H, W = im.shape[:2]
            for k in range(1, 10):   # lưới toạ độ chuẩn hoá 0.1 → đọc box vật thể (x, y, w, h) cho lệnh track
                cv2.line(im, (int(W * k / 10), 0), (int(W * k / 10), H), (0, 255, 255) if k == 5 else (200, 200, 200), 1)
                cv2.line(im, (0, int(H * k / 10)), (W, int(H * k / 10)), (0, 255, 255) if k == 5 else (200, 200, 200), 1)
                cv2.putText(im, f".{k}", (int(W * k / 10) + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)
                cv2.putText(im, f".{k}", (2, int(H * k / 10) - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 0), 1)
            cv2.putText(im, f"{fid} {float(t):.1f}s", (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            ims.append(im)
    h = max(i.shape[0] for i in ims)
    ims = [cv2.copyMakeBorder(i, 0, h - i.shape[0], 0, 4, cv2.BORDER_CONSTANT) for i in ims]
    out = Path(pdir) / "review" / "frames.jpg"
    cv2.imwrite(str(out), np.hstack(ims))
    print(out)


def check(pdir):
    from .edit import duration, load, validate
    e = load(pdir)
    iss = validate(pdir, e)
    for s, m in iss:
        print(f"[{s}] {m}")
    print(f"{sum(s == 'error' for s, _ in iss)} lỗi, {sum(s == 'warn' for s, _ in iss)} cảnh báo · thời lượng {duration(e):.1f}s")


def stills(pdir, fmt, *ts):
    """ảnh đúng như bản xuất (crop + chữ) — kiểm trước khi dựng cả video."""
    import cv2
    from .edit import FORMATS, crop_box, load
    from .graphics import Layer
    from .render import _pieces
    e = load(pdir)
    W, H = FORMATS[fmt]
    ps = _pieces(e, pdir, fmt)
    L = Layer(e, pdir, fmt)
    ims = []
    for t in map(float, ts):
        acc = 0.0
        for p in ps:
            if acc <= t < acc + p["dur"] or p is ps[-1]:
                break
            acc += p["dur"]
        src_t = p["in"] + (t - acc)
        m, c = p["m"], p["crop"]
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{src_t:.3f}", "-i", m["path"], "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                             capture_output=True).stdout
        im = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
        if c.get("fit") == "blur":
            bg = cv2.GaussianBlur(cv2.resize(im, (W, H)), (0, 0), 25)
            s = min(W / im.shape[1], H / im.shape[0])
            fg = cv2.resize(im, (int(im.shape[1] * s), int(im.shape[0] * s)))
            y0, x0 = (H - fg.shape[0]) // 2, (W - fg.shape[1]) // 2
            bg[y0:y0 + fg.shape[0], x0:x0 + fg.shape[1]] = fg
            im = bg
        else:
            x, y, w, h, _ = crop_box(im.shape[1], im.shape[0], fmt, c)
            im = cv2.resize(im[y:y + h, x:x + w], (W, H))
        g = L.rgba(t)
        if g is not None:
            a = g[..., 3:4]
            im = ((im[..., ::-1] / 255 * (1 - a) + g[..., :3] * a) * 255).astype(np.uint8)[..., ::-1].copy()
        cv2.putText(im, f"{t:.1f}s {p['seg']}{' cutaway' if p.get('cutaway') else ''}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 255), 3)
        ims.append(cv2.resize(im, (W // 4, H // 4)))
    cols = 6 if fmt == "9x16" else 4
    rows = [ims[i:i + cols] for i in range(0, len(ims), cols)]
    rows[-1] += [np.zeros_like(ims[0])] * (cols - len(rows[-1]))
    out = Path(pdir) / "review" / f"stills_{fmt}.jpg"
    cv2.imwrite(str(out), np.vstack([np.hstack(r) for r in rows]))
    print(out)


def render(pdir, *fmts):
    from .render import render as rr
    for q in rr(pdir, [f for f in fmts if f in ("9x16", "16x9")] or None):
        print(json.dumps(q, ensure_ascii=False, indent=1))


def hands_cmd(pdir, fid, t0=0, t1=None):
    from .objects import hands
    for c in hands(pdir, fid, float(t0), float(t1) if t1 else None):
        print(f"chỉ tay {c['t0']:.2f}–{c['t1']:.2f}s đầu ngón {c['tip']} vùng gợi ý {c['target']} (xác nhận bằng frames)")


def track_cmd(pdir, name, fid, t, box, t0, t1):
    from .objects import track
    r = track(pdir, name, fid, float(t), [float(x) for x in box.split(",")], float(t0), float(t1))
    print(f"track {name}: {r['t0']}–{r['t1']}s, {len(r['points'])} mẫu, mất dấu {r['lost_s']}s" + (f" từ {r['lost_from']}s" if r["lost_from"] else ""))
    for p in r["points"][::10]:
        print("  ", p["t"], [round(x, 3) for x in p["box"]], "MẤT" if p["lost"] else "")


def motion(pdir, fid, t0=0, t1=1e9):
    """độ nét / chuyển động mỗi 0,5s + lời → chọn điểm cắt bỏ thao tác chuẩn bị, khung nhòe."""
    from .edit import media
    m = media(pdir)[fid]
    st = m.get("sharp_track", [])
    med = sorted(x[1] for x in st)[len(st) // 2] if st else 0
    ws = m.get("words", [])
    for t, sh, mo in st:
        if float(t0) <= t <= float(t1):
            said = " ".join(w["text"] for w in ws if t <= w["start"] < t + 0.5)
            flag = "NHÒE" if sh < 0.4 * med else ("ĐỘNG MẠNH" if mo > 0.12 else "")
            print(f"{t:6.1f}s nét {sh:7.1f} động {mo:.3f} {flag:9s} {said}")


def joins(pdir):
    """điểm nối theo nhịp nói: đệm đầu/cuối, khoảng nghỉ, cắt khi còn tiếng + ảnh waveform review/joins.jpg."""
    from .audiocut import junctions, sheet
    from .edit import load
    e = load(pdir)
    for j in junctions(e, pdir):
        print(f"{j['seg']} @{j['t_out']}s đầu {j['head'] * 1000:.0f}ms “{j['first']}” · cuối {j['tail'] * 1000:.0f}ms “{j['last']}”"
              + (f" · nghỉ trước {j['gap'] * 1000:.0f}ms" if "gap" in j else ""))
        for lv, msg in j["flags"]:
            print(f"   [{lv}] {msg}")
    print(sheet(e, pdir), "(waveform: soát bằng mắt — KHÔNG thay việc nghe)")


def fixjoins(pdir):
    """nới in/out mọi đoạn nói theo nhịp tự nhiên (đệm trước ~120ms, sau ~220ms, theo năng lượng tới 0,2/0,4s; không lấn từ kề);
    dời mốc at của chữ/cutaway/reframe tương ứng. Lưu bản cũ edit.json.bak."""
    import shutil
    from .audiocut import refine
    from .edit import load
    p = Path(pdir) / "review" / "edit.json"
    e2, notes = refine(load(pdir), pdir)
    shutil.copy2(p, p.with_suffix(".json.bak"))
    p.write_text(json.dumps(e2, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(notes) or "không cần nới")


def keyinfo(pdir):
    """số liệu / thông tin then chốt trong lời (timeline xuất) — gợi ý khối role "stat"."""
    from .edit import load
    from .keyinfo import detect
    for k in detect(load(pdir), pdir):
        print(f"{k['t']:6.2f}s  “{k['text']}”  (đoạn {k['seg']}) → {{\"role\": \"stat\", \"value\": {k['value']:g}, \"unit\": \"{k['unit']}\", \"label\": \"…\"}}")


def clean(pdir):
    """Cắt sạch TRONG đoạn nói (lặng thừa, từ đệm, vấp, nói lại) bằng bộ của Talking Head → chia đoạn con, punch-in che điểm cắt.
    Lưu edit.json.bak; báo cáo review/cleanup.json."""
    import shutil
    from .cleanup import split
    from .edit import load
    from .edit import media
    from .restart import detect
    p = Path(pdir) / "review" / "edit.json"
    e0 = load(pdir)
    spans = {}
    for s in e0["segments"]:
        if s.get("role", "talk") == "talk":
            spans.setdefault(s["src"], []).append((float(s["in"]), float(s["out"])))
    M = media(pdir)
    found = False
    for fid, sp in spans.items():                 # nói hỏng rồi nói lại mà máy chép lời bỏ sót → nghe lại sau chỗ ngừng
        found |= bool(detect(pdir, M[fid], sp))
    if found:
        media.__defaults__[0].pop(str(pdir), None)   # nạp lại lời đã vá
    e2, rep = split(e0, pdir)
    shutil.copy2(p, p.with_suffix(".json.bak"))
    p.write_text(json.dumps(e2, ensure_ascii=False, indent=1), encoding="utf-8")
    (Path(pdir) / "review" / "cleanup.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rep:
        print(f"{r['seg']}: bỏ {r['from']}–{r['to']}s ({r['s']}s) — {r['reason']}")
    print(f"{len(rep)} chỗ cắt · {len(e2['segments'])} đoạn")


CMDS = {"keyinfo": keyinfo, "clean": clean, "joins": joins, "fixjoins": fixjoins, "hands": hands_cmd, "track": track_cmd, "motion": motion, "inventory": inventory, "media": media_cmd, "words": words, "takes": takes, "frames": frames, "check": check, "stills": stills,
        "render": render}


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        print(__doc__)
        return
    CMDS[sys.argv[1]](*sys.argv[2:])


if __name__ == "__main__":
    main()
