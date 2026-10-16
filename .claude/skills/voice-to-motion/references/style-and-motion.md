# Phong cách và thư viện chuyển động

## Cơ sở quan sát

Bốn video do người dùng cung cấp đã được rà khung hình toàn thời lượng, xem sát chuyển cảnh và đối chiếu ASR. Timestamp dưới đây xấp xỉ. Phân tích này mô tả kỹ thuật hình ảnh, không xác minh nội dung kinh tế trong video. Không có xác nhận nghe trực tiếp SFX và không xác định chắc chắn họ font gốc. Không phụ thuộc các file tham khảo phải còn tồn tại để vận hành skill.

| Mẫu | Mốc quan sát | Quy tắc rút ra |
| --- | --- | --- |
| Rehman, 21,57s | 0–2s: tiền quanh chữ đỏ; 3,2–4,2s: dải sáng/silhouette; 10,5–13,3s: nhãn xếp lần lượt; 13,5–14,5s: người vàng giữa đám đông; 19–21s: CTA nghiêng rồi ổn định | Text phân cấp mạnh, hình ẩn dụ, mảng nền và nhóm đối tượng cùng chuyển động. |
| Danush, 18,26s | 0,4–1s: thẻ chữ “problem?”; 1,15–1,75s: thẻ tăng chiều cao thành khung người; 2,6–3,5s: đổi thẻ với blur; 4,4–10,5s: kéo dài danh sách | Giữ đối tượng xuyên cảnh, biến đổi shape, dựng danh sách theo voice, dùng khoảng trống chủ đích. |
| Người Quan Sát, “ba không”, 221,54s | 11–14s: trích báo/highlight; 15–19s: cá nhân thành tập hợp trên bản đồ; 43–54s: nhánh nguyên nhân và bố cục kỳ vọng/thực tế; 98–150s: biểu đồ và luận điểm | Giải thích bằng quan hệ, camera theo nhánh, dẫn chứng nổi đúng phần, giữ điểm tham chiếu. |
| Người Quan Sát, Antex, 231,13s | 8–19s: trích dẫn → logo → vòng tròn → nhánh; 55–74s: nút và luồng vận hành; 110–123s: đường dẫn mắt và chữ kết luận | Cảnh mở rộng từng bước, đường đi có ý nghĩa, camera giữ người xem theo được cấu trúc. |

Hai mẫu Người Quan Sát có người dẫn ở cuối. Đây là đặc điểm tham khảo, không là yêu cầu thêm người vào video voice-only.

## Ba bộ bố cục

1. **Giải thích thông tin:** nền tối hoặc trung tính; một chủ thể chính; nhánh quan hệ, nguồn trích dẫn; màu nhấn thống nhất. Dùng cho thân bài.
2. **Typography và hình ảnh ẩn dụ:** cụm chữ trung tâm hoặc lệch có chủ đích; từ khóa lớn; ảnh cắt nền/biểu tượng minh họa. Dùng cho mở bài, luận điểm và kết.
3. **Thẻ và shape liên tục:** nền sáng, thẻ thông tin, đường nối; thẻ chữ phát triển thành khung ảnh hoặc bảng so sánh. Dùng khi ý này phát triển từ ý trước.

Đồng bộ palette/font giữa ba bộ. Không bê nguyên dấu trang trí, barcode, logo, watermark, nội dung hay nhận diện của tác giả. Bóng/độ nổi nhẹ là tùy chọn theo cảnh, không mặc định cấm hoặc bắt buộc.

## Thành phần cần có

- Thẻ chữ có mask reveal và trạng thái mở rộng thành khung hình.
- Cụm text dẫn/nhấn/nhãn/nguồn; text giữ vị trí tương đối với đối tượng.
- Ảnh cắt nền, khung ảnh, vùng che lớp trước/sau.
- Nút sơ đồ, nhánh, đường thẳng/cong, mũi tên và nhãn cạnh.
- Trích báo có vùng crop và highlight đúng dòng; nguồn luôn gắn với tài liệu.
- Bản đồ thật, điểm, ranh giới/tuyến đã kiểm chứng.
- Biểu đồ có trục, đơn vị, nguồn, trạng thái trước/sau; số chạy dừng đúng giá trị.
- Camera để pan/zoom/rotate nhóm cảnh, không làm nhãn mất khả năng đọc.

## Mặc định thiết kế thử nghiệm

Các giá trị dưới đây là điểm khởi đầu, không phải thông số đo từ video mẫu:
- Canvas 1080×1920; ưu tiên nội dung quan trọng trong x=80–920, y=160–1560 để tránh vùng UI. Điều chỉnh theo nền tảng khi được chỉ định.
- Headline khoảng 72–112px; chữ phụ 42–60px; nguồn 26–32px. Đo chiều rộng thực tế, kiểm tra ở kích thước màn hình điện thoại, không ép chữ quá nhỏ.
- Một điểm nhấn chính tại một thời điểm. Từ khóa thường 2–6 từ; chia theo cụm nghĩa, không phá tên riêng và đơn vị.
- Entrance khoảng 0,2–0,5s; chuyển góc nhìn khoảng 0,4–0,8s. Thay đổi theo nhịp voice và lượng thông tin.
- Bắt đầu gần từ neo, cho chuyển động kết thúc trước giai đoạn cần đọc. Giữ chữ theo khả năng đọc, không khóa mọi cảnh vào cùng số giây.
- Dùng easing tăng/giảm tốc; overshoot nhỏ nếu hợp mood. Không bounce tất cả đối tượng, không đổi zoom ở mọi câu.
- Vẽ đường theo hướng quan hệ, sau đó hiện nút/nhãn đích; tránh cho mọi nhánh xuất hiện cùng lúc.
- Khi đổi chủ thể, ưu tiên di chuyển/cải biến thành phần liên quan hoặc dùng màu/shape chung nối cảnh.

## Ví dụ chuỗi hành động

Voice nêu “vị trí, không gian sống, tổng chi phí”: hiện căn hộ trung tâm → mở ba nhánh theo thứ tự → camera tập trung nhánh vị trí → hiện biểu tượng điểm đi hằng ngày → trở lại nhánh không gian → mở hình phòng và ánh sáng → nhánh chi phí mở thành nhóm khoản mục → thu lại tổng thể để kết luận. Nếu không có dự án thật, dùng sơ đồ khái niệm và biểu tượng trung tính, không dựng bản đồ địa lý giả.
