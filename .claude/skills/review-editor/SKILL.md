---
name: review-editor
version: 1.3.0
description: Dựng video review hoàn chỉnh từ bộ footage người dùng cung cấp (bất động sản; sản phẩm công nghệ, mỹ phẩm, đồ dùng) — kiểm kê tư liệu, chọn take, xây mạch review, ghép lời với B-roll đúng đối tượng, phụ đề/thông tin/chữ nhấn, xuất dọc 9:16 và/hoặc ngang 16:9. Dùng khi người dùng chọn style Review hoặc yêu cầu dựng review từ nhiều đoạn quay. Không dùng cho Talking Head một người nói (skill talking-head-style) hay motion graphic từ voice (skill voice-to-motion).
---

# Review Editor

**Phiên bản 1.2.2** — xem `CHANGELOG.md`.

Dựng video review từ tư liệu THẬT của người dùng. Giữ nguyên ý, quan điểm và cá tính người dẫn; B-roll là bằng chứng cho lời nói, không phải để làm đẹp.
Tự chạy tới bản xuất; không xin duyệt storyboard/preview ở các bước thông thường. Chỉ hỏi khi thiếu dữ liệu thiết yếu khiến không thể dựng đúng
(vd không phân biệt được footage thuộc sản phẩm/căn nhà nào).

## Điều quan trọng nhất: hiểu hành động → hướng sự chú ý (v1.1)

Xuất được MP4 có phụ đề KHÔNG phải là dựng review. Khi người dẫn **đưa sản phẩm lên / chỉ vào chi tiết**, bản dựng phải đáp lại đúng lúc:
`hands` dò lúc chỉ tay → `track` bám vật → **reframe** ưu tiên mặt + sản phẩm (giảm khoảng trống thừa) → **nhãn sát vật** (đường dẫn ngắn)
→ **một điểm nhấn** (vòng mềm ôm vật) đúng lúc chỉ tay → trở về khung người nói khi chuyển sang nhận xét. Không chồng glow + rung + zoom + nhiều mũi tên.
Nhịp khung: giới thiệu → khung trung (thấy biểu cảm); đưa sản phẩm lên → khung mặt + sản phẩm; chỉ chi tiết → cận/vòng nhấn; nhận xét → về người nói.
Không zoom đều suốt video, không chuyển khung liên tục không lý do.

## Nhịp nói tự nhiên (v1.2 — bắt buộc)

Không cắt sát mốc từ của máy chép lời (mốc lệch, nhất là âm cuối và tiếng nói nhỏ). Mỗi điểm nối giữ đệm room tone thật của nguồn:
đầu ~80–150ms, cuối ~150–300ms (nới tới khi tiếng tắt), nghỉ giữa ý ~200–400ms, chuyển ý lớn ~400–650ms — điều chỉnh theo giọng, không cộng dồn máy móc.
Không chèn lặng số, không lặp/kéo giãn tiếng, không crossfade chồng câu; microfade chỉ chống click. `joins` + `fixjoins` + waveform `review/joins.jpg`.
Chưa nghe được → ghi rõ, không tuyên bố đã kiểm bằng tai.

## Dùng lại phần hay của các skill trước (v1.2.1)

Thứ gì đã tốt ở Talking Head / Voice to Motion mà áp dụng chung được thì DÙNG LẠI, không làm lại kém hơn:
- **Cắt sạch** (Talking Head): `clean` bỏ khoảng lặng thừa, từ đệm, nói vấp/lắp, câu nói lại BÊN TRONG đoạn nói; điểm cắt giữa câu che bằng punch-in ×1,06 xen kẽ.
- **Số liệu then chốt**: `keyinfo` tìm số + đơn vị trong lời → khối `stat` (số đếm lên + đơn vị + nhãn ngắn). Số liệu then chốt KHÔNG được chỉ nằm trong phụ đề.
- **Zoom in–out có chủ đích**: `"auto_zoom": true` đẩy vào ×1,12 lúc khối stat/chữ nhấn hiện, lùi ra khi tắt; tay: reframe `"push:1.15"`. Không zoom đều.
- **SFX** theo bộ đã duyệt của Talking Head (assets/sfx): âm nhẹ “soft” cho số liệu / chữ nhấn / nhãn, flash khi mở sơ đồ; KHÔNG whoosh, swish,
  tiền, data; cách nhau ≥ 10 khung; tắt `"sfx": false`, thêm tay `sfx_events`.
- **Nói hỏng rồi nói lại** (kể cả khi máy chép lời bỏ sót lần nói thứ hai): `clean` tự nghe lại sau chỗ ngừng, cắt mẩu hỏng, giữ câu trơn.
- **Chữ hai tầng** (nhãn trên số / dòng nhỏ trên chữ nhấn): chữ phụ ≈ 0,6 chữ chính — không để chênh lệch quá.

## Học từ thư viện kỹ thuật dựng (v1.3.0)
- Cấu trúc review ngắn 30–60s: câu phán / câu bất ngờ nhất của người review trên cận sản phẩm → mở hộp, gọi tên bộ phận → 2–3 điểm, mỗi điểm một cận đúng
  thứ đang nói → **MỘT nhược điểm thật** (người review có nói thì phải giữ) → phán + giá đúng lời + CTA. Đổi khung / chèn cận sản phẩm mỗi 3–6s; giữ sản phẩm yên đủ để nhìn.
- Câu nói lại nhiều lần: mặc định giữ lần sạch CUỐI. Không thêm giá, thông số, công dụng người review không nói; không dùng stock thay cho chính sản phẩm.
- Cảnh không có người nói vào máy (cận sản phẩm, món ăn): một động từ / một từ mỗi cảnh trồi lên từ mặt nạ đúng lúc cắt; chú thích đường dẫn mảnh
  (vòng trắng đáp lên chi tiết → nhãn chữ hoa giãn cách); vệt sáng quét mặt kính sản phẩm đúng phách.

**Chọn phong cách theo nội dung (BẮT BUỘC trước khi lập kế hoạch):** xác định nhóm nội dung (kiến thức, mẹo, tài chính/số liệu, BĐS, review công nghệ, ẩm thực/mỹ phẩm, tin tức, kể chuyện, nhân vật, du lịch, động lực, năng suất, so sánh, CTA) rồi chọn 1 phong cách chủ đạo + 3–6 điểm nhấn theo `.claude/shared/editatlas/chon-phong-cach-theo-noi-dung.md`; ghi `style: <nhóm> / <chủ đạo>` vào ghi chú.

- Thông số chuyển động, phụ đề, chuyển cảnh: `.claude/shared/editatlas/thong-so-chuyen-dong.md`; luật cắt / âm / phụ đề chung: `.claude/shared/editatlas/quy-tac-dung.md`.

**Bảng motion + SFX theo hình:** chọn 8–12 kỹ thuật mỗi video từ `.claude/shared/editatlas/danh-muc-ky-thuat.md` (hợp phong cách, khác video trước, ghi `motion: …` vào ghi chú); nhạc nền + tắt ngắn trước cảnh lớn, mỗi SFX gắn đúng một thứ trên hình, loé trắng khi trở về người nói — `.claude/shared/editatlas/sfx-va-nhip.md`.

## Hai kiểu quay (v1.3.0)
- **Vừa quay vừa nói** (nói tại chỗ, tắt máy, quay đoạn khác, nói tiếp): app chép lời từng clip, nhóm các lần nói lại, chọn take, ghép thành một mạch — quy trình chính bên dưới.
- **Quay trước, lồng tiếng sau** (thư mục có 1 file âm thanh giọng lồng + các clip / ảnh): dùng CHẾ ĐỘ LỒNG TIẾNG — `"voiceover": {"src": "<ID giọng>"}`,
  `segments` là các CẢNH HÌNH xếp theo lời giọng (mỗi ý → cảnh đúng vật, ≥ 1,2s, có `say` + `why`), tổng = độ dài giọng (cảnh cuối tự khớp).
  Tiếng clip tắt; cảnh món ăn / rót / xèo xèo giữ `"audio": "nat", "nat_db": -20`. Phụ đề + số liệu then chốt lấy từ giọng lồng.
  Không chạy `joins` / `fixjoins` / `clean` (giọng không bị cắt). Định dạng: `.claude/shared/schemas/review-edit.md`.

**Nhắc tên web / app / hãng / nhân vật → TƯ LIỆU THẬT làm motion graphic (bắt buộc khi được nhắc):** `python -m thagent.tools brand <dự-án> <url trang chủ>` (logo chính thức + icon + ảnh đại diện + màu thương hiệu → assets_web/brand_x/, Read sheet.jpg), `tools webshot <dự-án> <url>` (ảnh chụp trang thật), `tools paper <dự-án> <ảnh nhân vật>` (xoá nền → sticker giấy viền trắng; người tự cắt ngang THẮT LƯNG — chỉ thêm `full` khi dáng đẹp). Dựng bằng mg2 / s.mg kind `brand` (logo bật trong ô sáng màu hãng), `webpage` (trang thật trong khung trình duyệt; nói tới MỘT MỤC NHỎ → `mark` + `at` = camera từ giao diện chính ĐẨY VÀO đúng mục đó rồi khoanh, làm tối phần còn lại), `paper` (nhân vật sticker giấy + băng nhãn tên) — xem talking-head-mg2.md. Ảnh nhân vật lấy ảnh THẬT của đúng người (báo, trang chính thức, Wikimedia), ghi nguồn.
**Không đè dính:** icon, shape, ảnh, nhãn minh hoạ KHÔNG chồng / chạm nhau (chừa ≥ 24px); vật chuyển động (xe, mũi tên, con trỏ) dừng TRƯỚC vật đích, xuất phát SAU vật nguồn; nhãn nằm hẳn ngoài khung / vòng của icon. Xem ảnh tĩnh lúc vào, giữa và cuối chuyển động.
**Luật đo trên reel thật + gu người dùng:** `.claude/shared/editatlas/bai-hoc-ghost-editor.md` (b-roll đúng câu, ưu tiên tư liệu của người dùng và ảnh trong khung, một ý một cảnh, liệt kê → chữ; SFX theo đỉnh giọng, 6–12 âm nhẹ / phút, âm phản ứng vào khoảng ngừng sau câu chốt; phụ đề ≥ 48px, tương phản ≥ 3:1). Người dùng góp ý cách dựng → sửa + `python -m thagent.tools taste add "<lời họ>" [skill|all]`.

## Font chữ do người dùng chọn trong app

`review/options.json` → `"font"`: id font người dùng chọn ở khung Review (trống = Montserrat mặc định). App tự vẽ MỌI chữ nhấn + chữ phụ bằng đúng font đó (1 font cho cả clip) — không tự đổi font, không trộn font khác.
- Chỉ IN HOA chữ nhấn; chữ phụ viết thường. Font "chỉ chữ HOA" (Heavitas, Bebas, Trajan…) thì chữ phụ cũng hiện hoa — đó là lựa chọn của người dùng, không phải lỗi.
- Chữ vừa đủ, tinh tế, không che món/đầu người; câu nhấn ngắn để 1 dòng.

## Đọc theo thứ tự

1. `references/workflow.md` — quy trình kiểm kê → phân tích → chọn take → mạch → ghép lời–hình → dựng → kiểm → xuất, kèm lệnh công cụ.
1b. `references/niches.md` — quy tắc RIÊNG từng lĩnh vực: công nghệ (so sánh `compare`), mỹ phẩm (khoá màu, cấm hứa hẹn công dụng), ẩm thực (tiếng hiện trường, ấm màu).
2. `references/styles.md` — 3 phong cách (Tour BĐS / Review trực tiếp / Review tinh tế) × 3 mức thể hiện; KHÔNG trộn phong cách.
3. `references/edit-rules.md` — nguyên tắc dựng hình, J/L-cut, hành động không được cắt, chỉnh màu trung thực.
4. `references/text-graphics.md` — phụ đề / thông tin / chữ nhấn, PiP, callout.
5. `references/formats.md` — dọc và ngang: crop riêng, không crop giữa cố định, bố cục chứa footage khi lệch tỷ lệ.
6. `references/audio.md` — lời rõ, J/L-cut, tiếng hiện trường, nhạc tự giảm, kiểm file xuất.
7. `references/qa.md` — tự kiểm trước bàn giao + báo cáo.
8. `references/reference-study.md` — những gì đã QUAN SÁT ĐƯỢC từ video tham khảo (chỉ hình, chưa nghe).

## Đầu vào / đầu ra

- **Tư liệu dựng**: nhiều file video (người dẫn, B-roll, thao tác, âm hiện trường), có thể có ảnh; hoặc 1 video dài nhiều đoạn. Cả thư mục = MỘT review.
- **Tham khảo phong cách** (thư mục con `tham_khao/`, `reference/`, `ref/`, hoặc mục Tham khảo của app): CHỈ học cách dựng — không chèn footage,
  watermark, logo, intro/outro nền tảng, câu nhận xét hay số liệu của tác giả khác vào video mới.
- **Kèm theo** (tuỳ chọn): brief, kịch bản, thông số, logo.
- **Xuất**: dọc 1080×1920, ngang 1920×1080, hoặc cả hai; 30 fps (trừ khi người dùng yêu cầu khác); nguồn khác fps được chuẩn hoá đúng kỹ thuật.
- **Thời lượng**: theo yêu cầu người dùng; không có → chọn theo lượng nội dung có giá trị + phong cách, ghi lý do trong báo cáo. Không áp một thời lượng cố định.

## Cấm

- Tự tạo lời trải nghiệm, khen/chê, thông số, giá, CTA không có căn cứ; tự tạo voice thay người dẫn khi chưa được yêu cầu.
- Dùng stock/ảnh tạo sinh giả làm nội thất, tiện ích, dự án, sản phẩm thật; tạo before/after hay kết quả thử không có trong tư liệu.
- Cắt mất từ phủ định, điều kiện, đối tượng làm đổi nghĩa; chọn B-roll đẹp nhưng sai sản phẩm/phiên bản/không gian.
- Ghép hai không gian không liền nhau như thể nối trực tiếp (tour BĐS).
- Đánh dấu “đạt” tiêu chí chưa thực sự kiểm.

## Công cụ (app C-Cut)

`.venv/bin/python -m thagent.review <lệnh>` — inventory, media, words, takes, frames, motion, hands, track, joins, fixjoins, clean, keyinfo, check, stills, render (chi tiết trong workflow.md).
Bản dựng là `review/edit.json` tham chiếu nguồn bằng ID + timecode → sửa cục bộ (“thay cảnh này”, “giữ take 2”, “giảm text”, “đổi hook”)
chỉ sửa đúng đoạn trong edit.json rồi dựng lại; phân tích tư liệu được lưu đệm, không làm lại.
