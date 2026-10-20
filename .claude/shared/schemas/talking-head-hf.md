# plan.hf — lớp HyperFrames trong Talking Head

(Tự sinh từ thagent/th_hf.py — không sửa tay.)

```
Talking Head × HyperFrames (công cụ dựng dùng chung thagent.hyper): text nhấn, tiêu đề, phụ đề thiết kế, overlay.

plan.hf = [{"id": "cap1", "start": <frame timeline>, "end": <frame>, "layer": "front" | "behind_subject",
            "spec": {"layers": [ … chuẩn thagent/hyper/spec.py, giây tính từ start … ]}}]
- Kích thước/fps/thời lượng lấy từ plan (không ghi trong spec). Mỗi mục render MỘT clip mov có alpha (lưu đệm theo mã băm).
- Ghép trong render.composite: "behind_subject" vào lớp SAU nhân vật (alpha người vẫn đè lên — giữ quy tắc chữ sau đầu),
  "front" vào lớp trước; vẽ trước chữ/thẻ của Talking Head trong cùng lớp. Logic cắt lời/biên tập không đổi.
- Phụ đề theo lời: words_tl(pid, start_f, end_f) → [(chữ, giây tính từ start)] theo timeline ĐÃ cắt (đúng mapping nguồn→timeline).
- HyperFrames chưa sẵn sàng: plan.hf không có phương án tương đương trong bộ vẽ Talking Head → preflight báo LỖI (bị chặn), không âm thầm bỏ.
```
