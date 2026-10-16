# Tương phản, shape và minh họa theo nội dung

## 1. Tương phản và shape

- Shape phải tách khỏi nền bằng ít nhất một trong: độ sáng chênh rõ, độ đục cao, viền sáng 1,5–2px, hoặc làm tối nền phía sau.
- Nhãn bản đồ thường là chữ trơn (xem maps.md §3b). `plate: "auto"` dành cho chữ dài/câu trên nền bận (tiêu đề phụ đè lên bản đồ): renderer đo màu nền thật phía sau khối chữ và **đảo tương phản**: nền tối → hộp sáng (#F3F5F8) chữ tối; nền sáng → hộp tối chữ trắng; thêm viền (màu tuyến với nhãn tuyến) và làm tối mềm chi tiết bản đồ quanh chữ. Không dùng hộp tối trên nền tối (lỗi cũ: hộp #0E1622 trên biển #0A1019, rồi #0A0F17 trên bản đồ #182A3E — vẫn chìm).
- Đối tượng/tuyến đã giới thiệu được giảm nhấn ở **nét**, còn nhãn của nó vẫn giữ độ đọc ≥ 85% (`label_min_op`).
- Padding ≥ 0,35 × cỡ chữ; viền không cắt qua chữ.
- Tương phản tối thiểu (QA đo trên nền thật): chữ ≥ 40px → 3:1; chữ nhỏ → 4,5:1; dưới 2:1 là lỗi chặn. Chữ đỏ trên nền tối: dùng đỏ sáng (#FF5A52) hoặc đặt trong hộp.
- Hạn chế shadow dày, glow mạnh. Không biến mọi câu thành một hộp chữ — chỉ dùng shape khi giúp phân nhóm hoặc tăng khả năng đọc.

## 2. Minh họa theo loại ý (không mặc định một câu = một icon)

| Ý trong lời | Cách minh họa | Component |
|---|---|---|
| Hành trình | bản đồ + tuyến thật vẽ dần, camera bám | `geoline`, `routelabel`, camera |
| Hành động (vận động, tập, đi) | nhân vật minh họa đổi tư thế | `figure` (`poses` hoặc `cycle`) |
| Nhịp thở / chu kỳ | giãn – thu có nhịp, nhãn “hít vào / thở ra” | `pulse` (+ `figure` cycle breathe_in/out) |
| Ánh sáng, thông thoáng | tia sáng vào khung cửa, luồng khí đi qua | `flow` kind light / air trong một `rect` cửa |
| Nguyên nhân → kết quả | đối tượng A đổi trạng thái kéo theo B, mũi tên có hướng một chiều | `line arrow`, `animate` trạng thái |
| Chi phí / thành phần | từng khoản cộng dồn vào tổng thể, các khối **cao bằng nhau** | `stack` (không số) |
| So sánh | hai trạng thái cạnh nhau cùng thang | 2 thẻ/2 nhân vật/2 tuyến |
| Cảm xúc | nhịp, màu, typography | hiệu ứng chữ, khoảng dừng |

Ràng buộc:
- Sơ đồ mũi tên phải đúng quan hệ: **không xếp các nút thành vòng tròn** khi quan hệ không phải vòng lặp (lỗi cũ: FED → USD/lợi suất → vàng vẽ thành vòng). Dùng bố cục cây/dòng chảy trái→phải hoặc trên→dưới.
- Không dựng cột/thanh có chiều cao khác nhau khi không có số liệu (lỗi cũ: “nhà cái / người chơi”). Dùng ẩn dụ không định lượng (cán cân nghiêng, cánh cửa một chiều) hoặc chỉ typography.
- Lời giới thiệu/quảng bá trong voice **không trình bày như lời chứng thực của khách hàng thật** (không avatar, không bong bóng chat gắn người). Trình bày như ý chính của chương trình.
- Hình dự án, địa điểm, quy hoạch, bản đồ thật phải có nguồn; không tự tạo rồi trình bày như tài liệu thật.
