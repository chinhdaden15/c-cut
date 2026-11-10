"""Tự nhận diện NHÓM NỘI DUNG của video và chọn phong cách dựng (bảng `.claude/shared/editatlas/chon-phong-cach-theo-noi-dung.md`).

Người dùng không phải chọn: Claude chạy `python -m thagent.tools style <dự-án>` ngay sau khi có lời (transcript / kịch bản):
  - app chấm điểm theo từ khoá → đề xuất nhóm + phong cách chủ đạo + điểm nhấn + giọng điệu, ghi `<dự-án>/content_style.json`
  - Claude đọc lời thật, nếu đề xuất sai thì chốt lại: `tools style <dự-án> <nhóm> [lý do]` (source "claude")
  - người dùng đã nói rõ phong cách → `source: "user"`, app / Claude không đổi
Kiểm tra trước khi dựng (preflight TH, validate V2M / T2V / Review) cảnh báo khi chưa có content_style.json.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

FILE = "content_style.json"

# id: (tên, chủ đạo, điểm nhấn, từ khoá (không dấu, chữ thường))
GROUPS: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    "kienthuc": ("Kiến thức / lời khuyên / tâm lý", "Clean OS (thẻ chữ 1–3 từ hiện từ mờ, cảnh iOS đúng vật) hoặc Whiteboard (split: bảng trên, mặt dưới)",
                 "marker-doodles, loop-arrows, venn-overlap, puzzle-fit, stage-spotlight, monument-word",
                 ("tam ly", "thoi quen", "bai hoc", "loi khuyen", "suy nghi", "nao bo", "cam xuc", "ban than", "cuoc song", "tu duy",
                  "nguyen nhan", "vi sao", "tai sao", "hieu", "ky nang", "giao tiep", "moi quan he", "phat trien")),
    "meo": ("Danh sách mẹo / các bước", "Step Deck (số nghiêng lớn mở mỗi bước rồi thu vào góc) hoặc Swiss Grid",
            "checklist-ticks, orbit-cards, receipt-print, numbered-tip-chapter, value-list",
            ("buoc 1", "buoc thu", "meo", "cach de", "dieu thu", "thu nhat", "thu hai", "thu ba", "dau tien", "tiep theo", "cuoi cung",
             "bi quyet", "huong dan", "lam sao de", "cach lam", "hai dieu", "ba dieu", "bon dieu", "nam dieu", "kiem tra", "dung voi", "luu y")),
    "taichinh": ("Kinh doanh / tài chính / số liệu", "Data Story (biểu đồ tự vẽ, có nguồn) + preset clean",
                 "glass-counter, split-flap-stats, donut-chart-morph, chalk-math-board, price-tag-rain, stamp-verdict",
                 ("lai suat", "ty gia", "ngan hang", "dau tu", "co phieu", "chung khoan", "loi nhuan", "doanh thu", "tiet kiem", "vay",
                  "trieu dong", "ty dong", "phan tram", "%", "gia vang", "usd", "lam phat", "kinh doanh", "khach hang", "dong tien", "thue", "trieu", "nghin", "so tien", "tien", "mot thang", "mot nam", "chi tieu", "thu nhap", "luong", "bo ong", "xuong tien")),
    "bds": ("Bất động sản / dự án / vị trí", "Product page cho dự án + bản đồ; preset cinematic cho cảnh quan",
            "route-map-journey, road-sign-timer, leader-callout-notes, glass-counter (giá/m²), calendar-week-strip (tiến độ)",
            ("du an", "can ho", "chung cu", "dat nen", "nha pho", "biet thu", "m2", "met vuong", "phap ly", "so do", "chu dau tu",
             "tien ich", "vi tri", "san bay", "cao toc", "khu do thi", "ban giao", "mat tien", "quy hoach", "bat dong san", "mua nha", "nha dat", "ha tang", "gia rao", "dat", "khu vuc", "can nha")),
    "congnghe": ("Review sản phẩm / công nghệ / app / web / tool", "Product page hoặc stan style (quay màn hình); thông số → Hologram HUD; preset launch",
                 "cursor-clicks, search-rank, docs-fly, bento-split, glass-glint-sweep, label-morph, glitch-drop; brandfx webpage (zoom vào mục nhỏ)",
                 ("ai", "chatgpt", "claude", "app", "ung dung", "phan mem", "website", "trang web", "dien thoai", "iphone", "laptop", "may tinh",
                  "cong nghe", "tinh nang", "cap nhat", "phien ban", "chip", "camera", "pin", "man hinh", "tool", "cong cu", "lap trinh", "code")),
    "amthuc": ("Ẩm thực / đồ uống / mỹ phẩm / sản phẩm quay đẹp", "recipe-in-verbs / pour-ritual; cao cấp → tasting-notes-label",
               "beat-punch-cut, whip-pan-cut, mask-rise-verbs, outline-slam-words, leader-callout-notes, film-light-leak",
               ("mon an", "an ngon", "quan an", "nha hang", "huong vi", "nuoc dung", "pho", "bun", "com", "banh", "tra sua",
                "do uong", "cong thuc", "nau", "nuong", "chien", "my pham", "kem duong", "son", "serum", "skincare", "trang diem", "nuoc hoa")),
    "tintuc": ("Tin tức / thời sự / dẫn nguồn", "Caption News hoặc News Package",
               "split-flap-stats, stamp-verdict, search-rank, phone-feed-proof; mg2 doc quét highlight",
               ("tin tuc", "thoi su", "vua qua", "hom qua", "chinh phu", "nghi dinh", "thong tu", "quy dinh", "theo bao", "nguon tin",
                "cong bo", "chinh thuc", "su kien", "ban tin")),
    "kechuyen": ("Kể chuyện / hành trình / khởi nghiệp / hồi ức", "RESULT / Face RESULT hoặc Kinetic doc; preset cinematic",
                 "origin-story-film, cage-open, vhs-pause, route-map-journey, film-light-leak, game-level-up, roller-shutter",
                 ("ngay xua", "hoi do", "nam ay", "cau chuyen", "toi tung", "that bai", "khoi nghiep", "hanh trinh", "bat dau tu", "nho lai",
                  "ky niem", "lich su", "nam 19", "nam 20")),
    "nhanvat": ("Người nổi tiếng / nhân vật / thương hiệu", "Halftone Dossier hoặc Tactile paper",
                "sticker-poster, comic-panel, stamp-verdict; brandfx paper (cắt từ thắt lưng) + brand",
                ("ty phu", "ceo", "nha sang lap", "elon", "musk", "steve jobs", "thuong hieu", "tap doan", "ca si", "dien vien", "nguoi noi tieng")),
    "dulich": ("Du lịch / vlog / một ngày của tôi", "Seoul list (danh sách trên b-roll nhanh) hoặc POV montage",
               "route-map-journey, whip-pan-cut, beat-punch-cut, calendar-week-strip, day-log-diary",
               ("du lich", "chuyen di", "check in", "khach san", "resort", "bien", "nui", "thanh pho", "mot ngay", "vlog", "ve may bay", "dia diem")),
    "dongluc": ("Động lực / tuyên ngôn / câu nói mạnh", "preset kinetic hoặc pop",
                "monument-word, outline-slam-words, stage-spotlight, lights-out-neon, cage-open, momentum-close-cta",
                ("dong luc", "dam me", "uoc mo", "thanh cong", "ky luat", "dung bo cuoc", "hay bat dau", "ban xung dang", "thay doi cuoc doi", "no luc")),
    "nangsuat": ("Năng suất / kiệt sức / công việc", "Clean OS / editorial + đạo cụ công việc",
                 "battery-drain, buffer-wheel, notification-stack-letdown, sticky-note-wall, calendar-week-strip, clone-crowd, corporate-peel",
                 ("deadline", "kiet suc", "met moi", "ap luc", "nang suat", "freelance", "lam them", "cong viec", "sep", "dong nghiep",
                  "nghi ngoi", "thoi gian", "lich lam", "qua tai", "burnout")),
    "sosanh": ("So sánh A vs B / chọn phương án", "mg2 compare + textfx strike",
               "label-morph, receipt-print, venn-overlap, card-pick, stamp-verdict",
               ("so sanh", "nen chon", "khac nhau", "tot hon", "con hon", "vs", "loai nao", "lua chon")),
}
TONES = {"diem-tinh": "clean / editorial / cinematic, chuyển động êm, SFX nhẹ",
         "soi-noi": "pop / meme / beat-punch, cắt theo nhịp nhạc",
         "cam-xuc": "cinematic, ánh sáng phim, khoảng lặng trước câu chốt"}
TECH_ONLY = "scramble, glitch, HUD, tách RGB chỉ dùng cho nhóm congnghe"


def _plain(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower().replace("đ", "d"))
    return " " + re.sub(r"\s+", " ", "".join(c for c in s if unicodedata.category(c) != "Mn")) + " "


def text_of(pdir: Path) -> str:
    """lời của dự án: kịch bản gốc → transcript → project words (TH) → edit.json VO (Review)."""
    for n in ("script_goc.txt", "kichban.txt", "script.txt"):
        f = pdir / n
        if f.is_file() and f.stat().st_size > 20:
            return f.read_text(encoding="utf-8", errors="ignore")
    for n in ("transcript.json", "project.json", "words.json", "captions.json"):
        f = pdir / n
        if not f.is_file():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        ws = d.get("words") if isinstance(d, dict) else d
        if isinstance(ws, list) and ws:
            return " ".join(str(w.get("text") or w.get("w") or w.get("word") or "") if isinstance(w, dict) else
                            str(w[0] if isinstance(w, (list, tuple)) else w) for w in ws)
    return ""


def detect(text: str) -> list[tuple[str, float]]:
    """[(nhóm, điểm)] giảm dần; điểm = số lần gặp từ khoá / căn số từ."""
    t = _plain(text)
    n = max(1, len(t.split()))
    sc = {}
    for g, (_, _, _, kws) in GROUPS.items():
        hit = 0
        for k in kws:
            hit += t.count("%") if k == "%" else t.count(f" {k.strip()} ")
        sc[g] = round(hit / (n ** 0.5) * 10, 2)
    return sorted(sc.items(), key=lambda x: -x[1])


def tone(text: str) -> str:
    t = _plain(text)
    if t.count("!") >= 3 or any(k in t for k in (" cuc ky ", " sieu ", " qua dinh ", " bung no ", " shock ", " soc ")):
        return "soi-noi"
    if any(k in t for k in (" ky niem ", " nho ", " buon ", " co don ", " ngay xua ", " me ", " bo toi ")):
        return "cam-xuc"
    return "diem-tinh"


def load(pdir: Path) -> dict | None:
    f = Path(pdir) / FILE
    try:
        return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    except Exception:
        return None


def choose(pdir: Path, group: str | None = None, why: str = "", source: str = "claude") -> dict:
    pdir = Path(pdir)
    old = load(pdir)
    if old and old.get("source") == "user" and source != "user":
        return old                                         # người dùng đã chọn — giữ
    text = text_of(pdir)
    ranks = detect(text) if text else []
    auto = not group
    if auto:
        group = ranks[0][0] if ranks and ranks[0][1] > 0 else "kienthuc"
    if group not in GROUPS:
        raise SystemExit("nhóm phải là: " + " | ".join(GROUPS))
    name, main, acc, _ = GROUPS[group]
    d = {"group": group, "name": name, "main": main, "accents": acc, "tone": tone(text) if text else "diem-tinh",
         "source": source, "auto": auto, "why": why, "scores": dict(ranks[:4])}
    d["tone_hint"] = TONES[d["tone"]]
    if group != "congnghe":
        d["avoid"] = TECH_ONLY
    (pdir / FILE).write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def check(pdir) -> list[tuple[str, str]]:
    """chưa chọn → app tự nhận diện và ghi luôn (không hỏi người dùng); Claude vẫn nên đọc lời rồi chốt lại nếu lệch."""
    d = load(Path(pdir))
    if not d:
        try:
            d = choose(Path(pdir), source="app")
        except Exception as e:
            return [("warn", f"không tự nhận diện được phong cách ({e}) — chạy `python -m thagent.tools style <dự-án> <nhóm>`")]
        return [("warn", f"app tự chọn phong cách: {d['name']} → {d['main']} — Claude chưa chạy `tools style`; "
                         "đọc lời, sai nhóm thì `tools style <dự-án> <nhóm> <lý do>` (bảng: .claude/shared/editatlas/chon-phong-cach-theo-noi-dung.md)")]
    if d.get("group") not in GROUPS:
        return [("warn", f"content_style.json: nhóm {d.get('group')} không có")]
    return [("info", f"phong cách: {d['name']} → {d['main']} ({d.get('source')}{', tự nhận diện' if d.get('auto') else ''})")]
