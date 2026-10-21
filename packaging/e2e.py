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
os.environ["CCUT_LICENSE_STORE"] = str(WORK / "license.json")      # bản quyền thử của bộ kiểm — không đụng dữ liệu thật
os.environ["CCUT_LICENSE_URL"] = "http://127.0.0.1:9"              # không gọi máy chủ thật (cổng đóng)


def _signing_seed() -> bytes | None:
    """khoá ký bản quyền (CI: bí mật CCUT_TEST_SIGNING_KEY; máy chủ app: ~/.ccut-license/keys.json) → 32 byte seed."""
    import base64
    k = os.environ.get("CCUT_TEST_SIGNING_KEY")
    f = Path.home() / ".ccut-license" / "keys.json"
    if not k and f.exists():
        k = json.loads(f.read_text())["SIGNING_KEY"]
    return base64.b64decode(k)[-32:] if k else None


def _test_token(seed: bytes, product: str, device: str) -> str:
    import base64
    from thagent import license as L
    body = json.dumps({"v": 1, "t": "lic", "key": "CC-E2E00-TEST0-" + product[:5].upper().ljust(5, "0"), "product": product,
                       "device": device, "iat": int(time.time())}).encode()
    b = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
    return f"{b(body)}.{b(L._sign(seed, body))}"

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


@case("common", "tài liệu lời dặn Claude nhắc tới đều có trong bản cài (không trỏ vào mã nguồn đã biên dịch)")
def _prompt_docs():
    import re
    from thagent.agent import system_prompt
    from thagent.paths import ROOT
    from thagent import schemadocs
    texts = [system_prompt(st, "x", str(WORK)) for st in ("talking-head-style", "voice-to-motion", "review-editor")]
    texts += [f.read_text(encoding="utf-8") for f in (ROOT / ".claude" / "shared").glob("*.md")]
    texts.append(schemadocs.text("edl.md"))
    bad = sorted({m for t in texts for m in re.findall(r"(?:docstring|schema (?:ở|trong))[^\n]{0,40}thagent/[\w/]+\.py", t)})
    assert not bad, f"lời dặn trỏ vào mã nguồn (bản cài không đọc được): {bad}"
    refs = sorted({m for t in texts for m in re.findall(r"\.claude/shared/[\w/.-]+\.md", t)})
    miss = [r for r in refs if not (ROOT / r).is_file()]
    assert refs and not miss, f"thiếu tài liệu: {miss}"
    assert '"segments"' in schemadocs.text("edl.md") and '"segments"' in schemadocs.text("review-edit.md")
    return f"{len(refs)} tài liệu"


@case("common", "bản quyền skill: mọi skill bán (Talking Head, Review, Voice to Motion) bị chặn khi chưa mua/không có lượt thử, mã giả bị từ chối")
def _license():
    import base64
    from thagent import license as L
    real = L.STORE
    L.STORE = WORK / "license_empty.json"
    try:
        assert "talking-head-style" in L.PAID and not L.FREE, "Talking Head phải là skill bán"
        for sk in L.PAID:
            try:
                L.require(sk, "p-e2e")
                raise AssertionError(f"{sk} không bị chặn khi chưa mua")
            except L.LicenseError as e:
                assert str(e).startswith("BẢN QUYỀN"), e
        body = json.dumps({"t": "lic", "key": "X", "product": "all", "device": L.device_id()}).encode()
        fake = base64.urlsafe_b64encode(body).decode().rstrip("=") + "." + "A" * 86
        L._save({"tokens": [fake]})
        assert not L.owns("review-editor"), "mã giả (sai chữ ký) lại mở khoá được"
        seed = _signing_seed()
        if seed:
            L._save({"tokens": [_test_token(seed, "all", "f" * 64)]})
            assert not L.owns("review-editor"), "mã của máy khác lại mở khoá được"
            L._save({"tokens": [_test_token(seed, "review-editor", L.device_id())]})
            assert L.owns("review-editor") and not L.owns("voice-to-motion"), "mã lẻ mở sai skill"
            # thu hồi / gỡ khỏi máy: máy chủ trả danh sách mã còn hiệu lực (đã ký kèm nonce) → app bỏ mã không còn trong đó
            import base64
            tok = _test_token(seed, "review-editor", L.device_id())
            key = L.read_token(tok)["key"]
            b = lambda x: base64.urlsafe_b64encode(x).decode().rstrip("=")
            real_http = L._http

            def fake(keys, nonce_ok=True):
                def h(method, path, body=None, timeout=12):
                    st = json.dumps({"v": 1, "t": "st", "device": L.device_id(), "nonce": body["nonce"] if nonce_ok else "cu",
                                     "keys": keys, "blocked": False, "iat": int(time.time())}).encode()
                    return {"ok": True, "tokens": [tok] if key in keys else [], "trials": {}, "revoked": [], "state": f"{b(st)}.{b(L._sign(seed, st))}"}
                return h
            try:
                L._save({"tokens": [tok], "verified": 0})
                L._http = fake([key])
                assert L.require("review-editor", "p-e2e") == "licensed", "mã còn hiệu lực bị bỏ"
                L._save({"tokens": [tok], "verified": 0})
                L._http = fake([key], nonce_ok=False)
                try:
                    L.sync(); raise AssertionError("phát lại phản hồi cũ (sai nonce) vẫn được nhận")
                except L.LicenseError:
                    pass
                L._http = fake([])
                try:
                    L.require("review-editor", "p-e2e2"); raise AssertionError("mã đã thu hồi / gỡ khỏi máy vẫn dùng được")
                except L.LicenseError:
                    pass
                assert not L.owns("review-editor"), "mã thu hồi vẫn còn trên máy"
                L._save({"tokens": [tok], "verified": time.time() + 10 ** 8})
                try:
                    L.require("review-editor", "p-e2e3"); raise AssertionError("sửa tay giờ xác minh để khỏi hỏi lại vẫn qua")
                except L.LicenseError:
                    pass
            finally:
                L._http = real_http
    finally:
        L.STORE = real
    return "đã kiểm chữ ký" if _signing_seed() else "không có khoá ký — bỏ phần mã hợp lệ"


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


@case("common", "ảnh đúng chủ thể: tên riêng chưa khai, chữ trên hình gọi tên dự án, ảnh sai vật (sân bay/sông), ảnh lặp")
def _entities():
    from PIL import Image
    from thagent import entities as E
    from thagent.imgsearch import page_results
    p = WORK / "entities"
    shutil.rmtree(p, ignore_errors=True)
    (p / "assets_web").mkdir(parents=True)
    fs = ["i_doanhnhan.jpg", "i_phongkhach.jpg", "i_bietthu.jpg"]
    for n in fs:
        Image.new("RGB", (64, 64)).save(p / "assets_web" / n)
    (p / "assets_web" / "illus_sources.json").write_text(json.dumps({n: "https://x.vn/a" for n in fs}))
    (p / "assets_web" / "illus_check.json").write_text(json.dumps({"i_doanhnhan.jpg": {"noi_dung_anh": "doanh nhân trong văn phòng"},
        "i_phongkhach.jpg": {"noi_dung_anh": "phòng khách nhìn ra biển"}, "i_bietthu.jpg": {"noi_dung_anh": "biệt thự hồ bơi"}}, ensure_ascii=False), encoding="utf-8")
    (p / "entities.json").write_text(json.dumps([{"name": "The Victoria", "aka": ["Vinhomes Tân Cảng"], "photos": []}], ensure_ascii=False), encoding="utf-8")
    ws = [(w, 20 + i * 0.3) for i, w in enumerate("Ví dụ khu biệt thự Ba Son tại trung tâm".split())]
    ws += [(w, 60 + i * 0.3) for i, w in enumerate("căn nhà 3 mặt view sông".split())]
    ws += [(w, 70 + i * 0.3) for i, w in enumerate("rất gần sân bay quốc tế".split())]
    im = lambda f: {"file": f, "label": "", "real": False}
    scenes = [{"id": "A", "t0": 23, "t1": 28, "text": "70 TỶ LÊN 300 TỶ", "images": [im("i_doanhnhan.jpg")]},
              {"id": "B", "t0": 33, "t1": 37, "text": "THE VICTORIA", "images": [im("i_bietthu.jpg")]},
              {"id": "C", "t0": 60.5, "t1": 65, "text": "3 MẶT VIEW SÔNG", "images": [im("i_phongkhach.jpg")]},
              {"id": "D", "t0": 71, "t1": 75, "text": "ĐIỀU 4", "images": [im("i_doanhnhan.jpg")]}]
    errs = [m for sev, m in E.check(p, ws, scenes, lambda i: i["real"]) if sev == "error"]
    need = {"A": "Ba Son", "B": "The Victoria", "C": "sông", "D": "sân bay"}
    for sid, key in need.items():
        assert any(m.startswith(sid + ":") and key in m for m in errs), f"không bắt lỗi cảnh {sid} ({key}): {errs}"
    assert any("đã dùng ở A" in m for m in errs), "không bắt ảnh lặp"
    page = WORK / "entities" / "page.html"
    page.write_text('<title>T</title><meta property="og:image" content="/a.jpg"><img src="logo.png"><img data-src="https://cdn.x/b.jpg">')
    rs = [r["url"] for r in page_results(page.resolve().as_uri())]
    assert rs == ["https://cdn.x/b.jpg"], f"lấy ảnh trong trang sai: {rs}"     # bỏ logo; ảnh không phải http(s) bị loại
    return f"{len(errs)} lỗi đúng chỗ"


@case("voice", "giọng đọc: tải model ghim phiên bản → giọng có sẵn đọc Việt + Anh → nhân bản giọng từ video (bắt buộc xác nhận quyền) → đọc bằng giọng nhân bản")
def _voice():
    import soundfile as sf
    from thagent import voice as V
    for k in range(3):                                   # máy chủ tải model đôi khi giới hạn lượt → thử lại
        try:
            V.download()
            break
        except V.VoiceError:
            if k == 2:
                raise
            time.sleep(30 * (k + 1))
    assert V.ready(), "chưa tải xong bộ giọng đọc"
    ids = [v["id"] for v in V.voices()]
    assert V.DEFAULT in ids, ids
    out = WORK / "voice"
    w = V.say("Giá căn hộ 3,5 tỷ đồng. Welcome to C-Cut.", V.DEFAULT, out / "preset.wav", 1.1)
    x, sr = sf.read(str(w))
    assert sr == V.SR and 1.0 < len(x) / sr < 15, f"giọng có sẵn đọc sai độ dài {len(x) / sr:.1f}s"
    try:
        V.clone(FIX / "presenter.mp4", "Giọng kiểm thử", consent=False)
        raise AssertionError("nhân bản không cần xác nhận quyền")
    except V.VoiceError:
        pass
    c = V.clone(FIX / "presenter.mp4", "Giọng kiểm thử", consent=True)
    assert c["id"] in [v["id"] for v in V.voices()] and 4.0 <= c["ref_seconds"] <= 8.0, c
    text = "Đây là giọng được nhân bản từ đoạn video mẫu, đọc một câu đủ dài để so sánh chất giọng với người nói gốc."
    enc = V.engine().engine.speaker_encoder
    emb = lambda f: enc.embed(*sf.read(str(f)))
    cos = lambda a, b: float(a @ b / (abs(a @ a) ** 0.5 * abs(b @ b) ** 0.5))
    src = enc.embed(V._load_audio(FIX / "presenter.mp4")[: V.SR * 30], V.SR)
    sim = cos(emb(V.say(text, c["id"], out / "clone.wav")), src)
    other = cos(emb(V.say(text, V.DEFAULT, out / "default.wav")), src)
    V.remove(c["id"])
    assert sim > other + 0.1, f"giọng nhân bản không giống giọng gốc hơn giọng có sẵn (nhân bản {sim:.2f} · giọng có sẵn {other:.2f})"
    return f"giọng có sẵn + nhân bản (độ giống {sim:.2f}, giọng khác {other:.2f})"


@case("voice", "Text to Video: tách file nhiều kịch bản → đọc thành giọng tốc độ 1.1 → mốc từng từ đúng chữ kịch bản; dùng lại hình chỉ khi nói đúng vật")
def _t2v():
    import soundfile as sf
    from thagent import t2v as TV, entities as E
    vids = TV.split("Video 1: Son\nBạn đã thử cây son kem lì này chưa? Đầu cọ mềm, tán đều chỉ một lần quẹt.\n\n"
                    "Video 2: Nhà\nThời lượng: 30s\nCăn hộ hai phòng ngủ rộng bảy mươi lăm mét vuông, cách trung tâm mười lăm phút đi xe.")
    assert [v["title"] for v in vids] == ["Video 1: Son", "Video 2: Nhà"] and "Thời lượng" not in vids[1]["text"], vids
    p = WORK / "t2v"
    shutil.rmtree(p, ignore_errors=True)
    m = TV.prepare(p, vids[0]["text"], "nam_huong_dan", progress=lambda x: None)
    tr = json.loads((p / "transcript.json").read_text(encoding="utf-8"))
    x, sr = sf.read(str(p / "voice.wav"))
    assert abs(len(x) / sr - tr["duration_s"]) < 0.1 and m["speed"] == 1.1, m
    assert " ".join(w["text"] for w in tr["words"]) == " ".join(s["text"] for s in TV.sentences(vids[0]["text"])), "phụ đề không đúng chữ kịch bản"
    assert all(a["start"] <= b["start"] + 0.01 for a, b in zip(tr["words"], tr["words"][1:])), "mốc từ không tăng dần"
    # dùng lại clip: được khi cảnh nói lại đúng vật, lỗi khi nói ý khác
    (p / "assets_web").mkdir(exist_ok=True)
    import numpy as np
    from PIL import Image
    Image.fromarray(np.zeros((8, 8, 3), np.uint8)).save(p / "assets_web" / "i_dau_co.jpg")
    (p / "assets_web" / "illus_sources.json").write_text(json.dumps({"i_dau_co.jpg": "https://x.vn/a"}))
    (p / "assets_web" / "illus_check.json").write_text(json.dumps({"i_dau_co.jpg": {"noi_dung_anh": "cận cảnh đầu cọ son", "vat": "đầu cọ son"}}, ensure_ascii=False), encoding="utf-8")
    (p / "entities.json").write_text("[]")
    ws = [("đầu", 1.0), ("cọ", 1.2), ("mềm", 1.4), ("đầu", 5.0), ("cọ", 5.2), ("vát", 5.4), ("giá", 9.0), ("rẻ", 9.2)]
    sc = lambda i, a, b: {"id": i, "t0": a, "t1": b, "text": "", "images": [{"file": "i_dau_co.jpg", "label": "", "real": False}]}
    errs = lambda scenes: [m for sv, m in E.check(p, ws, scenes, lambda im: im["real"]) if sv == "error" and "dùng lại" in m]
    assert not errs([sc("A", 0.5, 3), sc("B", 4.6, 7)]), "nói lại đầu cọ mà không cho dùng lại clip"
    assert errs([sc("A", 0.5, 3), sc("C", 8.6, 10)]), "nói ý khác mà vẫn cho chèn lại clip đầu cọ"
    return f"{len(vids)} video tách đúng · giọng {m['duration_s']:.1f}s · chống lặp hình đúng ngữ cảnh"


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
    Pp.PROJECTS = Path(os.environ["CCUT_PROJECTS"])     # bài API (load_settings) có thể đã trỏ PROJECTS sang thư mục làm việc của app
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
        D = pl.duration_frames                   # đoạn kết: hình nhân vật + chữ kết (quy tắc mở đầu/kết của Talking Head)
        pl.hf.append({"id": "outro", "start": max(0, D - 60), "end": D, "layer": "front", "spec": {"layers": [
            {"type": "text", "text": "ĐĂNG KÝ KÊNH", "font": "black", "size": 96, "x": "50%", "y": "70%", "start": 0,
             "duration": round(min(D, 60) / 30, 3), "enter": {"type": "pop"}}]}})
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
    _seed = _signing_seed()
    if _seed:                          # skill bán (Review, Voice to Motion) cần bản quyền để xuất → cấp mã combo thử cho máy kiểm
        from thagent import license as _L
        _L._save({"tokens": [_test_token(_seed, "all", _L.device_id())], "verified": time.time()})   # máy chủ giả (cổng đóng) → dùng hạn offline
    else:
        print("CHÚ Ý: không có khoá ký bản quyền (CCUT_TEST_SIGNING_KEY) — bài dựng Review/Voice to Motion sẽ bị chặn", flush=True)
    for fn in CASES:
        fn()
    rep = WORK / "e2e_report.json"
    rep.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding="utf-8")
    bad = [r for r in RESULTS if not r["ok"]]
    print(f"\n{len(RESULTS) - len(bad)}/{len(RESULTS)} PASS · báo cáo: {rep}")
    sys.exit(1 if bad else 0)
