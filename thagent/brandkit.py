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
    """logo / icon app CHÍNH THỨC → assets_web/logo_<tên>.png (ảnh vuông, nền trong / nền icon app).
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
    if not dom:
        raise SystemExit(f"chưa biết tên miền của “{name}” — chạy: tools logo <dự-án> \"{name}\" <tên-miền> (vd zalo.me)")
    best = None
    try:                                                    # icon app chất lượng cao từ chính trang chủ
        kit = brand(pdir, dom, key)
        for k in ("icon", "logo"):
            f = pdir / "assets_web" / f"brand_{key}" / kit["files"].get(k, "")
            if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
                im = cv2.imread(str(f), cv2.IMREAD_UNCHANGED)
                if im is not None and min(im.shape[:2]) >= 120:
                    best = (f, kit["sources"].get(f.name, dom))
                    break
    except SystemExit:
        pass
    except Exception:
        pass
    if not best:
        try:
            b = _get(f"https://www.google.com/s2/favicons?domain={dom}&sz=256")
            tmp = out.with_suffix(".tmp.png")
            tmp.write_bytes(b)
            im = cv2.imread(str(tmp), cv2.IMREAD_UNCHANGED)
            if im is not None and min(im.shape[:2]) >= 64:
                best = (tmp, f"favicon {dom}")
        except Exception:
            pass
    if not best:                                            # chỉ có logo vector (Simple Icons, CC0) → dựng PNG 512px qua Chrome ngầm
        svg = pdir / "assets_web" / f"brand_{key}" / "logo.svg"
        if not svg.exists():
            _simple_icon(key, svg.parent) if svg.parent.mkdir(parents=True, exist_ok=True) is None else None
        if svg.exists():
            html = svg.with_suffix(".html")
            html.write_text('<html><body style="margin:0;background:transparent"><img src="logo.svg" '
                            'style="width:440px;height:440px;margin:36px"></body></html>', encoding="utf-8")
            tmp = out.with_suffix(".tmp.png")
            subprocess.run([_chrome(), "--headless", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                            "--window-size=512,512", f"--screenshot={tmp}", html.as_uri()], capture_output=True, timeout=60)
            if tmp.exists():
                best = (tmp, "Simple Icons (CC0)")
    if not best:
        raise SystemExit(f"không lấy được logo {name} ({dom}) — tải tay ảnh logo chính thức vào assets_web/logo_{key}.png")
    im = cv2.imread(str(best[0]), cv2.IMREAD_UNCHANGED)
    cv2.imwrite(str(out), im)
    if best[0].name.endswith(".tmp.png"):
        best[0].unlink(missing_ok=True)
    srcs[out.name] = best[1]
    srcs_f.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
    return out
