---
name: gia-tri
description: Video "Giá Trị" — câu ngẫm về sự đời. Giọng đọc chậm rãi, mỗi câu một cảnh ảnh / video thật dịu mắt, phụ đề cả câu chạy theo giọng, nhạc piano do C-Cut tự sáng tác theo cảm giác của nhạc mẫu. Gọn, không motion graphic. Dùng khi CN.AI gửi việc Text to Video kèm style "gia-tri".
---
# Skill Giá Trị

Chỉ gửi qua `POST /api/ccut/t2v/add` với `"style": "gia-tri"` (trường tuỳ chọn: `music_ref`, `tone`, `music_seed`). Không hiện trong ô chọn style của giao diện.

## Việc nào do app làm, việc nào do Claude làm
| Bước | Ai | Chi tiết |
|---|---|---|
| Lời đọc | app | `spoken()` lọc ghi chú; phần sau `=== GHI CHÚ DỰNG ===` thành `kich_ban_goc.txt` (gợi ý hình) |
| Giọng | app | tốc độ 0.93 (≤ 0.95), nghỉ ≈ 0,75 s sau câu, ≈ 1,25 s giữa đoạn (đoạn = các dòng giữa hai dòng trống), đuôi lặng 2 s |
| Nhạc | app | **nhạc thư viện miễn phí = mặc định** (danh mục `assets/music_catalog.json`: 15 bài PIANO SOLO; mặc định chỉ nhóm A = đúng kiểu `mixkit:688`, nhóm B chỉ khi chọn tay; `music_id` hoặc tự chọn theo `tone` / nhạc mẫu) (`music_id`: `mixkit:<mã>`, cắt đúng độ dài, mờ vào / nhỏ dần). Không có `music_id` → `thagent/music_gen.py` tự sáng tác: phân tích nhạc mẫu → tự viết giai điệu + hòa âm piano mới → mp3 dài đúng video, −15 dB dưới giọng, nhỏ dần 2 s cuối; lưu `<dữ liệu app>/music_lib/` |
| Chọn hình | **Claude** | mỗi câu (hoặc 2–3 câu liền ý) một hình / clip thật → `giatri_picks.json` |
| Dựng + kiểm | app | `python -m thagent.v2m giatri <dự-án>` (builder tự sinh, phụ đề tự chia, check chế độ `calm`) |

## Chọn hình (việc duy nhất của Claude)
- **Ưu tiên THIÊN NHIÊN** (rừng sương, mặt hồ, biển, mây trời, hoàng hôn, đồng cỏ, lá cây, nắng, mưa…) làm ẩn dụ cho ý câu. **Tránh người**: tối đa 2 cảnh có người, và chỉ tay / bóng lưng, không thấy mặt rõ.
- Cảnh tĩnh, màu dịu, ít chi tiết, **không chữ / logo** trong hình; khung dọc 9:16, vật chính không sát mép.
- Ghi chú dựng của CN.AI là gợi ý — khi gợi ý có người / đồ vật thì tìm cảnh thiên nhiên cùng cảm xúc thay vào.
- Tìm: `python -m thagent.v2m brollsearch <dự-án> "<từ khoá tiếng Anh>"` → ảnh ghép Mixkit có mã; tải: `python -m thagent.v2m broll <dự-án> <url> v_ten.mp4 "Mixkit"`. Ảnh thật: `python -m thagent.tools img …`.
- **Mỗi hình / clip chỉ dùng một lần.** Gom nhiều tìm kiếm trong một lệnh Bash; xem ảnh ghép một lần cho cả nhóm.
- `giatri_picks.json`: `[{"s": [0,1], "src": "assets_web/v_x.mp4", "desc": "điều thật sự thấy", "in": 0}, …]` — `s` liền nhau, đủ mọi câu theo thứ tự; `desc` bắt buộc.

## Cấm
Motion graphic, chữ động, icon, bản đồ, biểu đồ, b-roll dồn dập, nhạc có lời, chép giai điệu của nhạc mẫu (bản quyền — Facebook tắt tiếng).

## Hình ảnh & chuyển động (app tự làm)
Mỗi nhóm câu một cảnh, hình hiện sớm 0,35 s so với lời, chuyển cảnh mờ dần 0,8 s, zoom / trượt rất chậm (Ken Burns), phụ đề chữ lớn trắng bóng nhẹ, từ đang đọc ấm nhẹ.
