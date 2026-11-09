"""Tìm + tải video b-roll cho Voice to Motion / Text to Video.

    .venv/bin/python -m thagent.v2m brollsearch <dự-án> "<từ khoá tiếng Anh>"   → ảnh ghép các clip Mixkit (miễn phí, tải thẳng
        được) có đánh số mã → Read ảnh, chọn clip ĐÚNG ý câu → tải: broll <dự-án> mixkit:<mã> v_ten.mp4

    .venv/bin/python -m thagent.v2m broll <dự-án> <url> v_ten.mp4 ["nguồn"]

- Pinterest (pin video) / Pexels (trang video) tải bằng yt-dlp; link .mp4 trực tiếp tải thẳng.
- Chuẩn hoá: H.264, bỏ tiếng, tối đa 1080p và 30 giây (b-roll chỉ hiện vài giây trong khung bo góc) → nhẹ, dựng nhanh.
- Lưu ở <dự-án>/assets_web/, ghi nguồn vào assets_web/illus_sources.json (không hiện trên video).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path


def _ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def fetch(pdir, url: str, name: str, source: str = "") -> Path:
    pdir = Path(pdir)
    out_dir = pdir / "assets_web"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = name if name.lower().endswith(".mp4") else Path(name).stem + ".mp4"
    out = out_dir / name
    if url.startswith("mixkit:"):
        mid = url.split(":", 1)[1].strip()
        url = f"https://assets.mixkit.co/videos/{mid}/{mid}-720.mp4"
        source = source or f"Mixkit {mid}"
    with tempfile.TemporaryDirectory() as td:
        raw = Path(td) / "raw"
        import re as _re
        m = _re.search(r"pexels\.com/(?:[a-z-]+/)?video/(?:[^/]*-)?(\d+)/?", url)
        if m:   # trang video Pexels bị chặn chống bot → tải thẳng file gốc qua đường /download/video/<mã>/
            url = f"https://www.pexels.com/download/video/{m.group(1)}/"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = raw.with_suffix(".mp4")
            raw.write_bytes(urllib.request.urlopen(req, timeout=120).read())
        elif url.lower().split("?")[0].endswith((".mp4", ".mov", ".webm")):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            raw = raw.with_suffix(Path(url.split("?")[0]).suffix)
            raw.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        else:
            import yt_dlp
            opts = {"outtmpl": str(Path(td) / "raw.%(ext)s"), "quiet": True, "no_warnings": True, "noprogress": True, "noplaylist": True,
                    "format": "bv*[height<=1080]+ba/b[height<=1080]/bv*/b", "ffmpeg_location": _ffmpeg(),
                    "http_headers": {"User-Agent": "Mozilla/5.0"}}
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    y.download([url])
            except Exception as e:
                raise SystemExit(f"LỖI: không tải được video từ {url} ({str(e)[:160]}) — "
                                 "Pinterest không được thì thử link Pexels (pexels.com/video/…) hoặc link .mp4 trực tiếp")
            got = [p for p in Path(td).iterdir() if p.name.startswith("raw.")]
            if not got:
                raise SystemExit(f"LỖI: {url} không có video")
            raw = got[0]
        r = subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(raw), "-t", "30", "-an",
                            "-vf", "scale='min(1920,iw)':-2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                            "-pix_fmt", "yuv420p", str(out)], capture_output=True, text=True)
        if r.returncode != 0 or not out.exists():
            raise SystemExit(f"LỖI: chuẩn hoá video thất bại: {r.stderr[-200:]}")
    sj = out_dir / "illus_sources.json"
    src = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
    src[name] = source or url
    sj.write_text(json.dumps(src, ensure_ascii=False, indent=1), encoding="utf-8")
    xem = out_dir / "_xem"
    xem.mkdir(exist_ok=True)
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-i", str(out), "-vf", "fps=1/3,scale=320:-1,tile=4x1", "-frames:v", "1",
                    str(xem / (Path(name).stem + ".jpg"))], capture_output=True)
    info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height", "-of", "csv=p=0",
                           str(out)], capture_output=True, text=True).stdout.split()
    print(f"{out}  ({' '.join(info)})\nxem trước (4 khung, cách 3s): {xem / (Path(name).stem + '.jpg')} — Read để kiểm ĐÚNG nội dung")
    return out


def search(pdir, query: str, n: int = 16) -> Path:
    """Mixkit (miễn phí, không cần đăng ký, link .mp4 trực tiếp): tìm theo từ khoá → ảnh ghép 4×4 khung giữa clip, góc trên ghi mã."""
    import re
    import concurrent.futures as cf
    pdir = Path(pdir)
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    req = urllib.request.Request(f"https://mixkit.co/free-stock-video/{slug}/", headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
    except Exception as e:
        raise SystemExit(f"LỖI: không mở được Mixkit cho “{query}” ({e}) — thử từ khoá khác (1–2 từ tiếng Anh: podcast, smartphone, city…)")
    ids = list(dict.fromkeys(re.findall(r"assets\.mixkit\.co/videos/(\d+)/\1-360\.mp4", html)))[:n]
    if not ids:
        raise SystemExit(f"Mixkit không có clip cho “{query}” — thử từ khoá ngắn hơn / khác (1–2 từ tiếng Anh)")
    out_dir = pdir / "assets_web" / "_tim"
    out_dir.mkdir(parents=True, exist_ok=True)

    def grab(i):
        jpg = out_dir / f"m_{i}.jpg"
        if not jpg.exists():
            subprocess.run([_ffmpeg(), "-v", "error", "-y", "-ss", "2", "-i", f"https://assets.mixkit.co/videos/{i}/{i}-360.mp4", "-frames:v", "1",
                            "-vf", "scale=360:202:force_original_aspect_ratio=decrease,pad=360:202:(ow-iw)/2:(oh-ih)/2", str(jpg)],
                           capture_output=True, env=_ssl_env())
        return i if jpg.exists() else None
    with cf.ThreadPoolExecutor(8) as ex:
        got = [i for i in ex.map(grab, ids) if i]
    import cv2
    import numpy as np
    tiles = []
    for i in got:
        im = cv2.imread(str(out_dir / f"m_{i}.jpg"))
        cv2.rectangle(im, (0, 0), (110, 34), (0, 0, 0), -1)
        cv2.putText(im, i, (6, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 230, 255), 2, cv2.LINE_AA)
        tiles.append(im)
    while len(tiles) % 4:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[r:r + 4]) for r in range(0, len(tiles), 4)])
    dst = out_dir / f"{slug}.jpg"
    cv2.imwrite(str(dst), sheet)
    print(f"{dst}\nmã: {' '.join(got)}\nRead ảnh → chọn clip đúng ý → .venv/bin/python -m thagent.v2m broll {pdir} mixkit:<mã> v_ten.mp4")
    return dst


def _ssl_env():
    import os
    e = dict(os.environ)
    try:
        import certifi
        e.setdefault("SSL_CERT_FILE", certifi.where())
    except Exception:
        pass
    return e


def music_search(query: str = "") -> list[dict]:
    """nhạc nền Mixkit miễn phí (Mixkit License) theo thể loại / tâm trạng: tech-house, upbeat, corporate, cinematic, hip-hop,
    driving, energetic, happy, lo-fi… → mã, tên, thể loại, độ dài."""
    import re
    slug = re.sub(r"[^a-z0-9]+", "-", (query or "upbeat").lower()).strip("-")
    html = ""
    for path in (slug, f"tag/{slug}", f"mood/{slug}", f"genre/{slug}"):
        try:
            req = urllib.request.Request(f"https://mixkit.co/free-stock-music/{path}/", headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
            if "data-audio-player-item-id-value" in html:
                break
        except Exception:
            continue
    out = []
    for blk in html.split('data-audio-player-item-id-value="')[1:]:
        mid = blk.split('"', 1)[0]
        name = re.search(r'item-grid-card__title">\s*([^<]+?)\s*<', blk)
        tags = re.findall(r'meta-links__link"[^>]*>([^<]+)<', blk.split("item-grid__item")[0])
        dur = re.search(r'data-test-id="duration">\s*([\d:]+)', blk)
        if mid.isdigit() and mid not in {o["id"] for o in out}:
            import html as _h
            out.append({"id": mid, "name": _h.unescape(name.group(1)) if name else "?", "tags": [_h.unescape(x) for x in tags[:6]],
                        "dur": dur.group(1) if dur else ""})
    for it in out:
        print(f"mixkit:{it['id']:<6} {it['name']:<26} {it['dur']:>5}  {', '.join(it['tags'])}")
    if not out:
        print(f"không có nhạc cho “{query}” — thử: tech-house, upbeat, corporate, cinematic, hip-hop, driving, energetic, happy")
    return out


def music_fetch(pdir, mid: str) -> Path:
    """tải nhạc Mixkit → <dự-án>/assets_web/m_<mã>.mp3 (dùng: K.music("assets_web/m_<mã>.mp3"))."""
    mid = str(mid).removeprefix("mixkit:")
    out = Path(pdir) / "assets_web" / f"m_{mid}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(f"https://assets.mixkit.co/music/{mid}/{mid}.mp3", headers={"User-Agent": "Mozilla/5.0"})
    out.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    sj = out.parent / "illus_sources.json"
    src = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
    src[out.name] = f"Mixkit music {mid} (Mixkit License)"
    sj.write_text(json.dumps(src, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out}  → trong builder: K.music(\"assets_web/{out.name}\")")
    return out
