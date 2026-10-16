# Renderer `thagent.v2m` — lệnh và component

Renderer chạy trong app C-Cut / repo Agent Talking Head (Python, `.venv/bin/python`). Mọi frame là hàm thuần của timeline.

## Lệnh

```
.venv/bin/python -m thagent.v2m init   <âm thanh|video> <dự-án> âm thanh: chép nguyên; video: chỉ tách tiếng → voice.wav; ASR từng từ → transcript.json
.venv/bin/python -m thagent.v2m clean  <dự-án> [--no-denoise]   cắt vấp/lắp bắp/từ đệm/khoảng lặng (Cắt sạch của Talking Head) → voice_clean.wav
.venv/bin/python -m thagent.v2m restore <dự-án>                 dùng lại voice gốc
.venv/bin/python -m thagent.v2m speed  <dự-án> 1.1              tốc độ xuất 0.8–1.5, giọng giữ cao độ
.venv/bin/python -m thagent.v2m words  <dự-án> [t0 t1]          từ + giây
.venv/bin/python -m thagent.v2m check  <dự-án> [--deep]         QA tĩnh; --deep dựng frame mẫu 0,2s (không mã hoá) để bắt chồng chữ/cắt khung
.venv/bin/python -m thagent.v2m stills <dự-án> t1 t2 …          ảnh tĩnh → stills.jpg
.venv/bin/python -m thagent.v2m render <dự-án> [9x16|16x9|both] dựng + trộn âm + QA → versions/vNNN/{video[_fmt].mp4, qa[_fmt].json, sheet[_fmt].jpg} + <id>_<fmt>.mp4
.venv/bin/python -m thagent.v2m revise <dự-án> '<json>'         sửa nhanh (text_scale, sfx_gain) → phiên bản mới
```

`render` từ chối dựng nếu QA tĩnh còn lỗi; sau dựng ghi `qa.json` với `status` (“đạt kiểm tra tự động” / “CHƯA ĐẠT…”).

## Timeline (tóm tắt)

`timeline.json`: `audio{path,duration_s}`, `canvas{width,height,fps}`, `theme{bg,bg2,glow,text,muted,accent,alt,deco,drift}`,
`camera[]` + `scenes[]{id,start_s,end_s,voice_span,purpose,visual_type,objects[],events[],camera[],audio_events[],transition_in,bg}`.

Event: `{object_id, action: reveal|hide|animate|draw|count|pulse, start_s, end_s, style, to{}, ease}`.
SFX: `audio_events: [{t, role: whoosh|swish|click|pop|tick|impact|flash|transition|success|money|paper|write|camera|typing|data, gain_db?}]` (kho `assets/sfx_v2m`, đỉnh âm đặt đúng `t`); `theme.sfx_auto` (mặc định bật) tự sinh SFX theo chuyển động.
Camera key: `{t, x, y, zoom, rot, dur, ease}` — tới vị trí lúc `t`, đi trong `dur` giây trước đó.

Thuộc tính chung của object: `id, type, x, y, scale, rot, opacity, layer, space: world|screen, parent, persist, until_s, fixed, lod`.

## Component

| type | Thuộc tính chính |
|---|---|
| `text` | `inside{iso | src,name}, min_size` (tên lãnh thổ nằm trong lãnh thổ), `color: "auto"`, `text, font, size, color, max_w, keep[], allow_orphan, align, anchor, line_h, word_times[], word_style, word_dur, highlight{match/words,color,t,punch}, marker{match,t,dur,color,mode}, plate("auto"/màu), plate_pad, upper` |
| `rect` / `circle` | `w,h,r / r, fill, fill2, stroke, stroke_w, shadow` (animate w/h/r để thẻ mở thành cảnh) |
| `image` / `video` | `src, w, h, r, fit, shadow, label, source` (nguồn bắt buộc với ảnh thật) |
| `icon` | `name` (Uicons solid-rounded), `size, color, bg, bg_r, ring, label, label_size` |
| `line` | `from/to` (id hoặc [x,y]) hoặc `points`, `bend, width, color, dash, arrow, progress, trim_start/end, fixed` |
| `list` | `items[{text,t}], style: dot|pill, size, gap` |
| `counter` / `progress` / `bars` | số chạy / thanh % / cột — **chỉ dùng với số liệu có nguồn** |
| `quote` | khung trích dẫn có tô câu + nguồn |
| `figure` | nhân vật minh họa: `h, color, poses[{t,pose,dur}]` hoặc `cycle{poses[],period,t0,t1}`; tư thế: stand, arms_up, arms_side, arms_front, squat, lean_left, lean_right, breathe_in, breathe_out, step |
| `pulse` | nhịp giãn–thu: `r_min, r_max, period, t0, rings, color, labels["hít vào","thở ra"]` |
| `flow` | luồng khí/tia sáng: `kind: air|light, w, h, angle, n, speed, color` |
| `stack` | khoản cộng dồn (khối cao bằng nhau): `items[{text,t,color}], w, item_h` |
| `map` / `region` | bản đồ thế giới / tô quốc gia (ISO3; VNM kèm Hoàng Sa, Trường Sa) |
| `geo` | ranh giới GeoJSON: `src[], fill, fill_by{tên: màu}, stroke` |
| `geoline` | tuyến GeoJSON: `src, feature, progress, color, width, head, dash, glow, reverse` |
| `routelabel` | nhãn gắn tuyến: `src, feature, at, offset, text, color, size, keep` |

Định dạng: `canvas{width,height,fps,format}`; `thagent.v2m.layout.Frame("9x16"|"16x9")` cho vùng `safe/title/text/main/map/full/caption/source`, `F.width()`, `F.center()`, `F.fit_geo(lon0,lat0,lon1,lat1,region,t,dur)` → camera key.

Hàm hỗ trợ khi viết timeline: `from thagent.v2m.render import geo_xy` (kinh/vĩ → toạ độ thế giới), `thagent.v2m.vtext.break_lines` (xem trước cách ngắt dòng).
