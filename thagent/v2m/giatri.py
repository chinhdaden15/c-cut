"""Skill Giá Trị — video câu ngẫm: mỗi câu một cảnh (ảnh / video thật, Ken Burns chậm), chuyển cảnh mờ dần, phụ đề cả câu
chạy theo giọng, nhạc piano tự sáng tác. KHÔNG motion graphic / bản đồ / biểu đồ / icon.

Claude chỉ làm MỘT việc: chọn hình cho từng câu → ghi giatri_picks.json:
  [{"s": [0, 1], "src": "assets_web/v_xxx.mp4", "desc": "cuộn chỉ rối trên bàn gỗ", "in": 0.0}, {"s": [2], "src": "assets_web/i_xxx.jpg", "desc": "…"}, …]
  s = chỉ số câu (trong script.json) dùng chung hình đó — liền nhau; desc = một câu mô tả điều THẬT SỰ thấy trong hình (bắt buộc);
  "in" = giây bắt đầu trong clip (tuỳ chọn). Mỗi hình / clip chỉ dùng MỘT lần.
Rồi chạy: .venv/bin/python -m thagent.v2m giatri <dự-án>  → viết build_timeline.py + dựng + kiểm tra + ảnh tĩnh (lệnh verify).
"""
from __future__ import annotations

import json
from pathlib import Path

BUILDER = '''"""Builder skill Giá Trị — sinh tự động bởi `python -m thagent.v2m giatri` (đừng sửa tay; sửa giatri_picks.json)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, ".")
from thagent.v2m.kit import build
from thagent.v2m.giatri import content

build(__file__, content, fmts=("9x16",), theme="dark")
'''


def groups(pdir: Path) -> list[dict]:
    """picks → nhóm cảnh có mốc thời gian: [{"t0","t1","src","in","text"}]. Thiếu câu nào → báo rõ."""
    meta = json.loads((pdir / "script.json").read_text(encoding="utf-8"))
    sents = meta["sentences"]
    picks = json.loads((pdir / "giatri_picks.json").read_text(encoding="utf-8"))
    seen: list[int] = []
    out = []
    for p in picks:
        idx = [int(i) for i in p["s"]]
        if idx != list(range(idx[0], idx[-1] + 1)):
            raise SystemExit(f"giatri_picks.json: nhóm {idx} phải là các câu LIỀN NHAU")
        seen += idx
        src = p["src"]
        if not (pdir / src).exists():
            raise SystemExit(f"giatri_picks.json: không có file {src}")
        if not str(p.get("desc", "")).strip():
            raise SystemExit(f"giatri_picks.json: nhóm {idx} thiếu \"desc\" — một câu mô tả điều THẬT SỰ thấy trong hình / clip")
        if any(src == g["src"] for g in out):
            raise SystemExit(f"giatri_picks.json: {src} đã dùng ở nhóm trước — mỗi hình / clip chỉ dùng một lần, chọn hình khác")
        out.append({"i0": idx[0], "i1": idx[-1], "src": src, "in": float(p.get("in", 0.0)), "desc": str(p["desc"]).strip()})
    miss = sorted(set(range(len(sents))) - set(seen))
    if miss or seen != sorted(seen):
        raise SystemExit(f"giatri_picks.json: thiếu / sai thứ tự câu {miss or seen} — mỗi câu (0…{len(sents) - 1}) phải thuộc đúng một nhóm, theo thứ tự")
    for k, g in enumerate(out):
        g["t0"] = 0.0 if k == 0 else round(sents[g["i0"]]["start"] - 0.35, 3)           # hình mới hiện sớm 0,35s so với lời → hình dẫn lời
        g["t1"] = round(sents[out[k + 1]["i0"]]["start"] - 0.35, 3) if k + 1 < len(out) else None
        g["text"] = " ".join(sents[i]["text"] for i in range(g["i0"], g["i1"] + 1))
    return out


def content(K):
    pdir = K.pdir
    gs = groups(pdir)
    T = K.T
    K.th["sfx_auto"] = False                       # không SFX chuyển cảnh: chỉ giọng + nhạc piano
    K.F.set_zone("caption", (90, 800, 990, 1120) if K.V else (360, 400, 1560, 680))   # phụ đề GIỮA khung
    K.th["calm"] = True                            # check bỏ luật nhịp dồn dập (hình đứng im, cảnh dài, cùng kiểu hình…)
    K.th["caption_size"] = 68 if K.V else 56
    for k, g in enumerate(gs):
        t1 = g["t1"] if g["t1"] is not None else T
        s = K.scene(g["t0"], t1, f"câu {g['i0'] + 1}–{g['i1'] + 1}", transition={"type": "fade", "dur": 0.8},
                    bg={"style": "charcoal", "color": "#0d1117"})
        s.exit = False                              # giữ hình tới đúng điểm cắt, cảnh sau mờ vào ĐÈ LÊN → hoà tan (không tối đen giữa hai cảnh)
        s.photo_bg(g["src"], g["t0"], dim=0.42, **({"in": g["in"]} if g["in"] else {}))
    m = pdir / "assets_web" / "m_giatri.mp3"
    if m.exists():
        K.music("assets_web/m_giatri.mp3", gain_db=-15, duck=True)


def _wrap(words: list[str], width: int = 28) -> list[str]:
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    return lines + ([cur] if cur else [])


def captions(pdir: Path) -> list[str]:
    """phụ đề: MỖI CÂU một cụm (≤ 2 dòng × 28 ký tự, xuống dòng cân đều); câu dài hơn 2 dòng mới tách thành các cụm liên tiếp."""
    sents = json.loads((pdir / "script.json").read_text(encoding="utf-8"))["sentences"]
    out = []
    for s in sents:
        ws = s["text"].split()
        lines = _wrap(ws)
        if len(lines) <= 2:
            if len(lines) == 2:                                       # cân hai dòng cho đẹp
                for w in range(28, 8, -1):
                    l2 = _wrap(ws, w)
                    if len(l2) == 2:
                        lines = l2
                        break
            out.append("\n".join(lines))
            continue
        commas = [i for i, w in enumerate(ws[:-1]) if w.endswith((",", ";", ":"))]
        if commas:                                                    # tách tại dấu phẩy gần giữa câu nhất → cụm tự nhiên
            ci = min(commas, key=lambda i: abs(i - len(ws) / 2))
            parts = [ws[:ci + 1], ws[ci + 1:]]
            if all(len(_wrap(x)) <= 2 for x in parts):
                out += ["\n".join(_wrap(x)) for x in parts]
                continue
        k = 0
        while k < len(ws):                                            # tách theo cụm ≤ 2 dòng
            chunk, n = [], 0
            while k + n < len(ws) and len(_wrap(ws[k:k + n + 1])) <= 2:
                n += 1
            chunk = ws[k:k + max(n, 1)]
            out.append("\n".join(_wrap(chunk)))
            k += max(n, 1)
    return out


def run(pdir) -> None:
    pdir = Path(pdir)
    groups(pdir)                                            # kiểm hợp lệ trước
    (pdir / "look.json").write_text(json.dumps({"look": "gia_tri", "name": "Giá Trị"}, ensure_ascii=False), encoding="utf-8")
    (pdir / "captions.json").write_text(json.dumps(captions(pdir), ensure_ascii=False, indent=1), encoding="utf-8")
    ic_f = pdir / "assets_web" / "illus_check.json"
    ic = json.loads(ic_f.read_text(encoding="utf-8")) if ic_f.exists() else {}
    for g in groups(pdir):
        ic[Path(g["src"]).name] = {"noi_dung_anh": g["desc"], "cau_noi": g["text"], "khop": True}
    ic_f.write_text(json.dumps(ic, ensure_ascii=False, indent=1), encoding="utf-8")
    if not (pdir / "entities.json").exists():
        (pdir / "entities.json").write_text("[]", encoding="utf-8")                 # video câu ngẫm: không có chủ thể có tên cần ảnh thật
    (pdir / "build_timeline.py").write_text(BUILDER, encoding="utf-8")
    from . import __main__ as V
    V.verify(str(pdir), "9x16")
