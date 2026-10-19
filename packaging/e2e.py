"""Kiểm thử ĐẦU-CUỐI mọi skill của C-Cut (chạy thật, không giả lập) — dev (.venv/bin/python) hoặc bản đóng gói (ccut-py).

  python packaging/e2e.py [thư_mục_làm_việc] [--only th,v2m,review,hyper,common] [--no-hyper]

Dữ liệu thử: packaging/fixtures (Pexels + giọng đọc máy). Không cần đăng nhập Claude (planner heuristic, không gọi LLM).
CCUT_ASR_MODEL (vd "small") rút ngắn chép lời trên CI. Kết quả: in từng mục PASS/FAIL + e2e_report.json; thoát ≠ 0 nếu có FAIL.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
REPO = HERE.parent
try:                                   # bản đóng gói (ccut-py): dùng thagent ĐÃ BIÊN DỊCH, không lấy mã nguồn trong repo
    import thagent  # noqa: F401
except ImportError:
    sys.path.insert(0, str(REPO))
os.environ.pop("ANTHROPIC_API_KEY", None)

args = sys.argv[1:]
ONLY = None
if "--only" in args:
    i = args.index("--only"); ONLY = set(args[i + 1].split(",")); del args[i:i + 2]
NO_HYPER = "--no-hyper" in args
args = [a for a in args if a != "--no-hyper"]
WORK = Path(args[0]) if args else Path(tempfile.mkdtemp(prefix="ccut_e2e_"))
WORK.mkdir(parents=True, exist_ok=True)
os.environ["CCUT_PROJECTS"] = str(WORK / "projects")
(WORK / "projects").mkdir(exist_ok=True)

RESULTS: list[dict] = []
CTX: dict = {}


def run(mod: str, *a, timeout=1800, ok_codes=(0,)) -> str:
    """lệnh `python -m mod …` như agent/app gọi (frozen: ccut-py -m)."""
    cmd = [sys.executable, "-m", mod, *map(str, a)]
    r = subprocess.run(cmd, cwd=str(REPO), capture_output=True, timeout=timeout, env=dict(os.environ))
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    if r.returncode not in ok_codes:
        raise AssertionError(f"{mod} {' '.join(map(str, a))} → mã {r.returncode}\n{out[-2500:]}")
    return out


def probe(p) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate,pix_fmt:format=duration",
                        "-of", "json", str(p)], capture_output=True)
    d = json.loads(r.stdout.decode("utf-8", "replace") or "{}")
    v = next((s for s in d.get("streams", []) if s["codec_type"] == "video"), {})
    a = any(s["codec_type"] == "audio" for s in d.get("streams", []))
    n, _, dn = (v.get("r_frame_rate") or "0/1").partition("/")
    return {"w": v.get("width"), "h": v.get("height"), "fps": round(float(n) / float(dn or 1), 2), "pix": v.get("pix_fmt"),
            "dur": float(d.get("format", {}).get("duration", 0) or 0), "audio": a}


def expect_video(p, w, h, dur=None, audio=True, tol=0.25):
    p = Path(p)
    assert p.exists() and p.stat().st_size > 1000, f"không có file xuất {p}"
    q = probe(p)
    assert (q["w"], q["h"]) == (w, h), f"{p.name}: kích thước {q['w']}x{q['h']} ≠ {w}x{h}"
    assert abs(q["fps"] - 30) < 0.05, f"{p.name}: fps {q['fps']}"
    if dur is not None:
        assert abs(q["dur"] - dur) <= tol, f"{p.name}: thời lượng {q['dur']:.2f} ≠ {dur:.2f}"
    if audio:
        assert q["audio"], f"{p.name}: không có tiếng"
    return q


def case(group: str, name: str):
    def deco(fn):
        def wrapped():
            if ONLY and group not in ONLY:
                return
            t0 = time.time()
            try:
                info = fn()
                RESULTS.append({"group": group, "case": name, "ok": True, "s": round(time.time() - t0, 1), "info": info})
                print(f"PASS  [{group}] {name} ({time.time() - t0:.1f}s){' — ' + str(info)[:160] if info else ''}", flush=True)
            except Exception as e:
                RESULTS.append({"group": group, "case": name, "ok": False, "s": round(time.time() - t0, 1),
                                "error": f"{type(e).__name__}: {e}"[:3000], "trace": traceback.format_exc()[-3000:]})
                print(f"FAIL  [{group}] {name} ({time.time() - t0:.1f}s)\n      {type(e).__name__}: {str(e)[:1500]}", flush=True)
        wrapped.__name__ = fn.__name__
        CASES.append(wrapped)
        return wrapped
    return deco


CASES: list = []


def hyper_ready() -> bool:
    if NO_HYPER:
        return False
    if "hyper" not in CTX:
        from thagent.hyper.runtime import doctor
        CTX["hyper"] = doctor()
    return bool(CTX["hyper"].get("ok"))


# ===================== chung =====================
@case("common", "nạp mọi mô-đun thagent")
def _imports():
    import importlib
    import pkgutil
    import thagent
    bad, n = [], 0
    for m in pkgutil.walk_packages(thagent.__path__, "thagent."):
        if m.name.endswith("__main__") or m.name in ("thagent.app_main", "thagent.server"):
            continue
        try:
            importlib.import_module(m.name); n += 1
        except Exception as e:
            bad.append(f"{m.name}: {e}")
    assert not bad, "; ".join(bad)
    return f"{n} mô-đun"


@case("common", "lệnh CLI in hướng dẫn (tools, v2m, review, hyper, capabilities, newskill)")
def _clis():
    for mod, key in (("thagent.tools", "thagent.tools where"), ("thagent.v2m", "Voice to Motion"), ("thagent.review", "Review Editor"),
                     ("thagent.hyper", "HyperFrames"), ("thagent.newskill", "newskill")):
        out = run(mod, ok_codes=(0, 1))
        assert key in out, f"{mod}: không thấy '{key}' trong hướng dẫn"
    out = run("thagent.capabilities")
    d, _ = json.JSONDecoder().raw_decode(out[out.index("{"):])
    for s in ("talking-head-style", "voice-to-motion", "review-editor"):
        assert "hyperframes" in d["skills"][s]["tools"], f"{s} không nhận công cụ chung"
    return "6 lệnh"


@case("common", "prompt agent mọi style có khối công cụ dùng chung; skill mới dùng prompt chung")
def _prompts():
    from thagent.agent import system_prompt
    for st in ("talking-head-style", "voice-to-motion", "review-editor"):
        p = system_prompt(st, "x", str(WORK))
        assert "CÔNG CỤ DỰNG DÙNG CHUNG" in p and "{" not in p.split("CÔNG CỤ")[0][-5:], st
    from thagent import newskill
    from thagent.paths import ROOT
    slug = "e2e-probe"
    d = ROOT / ".claude" / "skills" / slug
    shutil.rmtree(d, ignore_errors=True)
    try:
        newskill.create(slug, "E2E Probe", "skill thử tạm của bộ kiểm")
        p = system_prompt(slug, "x", str(WORK))
        assert "SKILL.md" in p and slug in p and "HyperFrames" in p, "skill mới không nhận prompt chung / công cụ"
    finally:
        shutil.rmtree(d, ignore_errors=True)
    return "3 style + skill mới"


@case("common", "quy tắc riêng ngành: mỹ phẩm (khoá màu, chặn hứa hẹn công dụng), ẩm thực (tiếng hiện trường, ấm màu)")
def _niches():
    import copy
    from thagent.review import niche
    e = {"category": "my_pham", "segments": [{"id": "A", "texts": [], "cutaways": [{"src": "x"}]},
                                              {"id": "B", "category": "am_thuc", "cutaways": [{"src": "y"}, {"src": "z", "audio": "mute"}]}]}
    e2 = niche.apply(copy.deepcopy(e))
    a, b = e2["segments"]
    assert a["tone"] == {"lift": 0, "warm": 0} and a["cutaways"][0]["tone"]["lift"] == 0, "mỹ phẩm chưa khoá màu"
    assert b["tone"]["warm"] > 0 and b["cutaways"][0]["nat_db"] == niche.FOOD_NAT_DB and "nat_db" not in b["cutaways"][1], "ẩm thực sai"
    assert niche.claims("Trị mụn sau 7 ngày") and not niche.claims("Serum Niacinamide 10%"), "nhận diện hứa hẹn công dụng sai"
    return "3 ngành"


@case("common", "API app (FastAPI): trang chính, thiết lập, trạng thái, kênh")
def _api():
    from thagent.server import app
    try:
        from fastapi.testclient import TestClient
        c = TestClient(app)
    except Exception:                      # bản đóng gói không kèm httpx → chạy server thật, gọi HTTP
        import threading
        import urllib.request
        import uvicorn

        class _R:
            def __init__(self, code, body):
                self.status_code, self.text = code, body

            def json(self):
                return json.loads(self.text)

        srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8799, log_level="error"))
        threading.Thread(target=srv.run, daemon=True).start()
        for _ in range(100):
            if srv.started:
                break
            time.sleep(0.1)

        class _C:
            def get(self, path):
                with urllib.request.urlopen("http://127.0.0.1:8799" + path, timeout=60) as r:
                    return _R(r.status, r.read().decode("utf-8"))
        c = _C()
    out = {}
    for path in ("/", "/api/ccut/setup", "/api/ccut/state", "/api/ccut/channels", "/api/ccut/workspace"):
        r = c.get(path)
        assert r.status_code == 200, f"GET {path} → {r.status_code} {r.text[:300]}"
        out[path] = r.status_code
    st = c.get("/api/ccut/setup").json()
    os.environ["CCUT_PROJECTS"] = str(WORK / "projects")      # server đặt lại CCUT_PROJECTS theo thư mục đang mở — trả về cho các mục sau
    assert "hyperframes" in st, "thiết lập thiếu mục HyperFrames"
    html = c.get("/").text
    for k in ("rvCat", "cong_nghe", "my_pham", "am_thuc", "instHF"):
        assert k in html, f"giao diện thiếu {k}"
    return f"{len(out)} endpoint"


# ===================== HyperFrames =====================
@case("hyper", "doctor + spec chặn spotlight không có track + render lớp phủ + lưu đệm + huỷ + timeout")
def _hyper():
    if not hyper_ready():
        from thagent.capabilities import prompt_block, _CACHE
        _CACHE.pop("hyperframes", None)
        assert "CHƯA SẴN SÀNG" in prompt_block("review-editor"), "HF không sẵn sàng nhưng prompt không báo"
        return f"BỎ QUA render (HyperFrames chưa cài: {CTX['hyper'].get('problems')}) — đã kiểm báo 'chưa sẵn sàng'"
    from thagent.hyper import spec as S
    from thagent.hyper.job import Job, HyperError, cancel
    bad = S.normalize({"width": 1080, "height": 1920, "duration": 2, "output": {"path": str(WORK / "x.mov")},
                       "layers": [{"type": "spotlight", "start": 0, "duration": 2}]})
    assert any("bám vật" in m for lv, m in S.validate(bad) if lv == "error"), "spotlight không track phải là lỗi"
    out = WORK / "hyper" / "ov.mov"
    sp = {"job_id": "e2e-ov", "width": 1080, "height": 1920, "fps": 30, "duration": 2, "output": {"path": str(out), "format": "mov"},
          "layers": [{"type": "text", "text": "Kiểm thử tiếng Việt: ắ ằ ẳ ẵ ặ ữ", "font": "black", "size": 60, "stroke": 5, "x": "50%",
                      "y": "20%", "max_w": 900, "start": 0, "duration": 2},
                     {"type": "spotlight", "start": 0.1, "duration": 1.8, "track": [{"t": 0, "x": 300, "y": 800, "w": 300, "h": 260},
                                                                                    {"t": 1.8, "x": 420, "y": 860, "w": 300, "h": 260}]},
                     {"type": "callout", "text": "Nhãn", "start": 0.2, "duration": 1.7, "target_track": [{"t": 0, "x": 450, "y": 800},
                                                                                                         {"t": 1.7, "x": 570, "y": 860}]},
                     {"type": "table", "title": "So sánh", "cols": ["A", "B"], "rows": [["Pin", "5.000", "4.500"]], "win": [1],
                      "x": "50%", "y": 1400, "start": 0.2, "duration": 1.8},
                     {"type": "bars", "items": [{"label": "1", "value": 2}, {"label": "2", "value": 4}], "x": "50%", "y": 1150,
                      "w": 600, "h": 300, "start": 0.3, "duration": 1.7}]}
    st = Job(sp, WORK / "hyper" / "jobs").run(progress=lambda m: None)
    q = expect_video(out, 1080, 1920, 2.0, audio=False, tol=0.05)
    assert q["pix"].startswith("yuva"), f"mov không có alpha ({q['pix']})"
    t0 = time.time()
    st2 = Job(sp, WORK / "hyper" / "jobs").run(progress=lambda m: None)
    assert time.time() - t0 < 5 and st2["status"] == "done", "chạy lại không dùng kết quả lưu đệm"
    # huỷ: job 20s, huỷ khi đang render
    long = dict(sp, job_id="e2e-cancel", duration=20, output={"path": str(WORK / "hyper" / "long.mov"), "format": "mov"},
                layers=[dict(sp["layers"][0], duration=20)])
    j = Job(long, WORK / "hyper" / "jobs")
    import threading

    def killer():
        for _ in range(600):
            time.sleep(0.5)
            if j.state().get("stage") == "render" and j.state().get("pid"):
                time.sleep(2); cancel(j.dir); return
    threading.Thread(target=killer, daemon=True).start()
    try:
        j.run(progress=lambda m: None, check=False)
        raise AssertionError("huỷ không có tác dụng")
    except HyperError as e:
        assert "huỷ" in str(e), f"lỗi khác khi huỷ: {e}"
    assert j.state()["status"] == "cancelled"
    # timeout
    j2 = Job(dict(long, job_id="e2e-timeout"), WORK / "hyper" / "jobs")
    try:
        j2.run(progress=lambda m: None, check=False, timeout=3)
        raise AssertionError("timeout không có tác dụng")
    except HyperError as e:
        assert "thời gian" in str(e), f"lỗi khác khi quá giờ: {e}"
    return f"render 2s ok, cache ok, huỷ ok, timeout ok ({st['probe']['pix_fmt']})"


@case("hyper", "lệnh CLI: validate, render, status, render-dir")
def _hyper_cli():
    if not hyper_ready():
        return "BỎ QUA (HyperFrames chưa cài)"
    (WORK / "hyper").mkdir(parents=True, exist_ok=True)
    spf = WORK / "hyper" / "cli_spec.json"
    spf.write_text(json.dumps({"job_id": "e2e-cli", "width": 1920, "height": 1080, "fps": 30, "duration": 1.5,
                               "background": "#0A1626", "output": {"path": "cli_out.mp4", "format": "mp4"},
                               "layers": [{"type": "text", "text": "Ngang 16:9 — chữ Việt", "size": 72, "x": "50%", "y": "50%",
                                           "start": 0, "duration": 1.5, "enter": {"type": "up"}}]}, ensure_ascii=False), encoding="utf-8")
    run("thagent.hyper", "validate", spf)
    out = run("thagent.hyper", "render", spf, timeout=900)
    d, _ = json.JSONDecoder().raw_decode(out[out.index("{"):])
    assert d["ok"], out[-1500:]
    expect_video(WORK / "hyper" / "cli_out.mp4", 1920, 1080, 1.5, audio=False, tol=0.05)
    st = run("thagent.hyper", "status", Path(d["log"]).parent)
    assert '"done"' in st
    rd = run("thagent.hyper", "render-dir", Path(d["log"]).parent / "project", "--output", WORK / "hyper" / "dir.mov", timeout=900)
    assert (WORK / "hyper" / "dir.mov").exists(), rd[-800:]
    return "4 lệnh"


# ===================== Voice to Motion =====================
@case("v2m", "init → words → clean/restore → speed → check → stills → render dọc + ngang (+ lớp HyperFrames)")
def _v2m():
    P = WORK / "v2m"
    shutil.rmtree(P, ignore_errors=True)
    run("thagent.v2m", "init", FIX / "voice_vi.mp3", P, timeout=1800)
    w = run("thagent.v2m", "words", P)
    assert "@" in w, "không có lời"
    run("thagent.v2m", "clean", P, timeout=900)
    run("thagent.v2m", "restore", P)
    run("thagent.v2m", "speed", P, "1.0")
    D = float(json.loads((P / "transcript.json").read_text(encoding="utf-8")).get("duration_s") or 13.1)
    use_hf = hyper_ready()
    for fmt, (W, H) in {"9x16": (1080, 1920), "16x9": (1920, 1080)}.items():
        objs, evs = [], []
        beats = [x * D / 6 for x in range(6)]
        for k, t in enumerate(beats):
            objs.append({"id": f"t{k}", "type": "text", "text": ["Phở bò", "Nước dùng trong", "Rau thơm", "Bánh phở mềm", "45.000đ", "Mở cửa 6 giờ"][k],
                         "font": "display", "size": 90 if fmt == "9x16" else 80, "space": "screen", "x": W / 2, "y": H * 0.3})
            evs += [{"object_id": f"t{k}", "action": "reveal", "start_s": round(t + 0.05, 2), "end_s": round(t + 0.45, 2), "style": "up"},
                    {"object_id": f"t{k}", "action": "hide", "start_s": round(t + D / 6 - 0.3, 2), "end_s": round(t + D / 6 - 0.05, 2), "style": "fade"}]
        objs.append({"id": "cnt", "type": "counter", "value": 0, "suffix": "đ", "font": "display", "size": 80, "space": "screen",
                     "x": W / 2, "y": H * 0.55, "color": "#F5C443"})
        evs += [{"object_id": "cnt", "action": "reveal", "start_s": 0.2, "end_s": 0.6, "style": "fade"},
                {"object_id": "cnt", "action": "count", "start_s": 0.6, "end_s": 2.0, "to": {"value": 45000}}]
        if use_hf:
            objs.append({"id": "hfl", "type": "hf", "spec": {"layers": [
                {"type": "bars", "items": [{"label": "Sáng", "value": 3}, {"label": "Trưa", "value": 5}, {"label": "Tối", "value": 4}],
                 "x": "50%", "y": "78%" if fmt == "9x16" else "75%", "w": 700, "h": 320, "start": 0.3, "duration": D - 0.6},
                {"type": "shape", "shape": "circle", "fill": "rgba(51,209,224,.2)", "w": 200, "h": 200, "x": "15%", "y": "15%",
                 "start": 0, "duration": D - 0.1, "keyframes": [{"t": 0, "x": "15%", "y": "15%"}, {"t": D - 0.2, "x": "25%", "y": "20%"}]}]}})
        tl = {"project_id": "e2e", "version": 1, "audio": {"path": "voice.mp3", "duration_s": D, "preserve_timing": True},
              "canvas": {"width": W, "height": H, "fps": 30, "format": fmt},
              "theme": {"bg": "#0A1626", "text": "#FFFFFF", "muted": "#9FB0C6", "accent": "#F5C443", "alt": "#33D1E0"},
              "scenes": [{"id": "S01", "start_s": 0, "end_s": D, "objects": objs, "events": evs}], "assets": [], "limitations": []}
        (P / f"timeline_{fmt}.json").write_text(json.dumps(tl, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copy2(P / "timeline_9x16.json", P / "timeline.json")
    chk = run("thagent.v2m", "check", P, timeout=900, ok_codes=(0, 1))
    assert "0 lỗi" in chk, chk[-1500:]
    run("thagent.v2m", "stills", P, "1", "5", timeout=900)
    run("thagent.v2m", "render", P, "both", timeout=3600)
    outs = {f: next(P.glob(f"*_{f}.mp4"), None) for f in ("9x16", "16x9")}
    expect_video(outs["9x16"], 1080, 1920, D, tol=0.4)
    expect_video(outs["16x9"], 1920, 1080, D, tol=0.4)
    v = sorted((P / "versions").glob("v*"))[-1]
    for f in ("9x16", "16x9"):
        qa = json.loads((v / f"qa_{f}.json").read_text(encoding="utf-8"))
        assert not qa.get("errors"), f"QA v2m {f}: {qa.get('errors')}"
    return f"{D:.1f}s × 2 tỷ lệ{' + HyperFrames' if use_hf else ''}"


# ===================== Review =====================
def _rv_edit(P, hf=False):
    from thagent.review.edit import media
    M = media(P)
    talk = next(k for k, m in M.items() if m.get("words"))
    br = next(k for k in M if k != talk)
    ws = M[talk]["words"]
    dur = float(M[talk]["duration"])
    allw = list(ws)
    ws = [w for w in ws if w["end"] <= dur - 0.7]                 # kết ở chữ còn đủ chỗ giữ hình
    after = [w["start"] for w in allw if w["start"] > ws[-1]["end"]]
    end = round(min(dur - 0.05, ws[-1]["end"] + 0.6, (after[0] - 0.1) if after else 1e9), 2)
    gaps = [(ws[i + 1]["start"] - ws[i]["end"], i) for i in range(2, len(ws) - 3)]
    mid_t = (ws[0]["start"] + ws[-1]["end"]) / 2
    g, i = min((x for x in gaps if x[0] >= 0.3), key=lambda x: abs(ws[x[1]]["end"] - mid_t), default=max(gaps))   # nghỉ gần giữa clip
    cut = round(ws[i]["end"] + min(0.25, g / 2), 2)
    nxt = round(max(cut + 0.01, ws[i + 1]["start"] - 0.15), 2)
    a = max(0.0, round(ws[0]["start"] - 0.15, 2))
    hfx = {"engine": "hyperframes"} if hf else {}
    e = {"category": "cong_nghe", "style": "truc_tiep", "intensity": "can_bang", "formats": ["9x16", "16x9"], "fps": 30, "subtitles": True,
         "auto_zoom": True, "keep_terms": ["mAh"],
         "segments": [
             {"id": "S1", "src": talk, "in": a, "out": end, "role": "talk", "clean": False, "say": "mở hộp + so sánh", "why": "kiểm thử",
              "cutaways": [{"src": br, "in": 0.2, "at": 2.6, "dur": 1.6, "why": "cầm máy"}],
              "texts": [{"role": "emph", "text": "Mở hộp điện thoại", "sub": "Công nghệ", "at": 0.15, "dur": 1.0},
                        {"role": "label", "text": "Hộp máy", "track": "obj", "at": 1.2, "dur": 1.3, **hfx},
                        {"role": "spotlight", "track": "obj", "at": 1.2, "dur": 1.3, **hfx},
                        {"role": "compare", "title": "So với đời trước", "cols": ["Mới", "Cũ"],
                         "rows": [["Màn hình", "6,7 inch", "6,1 inch"], ["Pin", "5.000 mAh", "4.500 mAh"]], "win": [1, 1],
                         "at": 4.6, "dur": 2.4, **hfx},
                        {"role": "info", "text": "Kịch bản mẫu", "sub": "Ghi chú", "at": 7.3, "dur": 1.3, **hfx},
                        {"role": "stat", "value": 5000, "unit": "mAh", "label": "Pin", "at": 8.9, "dur": 1.3}]}]}
    return e


@case("review", "inventory → media → words → takes → frames → motion → hands → track → joins → fixjoins → clean → keyinfo → check → stills → render 2 tỷ lệ")
def _review():
    P = WORK / "review"
    shutil.rmtree(P, ignore_errors=True)
    P.mkdir()
    run("thagent.review", "inventory", P, FIX / "presenter.mp4", FIX / "broll.mp4", timeout=3600)
    out = run("thagent.review", "media", P)
    from thagent.review.edit import media
    M = media(P)
    talk = next(k for k, m in M.items() if m.get("words"))
    assert M[talk]["words"], "không chép được lời"
    run("thagent.review", "media", P, talk)
    run("thagent.review", "words", P, talk, 0, 5)
    run("thagent.review", "takes", P)
    run("thagent.review", "frames", P, talk, 1, 3)
    run("thagent.review", "motion", P, talk, 0, 4)
    run("thagent.review", "hands", P, talk, 0, 4, timeout=900)
    run("thagent.review", "track", P, "obj", talk, 2.0, "0.62,0.43,0.16,0.09", 0.8, 3.6, timeout=900)
    e = _rv_edit(P)
    (P / "review" / "edit.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    run("thagent.review", "joins", P)
    run("thagent.review", "fixjoins", P)
    run("thagent.review", "clean", P, timeout=1800)
    run("thagent.review", "keyinfo", P)
    chk = run("thagent.review", "check", P, ok_codes=(0, 1))
    errs = [l for l in chk.splitlines() if l.startswith("[error]")]
    assert not errs, "check Review báo lỗi:\n" + "\n".join(errs)
    run("thagent.review", "stills", P, "9x16", 1, 3, timeout=900)
    run("thagent.review", "stills", P, "16x9", 1, 3, timeout=900)
    r = run("thagent.review", "render", P, timeout=3600)
    v = sorted((P / "review" / "versions").glob("v*"))[-1]
    from thagent.review.edit import load, duration
    T = duration(load(P))
    for f, (W, H) in {"9x16": (1080, 1920), "16x9": (1920, 1080)}.items():
        expect_video(v / f"review_{f}.mp4", W, H, T, tol=0.2)
        qa = json.loads((v / f"qa_{f}.json").read_text(encoding="utf-8"))
        assert qa.get("ok") and not qa.get("errors"), f"QA Review {f}: {qa.get('errors')}"
    CTX["review_P"] = P
    return f"{T:.1f}s × 2 tỷ lệ, 5 loại chữ + spotlight/nhãn bám track, 2 lĩnh vực"


@case("review", "Review với HyperFrames (nhãn/spotlight bám track thật, bảng so sánh) — 2 tỷ lệ")
def _review_hf():
    if not hyper_ready():
        return "BỎ QUA (HyperFrames chưa cài)"
    P = CTX.get("review_P")
    assert P, "cần chạy mục Review trước"
    e = _rv_edit(P, hf=True)
    (P / "review" / "edit.json").write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")
    chk = run("thagent.review", "check", P, ok_codes=(0, 1))
    errs = [l for l in chk.splitlines() if l.startswith("[error]")]
    assert not errs, "check báo lỗi:\n" + "\n".join(errs)
    run("thagent.review", "render", P, timeout=3600)
    v = sorted((P / "review" / "versions").glob("v*"))[-1]
    n = 0
    for f, (W, H) in {"9x16": (1080, 1920), "16x9": (1920, 1080)}.items():
        expect_video(v / f"review_{f}.mp4", W, H)
        qa = json.loads((v / f"qa_{f}.json").read_text(encoding="utf-8"))
        assert qa.get("ok"), f"QA {f}: {qa.get('errors')}"
        n += sum(1 for s in qa.get("spotlights", []) if s.get("engine") == "hyperframes")
    assert n >= 6, f"chỉ {n} lớp HyperFrames được ghép (cần ≥ 6)"
    return f"{n} lớp HyperFrames"


# ===================== Talking Head =====================
@case("th", "ingest → chép lời → tách nền → kế hoạch → preflight → dựng (+ lớp HyperFrames trước/sau nhân vật)")
def _th():
    from thagent import pipeline as Pp
    from thagent.preflight import check
    pid = "e2e_th"
    shutil.rmtree(Pp.PROJECTS / pid, ignore_errors=True)
    c = Pp.Ctx(pid, log=lambda m: None)
    Pp.step_ingest(c, str(FIX / "presenter.mp4"))
    Pp.step_transcribe(c)
    assert c.project.words, "không chép được lời"
    Pp.step_matting(c)
    Pp.step_plan(c)
    pl = c.project.plan
    assert pl and pl.duration_frames > 30, "kế hoạch rỗng"
    use_hf = hyper_ready()
    if use_hf:
        from thagent.th_hf import words_tl
        f1 = min(pl.duration_frames, 150)
        ws = words_tl(pid, 0, f1)
        pl.hf = [{"id": "cap", "start": 0, "end": f1, "layer": "front", "spec": {"layers": [
                     {"type": "text", "text": " ".join(w for w, _ in ws) or "Phụ đề", "word_times": [t for _, t in ws] or None,
                      "reveal": "words" if ws else None, "font": "bold", "size": 58, "stroke": 6, "max_w": 940, "x": "50%", "y": "80%",
                      "active_color": "#FFD34D", "start": 0, "duration": round(f1 / 30, 3)}]}},
                 {"id": "title", "start": 10, "end": min(pl.duration_frames, 100), "layer": "behind_subject", "spec": {"layers": [
                     {"type": "text", "text": "SERUM", "font": "black", "size": 130, "x": "50%", "y": "40%", "start": 0,
                      "duration": round((min(pl.duration_frames, 100) - 10) / 30, 3), "enter": {"type": "pop"}}]}}]
        for L in pl.hf[0]["spec"]["layers"]:
            for k in [k for k, v in L.items() if v is None]:
                L.pop(k)
        c.save()
    errs = [m for lv, m in check(pid) if lv == "error"]
    assert not errs, "preflight lỗi: " + "; ".join(errs)
    r = Pp.step_render(c, frame_range=(0, min(pl.duration_frames, 150)), label="e2e")
    f = Path(c.project.renders[-1]["file"])
    f = f if f.is_absolute() else Pp.PROJECTS.parent / f
    if not f.exists():
        f = next((Pp.PROJECTS / pid / "renders").glob("*e2e*/*.mp4"))
    expect_video(f, 1080, 1920, min(pl.duration_frames, 150) / 30, tol=0.2)
    out = run("thagent.tools", "where", pid)
    assert "duration" in out
    run("thagent.tools", "words", pid)
    run("thagent.tools", "frames", pid, 1, 2)
    if use_hf:
        run("thagent.tools", "hfwords", pid, 0, 60)
    return f"{c.project.renders[-1].get('issues')} vấn đề QA{' + HyperFrames' if use_hf else ''}"


if __name__ == "__main__":
    print(f"C-Cut e2e · python {sys.version.split()[0]} · {sys.platform} · làm việc: {WORK}", flush=True)
    for fn in CASES:
        fn()
    rep = WORK / "e2e_report.json"
    rep.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in RESULTS if not r["ok"]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} PASS · báo cáo: {rep}")
    sys.exit(1 if bad else 0)
