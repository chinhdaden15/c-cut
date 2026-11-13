"""Tư liệu THẬT cho web / app / hãng / nhân vật được nhắc tới trong video — để dựng motion graphic đúng cái đang nói.
Ý tưởng từ ghost-editor (brand_kit.py, cutout sticker — MIT), viết lại cho C-Cut.

  python -m thagent.tools brand <dự-án> <url trang chủ> [slug]        logo + icon app + ảnh đại diện trang (og:image) + màu thương hiệu
        → assets_web/brand_<slug>/ (kit.json, logo.*, icon.png, og.jpg, sheet.jpg) — Read sheet.jpg trước khi dùng
  python -m thagent.tools webshot <dự-án> <url> [tên.jpg] [rộng] [cao] ảnh chụp trang web thật (Chrome chạy ngầm của app) → assets_web/
  python -m thagent.tools paper <dự-án> <ảnh> [tên.png]                ảnh NHÂN VẬT / vật → xoá nền → sticker giấy cắt viền trắng + vân giấy + bóng
        → assets_web/p_<tên>.png (dùng trong mg2 kind "paper" hoặc ảnh thường)
Nguồn ảnh nhân vật: ảnh thật của đúng người (báo, trang chính thức, Wikimedia) — ghi nguồn như mọi ảnh web (illus_sources.json).
"""
from __future__ import annotations

import colorsys
import html as H
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import numpy as np

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _get(url: str, timeout=25) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _slug(s: str) -> str:
    s = re.sub(r"^https?://(www\.)?", "", s.lower()).split("/")[0]
    return re.sub(r"[^a-z0-9]+", "_", s.split(".")[0] if "." in s else s).strip("_") or "brand"


def _attrs(tag: str) -> dict:
    return {k.lower(): H.unescape(v) for k, v in re.findall(r'([\w:-]+)\s*=\s*["\']([^"\']*)["\']', tag)}


def _accent_of(img_path: Path) -> str | None:
    """màu bão hoà nổi bật nhất của logo / icon (bỏ trắng, đen, xám)."""
    import cv2
    import numpy as np
    im = cv2.imread(str(img_path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    a = im[..., 3] > 128 if im.shape[2] == 4 else np.ones(im.shape[:2], bool)
    px = im[..., :3][a].reshape(-1, 3).astype(np.float32)
    if len(px) < 20:
        return None
    hsv = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    keep = (hsv[:, 1] > 80) & (hsv[:, 2] > 60)
    if keep.sum() < 20:
        return None
    sel = px[keep]
    _, lab, cen = cv2.kmeans(sel, min(3, len(sel)), None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 2,
                             cv2.KMEANS_PP_CENTERS)
    b, g, r = cen[np.bincount(lab.ravel()).argmax()]
    return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))


def brand(pdir, url: str, slug: str | None = None) -> dict:
    pdir = Path(pdir)
    if not url.startswith("http"):
        url = "https://" + url
    slug = slug or _slug(url)
    d = pdir / "assets_web" / f"brand_{slug}"
    d.mkdir(parents=True, exist_ok=True)
    try:
        page = _get(url).decode("utf-8", "ignore")
    except Exception:                                   # trang chặn trình tải (403 / Cloudflare) → đọc qua Chrome chạy ngầm
        r = subprocess.run([_chrome(), "--headless", "--disable-gpu", "--virtual-time-budget=6000", f"--user-agent={UA}", "--dump-dom", url],
                           capture_output=True, text=True, timeout=90)
        page = r.stdout or ""
    base = url
    kit = {"name": slug, "url": url, "files": {}}
    m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
    if m:
        kit["title"] = H.unescape(re.sub(r"\s+", " ", m.group(1)).strip())[:120]
    cands = []                                          # (ưu tiên, loại, url)
    for tag in re.findall(r"<(?:link|meta|img)\b[^>]*>", page, re.I):
        a = _attrs(tag)
        rel, prop, src = a.get("rel", "").lower(), (a.get("property") or a.get("name") or "").lower(), a.get("href") or a.get("content") or a.get("src")
        if not src:
            continue
        u = urllib.parse.urljoin(base, src)
        if "apple-touch-icon" in rel:
            cands.append((0, "icon", u))
        elif "icon" in rel and ("svg" in u or a.get("sizes", "") in ("192x192", "512x512", "180x180")):
            cands.append((1, "icon", u))
        elif "icon" in rel:
            cands.append((3, "icon", u))
        elif prop in ("og:image", "twitter:image"):
            cands.append((0, "og", u))
        elif prop == "theme-color" and a.get("content", "").startswith("#"):
            kit["theme_color"] = a["content"]
        elif tag.lower().startswith("<img") and re.search(r"logo", (a.get("class", "") + a.get("alt", "") + a.get("id", "") + src), re.I):
            cands.append((0, "logo", u))
    got = {}
    si = _simple_icon(slug, d)                          # logo chính thức (Simple Icons, CC0) + mã màu thương hiệu
    if si:
        got["logo"] = si["file"]
        kit["files"]["logo"] = si["file"].name
        kit["simple_icons_hex"] = si["hex"]
        kit.setdefault("sources", {})[si["file"].name] = si["url"]
    for pr, kind, u in sorted(cands):
        if kind in got:
            continue
        try:
            b = _get(u)
        except Exception:
            continue
        ext = (Path(urllib.parse.urlparse(u).path).suffix.lower() or ".png")[:5]
        if ext not in (".png", ".jpg", ".jpeg", ".svg", ".webp", ".ico"):
            ext = ".png"
        f = d / f"{kind}{ext}"
        f.write_bytes(b)
        got[kind] = f
        kit["files"][kind] = f.name
        kit.setdefault("sources", {})[f.name] = u
    acc = None
    for k in ("logo", "icon"):
        if k in got and got[k].suffix != ".svg":
            acc = _accent_of(got[k])
            if acc:
                break
    kit["accent"] = kit.get("simple_icons_hex") or acc or kit.get("theme_color") or "#1E86FF"
    (d / "kit.json").write_text(json.dumps(kit, ensure_ascii=False, indent=1), encoding="utf-8")
    _sheet(d, kit)
    src_file = pdir / "assets_web" / "illus_sources.json"
    try:
        srcs = json.loads(src_file.read_text(encoding="utf-8"))
    except Exception:
        srcs = {}
    for fn, u in kit.get("sources", {}).items():
        srcs[f"brand_{slug}/{fn}"] = u
    src_file.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"brand {slug}: {', '.join(kit['files'].values()) or '(không tìm được ảnh)'} · màu {kit['accent']} → {d}/sheet.jpg (Read để kiểm)")
    return kit


def _simple_icon(slug: str, d: Path) -> dict | None:
    """Simple Icons (CC0): logo SVG một màu + mã màu chính thức. slug = tên hãng viết liền (canva, figma, youtube, tiktok…)."""
    try:
        data = json.loads(_get("https://cdn.jsdelivr.net/npm/simple-icons@13/_data/simple-icons.json", 40))
        items = data if isinstance(data, list) else data.get("icons", [])
        norm = lambda t: re.sub(r"[^a-z0-9]", "", t.lower())
        hit = next((x for x in items if norm(x.get("slug") or x.get("title", "")) == norm(slug) or norm(x.get("title", "")) == norm(slug)), None)
        if not hit:
            return None
        sl = hit.get("slug") or norm(hit["title"])
        u = f"https://cdn.jsdelivr.net/npm/simple-icons@13/icons/{sl}.svg"
        svg = _get(u).decode("utf-8")
        hexc = "#" + hit["hex"].upper()
        svg = svg.replace("<svg ", f'<svg fill="{hexc}" ', 1)
        f = d / "logo.svg"
        f.write_text(svg, encoding="utf-8")
        (d / "logo_white.svg").write_text(svg.replace(f'fill="{hexc}"', 'fill="#FFFFFF"', 1), encoding="utf-8")
        return {"file": f, "hex": hexc, "url": u}
    except Exception:
        return None


def _sheet(d: Path, kit: dict):
    import cv2
    import numpy as np
    tiles = []
    for name in ("logo", "icon", "og"):
        fn = kit["files"].get(name)
        if not fn or fn.endswith(".svg"):
            continue
        im = cv2.imread(str(d / fn), cv2.IMREAD_UNCHANGED)
        if im is None:
            continue
        if im.ndim == 2:
            im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
        if im.shape[2] == 4:
            a = im[..., 3:4] / 255.0
            im = (im[..., :3] * a + 40 * (1 - a)).astype(np.uint8)
        h, w = im.shape[:2]
        s = 300 / max(h, w)
        im = cv2.resize(im, (max(1, int(w * s)), max(1, int(h * s))))
        t = np.full((320, 320, 3), 40, np.uint8)
        y, x = (320 - im.shape[0]) // 2, (320 - im.shape[1]) // 2
        t[y:y + im.shape[0], x:x + im.shape[1]] = im
        cv2.putText(t, name, (8, 312), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        tiles.append(t)
    c = kit["accent"].lstrip("#")
    sw = np.zeros((320, 160, 3), np.uint8); sw[:] = (int(c[4:6], 16), int(c[2:4], 16), int(c[0:2], 16))
    tiles.append(sw)
    cv2.imwrite(str(d / "sheet.jpg"), np.hstack(tiles))


def _chrome() -> str:
    from .hyper.runtime import managed_chrome
    c = managed_chrome()
    if not c:
        raise RuntimeError("chưa có Chrome chạy ngầm của HyperFrames — mở app một lần để app tự cài")
    return c


def webshot(pdir, url: str, name: str | None = None, w: int = 1280, h: int = 800) -> Path:
    """ảnh chụp trang web thật (khung trình duyệt máy tính, cuộn đầu trang)."""
    pdir = Path(pdir)
    if not url.startswith("http"):
        url = "https://" + url
    out = pdir / "assets_web" / (name or f"web_{_slug(url)}.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    png = out.with_suffix(".png")
    subprocess.run([_chrome(), "--headless", "--hide-scrollbars", "--disable-gpu", f"--window-size={int(w)},{int(h)}",
                    "--virtual-time-budget=6000", f"--user-agent={UA}", f"--screenshot={png}", url],
                   capture_output=True, timeout=90)
    if not png.exists():
        raise RuntimeError(f"không chụp được {url}")
    if out.suffix.lower() != ".png":
        import cv2
        cv2.imwrite(str(out), cv2.imread(str(png)), [cv2.IMWRITE_JPEG_QUALITY, 92]); png.unlink()
    src_file = pdir / "assets_web" / "illus_sources.json"
    try:
        srcs = json.loads(src_file.read_text(encoding="utf-8"))
    except Exception:
        srcs = {}
    srcs[out.name] = url
    src_file.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"webshot → {out} (Read để kiểm: đúng trang, không bị bảng cookie / đăng nhập che)")
    return out


def _waist_cut(bgr, a):
    """người → cắt ngang THẮT LƯNG (đỉnh đầu + ~3,3 chiều cao mặt): bán thân đẹp hơn cả người (góp ý người dùng). Không thấy mặt → giữ nguyên."""
    import numpy as np
    try:
        import mediapipe as mp
        with mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5) as fd:
            r = fd.process(bgr[..., ::-1].copy())
        if not r.detections:
            return a, False
        bb = max(r.detections, key=lambda d: d.location_data.relative_bounding_box.height).location_data.relative_bounding_box
        h = a.shape[0]
        fy, fh = bb.ymin * h, bb.height * h
        ys = np.where(a.max(axis=1) > 0.1)[0]
        head_top = ys.min() if len(ys) else fy - fh * 0.35
        waist = int(head_top + fh * 3.3 + fh * 0.6)
        if waist < ys.max() - fh * 0.3:
            a = a.copy(); a[waist:] = 0
            return a, True
    except Exception:
        pass
    return a, False


def paper(pdir, src: str, name: str | None = None, stroke: int = 22, full: bool = False) -> Path:
    """ảnh → xoá nền (HyperFrames remove-background, mô hình chạy trên máy) → sticker giấy: viền trắng cắt theo dáng,
    vân giấy nhẹ, bóng đổ mềm. → assets_web/p_<tên>.png"""
    import cv2
    import numpy as np
    from .hyper import runtime as R
    pdir = Path(pdir)
    sp = Path(src) if Path(src).is_absolute() else pdir / (src if "/" in src else f"assets_web/{src}")
    out = pdir / "assets_web" / (name or f"p_{sp.stem}.png")
    cut = out.with_name(out.stem + "_cut.png")
    r = R.run_cli(["remove-background", str(sp), "-o", str(cut)], cwd=pdir, timeout=600)
    if not cut.exists():
        raise RuntimeError("xoá nền lỗi: " + ((r.stdout or "") + (r.stderr or ""))[-400:])
    im = cv2.imread(str(cut), cv2.IMREAD_UNCHANGED)
    a = im[..., 3].astype(np.float32) / 255
    a = cv2.erode(a, np.ones((3, 3), np.uint8), iterations=2)          # bỏ quầng màu nền cũ ở mép (tóc, vai)
    if not full:
        a, cut_w = _waist_cut(im[..., :3], a)
    ys, xs = np.where(a > 0.1)
    pad = stroke * 3
    y0, y1, x0, x1 = max(0, ys.min() - pad), min(a.shape[0], ys.max() + pad), max(0, xs.min() - pad), min(a.shape[1], xs.max() + pad)
    im, a = im[y0:y1, x0:x1], a[y0:y1, x0:x1]
    im = cv2.copyMakeBorder(im, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
    a = cv2.copyMakeBorder(a, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * stroke + 1, 2 * stroke + 1))
    border = cv2.GaussianBlur(cv2.dilate((a > 0.5).astype(np.uint8), k).astype(np.float32), (0, 0), 1.2)
    hgt, wid = a.shape
    rng = np.random.default_rng(7)
    paper_tex = np.clip(0.95 + cv2.GaussianBlur(rng.normal(0, 0.05, (hgt, wid)).astype(np.float32), (0, 0), 1.5), 0.86, 1.0)
    rgb = np.dstack([paper_tex * 250, paper_tex * 247, paper_tex * 240])          # giấy trắng ngà (BGR)
    fg = im[..., :3].astype(np.float32)
    rgb = rgb * (1 - a[..., None]) + fg * a[..., None]
    sh = cv2.GaussianBlur(np.roll(np.roll(border, int(stroke * 0.8), 0), int(stroke * 0.4), 1), (0, 0), stroke * 0.9) * 0.45
    alpha = np.maximum(border, sh)
    rgb = rgb * (border[..., None]) + 0 * (1 - border[..., None])                 # bóng đen mờ ngoài viền
    outimg = np.dstack([rgb, alpha * 255]).clip(0, 255).astype(np.uint8)
    cv2.imwrite(str(out), outimg)
    cut.unlink(missing_ok=True)
    print(f"paper → {out} ({wid}×{hgt}) — Read để kiểm viền / tóc / tay")
    return out


# ------------------------------------------------------------------ logo ĐÚNG của app / thương hiệu được nhắc tên
KNOWN = {   # tên người nói → tên miền (logo / icon app chính thức)
    "tiktok": "tiktok.com", "youtube": "youtube.com", "facebook": "facebook.com", "instagram": "instagram.com", "reels": "instagram.com",
    "zalo": "zalo.me", "messenger": "messenger.com", "chatgpt": "chatgpt.com", "openai": "openai.com", "claude": "claude.ai",
    "gemini": "gemini.google.com", "google": "google.com", "canva": "canva.com", "capcut": "capcut.com", "shopee": "shopee.vn",
    "lazada": "lazada.vn", "tiki": "tiki.vn", "grab": "grab.com", "momo": "momo.vn", "vnpay": "vnpay.vn", "netflix": "netflix.com",
    "spotify": "spotify.com", "telegram": "telegram.org", "twitter": "x.com", "threads": "threads.net",
    "linkedin": "linkedin.com", "apple": "apple.com", "iphone": "apple.com", "samsung": "samsung.com", "microsoft": "microsoft.com",
    "windows": "microsoft.com", "macos": "apple.com", "adobe": "adobe.com", "premiere": "adobe.com", "figma": "figma.com",
    "notion": "notion.so", "elevenlabs": "elevenlabs.io", "midjourney": "midjourney.com", "vinfast": "vinfastauto.com",
    "vinhomes": "vinhomes.vn", "bmw": "bmw.com", "tesla": "tesla.com", "toyota": "toyota.com", "honda": "honda.com",
}
OWN = {"ccut", "c-cut", "c cut"}             # app của chính người dùng: logo đóng gói sẵn trong app


def _norm_name(s: str) -> str:
    import unicodedata as U
    s = U.normalize("NFD", s.lower().replace("đ", "d"))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if U.category(c) != "Mn"))


def logo(pdir, name: str, domain: str | None = None) -> Path:
    """BIỂU TƯỢNG (symbol) / icon app CHÍNH THỨC → assets_web/logo_<tên>.png (ảnh vuông, nền trong / nền icon app).
    Chỉ lấy biểu tượng: bản logo có chữ (tên hãng) bị bỏ qua.
    C-Cut: logo đóng gói sẵn (assets/brand). Hãng khác: icon chính thức theo tên miền (apple-touch-icon → favicon 256px),
    rồi Simple Icons (SVG CC0) nếu chỉ có bản vector."""
    from .paths import ROOT
    pdir = Path(pdir)
    key = _norm_name(name)
    out = pdir / "assets_web" / f"logo_{key}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    srcs_f = pdir / "assets_web" / "illus_sources.json"
    try:
        srcs = json.loads(srcs_f.read_text(encoding="utf-8"))
    except Exception:
        srcs = {}
    if key in {_norm_name(x) for x in OWN}:
        for cand in (ROOT / "assets" / "brand" / "mark_512.png", ROOT / "packaging" / "icon.png"):
            if cand.exists():
                out.write_bytes(cand.read_bytes())
                srcs[out.name] = "logo C-Cut (đóng gói trong app)"
                srcs_f.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
                return out
    dom = domain or KNOWN.get(key) or (name if "." in name else None)
    best = None
    tmp = out.with_suffix(".tmp.png")
    kit = {}
    try:
        kit = brand(pdir, dom, key) if dom else {}
    except BaseException:
        kit = {}
    bdir = pdir / "assets_web" / f"brand_{key}"
    files = (kit or {}).get("files", {})
    srcmap = (kit or {}).get("sources", {})

    def _read(f):
        try:
            from PIL import Image
            im = Image.open(f)
            if getattr(im, "info", {}).get("sizes"):        # .ico nhiều cỡ → lấy cỡ lớn nhất
                im.size = max(im.info["sizes"])
            return cv2.cvtColor(np.array(im.convert("RGBA")), cv2.COLOR_RGBA2BGRA)
        except Exception:
            return cv2.imread(str(f), cv2.IMREAD_UNCHANGED)

    _symbol = pick_symbol

    # 1. icon app / apple-touch-icon chính thức đủ nét (≥120px) — chính là biểu tượng của hãng
    f = bdir / files.get("icon", "")
    if files.get("icon") and f.is_file():
        im = _read(f)
        if im is not None and min(im.shape[:2]) >= 120:
            cv2.imwrite(str(tmp), im)
            best = (tmp, srcmap.get(f.name, dom))
    # 2. Wikimedia Commons: biểu tượng (ưu tiên tên có icon / symbol), bản có chữ → cắt phần biểu tượng
    if not best:
        best = _commons_symbol(name, tmp, _symbol)
    # 3. Simple Icons — chỉ nhận biểu tượng (ảnh "logo" trên trang chủ không dùng: hay dính ảnh sản phẩm / banner)
    if not best:
        svg = bdir / "logo.svg"
        if not svg.exists():
            bdir.mkdir(parents=True, exist_ok=True)
            _simple_icon(key, bdir)
        if svg.exists():
            r = svg.with_name("logo_si.png")
            html = svg.with_suffix(".html")
            html.write_text('<html><body style="margin:0;background:transparent"><img src="logo.svg" '
                            'style="width:440px;height:440px;margin:36px;object-fit:contain"></body></html>', encoding="utf-8")
            subprocess.run([_chrome(), "--headless", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                            "--window-size=512,512", f"--screenshot={r}", html.as_uri()], capture_output=True, timeout=60)
            if r.exists():
                best = _symbol(r, "Simple Icons (CC0)")
    # 4. favicon (Google, tới 256px), rồi icon nhỏ của trang phóng to — cuối cùng mới dùng vì kém nét
    if not best and dom:
        try:
            tmp.write_bytes(_get(f"https://www.google.com/s2/favicons?domain={dom}&sz=256"))
            im = cv2.imread(str(tmp), cv2.IMREAD_UNCHANGED)
            if im is not None and min(im.shape[:2]) >= 64:
                best = (tmp, f"favicon {dom}")
        except Exception:
            pass
    if not best:
        f = bdir / files.get("icon", "")
        im = _read(f) if files.get("icon") and f.is_file() else None
        if im is None and tmp.exists():
            im = cv2.imread(str(tmp), cv2.IMREAD_UNCHANGED)
        if im is not None and min(im.shape[:2]) >= 32:
            k = 256 / max(im.shape[:2])
            cv2.imwrite(str(tmp), cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC))
            best = (tmp, f"icon nhỏ {dom} (phóng to — nên thay ảnh nét hơn)")
    if not best and not dom:
        raise SystemExit(f"chưa tìm được biểu tượng “{name}” — chạy: tools logo <dự-án> \"{name}\" <tên-miền> (vd zalo.me)")
    if not best:
        raise SystemExit(f"không lấy được BIỂU TƯỢNG {name} ({dom}) — tải tay ảnh biểu tượng chính thức (không chữ) vào assets_web/logo_{key}.png")
    im = cv2.imread(str(best[0]), cv2.IMREAD_UNCHANGED)
    cv2.imwrite(str(out), im)
    for t in out.parent.glob(f"logo_{key}.tmp*"):           # dọn ảnh tạm (ứng viên đã thử)
        t.unlink(missing_ok=True)
    srcs[out.name] = best[1]
    srcs_f.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def pick_symbol(f, label):
    """ảnh logo → (file biểu tượng, nguồn): không có chữ thì dùng luôn; có chữ thì cắt riêng phần biểu tượng; toàn chữ → None."""
    f = Path(f)
    if not logo_has_text(f):
        return (f, label)
    c = symbol_crop(f, f.with_name(f.stem + "_sym.png"))
    return (c, label + " (cắt phần biểu tượng)") if c else None


def _norm_words(s: str) -> str:
    import unicodedata as U
    s = U.normalize("NFD", s.lower().replace("đ", "d").replace("_", " "))
    return "".join(c for c in s if U.category(c) != "Mn")


def _commons_symbol(brand: str, tmp: Path, pick):
    """Wikimedia Commons: tìm logo SVG của hãng (tải bản PNG 512px), ưu tiên tên có icon / symbol; trả (file, nguồn) qua pick()."""
    ua = {"User-Agent": "Mozilla/5.0 ccut"}
    try:
        q = urllib.parse.urlencode({"action": "query", "list": "search", "srnamespace": 6, "format": "json", "srlimit": 12,
                                    "srsearch": f"{brand} logo filetype:svg"})
        r = json.loads(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=ua), timeout=20).read())
        hits = r.get("query", {}).get("search") or []
    except Exception:
        return None
    b0 = _norm_name(brand)
    btok = "_" + "_".join(re.findall(r"[a-z0-9]+", _norm_words(brand))) + "_"

    def same(t):                                            # đúng tên hãng (cả từ), không dính tên khác (Grab ≠ PyGrabber)
        tt = "_" + "_".join(re.findall(r"[a-z0-9]+", _norm_words(t))) + "_"
        return btok in tt or ("_" + b0 + "_") in tt
    SETS = r"tabler|font.?awesome|octicon|bootstrap|feather|ionicon|simple.?icons|icons8|material|remix|boxicon|glyphicon|devicon|\bcib\b|\bbi\b"

    def rank(h):
        t = h["title"].lower()
        return (not same(h["title"]), not re.search(r"icon|symbol|logomark|favicon|emblem|glyph|\bmark\b", t),
                bool(re.search(r"wordmark|text|full|horizontal|old|19\d\d|200\d|201[0-5]", t)))
    for h in sorted(hits, key=rank)[:5]:
        if not same(h["title"]):
            break
        if re.search(SETS, h["title"].lower()):            # icon vẽ lại trong bộ icon chung — không phải logo chính thức
            continue
        name = h["title"].removeprefix("File:").replace(" ", "_")
        try:
            data = urllib.request.urlopen(urllib.request.Request(
                f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(name)}?width=512", headers=ua), timeout=30).read()
        except Exception:
            continue
        if not data.startswith(b"\x89PNG"):
            continue
        f = tmp.with_name(tmp.stem + f"_c{len(name) % 97}.png")
        f.write_bytes(data)
        if re.search(r"\b(app.?)?icon\b", h["title"].lower()):   # icon app chính thức: dùng nguyên (kể cả có chữ trong ô)
            _fill_icon(f)
            got = (f, f"https://commons.wikimedia.org/wiki/File:{name}")
        else:
            got = pick(f, f"https://commons.wikimedia.org/wiki/File:{name}")
        if got:
            return got
    return None


def _fill_icon(f: Path):
    """icon app vẽ để đặt trên nền trắng (lòng icon trong suốt, vd Zalo) → đổ trắng phần lòng kín, để không thủng trên video."""
    im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
    if im is None or im.ndim < 3 or im.shape[2] < 4:
        return
    a = (im[..., 3] > 127).astype(np.uint8)
    ff = np.pad(1 - a, 1, constant_values=1).copy()
    cv2.floodFill(ff, None, (0, 0), 2)
    holes = (ff[1:-1, 1:-1] == 1)
    if holes.sum() > a.sum() * 0.5:                          # lòng chiếm phần lớn icon → đây là nền trắng của icon
        im[holes] = (255, 255, 255, 255)
        cv2.imwrite(str(f), im)


def symbol_crop(src, out) -> Path | None:
    """logo có chữ (biểu tượng + tên hãng) → cắt riêng phần BIỂU TƯỢNG. Chữ = các mảng cùng cỡ xếp thành hàng (≥3 ký tự liền nhau);
    phần còn lại (mảng lớn nhất và các mảng sát nó) là biểu tượng. None nếu không còn biểu tượng (logo toàn chữ)."""
    rgb, al, opaque, bgcol = _logo_rgba(Path(src))
    if opaque:
        return None
    h, w = al.shape
    k = 600 / max(h, w)
    m = (cv2.resize(al, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    ids = [i for i in range(1, n) if st[i, 4] > m.size * 0.0004]
    if not ids:
        return None
    hs = {i: st[i, 3] for i in ids}
    cy = {i: st[i, 1] + st[i, 3] / 2 for i in ids}
    # nhóm ký tự: cùng hàng, cao gần bằng nhau, đứng sát nhau
    par = {i: i for i in ids}
    def root(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for a in ids:
        for b in ids:
            if a < b:
                ha, hb = hs[a], hs[b]
                if max(ha, hb) > 1.45 * min(ha, hb) or abs(cy[a] - cy[b]) > 0.35 * max(ha, hb):
                    continue
                gap = max(st[a, 0], st[b, 0]) - min(st[a, 0] + st[a, 2], st[b, 0] + st[b, 2])
                if gap < 0.55 * max(ha, hb):
                    par[root(a)] = root(b)
    groups = {}
    for i in ids:
        groups.setdefault(root(i), []).append(i)
    def is_row(g):                                           # hàng chữ: ≥3 mảng, nằm thẳng một dòng, dài theo chiều ngang
        if len(g) < 3:
            return False                                     # (cánh hoa / chi tiết xếp vòng quanh tâm không phải chữ)
        gx0, gy0 = min(st[i, 0] for i in g), min(st[i, 1] for i in g)
        gx1, gy1 = max(st[i, 0] + st[i, 2] for i in g), max(st[i, 1] + st[i, 3] for i in g)
        return (gy1 - gy0) <= 1.35 * max(hs[i] for i in g) and (gx1 - gx0) >= 1.8 * (gy1 - gy0)
    text = {i for g in groups.values() if is_row(g) for i in g}
    rest = [i for i in ids if i not in text]
    if not rest:
        return None
    for i in [i for i in rest]:                              # dấu nhỏ nằm trong hàng chữ (dấu chấm, dấu thanh) → bỏ
        if st[i, 4] < m.size * 0.004 and any(abs(cy[i] - cy[t]) < hs[t] for t in text):
            rest.remove(i)
    if not rest:
        return None
    main = max(rest, key=lambda i: st[i, 4])
    x0, y0, x1, y1 = st[main, 0], st[main, 1], st[main, 0] + st[main, 2], st[main, 1] + st[main, 3]
    changed = True
    while changed:                                           # gom các mảng sát biểu tượng chính
        changed = False
        for i in rest:
            bx0, by0, bx1, by1 = st[i, 0], st[i, 1], st[i, 0] + st[i, 2], st[i, 1] + st[i, 3]
            pad = 0.12 * max(x1 - x0, y1 - y0)
            if (bx0 < x1 + pad and bx1 > x0 - pad and by0 < y1 + pad and by1 > y0 - pad) and not (x0 <= bx0 and bx1 <= x1 and y0 <= by0 and by1 <= y1):
                x0, y0, x1, y1 = min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1)
                changed = True
    if (x1 - x0) * (y1 - y0) < m.size * 0.03 or min(x1 - x0, y1 - y0) < 25:
        return None
    inside = [i for i in ids if x0 <= st[i, 0] and st[i, 0] + st[i, 2] <= x1 and y0 <= st[i, 1] and st[i, 1] + st[i, 3] <= y1]
    keep = np.isin(lab, inside)                              # mọi mảng nằm TRONG khung biểu tượng (cả chi tiết bên trong, vd ngôi sao giữa hoa)
    keep = cv2.resize(cv2.dilate(keep.astype(np.uint8), np.ones((5, 5), np.uint8)), (w, h), interpolation=cv2.INTER_NEAREST).astype(bool)
    X0, Y0, X1, Y1 = int(x0 / k), int(y0 / k), int(np.ceil(x1 / k)), int(np.ceil(y1 / k))
    a2 = (al * keep)[Y0:Y1, X0:X1]
    bgr = (rgb[Y0:Y1, X0:X1] * 255).astype(np.uint8)
    cv2.imwrite(str(out), np.dstack([bgr, (a2 * 255).astype(np.uint8)]))
    return Path(out)


def logo_glow(src: Path, accent: str | None = None) -> Path:
    """logo → bản PHÁT SÁNG không viền: quầng sáng màu thương hiệu (2 lớp mềm) quanh nét logo; logo tối (TikTok đen…) chuyển trắng
    để nổi trên nền đã làm tối. → <tên>_glow.png (lớn gấp ~1,8 lần logo, logo nằm giữa)."""
    src = Path(src)
    out = src.with_name(src.stem + "_glow.png")
    im = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"không đọc được {src}")
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGRA)
    if im.shape[2] == 3:                                    # logo không nền trong
        bd = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]])
        if np.median(bd, 0).min() >= 235:                   # nền trắng → bỏ nền trắng / gần trắng ở mép
            a = 255 - cv2.inRange(im, (235, 235, 235), (255, 255, 255))
        else:                                               # icon app nền màu → giữ nguyên cả ô, chỉ bo góc
            h0, w0 = im.shape[:2]
            r = int(min(h0, w0) * 0.22)
            a = np.zeros((h0, w0), np.uint8)
            cv2.rectangle(a, (r, 0), (w0 - 1 - r, h0 - 1), 255, -1)
            cv2.rectangle(a, (0, r), (w0 - 1, h0 - 1 - r), 255, -1)
            for cx, cy in ((r, r), (w0 - 1 - r, r), (r, h0 - 1 - r), (w0 - 1 - r, h0 - 1 - r)):
                cv2.circle(a, (cx, cy), r, 255, -1, cv2.LINE_AA)
        im = np.dstack([im, a])
    s = 512 / max(im.shape[:2])
    im = cv2.resize(im, (int(im.shape[1] * s), int(im.shape[0] * s)), interpolation=cv2.INTER_AREA)
    a = im[..., 3].astype(np.float32) / 255
    rgb = im[..., :3].astype(np.float32)
    on = a > 0.5
    lum = (rgb[on] @ np.array([0.114, 0.587, 0.299], np.float32)).mean() / 255 if on.any() else 1
    if lum < 0.28:                                          # logo đen / tối: GIỮ màu gốc, đặt trên ô trắng bo góc (kiểu icon app)
        h0, w0 = im.shape[:2]
        side = int(max(h0, w0) / 0.68)
        r = int(side * 0.23)
        tile_a = np.zeros((side, side), np.uint8)
        cv2.rectangle(tile_a, (r, 0), (side - r, side), 255, -1)
        cv2.rectangle(tile_a, (0, r), (side, side - r), 255, -1)
        for cx, cy in ((r, r), (side - r, r), (r, side - r), (side - r, side - r)):
            cv2.circle(tile_a, (cx, cy), r, 255, -1, cv2.LINE_AA)
        tile = np.full((side, side, 3), 255, np.float32)
        oy, ox = (side - h0) // 2, (side - w0) // 2
        tile[oy:oy + h0, ox:ox + w0] = rgb * a[..., None] + tile[oy:oy + h0, ox:ox + w0] * (1 - a[..., None])
        rgb, a = tile, tile_a.astype(np.float32) / 255
        im = np.dstack([rgb, a * 255]).astype(np.uint8)
        accent = accent or "#FFFFFF"
    if accent:
        acc = np.array([int(accent.lstrip("#")[i:i + 2], 16) for i in (4, 2, 0)], np.float32)
    else:                                                    # màu thương hiệu = màu bão hoà nhất trên logo
        hsv = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV)
        m = on & (hsv[..., 1] > 90) & (hsv[..., 2] > 90)
        acc = rgb[m].mean(0) if m.sum() > 50 else np.array([255, 200, 120], np.float32)
    H, W = im.shape[:2]
    P = int(max(H, W) * 0.42)
    A = np.zeros((H + 2 * P, W + 2 * P), np.float32)
    A[P:P + H, P:P + W] = a
    g1 = cv2.GaussianBlur(A, (0, 0), max(H, W) * 0.10)
    g2 = cv2.GaussianBlur(A, (0, 0), max(H, W) * 0.035)
    glow = np.clip(g1 * 1.25 + g2 * 0.9, 0, 1)
    C = np.zeros((H + 2 * P, W + 2 * P, 3), np.float32)
    C[:] = acc
    L = np.zeros_like(C)
    L[P:P + H, P:P + W] = rgb
    La = A
    outa = np.clip(La + glow * (1 - La) * 0.85, 0, 1)
    outc = (L * La[..., None] + C * (glow * (1 - La) * 0.85)[..., None]) / np.maximum(outa[..., None], 1e-4)
    cv2.imwrite(str(out), np.dstack([np.clip(outc, 0, 255), outa * 255]).astype(np.uint8))
    return out



# ------------------------------------------------------------------ logo trên TẤM NỀN (thay quầng sáng / làm trắng)
def _logo_rgba(src: Path):
    """đọc logo → (BGR float 0..1, alpha 0..1, opaque) đã cắt sát nét. opaque = ảnh kín nền (icon app có nền riêng)."""
    im = cv2.imread(str(src), cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"không đọc được {src}")
    if im.ndim == 2:
        im = cv2.cvtColor(im, cv2.COLOR_GRAY2BGR)
    opaque, bgcol = False, None
    if im.shape[2] == 3:                                    # không có lớp trong suốt → tách nền đều màu theo viền ảnh
        bd = np.concatenate([im[0], im[-1], im[:, 0], im[:, -1]]).astype(np.float32)
        if bd.std(0).max() < 12:
            bgcol = tuple(float(v) / 255 for v in np.median(bd, 0))   # logo vẽ sẵn trên nền màu → dùng chính màu nền đó làm tấm
            d = np.abs(im.astype(np.float32) - np.median(bd, 0)).max(2)
            al = np.clip((d - 12) / 40, 0, 1)
        else:
            al, opaque = np.ones(im.shape[:2], np.float32), True
        im = np.dstack([im, (al * 255).astype(np.uint8)])
    rgb = im[..., :3].astype(np.float32) / 255
    al = im[..., 3].astype(np.float32) / 255
    if not opaque and (al > 0.95).mean() > 0.97:
        opaque = True
    ys, xs = np.where(al > 0.05)
    if len(ys):
        rgb, al = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1], al[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return rgb, al, opaque, bgcol


def logo_has_text(src) -> bool:
    """logo CÓ CHỮ (wordmark / biểu tượng kèm tên) hay CHỈ biểu tượng. Có chữ → đặt lên tấm nền; chỉ biểu tượng → giữ kiểu phát sáng.
    Dấu hiệu chữ: logo dài ngang / cao dọc hẳn, hoặc nhiều mảng nhỏ cùng cỡ xếp thành hàng (các ký tự)."""
    rgb, al, opaque, bgcol = _logo_rgba(Path(src))
    h, w = al.shape
    if opaque or h < 4 or w < 4:
        return False
    if w / h > 1.75 or h / w > 1.9:
        return True
    k = 400 / max(h, w)
    m = (cv2.resize(al, (max(1, int(w * k)), max(1, int(h * k))), interpolation=cv2.INTER_AREA) > 0.5).astype(np.uint8)
    n, _, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    H = m.shape[0]
    big = [s for s in st[1:] if s[4] > m.size * 0.001]
    small = [s for s in big if s[3] < H * 0.32]              # mảng thấp hơn 1/3 logo = cỡ ký tự
    if len(small) < 3:
        return False
    hs = np.array([s[3] for s in small], np.float32)
    ys = np.array([s[1] + s[3] / 2 for s in small], np.float32)
    rows = np.abs(ys[:, None] - ys[None, :]) < np.median(hs) * 0.6   # cùng hàng chữ
    return int(rows.sum(1).max()) >= 4


def logo_is_light(src) -> bool:
    """logo trắng / rất sáng (bản logo trắng) → cần nền ĐEN; còn lại nền TRẮNG."""
    rgb, al, opaque, bgcol = _logo_rgba(Path(src))
    if opaque or bgcol:
        return False
    on = al > 0.5
    if not on.any():
        return False
    lum = rgb[on] @ np.array([0.114, 0.587, 0.299], np.float32)
    return float(np.median(lum)) > 0.82


def _round_mask(h: int, w: int, r: int) -> np.ndarray:
    m = np.zeros((h, w), np.uint8)
    r = max(1, min(r, h // 2, w // 2))
    cv2.rectangle(m, (r, 0), (w - 1 - r, h - 1), 255, -1)
    cv2.rectangle(m, (0, r), (w - 1, h - 1 - r), 255, -1)
    for cx, cy in ((r, r), (w - 1 - r, r), (r, h - 1 - r), (w - 1 - r, h - 1 - r)):
        cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return m.astype(np.float32) / 255


def _accent(rgb: np.ndarray, al: np.ndarray):
    """màu chủ đạo của logo (BGR 0..1) cho quầng sáng; logo đen / xám → None."""
    u8 = (np.clip(rgb, 0, 1) * 255).astype(np.uint8)
    hsv = cv2.cvtColor(u8, cv2.COLOR_BGR2HSV)
    m = (al > 0.5) & (hsv[..., 1] > 80) & (hsv[..., 2] > 60)
    if m.sum() < max(30, (al > 0.5).sum() * 0.05):
        return None
    c = rgb[m].mean(0)
    hh, ll, ss = colorsys.rgb_to_hls(float(c[2]), float(c[1]), float(c[0]))
    r, g, b = colorsys.hls_to_rgb(hh, min(0.62, max(0.5, ll)), min(1.0, ss * 1.1 + 0.1))   # quầng tươi, không quá tối
    return np.array([b, g, r], np.float32)


def logo_plate(src) -> Path:
    """logo / biểu tượng thật → ô KÍNH TRẮNG bo góc kiểu icon app hiện đại (gradient trắng → xám rất nhạt, viền sáng mảnh,
    vệt sáng mép trên), logo GIỮ NGUYÊN MÀU ở giữa (không làm sáng / không đổi màu), quầng sáng nhẹ màu thương hiệu
    nhạt dần ra ngoài + bóng đổ mềm. Logo trắng → ô kính TỐI. Icon app kín ô (có nền riêng) → giữ ô của nó, bo góc + quầng.
    Biểu tượng → ô vuông; logo dài (hãng chỉ có chữ) → ô dài theo logo. → <tên>_glass.png cạnh file gốc."""
    src = Path(src)
    out = src.with_name(src.stem + "_glass.png")
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    rgb, al, opaque, bgcol = _logo_rgba(src)
    h, w = al.shape
    T = 720                                                  # cỡ lớn nhất của phần logo / icon
    k = T / max(h, w)
    nw, nh = max(1, round(w * k)), max(1, round(h * k))
    it = cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC
    rgb = np.clip(cv2.resize(rgb, (nw, nh), interpolation=it), 0, 1)
    al = np.clip(cv2.resize(al, (nw, nh), interpolation=it), 0, 1)
    acc = _accent(rgb, al)
    if opaque:                                               # icon app kín ô: chính nó là ô
        pw, ph = nw, nh
        r = int(min(pw, ph) * 0.22)
        ta = _round_mask(ph, pw, r)
        C = rgb.copy()
        dark = False
        if acc is None:
            acc = _accent(rgb, np.ones_like(al))
    else:
        light = logo_is_light(src) and not bgcol
        if max(nw, nh) / min(nw, nh) < 1.9:                  # biểu tượng → ô vuông, logo chiếm ~62%
            side = int(max(nw, nh) / 0.62)
            pw = ph = side
        else:                                                # logo dài → ô dài theo logo
            pad = int(max(0.30 * min(nw, nh), 0.07 * max(nw, nh)))
            pw, ph = nw + 2 * pad, nh + 2 * pad
        r = int(min(pw, ph) * 0.24)
        ta = _round_mask(ph, pw, r)
        yy = np.linspace(0, 1, ph, dtype=np.float32)[:, None, None]
        if bgcol:                                            # logo vẽ sẵn trên nền màu → ô màu đó (gradient nhẹ)
            base = np.array(bgcol, np.float32)
            C = np.broadcast_to(base * (1.04 - 0.10 * yy), (ph, pw, 3)).copy()
            dark = False
        elif light:                                          # logo trắng → kính tối
            C = np.broadcast_to(np.array([0.20, 0.17, 0.16], np.float32) * (1 - 0.45 * yy), (ph, pw, 3)).copy()
            dark = True
        else:                                                # kính trắng: trắng → xám lạnh rất nhạt
            top, bot = np.array([1.0, 1.0, 1.0], np.float32), np.array([0.93, 0.91, 0.90], np.float32)
            C = (top * (1 - yy) + bot * yy) * np.ones((ph, pw, 3), np.float32)
            dark = False
        sheen = np.clip(1 - yy[..., 0] / 0.5, 0, 1) ** 2 * 0.06   # vệt sáng phủ nửa trên (kính)
        C = np.clip(C + (1 - C) * sheen[..., None] * (3 if dark else 1), 0, 1)
        oy, ox = (ph - nh) // 2, (pw - nw) // 2
        C[oy:oy + nh, ox:ox + nw] = rgb * al[..., None] + C[oy:oy + nh, ox:ox + nw] * (1 - al[..., None])
    # viền: sáng mảnh phía trên, tối nhẹ phía dưới (cảm giác kính có độ dày)
    bw = max(2, int(min(pw, ph) * 0.010))
    edge = np.clip(ta - cv2.erode(ta, np.ones((2 * bw + 1, 2 * bw + 1), np.uint8)), 0, 1)
    yy2 = np.linspace(0, 1, ph, dtype=np.float32)[:, None]
    hi = edge * (1 - yy2)
    lo = edge * yy2
    C = C + (1 - C) * hi[..., None] * (0.55 if dark else 0.8)
    C = C * (1 - lo[..., None] * (0.05 if dark else 0.12))
    if dark:
        C = C + (1 - C) * edge[..., None] * 0.18
    # khung ra: lề cho quầng + bóng
    m = int(min(pw, ph) * 0.42) + 12
    H, W = ph + 2 * m, pw + 2 * m
    A = np.zeros((H, W), np.float32)
    A[m:m + ph, m:m + pw] = ta
    s0 = min(pw, ph)
    if acc is None:
        acc = np.array([1.0, 0.92, 0.80], np.float32) if not dark else np.array([1.0, 0.85, 0.65], np.float32)
    g = cv2.GaussianBlur(A, (0, 0), s0 * 0.16) * 0.55 + cv2.GaussianBlur(A, (0, 0), s0 * 0.07) * 0.35   # quầng gradient 2 lớp
    g = np.clip(g, 0, 0.62)
    sh = np.roll(cv2.GaussianBlur(A, (0, 0), s0 * 0.06), int(s0 * 0.05), axis=0) * 0.45                 # bóng đổ mềm
    # trộn (nhân alpha sẵn): bóng đen → quầng màu → ô
    pc = np.zeros((H, W, 3), np.float32)
    pa = sh.copy()
    pc = pc * (1 - g[..., None]) + acc * g[..., None]
    pa = pa * (1 - g) + g
    Cf = np.zeros((H, W, 3), np.float32)
    Cf[m:m + ph, m:m + pw] = C
    pc = pc * (1 - A[..., None]) + Cf * A[..., None]
    pa = pa * (1 - A) + A
    st = np.where(pa[..., None] > 1e-4, pc / np.maximum(pa[..., None], 1e-4), 0)
    cv2.imwrite(str(out), (np.clip(np.dstack([st, pa]), 0, 1) * 255).astype(np.uint8))
    return out


def plate_box(path) -> tuple[float, float, float, float]:
    """(w, h, lề_bóng_ngang, lề_bóng_dọc) của ảnh tấm — để đặt cỡ theo TẤM chứ không theo cả bóng."""
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    h, w = im.shape[:2]
    on = np.where(im[..., 3] > 250)
    if not len(on[0]):
        return w, h, 0, 0
    return w, h, float(on[1].min()), float(on[0].min())


def vignette(pdir, W: int, H: int) -> Path:
    """lớp làm tối nền (giữa tối vừa, mép tối hơn) — phủ lên video khi logo xuất hiện."""
    out = Path(pdir) / "assets_web" / f"_dim_{W}x{H}.png"
    if out.exists():
        return out
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.45) / (H * 0.55)) ** 2)
    a = np.clip(0.50 + 0.35 * d, 0, 0.88)
    img = np.zeros((H, W, 4), np.uint8)
    img[..., :3] = (14, 8, 6)
    img[..., 3] = (a * 255).astype(np.uint8)
    cv2.imwrite(str(out), img)
    return out
