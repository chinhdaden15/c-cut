---
name: text-to-video
description: Dựng video từ kịch bản hoặc yêu cầu ngắn của người dùng — app đọc kịch bản bằng giọng đã chọn (tốc độ 1.1, mốc từng từ đúng chữ kịch bản), Claude chia cảnh theo câu và dựng bằng bộ kit Voice to Motion: video/ảnh minh hoạ thật đúng vật đang nói + motion graphic (số, sơ đồ, bản đồ, chữ động). Xuất cả dọc lẫn ngang. Dùng khi người dùng chọn style Text to Video.
---

# Text to Video

Bộ dựng dùng chung với Voice to Motion: ĐỌC `.claude/skills/voice-to-motion/SKILL.md` + các reference nó chỉ định (kit, khối, bản đồ,
ảnh/b-roll, âm thanh, QA). File này chỉ ghi những điểm KHÁC / THÊM.

## 1. Đầu vào (app đã làm xong trước khi giao)
- `voice.wav` do app đọc từ kịch bản (giọng người dùng chọn, tốc độ 1.1). KHÔNG chạy `v2m clean / restore / speed` — giọng đã sạch, đúng tốc độ.
- `transcript.json`: chữ = ĐÚNG chữ kịch bản (không phải bản chép lời) → phụ đề, chữ nhấn dùng thẳng, không sửa chính tả.
- `script.json`: từng câu + mốc giây (start/end) + `match` (độ khớp giọng đọc; < 0.6 → nghe lại câu đó trước khi dựng).

## 2. Mỗi câu = một nhịp hình (kiểu KẾT HỢP)
| Câu nói về… | Hình |
|---|---|
| chủ thể có tên (dự án, thương hiệu, sản phẩm, địa danh) | ảnh/video THẬT của đúng chủ thể (entities.json — quy tắc chung) |
| vật / cảnh cụ thể (đầu cọ son, hồ bơi, bác sĩ…) | VIDEO minh hoạ đúng vật (ảnh nếu không có video) |
| số liệu | thẻ số đếm, cột/tròn, so sánh (stat, bars, compare, meter) |
| quy trình, liệt kê, nguyên nhân–kết quả | sơ đồ / steps / checklist hiện dần |
| địa điểm, kết nối | bản đồ (region/pin/route) |
| ý trừu tượng, câu chuyển | chữ động + icon |
Một cảnh có thể là video nền + thẻ số/chữ nhấn phía trên. Chủ đề cụ thể (sản phẩm, BĐS, du lịch, ẩm thực, sức khoẻ) → ≥ 40% cảnh có video/ảnh thật.

## 3. Tìm hình KỸ, đúng ngữ cảnh
- Từ khoá tạo từ CẢ câu + chủ đề video, tiếng Anh cụ thể (vd video son, câu “đầu cọ mềm” → "lipstick applicator close up", không phải "brush").
- Video minh hoạ: Pexels trước (WebSearch `<từ khoá> site:pexels.com/video`), không có thì Pinterest (`<từ khoá> video site:pinterest.com`),
  Pixabay chỉ khi tải được. Tải: `.venv/bin/python -m thagent.v2m broll {pdir} <url> v_ten.mp4 "<nguồn>"` → Read ảnh xem trước in ra.
- Ảnh: `.venv/bin/python -m thagent.tools imgsearch {pdir} "<từ khoá>"` hoặc `tools imgpage {pdir} <link trang>` → Read ảnh ghép → `tools img {pdir} #số i_ten.jpg`.
- Trên video chỉ ghi “Hình ảnh minh họa” / “Hình ảnh thực tế”; KHÔNG ghi nguồn (nguồn lưu trong illus_sources.json).

## 4. Mô tả + nhãn vật (bắt buộc, app kiểm)
`assets_web/illus_check.json` cho MỌI ảnh/video web: `{"v_dau_co.mp4": {"noi_dung_anh": "cận cảnh đầu cọ son đang tán lên môi", "vat": "đầu cọ son", "cau_noi": "…", "khop": true}}`
- `noi_dung_anh`: THẬT những gì thấy (sau khi Read ảnh/ảnh xem trước).
- `vat`: tên vật/cảnh chính, ngắn, đúng cách kịch bản gọi.
- DÙNG LẠI một ảnh/clip CHỈ khi câu ở cảnh sau cũng nói đúng `vat` đó (vd nhắc “đầu cọ” 3 lần → dùng lại clip đầu cọ, ưu tiên khúc khác của clip).
  Nói ý khác mà chèn lại → LỖI. Không lặp cùng một loại motion quá 2 cảnh liên tiếp.

## 5. Nhịp, mở đầu, kết
- Cảnh 2,5–6s; ≤ 3s phải có thay đổi gắn với từ đang đọc (khối mới, số chạy, zoom, chữ nhấn) — check báo “hình đứng im” là lỗi.
- Ảnh tĩnh luôn có chuyển động chậm (kb); chuyển cảnh đúng chỗ ngắt câu, kèm SFX vai trò tương ứng.
- Mở đầu: hook trong 1s đầu (hình mạnh nhất + chữ lớn). Kết: ~5s cuối CTA chữ lớn, nhịp chậm lại.

## 6. Sửa
Người dùng góp ý → chỉ sửa đúng cảnh được nhắc. Sửa LỜI → app đọc lại câu đó (người dùng sửa trong ô kịch bản), không tự đổi lời.
