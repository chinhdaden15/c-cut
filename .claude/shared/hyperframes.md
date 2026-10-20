# HyperFrames trong C-Cut — hướng dẫn chung cho mọi skill video

App cài HyperFrames ở cấp app (runtime ghim phiên bản `assets/hyperframes/package.json`, cài vào `tools/hyperframes`).
Skill KHÔNG chứa runtime hay tài liệu HyperFrames — chỉ gọi qua lớp chung `thagent.hyper`.

## Khi nào dùng

Cân nhắc HyperFrames cho: text motion, tiêu đề, phụ đề thiết kế, callout/nhãn, overlay; sơ đồ, biểu đồ, bảng; composition ghép
ảnh + video + đồ hoạ; đoạn đồ hoạ tái sử dụng. Giữ công cụ của app cho: ASR/căn thời gian lời, cắt lời/khoảng nghỉ/âm thanh,
tracking, tách nền, voice/ảnh/video AI, dữ liệu địa lý — HyperFrames nhận KẾT QUẢ các bước đó.

**Ai sở hữu timeline cuối**: bộ dựng của skill (Talking Head / v2m / Review…). HyperFrames render đúng lớp hoặc đoạn cần thành
clip `mov` có alpha (hoặc `mp4` khi là đoạn hoàn chỉnh) — không render cả video hai lần.

## Lệnh

```
.venv/bin/python -m thagent.hyper doctor                     sẵn sàng? (Node ≥22, bản ghim, ffmpeg, Chrome)
.venv/bin/python -m thagent.hyper validate <spec.json>       kiểm spec, không dựng
.venv/bin/python -m thagent.hyper stills   <spec.json> 0.5 1.8   ảnh khung (Read để xem) — trước khi render
.venv/bin/python -m thagent.hyper render   <spec.json>        kiểm → lint → check trình duyệt → render → kiểm file; in state JSON
.venv/bin/python -m thagent.hyper status|cancel <thư_mục_job>
```

Mỗi job có thư mục riêng (`hf_jobs/<job_id>/`: project/, state.json, render.log, lint.json, check.json). Nội dung không đổi →
dùng lại kết quả. Lỗi spec/lint/check → không render, sửa spec rồi chạy lại. Render lỗi tạm thời thử lại tối đa 2 lần.

## Spec (tóm tắt — đầy đủ ở `.claude/shared/schemas/hyperframes-spec.md`)

```json
{"job_id": "rv-9x16-spot-01", "width": 1080, "height": 1920, "fps": 30, "duration": 3.2, "background": "transparent",
 "output": {"path": "hf/spot.mov", "format": "mov"},
 "layers": [
  {"type": "spotlight", "start": 0.2, "duration": 2.8, "dim": 0.32, "track": [{"t": 0, "x": 310, "y": 820, "w": 300, "h": 260}, …]},
  {"type": "callout", "text": "Khăn giấy ướt", "target_track": [{"t": 0, "x": 460, "y": 950}, …], "start": 0.5, "duration": 2.4},
  {"type": "text", "text": "Mở hộp điện thoại", "font": "black", "size": 96, "stroke": 6, "x": "50%", "y": 300, "enter": {"type": "pop"}}
 ]}
```

Loại lớp: text (kể cả phụ đề hiện từng từ theo `word_times`), image, video, shape, callout, spotlight, bars, table, html (lối thoát).
Toạ độ px hoặc "50%"; `keyframes`/`track` = vị trí THẬT theo thời gian (render bằng transform, không giật).
Font mặc định của app (Montserrat, Be Vietnam Pro — đủ dấu tiếng Việt), GSAP cục bộ (chạy không cần mạng).

## Quy tắc

- Spotlight/callout bám vật: lấy `track` từ dữ liệu tracking thật của skill; không có → không dựng (validate báo lỗi).
- Công cụ chưa sẵn sàng → phương án tương đương của skill; không có → báo rõ phần bị chặn. Không âm thầm bỏ hiệu ứng.
- Không nâng phiên bản HyperFrames trong job. Nâng = sửa `assets/hyperframes/package.json` + lock, chạy `python -m thagent.hyper selftest`.
- Skill HyperFrames chính thức cho agent (plugin) là tài liệu cho agent, KHÔNG thay runtime này; app không tự cài chúng.

## Điểm nối trong các skill hiện có

| Skill | Ghi ở đâu | Bộ dựng sở hữu timeline |
| --- | --- | --- |
| Talking Head | `plan.hf` (định dạng: `.claude/shared/schemas/talking-head-hf.md`), layer `front` / `behind_subject`; phụ đề: `python -m thagent.tools hfwords <pid> f0 f1` | render.composite (alpha người đè lớp sau) |
| Voice to Motion | object `{"type": "hf", "spec": {...}}` trong timeline_<fmt>.json | v2m renderer (camera, geo, nhịp) |
| Review | texts[] `"engine": "hyperframes"` / `edit.graphics_engine`; role `hf` | review render (track thật → spotlight/nhãn) |
| Skill mới | gọi `thagent.hyper` trực tiếp, hoặc tạo điểm nối riêng theo mẫu trên | skill tự quyết, ghi rõ trong SKILL.md |
