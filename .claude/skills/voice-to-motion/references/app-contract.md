# Hợp đồng khi xây app thực thi skill

Chỉ dùng khi người dùng yêu cầu xây app. Không coi việc tạo skill là hoàn thành một ứng dụng.

## Giai đoạn 1

Nhận voice thu sẵn và tài nguyên tùy chọn, chạy không có cổng duyệt:
queued → inspecting → transcribing → planning → sourcing → composing → rendering → checking → completed.

Có trạng thái failed/cancelled và thông báo lỗi cụ thể. Preview nội bộ không là bước bắt người dùng duyệt. UI cần upload voice, thêm tài nguyên, trạng thái tiến độ, preview final, tải MP4 và ô yêu cầu sửa theo câu tự nhiên. Có thể xem storyboard nhưng không bắt buộc mở/duyệt để tiếp tục.

Tách các thành phần: media inspector, ASR/alignment, semantic planner, asset resolver, layout/motion composer, audio mixer, renderer, QA và revision manager. Dùng adapter cho công cụ/mô hình, không viết cứng provider hoặc API chưa kiểm tra tài liệu hiện hành.

Lưu audio gốc bất biến, bản transcript, scene/object ID, asset provenance, timeline, phiên bản và kết quả QA. Dùng job id/checkpoint để tiếp tục hoặc retry bước lỗi; không chạy lại toàn bộ và tính phí lặp khi job cũ còn chưa rõ trạng thái.

## Tiêu chí nghiệm thu

- Với voice khoảng 30s: xuất MP4 có nội dung đúng, cùng nhịp và thứ tự, không cần thao tác duyệt giữa chừng.
- Ít nhất một cảnh có bố cục phát triển theo voice và một chuyển cảnh có quan hệ giữa đối tượng; không chỉ slideshow và phụ đề.
- Chữ tiếng Việt rõ, đường nối có ý nghĩa, không tạo dữ kiện dự án giả khi thiếu tài nguyên.
- Sửa “tăng chữ 15–20s” hoặc “giảm SFX” tạo phiên bản mới, giữ nội dung ngoài phạm vi yêu cầu.
- Pipeline báo trung thực lỗi, tài nguyên thiếu và giới hạn QA. Các tính năng chưa triển khai không được báo là hoạt động.
- Kiểm tra bằng voice thực tế; không coi mock UI hoặc file JSON là kết quả video đạt nghiệm thu.

## Giai đoạn 2

Bổ sung đầu vào kịch bản → tạo voice được người dùng lựa chọn/cho phép → đo thời lượng → dùng lại toàn bộ pipeline giai đoạn 1. Không triển khai TTS hoặc cloning giọng như mặc định của giai đoạn 1.
