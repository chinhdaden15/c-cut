# Nguyên tắc dựng hình

- Cắt theo ý nghĩa, nhịp nói, hành động. Điểm cắt nằm ở ranh giới từ (check chặn cắt giữa từ).
- Giữ trọn phần quan trọng của thao tác: mở nắp, cắm cáp, thoa sản phẩm, mở cửa, bước vào phòng. Không cắt ngay trước kết quả người xem đang chờ.
  Khi một cảnh B-roll chứa thao tác, đặt `in` trước lúc thao tác bắt đầu và `dur` đủ tới lúc thấy kết quả (xem bằng `frames`).
- Xen cỡ cảnh tổng – trung – cận để làm rõ thông tin; tránh hai cảnh cùng cỡ cùng góc nối nhau (nhảy hình) — chen B-roll che điểm nối.
- B-roll (cutaway `kind: full`) thay hình trong lúc lời vẫn chạy = che điểm cắt và minh họa. Trở về người dẫn ở đoạn nhận xét, cảm xúc, hạn chế, kết luận.
- J-cut (`j`): tiếng đoạn sau vào sớm trên hình đoạn trước; L-cut (`l` ở đoạn sau): tiếng đoạn trước kéo dài sang hình đoạn sau. Dùng 0,2–0,6s.
- Ưu tiên chuyển động có sẵn trong footage; chỉ zoom crop (`crop.zoom`) khi phục vụ điểm nhấn. Không bắt mọi cảnh phải chuyển động,
  không cắt theo số giây cố định, không dùng kiểu xoay camera của bản đồ/motion graphic.
- KHÔNG speed ramp trên đoạn người đang nói (khẩu hình). Không ổn định hình/hiệu chỉnh phối cảnh quá mức làm méo sản phẩm, căn phòng.
- Màu: nhất quán giữa các cảnh nhưng giữ màu da, màu mỹ phẩm (son, phấn, nền), chất liệu sản phẩm trung thực — app không tự chỉnh màu mạnh;
  footage HDR được chuyển SDR đúng (tonemap) để không bệch/cháy.
- Đoạn đen, đứng hình/outro nền tảng (TikTok…), watermark của file tải về: không dùng (check chặn dùng vào đoạn `black`/`outro`).
