# Định dạng dọc 9:16 và ngang 16:9

## Câu lệnh của người dùng

| Người dùng nói | Làm |
|---|---|
| (không nói gì) / “Xuất cả dọc lẫn ngang” | **mặc định**: hai bản riêng từ cùng voice + nội dung → `<id>_9x16.mp4` và `<id>_16x9.mp4` |
| “Dựng dọc” | chỉ bản dọc 9:16, 1080×1920 → `<id>_9x16.mp4` |
| “Dựng ngang” | chỉ bản ngang 16:9, 1920×1080 → `<id>_16x9.mp4` |

Trong app C-Cut: ghi lựa chọn vào `plan_ready.json` → `"formats": ["9x16"]` (chỉ dọc), `["16x9"]` (chỉ ngang), bỏ trống = cả hai. App chỉ xuất đúng các tỷ lệ này, kể cả khi thư mục còn timeline của tỷ lệ kia; giữ lựa chọn cho các lần sửa sau.

Lệnh renderer: `.venv/bin/python -m thagent.v2m render <dự-án>` (mặc định cả hai, dựng song song — bản ngang ở tiến trình con, log `versions/vNNN/render_16x9.log`), hoặc `render <dự-án> 9x16 | 16x9`. `--serial` để dựng lần lượt khi máy yếu.
Thời gian tham khảo (máy hiện tại): video không bản đồ ~2–4 phút/bản cho 30–70 giây; video bản đồ hành chính + tuyến đường ~35 phút/bản cho 48 giây (song song → tổng gần bằng một bản).
(`check <dự-án> 16x9 [--deep]`, `stills <dự-án> 16x9 t1 t2 …` để kiểm riêng từng tỷ lệ).

## Nguyên tắc

- **Không** kéo giãn, thêm viền đen, crop hay thu nhỏ bản dọc để thành bản ngang. Mỗi tỷ lệ có **timeline bố cục riêng**: `timeline_9x16.json`, `timeline_16x9.json` (renderer từ chối dựng một tỷ lệ chưa có bố cục riêng).
- Hai bản **dùng chung**: voice (giữ nguyên tốc độ/thứ tự), chữ, asset, phong cách, màu, các mốc nhấn chính, thời lượng.
- Hai bản **được khác**: vị trí/cỡ/ngắt dòng chữ, sắp xếp hình–icon–shape–sơ đồ, khung bản đồ, vị trí nhãn, đường camera, hướng xuất hiện, khoảng di chuyển, chuyển cảnh.
- Cách viết: **một builder** cho nội dung, nhận tham số định dạng và dùng `thagent.v2m.layout.Frame(fmt)` để lấy vùng — không hard-code toạ độ 1080×1920, không nhân mọi toạ độ theo một hệ số.

## Vùng bố cục (`layout.py`)

| Vùng | Dọc 9:16 | Ngang 16:9 |
|---|---|---|
| `safe` (an toàn UI) | x 60–1020, y 150–1600 | x 90–1830, y 70–1000 |
| `title` | dải trên y 220–560 | dải trên y 80–250 (khi minh họa toàn ngang) |
| `text` | = title (chữ phía trên) | **cột trái** x 110–800 (chữ căn trái) |
| `main` / `map` | giữa khung | **phần phải** x 840–1840 khi có cột chữ |
| `full` | bản đồ/hình toàn khung | toàn khung |
| `caption` | dưới y 1420–1600 | dưới cột chữ |

- Bản dọc: bố cục trên–dưới, một trọng tâm; nhóm thông tin xuất hiện tuần tự.
- Bản ngang: chữ một bên – minh họa một bên khi có câu dẫn; bản đồ/sơ đồ toàn khung (`full`) khi cảnh không có chữ dài. Không bắt buộc chia đôi mọi cảnh; tránh nội dung nhỏ ở giữa, hai bên trống.

## Chữ và shape theo tỷ lệ

- `max_w` lấy theo vùng của tỷ lệ đó (`F.width("text")`), renderer ngắt dòng theo nghĩa lại cho từng bản — không chép ngắt dòng của bản dọc.
- Ngang: chữ HUD căn trái trong cột chữ; dọc: căn giữa trong dải tiêu đề.
- Không giảm cỡ chữ dưới mức đọc được để nhét vừa; đổi bố cục/chia dòng. Shape (thẻ, hộp) tự theo chữ + padding.

## Bản đồ và camera

- Toạ độ, hình học địa lý giữ nguyên. Camera tính lại bằng `F.fit_geo(lon0, lat0, lon1, lat1, region="map"|"full", t=…, dur=…)`: vùng địa lý cần giải thích nằm trọn trong vùng bố cục của tỷ lệ đó.
- Nhãn/callout được renderer đặt và khoá **riêng cho từng bản** (bỏ phiếu qua nhiều thời điểm). LOD theo zoom của từng bản.
- Không dùng nguyên đường camera bản dọc cho bản ngang.

## Timeline, âm thanh, kiểm tra

- Hai bản cùng `duration`, cùng mốc nội dung; choreography trong cảnh được chỉnh theo bố cục; SFX đặt theo hành động thị giác của từng bản.
- Dựng và kiểm tra **riêng từng tỷ lệ** (QA tĩnh, QA khung chữ trong lúc animate, tất định, codec/kích thước/fps/thời lượng). Không coi bản ngang đạt vì bản dọc đạt.
- Dự án dọc cũ (chỉ có `timeline.json`) vẫn dựng như trước.
