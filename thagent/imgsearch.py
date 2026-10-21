"""Tìm ảnh trên web cho Claude (dùng chung Talking Head + Voice to Motion) — không cần khoá API.

search(work_dir, "sân bay Long Thành", n=12) → ảnh ghép đánh số work/imgsearch.jpg + work/imgsearch.json (tìm qua Bing)
from_page(work_dir, "<link bài báo / trang dự án>")  → như trên, lấy mọi ảnh lớn trong trang (ổn định hơn: WebSearch tìm trang trước)
  [{"n": 1, "url": <link ảnh gốc>, "page": <trang chứa ảnh>, "title": …, "size": "1280x720"}]
Claude Read ảnh ghép, chọn số đúng chủ thể / đúng nội dung, rồi tải bằng lệnh img với "#số" thay cho URL
(nguồn = trang chứa ảnh được ghi tự động).
"""
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FILE = "imgsearch.json"


def _get(url: str, timeout=20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi,en;q=0.8"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def results(query: str, n: int = 12) -> list[dict]:
    import unicodedata
    ascii_q = unicodedata.normalize("NFKD", query.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode()
    page = ""
    for q in dict.fromkeys([query, ascii_q]):            # có trang Bing trả rỗng với từ có dấu → thử lại bản không dấu
        try:
            page = _get("https://www.bing.com/images/search?" + urllib.parse.urlencode({"q": q, "form": "HDRSC2", "first": 1})).decode("utf-8", "ignore")
        except Exception:
            continue
        if "murl" in page:
            break
    out, seen = [], set()
    for m in re.finditer(r'\bm="(\{[^"]+\})"', page):
        try:
            d = json.loads(html.unescape(m.group(1)))
        except ValueError:
            continue
        url = d.get("murl")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"n": len(out) + 1, "url": url, "page": d.get("purl", ""), "title": d.get("t", ""), "thumb": d.get("turl", "")})
        if len(out) >= n:
            break
    return out


def _thumb(r: dict):
    from PIL import Image
    import io
    for u in (r.get("thumb"), r["url"]):
        if not u:
            continue
        try:
            im = Image.open(io.BytesIO(_get(u, 12))).convert("RGB")
            return im
        except Exception:
            continue
    return None


def page_results(page_url: str, n: int = 16) -> list[dict]:
    """ảnh trong một trang web: og:image + <img> (src / data-src / srcset lớn nhất), bỏ icon/logo/ảnh nhỏ theo tên."""
    doc = _get(page_url).decode("utf-8", "ignore")
    title = html.unescape((re.search(r"<title[^>]*>([^<]*)", doc, re.I) or [None, ""])[1]).strip()
    cands = re.findall(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', doc, re.I)
    for tag in re.findall(r"<img\b[^>]*>", doc, re.I):
        srcset = re.search(r'\b(?:data-)?srcset=["\']([^"\']+)', tag, re.I)
        if srcset:
            cands.append(srcset.group(1).split(",")[-1].strip().split(" ")[0])
        for at in ("data-original", "data-src", "data-lazy-src", "src"):
            m = re.search(rf'\b{at}=["\']([^"\']+)', tag, re.I)
            if m and not m.group(1).startswith("data:"):
                cands.append(m.group(1))
                break
    out, seen = [], set()
    for u in cands:
        u = urllib.parse.urljoin(page_url, html.unescape(u))
        low = u.lower()
        if u in seen or not low.startswith("http") or re.search(r"logo|icon|avatar|sprite|banner-ads|1x1|pixel|\.svg|\.gif", low):
            continue
        seen.add(u)
        out.append({"n": len(out) + 1, "url": u, "page": page_url, "title": title, "thumb": ""})
        if len(out) >= n:
            break
    return out


def from_page(work_dir, page_url: str, n: int = 16) -> tuple[Path, list[dict]]:
    rs = page_results(page_url, n)
    if not rs:
        raise SystemExit(f"không thấy ảnh trong {page_url} — mở trang khác (bài báo / trang dự án của chủ đầu tư)")
    return _sheet(work_dir, rs, page_url, min_side=300)


def search(work_dir, query: str, n: int = 12) -> tuple[Path, list[dict]]:
    rs = results(query, n)
    if not rs:
        raise SystemExit(f"không tìm được ảnh cho “{query}” — WebSearch tìm bài báo / trang dự án rồi dùng lệnh imgpage <dự-án> <link trang>")
    return _sheet(work_dir, rs, query)


def _sheet(work_dir, rs: list[dict], query: str, min_side: int = 0) -> tuple[Path, list[dict]]:
    from PIL import Image, ImageDraw
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(_thumb, rs))
    if min_side:                                   # ảnh trong trang: bỏ ảnh nhỏ (icon, ảnh đại diện) rồi đánh số lại
        keep = [(r, im) for r, im in zip(rs, ims) if im is not None and min(im.width, im.height) >= min_side]
        rs, ims = [r for r, _ in keep], [im for _, im in keep]
        for i, r in enumerate(rs):
            r["n"] = i + 1
        if not rs:
            raise SystemExit("trang không có ảnh đủ lớn (≥300px) — mở trang khác")
    cols, cw, ch = 4, 300, 220
    rows = (len(rs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * ch), (24, 24, 24))
    dr = ImageDraw.Draw(sheet)
    for i, (r, im) in enumerate(zip(rs, ims)):
        x, y = (i % cols) * cw, (i // cols) * ch
        if im is not None:
            r["size"] = f"{im.width}x{im.height}"
            im.thumbnail((cw - 8, ch - 8))
            sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        dr.rectangle([x + 4, y + 4, x + 44, y + 34], fill=(255, 200, 0))
        dr.text((x + 12, y + 10), str(r["n"]), fill=(0, 0, 0))
    out = work / "imgsearch.jpg"
    sheet.save(out, quality=88)
    (work / FILE).write_text(json.dumps({"query": query, "results": rs}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out, rs


def resolve(work_dir, ref: str) -> tuple[str, str]:
    """“#3” → (link ảnh, trang nguồn) từ lần tìm gần nhất."""
    f = Path(work_dir) / FILE
    if not f.exists():
        raise SystemExit("chưa tìm ảnh — chạy lệnh imgsearch trước khi dùng #số")
    k = int(ref.lstrip("#"))
    for r in json.loads(f.read_text(encoding="utf-8"))["results"]:
        if r["n"] == k:
            return r["url"], r.get("page") or r["url"]
    raise SystemExit(f"không có ảnh #{k} trong lần tìm gần nhất")


def print_results(sheet: Path, rs: list[dict]):
    print(f"{sheet}  ← Read ảnh ghép này, chọn số ĐÚNG chủ thể/nội dung (ô không có hình = không tải được)")
    for r in rs:
        dom = urllib.parse.urlparse(r.get("page") or r["url"]).netloc
        print(f"#{r['n']:<2} {r.get('size', '?'):>10}  {dom:<28} {r['title'][:70]}")
