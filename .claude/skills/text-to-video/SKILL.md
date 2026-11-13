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
| chủ thể có tên (dự án, thương hiệu, sản phẩm, địa danh) | ảnh/video THẬT của đúng chủ thể (entities.json — quy tắc chung). Sản phẩm / hãng / người: khai `"kind": "product" \| "brand" \| "person"` → chỉ lần nhắc ĐẦU (và khi cách > 10s) cần ảnh thật; các câu sau về tính năng dùng VIDEO minh hoạ đúng ý (động cơ, bánh xe, sạc, người dùng…). Dự án / địa danh (mặc định "place"): mọi lần nhắc cần ảnh thật |
| vật / cảnh cụ thể (đầu cọ son, hồ bơi, bác sĩ…) | VIDEO minh hoạ đúng vật (ảnh nếu không có video) |
| số liệu | thẻ số đếm, cột/tròn, so sánh (stat, bars, compare, meter) |
| quy trình, liệt kê, nguyên nhân–kết quả | sơ đồ / steps / checklist hiện dần |
| địa điểm, kết nối | bản đồ (region/pin/route) |
| bản đồ / công nghệ, AI / gõ lệnh / đăng mạng xã hội / quy trình A→B | cảnh hoạt hình đúng lời: `s.mg("mapdraw"|"tech"|"prompt"|"devices"|"pipeline")` (engagement.md §2b) |
| ý trừu tượng, câu khẳng định, câu chuyển | chữ động toàn khung `s.mg("kinetic", lines=[…])` |
VIDEO MINH HOẠ LÀ HÌNH CHÍNH: `s.photo_bg("assets_web/v_x.mp4", dim=0.35, in=<giây>)` phủ kín khung, chữ nhấn / thẻ số / nhãn đè lên.
Không đặt clip nhỏ giữa nền trống. Chủ đề cụ thể (sản phẩm, BĐS, du lịch, ẩm thực, sức khoẻ) → motion-only ≤ 40% thời lượng.
MỖI Ý CỤ THỂ MỘT CLIP RIÊNG (vd son: “đầu cọ”, “chất son mịn”, “giữ màu”, “bảng màu” = 4 clip khác nhau).
**VIDEO ≥ 50% thời lượng** khi chủ đề là sản phẩm / xe / máy / món / nơi chốn: ảnh tĩnh chỉ để nhận diện đúng chủ thể (ảnh thật) và ≤ 2 cảnh ảnh liền nhau.
Không có clip của ĐÚNG mẫu (thường gặp: xe, điện thoại đời cụ thể) → tìm clip CHUNG khớp ý câu (xe chạy nhanh, đồng hồ tốc độ, khoang máy, mâm xe,
trạm sạc, người ngoái nhìn), mỗi câu một clip; KHÔNG đặt clip mẫu / hãng khác đúng lúc đang gọi tên chủ thể (dễ hiểu nhầm là chính nó).
Đổi nền giữa câu trong cùng cảnh: `s.photo_bg(src, t, dim=…)` (ảnh thật nhận diện → clip ý tiếp theo).
**Địa danh / vị trí / kết nối → BẢN ĐỒ ĐƯỜNG PHỐ THẬT, không icon** (học từ map-route-video, MIT): nhắc khu vực, phường, nút giao,
"gần X", "cách Y bao nhiêu phút" → `python -m thagent.v2m geocode "<tên>"` (toạ độ OSM, KHÔNG tự nhớ toạ độ) →
`python -m thagent.v2m osrm {pdir} <lon,lat> <lon,lat> <tên>` (tuyến + km + phút THẬT) → `python -m thagent.v2m streetmap {pdir}
<lon0,lat0,lon1,lat1> dark <tên>` → trong cảnh: `s.street_map("assets_web/map_<tên>.png")`, `s.look(box, t)`, `s.callout(lonlat, "Tên", t,
sub="~6,1 km · ~9 phút (ước tính)")`, `s.route("assets_web/route_<tên>.geojson", "<tên>", t, d=2)`. Camera: khu vực → dự án → vẽ tuyến
tới điểm đến đúng lúc nói. Thời gian luôn ghi "ước tính", nguồn bản đồ tự hiện. Ảnh mặt bằng / bản đồ vị trí của chủ đầu tư vẫn dùng được.
CẤM: hàng icon (pin / cây cầu / con đường) thay cho địa danh; ảnh vệ tinh ghép từ dịch vụ khác.
**Chữ nhấn (keyword) KHÔNG đè ảnh / bản đồ:** app tự dời viên chữ lên trên / xuống dưới ảnh; đừng đặt ry vào giữa ảnh.
Ảnh đã nói đủ thì bỏ chữ nhấn. **Icon tiền = XẤP TIỀN** (`3d:f-dollar-banknote`), không bao giờ túi tiền (app tự đổi).
**Chữ động (kinetic) đọc thành MỘT câu:** 2–3 dòng nối nhau đúng thứ tự lời (vd "LƯU VIDEO / THEO DÕI KÊNH"), mỗi dòng ≤ 3 từ,
`hl` là MỘT cụm liền trong dòng (không tô lẻ từng chữ), không dòng rời không nghĩa; cùng cỡ, gọn ~70% bề ngang (app tự chỉnh).
**Phụ đề:** mỗi cụm trong captions.json ≤ 2 dòng, dòng dọc ≤ ~22 ký tự (chữ đậm 62px, khung 920px) — app đo chữ thật và tự tách cụm dài,
nhưng tự chia ngắn từ đầu thì nhịp đẹp hơn; không ngắt giữa từ ghép / cụm số (“ánh / mắt”, “ba trăm sáu / mươi”).

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

**Chọn phong cách theo nội dung — Claude TỰ làm, không hỏi người dùng:** ngay khi có lời (transcript / kịch bản) chạy `python -m thagent.tools style <dự-án>` → app nhận diện nhóm (kiến thức, mẹo, tài chính, BĐS, công nghệ, ẩm thực/mỹ phẩm, tin tức, kể chuyện, nhân vật, du lịch, động lực, năng suất, so sánh) + phong cách chủ đạo + điểm nhấn + giọng điệu, ghi `content_style.json`. Đọc lời thật: đúng thì dựng theo; sai / hai nhóm sát điểm thì chốt `tools style <dự-án> <nhóm> <lý do>`. Người dùng đã nói rõ phong cách → làm theo họ. Chi tiết từng nhóm: `.claude/shared/editatlas/chon-phong-cach-theo-noi-dung.md`. Quên bước này thì lúc kiểm tra app tự chọn và báo cảnh báo.

**LOGO CHÍNH THỨC khi nhắc app / ứng dụng / thương hiệu (bắt buộc, app kiểm và chặn):** nói "C-Cut", "TikTok", "YouTube", "Reels",
"Zalo", "ChatGPT", "Canva", tên hãng / sản phẩm (khai `"kind": "brand"` trong entities.json)… → `python -m thagent.tools logo {pdir} "<tên>"
[tên-miền]` (C-Cut lấy logo đóng gói trong app; hãng khác lấy icon chính thức) → hiện đúng lúc nói. CHỈ dùng BIỂU TƯỢNG (symbol / icon app) của doanh nghiệp, thương hiệu, ứng dụng — không dùng bản logo có chữ tên hãng, không tự vẽ / tự gõ chữ thành logo. Tên hãng nếu cần thì để ở nhãn chữ cạnh logo. Không bao giờ thay bằng icon chung
(hộp tải về, điện thoại, play…). Video hướng dẫn / giới thiệu C-Cut: dùng ẢNH CHỤP GIAO DIỆN THẬT người dùng gửi (tu_lieu/) và đẩy camera
vào đúng nút đang nói (brandfx webpage `mark`), không thay bằng cảnh "gõ lệnh" / sơ đồ chung.
Trong builder: `s.logo("assets_web/logo_<tên>.png", t, "Tên")` (ô trắng bo góc — logo đen không chìm).

**Phụ đề 2 dòng phải CĂN ĐỀU** (không trên dài dưới ngắn): app tự cân lại theo bề rộng thật; khi viết captions.json cũng chia cụm sao cho 2 dòng dài gần bằng nhau, không ngắt giữa từ ghép / cụm số.

thay cho kinetic chữ trơn hoặc thẻ icon: `.claude/shared/editatlas/y-tuong-theo-loi.md`. Thông số chuyển động: `.claude/shared/editatlas/thong-so-chuyen-dong.md`.
Không lặp cùng một ý tưởng trong một video; b-roll thật vẫn là hình chính (≥ 40%).

**Bảng motion + SFX theo hình:** chọn 8–12 kỹ thuật mỗi video từ `.claude/shared/editatlas/danh-muc-ky-thuat.md` (hợp phong cách, khác video trước, ghi `motion: …` vào ghi chú); nhạc nền + tắt ngắn trước cảnh lớn, mỗi SFX gắn đúng một thứ trên hình, loé trắng khi trở về người nói — `.claude/shared/editatlas/sfx-va-nhip.md`.

**Chữ động mới:** `s.mg("headline"|"scramble"|"drum"|"flipstack"|"spring", t0, t1, …, at=[giây từng từ])` — xem talking-head-mg2.md (scramble chỉ cho video công nghệ); thay cho chữ nhấn tĩnh ở câu mang ý (1–2 lần / phút).
**Nhắc tên web / app / hãng / nhân vật → TƯ LIỆU THẬT làm motion graphic (bắt buộc khi được nhắc):** `python -m thagent.tools brand <dự-án> <url trang chủ>` (logo chính thức + icon + ảnh đại diện + màu thương hiệu → assets_web/brand_x/, Read sheet.jpg), `tools webshot <dự-án> <url>` (ảnh chụp trang thật), `tools paper <dự-án> <ảnh nhân vật>` (xoá nền → sticker giấy viền trắng; người tự cắt ngang THẮT LƯNG — chỉ thêm `full` khi dáng đẹp). Dựng bằng mg2 / s.mg kind `brand` (logo bật trong ô sáng màu hãng), `webpage` (trang thật trong khung trình duyệt; nói tới MỘT MỤC NHỎ → `mark` + `at` = camera từ giao diện chính ĐẨY VÀO đúng mục đó rồi khoanh, làm tối phần còn lại), `paper` (nhân vật sticker giấy + băng nhãn tên) — xem talking-head-mg2.md. Ảnh nhân vật lấy ảnh THẬT của đúng người (báo, trang chính thức, Wikimedia), ghi nguồn.
**Không đè dính:** icon, shape, ảnh, nhãn minh hoạ KHÔNG chồng / chạm nhau (chừa ≥ 24px); vật chuyển động (xe, mũi tên, con trỏ) dừng TRƯỚC vật đích, xuất phát SAU vật nguồn; nhãn nằm hẳn ngoài khung / vòng của icon. Xem ảnh tĩnh lúc vào, giữa và cuối chuyển động.
**Luật đo trên reel thật + gu người dùng:** `.claude/shared/editatlas/bai-hoc-ghost-editor.md` (b-roll đúng câu, ưu tiên tư liệu của người dùng và ảnh trong khung, một ý một cảnh, liệt kê → chữ; SFX theo đỉnh giọng, 6–12 âm nhẹ / phút, âm phản ứng vào khoảng ngừng sau câu chốt; phụ đề ≥ 48px, tương phản ≥ 3:1). Người dùng góp ý cách dựng → sửa + `python -m thagent.tools taste add "<lời họ>" [skill|all]`.

## 5e. Video TIN TỨC từ bài báo (article.json có sẵn — từ 2.5.11)

Người dùng dán LINK bài báo (hoặc nội dung bài) → app đã đọc bài (`article.json`: title, sapo, date, source, paragraphs, images,
interaction), tải ảnh trong bài (`assets_web/news_chinh.jpg`, `news_anh_NN.jpg`), chụp trang báo thật (`assets_web/_bao/doan_NN.jpg`
= vùng quanh đoạn NN đã tô dạ quang). Xem nhanh: `assets_web/_bao/sheet.jpg`.
Đọc lại bài bất kỳ lúc nào: `python -m thagent.article fetch <link>`; chuẩn bị lại: `python -m thagent.article prepare <dự-án> <link>`.

**Lời đọc** (app giao trước khi dựng): bản tin 40–90 giây; câu đầu là hook; giữ ĐÚNG số liệu, tên riêng, chức danh, mốc thời gian;
không chép nguyên văn cả đoạn, không thêm thông tin ngoài bài, không bình luận chủ quan; ghi nguồn bằng lời một lần (“Theo VnExpress, …”);
không đọc link.

**Khuôn hình** (bắt buộc, cả 9:16 và 16:9 — `thagent/v2m/news.py`):
```
A = K.news()                                  # bật khuôn tin tức, chuyển cảnh nhẹ
s = K.scene(0, t_hook, "thumbnail"); s.news_open()          # ảnh chính + TIÊU ĐỀ LỚN + ngày đăng (trong câu hook)
K.news_bar()                                  # 1 dòng nhỏ “Nguồn: <báo>” góc trên trái, suốt video
...thân bài theo từng ý của bài: ảnh trong bài (photo / photo_bg, real=True khi đúng chủ thể), video thật đúng chủ thể (v2m broll),
   stat / bars cho số liệu, street_map / mapclip khi bài có địa điểm, logo khi nhắc thương hiệu
s.news_page(i, t)                             # ẢNH CHỤP TRANG BÁO THẬT, phóng chậm vào đúng ĐOẠN i đang nói (i theo article.json
                                              # "paragraphs", 1 = đoạn đầu; 0 = đầu trang) — ít nhất 2 lần, đúng đoạn chứa ý đang đọc
s = K.scene(t_end, K.T, "nguồn"); s.news_end(t_end, summary="câu tóm")   # câu tóm + “Nguồn: <báo> · <ngày>” + tiêu đề bài
```
- KHÔNG khung / nhãn / logo / màu của báo trên hình (người dùng duyệt 12/11/2026): nguồn chỉ là 1 dòng nhỏ góc trên trái
  (K.news_bar) + dòng nguồn ở cảnh kết. Không đặt chữ / khối đè lên dòng nguồn.
- Thumbnail và cảnh kết KHÔNG cần ảnh minh hoạ web thêm; thân bài ưu tiên ảnh trong bài > video thật đúng chủ thể > ảnh web đúng chủ thể.
- Ảnh trong bài là của báo: chỉ dùng để minh hoạ đúng bài đó (đã ghi nguồn trong illus_sources.json).

## 5c. Âm thanh + chuyển động
Nhạc nền (Mixkit, `musicsearch` → `music` → `K.music`), SFX hiện đại, chuyển cảnh zoom/glitch, icon nét `ui:` — engagement.md §4b.

## 6. Sửa
Người dùng góp ý → chỉ sửa đúng cảnh được nhắc. Sửa LỜI → app đọc lại câu đó (người dùng sửa trong ô kịch bản), không tự đổi lời.
