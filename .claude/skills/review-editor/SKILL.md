---
name: review-editor
version: 1.2.2
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
