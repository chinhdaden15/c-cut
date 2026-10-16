"""Bố cục theo tỷ lệ khung (skill voice-to-motion v1.2): dọc 9:16 và ngang 16:9.

Mỗi định dạng có vùng riêng — không nhân toạ độ theo một hệ số. Timeline của từng định dạng được viết từ cùng nội dung
(voice, chữ, asset, mốc nhấn) nhưng dùng Frame của định dạng đó để đặt chữ, chọn khung camera bản đồ, đặt callout.

    from thagent.v2m.layout import Frame
    F = Frame("16x9")
    F.W, F.H, F.portrait
    F.zone("title")              # (x0, y0, x1, y1) px
    F.center("main")             # tâm vùng
    F.width("text")              # bề rộng tối đa cho chữ ở vùng chữ
    F.fit_geo(lon0, lat0, lon1, lat1, region="map")   # → camera key dict để thấy trọn vùng địa lý trong vùng `region`
"""
from __future__ import annotations

import math

FORMATS = {"9x16": (1080, 1920), "16x9": (1920, 1080)}
DEFAULT_FORMAT = "9x16"

# vùng an toàn: chừa giao diện nền tảng (dọc: thanh trên/dưới & cột nút phải của video ngắn; ngang: tiêu đề/thanh điều khiển)
SAFE = {"9x16": (60, 150, 1020, 1600), "16x9": (90, 70, 1830, 1000)}

ZONES = {
    "9x16": {
        "title":   (80, 220, 1000, 560),     # câu dẫn + điểm nhấn, phía trên
        "main":    (60, 560, 1020, 1420),    # minh họa chính
        "caption": (80, 1420, 1000, 1600),   # chú thích, chú giải, nguồn
        "text":    (80, 220, 1000, 560),     # vùng chữ chính (dọc: = title)
        "map":     (40, 480, 1040, 1560),    # vùng bản đồ cần thấy rõ khi có tiêu đề phía trên
        "full":    (40, 160, 1040, 1600),    # bản đồ/hình toàn khung
        "source":  (60, 1820, 1020, 1880),
    },
    "16x9": {
        "title":   (110, 80, 1810, 250),     # dải tiêu đề phía trên (khi minh họa chiếm toàn ngang)
        "main":    (860, 80, 1830, 1000),    # minh họa bên phải
        "caption": (110, 900, 820, 1000),    # chú thích dưới cột chữ
        "text":    (110, 150, 800, 880),     # cột chữ bên trái
        "map":     (840, 70, 1840, 1010),    # bản đồ bên phải khi có cột chữ trái
        "full":    (90, 70, 1830, 1010),     # bản đồ toàn khung
        "source":  (90, 1040, 1830, 1070),
    },
}


def fmt_of(W: int, H: int) -> str:
    return "9x16" if H >= W else "16x9"


class Frame:
    def __init__(self, fmt: str = DEFAULT_FORMAT):
        if fmt not in FORMATS:
            raise ValueError(f"định dạng {fmt} chưa hỗ trợ (9x16 | 16x9)")
        self.fmt = fmt
        self.W, self.H = FORMATS[fmt]
        self.portrait = fmt == "9x16"
        self.safe = SAFE[fmt]

    def zone(self, name: str) -> tuple:
        return ZONES[self.fmt][name]

    def center(self, name: str) -> tuple[float, float]:
        x0, y0, x1, y1 = self.zone(name)
        return (x0 + x1) / 2, (y0 + y1) / 2

    def width(self, name: str) -> float:
        x0, _, x1, _ = self.zone(name)
        return x1 - x0

    def height(self, name: str) -> float:
        _, y0, _, y1 = self.zone(name)
        return y1 - y0

    def canvas(self, fps: int = 30) -> dict:
        return {"width": self.W, "height": self.H, "fps": fps, "format": self.fmt}

    def fit_geo(self, lon0, lat0, lon1, lat1, region: str = "map", pad: float = 0.1, t=None, dur=0.8, ease="inout",
                zmax: float | None = None) -> dict:
        """camera để vùng địa lý [lon0..lon1]×[lat0..lat1] nằm trọn trong `region` (px), chừa `pad`. Toạ độ địa lý giữ nguyên."""
        from .render import geo_xy
        x0, y0 = geo_xy(lon0, lat1)
        x1, y1 = geo_xy(lon1, lat0)
        bw, bh = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
        rx0, ry0, rx1, ry1 = self.zone(region) if isinstance(region, str) else region
        rw, rh = (rx1 - rx0) * (1 - pad), (ry1 - ry0) * (1 - pad)
        z = min(rw / bw, rh / bh)
        if zmax:
            z = min(z, zmax)
        from .render import MAP_W
        z = max(z, self.W / MAP_W * 1.12)   # không lùi xa hơn một vòng thế giới phủ kín bề ngang khung (không lặp quốc gia)
        # tâm vùng địa lý phải rơi vào tâm region (không phải tâm khung)
        rcx, rcy = (rx0 + rx1) / 2, (ry0 + ry1) / 2
        cx = (x0 + x1) / 2 - (rcx - self.W / 2) / z
        cy = (y0 + y1) / 2 - (rcy - self.H / 2) / z
        k = {"x": round(cx, 4), "y": round(cy, 4), "zoom": round(z, 4), "dur": dur, "ease": ease}
        if t is not None:
            k["t"] = round(t, 3)
        return k
