# Làm sạch voice và tốc độ (dùng chung bộ “Cắt sạch” của Talking Head)

## Mặc định

Sau `init` (chép lời), chạy `clean` trước khi lập timeline:

```
.venv/bin/python -m thagent.v2m clean <dự-án> [--no-denoise]
```

Cắt (đo bằng sóng âm thật, như Talking Head): nói vấp/lắp bắp lặp liền kề (“Đến… Đến”), từ đệm ừ/à/ờ, âm đệm không thành lời,
chữ kéo dài (“vớiii”), hiệu lệnh đếm (“2 3 diễn”), khoảng lặng thừa (giữ 0,3s giữa câu, 0,15s giữa từ), đầu/đuôi thừa;
lọc ồn theo độ to của chính file (tắt bằng `--no-denoise` nếu voice đã xử lý sẵn, vd ElevenLabs).

- Voice gốc giữ nguyên; bản cắt `voice_clean.wav`; `transcript.json` được dời mốc theo bản cắt (gốc lưu `transcript_raw.json`).
- **Không bỏ chữ nào** ngoài vấp/lặp/từ đệm do bộ Cắt sạch xác định; từ viết tắt in hoa (IPC, FED, USD…) không bị coi là “kéo dài”.
- Báo cáo `voice_edit.json`: từng chỗ cắt (giây, độ dài, lý do), thời lượng trước/sau, từ bị bỏ. Ghi tóm tắt vào báo cáo cuối.
- Timeline dùng `audio.path = "voice_clean.wav"`, `duration_s` = thời lượng sau cắt.

Người dùng nói **“giữ nguyên voice”** / “không cắt” → `restore <dự-án>` (bỏ cắt), dựng trên voice gốc.

## Tốc độ

“Tăng tốc 1.1”, “nhanh hơn chút” (≈ 1.1), “chậm lại” (≈ 0.9):

```
.venv/bin/python -m thagent.v2m speed <dự-án> 1.1      # 0.8–1.5; 1 = gốc
```

Áp lúc xuất cho mọi định dạng (hình + tiếng cùng lúc, giọng giữ cao độ — như Talking Head); **không** đổi timing chữ/hình
trong timeline. QA quy thời lượng về voice khi kiểm. Đây là tính năng có sẵn — không trả lời là không làm được.
