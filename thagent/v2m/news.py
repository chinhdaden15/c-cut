"""KHUÔN VIDEO TIN TỨC (Text to Video / Voice to Motion dựng từ bài báo — article.json do `python -m thagent.article prepare` tạo).

    def content(K):
        A = K.news()                                   # đọc article.json, bật khuôn tin tức (chuyển cảnh nhẹ)
        s = K.scene(0, t_hook, "thumbnail")
        s.news_open()                                  # ảnh chính + tiêu đề lớn + ngày đăng
        K.news_bar()                                   # dòng nhỏ “Nguồn: <báo>” góc trên trái, suốt video
        s = K.scene(...); s.news_page(3, t)            # ảnh chụp trang báo thật, phóng vào ĐOẠN 3 (đang nói), đoạn tô dạ quang
        ...                                            # thân bài: ảnh/video thật đúng chủ thể, stat, street_map khi có địa điểm
        s = K.scene(t_end, K.T, "nguồn"); s.news_end(t_end)   # câu tóm + “Nguồn: …” + ngày + tiêu đề bài

Không tự viết thêm thông tin ngoài bài; số liệu / tên riêng / mốc thời gian lấy đúng article.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def _art(K) -> dict:
    if getattr(K, "art", None) is None:
        f = K.pdir / "article.json"
        if not f.exists():
            raise SystemExit("chưa có article.json — chạy: python -m thagent.article prepare <dự-án> <link>")
        K.art = json.loads(f.read_text(encoding="utf-8"))
    return K.art


def _brand_color(K) -> str:
    """màu chủ đạo của logo báo (pixel bão hoà) → màu nhãn tên báo; không có → màu nhấn của theme."""
    a = _art(K)
    if a.get("color"):
        return a["color"]
    lg = a.get("logo")
    try:
        im = cv2.imread(str(K.pdir / lg), cv2.IMREAD_UNCHANGED) if lg else None
        if im is not None:
            rgb = im[..., :3].reshape(-1, 3).astype(np.float32)
            al = im[..., 3].reshape(-1) if im.shape[2] == 4 else np.full(len(rgb), 255)
            hsv = cv2.cvtColor(im[..., :3], cv2.COLOR_BGR2HSV).reshape(-1, 3)
            m = (al > 200) & (hsv[:, 1] > 90) & (hsv[:, 2] > 60)
            if m.sum() > 30:
                b, g, r = np.median(rgb[m], axis=0)
                return "#%02X%02X%02X" % (int(r), int(g), int(b))
    except Exception:
        pass
    return K.th["alt"]


def _fit_line(text: str, role: str, size: int, max_w: float) -> str:
    """cắt một dòng cho vừa bề rộng (đo font thật), thêm “…”."""
    from . import draw as D
    f = D.font(role, int(size))
    if f.getlength(text) <= max_w:
        return text
    ws = text.split()
    while ws and f.getlength(" ".join(ws) + "…") > max_w:
        ws.pop()
    return " ".join(ws).rstrip(",;:–-") + "…"


def _wrap(text: str, role: str, size: int, max_w: float, max_lines: int) -> tuple[str, int]:
    """ngắt dòng theo bề rộng thật, thu cỡ chữ tới khi ≤ max_lines dòng."""
    from . import draw as D
    s = size
    while s > size * 0.55:
        f = D.font(role, int(s))
        lines, cur = [], ""
        for w in text.split():
            nxt = (cur + " " + w).strip()
            if f.getlength(nxt) <= max_w or not cur:
                cur = nxt
            else:
                lines.append(cur); cur = w
        lines.append(cur)
        if len(lines) <= max_lines:
            return "\n".join(lines), int(s)
        s -= 2
    return "\n".join(lines[:max_lines - 1] + [_fit_line(" ".join(lines[max_lines - 1:]), role, int(s), max_w)]), int(s)


def _likes(a: dict) -> str:
    it = a.get("interaction") or {}
    def k(n):
        return f"{n / 1000:.1f}K".replace(".0K", "K").replace(".", ",") if n >= 1000 else str(n)
    parts = []
    if it.get("likes"):
        parts.append(f"♥ {k(it['likes'])}")
    if it.get("comments"):
        parts.append(f"💬 {k(it['comments'])}")
    if not parts and it.get("tuong_tac"):
        parts.append(f"♥ {k(it['tuong_tac'])}")
    return "  ".join(parts)


# ---------------- Kit ----------------
def news(K) -> dict:
    """bật khuôn tin tức: đọc article.json; chuyển cảnh mặc định nhẹ (fade) để dòng nguồn góc trên đứng yên qua các cảnh."""
    a = _art(K)
    K.th["transition"] = "fade"
    K.news_mode = True
    return a


def news_bar(K, t_from: float = 0.0):
    """dòng nguồn nhỏ ở góc trên trái giữ suốt video từ t_from: “Nguồn: <báo>” — không khung, không nhãn màu báo
    (người dùng duyệt 12/11/2026: chỉ cần 1 dòng nhỏ). Dọc: dưới thanh giao diện nền tảng; ngang: góc trên trái."""
    a = _art(K)
    src = a.get("source") or ""
    if not src:
        return
    V = K.V
    o = {"type": "text", "text": f"Nguồn: {src}", "font": "semi", "size": 28 if V else 26, "color": "#FFFFFF", "opacity": 0.85,
         "space": "screen", "x": 64 if V else 92, "y": 178 if V else 52, "align": "left", "anchor": "left", "shadow": 0.6,
         "layer": 42, "id": K.uid("nb"), "persist": True, "role": "news_source"}
    K.base.append(o)
    K.base_evs = getattr(K, "base_evs", []) + [{"object_id": o["id"], "action": "reveal", "start_s": round(t_from, 3),
                                                "end_s": round(t_from + 0.3, 3), "style": "fade"}]
    K.news_bar_from = t_from


news_source = news_bar


# ---------------- Scene ----------------
def news_open(s, t: float | None = None, until: float | None = None, img: str | None = None, real: bool = False) -> list[str]:
    """THUMBNAIL TIN mở video: nền ảnh chính mờ tối, ảnh chính bo góc, TIÊU ĐỀ LỚN, ngày đăng (tên báo: dòng nguồn góc trên).
    img: ảnh khác ảnh chính của bài (vd ảnh thật nhân vật được nhắc trong câu hook) — real=True khi đúng chủ thể."""
    K = s.K
    a = _art(K)
    t = s.t0 if t is None else t
    img = img or a.get("thumb_file") or a.get("image_file") or next((im["file"] for im in a.get("images", []) if im.get("file")), None)
    ids = []
    if img:
        s.photo_bg(img, t, dim=0.72, real=real)
    from . import draw as D
    V = K.V
    if V:
        cw, chh, cx, cy = 960, 560, 540, 560
        tx, ty, tw, talign, tanchor = 540, 1140, 940, "center", "center"
        by, dy = 905, 1390
    else:
        cw, chh, cx, cy = 900, 520, 1350, 470
        tx, ty, tw, talign, tanchor = 110, 520, 700, "left", "left"
        by, dy = 250, 790
    if img:
        from .. import fonts as FT
        ids.append(s.add({"type": "image", "src": img, "w": cw, "h": chh, "r": 26, "space": "screen", "x": cx, "y": cy, "shadow": 0.45,
                          "kb": {"z": [1.02, 1.12], "pan": [0, 0, 0.1, -0.1]}, "layer": 2,
                          **({"label": FT.label(True)} if real else {})}, t + 0.05, "scale", 0.5))
    title, sz = _wrap(a.get("title", ""), "black", 84 if V else 66, tw, 4 if V else 5)
    ids.append(s.add({"type": "text", "text": title, "font": "black", "size": sz, "color": "#FFFFFF", "space": "screen", "x": tx,
                      "y": ty if V else (by + 60 + (dy - by - 120) / 2), "max_w": tw + 40, "align": talign, "anchor": tanchor,
                      "line_h": 1.08, "shadow": 0.5, "layer": 3}, t + 0.45, "up", 0.45))
    if a.get("date"):
        ids.append(s.add({"type": "text", "text": f"Đăng ngày {a['date']}", "font": "semi", "size": 34 if V else 30,
                          "color": "#C9D2E0", "space": "screen", "x": tx if not V else 540, "y": dy, "align": talign,
                          "anchor": tanchor, "shadow": 0.4, "layer": 3}, t + 0.75, "fade", 0.3))
    s.sound(t + 0.3, "impact")
    end = until if until is not None else s.t1
    k = t + 2.4
    while k < end - 0.8:                                      # thumbnail dài: nhịp nhấn tiêu đề / nhãn báo (không đứng im)
        s.pulse(ids[-2] if a.get("date") and len(ids) > 1 else ids[-1], k)
        k += 2.4
    if until is not None:
        for i in ids:
            s.hide(i, until, "fade", 0.3)
    return ids


def news_page(s, i: int, t: float, until: float | None = None, region="main", zoom: float = 1.22) -> str:
    """ẢNH CHỤP TRANG BÁO THẬT quanh đoạn i (1 = đoạn đầu thân bài, theo article.json "paragraphs"), đoạn đó tô dạ quang;
    camera phóng chậm vào đúng đoạn suốt lúc hiện. i = 0 → đầu trang (tiêu đề + sapo + ảnh chính)."""
    K = s.K
    a = _art(K)
    pg = a.get("page") or {}
    if i == 0:
        f, focus = pg.get("head"), [0.5, 0.35]
    else:
        ps = pg.get("paras") or []
        p = ps[i - 1] if 0 < i <= len(ps) else None
        if not p:
            raise SystemExit(f"news_page: không có ảnh chụp đoạn {i} (xem article.json → page.paras)")
        f, focus = p["file"], p["focus"]
    if not f:
        raise SystemExit("news_page: chưa có ảnh chụp trang (article.json → page)")
    k = 1 - 1 / zoom
    kx = max(-1.0, min(1.0, (focus[0] - 0.5) * 2 / k))
    ky = max(-1.0, min(1.0, (focus[1] - 0.5) * 2 / k))
    x, y = K.at_zone(region, 0.5, 0.5)
    w = K.F.width(region) * (0.9 if K.V else 0.86)
    h = w * 0.72 if K.V else w * 0.62
    oid = s.add({"type": "image", "src": f, "w": w, "h": h, "r": 20, "space": "screen", "x": x, "y": y - 20, "shadow": 0.45,
                 "kb": {"z": [1.0, zoom], "pan": [0, 0, kx, ky]}, "layer": 4, "news_page": True}, t, "up", 0.5)
    if until is not None:
        s.hide(oid, until, "fade", 0.3)
    return oid


def news_end(s, t: float, summary: str | None = None) -> list[str]:
    """KẾT: câu tóm (chữ lớn) + “Nguồn: <báo> · <ngày>” + tiêu đề bài (mờ). Không logo / khung của báo."""
    K = s.K
    a = _art(K)
    ids = []
    V = K.V
    if V:
        y_sum, y0, sum_w = 820, 1080, K.F.width("text") * 0.95
    else:
        y_sum, y0, sum_w = 400, 650, 1500
    if summary:
        txt, sz = _wrap(summary, "black", 72 if V else 64, sum_w, 4 if V else 2)
        ids.append(s.add({"type": "text", "text": txt, "font": "black", "size": sz, "color": "#FFFFFF", "space": "screen",
                          "x": K.W / 2, "y": y_sum, "align": "center", "anchor": "center",
                          "line_h": 1.08, "shadow": 0.5, "layer": 15}, t, "up", 0.35))
    src = "Nguồn: " + (a.get("source") or "") + (f" · {a['date']}" if a.get("date") else "")
    ids.append(s.add({"type": "text", "text": src, "font": "bold", "size": 44 if V else 40, "color": "#FFFFFF", "space": "screen",
                      "x": K.W / 2, "y": y0, "align": "center", "anchor": "center", "shadow": 0.5, "layer": 15}, t + 0.2, "up", 0.3))
    ttl, sz = _wrap("“" + a.get("title", "") + "”", "semi", 34 if V else 30, K.F.width("main") * 0.86, 3)
    ids.append(s.add({"type": "text", "text": ttl, "font": "semi", "size": sz, "color": "#C9D2E0", "space": "screen",
                      "x": K.W / 2, "y": y0 + (95 if V else 75), "align": "center", "anchor": "center", "line_h": 1.15, "shadow": 0.4,
                      "layer": 15}, t + 0.35, "fade", 0.3))
    return ids
