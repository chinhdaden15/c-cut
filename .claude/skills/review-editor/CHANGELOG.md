# Changelog — Review Editor

## 1.2.2
- Lĩnh vực mới: Công nghệ, Mỹ phẩm – skincare, Ẩm thực (cùng BĐS, Sản phẩm khác); đặt cho cả video hoặc từng đoạn (video nhiều ngành).
- Công nghệ: khối so sánh 2 cột `compare` (tô cột thắng), bản ngang đặt ô bên, không đè phụ đề.
- Mỹ phẩm: khoá màu; check chặn chữ trên hình hứa hẹn công dụng mà người nói không nói, cảnh báo khi lời có khẳng định mạnh.
- Ẩm thực: tiếng hiện trường cảnh món tự trộn −18 dB dưới lời; ấm màu nhẹ trung thực.
- Phụ đề gộp số bị máy chép lời tách (“6 ,7” → “6,7”; “350 .000” → “350.000”); check số liệu so theo giá trị kiểu Việt.
- Sửa: crop-mất-mặt báo sai khi mặt đã sát mép khung nguồn; ô chữ ngang lấn vùng an toàn; khối số đo bề rộng theo chữ hiển thị.

## 1.2.1
- Dùng lại Cắt sạch của Talking Head (`clean`): bỏ lặng thừa / từ đệm / nói vấp / câu nói lại trong đoạn nói; đoạn con khoá biên, punch-in ×1,06 che điểm cắt;
  chữ/cutaway/reframe giữ đúng khoảnh khắc nguồn; báo cáo `review/cleanup.json`.
- Mốc từ được siết theo khoảng lặng đo bằng sóng âm (như Talking Head) → phụ đề khớp tiếng hơn; chữ có mốc máy chép lời lấn vào chỗ đã cắt vẫn giữ trên phụ đề.
- Số liệu then chốt: `keyinfo` (số + đơn vị, khoảng “từ 3 đến 5”) + khối `stat` (số đếm lên, đơn vị, nhãn); check cảnh báo số liệu chỉ có trong phụ đề.
- Zoom in–out có chủ đích: `auto_zoom`, reframe `push:<hệ số>` (giới hạn giữ nét).
- Nói hỏng rồi nói lại mà máy chép lời bỏ sót (“Đến… Đến bây giờ”): `clean` nghe lại đoạn sau chỗ ngừng (restart.py) → cắt mẩu hỏng, giữ câu trơn; vá lời phụ đề.
- Mốc từ chỉnh theo sóng âm thật: từ mà máy chép lời cho bắt đầu trong khoảng lặng → dời tới chỗ có tiếng (đúng cả nền ồn ngoài trời); dùng chung cho phụ đề, điểm cắt, check.
- Cắt sạch giữ nguyên biên ngoài người dựng đặt (giữ hình kết), bỏ mẩu đầu quá ngắn; chữ/cutaway có mốc rơi vào chỗ cắt chuyển sang đoạn con kế (không mất).
- SFX theo bộ ĐÃ DUYỆT của Talking Head: âm nhẹ “soft” cho số liệu/chữ nhấn/nhãn, flash khi mở sơ đồ; không whoosh/swish/tiền/data (dịu tai).
- Check “cắt dồn”: cảnh giữa hai lần cắt < 0,8s → cảnh báo (< 0,3s = lỗi); cutaway nối thẳng sang cutaway kế, không chen hình người dẫn vài khung.
- Chữ hai tầng cân nhau: chữ phụ ≈ 0,58 chữ chính (số liệu 104/94, chữ nhấn 88/80), khoảng cách hai tầng rộng hơn.
- Phụ đề: ưu tiên ngắt ở dấu phẩy; không tách tên ngắn (“đường D”, “khu A”); không ngắt sau giới từ dù có chỗ ngừng.
- Phụ đề: đoạn con của Cắt sạch vẫn chung câu; không kết cụm bằng giới từ (tại/dọc/trên/về/theo…); cụm hiện < 1s gộp với cụm sau khi còn đọc được.

## 1.2.0
- Nhịp nói tự nhiên: `joins` (đệm, nghỉ, còn tiếng tại điểm cắt, waveform `joins.jpg`), `fixjoins` (nới theo năng lượng tiếng, chỉ nới, dời mốc);
  check chặn điểm nối gấp (< 120ms) / đuôi bị cắt.
- Spotlight: lớp đen 25–40% ngoài ô bo góc mềm ôm vật, giữ màu sản phẩm, theo vật từng khung, fade ~0,24s, mất dấu → tắt; viền mảnh kèm theo.
- Sơ đồ minh họa ý (`diagram`) phủ hình trong lúc lời chạy.
- Phụ đề theo cụm nghĩa (liên từ, chỗ ngừng, không kết cụm bằng từ chỉ định/giới từ, giữ thuật ngữ), tự thêm dấu chấm khi máy chép lời viết hoa giữa câu.
- Chữ nhấn tự né mặt/tóc; QA file xuất: chữ chạm mặt, spotlight mất dấu, phụ đề đổi nhanh, điểm nối.
- Check: lời nhắc sản phẩm phải có spotlight/nhãn đúng lúc, reframe giữ trọn mặt + vật, chữ nhấn lặp khi hình đã thể hiện ý.

## 1.1.0
- Hiểu hành động + hướng sự chú ý: `hands` (dò giơ/chỉ tay), `track` (bám vật CSRT), `frames` có lưới toạ độ, `motion` (nét/chuyển động + lời).
- Reframe động có khoá (`face`, `<track>`, `face+<track>`, `base`), chuyển mượt, tự giới hạn phóng giữ nét.
- Nhãn sản phẩm sát vật (chấm neo + đường dẫn, khung ôm chữ, đi theo vật); vòng nhấn đúng lúc chỉ tay.
- Phụ đề hiện cả cụm, tô màu từ đang đọc; thẻ thông tin ôm nội dung.
- Nhận biết ngược sáng → nâng vùng tối nhẹ (không tăng bão hoà).
- Check mới: track phủ đủ, khung nhòe/thao tác chuẩn bị, kết hụt, reframe phóng quá; QA file xuất: phụ đề khớp tiếng (năng lượng tiếng).

## 1.0.0
- Skill thứ 3 của C-Cut: dựng video review từ footage người dùng (BĐS; sản phẩm công nghệ, mỹ phẩm, đồ dùng).
- Công cụ `thagent.review`: kiểm kê (ID ổn định, thông số, trùng, đoạn đen, outro, lưu đệm), phân tích (cảnh, nét/rung/sáng, mặt, lời từng từ,
  từ cần soát), nhóm take + điểm, bản dựng edit.json tham chiếu nguồn, check trước dựng, stills đúng như bản xuất, render dọc/ngang
  (crop riêng theo mặt, bố cục chứa footage khi lệch tỷ lệ, cutaway/PiP, J/L-cut, tiếng hiện trường, nhạc tự giảm, −16 LUFS),
  phụ đề/thông tin/chữ nhấn, kiểm file xuất thật.
- Sửa chữ chép sai trên phụ đề (`replace`, `fixes`).
- 3 phong cách × 3 mức thể hiện; tách tư liệu dựng và video tham khảo.
