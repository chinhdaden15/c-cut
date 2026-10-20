"""Chủ thể có tên trong lời nói (dự án, khu đô thị, toà nhà, thương hiệu, địa danh, người…) → ảnh PHẢI là ảnh thật của đúng chủ thể.

Claude ghi {pdir}/entities.json (bắt buộc khi video có ảnh tải từ mạng; không có chủ thể nào → []):
[{"name": "Vinhomes Central Park", "aka": ["Vinhomes Tân Cảng", "Tân Cảng"],      tên + cách gọi khác đúng như người nói
  "photos": ["w_vhcp_1.jpg", "w_vhcp_2.jpg"],                                     ảnh THẬT của chính chủ thể (assets_web/, có URL nguồn)
  "no_photo": null}]                                                              tìm kỹ không có ảnh thật → ghi lý do (chuỗi)
Kiểm (dùng chung Talking Head + Voice to Motion):
- lời nhắc chủ thể trong một cảnh có ảnh → cảnh đó phải có ≥1 ảnh trong photos của chủ thể (no_photo → cảnh báo, không giả ảnh nơi khác);
- ảnh trong photos: có trong assets_web, nguồn là URL, được dựng như ảnh thật (Talking Head: tên w_*; Voice to Motion: real=True);
- ảnh minh hoạ chung không được gắn nhãn tên chủ thể; tên riêng nghe thấy trong cảnh có ảnh mà chưa khai → cảnh báo.
Ảnh nội thất / tiện ích / khái niệm nói chung chung (không gọi tên chủ thể) vẫn dùng ảnh minh hoạ như cũ.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

FILE = "entities.json"


def norm(t: str) -> list[str]:
    t = unicodedata.normalize("NFC", str(t)).lower()
    return [x for x in re.split(r"[^\w]+", t) if x]


def load(pdir) -> list[dict] | None:
    f = Path(pdir) / FILE
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else None
    except Exception:
        return None


def sources(pdir) -> dict:
    f = Path(pdir) / "assets_web" / "illus_sources.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def mentions(ents: list[dict], words: list[tuple[str, float]]) -> list[tuple[dict, float, str]]:
    """[(chủ thể, thời điểm, cụm nghe được)] — so khớp chuỗi từ (không dấu câu, chữ thường) với name/aka."""
    toks = [(t, x) for w, x in words for t in norm(w)]
    out = []
    for e in ents:
        for nm in [e.get("name", ""), *(e.get("aka") or [])]:
            ph = norm(nm)
            if not ph:
                continue
            for i in range(len(toks) - len(ph) + 1):
                if all(toks[i + j][0] == ph[j] for j in range(len(ph))):
                    out.append((e, toks[i][1], nm))
    return out


def _proper_names(words: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """cụm ≥2 từ viết hoa liên tiếp (không đứng đầu câu) — gợi ý tên riêng chưa khai báo."""
    out, cur, prev_end = [], [], True
    for w, x in words:
        s = w.strip()
        cap = bool(s) and s[0].isupper() and not s.isupper()
        if cap and not prev_end:
            cur.append((s.strip(".,!?"), x))
        else:
            if len(cur) >= 2:
                out.append((" ".join(t for t, _ in cur), cur[0][1]))
            cur = []
        prev_end = s[-1:] in ".!?" if s else prev_end
    if len(cur) >= 2:
        out.append((" ".join(t for t, _ in cur), cur[0][1]))
    return out


IGNORE = {"tp hcm", "hồ chí minh", "việt nam", "hà nội", "sài gòn"}     # tên chung, ảnh minh hoạ thành phố vẫn được


def check(pdir, words: list[tuple[str, float]], scenes: list[dict], real_ok, unit: str = "s") -> list[tuple[str, str]]:
    """scenes: [{"id", "t0", "t1", "images": [{"file": basename, "real": bool, "label": str}]}] — t cùng đơn vị với words.
    real_ok(img) → ảnh được dựng như ảnh thật (Talking Head: w_*; V2M: real=True)."""
    img_scenes = [s for s in scenes if s["images"]]
    web = [i for s in img_scenes for i in s["images"] if (Path(pdir) / "assets_web" / i["file"]).exists()]
    if not web:
        return []
    ents = load(pdir)
    if ents is None:
        return [("error", f"chưa có {FILE} — liệt kê mọi dự án/khu đô thị/toà nhà/thương hiệu/địa danh có tên được nói trong video "
                          "kèm ảnh THẬT của từng chủ thể (không có chủ thể nào → ghi [])")]
    out, src = [], sources(pdir)
    names = {n: e for e in ents for n in [e.get("name", ""), *(e.get("aka") or [])] if n}
    for e in ents:
        for f in e.get("photos") or []:
            if not (Path(pdir) / "assets_web" / f).exists():
                out.append(("error", f"{e['name']}: không có ảnh assets_web/{f}"))
            elif "://" not in str(src.get(f, "")):
                out.append(("error", f"{e['name']}: ảnh {f} chưa có URL nguồn (tải bằng thagent.tools img … <url> {f} <url trang nguồn>)"))
    for s in img_scenes:
        for im in s["images"]:
            owner = next((e for e in ents if im["file"] in (e.get("photos") or [])), None)
            if owner and not real_ok(im):
                out.append(("error", f"{s['id']}: {im['file']} là ảnh của {owner['name']} nhưng đang dựng như ảnh minh hoạ chung"))
            if not owner and real_ok(im):
                out.append(("warn", f"{s['id']}: ảnh thật {im['file']} chưa gắn với chủ thể nào trong {FILE}"))
            lab = " ".join(norm(im.get("label") or ""))
            if not real_ok(im) and lab:
                for n in names:
                    if " ".join(norm(n)) and " ".join(norm(n)) in lab:
                        out.append(("error", f"{s['id']}: ảnh minh hoạ chung {im['file']} gắn nhãn “{im['label']}” — ảnh không phải {n}, "
                                             "dùng ảnh thật của chủ thể hoặc bỏ tên khỏi nhãn"))
    seen = set()
    for e, t, said in mentions(ents, words):
        s = next((s for s in img_scenes if s["t0"] <= t < s["t1"]), None)
        if not s or (e["name"], s["id"]) in seen:
            continue
        seen.add((e["name"], s["id"]))
        if any(im["file"] in (e.get("photos") or []) and real_ok(im) for im in s["images"]):
            continue
        if e.get("no_photo"):
            out.append(("warn", f"{s['id']}: nói “{said}” nhưng không có ảnh thật ({e['no_photo']}) — chỉ dùng bản đồ/sơ đồ/chữ tên, "
                                "không dùng ảnh nơi khác; ghi rõ vào confirm.json"))
        else:
            out.append(("error", f"{s['id']}: đang nói “{said}” ({t:.1f}{unit}) mà cảnh không có ảnh THẬT của {e['name']} — "
                                 "tìm ảnh đúng dự án (web chủ đầu tư/báo), không dùng ảnh minh hoạ chung"))
    known = {" ".join(norm(n)) for n in names} | IGNORE
    for nm, t in _proper_names(words):
        k = " ".join(norm(nm))
        if k in known or any(k in n or n in k for n in known if n):
            continue
        s = next((s for s in img_scenes if s["t0"] <= t < s["t1"]), None)
        if s:
            out.append(("warn", f"{s['id']}: nghe có tên riêng “{nm}” ({t:.1f}{unit}) chưa khai trong {FILE} — nếu là dự án/địa danh/"
                                "thương hiệu thì thêm vào và dùng ảnh thật"))
    return out
