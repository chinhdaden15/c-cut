# Sound design — kho SFX của Voice to Motion

## Kho (`assets/sfx_v2m/`, manifest `manifest.json`)

Âm thật lấy từ thư viện SFX của người dùng (`Documents/Chính Dùng/SFX`, cùng nguồn với Talking Head), đã: bỏ lặng đầu, cắt độ dài,
fade đuôi, chuẩn đỉnh −3 dBFS, đo `peak_ms` (renderer đặt **đỉnh âm đúng khung hành động**). Dựng lại kho:
`.venv/bin/python -c "from thagent.v2m import sfxkit; sfxkit.build()"` (khi người dùng thêm/đổi âm trong thư viện, sửa bảng `KIT` trong `thagent/v2m/sfxkit.py`).

| Vai trò | Dùng khi | Gain mặc định |
|---|---|---|
| `whoosh` | camera đi xa, chuyển vùng | −17 dB |
| `swish` | vật trượt vào, tuyến bắt đầu vẽ | −19 dB |
| `click` | pin, callout, điểm đến | −15 dB |
| `pop` | thẻ, nút, shape xuất hiện | −16 dB |
| `tick` | liệt kê, từng mục | −14 dB |
| `impact` | thông điệp chính, câu kết | −13 dB |
| `flash` | tiêu đề lớn, đảo nền | −14 dB |
| `transition` | đổi chương, chuyển cảnh phủ | −16 dB |
| `success` | hoàn tất, dấu ✓ | −16 dB |
| `money` · `paper` · `write` · `camera` · `typing` · `data` | tiền/giá · trích dẫn · gạch chân/marker · ảnh · chữ gõ · bản đồ/biểu đồ | −15…−18 dB |

## Cách dùng trong timeline

- **Tự động (mặc định, `theme.sfx_auto: true`)**: renderer sinh SFX từ chuyển động thật của TỪNG bản (dọc/ngang):
  camera chuyển vùng → `whoosh`; callout/nhãn tuyến → `click`; tiêu đề lớn → `flash` (cảnh cuối → `impact`); thẻ/icon/shape → `pop`;
  ảnh → `camera`; trích dẫn → `paper`; mục danh sách → `tick`; tuyến bắt đầu vẽ → `swish`; marker → `write`; chuyển cảnh phủ → `transition`.
  Lọc: cách nhau ≥ 0,25s, âm nhẹ ≤ ~1/giây, ưu tiên impact/flash/whoosh; xoay vòng âm trong vai trò (không lặp một âm liên tục).
- **Khai báo tay** khi cần ý đồ riêng: `audio_events: [{"t": 12.4, "role": "money"}]` (hoặc `"sfx": "role:money"`, `"gain_db"` để chỉnh).
  SFX tay được ưu tiên: SFX tự động trong ±0,3s quanh nó bị bỏ. Tên âm cũ của `assets/sfx` vẫn dùng được (`"sfx": "pop_03"`).
- Tắt hẳn SFX tự động: `theme.sfx_auto: false`.

## Quy tắc

- Voice là lớp ưu tiên (trộn `normalize=0`, chặn đỉnh chỉ khi mix vượt −1 dBFS). Nhạc nền (nếu có) thấp hơn voice ≥ 18 dB, ducking sidechain.
- SFX gắn vào thời điểm **nhấn thị giác**, không cho mọi từ. QA tĩnh cảnh báo: mật độ > 0,9/giây, hai SFX < 120ms, một họ âm > 45% sự kiện.
- Môi trường hiện tại không nghe trực tiếp được → báo rõ “chưa nghe đánh giá”, chỉ khẳng định số đo kỹ thuật (đỉnh, clipping, độ dài).
