# Changelog — voice-to-motion

## 1.3.0
- Video b-roll ngoài: lệnh `broll` tải từ Pinterest (ưu tiên) hoặc Pexels, chuẩn hoá + ảnh xem trước để kiểm nội dung.
- Thư mục: mỗi file âm thanh/video = một video riêng, xuất dọc + ngang cho từng file; ảnh gốc + thư mục con = tư liệu dùng chung (`tu_lieu/`).
- Trên video chỉ ghi “Hình ảnh minh họa” / “Hình ảnh thực tế”, không ghi nguồn (nguồn vẫn lưu trong dự án).
- Ảnh minh họa + video b-roll: khối `photo`, `photos`, `before_after`, `photo_bg`, `photo_pin`; ảnh zoom/trượt chậm (Ken Burns); file .mp4/.mov tự thành khung video bo góc, thu nhỏ.
- Quy tắc ảnh ĐÚNG CHÍNH XÁC theo lĩnh vực, tự kiểm từng ảnh (`illus_check.json`), ảnh minh họa luôn ghi “Hình ảnh minh họa”, chủ thể có thật chỉ dùng ảnh thật.
- Thứ tự nguồn: thư mục người dùng → ảnh thật chủ thể → kho ảnh có giấy phép (Openverse/Unsplash/Pexels/Wikimedia).

## 1.2.3
- Tra icon: `python -m thagent.v2m icons <từ khóa>` (tiếng Anh/Việt) trong kho ≈3.500 icon của app; check báo icon sai kèm tên gợi ý.
- Nhịp theo lời: check chặn “hình đứng im > 3s” và “khung trống”; `K.beats()` gợi ý mốc từ khóa.
- Phụ đề chạy theo lời tự thêm (ngắt cụm theo dấu câu/chữ hoa đầu câu/chỗ ngừng), không chồng cụm.
- Khối sống sau khi hiện (`theme.idle`): trôi/giãn/lắc nhẹ, lệch pha.
- Khối mới: `spotlight`, `keyword`, `checklist`, `steps`, `street` (sơ đồ mặt đường cho BĐS); thẻ/icon/so sánh to hơn.
- SFX tự động đa dạng hơn: dấu tích → success, số liệu → data, nhãn/từ khóa → click; phụ đề không gắn SFX.

## 1.2.2
- Camera có diễn tiến: `s.story` (Establish → Focus → Resolve); kit tự thêm nhịp Explain (đẩy vào +6%, xoay ±2°) cho cảnh bản đồ đứng yên lâu; tự nối key không chồng nhau.
- Renderer giữ chữ/icon/callout luôn thẳng khi camera xoay.
- Lãnh thổ tô dần: viền vẽ dần → màu lan trong mask ranh giới thật (đủ polygon, đảo); `dim` giảm nhấn phần ngoài lãnh thổ; `s.focus`, `s.halo` (vòng gợn dẫn mắt).
- Màu quốc gia riêng, nhất quán (`K.color`); tên lãnh thổ trắng viền tối, nằm trên lớp tô, ẩn khi zoom ra.
- Cảnh không gắn vị trí: `s.backdrop()`, `K.map_until(t)`.
- Sửa lỗi hai Việt Nam ở bản ngang: chỉ vẽ một bản thế giới khi vòng thế giới hẹp hơn khung + `fit_geo` không lùi quá một vòng thế giới.
- Sửa lỗi đường nối trên màn hình bị phóng dày theo zoom bản đồ.

## 1.2.1
- Bộ khung dựng sẵn: `templates/build_timeline.py` + `thagent/v2m/kit.py` — khối tiêu đề, câu dẫn, nhãn, icon, thẻ, so sánh, số liệu, danh sách, thanh mức, biểu đồ, trích dẫn, ảnh, mũi tên; bản đồ: tô quốc gia, tên lãnh thổ (chữ trơn), pin, callout, tuyến, nhãn tuyến, camera theo vùng. Tự bố cục dọc/ngang, tự thu cỡ tiêu đề cho vừa cột, mốc lời bằng `K.find`, tự mờ ra cuối cảnh.
- App: Claude chép khung rồi chỉ điền nội dung; kiểm tra + ảnh tĩnh một lượt.

## 1.2.0 — 2026-10-16
- **Kho SFX riêng** `assets/sfx_v2m` (`thagent/v2m/sfxkit.py`): 38 âm thật từ thư viện SFX của người dùng (cùng nguồn Talking Head), 15 vai trò; chuẩn đỉnh −3 dBFS, đo `peak_ms` → đỉnh âm rơi đúng khung hành động.
- **SFX tự động** theo chuyển động thật của từng bản (dọc/ngang khác nhau theo camera của mình); SFX tay theo vai trò (`role`), ưu tiên hơn tự động; xoay vòng âm, giới hạn mật độ.
- **Đầu vào âm thanh hoặc video**: video chỉ lấy tiếng khi chọn Voice to Motion.

## 1.1.3 — 2026-10-16
- **Làm sạch voice như Talking Head** (`thagent/v2m/voiceprep.py`, dùng chung `thagent.cleancut`): `clean` cắt vấp/lắp bắp/từ đệm/âm kéo dài/khoảng lặng thừa + lọc ồn → `voice_clean.wav`, dời mốc từng từ, báo cáo `voice_edit.json`; từ viết tắt in hoa không bị cắt; không bỏ chữ ngoài vấp/lặp/từ đệm. `restore` để giữ nguyên voice.
- **Tốc độ**: `speed <dự-án> 1.1` (0.8–1.5) áp lúc xuất cho mọi định dạng, giọng giữ cao độ; QA quy đổi thời lượng.
- Thay đổi quy tắc “giữ nguyên voice” của 1.0: nay mặc định làm sạch (theo yêu cầu người dùng); giữ nguyên khi người dùng nói rõ.

## 1.1.2 — 2026-10-16
- Mặc định xuất **cả dọc lẫn ngang trong một lượt**: `render <dự-án>` dựng song song hai bản khi có `timeline_9x16.json` + `timeline_16x9.json`; “Dựng dọc”/“Dựng ngang” để chỉ một bản. Dự án cũ chỉ có `timeline.json` vẫn dựng như trước.
- Ảnh kiểm tra/sheet dùng lại renderer đã dựng (vị trí nhãn chỉ tính một lần) → bước QA sau dựng nhanh hơn ~20 phút với video bản đồ.

## 1.1.1 — 2026-10-16

**Dọc 9:16 và ngang 16:9** (`references/formats.md`).
- `thagent/v2m/layout.py` (mới): `Frame(fmt)` với vùng an toàn/tiêu đề/cột chữ/minh họa/bản đồ/chú thích riêng cho từng tỷ lệ; `fit_geo` tính camera để vùng địa lý nằm trọn trong vùng bố cục.
- Renderer không còn giả định 1080×1920: vùng an toàn, giới hạn đặt nhãn/callout, ảnh kiểm tra theo `canvas`; `canvas.format`.
- CLI: `render <dự-án> 9x16|16x9|both` dùng `timeline_<fmt>.json` riêng, xuất `<id>_<fmt>.mp4`, QA riêng từng bản; `check`/`stills` nhận định dạng. Dự án dọc cũ (`timeline.json`) không đổi.
- Ngắt dòng: chữ in hoa toàn bộ không còn bị coi là tên riêng; phạt dòng giữa chỉ một từ; QA không báo chỗ xuống dòng chủ động.

## 1.1.0 — 2026-10-15

Nâng cấp sau đánh giá 5 video thử (căn hộ, cá độ, giá vàng – bản đồ, giao thông miền Tây – miền Đông, dưỡng sinh).
Chi tiết nguyên nhân từng lỗi: `references/case-studies.md`.

**Tài liệu mới**: `layout-typography.md`, `motion-system.md`, `maps.md`, `contrast-shape-illustration.md`, `sound-design.md`,
`renderer-api.md`, `case-studies.md`. `SKILL.md` thêm quy tắc cứng v1.1 và vòng lặp QA; `timeline-and-qa.md` thêm vòng tự kiểm tra và lỗi chặn bàn giao.

**Renderer `thagent/v2m`**
- `vtext.py` (mới): ngắt dòng theo nghĩa tiếng Việt (giữ cụm, tên riêng, số + đơn vị, từ ghép; tránh mồ côi; ngắt ở cỡ gốc, chốt trước animate).
- Chữ: từ thiếu mốc không còn hiện sớm; hiệu ứng `word_style` (up/mask/fade/scale), `marker` chạy dưới/sau cụm, `highlight.t` đổi màu đúng thời điểm + `punch`; `plate: "auto"` (đo nền thật, backdrop làm tối bản đồ, viền).
- Camera: đoạn sau bắt đầu từ vị trí thật (không nhảy khi key chồng), zoom nội suy log; bỏ “drift” mặc định.
- Bản đồ: `lod` (fade theo zoom), `routelabel` (nhãn gắn hình học tuyến + đường dẫn), `geoline.dash`, lớp `geo` (GeoJSON hành chính), nhãn `fixed` lệch theo px màn hình.
- Minh họa: `figure` (nhân vật đổi tư thế / chu kỳ), `pulse` (nhịp thở), `flow` (luồng khí, tia sáng), `stack` (khoản cộng dồn không số).
- `callout` (theo video Bộ Callout tham khảo): dấu neo + thân mảnh + nhãn ở xa, `tag`/`plain`, tự tránh che tuyến (route_mask) và vùng tiêu đề; `routelabel` dùng callout. Nhãn bản đồ trở về chữ trơn (không hộp), chỉ thêm `lod`. Callout chỉ cho đối tượng nhỏ (đường, dự án, cầu, nút giao), không cho quốc gia/lãnh thổ/hải đảo. Điểm đảo Hoàng Sa, Trường Sa mờ dần khi zoom ra châu lục/thế giới (`islands_lod`).
- Quy tắc bắt buộc bản đồ: tên lãnh thổ nằm trọn trong lãnh thổ (`inside`, dò vị trí + xếp dòng + thu nhỏ tới 22px, không vừa thì ẩn; giữ màu trắng); vị trí nhãn/callout khoá một lần sau khi bỏ phiếu qua nhiều thời điểm (không xê dịch theo camera); chữ/shape/callout trên bản đồ giữ cỡ màn hình khi zoom (tự `fixed`).
- Tự tránh va chạm nhãn (`avoid`): thử vị trí quanh điểm neo, giữ ổn định qua frame, đường dẫn khi dời xa; `plate: "auto"` đảo tương phản (nền tối → hộp sáng chữ tối); nhãn tuyến giảm nhấn chỉ ở nét.
- Con thừa hưởng hiệu ứng vào/ra của cha (chữ không lòi khỏi thẻ đang mở); camera mở đầu ở key đầu tiên (hết frame nhảy ở 0s).
- `qa.py` (mới): QA tĩnh (mốc từ, ngắt dòng, thời gian đọc, câu kết, SFX, camera_jerk, lod), QA khung chữ trong lúc animate (chồng, chạm viền, cắt khung, vùng an toàn, cỡ, tương phản), kiểm tra tất định; `check --deep`; `render` ghi `status`.

**Chưa làm trong 1.1.0**: dựng lại các video thử (theo yêu cầu người dùng, để sau); nền ảnh vệ tinh/địa hình và nghiêng 3D kiểu GeoLayers; nghe đánh giá mix trực tiếp.

## 1.0.0 — 2026-10-15
Bản đặc tả ban đầu do người dùng cung cấp + renderer v1 (text, shape, ảnh, icon, đường nối, danh sách, số, biểu đồ, trích dẫn, camera, bản đồ thế giới/vùng, GeoJSON tuyến).
