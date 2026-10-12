# Talking Head Agent — MVP v0.1 (Bất động sản, tiếng Việt)

App cục bộ dựng video Talking Head: nhập video → ASR theo từ → cắt dựng thô → text/motion/SFX
→ tách nhân vật động (text sau đầu / trước ngực) → zoom, lóe sáng → QA → xuất MP4.

## Cài & chạy

Yêu cầu: macOS, Python 3.11, FFmpeg/ffprobe trong PATH (đã kiểm tra: FFmpeg 9.0.2).

```bash
./run.sh            # tạo .venv nếu chưa có, mở UI tại http://127.0.0.1:8765
```

Model cần có (đã tải sẵn trong máy này):
- `models/rvm_mobilenetv3_fp32.onnx` — Robust Video Matting (GPL-3.0, dùng nội bộ).
- faster-whisper `large-v3` (tự tải về `~/.cache/huggingface` lần đầu, ~3 GB).

Font (OFL, hỗ trợ tiếng Việt) trong `assets/fonts/`: Be Vietnam Pro (body/số),
Playfair Display Italic (nhấn), Dancing Script (trang trí). Đây là **font thay thế** cho
SF Pro Display / Playfair Display Italic / Whisper thấy trong video mẫu. Đổi trong
`thagent/typography.py → FONT_ROLES`.

### Planner Claude (tùy chọn)
Chưa có `ANTHROPIC_API_KEY` → planner chạy chế độ **heuristic** (quy tắc, gắn nhãn trong
plan.json). Để bật: `export ANTHROPIC_API_KEY=...` rồi `pip install anthropic`. Chỉ transcript
dạng văn bản được gửi, không gửi video.

## Dùng CLI

```bash
.venv/bin/python -m thagent.cli demo --source /đường/dẫn/video.MOV --test 0 750   # đoạn thử 25s
.venv/bin/python -m thagent.cli demo --full                                        # toàn bộ
```

## Luồng & module

```
ingest (probe, proxy SDR 1080x1920@30, HDR→SDR tonemap)
  → transcribe (faster-whisper, word timestamps, cờ kiểm tra số/độ tin cậy thấp)
  → matting (RVM hồi quy theo thời gian → alpha.mp4 + neo mặt/đỉnh đầu MediaPipe)
  → planner (cắt lặng/lặp, Hook/CTA, nhóm text, SFX, zoom/flash, nhu cầu tư liệu)
  → render (rough cut ffmpeg → compositor theo frame → mix + loudnorm → mux)
  → qa (kích thước/fps/độ dài/AV/loudness/true peak/thời gian đọc/tư liệu thiếu)
```

Thứ tự lớp: `video gốc → text vùng đầu → nhân vật (alpha) → text vùng ngực → light wash`.
Nhân vật = chính pixel video gốc × alpha cùng frame, cùng transform zoom → không lệch.

Timeline: `thagent/timeline.py` là nơi duy nhất ánh xạ nguồn ↔ timeline (`[start,end)` frame).
Mọi text/SFX/FX tính theo frame timeline sau cắt.

Schema: `thagent/schema.py` (Pydantic, `schema_version`). Mỗi lần render lưu
`projects/<id>/renders/vNNN_<label>/{mp4, plan.json, qa.json, snap_*.jpg}`.

## Sửa & render lại
UI tab “Preview & chỉnh”: bật/tắt nhóm text (SFX liên kết tắt theo), sửa chữ, đổi lớp
sau/trước người, đổi/mute SFX, gain, cường độ zoom/flash; tab “Phân tích” bật/tắt đoạn cắt.
Hoặc sửa `projects/<id>/project.json → plan` rồi render lại.

## SFX
`assets/sfx/*.wav` hiện là **âm tổng hợp tạm** (procedural) để kiểm tra đồng bộ — chưa
phải chất lượng sản xuất. Thay bằng WAV có quyền dùng cùng tên, `peak_offset_ms` được đo lại
tự động (`thagent/sfx.py`).

## Lỗi thường gặp
- Job “failed”: xem log trong UI; chạy lại bước lỗi — các bước trước có checkpoint.
- Thiếu tư liệu dự án/bản đồ: QA báo `missing_asset`; tải ảnh thật vào vai trò `project_asset`.
- Mask kém (viền tóc/tay): xem `snap_*.jpg`, đổi lớp text sang “trước người” hoặc dời vị trí.
