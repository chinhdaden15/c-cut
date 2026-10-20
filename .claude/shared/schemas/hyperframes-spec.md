# Spec job HyperFrames (dùng chung mọi skill)

(Tự sinh từ thagent/hyper/spec.py — không sửa tay.)

```
Chuẩn dữ liệu job HyperFrames của app (dùng chung mọi skill). Kiểm TRƯỚC khi dựng composition.

{
  "job_id": "rv-9x16-spot-01",                 # tuỳ chọn — thiếu thì app đặt theo mã băm nội dung
  "width": 1080, "height": 1920, "fps": 30, "duration": 3.2,
  "background": "transparent",                 # "transparent" (lớp phủ) | "#101010"
  "output": {"path": "…/spot.mov", "format": "mov", "quality": "looks"},
       # mov = ProRes 4444 CÓ alpha (lớp phủ ghép vào bộ dựng của skill) | webm (VP9 alpha) | mp4 (đoạn hoàn chỉnh) | png-sequence
  "fonts": [{"family": "Montserrat", "file": "assets/fonts/Montserrat-VF.ttf", "weight": "100 900"}],   # mặc định: font app
  "audio": [{"src": "voice.wav", "start": 0, "volume": 1}],            # chỉ khi xuất đoạn hoàn chỉnh (mp4)
  "scenes": [{"id": "s1", "start": 0, "duration": 3.2, "layers": [ … ]}]   # hoặc "layers" ở gốc = 1 cảnh
}

Lớp (mọi lớp): id, type, start, duration (giây, tính trong cảnh), x, y (điểm neo; px hoặc "50%"), anchor (center|top-left|…),
  w, h, z, opacity, style {css}, enter {type: fade|up|down|left|right|pop|wipe|none, dur, ease}, exit {type, dur},
  keyframes [{t, x, y, w, h, opacity, scale}]  (t tính từ đầu lớp — vị trí THẬT theo thời gian, vd dữ liệu bám vật).
Loại:
  text      text, font (black|display|bold|semi|medium|body|body_bold), size, color, stroke, stroke_color, align, max_w,
            line_h, bg, pad, radius, highlight [{match, color}], reveal "words" + word_times [giây] + active_color (phụ đề theo lời)
  image     src, fit (cover|contain), radius, border
  video     src, in (giây nguồn), muted (mặc định true), fit
  shape     shape (rect|circle|line), fill, stroke, stroke_w, radius
  callout   text, target {x, y} hoặc target_track [{t, x, y}] (điểm bám thật), side (left|right|top|bottom), gap, dot
  spotlight track [{t, x, y, w, h}] BẮT BUỘC (vị trí thật theo thời gian — từ tracking), dim 0.25–0.4, radius, pad, feather
            (không có dữ liệu bám → lỗi; khung cố định chỉ khi ghi rõ "static_reason")
  bars      items [{label, value}], unit, max, color, label_color
  table     title, cols [A, B], rows [[nhãn, a, b]], win [1|2|0…]
  html      html, css, js (đoạn GSAP dùng biến `tl` và `sel` = selector gốc của lớp) — lối thoát cho hiệu ứng riêng
```
