"""Chủ thể có tên trong lời nói / chữ trên hình (dự án, khu đô thị, toà nhà, thương hiệu, địa danh, người…) → ảnh PHẢI là ảnh thật của đúng chủ thể.

Claude ghi {pdir}/entities.json (bắt buộc khi video có ảnh tải từ mạng; không có chủ thể nào → []):
[{"name": "Vinhomes Central Park", "aka": ["Vinhomes Tân Cảng", "Tân Cảng"],      tên + cách gọi khác đúng như người nói (cả cách chép lời nghe sai)
  "photos": ["w_vhcp_1.jpg", "w_vhcp_2.jpg"],                                     ảnh THẬT của chính chủ thể (assets_web/, có URL nguồn)
  "no_photo": null},                                                              tìm kỹ không có ảnh thật → ghi lý do (chuỗi)
 {"name": "Global City", "not_entity": "tên hệ sinh thái nói chung, cảnh không có ảnh"}]   tên riêng KHÔNG cần ảnh → ghi lý do
Tìm ảnh thật: python -m thagent.tools imgsearch <dự-án> "<tên dự án + chủ đầu tư>" → Read ảnh ghép → tools img <dự-án> #số w_ten.jpg
Mô tả ảnh (bắt buộc với mọi ảnh web, sau khi Read ảnh): assets_web/illus_check.json
  {"i_ten.jpg": {"noi_dung_anh": "sân bay, nhà ga, máy bay đậu", "cau_noi": "…", "khop": true}}   ghi THẬT những gì thấy trong ảnh
Kiểm (dùng chung Talking Head + Voice to Motion):
- cảnh có ảnh mà lời nói (trong cảnh hoặc ≤2s trước khi cảnh hiện) hay CHỮ TRÊN HÌNH gọi tên chủ thể → cảnh phải có ≥1 ảnh trong photos
  của chủ thể (no_photo → cảnh báo, không giả ảnh nơi khác);
- ảnh trong photos: có trong assets_web, nguồn là URL, được dựng như ảnh thật (Talking Head: tên w_*; Voice to Motion: real=True);
- ảnh minh hoạ chung không được gắn nhãn tên chủ thể; tên riêng nghe thấy quanh cảnh có ảnh mà chưa khai → LỖI (khai chủ thể hoặc not_entity);
- lời/chữ của cảnh nói vật cụ thể (sân bay, sông, biển, hồ bơi, công viên, metro, cầu, trường học, bệnh viện…) → phải có ảnh mà
  noi_dung_anh có đúng vật đó; ảnh web chưa mô tả → lỗi;
- một ảnh web chỉ dùng ở MỘT cảnh trong cả video.
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


def _saturation(path) -> float | None:
    """độ bão hoà màu trung bình (0..1) — ảnh trắng đen / ngả màu cũ ≈ 0."""
    try:
        import cv2
        im = cv2.imread(str(path))
        if im is None:
            return None
        hsv = cv2.cvtColor(cv2.resize(im, (160, 120)), cv2.COLOR_BGR2HSV)
        return float(hsv[..., 1].mean()) / 255
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


LEAD = 2.0          # giây: lời nói ngay trước khi cảnh ảnh hiện vẫn tính cho cảnh đó (cảnh thường vào sau câu nói)
# vật cụ thể → (cách nói trong lời/chữ, từ phải có trong mô tả ảnh); cụm loại trừ để khỏi bắt nhầm
THINGS = [
    ("sân bay", [r"sân bay", r"phi trường", r"airport"], ["sân bay", "máy bay", "nhà ga", "airport", "phi trường"]),
    ("sông", [r"(?<!\w)sông(?!\w)", r"ven sông", r"bờ sông"], ["sông", "river", "kênh", "bến"]),
    ("biển", [r"(?<!\w)biển(?! (số|quảng|báo|hiệu|tên))"], ["biển", "bãi biển", "sea", "beach", "ocean"]),
    ("hồ bơi", [r"hồ bơi", r"bể bơi"], ["hồ bơi", "bể bơi", "pool"]),
    ("công viên", [r"công viên"], ["công viên", "park", "cây xanh"]),
    ("metro", [r"metro", r"tàu điện"], ["metro", "tàu điện", "nhà ga", "đường ray"]),
    ("cầu", [r"cây cầu", r"(?<!\w)cầu (thủ thiêm|ba son|phú mỹ|sài gòn|rồng|vượt|cạn|bắc qua)"],
     ["cầu", "bridge"]),
    ("trường học", [r"trường học", r"trường quốc tế", r"trường mầm non", r"trường đại học"], ["trường", "lớp học", "học sinh", "school", "campus"]),
    ("bệnh viện", [r"bệnh viện"], ["bệnh viện", "hospital", "phòng khám", "y tế"]),
    ("cao tốc", [r"cao tốc"], ["cao tốc", "đường", "highway", "xa lộ"]),
]


def _things(text: str) -> list[tuple[str, list[str]]]:
    t = " ".join(norm(text))
    return [(k, need) for k, pats, need in THINGS if any(re.search(p, t) for p in pats)]


def descriptions(pdir) -> dict:
    f = Path(pdir) / "assets_web" / "illus_check.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return {k: (v.get("noi_dung_anh") if isinstance(v, dict) else v) or "" for k, v in d.items()}
    except Exception:
        return {}


def _scene_at(img_scenes: list[dict], t: float, lead: float) -> dict | None:
    return next((s for s in img_scenes if s["t0"] <= t < s["t1"]), None) or \
        next((s for s in img_scenes if s["t0"] - lead <= t < s["t0"]), None)


def check(pdir, words: list[tuple[str, float]], scenes: list[dict], real_ok, unit: str = "s") -> list[tuple[str, str]]:
    """scenes: [{"id", "t0", "t1", "text": chữ trên hình, "images": [{"file": basename, "real": bool, "label": str}]}] — t cùng đơn vị với words.
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
    lead = LEAD if unit == "s" else LEAD * 30
    dismissed = [e for e in ents if e.get("not_entity")]
    ents = [e for e in ents if not e.get("not_entity")]
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
    hits = []
    for e, t, said in mentions(ents, words):
        s = _scene_at(img_scenes, t, lead)
        if s:
            hits.append((e, t, said, s))
    for s in img_scenes:                                         # tên chủ thể nằm trong CHỮ trên hình của cảnh
        for e, _, said in mentions(ents, [(s.get("text") or "", s["t0"])]):
            hits.append((e, s["t0"], said, s))
    seen = set()
    for e, t, said, s in hits:
        if (e["name"], s["id"]) in seen:
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
    known = {" ".join(norm(n)) for e in [*ents, *dismissed] for n in [e.get("name", ""), *(e.get("aka") or [])] if n} | IGNORE
    for nm, t in _proper_names(words):
        k = " ".join(norm(nm))
        if k in known or any(k in n or n in k for n in known if n):
            continue
        s = _scene_at(img_scenes, t, lead)
        if s:
            out.append(("error", f"{s['id']}: nghe có tên riêng “{nm}” ({t:.1f}{unit}) chưa khai trong {FILE} — dự án/địa danh/thương hiệu → "
                                 "sửa chép lời cho đúng tên, thêm vào kèm ảnh thật (tools imgsearch); không phải chủ thể → "
                                 '{"name": …, "not_entity": "lý do"}'))
    # vật cụ thể được nói / ghi trên hình → phải có ảnh đúng vật đó (theo mô tả sau khi Read ảnh)
    desc = descriptions(pdir)
    for s in img_scenes:
        files = [im["file"] for im in s["images"] if (Path(pdir) / "assets_web" / im["file"]).exists()]
        for fl in files:
            sat = _saturation(Path(pdir) / "assets_web" / fl)
            if sat is not None and sat < 0.07:
                out.append(("error", f"{s['id']}: ảnh {fl} trắng đen / màu bạc như ảnh cũ (độ bão hoà {sat:.2f}) — minh hoạ phải là ảnh "
                                     "HIỆN ĐẠI, CÓ MÀU, đúng bối cảnh bây giờ (ưu tiên Việt Nam / châu Á); thay ảnh khác"))
            if not desc.get(fl):
                out.append(("error", f"{s['id']}: ảnh {fl} chưa mô tả trong assets_web/illus_check.json — Read ảnh rồi ghi "
                                     '{"' + fl + '": {"noi_dung_anh": "những gì THẬT SỰ thấy trong ảnh", "cau_noi": "…", "khop": true}}'))
        said = " ".join(w for w, x in words if s["t0"] - lead <= x < s["t1"])
        th = _things(said + " " + (s.get("text") or ""))        # liệt kê nhiều tiện ích → ảnh có ít nhất một thứ trong đó
        if th and files and not any(any(n in " ".join(norm(desc.get(fl, ""))) for _, need in th for n in need) for fl in files):
            k = " / ".join(k for k, _ in th)
            out.append(("error", f"{s['id']}: lời/chữ nói “{k}” nhưng không ảnh nào trong cảnh có {k} ("
                                 + "; ".join(f"{fl}: {desc.get(fl) or 'chưa mô tả'}" for fl in files)
                                 + f") — tìm ảnh đúng {k} (tools imgsearch / imgpage), có tên riêng thì ảnh thật của đúng nơi đó"))
    # dùng lại ảnh/clip: chỉ khi cảnh sau nói ĐÚNG vật của hình đó (nhãn "vat" trong illus_check.json); không nhãn → mỗi hình một cảnh
    first, tags = {}, labels(pdir)
    for s in img_scenes:
        said = " ".join(norm(" ".join(w for w, x in words if s["t0"] - lead <= x < s["t1"]) + " " + (s.get("text") or "")))
        for fl in dict.fromkeys(im["file"] for im in s["images"]):
            if fl in first and first[fl] != s["id"]:
                tag = " ".join(norm(tags.get(fl, "")))
                if not tag:
                    out.append(("error", f"{s['id']}: ảnh {fl} đã dùng ở {first[fl]} — mỗi ảnh chỉ dùng một lần; muốn dùng lại khi nói lại "
                                         "đúng vật đó thì ghi \"vat\" cho ảnh trong illus_check.json"))
                elif not _has_tag(said, tag):
                    out.append(("error", f"{s['id']}: dùng lại {fl} (“{tags[fl]}”) nhưng cảnh này không nói tới “{tags[fl]}” — "
                                         "lặp hình sai ngữ cảnh, tìm hình khác đúng câu đang nói"))
            first.setdefault(fl, s["id"])
    return out


def labels(pdir) -> dict:
    """nhãn vật của từng ảnh/clip web (illus_check.json → "vat")."""
    f = Path(pdir) / "assets_web" / "illus_check.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return {k: v.get("vat", "") for k, v in d.items() if isinstance(v, dict) and v.get("vat")}
    except Exception:
        return {}


def _has_tag(said: str, tag: str) -> bool:
    """cảnh nói tới vật: đủ cụm, hoặc ≥ 2/3 số từ của nhãn (nhãn dài kiểu “đầu cọ son” vẫn khớp khi chỉ nói “đầu cọ”)."""
    if f" {tag} " in f" {said} ":
        return True
    t = [x for x in tag.split() if len(x) > 1]
    hit = sum(1 for x in t if f" {x} " in f" {said} ")
    return bool(t) and hit >= (len(t) if len(t) <= 2 else round(len(t) * 2 / 3))     # nhãn ngắn phải khớp đủ
