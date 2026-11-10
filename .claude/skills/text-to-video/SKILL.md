---
name: text-to-video
version: 1.1.0
description: Dựng video từ kịch bản hoặc yêu cầu ngắn của người dùng — app đọc kịch bản bằng giọng đã chọn (tốc độ 1.1, mốc từng từ đúng chữ kịch bản), Claude chia cảnh theo câu và dựng bằng bộ kit Voice to Motion: video/ảnh minh hoạ thật đúng vật đang nói + motion graphic (số, sơ đồ, bản đồ, chữ động). Xuất cả dọc lẫn ngang. Dùng khi người dùng chọn style Text to Video.
---

# Text to Video

Bộ dựng dùng chung với Voice to Motion: ĐỌC `.claude/skills/voice-to-motion/SKILL.md` + các reference nó chỉ định (kit, khối, bản đồ,
ảnh/b-roll, âm thanh, QA). File này chỉ ghi những điểm KHÁC / THÊM.

## 1. Đầu vào (app đã làm xong trước khi giao)
- `voice.wav` do app đọc từ kịch bản (giọng người dùng chọn, tốc độ 1.1). KHÔNG chạy `v2m clean / restore / speed` — giọng đã sạch, đúng tốc độ.
- `transcript.json`: chữ = ĐÚNG chữ kịch bản (không phải bản chép lời) → phụ đề, chữ nhấn dùng thẳng, không sửa chính tả.
- `script.json`: từng câu + mốc giây (start/end) + `match` (độ khớp giọng đọc; < 0.6 → nghe lại câu đó trước khi dựng).
- App đã LỌC kịch bản trước khi đọc (2.5.8): bỏ dòng ghi chú `*…*`, tiêu đề mốc giờ, "Hình ảnh gợi ý:", link nguồn; lời trong “…” mới đọc.
  `script.txt` = lời đã đọc; `script_goc.txt` = bản gốc (lấy link nguồn từ đây cho phần ghi nguồn, KHÔNG đưa vào phụ đề / chữ trên hình).
  Phụ đề (`captions.json`) dựng từ `transcript.json`, không từ kịch bản gốc. Check báo captions sai → đọc đúng cụm / từ nó chỉ ra, sửa đúng chỗ đó.

## 2. Mỗi câu = một nhịp hình (kiểu KẾT HỢP)
| Câu nói về… | Hình |
|---|---|
| chủ thể có tên (dự án, thương hiệu, sản phẩm, địa danh) | ảnh/video THẬT của đúng chủ thể (entities.json — quy tắc chung) |
| vật / cảnh cụ thể (đầu cọ son, hồ bơi, bác sĩ…) | VIDEO minh hoạ đúng vật (ảnh nếu không có video) |
| số liệu | thẻ số đếm, cột/tròn, so sánh (stat, bars, compare, meter) |
| quy trình, liệt kê, nguyên nhân–kết quả | sơ đồ / steps / checklist hiện dần |
| địa điểm, kết nối | bản đồ (region/pin/route) |
| bản đồ / công nghệ, AI / gõ lệnh / đăng mạng xã hội / quy trình A→B | cảnh hoạt hình đúng lời: `s.mg("mapdraw"|"tech"|"prompt"|"devices"|"pipeline")` (engagement.md §2b) |
| ý trừu tượng, câu khẳng định, câu chuyển | chữ động toàn khung `s.mg("kinetic", lines=[…])` |
VIDEO MINH HOẠ LÀ HÌNH CHÍNH: `s.photo_bg("assets_web/v_x.mp4", dim=0.35, in=<giây>)` phủ kín khung, chữ nhấn / thẻ số / nhãn đè lên.
Không đặt clip nhỏ giữa nền trống. Chủ đề cụ thể (sản phẩm, BĐS, du lịch, ẩm thực, sức khoẻ) → motion-only ≤ 40% thời lượng.
MỖI Ý CỤ THỂ MỘT CLIP RIÊNG (vd son: “đầu cọ”, “chất son mịn”, “giữ màu”, “bảng màu” = 4 clip khác nhau).

## 3. Tìm hình KỸ, đúng ngữ cảnh
- Từ khoá tạo từ CẢ câu + chủ đề video, tiếng Anh cụ thể (vd video son, câu “đầu cọ mềm” → "lipstick applicator close up", không phải "brush").
- Video minh hoạ: **Mixkit trước** — `.venv/bin/python -m thagent.v2m brollsearch {pdir} "<1–2 từ tiếng Anh>"` → Read ảnh ghép có mã →
  `.venv/bin/python -m thagent.v2m broll {pdir} mixkit:<mã> v_ten.mp4` → Read ảnh xem trước in ra. Không có clip hợp thì Pexels / Pinterest
  (WebSearch tìm link, `broll {pdir} <url> v_ten.mp4 "<nguồn>"`).
- Ảnh: `.venv/bin/python -m thagent.tools imgsearch {pdir} "<từ khoá>"` hoặc `tools imgpage {pdir} <link trang>` → Read ảnh ghép → `tools img {pdir} #số i_ten.jpg`.
- Trên video KHÔNG ghi nhãn loại ảnh (“Hình ảnh minh họa / thực tế”) lên video — app tự ẩn; vẫn phân loại ảnh thật (w_*, real=True) để app kiểm; KHÔNG ghi nguồn (nguồn lưu trong illus_sources.json).

## 4. Mô tả + nhãn vật (bắt buộc, app kiểm)
`assets_web/illus_check.json` cho MỌI ảnh/video web: `{"v_dau_co.mp4": {"noi_dung_anh": "cận cảnh đầu cọ son đang tán lên môi", "vat": "đầu cọ son", "cau_noi": "…", "khop": true}}`
- `noi_dung_anh`: THẬT những gì thấy (sau khi Read ảnh/ảnh xem trước).
- `vat`: 2–4 từ, CỤ THỂ đúng ý của clip, đúng cách kịch bản gọi (vd “đầu cọ son”, “bảng màu son”) — không nhãn chung kiểu “son”.
- DÙNG LẠI một ảnh/clip CHỈ khi câu ở cảnh sau cũng nói đúng `vat` đó (vd nhắc “đầu cọ” 3 lần → dùng lại clip đầu cọ, ưu tiên khúc khác của clip).
  Nói ý khác mà chèn lại → LỖI. Không lặp cùng một loại motion quá 2 cảnh liên tiếp.

## 5. Nhịp, mở đầu, kết
- Cảnh 2,5–6s; ≤ 3s phải có thay đổi gắn với từ đang đọc (khối mới, số chạy, zoom, chữ nhấn) — check báo “hình đứng im” là lỗi.
- Ảnh tĩnh luôn có chuyển động chậm (kb); chuyển cảnh đúng chỗ ngắt câu, kèm SFX vai trò tương ứng.
- Mở đầu: hook trong 1s đầu (hình mạnh nhất + chữ lớn). Kết: ~5s cuối CTA chữ lớn, nhịp chậm lại.

## 5b. Thu hút, không đơn điệu (app kiểm, chặn xuất)
**Đọc `.claude/skills/voice-to-motion/references/engagement.md` trước khi lập cảnh** — hook 1s đầu, mỗi cảnh ≤ 6s có một điểm nhấn lớn,
không 3 cảnh liền cùng kiểu, không một nền suốt video, thẻ kết logo lớn. Các điểm dưới đây bổ sung riêng cho Text to Video.
- **Hình thật ≥ 40% thời lượng (check báo LỖI)** — kể cả video giới thiệu app/dịch vụ/khái niệm: tìm b-roll đúng ý câu
  (người ngồi máy tính gõ ý tưởng, người quay điện thoại, màn hình dựng phim, người xem TikTok…). Nền màu + icon chỉ là cảnh chen.
- **Khung đầy:** nội dung chính chiếm ≥ 55% chiều cao, nằm giữa khung; tiêu đề dọc dùng `size="xl"|"l"` (140/112), không để
  một dải chữ nhỏ trên đầu + khoảng giữa trống. Cảnh motion-only phải có 1 khối lớn (icon 3D ≥ 260px, số khổng lồ, thẻ kính).
- **Icon 3D mặc định:** `s.icons` / `s.steps` tự đổi icon phẳng sang icon 3D cùng nghĩa (kho chung); ghi thẳng `"3d:<id>"`
  (`.venv/bin/python -m thagent.tools icon3d <từ khoá>`) để chọn đúng hình. Icon phẳng trong vòng tròn chỉ là phụ.
- **Nhấn nhá mỗi ý chính:** chữ khoá to bật vào đúng lúc nói (`s.keyword` / `s.title(... size="xl")`) + `s.pulse`, ~4s một lần;
  con số → `s.mg("money"|"chart"…)` hoặc `s.stat`; chuyển cảnh có SFX. Nền đổi theo đoạn ý (2 màu chủ đạo, gradient/bokeh/
  ảnh mờ từ b-roll), không giữ một nền phẳng suốt video.
- **Phụ đề:** app tự vẽ kiểu mạng xã hội (cụm 4–6 từ, chữ đậm viền, từ đang đọc đổi màu nhấn); cụm cũ tắt hẳn rồi cụm mới vào;
  cảnh có chữ nhấn trùng lời → `s.captions = False`.
- **App / sản phẩm của chính người làm video** (C-Cut, thương hiệu kênh): khi nói tới cài / dùng / tải app → hiện ĐÚNG icon / logo thật
  (C-Cut: `packaging/icon.png`, chép vào assets_web rồi đặt như ảnh bo góc), không thay bằng icon chung (hộp tải xuống, laptop…).
- **Số tiền:** viết gọn — “một trăm chín mươi chín nghìn đồng” → `199K` (unit="K"), triệu → `M` hoặc “triệu”, tỷ → “tỷ”; tiền ngoại giữ ký hiệu như lời ($, €). Cả cụm một dòng (app tự co chữ).

## 5d. Ý tưởng theo lời (từ 11/2026)
Cảnh `s.mg("custom")` để `region="main"` (mặc định) — một html dùng cho cả 9:16 lẫn 16:9; mốc trong js tính từ t0 của chính lớp đó.
Câu khẳng định trừu tượng, con số, thời gian, so sánh, danh sách → ưu tiên MỘT VẬT ẨN DỤ có 3–5 nhịp đổi neo theo từ (`s.mg("custom")`),
thay cho kinetic chữ trơn hoặc thẻ icon: `.claude/shared/editatlas/y-tuong-theo-loi.md`. Thông số chuyển động: `.claude/shared/editatlas/thong-so-chuyen-dong.md`.
Không lặp cùng một ý tưởng trong một video; b-roll thật vẫn là hình chính (≥ 40%).

**Bảng motion + SFX theo hình:** chọn 8–12 kỹ thuật mỗi video từ `.claude/shared/editatlas/danh-muc-ky-thuat.md` (hợp phong cách, khác video trước, ghi `motion: …` vào ghi chú); nhạc nền + tắt ngắn trước cảnh lớn, mỗi SFX gắn đúng một thứ trên hình, loé trắng khi trở về người nói — `.claude/shared/editatlas/sfx-va-nhip.md`.

**Chữ động mới:** `s.mg("headline"|"scramble"|"drum"|"flipstack"|"spring", t0, t1, …, at=[giây từng từ])` — xem talking-head-mg2.md (scramble chỉ cho video công nghệ); thay cho chữ nhấn tĩnh ở câu mang ý (1–2 lần / phút).
**Nhắc tên web / app / hãng / nhân vật → TƯ LIỆU THẬT làm motion graphic (bắt buộc khi được nhắc):** `python -m thagent.tools brand <dự-án> <url trang chủ>` (logo chính thức + icon + ảnh đại diện + màu thương hiệu → assets_web/brand_x/, Read sheet.jpg), `tools webshot <dự-án> <url>` (ảnh chụp trang thật), `tools paper <dự-án> <ảnh nhân vật>` (xoá nền → sticker giấy viền trắng; người tự cắt ngang THẮT LƯNG — chỉ thêm `full` khi dáng đẹp). Dựng bằng mg2 / s.mg kind `brand` (logo bật trong ô sáng màu hãng), `webpage` (trang thật trong khung trình duyệt, cuộn, khoanh đúng chỗ nói), `paper` (nhân vật sticker giấy + băng nhãn tên) — xem talking-head-mg2.md. Ảnh nhân vật lấy ảnh THẬT của đúng người (báo, trang chính thức, Wikimedia), ghi nguồn.
**Luật đo trên reel thật + gu người dùng:** `.claude/shared/editatlas/bai-hoc-ghost-editor.md` (b-roll đúng câu, ưu tiên tư liệu của người dùng và ảnh trong khung, một ý một cảnh, liệt kê → chữ; SFX theo đỉnh giọng, 6–12 âm nhẹ / phút, âm phản ứng vào khoảng ngừng sau câu chốt; phụ đề ≥ 48px, tương phản ≥ 3:1). Người dùng góp ý cách dựng → sửa + `python -m thagent.tools taste add "<lời họ>" [skill|all]`.

## 5c. Âm thanh + chuyển động
Nhạc nền (Mixkit, `musicsearch` → `music` → `K.music`), SFX hiện đại, chuyển cảnh zoom/glitch, icon nét `ui:` — engagement.md §4b.

## 6. Sửa
Người dùng góp ý → chỉ sửa đúng cảnh được nhắc. Sửa LỜI → app đọc lại câu đó (người dùng sửa trong ô kịch bản), không tự đổi lời.
