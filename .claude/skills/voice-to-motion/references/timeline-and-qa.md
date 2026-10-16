# Timeline, kiểm tra và chỉnh sửa

## Hợp đồng dữ liệu

Dùng giây từ đầu voice gốc làm thời gian chuẩn. Chuyển sang frame bằng fps dự án, xử lý làm tròn nhất quán. Lưu ít nhất:

```json
{
  "project_id": "example",
  "version": 1,
  "status": "planned",
  "audio": {"path": "voice.wav", "duration_s": 30.0, "preserve_timing": true},
  "canvas": {"width": 1080, "height": 1920, "fps": 30},
  "scenes": [{
    "id": "scene_001", "start_s": 0.0, "end_s": 4.0,
    "voice_span": "Câu nguyên văn trong transcript thực tế",
    "purpose": "Giới thiệu tiêu chí",
    "visual_type": "expanding-card",
    "initial_state": "Một thẻ chủ thể",
    "final_state": "Chủ thể và nhánh đầu tiên",
    "objects": [{"id": "card_01", "type": "shape", "asset_id": null}],
    "events": [{"object_id": "card_01", "start_s": 0.2, "end_s": 0.6,
                "action": "reveal", "voice_anchor": "Từ neo thực tế"}],
    "camera": [], "audio_events": [], "source_ids": []
  }],
  "assets": [], "qa": [], "limitations": []
}
```

Đây là cấu trúc minh họa; không coi thời gian hoặc câu mẫu là dữ liệu thực tế. Thêm vị trí/kích thước/anchor/layer/style/keyframe vào từng object để renderer tái lập được cảnh. Phân biệt thời gian tuyệt đối và tương đối nếu renderer dùng cả hai. Các scene không được vượt thời lượng voice, để hở frame hoặc ghi đè audio ngoài ý muốn.

Mỗi tài nguyên ghi id, file, loại, nguồn URL hoặc tên file người dùng, vai trò, trạng thái xác minh và quyền sử dụng. Mỗi audio event ghi file, thời điểm, gain, fade và quan hệ với visual event. Không dựng đường dẫn giả tới tài nguyên chưa tồn tại.

## Kiểm tra trước render

- Voice giải mã được; transcript/timing phù hợp; giữ nguyên thứ tự và nhịp gốc.
- Mọi file/font tham chiếu tồn tại; font hiển thị đủ dấu tiếng Việt.
- Số liệu và tên riêng đối chiếu tài liệu; báo cáo những mục chưa xác minh.
- Bố cục có chỗ cho các bước mở rộng; nguồn, nhãn, đơn vị không mất khi camera chạy.
- Mỗi sự kiện có mục đích; không dùng overlay che thông tin quan trọng.

## Kiểm tra sau render

- Xác nhận tiến trình render thành công, file có video/audio đúng codec, kích thước và fps.
- So sánh thời lượng với voice; chênh lệch đóng gói dự kiến không quá khoảng 0,1s. Nếu nhiều hơn, tìm nguyên nhân và sửa; không kéo voice cho khớp lỗi hình.
- Quét toàn video để phát hiện frame đen ngoài chủ ý, mất media, chữ vượt khung, đứng hình bất thường. Kiểm tra khung đầu/giữa/cuối mỗi cảnh và hai bên mọi chuyển cảnh.
- Kiểm tra cue hình/text với từ neo; mục tiêu chênh khoảng 0,1–0,15s cho điểm nhấn nếu hợp ngữ nghĩa. Cho phép hình đến sớm có chủ đích để chuẩn bị bối cảnh.
- Xem ở kích thước điện thoại: text đủ lớn, đủ thời gian đọc; nhòe phải hết lúc giữ chữ.
- Kiểm tra audio stream, peak/clipping, chồng SFX và nhạc. Nghe thực tế khi công cụ cho phép; ghi rõ giới hạn nếu không nghe được. Không nhận waveform/ASR là phép đo độ dễ chịu của mix.
- Sửa lỗi có bằng chứng, render lại phần liên quan và kiểm tra tiếp giáp. Giữ lịch sử phiên bản, không lặp vô hạn khi công cụ thất bại cố định.

## Bàn giao và sửa

Xuất final MP4, lưu nội bộ transcript/timeline/manifest/project để sửa. Trả báo cáo ngắn về phần thiếu nguồn, font thay thế, giới hạn kiểm tra âm thanh nếu có. Không yêu cầu duyệt trước final.

Với sửa cục bộ, xác định thời gian và object ID, giữ các cảnh khác cùng voice. Tạo phiên bản mới; kiểm tra lại toàn bộ ảnh hưởng trực tiếp, thời lượng và điểm nối. Nếu yêu cầu thay đổi thời lượng voice, làm rõ hoặc dùng quyền đã được người dùng cung cấp; không tự suy diễn từ “nhanh hơn” rằng được tăng tốc giọng.

## Vòng lặp tự kiểm tra (v1.1 — đã cài vào renderer)

1. `check <dự-án>` — QA tĩnh, không cần dựng:
   - `word_times` đủ mốc cho mọi từ, tăng dần;
   - ngắt dòng theo nghĩa: không vỡ cụm `keep`/tên riêng/số + đơn vị, không mồ côi;
   - mọi chữ có đủ thời gian đọc (≈ ký tự/14 giây); **câu kết** còn ≥ max(1,6s, ký tự/14) sau khi hoàn tất;
   - SFX: không quá dày (≤ 0,9/giây), không sát nhau < 120ms, không lặp một họ cho mọi sự kiện;
   - camera: vận tốc không đổi đột ngột (camera_jerk);
   - nhãn bản đồ có `lod`.
2. `check <dự-án> --deep` — dựng frame mẫu mỗi 0,2s (không mã hoá) và đo trên khung chữ/shape THẬT trong lúc animate:
   chữ chồng chữ, chữ vắt qua viền shape, chữ bị cắt khỏi khung, ra ngoài vùng an toàn, < 22px, tương phản thấp; + tất định (dựng lại cùng frame).
3. `render` — chạy lại các kiểm tra trên mẫu mỗi 6 frame của bản dựng thật, kiểm codec/kích thước/fps/thời lượng/đỉnh âm, ghi `qa.json` + `sheet.jpg`.
4. Xem lại bằng mắt: `sheet.jpg` (đầu/cuối mỗi cảnh) **và** ảnh liên tiếp quanh mỗi chuyển cảnh (`stills` các mốc cách nhau 0,1s) để thấy diễn tiến chuyển động; ảnh storyboard không đủ để kết luận animation.
5. Ghi lỗi → sửa timeline/component → dựng lại. Lặp tới khi hết lỗi chặn.

### Lỗi chặn bàn giao (QA `error` hoặc phát hiện khi xem)
- chữ chồng, bị cắt, hoặc từ xuất hiện lẻ do lỗi;
- ngắt dòng làm vỡ cụm nghĩa rõ ràng;
- nhãn bản đồ gắn sai tuyến;
- bịa hình học đường, số liệu hoặc thông tin;
- chuyển động giật do lỗi kỹ thuật;
- câu kết không đủ thời gian đọc;
- shape/chữ quan trọng không phân biệt được với nền (tương phản < 2:1).

Âm thanh: môi trường hiện tại không nghe trực tiếp được — báo cáo ghi rõ “chưa nghe đánh giá”, chỉ khẳng định các số đo kỹ thuật (đỉnh, clipping, độ dài).
