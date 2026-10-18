# Dọc 9:16 và ngang 16:9

- Cùng mạch lời + nguồn tư liệu, nhưng bố cục và crop RIÊNG từng tỷ lệ (`crop: {"9x16": {...}, "16x9": {...}}`).
- Dọc ưu tiên mặt, tay, sản phẩm, chi tiết. Ngang tận dụng không gian, thao tác trên bàn, nhiều người, so sánh.
- Có nhiều góc quay → chọn góc hợp từng tỷ lệ (đoạn khác nhau cho 9x16 và 16x9 là được nếu cùng nội dung — ghi rõ).
- KHÔNG crop giữa cố định, KHÔNG kéo giãn. App tự tính crop theo vị trí mặt; check chặn crop làm mất khung mặt.
  Đoạn có sản phẩm/tay/chi tiết kiến trúc đang nói tới mà không có mặt → tự đặt `cx/cy` và xem `stills`.
- Lệch tỷ lệ mạnh (giữ < 50% khung nguồn, vd footage dọc cho bản ngang): app mặc định **bố cục chứa trọn footage** (`fit: "blur"` — hình đầy đủ ở giữa,
  hai bên là chính hình đó làm mờ). Ưu tiên cảnh thay thế đúng tỷ lệ nếu có.
- Tính lại chữ, vùng an toàn, vị trí PiP cho từng tỷ lệ (app tự làm). Hai tỷ lệ của cùng một bản dựng giữ cùng mạch lời và thời lượng;
  bản rút gọn là yêu cầu riêng.
- `formats` trong plan_ready.json quyết định app xuất tỷ lệ nào (“chỉ dọc”, “chỉ ngang”, mặc định cả hai).
