# Ca kiểm tra từ 5 video thử (v1.0) — nguyên nhân thật và cách xử lý trong v1.1

Đã mở lại timeline/source từng bản để xác định nguyên nhân; các lỗi KHÔNG chung một gốc.

| Video | Lỗi quan sát | Nguyên nhân trong source | Cách xử lý (v1.1) |
|---|---|---|---|
| Chọn căn hộ (12–16s) | sơ đồ bị cắt; “KHÔNG GIAN SỐNG” chạm viền hộp | thiết kế: camera zoom 1,15× **cả sơ đồ** thay vì dựng lại nhánh; nhãn icon đặt cố định `bg_r+40` dưới nút, hộp “căn phòng” đặt ngay dưới mà không đo khung nhãn | quy tắc “nhánh → cảnh chi tiết” (layout-typography §1); QA khung chữ ghi lỗi “chữ vắt qua viền shape” trong lúc animate |
| Chọn căn hộ | ánh sáng, thông thoáng, chi phí chỉ là icon | thiếu component hành động | `flow` (light/air), `stack` (cộng dồn, không số) |
| Cá độ | nhãn “VÒNG LẶP” nhỏ | cỡ 70 trong vòng bán kính 300 với 4 nút → trọng tâm yếu | hệ thống cỡ chữ (headline 84–130), quy tắc một trọng tâm/cảnh |
| Cá độ | hai cột cao/thấp gợi tỷ lệ không có dữ liệu | dùng `rect` cao khác nhau làm ẩn dụ | cấm biểu đồ định lượng khi không có số (contrast-shape-illustration §2) |
| Cá độ (26–28,5s) | câu kết rõ quá muộn | reveal neo vào từ “không” (26,98s), voice hết 28,44s → còn 1,46s | QA tĩnh: câu kết phải còn ≥ max(1,6s, ký tự/14) |
| Giao thông (35–39s) | tên tuyến, nút giao, địa danh chồng nhau | nhãn `fixed` đặt bằng độ lệch px cố định cạnh pin, không kiểm tra va chạm; nhãn cảnh trước còn hiện | `routelabel` gắn tuyến + đường dẫn; QA va chạm chữ–chữ trong lúc animate; LOD ẩn nhãn phụ |
| Giao thông | khó phân biệt hai tuyến phía đông | cùng họ màu cyan, cùng nét liền | quy tắc ≥ 2 thuộc tính khác nhau (màu + nét đứt `dash`); tuyến cũ giảm nhấn `opacity 0,45` |
| Giao thông | nhãn tuyến không rõ gắn đường nào | nhãn chữ tự do đặt theo toạ độ địa lý gần tuyến | `routelabel` (chấm neo trên tuyến + đường dẫn cùng màu) |
| Giao thông | chú giải cuối quá nhỏ | 26px, không hộp | chú giải ≥ 30px trong `plate`, mẫu nét |
| Giá vàng | sơ đồ FED/USD/lợi suất/vàng như vòng | 4 nút xếp thoi, mũi tên chéo → đọc như chu trình | cấm vòng khi quan hệ không phải vòng; cây/dòng chảy một chiều |
| Giá vàng | hộp tối trên bản đồ tối | `plate` cố định #0E1622 trên biển #0A1019 (tương phản ~1,1:1) | `plate: "auto"` + backdrop + viền; QA đo tương phản trên nền thật |
| Giá vàng (cảnh cuối) | nhãn chi tiết vẫn hiện khi zoom ra | nhãn `fixed` không có mức chi tiết | `lod` với fade theo zoom; nhãn Hoàng Sa – Trường Sa ẩn ở mức châu lục/thế giới (điểm đảo vẫn vẽ) |
| Dưỡng sinh | nhịp thở, động tác là icon tĩnh | thiếu component | `pulse` (giãn–thu liên tục, nhãn hít vào/thở ra), `figure` đổi tư thế |
| Dưỡng sinh | chữ nhỏ trên nền gần trống | cỡ 32–40px cho nội dung chính, vùng minh họa bỏ trống | hệ thống cỡ chữ; quy tắc nội dung chính ≥ 55% vùng minh họa |
| Dưỡng sinh (63–67s) | “trình”, “chào” xuất hiện rời rạc | **lỗi dữ liệu + renderer**: “chào đón bạn trong hành trình” có 6 từ nhưng 5 mốc → renderer coi từ thiếu mốc là hiện ngay | renderer: từ thiếu mốc lấy mốc kế tiếp (không bao giờ hiện sớm); QA tĩnh báo lỗi khi số mốc ≠ số từ |
| Dưỡng sinh | tin nhắn “cảm nhận” có avatar như khách thật | trình bày lời quảng bá như lời chứng thực | quy tắc không trình bày như chứng thực của khách hàng thật |
| Chung | khựng/đơ một số đoạn | (1) nhiều đoạn chờ element lần lượt hiện, không có hành động; (2) “drift” giả tạo chuyển động; (3) camera có thể nhảy nếu key chồng thời gian | bỏ drift mặc định; storyboard theo pha xuất hiện → hành động → tiếp nhận → chuyển; camera liên tục (bắt đầu từ vị trí thật, zoom log); QA camera_jerk |
| Chung | ngắt dòng vỡ cụm | tự xuống dòng theo chiều rộng ở cỡ đã lượng tử hoá → có thể đổi chỗ ngắt khi zoom | `vtext.break_lines` ngắt theo nghĩa ở cỡ gốc, chốt trước animate |
