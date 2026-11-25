"""Nhạc nền piano do C-Cut TỰ SÁNG TÁC (skill Giá Trị).

  nhạc mẫu (tuỳ chọn) → phân tích: giọng (tonality), nhịp (BPM), cảm xúc, độ sáng/dày
  → viết giai điệu + hòa âm MỚI cùng giọng / nhịp / cảm xúc → tổng hợp tiếng piano (numpy, không cần soundfont)
  → mp3 dài đúng bằng video, có mở – phát triển – cao trào – kết, nhỏ dần cuối.

KHÔNG chép giai điệu của nhạc mẫu (có bản quyền, Facebook quét ra sẽ tắt tiếng): chỉ lấy không khí — giọng, nhịp, cảm xúc.
Giai điệu / hòa âm sinh từ hạt giống (seed) → cùng seed = cùng chủ đề của kênh (nghe quen tai), khác seed = bài khác.
Thư viện: <dữ liệu app>/music_lib/<id>.json + .mp3 (giọng, nhịp, cảm xúc, seed, nhạc mẫu chỉ ghi TÊN file) để dùng lại.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import numpy as np

from .paths import ROOT

SR = 44100
LIB = ROOT / "music_lib"
NOTE_NAMES = ["Đô", "Đô♯", "Rê", "Rê♯", "Mi", "Fa", "Fa♯", "Sol", "Sol♯", "La", "La♯", "Si"]
_MAJ = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])      # Krumhansl–Kessler
_MIN = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
TONES = {      # tông gợi ý của kênh (trường "tone" khi không có nhạc mẫu)
    "thien-nhien": {"mode": "major", "bpm": 66, "tonic": 7, "mood": "bình yên, trong trẻo"},
    "pho-dem": {"mode": "minor", "bpm": 62, "tonic": 9, "mood": "buồn nhẹ, trầm lắng"},
    "doi-thuong-am": {"mode": "major", "bpm": 70, "tonic": 0, "mood": "ấm áp, gần gũi"},
}


def _ffmpeg() -> str:
    import shutil
    return shutil.which("ffmpeg") or "ffmpeg"


# ---------------- phân tích nhạc mẫu ----------------
def _load(path: Path, secs: float = 75.0, sr: int = 22050) -> np.ndarray:
    r = subprocess.run([_ffmpeg(), "-v", "error", "-i", str(path), "-t", str(secs), "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                       capture_output=True)
    if r.returncode or not r.stdout:
        raise ValueError("không đọc được nhạc mẫu")
    return np.frombuffer(r.stdout, np.float32)


def analyze(ref: str | Path) -> dict:
    """→ {tonic, mode, bpm, brightness, energy, mood, key_name}. Chỉ trích đặc trưng chung, không giữ giai điệu."""
    x = _load(Path(ref))
    sr = 22050
    n_fft, hop = 4096, 2048
    win = np.hanning(n_fft)
    frames = [x[i:i + n_fft] * win for i in range(0, len(x) - n_fft, hop)]
    if len(frames) < 8:
        raise ValueError("nhạc mẫu quá ngắn")
    S = np.abs(np.fft.rfft(np.array(frames), axis=1))
    freqs = np.fft.rfftfreq(n_fft, 1 / sr)
    band = (freqs > 65) & (freqs < 2100)
    pc = (np.round(12 * np.log2(freqs[band] / 440.0)).astype(int) + 9) % 12
    chroma = np.zeros(12)
    for k in range(12):
        chroma[k] = S[:, band][:, pc == k].sum()
    chroma /= chroma.sum() + 1e-9
    best = (-2, 0, "major")
    for t in range(12):
        for prof, mode in ((_MAJ, "major"), (_MIN, "minor")):
            c = np.corrcoef(chroma, np.roll(prof, t))[0, 1]
            if c > best[0]:
                best = (c, t, mode)
    _, tonic, mode = best
    # nhịp: độ biến thiên phổ (spectral flux) → tự tương quan
    flux = np.maximum(0, np.diff(np.log1p(S[:, band]), axis=0)).sum(1)
    flux = flux - flux.mean()
    fr = sr / hop
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    lo, hi = int(fr * 60 / 140), int(fr * 60 / 52)
    lag = lo + int(np.argmax(ac[lo:hi])) if hi > lo else int(fr)
    bpm = 60 * fr / max(lag, 1)
    while bpm > 100:
        bpm /= 2
    while bpm < 52:
        bpm *= 2
    cent = float((S * freqs).sum() / (S.sum() + 1e-9))
    energy = float(np.sqrt((x ** 2).mean()))
    bright = cent > 1100
    if mode == "minor":
        mood = "buồn nhẹ, trầm lắng" if bpm < 75 and not bright else "man mác, suy tư"
    else:
        mood = "ấm áp, bình yên" if bpm < 75 else "tươi sáng, nhẹ nhàng"
    return {"tonic": int(tonic), "mode": mode, "bpm": round(float(bpm), 1), "brightness": round(cent, 1), "energy": round(energy, 4),
            "mood": mood, "key_name": f"{NOTE_NAMES[tonic]} {'trưởng' if mode == 'major' else 'thứ'}"}


# ---------------- tổng hợp piano ----------------
def _midi_hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


_CACHE: dict = {}


def _piano(m: int, vel: float, dur: float) -> np.ndarray:
    """một nốt piano: các hoạ âm có độ lệch nhẹ, hoạ âm cao tắt nhanh hơn, tiếng búa gõ ngắn, đuôi ngân tự nhiên."""
    key = (m, round(vel * 8), round(dur * 4))
    if key in _CACHE:
        return _CACHE[key]
    f0 = _midi_hz(m)
    L = int(SR * (dur + 2.6))
    t = np.arange(L) / SR
    out = np.zeros(L)
    B = 0.00012 * (1 + (m - 40) / 50)
    for h in range(1, 9):
        fh = f0 * h * np.sqrt(1 + B * h * h)
        if fh > 9000:
            break
        amp = (1.0 / h ** 1.15) * (1.0 if h < 5 else 0.7)
        dec = (1.1 + 0.7 * h) / (1.0 + (m - 21) / 40)          # nốt cao tắt nhanh hơn
        out += amp * np.exp(-dec * t * 0.9) * np.sin(2 * np.pi * fh * t + h * 0.7)
    att = np.minimum(1, t / 0.006)
    rel = np.where(t > dur, np.exp(-(t - dur) * 4.5), 1.0)       # nhả phím
    env = att * rel
    rng = np.random.default_rng(m)
    hammer = rng.standard_normal(int(SR * 0.012)) * np.exp(-np.arange(int(SR * 0.012)) / (SR * 0.003)) * 0.05
    out = out * env
    out[:len(hammer)] += hammer * vel
    out *= vel * 0.5
    _CACHE[key] = out.astype(np.float32)
    return _CACHE[key]


def _reverb(L: np.ndarray, R: np.ndarray, wet: float = 0.28) -> tuple[np.ndarray, np.ndarray]:
    from scipy.signal import fftconvolve
    rng = np.random.default_rng(7)
    n = int(SR * 2.2)
    env = np.exp(-np.arange(n) / (SR * 0.55))
    ir_l, ir_r = rng.standard_normal(n) * env, rng.standard_normal(n) * env
    ir_l[0] = ir_r[0] = 0
    wl, wr = fftconvolve(L, ir_l)[:len(L)], fftconvolve(R, ir_r)[:len(R)]
    k = wet * (np.abs(L).max() + 1e-9) / (np.abs(wl).max() + 1e-9)
    return L * (1 - wet * 0.5) + wl * k, R * (1 - wet * 0.5) + wr * k


_PROG = {
    "minor": [[0, 5, 2, 6], [0, 3, 5, 4], [0, 6, 5, 6], [0, 2, 6, 3], [0, 5, 3, 6]],         # bậc trong gam thứ tự nhiên (0=i)
    "major": [[0, 4, 5, 3], [0, 5, 3, 4], [0, 2, 3, 4], [5, 3, 0, 4], [0, 3, 0, 4]],
}
_SCALE = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10]}


def compose(tonic: int, mode: str, bpm: float, duration: float, seed: int, mood: str = "") -> np.ndarray:
    """→ stereo float32 (2, N), dài `duration` giây. Mở → phát triển → cao trào → kết (về chủ âm)."""
    rng = np.random.default_rng(seed)
    beat = 60.0 / bpm
    bar = 4 * beat
    nbars = max(4, int(np.ceil(duration / bar)) + 1)
    scale = _SCALE[mode]
    prog = _PROG[mode][int(rng.integers(len(_PROG[mode])))]
    n = int(SR * (duration + 4))
    L, R = np.zeros(n, np.float32), np.zeros(n, np.float32)

    def deg_midi(deg: int, octave: int) -> int:
        return 12 * (octave + 1) + tonic + scale[deg % 7] + 12 * (deg // 7)

    def add(m: int, t0: float, vel: float, dur: float, pan: float = 0.0):
        w = _piano(m, vel, dur)
        i = int(t0 * SR)
        if i >= n:
            return
        seg = w[: n - i]
        L[i:i + len(seg)] += seg * (0.5 - pan * 0.4)
        R[i:i + len(seg)] += seg * (0.5 + pan * 0.4)

    phrase = [0, 2, 4, 2, 5, 4, 2, 1]                        # hình dáng giai điệu khởi đầu (sinh theo seed bên dưới)
    mel_deg = int(rng.choice([2, 4, 7]))
    for b in range(nbars):
        t_bar = b * bar
        pos = t_bar / max(duration, 1)
        chord_root = prog[b % 4]
        tones = [chord_root, chord_root + 2, chord_root + 4]
        intro, outro = pos < 0.12, pos > 0.86
        climax = 0.55 < pos < 0.8
        # tay trái: nốt trầm giữ
        add(deg_midi(chord_root, 2), t_bar, 0.55 + 0.1 * climax, bar * 0.95, -0.4)
        if not intro and rng.random() < 0.6:
            add(deg_midi(chord_root, 2) + 7, t_bar + 2 * beat, 0.4, beat * 1.8, -0.3)
        # tay phải: rải hợp âm nốt móc đơn
        pat = [0, 1, 2, 1, 2, 1, 2, 1] if rng.random() < 0.5 else [0, 2, 1, 2, 0, 2, 1, 2]
        if outro:
            pat = [0, 1, 2] + [1] * 0 + [2]
        step = beat / 2 if not outro else beat
        for k, ti in enumerate(pat):
            vel = (0.32 + 0.07 * climax + 0.04 * rng.random()) * (0.9 if k % 2 else 1.0)
            add(deg_midi(tones[ti], 4 + (1 if climax and k % 4 == 3 else 0)), t_bar + k * step, vel, step * 1.6, 0.15)
        # giai điệu thưa: vào sau phần mở, dày dần ở cao trào, thưa lại ở đoạn kết
        if not intro:
            nn = 3 if climax else (1 if outro else 2)
            slots = sorted(rng.choice(8, size=nn, replace=False))
            for sl in slots:
                mel_deg += int(rng.choice([-2, -1, -1, 0, 1, 1, 2]))
                mel_deg = int(np.clip(mel_deg, 0, 10))
                m = deg_midi(mel_deg, 5)
                add(m, t_bar + sl * beat / 2, 0.52 + 0.1 * climax, beat * (2.4 if sl % 2 == 0 else 1.2), 0.25)
        if b == nbars - 1 or (t_bar + bar >= duration):          # kết: về chủ âm
            add(deg_midi(0, 3), t_bar, 0.5, bar * 2, -0.3)
            add(deg_midi(4, 4), t_bar + beat, 0.4, bar * 2, 0.1)
            add(deg_midi(7, 5), t_bar + 2 * beat, 0.45, bar * 2, 0.25)
            break
    L, R = _reverb(L, R)
    out = np.stack([L, R])[:, : int(SR * (duration + 1.0))]
    pk = np.abs(out).max() + 1e-9
    out = out / pk * 0.85
    N = out.shape[1]
    fi = int(SR * 1.2)
    out[:, :fi] *= np.linspace(0, 1, fi)
    fo = int(SR * 2.4)
    out[:, N - fo:] *= np.linspace(1, 0, fo) ** 1.5              # nhỏ dần ~2 giây cuối
    return out.astype(np.float32)


# ---------------- dùng trong dự án ----------------
def make(pdir: str | Path, duration: float, ref: str | None = None, tone: str | None = None, seed: int | None = None,
         name: str = "giatri", log=print) -> dict:
    """tạo nhạc cho dự án: assets_web/m_<name>.mp3 + lưu vào thư viện. → meta."""
    pdir = Path(pdir)
    info: dict
    if ref:
        info = analyze(ref)
        info["from"] = "nhạc mẫu (chỉ lấy giọng / nhịp / cảm xúc)"
    else:
        t = TONES.get(tone or "", TONES["doi-thuong-am"])
        info = {"tonic": t["tonic"], "mode": t["mode"], "bpm": float(t["bpm"]), "mood": t["mood"],
                "key_name": f"{NOTE_NAMES[t['tonic']]} {'trưởng' if t['mode'] == 'major' else 'thứ'}", "from": f"tông kênh “{tone or 'mặc định'}”"}
    if seed is None:
        seed = int(time.time()) % 100000
    info["bpm"] = float(np.clip(info["bpm"], 54, 84))                          # nhạc ngẫm: không quá nhanh
    log(f"Nhạc nền: {info['key_name']} · {info['bpm']:.0f} BPM · {info['mood']}")
    wav = compose(info["tonic"], info["mode"], info["bpm"], duration, seed, info["mood"])
    out = pdir / "assets_web" / f"m_{name}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = out.with_suffix(".f32")
    raw.write_bytes(wav.T.astype("<f4").tobytes())
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", str(raw), "-b:a", "192k", str(out)], check=True)
    raw.unlink(missing_ok=True)
    LIB.mkdir(parents=True, exist_ok=True)
    mid = f"{time.strftime('%Y%m%d-%H%M%S')}-s{seed}"
    meta = {"id": mid, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "project": pdir.name, "duration_s": round(duration, 1), "seed": seed,
            "key": info["key_name"], "tonic": info["tonic"], "mode": info["mode"], "bpm": info["bpm"], "mood": info["mood"],
            "source": info.get("from"), "ref_name": Path(ref).name if ref else None, "tone": tone, "file": f"{mid}.mp3"}
    (LIB / f"{mid}.mp3").write_bytes(out.read_bytes())
    (LIB / f"{mid}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (pdir / "music.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta



def fit_library(pdir: str | Path, mid: str, duration: float, log=print) -> dict:
    """nhạc THƯ VIỆN miễn phí (Mixkit License — dùng được cho video, kể cả thương mại, không cần ghi nguồn) thay cho nhạc tự sáng tác:
    tải `mixkit:<mã>` → cắt / lặp đúng độ dài video, mờ vào 1,2s, nhỏ dần ~2,4s cuối → assets_web/m_giatri.mp3. Lưu thông tin vào thư viện."""
    from .v2m.broll import music_fetch
    pdir = Path(pdir)
    if stored(mid):                                  # đã có trong kho trên máy → không tải lại
        src = pdir / "assets_web" / f"m_{str(mid).removeprefix('mixkit:')}.mp3"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(store_path(mid).read_bytes())
    else:
        src = music_fetch(pdir, mid)
        try:
            STORE.mkdir(parents=True, exist_ok=True)
            store_path(mid).write_bytes(src.read_bytes())     # bài đã dùng cũng vào kho
        except Exception:
            pass
    out = pdir / "assets_web" / "m_giatri.mp3"
    fo = 2.4
    subprocess.run([_ffmpeg(), "-v", "error", "-y", "-stream_loop", "-1", "-i", str(src), "-t", f"{duration:.2f}",
                    "-af", f"afade=t=in:d=1.2,afade=t=out:st={max(0.1, duration - fo):.2f}:d={fo}", "-b:a", "192k", str(out)], check=True)
    meta = {"id": f"library-{str(mid).replace(':', '-')}", "created": time.strftime("%Y-%m-%d %H:%M:%S"), "project": pdir.name,
            "duration_s": round(duration, 1), "source": f"thư viện Mixkit ({mid}) — Mixkit License, dùng miễn phí", "file": out.name}
    (pdir / "music.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Nhạc nền: thư viện Mixkit {mid}")
    return meta




# ---------------- KHO NHẠC trên máy (music_lib/mixkit/<mã>.mp3) ----------------
STORE = ROOT / "music_lib" / "mixkit"


def store_path(mid: str) -> Path:
    return STORE / f"{str(mid).removeprefix('mixkit:')}.mp3"


def stored(mid: str) -> bool:
    f = store_path(mid)
    return f.exists() and f.stat().st_size > 100_000


def _download(mid: str, dst: Path) -> None:
    import urllib.request
    mid = str(mid).removeprefix("mixkit:")
    req = urllib.request.Request(f"https://assets.mixkit.co/music/{mid}/{mid}.mp3", headers={"User-Agent": "Mozilla/5.0"})
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".part")
    tmp.write_bytes(urllib.request.urlopen(req, timeout=90).read())
    tmp.replace(dst)


SYNC = {"busy": False, "done": 0, "total": 0, "error": None}


def sync(n: int = 60, log=print) -> dict:
    """tải ~n bài nhạc nhẹ nhất trong danh mục (kèm các bài featured) về kho trên máy — dùng ngoại tuyến, video không phải tải lại.
    Chỉ lưu trên máy này (KHÔNG đóng gói vào app, KHÔNG đưa lên git): Mixkit cho dùng trong video nhưng không cho phát lại file nhạc rời."""
    rows = [r for r in catalog() if r.get("dur_s", 0) >= 100]
    n = max(n, 0) or len(rows)
    feat = []
    try:
        feat = list((json.loads((ROOT / "assets" / "music_catalog.json").read_text(encoding="utf-8")).get("featured") or {}).values())[0]["tracks"]
    except Exception:
        pass
    ids = list(dict.fromkeys(feat + [r["id"] for r in sorted(rows, key=lambda r: -r["soft_score"])]))[:n]
    SYNC.update(busy=True, done=0, total=len(ids), error=None)
    ok = 0
    try:
        for i in ids:
            if not stored(i):
                try:
                    _download(i, store_path(i))
                except Exception as e:
                    log(f"  bỏ qua {i}: {type(e).__name__}")
                    continue
            ok += 1
            SYNC["done"] = ok
    finally:
        SYNC["busy"] = False
    return {"requested": len(ids), "stored": ok, "folder": str(STORE)}


# ---------------- danh mục nhạc thư viện (assets/music_catalog.json — đi kèm app) ----------------
def catalog() -> list[dict]:
    f = ROOT / "assets" / "music_catalog.json"
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("tracks", [])
    except Exception:
        return []


def pick_from_catalog(tone: str | None = None, seed: int | None = None, ref_info: dict | None = None, min_dur: float = 100.0) -> str | None:
    """chọn nhạc thư viện cho video: có nhạc mẫu → bài GẦN NHẤT về giọng (trưởng / thứ), nhịp, độ sáng; không có → theo tông kênh
    (thien-nhien: trưởng · pho-dem: thứ · doi-thuong-am: bất kỳ), ưu tiên piano + soft_score cao; seed cố định → cùng bài (kênh nghe quen tai)."""
    import random
    rows = [r for r in catalog() if r.get("dur_s", 0) >= min_dur]
    rows = [r for r in rows if r.get("kieu") == "A"] or rows      # MẶC ĐỊNH chỉ nhóm A (đúng kiểu mixkit:688); B chỉ khi chọn tay bằng music_id
    if not rows:
        return None
    if ref_info:
        def dist(r):
            return ((0 if r["mode"] == ref_info["mode"] else 1.5) + abs(r["bpm"] - ref_info["bpm"]) / 40
                    + abs(r["brightness"] - ref_info.get("brightness", r["brightness"])) / 1500 + (0 if r.get("piano") else 0.3) - r["soft_score"] * 0.6)
        return sorted(rows, key=dist)[0]["id"]
    suit = [r for r in rows if tone in r.get("suit", [])] or rows
    top = sorted(suit, key=lambda r: -r["soft_score"])[:8]
    rng = random.Random(seed if seed is not None else time.time())
    return rng.choice(top)["id"]


if __name__ == "__main__":
    import sys
    a = sys.argv[1:]
    if not a:
        print(__doc__)
    elif a[0] == "analyze":
        print(json.dumps(analyze(a[1]), ensure_ascii=False, indent=1))
    elif a[0] == "sync":      # sync [số bài=60]
        print(json.dumps(sync(int(a[1]) if len(a) > 1 else 60), ensure_ascii=False, indent=1))
    elif a[0] == "make":      # make <dự-án> <giây> [nhạc mẫu] [tone] [seed]
        print(json.dumps(make(a[1], float(a[2]), a[3] if len(a) > 3 and a[3] != "-" else None, a[4] if len(a) > 4 and a[4] != "-" else None,
                              int(a[5]) if len(a) > 5 else None), ensure_ascii=False, indent=1))
