"""Phụ đề TOÀN BỘ lời nói cho Talking Head — kiểu TỪNG TỪ (theo mẫu người dùng duyệt), app tự thêm.

- Mỗi lần hiện 1 từ / 1 cụm ngắn đúng lúc nói (tiếng Việt ghép từ 2–3 âm tiết liền nhau: "đơn điệu", "chuyên nghiệp",
  "hiệu ứng động"); không hiện cả câu.
- Vị trí: ngay DƯỚI CẰM, giữa khung (dải cổ) — gần mặt, dễ xem. Trong các đoạn MG: KHÔNG phụ đề.
- Cụm 2–4 từ MỘT dòng (tiếng Việt tách từ ghép đúng), ngắt ở dấu câu / chỗ ngừng; trong cụm chữ hiện dồn theo lời. Chữ nhấn hiện → phụ đề nằm ngay TRÊN làm dòng dẫn
  (bỏ từ trùng chữ nhấn); callout đang hiện → tạm ẩn; cảnh MG → chạy ở dải dưới khung.
- Chữ TRẮNG ĐẬM + quầng sáng trắng mờ; tối đa 2 dòng.
- Tắt: plan.captions = False.
"""
from __future__ import annotations

import re
from functools import lru_cache

import cv2
import numpy as np

SIZE = {"v": 74, "h": 60}          # theo mẫu: chữ ~4% chiều cao khung dọc
def _seg_counts(sylls: list[str]) -> list[int] | None:
    """tách từ tiếng Việt (pyvi, MIT): số âm tiết của từng từ — None nếu không có thư viện."""
    try:
        from pyvi import ViTokenizer
    except Exception:
        return None
    clean = [re.sub(r"[^\w%$€£₫]", "", s, flags=re.UNICODE) or "x" for s in sylls]
    toks = ViTokenizer.tokenize(" ".join(clean)).split()
    counts = [t.count("_") + 1 for t in toks]
    return counts if sum(counts) == len(sylls) else None


GHEP = {"khách thuê", "cho thuê", "phân khu", "chủ nhà", "căn nhà", "ngôi nhà", "thị trường", "quan trọng", "hoàn thiện",
        "doanh nghiệp", "văn phòng", "cửa hàng", "kinh doanh", "thương hiệu", "thương mại", "đầu tư", "hợp đồng", "khách hàng",
        "cà phê", "công ty", "đào tạo", "trung tâm", "không gian", "nhu cầu", "lợi thế", "tương lai", "dòng người", "mua bán",
        "trục đường", "nhận diện", "showroom", "bất động sản", "căn hộ", "nhà phố", "dự án", "giá trị", "lợi nhuận",
        "chưa chắc", "khác nhau", "cũng như", "thực tế", "phù hợp", "hình dung", "đa phần"}


def _join_common(groups: list[list]) -> list[list]:
    """pyvi bỏ sót từ ghép hay gặp ("khách thuê", "phân khu") → ghép lại, phụ đề không cắt đôi."""
    k = lambda g: " ".join(re.sub(r"[^\w]", "", x[2].lower()) for x in g)
    out = []
    for g in groups:
        if out and out[-1][-1][2][-1:] not in ".,!?;:…" and f"{k(out[-1][-1:])} {k(g[:1])}" in GHEP:
            out[-1] = out[-1] + g
        else:
            out.append(g)
    return out


def _group_vi(tl, fps) -> list[list]:
    return _join_common(_group_vi0(tl, fps))


def _group_vi0(tl, fps) -> list[list]:
    counts = _seg_counts([t for _, _, t in tl])
    groups, i = [], 0
    if counts is None:                                 # không tách được → từng âm tiết
        return [[x] for x in tl]
    for n in counts:
        g = tl[i:i + n]
        i += n
        cur = [g[0]]                                   # trong một từ mà ngừng lâu / có dấu câu → tách
        for x in g[1:]:
            if x[0] - cur[-1][1] > fps * 0.25 or cur[-1][2][-1:] in ".,!?;:…":
                groups.append(cur); cur = []
            cur.append(x)
        groups.append(cur)
    return groups


CH_MAX = {"v": 16, "h": 24}       # cụm phụ đề: 2–4 từ, MỘT dòng (chuẩn short-form / Hormozi: 2–4 từ một lần)
CH_WORDS = 4
HOLD = 0.4                          # nói xong cụm giữ thêm tối đa 0.4s (không trễ hơn lời)
MIN_S = 0.6                         # cụm hiện ít nhất 0.6s nếu phía sau còn trống


def _clean(t: str) -> str:
    t = re.sub(r"(\d) ([.,]?\d)", r"\1\2", t)                    # "5 ,500" → "5,500"
    t = re.sub(r"(\d) ([.,\-–]\d)", r"\1\2", t)
    t = re.sub(r" -(\w)", r"-\1", t)                                # "hard -working" → "hard-working"
    return re.sub(r"[.,;:!?…]+$", "", t)


def _pack(words, fps, mx) -> list[list]:
    """gom TỪ (tiếng Việt: từ ghép đã tách bằng pyvi, không cắt đôi “hoàn thiện”) thành cụm 2–4 từ một dòng;
    ngắt ở dấu câu / chỗ ngừng — ranh giới cụm ý, không cắt giữa từ."""
    txt = lambda c: " ".join(x[2] for w in c for x in w)
    out, cur = [], []
    for w in words:
        if cur:
            prev = cur[-1][-1]
            brk = prev[2][-1:] in ".,!?;:…" or w[0][0] - prev[1] > fps * 0.35
            name = prev[2][:1].isupper() and w[0][2][:1].isupper()   # tên riêng (chữ hoa liền nhau) không tách
            if not name and w[0][2][:1].isupper() and cur and len(txt(cur + [w])) > mx - 6:
                brk = True                                  # sắp vào tên riêng mà dòng đã dài → tên sang cụm mới
            if brk or (not name and (len(cur) >= CH_WORDS or len(txt(cur + [w])) > mx)):
                out.append(cur); cur = []
        cur.append(w)
    if cur:
        out.append(cur)
    for k in range(len(out) - 1, 0, -1):            # cụm 1 từ ngắn lẻ loi → ghép vào cụm trước nếu vừa dòng
        if len(out[k]) == 1 and len(txt(out[k])) <= 5 and len(txt(out[k - 1] + out[k])) <= mx + 4 \
                and out[k][0][0][0] - out[k - 1][-1][-1][1] <= fps * 0.35:
            out[k - 1] += out[k]
            del out[k]
    return out


WHOLE = False        # True: mỗi cụm hiện nguyên một lượt (không dồn từng từ)
NOI = {"và", "nhưng", "thì", "mà", "vì", "nên", "để", "hay", "hoặc", "khi", "nếu", "cũng"}           # từ nối mở đầu ý mới
TREO = {"cho", "cái", "của", "là", "những", "các", "với", "và", "có", "được", "ở", "rất", "thì", "mà", "đã", "sẽ",
        "một", "từ", "đến", "tới", "khá", "nhiều", "để", "như", "này", "nè", "thật", "hơn"} - {"này", "nè", "hơn"}   # không để cụm kết bằng từ treo


def _pack_y(words, fps, mx) -> list[list]:
    """gom theo Ý (như “xin chào các bạn” / “mình tự giới thiệu” / “mình tên là…”): cụm ≤ 5 từ, ngắt ở dấu câu, chỗ ngừng,
    trước từ nối / chữ hoa đầu câu; cụm không kết bằng từ treo (cho, cái, của, là…) — đẩy từ treo sang cụm sau."""
    low = lambda w: re.sub(r"[^\w]", "", w[0][2].lower())
    txt = lambda c: " ".join(x[2] for w in c for x in w)
    out, cur = [], []
    for w in words:
        if cur:
            prev = cur[-1][-1]
            name = prev[2][:1].isupper() and w[0][2][:1].isupper() and low(cur[-1]) not in NOI
            brk = prev[2][-1:] in ".,!?;:…" or w[0][0] - prev[1] > fps * 0.35
            brk = brk or (not name and ((len(cur) >= 2 and low(w) in NOI) or w[0][2][:1].isupper()))
            full = not name and (len(cur) >= 3 or len(txt(cur + [w])) > mx + 2)
            if brk or full:
                k = len(cur)
                while full and not brk and k > 1 and low(cur[k - 1]) in TREO:
                    k -= 1                                    # cụm đầy mà kết bằng từ treo → từ treo sang cụm sau
                out.append(cur[:k]); cur = cur[k:]
        cur.append(w)
    if cur:
        out.append(cur)
    for k in range(len(out) - 1, 0, -1):            # cụm vụn (1 từ / mở đầu bằng từ treo “là, được…”) → ghép vào cụm trước nếu vừa
        lone = len(out[k]) == 1 or low(out[k][0]) in {"là", "được", "của", "cho", "khá", "mới"}
        if lone and len(out[k - 1]) + len(out[k]) <= 4 and len(txt(out[k - 1] + out[k])) <= mx + 4 \
                and out[k][0][0][0] - out[k - 1][-1][-1][1] <= fps * 0.6 and not out[k][0][0][2][:1].isupper():
            out[k - 1] += out[k]
            del out[k]
    return out


def load_phrases(pdir) -> list[str] | None:
    """{pdir}/phude.json = Claude chia cụm theo Ý (mỗi cụm đủ nghĩa, 2–4 từ, đúng chữ + thứ tự transcript) → dùng thay chia tự động."""
    import json
    from pathlib import Path
    f = Path(pdir) / "phude.json"
    try:
        v = json.loads(f.read_text())
        return [str(x) for x in v] if isinstance(v, list) and v else None
    except (OSError, ValueError):
        return None


def _by_phrases(tl, phrases) -> list[list] | None:
    """khớp cụm Claude viết vào từ có mốc thời gian (theo số tiếng, bỏ dấu câu); lệch → None (dùng chia tự động)."""
    k = lambda t: re.sub(r"[^\w]", "", t.lower())
    toks = [x for x in tl if k(x[2])]
    out, i = [], 0
    for ph in phrases:
        n = len([w for w in ph.split() if k(w)])
        seg = toks[i:i + n]
        if len(seg) < n or [k(x[2]) for x in seg] != [k(w) for w in ph.split() if k(w)]:
            return None
        out.append([[x] for x in seg]); i += n
    return out if i == len(toks) else None


def chunks(plan, words, phrases: list[str] | None = None) -> list[tuple[int, int, str]]:
    """[(frame vào, frame ra, chữ)] — cụm 2–4 từ MỘT dòng; trong cụm chữ hiện dồn theo lời (như mẫu Joseph), hết cụm thay cụm mới."""
    from . import timeline as T, fonts as FT
    T.build_mapping(plan)
    tl = []
    for w in words or []:
        a = T.src_to_tl(plan, w.source_start)
        if a is None:
            continue
        b = T.src_to_tl(plan, w.source_end)
        tl.append((a, b if b is not None else a + 8, w.text.strip()))
    tl.sort()
    fps = plan.fps
    ws = _group_vi(tl, fps) if FT.current() == "vi" else [[x] for x in tl]
    cks = _by_phrases(tl, phrases) if phrases else None
    whole = WHOLE or cks is not None                # cụm do Claude chia theo ý → hiện nguyên cụm một lượt
    if cks is None:
        cks = (_pack_y if WHOLE else _pack)(ws, fps, CH_MAX["v" if plan.height > plan.width else "h"])
    out = []
    for i, c in enumerate(cks):
        sy = [x for w in c for x in w]
        nxt = cks[i + 1][0][0][0] if i + 1 < len(cks) else plan.duration_frames
        end = min(nxt, max(sy[-1][1] + int(fps * HOLD), sy[0][0] + int(fps * MIN_S)))
        if whole:                                    # cả cụm hiện một lượt
            out.append((sy[0][0], max(end, sy[0][0] + 1), _clean(" ".join(y[2] for y in sy))))
            continue
        for j, x in enumerate(sy):
            b = sy[j + 1][0] if j + 1 < len(sy) else end
            out.append((x[0], max(b, x[0] + 1), _clean(" ".join(y[2] for y in sy[:j + 1]))))
    return out


def _wrap(text: str, mx: int) -> list[str]:
    if len(text) <= mx:
        return [text]
    ws = text.split()
    best = min(range(1, len(ws)), key=lambda k: abs(len(" ".join(ws[:k])) - len(" ".join(ws[k:]))), default=1)
    return [" ".join(ws[:best]), " ".join(ws[best:])]


@lru_cache(maxsize=512)
def sprite(text: str, V: bool) -> np.ndarray:
    """chữ TRẮNG ĐẬM + viền tối mảnh + bóng đổ (người dùng chốt 2026-10-28: shadow, không glow — glow dễ chìm)."""
    from . import neon as N, fonts as FT
    size = SIZE["v" if V else "h"]
    ms = [N._mask(FT.shape_line(t), "display_bold", size) for t in _wrap(text, CH_MAX["v" if V else "h"] + 8)]
    def _trim(x):                                                         # bỏ lề trên/dưới để 2 dòng sát nhau
        r = np.where(x.max(1) > 0.02)[0]
        return x[r[0]:r[-1] + 1] if len(r) else x
    if len(ms) > 1:
        g = np.zeros((int(size * 0.08), 1), np.float32)
        ms = [_trim(ms[0]), g, _trim(ms[1])]
        ms[1] = np.zeros((g.shape[0], max(ms[0].shape[1], ms[2].shape[1])), np.float32)
    w = max(x.shape[1] for x in ms)
    m = np.concatenate([np.pad(x, ((0, 0), ((w - x.shape[1]) // 2, w - x.shape[1] - (w - x.shape[1]) // 2))) for x in ms], 0)
    pad = 34
    a = np.pad(np.clip(m, 0, 1), pad)
    edge = cv2.dilate(a, np.ones((3, 3), np.uint8)) * 0.85                 # viền tối mảnh
    sh = np.roll(np.roll(cv2.GaussianBlur(a, (0, 0), 5), 5, 0), 2, 1) * 0.85   # bóng đổ tối (không glow → không chìm trên nền sáng)
    out = np.zeros(a.shape + (4,), np.float32)
    out[..., 3] = np.clip(np.maximum.reduce([a, edge, sh]), 0, 1)
    out[..., :3] = a[..., None]                                            # trắng (premultiplied); viền + bóng = đen
    return out


def neck_y(anchors_tl, a: int, b: int, H: int) -> float:
    fr = [x for x in anchors_tl[max(a, 0):min(b, len(anchors_tl))] if x.get("face_bottom")] or \
         [x for x in anchors_tl if x.get("face_bottom")][::30]
    if not fr:
        return H * 0.55
    fb = float(np.median([x["face_bottom"] for x in fr])) * H
    fh = float(np.median([x["face_h"] for x in fr])) * H
    return fb + max(14.0, fh * 0.06)                # sát cằm như mẫu (cằm ~0.49H → chữ ~0.51H)


def chest_y(anchors_tl, a: int, b: int, H: int, zm=(1.0, 0.5, 0.4)) -> float:
    """ngực trên (vùng chữ nhấn) — dưới cằm ~0.3 mặt, theo khung đang zoom."""
    fr = [x for x in anchors_tl[max(a, 0):min(b, len(anchors_tl))] if x.get("face_bottom")] or \
         [x for x in anchors_tl if x.get("face_bottom")][::30]
    if not fr:
        return H * 0.6
    fb = float(np.median([x["face_bottom"] for x in fr])) * H
    fh = float(np.median([x["face_h"] for x in fr])) * H
    z, _, zcy = zm
    return z * (fb + fh * 0.3) + (1 - z) * zcy * H


_SHOTS = {}


def shot(anchors_tl, f: int) -> tuple[int, int]:
    """[a, b) góc máy chứa frame f — clip nhiều góc (cận / rộng): mặt nhảy vị trí đột ngột → góc mới.
    Phụ đề + chữ nhấn neo cố định TRONG một góc, sang góc khác thì neo theo người ở góc đó."""
    n = len(anchors_tl or [])
    if not n:
        return 0, 0
    key = (id(anchors_tl), n)
    if key not in _SHOTS:
        fb = np.array([x.get("face_bottom") if x.get("face_bottom") is not None else np.nan for x in anchors_tl], float)
        ok = ~np.isnan(fb)
        if ok.any():
            fb = np.interp(np.arange(n), np.arange(n)[ok], fb[ok])
        cuts, i = [0], 6
        while i < n - 6:
            if abs(fb[i + 6] - fb[i - 6]) > 0.07 and i - cuts[-1] > 20:
                cuts.append(i); i += 20
            else:
                i += 1
        _SHOTS.clear(); _SHOTS[key] = cuts + [n]
    cs = _SHOTS[key]
    for a, b in zip(cs, cs[1:]):
        if a <= f < b:
            return a, b
    return cs[-2], cs[-1]


def current(caps, f: int, anchors_tl, H: int, W: int, zm=(1.0, 0.5, 0.4), skip: set | None = None):
    """(sprite, x, y) cụm đang nói ở giữa ngực, hoặc None. skip = từ của chữ nhấn đang hiện (không lặp lại ở phụ đề)."""
    for a, b, t in caps or []:
        if a <= f < b:
            if skip:
                ws = [w for w in t.split() if re.sub(r"[^\w]", "", w.lower()) not in skip]
                if len(ws) < len(t.split()) and len(ws) <= 1:   # cụm gần hết là chữ nhấn → còn 1 từ lẻ thì khỏi hiện
                    return None
                t = " ".join(ws)
            spr = sprite(t, H > W)
            return spr, (W - spr.shape[1]) // 2, int(chest_y(anchors_tl or [], *shot(anchors_tl, f), H, zm) - 34)   # neo MỘT vị trí trong mỗi góc máy (không nhảy theo cụm)
    return None


def started_in(caps, f: int, spans) -> bool:
    """cụm đang nói đã bắt đầu trong cảnh MG (hiện ở dải dưới) → hết MG thì TẮT luôn, không nhảy lên ngực (người dùng chốt 2026-10-29)."""
    for a, b, _ in caps or []:
        if a <= f < b:
            return any(x <= a < y <= f for x, y in spans)
    return False


def draw_at(buf: np.ndarray, cur, low: bool = False) -> None:
    """vẽ cụm: giữa ngực; cảnh MG che kín → dải dưới khung an toàn."""
    if not cur:
        return
    from .callouts import over, SAFE_V, SAFE_H
    spr, x, y = cur
    H, W = buf.shape[:2]
    if low:
        y = int(H - (SAFE_V if H > W else SAFE_H)["bottom"] * 0.6 - spr.shape[0] + 34)  # dưới thẻ MG, vẫn trên thanh UI
    over(buf, spr, x, y)


def draw(buf: np.ndarray, caps, f: int, anchors_tl=None, busy: bool = False, low: bool = False,
         above: float | None = None, skip: set | None = None):
    """vẽ câu đang nói (dồn từng từ) ngay dưới cằm. busy = callout đang hiện → không vẽ;
    low = cảnh MG đang chạy → chạy ở dải dưới khung an toàn;
    above = mép trên chữ nhấn đang hiện → phụ đề nằm NGAY TRÊN làm dòng dẫn (như mẫu), bỏ các từ chữ nhấn đã hiện (skip)."""
    if not caps or busy or above == -1:
        return
    from .callouts import over
    H, W = buf.shape[:2]
    for a, b, t in caps:
        if a <= f < b:
            if skip:
                ws = [w for w in t.split() if re.sub(r"[^\w]", "", w.lower()) not in skip]
                t = " ".join(ws)
                if not t:
                    return
            spr = sprite(t, H > W)
            if low:
                from .callouts import SAFE_V, SAFE_H
                y = H - (SAFE_V if H > W else SAFE_H)["bottom"] - spr.shape[0] + 24
            elif above is not None:
                y = above - spr.shape[0] + 34 + 24 + 4               # sát mép trên chữ nhấn thành một khối
            else:
                y = neck_y(anchors_tl or [], a, b, H)
            over(buf, spr, (W - spr.shape[1]) // 2, int(y - 24))
            return
