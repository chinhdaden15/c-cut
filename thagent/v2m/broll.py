"""Tải video b-roll cho Voice to Motion: ƯU TIÊN Pinterest, không được thì Pexels (hoặc link .mp4 trực tiếp).

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
