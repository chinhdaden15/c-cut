# SFX, nhạc và nhịp hình — học từ video mẫu short (người nói + chèn cảnh, 25s)

Phân tích phổ âm + từng frame của video mẫu (11/2026). Áp cho Talking Head, Review, Voice to Motion, Text to Video.

## 1. Nhạc nền là sàn, SFX là dấu chấm câu
- Có NHẠC NỀN suốt video (bass sâu, đều), hạ dưới giọng. SFX nằm trên nền nhạc nên nghe liền, không "trơ trọi".
- **Tắt nhạc ngắn (~0.3–0.6s) ngay trước khoảnh khắc lớn** rồi cho nhạc + tiếng nổ vào cùng lúc cảnh mới hiện → cảnh "nổ" ra.
  App: `plan.music = {"file": "assets_web/m_<mã>.mp3", "gain_db": -21, "offset": <giây bắt đầu trong bài>}` — tự hạ dưới giọng,
  tự tắt 0.4s trước mỗi cảnh MG phủ khung, fade 1.5s cuối. Tìm nhạc: `python -m thagent.v2m musicsearch "<thể loại EN>"` → `music <thư mục dự án> <mã>`.
  Hợp người nói kiến thức / kinh doanh: house, minimal techno, lo-fi nhẹ; tránh bài có lời.
- 3s cuối: KHÔNG SFX, chỉ giọng + nhạc — để câu kết tự đứng.

## 2. Mỗi SFX gắn đúng một thứ thấy trên hình
| Trên hình | Âm trong mẫu | App |
|---|---|---|
| mở video bằng hiệu ứng số / HUD | tiếng va mạnh + lấp lánh cao | hook: impact + shimmer |
| từ khoá chữ to bật từng từ | pop / click ngắn tần cao, mỗi từ khoá một tiếng (không phải mọi từ phụ đề) | âm nhẹ chữ chính |
| loé trắng sang cảnh phủ khung | whoosh + tiếng trầm (bass drop) | `mgtrans` lúc vào |
| số đang chạy | tick dồn dập nhỏ (~0.15s/tiếng) → tiếng tiền / ding lúc dừng | money / chart tự có `_roll_ticks` + `u_money` |
| tiền / vật rơi bay | whoosh tụt cao độ | swish |
| tan điểm ảnh / glitch | tiếng số rè ngắn | glitch |
| zoom cận vào biểu đồ | zip / whoosh ngắn | punch |
| thẻ / chip hiện từng cái | một pop mỗi thẻ, cách ≥ 0.4s | pop theo `at` |
| loé trắng trả về người nói | swish sáng (air) | `u_swish` lúc cảnh MG hết |
- Không có hình → không có tiếng. Không SFX cho mọi chữ phụ đề. SFX thấp hơn giọng ~10 dB, tiếng tick số còn thấp hơn (~−23 dB).

## 3. Cỡ cảnh đổi liên tục (đỡ nhàm, giấu jump cut)
- Người nói được cắt như quay nhiều máy: **trung → rộng → cận** xen kẽ, mỗi cảnh ~3–6s, đổi ở chỗ ngắt câu / ranh giới từ.
  Cận không nối cận. App tự làm (`plan.framing` = None); tự đặt: `[{"at": frame, "size": "wide"|"medium"|"close"}]`; tắt: `[]`.
- Cận rất sát (thấy miệng + ngực) chỉ cho khoảnh khắc nhấn (số lớn, biểu đồ đi lên), giữ ngắn.
- Đổi cỡ là CẮT (1 frame), không trượt zoom. Trượt nhanh 1.0 → 1.5 trong vài frame trông như hình bị giật — app đã đổi chữ khổng lồ
  sau lưng sang kiểu cắt vào / cắt ra + loé nhẹ.

## 4. Chèn cảnh phủ khung theo nhịp
- Cứ ~4–6s có một thay đổi lớn: đổi cỡ cảnh, chữ từ khoá, chip / thẻ, hoặc cảnh phủ khung (đếm tiền, mô hình 3D, bản đồ…).
- Vào cảnh phủ khung: loé nhẹ + whoosh; trở về người nói: **loé trắng sáng loá rồi hạ** (app tự làm cho mọi cảnh MG phủ khung) + swish.
- Cảnh phủ khung ngắn 2–4s, có MỘT chuyển động chính (số chạy, vật rơi, camera lướt) — không đứng yên.
- Chữ từ khoá: dòng nhỏ trắng dẫn phía trên + từ khoá to màu nhấn hiện theo từng từ đúng lúc nói, kèm icon lấp lánh nhỏ.
