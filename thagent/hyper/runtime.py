"""HyperFrames runtime của app — cài/kiểm/gọi CLI đã GHIM phiên bản (không tự cập nhật trong lúc chạy job).

- Phiên bản ghim: assets/hyperframes/package.json + package-lock.json (đi kèm app). Cài vào <ROOT>/tools/hyperframes bằng `npm ci`
  → máy khác cài lại giống hệt. Nâng phiên bản = sửa 2 file đó + chạy bài thử (python -m thagent.hyper selftest), không tự nâng.
- Cần Node.js ≥ 22 (node hệ thống, hoặc <ROOT>/tools/node nếu app tự cài sau), FFmpeg (dùng đúng ffmpeg app đang dùng),
  Chrome (Chrome hệ thống; thiếu thì `hyperframes browser ensure` tải bản riêng).
- Môi trường chạy: tắt telemetry, tắt kiểm tra cập nhật, không tự cài skill cho agent (skill HyperFrames cho Claude là việc khác,
  không thay cho runtime này).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from ..paths import ROOT

PIN_DIR = ROOT / "assets" / "hyperframes"                        # package.json + package-lock.json ghim (đi kèm app)
TOOL_DIR = ROOT / "tools" / "hyperframes"                        # nơi cài (ghi được)
NODE_MIN = 22


def pinned() -> dict:
    d = json.loads((PIN_DIR / "package.json").read_text(encoding="utf-8"))["dependencies"]
    return {"hyperframes": d["hyperframes"], "gsap": d["gsap"]}


def node_exe() -> str | None:
    for c in (ROOT / "tools" / "node" / "bin" / "node", ROOT / "tools" / "node" / "node.exe"):
        if c.exists():
            return str(c)
    return shutil.which("node")


def _node_version(exe: str) -> tuple[int, str]:
    try:
        v = subprocess.run([exe, "-v"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10).stdout.strip()
        return int(re.match(r"v(\d+)", v).group(1)), v
    except Exception:
        return 0, ""


def npm_exe(node: str) -> str | None:
    p = Path(node).parent
    for c in (p / "npm", p / "npm.cmd"):
        if c.exists():
            return str(c)
    return shutil.which("npm")


def cli() -> Path:
    b = TOOL_DIR / "node_modules" / ".bin"
    return b / ("hyperframes.cmd" if os.name == "nt" else "hyperframes")


def cli_cmd() -> list[str]:
    """[node, bin/hyperframes.mjs] — gọi thẳng node (không qua shim .cmd của npm: Windows xử lý tham số .cmd khác, dễ lỗi)."""
    js = TOOL_DIR / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    node = node_exe()
    return [node, str(js)] if node and js.exists() else [str(cli())]


def gsap_js() -> Path:
    return TOOL_DIR / "node_modules" / "gsap" / "dist" / "gsap.min.js"


def ffmpeg_exe() -> str | None:
    return shutil.which("ffmpeg")


WRAPPER = TOOL_DIR / "chrome-wrapper.sh"


def browser_wrapper() -> str | None:
    """Chrome render của HyperFrames chạy KHÔNG dùng thiết bị âm thanh thật (--disable-audio-output --mute-audio) và KHÔNG dò proxy
    (--no-proxy-server — render chỉ đọc file cục bộ): loa/tai nghe lỗi → AudioContext lỗi → runtime không 'render-ready';
    VPN/proxy hệ thống (vd Cloudflare WARP) làm Chrome kẹt dò mạng ~8–15 phút mỗi lần mở. Cả hai đã đo trên máy dev.
    (macOS/Linux; Windows dùng trình duyệt mặc định của HyperFrames.)"""
    if os.name == "nt":
        return None
    try:
        r = subprocess.run([*cli_cmd(), "browser", "path"], env=_base_env(), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        real = (r.stdout.strip().splitlines() or [""])[-1]
    except Exception:
        return None
    if not real or not Path(real).exists():
        return None
    body = f'#!/bin/sh\nexec "{real}" --disable-audio-output --mute-audio --no-proxy-server "$@"\n'
    if not WRAPPER.exists() or WRAPPER.read_text() != body:
        WRAPPER.write_text(body)
        WRAPPER.chmod(0o755)
    return str(WRAPPER)


def env() -> dict:
    e = _base_env()
    if WRAPPER.exists() and os.name != "nt":
        e["HYPERFRAMES_BROWSER_PATH"] = str(WRAPPER)
    return e


def _base_env() -> dict:
    e = dict(os.environ, HYPERFRAMES_NO_TELEMETRY="1", DO_NOT_TRACK="1", HYPERFRAMES_NO_UPDATE_CHECK="1",
             HYPERFRAMES_SKIP_SKILLS="1", NO_COLOR="1", FORCE_COLOR="0")
    ff = ffmpeg_exe()
    if ff:
        e["HYPERFRAMES_FFMPEG_PATH"] = ff
        fp = shutil.which("ffprobe")
        if fp:
            e["HYPERFRAMES_FFPROBE_PATH"] = fp
    node = node_exe()
    if node:
        e["PATH"] = str(Path(node).parent) + os.pathsep + e.get("PATH", "")
    return e


def installed_version() -> str | None:
    pj = TOOL_DIR / "node_modules" / "hyperframes" / "package.json"
    if not pj.exists():
        return None
    return json.loads(pj.read_text(encoding="utf-8")).get("version")


def install(log=print) -> dict:
    """cài đúng phiên bản ghim (npm ci theo lockfile). Không nâng phiên bản."""
    node = node_exe()
    if not node:
        raise RuntimeError(f"Chưa có Node.js ≥ {NODE_MIN} — cài Node.js (nodejs.org) rồi chạy lại")
    major, v = _node_version(node)
    if major < NODE_MIN:
        raise RuntimeError(f"Node.js {v} quá cũ — HyperFrames cần ≥ {NODE_MIN}")
    npm = npm_exe(node)
    if not npm:
        raise RuntimeError("Không tìm thấy npm đi kèm Node.js")
    TOOL_DIR.mkdir(parents=True, exist_ok=True)
    for f in ("package.json", "package-lock.json"):
        shutil.copy2(PIN_DIR / f, TOOL_DIR / f)
    log(f"cài HyperFrames {pinned()['hyperframes']} vào {TOOL_DIR}")
    r = subprocess.run([npm, "ci", "--no-audit", "--no-fund", "--loglevel=error"], cwd=TOOL_DIR, env=env(),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
    if r.returncode:
        raise RuntimeError("npm ci lỗi: " + (r.stderr or r.stdout)[-800:])
    return doctor()


def ensure_browser(log=print) -> str | None:
    r = run_cli(["browser", "ensure"], timeout=900)
    if r.returncode != 0:
        return None
    return browser_wrapper()


def run_cli(args: list[str], cwd: Path | None = None, timeout: float = 600, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([*cli_cmd(), *args], cwd=str(cwd) if cwd else None, env=env(), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, **kw)


def doctor() -> dict:
    """trạng thái sẵn sàng: {ok, node, hyperframes, pinned, ffmpeg, chrome, problems[]} — chỉ các thành phần BẮT BUỘC."""
    out = {"ok": False, "pinned": pinned(), "tool_dir": str(TOOL_DIR), "problems": []}
    node = node_exe()
    major, v = _node_version(node) if node else (0, "")
    out["node"] = v or None
    if major < NODE_MIN:
        out["problems"].append(f"cần Node.js ≥ {NODE_MIN} (hiện: {v or 'chưa có'})")
    out["hyperframes"] = installed_version()
    if out["hyperframes"] != out["pinned"]["hyperframes"]:
        out["problems"].append(f"HyperFrames chưa cài đúng bản ghim {out['pinned']['hyperframes']} (hiện: {out['hyperframes']}) "
                               "— chạy: python -m thagent.hyper install")
    out["gsap"] = gsap_js().exists()
    if not out["gsap"]:
        out["problems"].append("thiếu GSAP cục bộ (cài lại runtime)")
    out["ffmpeg"] = ffmpeg_exe()
    if not out["ffmpeg"]:
        out["problems"].append("không thấy ffmpeg")
    out["chrome"] = None
    if not out["problems"] and not WRAPPER.exists():
        browser_wrapper()
    if not out["problems"]:
        try:
            r = run_cli(["doctor", "--json"], timeout=120)
            d = json.loads(r.stdout[r.stdout.index("{"):])
            for c in d.get("checks", []):
                if c["name"] in ("Chrome", "FFmpeg", "FFprobe", "Node.js"):
                    if c["name"] == "Chrome":
                        out["chrome"] = c.get("detail") if c.get("ok") else None
                    if not c.get("ok"):
                        out["problems"].append(f"{c['name']}: {c.get('detail')} {c.get('hint', '')}".strip())
        except Exception as e:
            out["problems"].append(f"hyperframes doctor lỗi: {e}")
    out["ok"] = not out["problems"]
    return out
