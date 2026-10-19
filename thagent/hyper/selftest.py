"""Bài thử ngắn sau khi cài / trước khi nâng phiên bản HyperFrames: render 2s lớp phủ (chữ tiếng Việt đủ dấu, spotlight theo track,
callout) dọc + ngang, kiểm kích thước/fps/thời lượng/alpha, ghép lên nền xám để xem. In JSON kết quả."""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from pathlib import Path


def _spec(W, H, out):
    return {"job_id": f"selftest-{W}x{H}", "width": W, "height": H, "fps": 30, "duration": 2.0, "background": "transparent",
            "output": {"path": str(out), "format": "mov"},
            "layers": [
                {"type": "spotlight", "start": 0.1, "duration": 1.8, "track": [{"t": 0, "x": W * 0.3, "y": H * 0.45, "w": W * 0.2, "h": H * 0.12},
                                                                               {"t": 1.8, "x": W * 0.4, "y": H * 0.48, "w": W * 0.2, "h": H * 0.12}]},
                {"type": "callout", "text": "Nhãn bám vật", "start": 0.2, "duration": 1.7,
                 "target_track": [{"t": 0, "x": W * 0.4, "y": H * 0.45}, {"t": 1.7, "x": W * 0.5, "y": H * 0.48}]},
                {"type": "text", "text": "Tiếng Việt đủ dấu: ắ ằ ẳ ẵ ặ ữ ỡ ợ", "font": "black", "size": 64 if H > W else 56, "stroke": 5,
                 "x": "50%", "y": "18%", "max_w": W * 0.86, "start": 0, "duration": 2.0, "enter": {"type": "pop", "dur": 0.4}}]}


def run(out_dir: Path | None = None) -> int:
    from .job import Job, HyperError
    from .runtime import doctor
    out_dir = Path(out_dir or tempfile.mkdtemp(prefix="hf_selftest_"))
    res = {"doctor": doctor(), "cases": []}
    for W, H in ((1080, 1920), (1920, 1080)):
        out = out_dir / f"selftest_{W}x{H}.mov"
        t0 = time.time()
        try:
            st = Job(_spec(W, H, out), out_dir / "jobs").run(progress=lambda m: None, force=True)
            sheet = out_dir / f"selftest_{W}x{H}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=0x5a6470:s={W}x{H}:d=2", "-i", str(out),
                            "-filter_complex", "[0][1]overlay=format=auto,select='eq(n\\,15)+eq(n\\,45)',scale=480:-1,tile=2x1",
                            "-fps_mode", "passthrough", "-frames:v", "1", str(sheet)], check=False)
            res["cases"].append({"size": f"{W}x{H}", "ok": True, "probe": st.get("probe"), "seconds": round(time.time() - t0, 1),
                                 "sheet": str(sheet)})
        except HyperError as e:
            res["cases"].append({"size": f"{W}x{H}", "ok": False, "error": str(e)[:800]})
    res["ok"] = res["doctor"]["ok"] and all(c["ok"] for c in res["cases"])
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0 if res["ok"] else 1
