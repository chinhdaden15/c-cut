"""Bộ khung dựng sẵn cho Voice to Motion — một builder, tự xuất bố cục dọc 9:16 và ngang 16:9.

Claude chỉ cần: chia cảnh theo lời → gọi các khối có sẵn (tiêu đề, câu dẫn, icon, thẻ, số liệu, so sánh, danh sách,
trích dẫn, ảnh, biểu đồ, bản đồ + callout/tuyến) với mốc từ transcript. Vị trí, cỡ chữ, căn lề, hiệu ứng vào/ra,
camera bản đồ được kit tính theo từng tỷ lệ (Frame) — KHÔNG hard-code toạ độ.

    from thagent.v2m.kit import build
    def content(K):
        s = K.scene(0, K.find("tuy nhiên"), "mở đầu")
        s.title("GIÁ VÀNG\\nTĂNG TRỞ LẠI", K.find("giá vàng"), hl="TĂNG TRỞ LẠI")
        s.icons([("dollar", "Đồng đô la", K.find("đô la")), ("bank", "Lãi suất", K.find("lãi suất"))])
        ...
    build(__file__, content)          # → timeline_9x16.json + timeline_16x9.json

Mốc thời gian: K.find("cụm từ", after=giây) = giây bắt đầu nói cụm đó (bỏ dấu câu, không phân biệt hoa thường).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

from .layout import Frame
from .render import geo_xy

# ---------------- bộ màu (theme) ----------------
THEMES = {
    # tin tức, tài chính, công nghệ, bản đồ — nền tối
    "dark": {"bg": "#0E1420", "bg2": "#141B2B", "glow": "#1E2A44", "text": "#FFFFFF", "muted": "#8E97A8", "accent": "#F2C14E",
             "alt": "#F0504A", "good": "#2FBF71", "panel": "#1A2232", "ink_on_accent": "#3A2805", "deco": ["dots", "dashes"],
             "deco_color": "#4A5470", "land": "#1B2534", "border": "#33445C"},
    # sức khỏe, giáo dục, đời sống, làm đẹp — nền sáng ấm
    "warm": {"bg": "#F5EFE4", "bg2": "#EADFCB", "glow": "#FFF8EC", "text": "#23302B", "muted": "#7C7A70", "accent": "#B5462E",
             "alt": "#2F6B57", "good": "#2F6B57", "panel": "#FFFFFF", "ink_on_accent": "#FFFFFF", "deco": ["dots", "dashes"],
             "deco_color": "#A99C84", "land": "#E3D8C4", "border": "#B9AA8E"},
    # bất động sản, hạ tầng, giao thông — xanh đêm + vàng/cyan
    "map": {"bg": "#0A1626", "bg2": "#0B1A2D", "glow": "#10233A", "text": "#FFFFFF", "muted": "#9FB0C6", "accent": "#F5C443",
            "alt": "#33D1E0", "good": "#3CC57E", "panel": "#12233A", "ink_on_accent": "#2A1E02", "deco": [],
            "deco_color": "#2A3F5A", "land": "#182A3E", "border": "#46607F"},
}

# màu tô quốc gia: đậm vừa, khác hẳn nhau (kể cả nước liền kề), đủ tương phản với tên trắng có viền tối.
# Gán theo thứ tự xuất hiện → cùng nội dung thì dọc và ngang cùng màu. Ghi đè: K.colors["VNM"] = "#…"
COUNTRY_COLORS = ["#C98A1B", "#2B8A9E", "#B4543A", "#4F6FC4", "#3D8F5F", "#8A55B0", "#A8743A", "#2F7D86"]

SIZES = {"xl": (104, 112), "l": (84, 92), "m": (60, 64), "s": (46, 48)}     # (dọc, ngang) cỡ tiêu đề


def fit_size(text: str, role: str, size: float, max_w: float, floor: float = 0.45) -> int:
    """thu cỡ chữ tới khi dòng dài nhất (theo \n) vừa max_w; không nhỏ hơn floor × cỡ gốc."""
    from . import draw as D
    s = float(size)
    while s > size * floor:
        if max(D.font(role, int(s)).getlength(l) for l in text.split("\n")) <= max_w:
            break
        s -= 2
    return int(s)


def _is_video(src: str) -> bool:
    return str(src).lower().endswith((".mp4", ".mov", ".m4v", ".webm", ".mkv"))


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^\w\s]", "", s).strip()


class Kit:
    def __init__(self, pdir, fmt: str, theme="dark", project_id: str | None = None):
        self.pdir = Path(pdir)
        self.F = Frame(fmt)
        self.fmt, self.V = fmt, self.F.portrait
        self.W, self.H = self.F.W, self.F.H
        tr = json.loads((self.pdir / "transcript.json").read_text(encoding="utf-8"))
        self.tr, self.words, self.T = tr, tr["words"], float(tr["duration_s"])
        self.th = dict(THEMES[theme]) if isinstance(theme, str) else {**THEMES["dark"], **theme}
        self.pid = project_id or self.pdir.name
        self.scenes: list[Scene] = []
        self.base: list[dict] = []          # lớp nền xuyên suốt (bản đồ, nguồn…)
        self._n = 0
        self._nw = [_norm(w["text"]) for w in self.words]
        self.colors: dict[str, str] = {}
        self._map_until = None
        self._drift = 1
        self.captions = True                # phụ đề chạy theo lời ở vùng dưới (tắt từng cảnh: s.captions = False)

    def color(self, iso: str) -> str:
        """màu nhất quán của một quốc gia trong cả video (và cả hai tỷ lệ)."""
        if iso not in self.colors:
            used = set(self.colors.values())
            self.colors[iso] = next((c for c in COUNTRY_COLORS if c not in used), COUNTRY_COLORS[len(self.colors) % len(COUNTRY_COLORS)])
        return self.colors[iso]

    def map_until(self, t: float):
        """nền bản đồ mờ ra lúc t — các cảnh sau là đồ họa riêng (nội dung không còn gắn vị trí)."""
        self._map_until = float(t)

    # ---------- thời gian từ transcript ----------
    def find(self, phrase: str, after: float | None = None, end: bool = False) -> float:
        """giây bắt đầu (end=True: giây kết thúc) của cụm từ, tìm từ mốc `after` (mặc định: đầu cảnh đang viết). Không thấy → báo lỗi rõ."""
        if after is None:
            after = self.scenes[-1].t0 if self.scenes else 0.0
        ps = [_norm(x) for x in phrase.split() if _norm(x)]
        for i in range(len(self.words) - len(ps) + 1):
            if self.words[i]["start"] + 1e-3 < after:
                continue
            if self._nw[i:i + len(ps)] == ps:
                return round(self.words[i + len(ps) - 1]["end"] if end else self.words[i]["start"], 3)
        raise ValueError(f"không thấy “{phrase}” sau {after:.2f}s — xem lại bằng: python -m thagent.v2m words <dự-án>")

    def wt(self, t0: float, t1: float) -> list[float]:
        """mốc từng từ trong [t0, t1) — dùng cho câu dẫn chạy theo lời."""
        return [w["start"] for w in self.words if t0 - 1e-3 <= w["start"] < t1]

    STOP = set("và là của có thì mà với cho các những một này đó được đã đang sẽ cũng như để từ ra vào lại rất nhưng nếu khi vì thế "
               "bạn mình tôi anh chị em ta chúng họ nó ở trong trên dưới không hay hoặc rồi nữa còn đây đấy kia nào gì ai sao".split())

    def beats(self, t0: float = 0.0, t1: float | None = None, every: float = 2.5) -> list[tuple[float, str]]:
        """gợi ý mốc nhịp: từ khóa (bỏ hư từ) cách nhau ≈ `every` giây trong [t0, t1). Dùng để đặt khối/đổi trạng thái theo lời."""
        t1 = self.T if t1 is None else t1
        out, last = [], -1e9
        for i, w in enumerate(self.words):
            if not (t0 <= w["start"] < t1) or self._nw[i] in self.STOP or len(self._nw[i]) < 3:
                continue
            if w["start"] - last >= every:
                nxt = self.words[i + 1]["text"] if i + 1 < len(self.words) else ""
                out.append((round(w["start"], 2), f'{w["text"]} {nxt}'.strip()))
                last = w["start"]
        return out

    def phrases(self, t0: float, t1: float, max_words: int | None = None) -> list[tuple[float, float, list[dict]]]:
        """chia lời trong [t0, t1) thành cụm đọc (ngắt ở dấu câu, chỗ ngừng > 0,35s, hoặc đủ số từ)."""
        mw = max_words or (7 if self.V else 9)
        ws = [w for w in self.words if t0 - 1e-3 <= w["start"] < t1]
        out, cur = [], []
        for i, w in enumerate(ws):
            if cur and w["text"][:1].isupper() and not w["text"].isupper() and len(cur) >= 2:   # chữ hoa đầu câu (ASR thiếu dấu chấm)
                out.append((cur[0]["start"], cur[-1]["end"], cur)); cur = []
            cur.append(w)
            gap = (ws[i + 1]["start"] - w["end"]) if i + 1 < len(ws) else 9
            if re.search(r"[.,!?;:…]$", w["text"]) or gap > 0.35 or len(cur) >= mw:
                out.append((cur[0]["start"], cur[-1]["end"], cur)); cur = []
        if cur:
            out.append((cur[0]["start"], cur[-1]["end"], cur))
        return out

    def text_between(self, t0: float, t1: float) -> str:
        return " ".join(w["text"] for w in self.words if t0 - 1e-3 <= w["start"] < t1)

    def uid(self, p="o") -> str:
        self._n += 1
        return f"{p}{self._n}"

    # ---------- bố cục ----------
    def zone(self, name):
        return self.F.zone(name)

    def at_zone(self, name, rx=0.5, ry=0.5):
        x0, y0, x1, y1 = self.F.zone(name)
        return x0 + (x1 - x0) * rx, y0 + (y1 - y0) * ry

    def text_anchor(self, region="text"):
        """dọc: căn giữa trong dải trên; ngang: cột chữ trái, căn trái."""
        x0, y0, x1, y1 = self.F.zone(region)
        if self.V or region == "title":
            return (x0 + x1) / 2, "center", "center", x1 - x0
        return x0, "left", "left", x1 - x0

    def grid(self, n: int, region="main", cols: int | None = None, pad=0.12):
        """vị trí n ô đều nhau trong vùng: ≤3 → một hàng, 4 → 2×2, 5–6 → 3×2 (dọc: 2×3)."""
        x0, y0, x1, y1 = self.F.zone(region)
        if cols is None:
            cols = n if n <= 3 else (2 if n == 4 or (self.V and n > 4) else 3)
        rows = -(-n // cols)
        w, h = (x1 - x0) * (1 - pad), (y1 - y0) * (1 - pad)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        out = []
        for i in range(n):
            r, c = divmod(i, cols)
            nc = min(cols, n - r * cols)
            out.append((cx + (c - (nc - 1) / 2) * w / cols, cy + (r - (rows - 1) / 2) * min(h / rows, 330)))
        return out, w / cols

    # ---------- cảnh ----------
    def scene(self, t0: float, t1: float, purpose: str = "", transition: str | dict | None = "fade", bg: dict | None = None):
        s = Scene(self, float(t0), float(t1), purpose, transition, bg)
        self.scenes.append(s)
        return s

    def chapters(self, cuts: list[float]):
        """cắt [0, T] thành cảnh liền nhau theo mốc → list Scene (mốc thường lấy bằng K.find)."""
        b = [0.0] + sorted(cuts) + [self.T]
        return [self.scene(b[i], b[i + 1]) for i in range(len(b) - 1)]

    # ---------- lớp nền bản đồ ----------
    def world_map(self, source=True):
        self.base.append({"id": "map", "type": "map", "fill": self.th["land"], "stroke": self.th["border"], "stroke_w": 1.2,
                          "persist": True, "layer": -10})
        if source:
            self.source("Bản đồ: Natural Earth (public domain)")

    def provinces(self, files: list[str], labels: dict | None = None, source=True):
        """ranh giới tỉnh (assets/geo/vn34/*.geojson). labels {tên trong geojson: (chữ hiển thị, lon, lat)} → tên nằm TRONG tỉnh."""
        files = [f if "/" in f else f"assets/geo/vn34/{f}.geojson" for f in files]
        self.base.append({"id": "prov", "type": "geo", "src": files, "fill": self.th["land"], "stroke": self.th["border"],
                          "stroke_w": 1.6, "persist": True, "layer": -10})
        for name, (lab, lon, lat) in (labels or {}).items():
            f = next((x for x in files if _norm(name).replace(" ", "_") in x.replace("-", "_")), files[0])
            x, y = geo_xy(lon, lat)
            self.base.append({"id": self.uid("pl"), "type": "text", "text": lab.upper(), "font": "semi", "size": 22, "color": "#B8C6D8",
                              "x": x, "y": y, "inside": {"src": f, "name": name}, "min_size": 20, "lod": [55, 160], "persist": True,
                              "layer": 5, "shadow": 0.6})
        if source:
            self.source("Ranh giới: thanglequoc/vietnamese-provinces-database · © OpenStreetMap contributors")

    def source(self, text: str):
        if any(o["id"] == "src" for o in self.base):
            return
        self.base.append({"id": "src", "type": "text", "text": text, "font": "medium", "size": 20, "color": self.th["muted"],
                          "space": "screen", "x": self.W / 2, "y": self.F.center("source")[1], "persist": True, "shadow": 0,
                          "max_w": self.F.width("source")})

    # ---------- xuất ----------
    def timeline(self) -> dict:
        sc = sorted(self.scenes, key=lambda s: s.t0)
        self._captions(sc)
        self._camera_explain(sc)
        self._camera_chain(sc)
        out = []
        for i, s in enumerate(sc):
            d = s.dump()
            if i == 0:
                d["objects"] = self.base + d["objects"]
                d.pop("transition_in", None)
            out.append(d)
        if out:
            out[-1]["end_s"] = max(out[-1]["end_s"], self.T)
        if self._map_until is not None:
            for o in self.base:
                if o["type"] in ("map", "geo") or o["id"] == "src":
                    o.pop("persist", None)
                    o["until_s"] = round(self._map_until, 3)
        th = {k: v for k, v in self.th.items() if k not in ("panel", "ink_on_accent", "good", "land", "border")}
        th.setdefault("idle", True)      # khối sống sau khi hiện (trôi/giãn nhẹ)
        return {"project_id": self.pid, "version": 1, "status": "planned",
                "audio": {"path": self.tr["voice"], "duration_s": self.T, "preserve_timing": True},
                "canvas": self.F.canvas(30), "theme": th, "scenes": out, "assets": [], "limitations": []}

    def _captions(self, scenes):
        """phụ đề chạy theo lời (từng từ hiện đúng lúc nói) ở vùng dưới — cảnh đã có câu dẫn (s.lead) thì bỏ qua."""
        if not self.captions:
            return
        x0, y0, x1, y1 = self.F.zone("caption")
        x, align, anchor = ((x0 + x1) / 2, "center", "center") if self.V else (x0, "left", "left")
        for s in scenes:
            if s.captions is False or any(o.get("word_times") and o.get("role") != "caption" for o in s.objs):
                continue
            ph = self.phrases(s.t0, s.t1)
            for j, (a, b, ws) in enumerate(ph):
                nxt = ph[j + 1][0] if j + 1 < len(ph) else s.t1
                end = max(min(b + 0.35, nxt - 0.2, s.t1 - 0.15), a + 0.3)   # mờ hẳn trước khi cụm sau hiện → không chồng
                cid = s.add({"type": "text", "role": "caption", "text": " ".join(w["text"] for w in ws), "font": "semi",
                             "size": 50 if self.V else 42, "color": self.th["text"], "space": "screen", "x": x, "y": (y0 + y1) / 2,
                             "max_w": x1 - x0, "align": align, "anchor": anchor, "shadow": 0.35, "line_h": 1.15,
                             "word_times": [round(w["start"], 3) for w in ws], "layer": 20}, a - 0.04, "fade", 0.12)
                s.hide(cid, end, "fade", 0.12)

    def _camera_explain(self, scenes):
        """nhịp Explain: cảnh bản đồ mà camera đứng yên > 2,2s → đẩy vào rất nhẹ (+6%) và xoay nhẹ ±2° quanh chủ thể
        cho tới cuối cảnh (chữ/nhãn vẫn thẳng). Không rung, không xoay vòng; mỗi cảnh đổi chiều xoay."""
        if not any(o["type"] in ("map", "geo") for o in self.base):
            return
        last = None
        for s in scenes:
            if self._map_until is not None and s.t0 >= self._map_until - 0.3:
                break
            s.cams.sort(key=lambda k: k["t"])
            if s.cams:
                last = s.cams[-1]
            if last is None or not s.auto_explain:
                continue
            t_free = max(float(last["t"]), s.t0)
            t_end = s.t1 - 0.05
            if t_end - t_free < 2.2:
                continue
            self._drift = -self._drift
            k = {"t": round(t_end, 3), "x": last["x"], "y": last["y"], "zoom": round(last["zoom"] * 1.06, 4),
                 "rot": 2.0 * self._drift, "dur": round(t_end - t_free - 0.05, 3), "ease": "inout"}
            s.cams.append(k)
            last = k

    def _camera_chain(self, scenes):
        """nối tiếp mượt: key sau không được khởi hành trước khi key trước tới nơi (chồng nhau → camera khựng giữa đường).
        Rút ngắn dur (≥0,6s) rồi mới lùi mốc tới."""
        prev = None
        for s in scenes:
            for k in sorted(s.cams, key=lambda k: k["t"]):
                if prev is not None:
                    start = k["t"] - k.get("dur", 0.6)
                    if start < prev["t"]:
                        k["dur"] = round(max(0.6, k["t"] - prev["t"]), 3)
                        k["t"] = round(max(k["t"], prev["t"] + k["dur"]), 3)
                prev = k

    def save(self) -> Path:
        f = self.pdir / f"timeline_{self.fmt}.json"
        f.write_text(json.dumps(self.timeline(), ensure_ascii=False, indent=1), encoding="utf-8")
        return f


class Scene:
    """một cảnh: các khối tự đặt theo tỷ lệ khung; mỗi khối nhận mốc `t` (giây) lúc xuất hiện."""

    def __init__(self, K: Kit, t0, t1, purpose, transition, bg):
        self.K, self.t0, self.t1, self.purpose = K, t0, t1, purpose
        self.objs, self.evs, self.cams, self.sfx = [], [], [], []
        self.transition = {"type": transition, "dur": 0.4} if isinstance(transition, str) else transition
        self.bg = bg
        self.exit = True                      # mờ ra nhẹ trước khi hết cảnh (đối tượng không persist)
        self.auto_explain = True              # camera trôi nhẹ khi cảnh bản đồ đứng yên lâu
        self.captions = True                  # phụ đề chạy theo lời trong cảnh này

    # ---------- nền tảng ----------
    def add(self, o: dict, t: float | None = None, style="up", d=0.4) -> str:
        o.setdefault("id", self.K.uid())
        self.objs.append(o)
        if t is not None:
            self.reveal(o["id"], t, style, d)
        return o["id"]

    def reveal(self, oid, t, style="up", d=0.4):
        self.evs.append({"object_id": oid, "action": "reveal", "start_s": round(t, 3), "end_s": round(t + d, 3), "style": style})

    def hide(self, oid, t, style="fade", d=0.35):
        self.evs.append({"object_id": oid, "action": "hide", "start_s": round(t, 3), "end_s": round(t + d, 3), "style": style})

    def animate(self, oid, t, d, to: dict, ease="inout"):
        self.evs.append({"object_id": oid, "action": "animate", "start_s": round(t, 3), "end_s": round(t + d, 3), "to": to, "ease": ease})

    def draw(self, oid, t, d=0.6):
        self.evs.append({"object_id": oid, "action": "draw", "start_s": round(t, 3), "end_s": round(t + d, 3), "ease": "inout"})

    def pulse(self, oid, t, d=0.5):
        self.evs.append({"object_id": oid, "action": "pulse", "start_s": round(t, 3), "end_s": round(t + d, 3)})

    def sound(self, t, role, gain_db=None):
        e = {"t": round(t, 2), "role": role}
        if gain_db is not None:
            e["gain_db"] = gain_db
        self.sfx.append(e)

    # ---------- chữ ----------
    def title(self, text, t, size="l", hl=None, color=None, ry=0.45, region="text", font="black", hl_color=None, style="up", **k) -> str:
        """tiêu đề/điểm nhấn lớn. dọc: dải trên, căn giữa; ngang: cột trái, căn trái. hl = cụm tô màu nhấn."""
        K = self.K
        x, align, anchor, mw = K.text_anchor(region)
        y = K.at_zone(region, 0.5, ry)[1]
        sz = SIZES[size][0 if K.V else 1] if isinstance(size, str) else size
        sz = fit_size(text, font, sz, mw * 0.96)     # dòng tự ngắt (\n) phải vừa cột, không để renderer bẻ giữa cụm
        o = {"type": "text", "text": text, "font": font, "size": sz, "color": color or K.th["text"], "space": "screen", "x": x, "y": y,
             "max_w": mw, "align": align, "anchor": anchor, "line_h": 1.05, "shadow": 0.25, **k}
        if hl:
            o["highlight"] = {"match": hl, "color": hl_color or K.th["accent"]}
        return self.add(o, t - 0.08, style, 0.4)

    def lead(self, t0, t1=None, text=None, ry=0.8, size=None, region="text", hl=None, **k) -> str:
        """câu dẫn chạy theo lời (word_times thật). Không truyền text → lấy đúng lời trong [t0, t1)."""
        K = self.K
        t1 = t1 or self.t1
        text = text or K.text_between(t0, t1)
        x, align, anchor, mw = K.text_anchor(region)
        o = {"type": "text", "text": text, "font": "semi", "size": size or (48 if K.V else 46), "color": K.th["muted"], "space": "screen",
             "x": x, "y": K.at_zone(region, 0.5, ry)[1], "max_w": mw, "align": align, "anchor": anchor, "shadow": 0,
             "word_times": K.wt(t0, t1)[:len(text.split())], **k}
        if hl:
            o["highlight"] = {"match": hl, "color": K.th["accent"]}
        return self.add(o, t0 - 0.05, "fade", 0.2)

    def tag(self, text, t, ry=0.12, color=None, region="text") -> str:
        """nhãn nhỏ dạng viên thuốc (ngày, chuyên mục, “TUY NHIÊN”)."""
        K = self.K
        x0, y0, x1, y1 = K.zone(region)
        sz = 40
        w = len(text) * sz * 0.62 + sz * 1.4
        x = (x0 + x1) / 2 if K.V else x0 + w / 2
        y = y0 + (y1 - y0) * ry
        rid = self.add({"type": "rect", "w": w, "h": sz * 1.9, "r": sz * 0.95, "fill": color or K.th["accent"], "space": "screen",
                        "x": x, "y": y}, t, "pop", 0.35)
        self.add({"type": "text", "text": text, "font": "black", "size": sz, "color": K.th["ink_on_accent"], "parent": rid, "x": 0, "y": 0,
                  "shadow": 0})
        return rid

    # ---------- minh họa ----------
    def icons(self, items, region="main", size=None, ring=True, connect=False, color=None) -> list[str]:
        """items [(icon, nhãn, t)] — nút icon có nhãn, tự xếp hàng/lưới. connect=True: nét đứt nối các nút."""
        K = self.K
        pos, cw = K.grid(len(items), region)
        sz = size or ((110 if K.V else 96) if len(items) <= 3 else (88 if K.V else 76))
        col = color or K.th["accent"]
        ids = []
        for (name, label, t), (x, y) in zip(items, pos):
            ids.append(self.add({"type": "icon", "name": name, "size": sz, "color": col, "bg": K.th["panel"], "bg_r": sz * 1.15,
                                 "ring": col if ring else None, "ring_w": 5, "x": x, "y": y - 40, "label": label,
                                 "label_size": 40 if K.V else 36, "label_color": K.th["text"], "space": "screen", "shadow": 0.25}, t, "pop", 0.35))
        if connect:
            for a, b in zip(ids, ids[1:]):
                lid = self.add({"type": "line", "from": a, "to": b, "width": 5, "color": K.th["muted"], "dash": 16, "gap": 10,
                                "trim_start": sz * 1.3, "trim_end": sz * 1.3, "layer": -1, "space": "screen", "progress": 0})
                tb = next(t for (_, _, t), i in zip(items, ids) if i == b)
                self.draw(lid, tb - 0.35, 0.4)
        return ids

    def cards(self, items, region="main", w=None, h=None) -> list[str]:
        """items [(icon, chữ, t)] — thẻ nền sáng/tối có icon trên, chữ dưới."""
        K = self.K
        pos, cw = K.grid(len(items), region)
        w = w or min(cw * 0.92, 360)
        h = h or w * 1.15
        ids = []
        for (name, text, t), (x, y) in zip(items, pos):
            rid = self.add({"type": "rect", "w": w, "h": h, "r": 30, "fill": K.th["panel"], "shadow": 0.25, "space": "screen", "x": x, "y": y},
                           t, "pop", 0.35)
            self.add({"type": "icon", "name": name, "size": w * 0.36, "color": K.th["accent"], "parent": rid, "x": 0, "y": -h * 0.14})
            self.add({"type": "text", "text": text, "font": "bold", "size": 40 if K.V else 36, "color": K.th["text"], "max_w": w * 0.86, "line_h": 1.1,
                      "parent": rid, "x": 0, "y": h * 0.27, "shadow": 0})
            ids.append(rid)
        return ids

    def stat(self, value, t, label=None, prefix="", suffix="", decimals=0, color=None, region="main", ry=0.42, count_d=0.9) -> str:
        """số liệu lớn chạy số + nhãn dưới. Chỉ dùng số có trong lời/nguồn."""
        K = self.K
        x, y = K.at_zone(region, 0.5, ry)
        cid = self.add({"type": "counter", "value": 0, "prefix": prefix, "suffix": suffix, "decimals": decimals, "font": "black",
                        "size": 150 if K.V else 160, "color": color or K.th["accent"], "space": "screen", "x": x, "y": y}, t, "pop", 0.35)
        self.evs.append({"object_id": cid, "action": "count", "start_s": round(t, 3), "end_s": round(t + count_d, 3),
                         "to": {"value": value}, "ease": "out"})
        if label:
            self.add({"type": "text", "text": label, "font": "bold", "size": 44, "color": K.th["text"], "space": "screen", "x": x,
                      "y": y + 130, "max_w": K.F.width(region) * 0.9, "shadow": 0}, t + 0.25, "up", 0.35)
        return cid

    def compare(self, a, b, t_a, t_b, vs="VS", region="main") -> list[str]:
        """so sánh hai vế: a/b = (icon, nhãn) hoặc (icon, nhãn, màu)."""
        K = self.K
        (x1, y), (x2, _) = K.grid(2, region)[0]
        ids = []
        for (it, t, x, c0) in ((a, t_a, x1, K.th["good"]), (b, t_b, x2, K.th["alt"])):
            col = it[2] if len(it) > 2 else c0
            ids.append(self.add({"type": "icon", "name": it[0], "size": 120, "color": col, "bg": K.th["panel"], "bg_r": 145, "ring": col,
                                 "ring_w": 6, "x": x, "y": y - 40, "label": it[1], "label_size": 42 if K.V else 38, "label_color": K.th["text"],
                                 "space": "screen"}, t, "pop", 0.35))
        self.add({"type": "text", "text": vs, "font": "black", "size": 54, "color": K.th["muted"], "space": "screen", "x": (x1 + x2) / 2,
                  "y": y - 30, "shadow": 0}, min(t_a + 0.4, t_b - 0.1), "fade", 0.3)
        return ids

    def bullets(self, items, region="main", pill=True, size=None) -> str:
        """danh sách từng mục theo lời: items [(chữ, t)]."""
        K = self.K
        n = len(items)
        sz = size or (52 if K.V else 46)
        gap = sz * (2.3 if pill else 1.7)
        x0, y0, x1, y1 = K.zone(region)
        x = (x0 + x1) / 2 if pill else x0 + 40
        y = (y0 + y1) / 2 - gap * (n - 1) / 2
        o = {"type": "list", "style": "pill" if pill else "dot", "size": sz, "gap": gap, "x": x, "y": y, "space": "screen",
             "items": [{"text": s, "t": round(t, 3)} for s, t in items]}
        if pill:
            o.update(pill_fill=K.th["alt"], pill_text="#FFFFFF")
        return self.add(o, items[0][1] - 0.1, "fade", 0.1)

    def quote(self, text, t, source=None, highlight=None, region="main") -> str:
        K = self.K
        x, y = K.F.center(region)
        return self.add({"type": "quote", "text": text, "source": source, "highlight": highlight, "highlight_t": t + 0.6,
                         "w": min(K.F.width(region) * 0.92, 900), "size": 40, "x": x, "y": y, "space": "screen"}, t, "up", 0.45)

    def image(self, src, t, label=None, source=None, region="main", w=None, h=None) -> str:
        """ảnh thật (bắt buộc ghi nguồn) hoặc ảnh minh họa có nhãn."""
        K = self.K
        x, y = K.F.center(region)
        w = w or K.F.width(region) * 0.8
        h = h or w * (0.62 if not K.V else 0.75)
        return self.add({"type": "image", "src": src, "w": w, "h": h, "r": 24, "label": label, "source": source, "x": x, "y": y - 30,
                         "space": "screen"}, t, "scale", 0.45)

    def bars(self, data, t, unit="", region="main", d=1.2) -> str:
        """biểu đồ cột: data [(nhãn, giá trị)] — chỉ số liệu có nguồn."""
        K = self.K
        x, y = K.F.center(region)
        bid = self.add({"type": "bars", "data": [{"label": l, "value": v} for l, v in data], "unit": unit, "w": K.F.width(region) * 0.8,
                        "h": K.F.height(region) * 0.5, "x": x, "y": y, "progress": 0, "space": "screen"}, t, "fade", 0.3)
        self.animate(bid, t, d, {"progress": 1}, "out")
        return bid

    def meter(self, value, t, label=None, region="main", ry=0.6, color=None) -> str:
        """thanh mức độ 0–1 (không hiện %) — mức cao/thấp, tiến độ."""
        K = self.K
        x, y = K.at_zone(region, 0.5, ry)
        pid = self.add({"type": "progress", "w": K.F.width(region) * 0.75, "h": 34, "value": value, "color": color or K.th["alt"],
                        "track": K.th["panel"], "show_value": False, "x": x, "y": y, "progress": 0, "space": "screen"}, t, "fade", 0.3)
        self.animate(pid, t, 0.9, {"progress": 1}, "out")
        if label:
            self.add({"type": "text", "text": label, "font": "bold", "size": 38, "color": K.th["text"], "space": "screen", "x": x, "y": y - 70,
                      "shadow": 0}, t, "up", 0.3)
        return pid

    def arrow(self, a, b, t, d=0.5, color=None, dash=None) -> str:
        """mũi tên nối hai đối tượng (id) hoặc hai điểm [x,y] trên màn hình."""
        o = {"type": "line", "from": a, "to": b, "width": 6, "color": color or self.K.th["muted"], "arrow": True, "progress": 0,
             "trim_start": 110 if isinstance(a, str) else 0, "trim_end": 120 if isinstance(b, str) else 0, "space": "screen", "layer": -1}
        if dash:
            o.update(dash=dash, gap=10)
        lid = self.add(o)
        self.draw(lid, t, d)
        return lid

    # ---------- ảnh (tải bằng: .venv/bin/python -m thagent.tools img <dự-án> <url> i_ten.jpg [nguồn]) ----------
    def _img_meta(self, src, label, source, real):
        """ảnh minh họa → nhãn “Hình ảnh minh họa”; ảnh đúng chủ thể (real=True) → nhãn = tên chủ thể. Nguồn lấy từ illus_sources.json."""
        import json as _j
        src = src if "/" in src else f"assets_web/{src}"
        if source is None:
            sj = self.K.pdir / "assets_web" / "illus_sources.json"
            try:
                source = _j.loads(sj.read_text(encoding="utf-8")).get(Path(src).name)
            except Exception:
                source = None
        if source and "://" in str(source):
            source = re.sub(r"^https?://(www\.)?", "", str(source)).split("/")[0]   # chỉ tên miền cho gọn
        # trên video chỉ ghi loại ảnh; nguồn KHÔNG hiện (người dùng tự ghi khi đăng bài) — vẫn lưu ở assets_web/illus_sources.json
        return src, ("Hình ảnh thực tế" if real else "Hình ảnh minh họa"), None

    def photo(self, src, t, label=None, source=None, real=False, region="main", w=None, h=None, kb=True, style="scale",
              ry=0.5, **k) -> str:
        """ảnh lớn bo góc, zoom/trượt chậm (Ken Burns) suốt lúc hiện, nhãn + nguồn dưới ảnh. style: scale | mask_left (quét mở) | up."""
        K = self.K
        src, label, source = self._img_meta(src, label, source, real)
        x, y = K.at_zone(region, 0.5, ry)
        w = w or K.F.width(region) * (0.86 if K.V else 0.84)
        h = h or w * (0.72 if K.V else 0.6)
        o = {"type": "image", "src": src, "w": w, "h": h, "r": 26, "label": label, "source": source, "x": x, "y": y - 40,
             "space": "screen", "shadow": 0.35, **k}
        if _is_video(src):            # b-roll: khung video bo góc như ảnh, không phủ kín khung
            o.update(type="video", **{"in": k.get("in", 0.0), "rate": k.get("rate", 1.0)})
            kb = False
        if kb:
            o["kb"] = kb if isinstance(kb, dict) else {"z": [1.03, 1.14], "pan": [-0.3, 0.1, 0.3, -0.1]}
        return self.add(o, t, style, 0.5 if style == "scale" else 0.7)

    def photos(self, items, region="main", real=False) -> list[str]:
        """2–3 ảnh lần lượt theo lời: items [(src, nhãn, t)] — ảnh mới trượt lên chồng, ảnh trước lùi nhẹ/nghiêng."""
        K = self.K
        x, y = K.F.center(region)
        w = K.F.width(region) * (0.8 if K.V else 0.7)
        h = w * (0.66 if K.V else 0.58)
        ids = []
        for i, (src, label, t) in enumerate(items):
            s_, lab, srcn = self._img_meta(src, label, None, real)
            rot = (-4, 3, -2)[i % 3]
            o = {"type": "image", "src": s_, "w": w, "h": h, "r": 22, "label": lab, "source": srcn, "space": "screen",
                 "x": x + (i - (len(items) - 1) / 2) * 26, "y": y - 40 + i * 14, "rot": rot, "shadow": 0.45,
                 "kb": {"z": [1.02, 1.1], "pan": [0.2 * (-1) ** i, 0, -0.2 * (-1) ** i, 0]}, "layer": i}
            if _is_video(s_):
                o.update(type="video", **{"in": 0.0, "rate": 1.0}); o.pop("kb")
            oid = self.add(o, t, "up", 0.5)
            for prev in ids:
                self.animate(prev, t, 0.45, {"scale": 0.92, "opacity": 0.55})
            ids.append(oid)
        return ids

    def before_after(self, src_a, src_b, t_a, t_b, labels=("TRƯỚC", "SAU"), region="main") -> list[str]:
        """trước / sau: ảnh sau quét mở đè lên ảnh trước đúng lúc nói; nhãn góc + dòng nguồn đổi theo ảnh đang thấy."""
        K = self.K
        x, y = K.F.center(region)
        w = K.F.width(region) * 0.86
        h = w * (0.72 if K.V else 0.6)
        ids = []
        for i, (src, t, lab, style) in enumerate(((src_a, t_a, labels[0], "scale"), (src_b, t_b, labels[1], "mask_left"))):
            s_, cap, srcn = self._img_meta(src, None, None, False)
            oid = self.add({"type": "image", "src": s_, "w": w, "h": h, "r": 26, "space": "screen", "x": x, "y": y - 30,
                            "shadow": 0.35, "kb": {"z": [1.02, 1.08]}, "layer": i}, t, style, 0.6 if style == "scale" else 0.9)
            t_lab = t + (0.0 if i == 0 else 0.85)          # nhãn ảnh sau hiện khi ảnh đã phủ kín
            tg = self.add({"type": "rect", "w": len(lab) * 26 + 60, "h": 64, "r": 32, "fill": K.th["accent"], "space": "screen",
                           "x": x - w / 2 + len(lab) * 13 + 60, "y": y - 30 - h / 2 + 52, "layer": 5 + i}, t_lab, "pop", 0.3)
            self.add({"type": "text", "text": lab, "font": "black", "size": 34, "color": K.th["ink_on_accent"], "parent": tg, "x": 0, "y": 0,
                      "shadow": 0})
            ct = self.add({"type": "text", "text": cap, "font": "semi", "size": 26,
                           "color": K.th["muted"], "space": "screen", "x": x, "y": y - 30 + h / 2 + 52, "line_h": 1.25, "shadow": 0,
                           "role": "source"}, t_lab, "fade", 0.25)
            if i == 0:
                self.hide(tg, t_b + 0.55, "fade", 0.2)
                self.hide(ct, t_b + 0.55, "fade", 0.2)
            ids.append(oid)
        self.hide(ids[0], t_b + 0.95, "fade", 0.1)     # ảnh sau đã phủ kín → bỏ ảnh trước
        return ids

    def photo_bg(self, src, t=None, dim=0.55, source=None) -> str:
        """ảnh làm nền cả khung (tối đi để chữ lớn đè lên đọc rõ) — cho câu mở đầu / câu kết / chuyển chương."""
        K = self.K
        s_, _, srcn = self._img_meta(src, None, source, False)
        oid = self.add({"type": "image", "src": s_, "w": K.W, "h": K.H, "r": 0, "space": "screen", "x": K.W / 2, "y": K.H / 2,
                        "dim": dim, "shadow": 0, "layer": -40, "role": "backdrop", "kb": {"z": [1.04, 1.16], "pan": [0, 0.2, 0, -0.2]}},
                       self.t0 if t is None else t, "fade", 0.6)
        if True:
            self.add({"type": "text", "text": "Hình ảnh minh họa", "font": "medium", "size": 22, "color": "#FFFFFF",
                      "space": "screen", "x": K.W / 2, "y": K.F.center("source")[1], "shadow": 0.6, "role": "source", "layer": 30},
                     self.t0 if t is None else t, "fade", 0.4)
        return oid

    def photo_pin(self, photo_id, rx, ry, text, t, color=None) -> str:
        """chấm chú thích một chi tiết trong ảnh (rx, ry: 0..1 theo khung ảnh) + nhãn nhỏ."""
        K = self.K
        o = next(x for x in self.objs if x["id"] == photo_id)
        px, py = (rx - 0.5) * o["w"], (ry - 0.5) * o["h"]
        col = color or K.th["accent"]
        dot = self.add({"type": "circle", "r": 14, "fill": col, "stroke": "#FFFFFF", "stroke_w": 4, "parent": photo_id, "x": px, "y": py},
                       t, "pop", 0.3)
        tag_w = len(text) * 20 + 50
        tg = self.add({"type": "rect", "w": tag_w, "h": 58, "r": 29, "fill": "#111111", "opacity": 0.85, "parent": photo_id,
                       "x": px + (tag_w / 2 + 26) * (1 if rx < 0.6 else -1), "y": py}, t + 0.15, "fade", 0.3)
        self.add({"type": "text", "text": text, "font": "bold", "size": 30, "color": "#FFFFFF", "parent": tg, "x": 0, "y": 0, "shadow": 0})
        return dot

    # ---------- khối có nhịp / đổi trạng thái ----------
    def spotlight(self, ids, times, d=0.35):
        """làm nổi mục đang nói: tới times[i] thì ids[i] to lên + rõ, các mục khác lùi lại (nhỏ, mờ)."""
        for i, (oid, t) in enumerate(zip(ids, times)):
            for j, other in enumerate(ids):
                if j == i:
                    self.animate(other, t, d, {"scale": 1.12, "opacity": 1.0}, "out")
                elif j < len(times) and times[j] <= t + 1e-3 or j < i:
                    self.animate(other, t, d, {"scale": 0.9, "opacity": 0.45}, "out")

    def keyword(self, text, t, region="main", ry=0.5, color=None, size=None) -> str:
        """từ khóa bật lên đúng lúc nói (viên lớn giữa vùng hình) — dùng khi ý chưa có icon/hình phù hợp."""
        K = self.K
        x, y = K.at_zone(region, 0.5, ry)
        sz = size or (64 if K.V else 60)
        w = len(text) * sz * 0.6 + sz * 1.6
        rid = self.add({"type": "rect", "w": w, "h": sz * 2.0, "r": sz, "fill": color or K.th["accent"], "space": "screen", "x": x, "y": y,
                        "shadow": 0.3}, t - 0.05, "pop", 0.35)
        self.add({"type": "text", "text": text, "font": "black", "size": sz, "color": K.th["ink_on_accent"], "parent": rid, "x": 0, "y": 0,
                  "shadow": 0})
        return rid

    def checklist(self, items, region="main", tick_after=0.5) -> list[str]:
        """danh sách đánh dấu: items [(chữ, t)] — dòng hiện theo lời, dấu tích bật xanh sau `tick_after` giây; dòng cũ mờ bớt."""
        K = self.K
        x0, y0, x1, y1 = K.zone(region)
        n = len(items)
        sz = 50 if K.V else 44
        gap = min((y1 - y0) * 0.86 / max(n, 1), sz * 3.0)
        w = (x1 - x0) * 0.9
        cx = (x0 + x1) / 2
        ys = [(y0 + y1) / 2 + (i - (n - 1) / 2) * gap for i in range(n)]
        ids = []
        for (text, t), y in zip(items, ys):
            rid = self.add({"type": "rect", "w": w, "h": sz * 2.2, "r": 24, "fill": K.th["panel"], "shadow": 0.22, "space": "screen",
                            "x": cx, "y": y}, t - 0.05, "left", 0.4)
            box = self.add({"type": "circle", "r": sz * 0.55, "fill": None, "stroke": K.th["muted"], "stroke_w": 4, "parent": rid,
                            "x": -w / 2 + sz * 1.1, "y": 0})
            tick = self.add({"type": "icon", "name": "check-circle", "size": sz * 1.2, "color": K.th["good"], "parent": rid,
                             "x": -w / 2 + sz * 1.1, "y": 0})
            self.reveal(tick, t + tick_after, "pop", 0.3)
            self.add({"type": "text", "text": text, "font": "bold", "size": sz, "color": K.th["text"], "parent": rid, "x": -w / 2 + sz * 2.2,
                      "y": 0, "anchor": "left", "align": "left", "max_w": w - sz * 3, "shadow": 0})
            ids.append(rid)
        for i, (_, t) in enumerate(items[1:], 1):
            self.animate(ids[i - 1], t, 0.35, {"opacity": 0.6, "scale": 0.97})
        return ids

    def steps(self, items, region="main") -> list[str]:
        """các bước nối tiếp: items [(icon, nhãn, t)] — nút số + đường nối vẽ dần tới bước kế (dọc: xếp dọc, ngang: hàng ngang)."""
        K = self.K
        x0, y0, x1, y1 = K.zone(region)
        n = len(items)
        if K.V:
            pts = [((x0 + x1) / 2, y0 + (y1 - y0) * (i + 0.5) / n) for i in range(n)]
        else:
            pts = [(x0 + (x1 - x0) * (i + 0.5) / n, (y0 + y1) / 2) for i in range(n)]
        sz = 84 if n <= 3 else 70
        ids = []
        for i, ((name, label, t), (x, y)) in enumerate(zip(items, pts)):
            oid = self.add({"type": "icon", "name": name, "size": sz, "color": K.th["accent"], "bg": K.th["panel"], "bg_r": sz * 1.15,
                            "ring": K.th["accent"], "ring_w": 5, "x": x - (sz * 2.6 if K.V else 0), "y": y - (0 if K.V else 30),
                            "space": "screen", "shadow": 0.25}, t, "pop", 0.35)
            lab = {"type": "text", "text": label, "font": "bold", "size": 42 if K.V else 36, "color": K.th["text"], "space": "screen",
                   "shadow": 0, "max_w": (x1 - x0) * (0.55 if K.V else 0.9 / n)}
            lab.update({"x": x - sz * 1.2, "y": y, "anchor": "left", "align": "left"} if K.V else {"x": x, "y": y + sz * 1.6})
            self.add(lab, t + 0.15, "up", 0.35)
            if ids:
                lid = self.add({"type": "line", "from": ids[-1], "to": oid, "width": 6, "color": K.th["muted"], "trim_start": sz * 1.3,
                                "trim_end": sz * 1.3, "space": "screen", "layer": -1, "progress": 0})
                self.draw(lid, t - 0.4, 0.4)
            ids.append(oid)
        return ids

    def street(self, home, around, t0, region="main") -> list[str]:
        """sơ đồ con phố (BĐS): con đường vẽ dần, căn nhà ở giữa, các điểm xung quanh bật lên theo lời.
        home = (icon, nhãn); around = [(icon, nhãn, t), …] (≤ 6)."""
        K = self.K
        x0, y0, x1, y1 = K.zone(region)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rw = (x1 - x0) * 0.96
        road = self.add({"type": "rect", "w": rw, "h": 70, "r": 12, "fill": K.th["muted"], "opacity": 0.35, "space": "screen",
                         "x": cx, "y": cy, "layer": -2}, t0, "left", 0.6)
        dash = self.add({"type": "line", "points": [[cx - rw / 2 + 20, cy], [cx + rw / 2 - 20, cy]], "width": 5, "color": "#FFFFFF",
                         "dash": 26, "gap": 20, "space": "screen", "layer": -1, "progress": 0})
        self.draw(dash, t0 + 0.1, 0.7)
        hid = self.add({"type": "icon", "name": home[0], "size": 110, "color": K.th["ink_on_accent"], "bg": K.th["accent"], "bg_r": 120,
                        "x": cx, "y": cy - 235, "label": home[1], "label_size": 40, "label_color": K.th["text"], "space": "screen",
                        "shadow": 0.3}, t0 + 0.3, "pop", 0.4)
        low = around[:3]                             # ≤3 điểm: hàng dưới đường; điểm 4–6: hai bên căn nhà, phía trên đường
        slots = [(cx + (k - (len(low) - 1) / 2) * rw / 3.2, cy + 215) for k in range(len(low))]
        side = [(cx - rw * 0.34, cy - 200), (cx + rw * 0.34, cy - 200), (cx - rw * 0.2, cy - 380)]
        slots += side[:max(0, len(around) - 3)]
        ids = [hid]
        for (name, label, t), (x, y) in zip(around, slots):
            ids.append(self.add({"type": "icon", "name": name, "size": 70, "color": K.th["accent"], "bg": K.th["panel"], "bg_r": 82,
                                 "ring": K.th["accent"], "ring_w": 4, "x": x, "y": y, "label": label, "label_size": 34,
                                 "label_color": K.th["text"], "space": "screen", "shadow": 0.25}, t, "pop", 0.35))
        return ids

    # ---------- bản đồ ----------
    def region(self, iso, t, color=None, opacity=0.9, d=None, dim=0.0, **k) -> str:
        """tô quốc gia (ISO3) theo ranh giới thật: viền vẽ dần → màu lan trong lãnh thổ → giữ. Mỗi nước một màu (K.color).
        Nhiều nước truyền list → mỗi nước một region riêng, màu riêng. dim=0.4: giảm nhấn mọi vùng ngoài lãnh thổ này.
        VNM tự kèm QĐ. Hoàng Sa, Trường Sa (ẩn khi thu nhỏ)."""
        isos = [iso] if isinstance(iso, str) else list(iso)
        if len(isos) > 1 and color is None:
            return [self.region(i, t + 0.25 * n, None, opacity, d, dim if n == 0 else 0, **k) for n, i in enumerate(isos)][0]
        d = d or max(0.7, min(1.3, (self.t1 - t) * 0.3))
        rid = self.add({"type": "region", "iso": isos, "fill": color or self.K.color(isos[0]), "fill_op": opacity, "layer": 1,
                        "progress": 0, "glow": 0.35, "dim": dim, **k}, t, "fade", 0.15)
        self.draw(rid, t, d)
        return rid

    def backdrop(self, t=None, opacity=0.94, d=0.4) -> str:
        """phủ nền riêng lên bản đồ → cảnh đồ họa riêng khi ý đang nói không gắn vị trí (bản đồ chỉ còn thấp thoáng)."""
        K = self.K
        return self.add({"type": "rect", "w": K.W + 40, "h": K.H + 40, "r": 0, "fill": K.th["bg"], "opacity": opacity, "space": "screen",
                         "x": K.W / 2, "y": K.H / 2, "layer": -50}, self.t0 if t is None else t, "fade", d)

    def focus(self, oid, t, dim=0.45, d=0.5):
        """dồn chú ý vào region `oid` (giảm nhấn phần còn lại) từ lúc t."""
        self.animate(oid, t, d, {"dim": dim})

    def halo(self, lonlat, t, r=70, color=None, **k) -> str:
        """vòng gợn dẫn mắt tới một điểm — chỉ là tín hiệu chú ý, KHÔNG phải ranh giới."""
        x, y = geo_xy(*lonlat)
        return self.add({"type": "halo", "x": x, "y": y, "r": r, "color": color or "#FFFFFF", "t0": t, "layer": 7, **k}, t, "fade", 0.3)

    def place(self, lonlat, text, t, size=44, color=None, inside=None, **k) -> str:
        """tên quốc gia/lãnh thổ/đảo: CHỮ TRƠN (không callout), cố định cỡ, khoá vị trí. inside={"iso":..} hoặc {"src","name"} → nằm trong lãnh thổ."""
        x, y = geo_xy(*lonlat)
        o = {"type": "text", "text": text, "font": "black", "size": size, "color": color or "#FFFFFF", "x": x, "y": y, "fixed": True,
             "shadow": 0.6, "stroke": 3, "stroke_color": "#0B0F17", "lod": [0.8, None], "layer": 8, **k}
        if inside:
            o["inside"] = inside
        return self.add(o, t, "fade", 0.4)

    def pin(self, lonlat, t, color=None, r=11, **k) -> str:
        x, y = geo_xy(*lonlat)
        return self.add({"type": "circle", "r": r, "fill": color or self.K.th["accent"], "stroke": "#FFFFFF", "stroke_w": 3, "x": x, "y": y,
                         "layer": 6, **k}, t, "pop", 0.3)

    def callout(self, lonlat, text, t, sub=None, style="tag", color=None, dirs=None, **k) -> str:
        """callout CHỈ cho vật nhỏ: đường, dự án, cây cầu, nút giao, công trình. Dấu neo + thân mảnh + nhãn ở xa, tự né tuyến."""
        x, y = geo_xy(*lonlat)
        o = {"type": "callout", "x": x, "y": y, "text": text, "style": style, "size": 30 if style == "tag" else 26,
             "color": color or self.K.th["accent"], "stem": 140 if style == "tag" else 80, "marker": "dot", "layer": 9, **k}
        if sub:
            o["sub"] = sub
        if dirs:
            o["dirs"] = dirs
        return self.add(o, t, "fade", 0.6)

    def route(self, src, feature, t, d=1.2, color=None, width=6, dash=None, head=8, **k) -> str:
        """vẽ tuyến GeoJSON (đường, sông, tuyến bay) chạy dần theo lời."""
        o = {"type": "geoline", "src": src, "feature": feature, "color": color or self.K.th["accent"], "width": width, "head": head,
             "progress": 0, "layer": 2, **k}
        if dash:
            o["dash"] = dash
        rid = self.add(o)
        self.draw(rid, t, d)
        return rid

    def route_label(self, src, feature, text, t, at=0.5, color=None, **k) -> str:
        """tên tuyến = callout neo trên chính tuyến (không trôi sang tuyến khác)."""
        return self.add({"type": "routelabel", "src": src, "feature": feature, "at": at, "text": text, "style": "tag", "size": 30,
                         "color": color or self.K.th["accent"], "stem": 150, "max_w": 360, "layer": 9, **k}, t, "fade", 0.7)

    def look(self, box, t, dur=1.0, region=None, rot=0.0, **k):
        """camera bản đồ: khung (lon0, lat0, lon1, lat1) nằm trọn trong vùng của tỷ lệ này.
        region mặc định: dọc → "map" (chừa tiêu đề trên), ngang → "map" (phải) nếu cảnh có chữ, ngược lại "full"."""
        if region is None:
            region = "map" if (self.K.V or self._has_text()) else "full"
        key = self.K.F.fit_geo(*box, region=region, t=round(t, 3), dur=dur, **k)
        key["rot"] = rot
        self.cams.append(key)

    def story(self, establish, focus, t_est, t_focus, resolve=None, t_resolve=None, region=None, est_dur=1.6):
        """camera có diễn tiến: Establish (khu vực) → Focus (chủ thể) → Explain (kit tự trôi nhẹ) → Resolve (lùi ra/sang chủ thể sau)."""
        self.look(establish, t_est, est_dur, region)
        self.look(focus, t_focus, max(1.0, min(1.6, t_focus - t_est - 0.1)), region)
        if resolve is not None:
            self.look(resolve, t_resolve or self.t1 - 0.1, 1.0, region)

    def look_at(self, lonlat, zoom, t, dur=1.0, ease="inout"):
        x, y = geo_xy(*lonlat)
        self.cams.append({"t": round(t, 3), "x": round(x, 1), "y": round(y, 1), "zoom": zoom, "dur": dur, "ease": ease})

    def _has_text(self):
        return any(o.get("space") == "screen" and o["type"] == "text" for o in self.objs)

    # ---------- xuất ----------
    def dump(self) -> dict:
        evs = list(self.evs)
        if self.exit:
            hidden = {e["object_id"] for e in evs if e["action"] == "hide"}
            parents = {o["id"] for o in self.objs if o.get("parent")}
            for o in self.objs:
                if o.get("persist") or o.get("until_s") is not None or o["id"] in hidden or o.get("parent"):
                    continue
                if self.t1 - self.t0 > 1.2:
                    evs.append({"object_id": o["id"], "action": "hide", "start_s": round(self.t1 - 0.3, 3), "end_s": round(self.t1 - 0.02, 3),
                                "style": "fade"})
        d = {"id": f"S{self.K.scenes.index(self) + 1:02d}", "start_s": round(self.t0, 3), "end_s": round(self.t1, 3),
             "voice_span": self.K.text_between(self.t0, self.t1)[:120], "purpose": self.purpose, "objects": self.objs, "events": evs,
             "camera": self.cams, "audio_events": self.sfx}
        if self.transition and self.transition.get("type"):
            d["transition_in"] = self.transition
        if self.bg:
            d["bg"] = self.bg
        return d


def build(builder_file, content, fmts=None, theme="dark", project_id=None):
    """chạy `content(K)` cho từng tỷ lệ → timeline_<fmt>.json cạnh builder. Dòng lệnh: python build_timeline.py [9x16|16x9]."""
    pdir = Path(builder_file).resolve().parent
    want = [a for a in sys.argv[1:] if a in ("9x16", "16x9")] or list(fmts or ("9x16", "16x9"))
    for f in want:
        K = Kit(pdir, f, theme, project_id)
        content(K)
        print("ok", K.save())
