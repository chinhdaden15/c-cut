"""Kho SFX của Voice to Motion — lấy từ thư viện SFX thật của người dùng (giống cách Talking Head dùng), chia theo VAI TRÒ.

- build(): nhập lại kho từ thư mục nguồn → assets/sfx_v2m/<vai_trò>_NN.wav (48 kHz mono, bỏ lặng đầu, cắt độ dài,
  fade đuôi, chuẩn đỉnh −3 dBFS) + manifest.json (nguồn, đỉnh peak_ms để đặt đỉnh âm đúng khung hành động).
- pick(role, k): chọn âm trong pool theo vòng, không lặp liền kề.
- auto_events(tl): sinh SFX từ CHÍNH chuyển động của timeline (mỗi tỷ lệ khung có SFX khớp hình của mình).
"""
from __future__ import annotations

import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np

from ..paths import ROOT

KIT_DIR = ROOT / "assets" / "sfx_v2m"
SRC_ROOT = Path.home() / "Documents" / "Chính Dùng" / "SFX"

# vai trò → (mô tả, gain mặc định dB, độ dài tối đa s, [file nguồn trong SRC_ROOT])
KIT = {
    "whoosh":     ("camera đi xa, chuyển vùng", -17, 1.0, ["Woosh/Short, Deep, Dry.mp3", "Woosh/Short, Low, Dry 02.mp3",
                                                         "Woosh/Short, Stove, Dry 01.mp3", "Swish/Short, Bandpass, Dry.mp3"]),
    "swish":      ("vật trượt vào, tuyến bắt đầu vẽ", -19, 0.7, ["Swish/Short, Wind Gusts, Dry.mp3", "Swish/Organic, Cloth.mp3",
                                                              "Swish/Sword Swing 02.mp3"]),
    "click":      ("pin, callout, điểm đến", -15, 0.45, ["Click/Neutral, Select Tone 03.mp3", "Best/Neutral, Select Tone 01.mp3",
                                                     "Click/Digital, Video Game, Select, Positive, Notification 03.mp3",
                                                     "User Interface/Button Press Click, Tap, Video Game, Main Menu, Select, Positive 04.mp3"]),
    "pop":        ("thẻ, nút, shape xuất hiện", -16, 0.6, ["User Interface/Notification, Message, Text.mp3",
                                                       "User Interface/Notification, Attention, Positive, Funny, Short 01.mp3",
                                                       "Click/Sci Fi Games, UI Menu, Very Short, Open 09.mp3",
                                                       "User Interface/Sci Fi Games, UI Menu, Very Short, Open 11.mp3"]),
    "tick":       ("liệt kê, từng mục, từng chữ nhấn", -14, 0.15, ["Best/Neutral, Select Tone 01.mp3", "Click/Neutral, Select Tone 03.mp3",
                                                              "Gõ phím/Keyboard, Small, Bluetooth, Type, Key Press, Spacebar 01.mp3"]),
    "impact":     ("thông điệp chính, câu kết", -13, 1.6, ["Impact/Impact, Final Hit.mp3", "Impact/Impact, Dark, Cinematic, Snappy Hit.mp3",
                                                       "Impact/Impact, Dark, Cinematic, Hard Hit 01.mp3"]),
    "flash":      ("tiêu đề lớn, đảo nền", -14, 1.2, ["Best/Flash, Modern, Design 03.mp3", "Chụp ảnh/Flash, Modern, Design 01.mp3",
                                                  "Chụp ảnh/Flash, Modern, Design 02.mp3", "Chụp ảnh/Flash, Modern, Design 04.mp3"]),
    "transition": ("đổi chương, chuyển cảnh phủ", -16, 1.1, ["User Interface/Glitch Transition 02.mp3",
                                                         "Impact/Sweep, Transition, Hard Hitting, Dark 02.mp3"]),
    "success":    ("hoàn tất, dấu ✓", -16, 1.1, ["User Interface/Notification, Checkpoint, Bling, Positive, Happy 06.mp3",
                                              "User Interface/Success, Reward, Bright, Happy Twinkle 01.mp3"]),
    "money":      ("tiền, giá, chi phí", -15, 1.0, ["Tiền rơi, giấy, viết/Money, Coins, Stack, Fast.mp3",
                                                  "Tiền rơi, giấy, viết/Coins, Box, Cardboard, Coins Dropping 01.mp3"]),
    "paper":      ("trích dẫn, tài liệu, lật trang", -15, 0.8, ["Tiền rơi, giấy, viết/Page Turn, Large Binder 03.mp3",
                                                            "Tiền rơi, giấy, viết/Directory, Telephone Book, Page Turn 04.mp3"]),
    "write":      ("gạch chân, marker, vẽ nét tay", -17, 1.0, ["Tiền rơi, giấy, viết/Marker Writing Sound, Drag.mp3"]),
    "camera":     ("ảnh xuất hiện, chụp", -15, 0.45, ["Chụp ảnh/Digital SLR, Sony Alpha, Take Photo, Shutter Click Only.mp3",
                                                    "Chụp ảnh/Olympus OM D E M10 Digital Camera, Focus.mp3"]),
    "typing":     ("chữ gõ ra", -18, 1.4, ["Gõ phím/Smartphone, Type, Sentence, Words, Clicks, Phone Filter.mp3"]),
    "data":       ("bản đồ, biểu đồ, dữ liệu hiện ra", -18, 1.2, ["User Interface/Digital Transmission, Loading, Moving, Panning.mp3"]),
}


def _peak_ms(path: Path) -> float:
    with wave.open(str(path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float)
        sr = w.getframerate()
    win = max(int(sr * 0.005), 1)
    e = np.convolve(x ** 2, np.ones(win) / win, "same")
    return round(float(np.argmax(e)) / sr * 1000, 1)


def build(src_root: Path = SRC_ROOT, log=print) -> dict:
    KIT_DIR.mkdir(parents=True, exist_ok=True)
    man = {}
    for role, (desc, gain, maxlen, files) in KIT.items():
        items = []
        for i, rel in enumerate(files):
            src = src_root / rel
            if not src.exists():
                log(f"  thiếu nguồn: {rel}")
                continue
            out = KIT_DIR / f"{role}_{i:02d}.wav"
            af = (f"silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.005,"
                  f"atrim=0:{maxlen},afade=t=out:st={max(maxlen - min(0.25, maxlen * 0.3), 0):.3f}:d={min(0.25, maxlen * 0.3):.3f},"
                  f"loudnorm=I=-16:TP=-1.5:LRA=11")
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", "48000", "-af", af, str(out)], check=True)
            # chuẩn đỉnh −3 dBFS (cùng chuẩn Talking Head) rồi mới áp gain theo vai trò
            with wave.open(str(out)) as w:
                x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
            x = x / (np.abs(x).max() + 1e-9) * (10 ** (-3 / 20))
            with wave.open(str(out), "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
                w.writeframes((x * 32767).astype(np.int16).tobytes())
            items.append({"file": out.name, "source": f"Chính Dùng/SFX/{rel}", "peak_ms": _peak_ms(out),
                          "dur_s": round(len(x) / 48000, 3)})
        man[role] = {"desc": desc, "gain_db": gain, "items": items,
                     "license": "thư viện SFX của người dùng (cùng nguồn với Talking Head)"}
        log(f"{role:<11} {len(items)} âm · {desc}")
    (KIT_DIR / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    return man


def manifest() -> dict:
    p = KIT_DIR / "manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def roles() -> list[str]:
    return list(manifest())


def pick(role: str, k: int) -> dict | None:
    """âm thứ k của vai trò (xoay vòng, không lặp liền kề) → {path, peak_ms, gain_db}."""
    m = manifest().get(role)
    if not m or not m["items"]:
        return None
    it = m["items"][k % len(m["items"])]
    return {"path": str(KIT_DIR / it["file"]), "peak_ms": it["peak_ms"], "gain_db": m["gain_db"]}


# ---------------- SFX tự động theo chuyển động thật của timeline ----------------
def auto_events(tl) -> list[dict]:
    """sinh sự kiện {t, role, gain_db?} từ hành động thị giác của timeline (đỉnh âm = thời điểm hành động).
    Không thay SFX khai báo tay: bỏ sự kiện tự động trong ±0,3s quanh một SFX tay. Mật độ ≤ 0,9/giây, cách nhau ≥ 0,25s."""
    from .render import camera_at
    ev = []
    # 1) camera đi xa / đổi zoom lớn → whoosh (đỉnh ở giữa quãng di chuyển)
    for k in tl.camera:
        dur = float(k.get("dur", 0.6))
        if dur < 0.35:
            continue
        a, b = camera_at(tl, float(k["t"]) - dur), camera_at(tl, float(k["t"]))
        dz = abs(math.log(max(b[2], 1e-6) / max(a[2], 1e-6)))
        dmov = math.hypot(b[0] - a[0], b[1] - a[1]) * max(a[2], b[2]) / tl.W
        if dz > 0.45 or dmov > 0.45:
            ev.append({"t": float(k["t"]) - dur * 0.5, "role": "whoosh", "why": "camera chuyển vùng"})
    # 2) theo đối tượng xuất hiện
    big_done = set()
    for oid, o in tl.objs.items():
        rev = [e for e in tl.events.get(oid, []) if e["action"] == "reveal"]
        if not rev:
            continue
        t = float(rev[0]["start_s"]) + 0.06
        typ = o["type"]
        if o.get("role") in ("caption", "backdrop"):   # phụ đề chạy chữ / phủ nền: không gắn SFX
            continue
        kids = [c for c in tl.objs.values() if c.get("parent") == oid]
        if typ == "icon" and "check" in str(o.get("name", "")):
            ev.append({"t": t, "role": "success", "why": f"dấu tích {oid}"}); continue
        if typ == "counter":
            ev.append({"t": t, "role": "data", "why": f"số liệu {oid}"}); continue
        if typ == "rect" and any(c["type"] == "text" for c in kids) and float(o.get("h", 0)) <= 140:
            ev.append({"t": t, "role": "click", "why": f"nhãn/từ khóa {oid}"}); continue
        if typ in ("callout", "routelabel"):
            ev.append({"t": t + 0.15, "role": "click", "why": f"callout {oid}"})
        elif typ == "text" and float(o.get("size", 0)) >= 80 and o.get("space") == "screen":
            sc = o.get("_scene")
            if sc not in big_done:
                big_done.add(sc)
                last = sc == tl.scenes[-1]["id"]
                ev.append({"t": t + 0.1, "role": "impact" if last else "flash", "why": f"tiêu đề lớn {oid}"})
        elif typ in ("rect", "icon", "circle", "stack") and not o.get("parent") and float(o.get("r", 0) or 0) < 300:
            ev.append({"t": t, "role": "pop", "why": f"{typ} {oid}"})
        elif typ in ("image", "video", "quote"):
            ev.append({"t": t, "role": "camera" if typ != "quote" else "paper", "why": f"{typ} {oid}"})
        if typ == "list":
            for it in o.get("items", []):
                if isinstance(it, dict) and it.get("t") is not None:
                    ev.append({"t": float(it["t"]), "role": "tick", "why": f"mục {it.get('text', '')[:12]}"})
    # 3) tuyến/đường bắt đầu vẽ → swish nhẹ; nét gạch chân (marker) → write
    for oid, evs in tl.events.items():
        o = tl.objs[oid]
        for e in evs:
            if e["action"] == "draw" and o["type"] in ("geoline", "line") and float(e.get("end_s", e["start_s"])) - float(e["start_s"]) >= 0.5:
                ev.append({"t": float(e["start_s"]) + 0.1, "role": "swish", "why": f"vẽ {oid}"})
    for oid, o in tl.objs.items():
        if o["type"] == "text" and (o.get("marker") or {}).get("t") is not None:
            ev.append({"t": float(o["marker"]["t"]), "role": "write", "why": f"marker {oid}"})
    # 4) chuyển cảnh phủ
    for sc in tl.scenes:
        tr = sc.get("transition_in") or {}
        if tr.get("type") in ("bars", "wipe", "flip"):
            ev.append({"t": float(sc["start_s"]), "role": "transition", "why": f"chuyển cảnh {sc['id']}"})
    # lọc: tránh SFX tay, giãn cách, giới hạn mật độ (ưu tiên vai trò quan trọng)
    manual = sorted(float(e["t"]) for sc in tl.scenes for e in sc.get("audio_events", []))
    prio = {"impact": 0, "flash": 1, "transition": 1, "whoosh": 2, "click": 3, "write": 3, "camera": 3, "paper": 3,
            "pop": 4, "swish": 5, "tick": 5}
    ev = [e for e in ev if 0 <= e["t"] < tl.duration and not any(abs(e["t"] - m) < 0.3 for m in manual)]
    ev.sort(key=lambda e: (prio.get(e["role"], 9), e["t"]))
    out = []
    for e in ev:
        if any(abs(e["t"] - o["t"]) < 0.25 for o in out):
            continue
        win = [o for o in out if abs(o["t"] - e["t"]) < 1.0]
        if len(win) >= 1 and prio.get(e["role"], 9) >= 4:   # âm nhẹ: tối đa ~1/giây quanh đó
            continue
        out.append(e)
    out.sort(key=lambda e: e["t"])
    counters: dict = {}
    for e in out:   # xoay vòng âm trong từng vai trò → không lặp một âm liên tục
        k = counters.get(e["role"], 0)
        e["k"] = k
        counters[e["role"]] = k + 1
    return out
