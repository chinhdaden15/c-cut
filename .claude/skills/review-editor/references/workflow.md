# Quy trình

Thư mục dự án `{pdir}`; kết quả công cụ nằm trong `{pdir}/review/`.

## 1. Kiểm kê (app chạy sẵn khi bắt đầu; tự chạy lại khi người dùng thêm tư liệu)

```
.venv/bin/python -m thagent.review inventory {pdir} <file|thư-mục…> --ref <video tham khảo…>
```
- ID ổn định theo tên file (F01, F02…), giữ nguyên khi chạy lại. File gốc KHÔNG bị sửa.
- Mỗi file: thời lượng, độ phân giải, fps, dọc/ngang, xoay, có tiếng, độ to (LUFS), **trùng** (chữ ký nội dung), **khoảng đen**,
  **đứng hình/đen cuối** (outro nền tảng → `outro`), **không dùng được** (lỗi đọc / trùng).
- Lưu đệm theo chữ ký file → chỉ phân tích lại file mới/đã đổi.

## 2. Phân tích (cùng lệnh inventory)

- Cảnh (shot) theo điểm cắt; mỗi cảnh: độ nét, rung, phơi sáng, tỉ lệ có mặt người, vị trí mặt (để crop), cờ `mờ / rung / tối / cháy sáng / đen`.
- Lời: chép từng từ + giây + độ tin cậy; câu; **từ cần soát** (tin cậy thấp, số/đơn vị, có thể là tên riêng) — giá, diện tích, mã sản phẩm
  phải đối chiếu brief/thông số/hình; không chắc → không đưa lên chữ thông tin.
- `role_guess`: người dẫn / B-roll / hỗn hợp — chỉ là gợi ý, Claude xác nhận bằng ảnh tổng hợp.

```
.venv/bin/python -m thagent.review media {pdir}            danh sách + ảnh tổng hợp review/sheets/<ID>.jpg (Read để nhận diện sản phẩm/không gian/thao tác)
.venv/bin/python -m thagent.review media {pdir} F03        cảnh + câu nói + từ cần soát của 1 file
.venv/bin/python -m thagent.review words {pdir} F03 10 30  lời từng từ + giây (đặt điểm cắt đúng ranh giới từ)
.venv/bin/python -m thagent.review frames {pdir} F07 2.5 6 9   ảnh khung nguồn tại các giây → review/frames.jpg (xem đúng vật/phòng/thao tác)
```
Ghi nhận diện vào `review/notes.json` (tuỳ ý): người nói, sản phẩm/phiên bản, không gian (tầng/phòng), cỡ cảnh, thao tác của từng cảnh.

## 3. Chọn take

```
.venv/bin/python -m thagent.review takes {pdir}     → review/takes.json: nhóm các lần nói lại cùng ý + điểm từng take
```
- Ưu tiên: rõ lời, trọn ý, biểu cảm tự nhiên, hình dùng được (nét, có mặt, không rung). Điểm chỉ là gợi ý; nghe nghĩa câu để quyết.
- KHÔNG mặc định take cuối hay take ngắn nhất. Mỗi nhóm take chỉ dùng 1 lần (check báo lỗi nếu dùng lại).
- Chừa đủ đầu/cuối: cắt ở ranh giới từ (check báo lỗi khi điểm cắt rơi giữa từ).

## 4. Xây mạch review (theo phong cách — styles.md)

- Hook lấy từ nội dung/khoảnh khắc CÓ THẬT trong footage (câu kết luận mạnh, phản ứng, cảnh đẹp nhất của chính sản phẩm/căn nhà).
- Cắt nói vấp, câu lặp, khoảng lặng thừa; KHÔNG cắt từ phủ định, điều kiện, đối tượng, ngữ cảnh làm đổi nghĩa.
- Được sắp lại các đoạn HOÀN CHỈNH, giữ logic + quan điểm người nói. Không tự tạo lời/CTA/thông số.

## 5. Ghép lời với hình minh họa

Mỗi đoạn trong `review/edit.json` ghi: `say` (ý đang nói), `src/in/out` (lời), `cutaways[]` (B-roll: `src/in/at/dur`), `why` (lý do khớp),
và `missing` (asset còn thiếu). Ví dụ: nói đầu nối → cận đúng đầu nối; nói chất son → swatch/thử đúng son đó; nói phòng ngủ → đúng phòng ngủ đang
giới thiệu; nói đường trước nhà → đường của đúng căn nhà. Xem lại bằng `frames` trước khi chốt.

Schema đầy đủ: docstring `thagent/review/edit.py` (category, style, intensity, formats, fps, subtitles, target_s, music, segments[…], missing, notes).

## 5b. Hiểu hành động + hướng sự chú ý (bắt buộc khi người dẫn cầm/chỉ sản phẩm)

```
.venv/bin/python -m thagent.review motion {pdir} F05 45 60          độ nét/chuyển động mỗi 0,5s + lời → thấy đoạn nhòe/thao tác chuẩn bị để cắt gọn
.venv/bin/python -m thagent.review hands  {pdir} F05 45 64          lúc giơ/chỉ tay (t0–t1, đầu ngón, vùng gợi ý)
.venv/bin/python -m thagent.review frames {pdir} F05 56 59           ảnh CÓ LƯỚI toạ độ 0.1 → đọc box sản phẩm x,y,w,h
.venv/bin/python -m thagent.review track  {pdir} khan F05 56 0.50,0.45,0.28,0.28 54.5 63.6   bám vật → review/tracks/khan.json
```
- Cắt gọn thao tác chuẩn bị/khung nhòe (check cảnh báo): dời `in` tới lúc sản phẩm đã rõ HOẶC che bằng cutaway — không cắt mất lời/động tác có nghĩa.
- Trong edit.json (đoạn có sản phẩm):
  - `"reframe": {"9x16": [{"at": 0.3, "dur": 0.6, "to": "face+khan"}, {"at": 7.5, "dur": 0.6, "to": "base"}]}` — `to`: "face" | "<track>" | "face+<track>"
    | "base" | {"cx","cy","zoom"}; app tự giới hạn phóng để giữ nét (≤ 1,45× độ phân giải cần). Bản ngang dùng nền mờ thì không reframe.
    Reframe chừa dải phụ đề bằng cách DỊCH khung (giữ mức phóng) khi đủ chỗ; không đủ thì giữ phóng và để phụ đề chọn dải trên.
  - `texts`: `{"role": "label", "text": "Khăn giấy ướt", "track": "khan", "at": 0.5, "dur": 3}` — nhãn sát vật, chấm neo + đường dẫn, đi theo vật.
  - `texts`: `{"role": "focus", "track": "khan", "at": 2.2, "dur": 1.8}` — vòng nhấn mềm ĐÚNG lúc chỉ tay (theo `hands`), một lần là đủ.
- Ngược sáng: inventory gắn `backlit` → app nâng vùng tối nhẹ (không tăng bão hoà, không hứa cứu vùng cháy); chỉnh tay: `"tone": {"lift": 0.05–0.15}` hoặc 0.

## 5c. Làm sạch lời + số liệu + nhịp hình (v1.2.1 — làm SAU khi chốt mạch, TRƯỚC check)

```
.venv/bin/python -m thagent.review fixjoins {pdir}       nới điểm nối theo nhịp nói
.venv/bin/python -m thagent.review clean    {pdir}       Cắt sạch (Talking Head) bên trong từng đoạn nói → đoạn con <id>a/b/…, punch-in che cắt
.venv/bin/python -m thagent.review keyinfo  {pdir}       số liệu/thông tin then chốt trong lời (giây trên timeline xuất)
```
- Đoạn không muốn cắt bên trong (ngập ngừng có chủ ý, cảm xúc): `"clean": false` trước khi chạy `clean`. Xem `review/cleanup.json` — không có cắt nào làm đổi nghĩa.
- Mỗi số liệu then chốt (giá, diện tích, năm kinh nghiệm, quy mô vốn, thông số) → khối stat đúng lúc nói, đặt trong đoạn con chứa số:
  `{"role": "stat", "value": 23, "unit": "năm", "label": "kinh nghiệm tại Việt Nam", "at": 0.1, "dur": 2.6}` — giá trị phải khớp lời/brief, không làm tròn đổi nghĩa.
  Số phụ (không then chốt) để phụ đề là đủ; check cảnh báo để xem lại.
- `"auto_zoom": true` ở gốc edit.json: đẩy vào lúc khối stat/chữ nhấn hiện, lùi ra khi tắt (bỏ qua đoạn đã có reframe tay).
- SFX tự gắn theo điểm nhấn (xem SKILL.md); `"sfx": false` để tắt, `"sfx_events": [{"t": 4.1, "role": "money"}]` để thêm.

## 6. Dựng – kiểm – xuất

```
.venv/bin/python -m thagent.review check  {pdir}                 kiểm bản dựng (nguồn, đoạn đen/outro, cắt giữa từ, take lặp, crop mất mặt, thời gian đọc chữ)
.venv/bin/python -m thagent.review stills {pdir} 9x16 t1 t2 …     ảnh đúng như bản xuất (crop + chữ) → Read, sửa trước khi dựng
.venv/bin/python -m thagent.review stills {pdir} 16x9 t1 t2 …
```
Sửa hết lỗi `check`, xem stills cả hai tỷ lệ → ghi `{pdir}/plan_ready.json` = `{"ready": true, "formats": [...], "summary": "…"}`.
App dựng (`render`) và kiểm file xuất thật (kích thước, fps, thời lượng, khung đen, lặng dài, độ to/đỉnh, chữ chồng/cắt khung) cho TỪNG tỷ lệ;
còn lỗi → app gửi lại để sửa edit.json (không xuất lại liên tục).

## 7. Sửa cục bộ

“Thay cảnh này / giữ take thứ hai / giảm text / đổi hook”: chỉ sửa đoạn tương ứng trong edit.json, chạy check + stills đoạn đó, ghi lại plan_ready.json.
Không phân tích lại tư liệu, không viết lại cả mạch.
