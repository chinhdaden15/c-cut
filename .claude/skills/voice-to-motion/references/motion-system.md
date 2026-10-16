# Hệ thống chuyển động và chuyển cảnh

## 1. Cấu trúc mỗi cảnh

**Xuất hiện → hành động/nhấn mạnh → thời gian tiếp nhận → chuyển tiếp.**

- Các bước được chồng thời gian (overlap 30–60%): đối tượng sau bắt đầu khi đối tượng trước đã đi được phần lớn quãng đường; không đợi từng hiệu ứng kết thúc hẳn.
- Thời gian tiếp nhận là **khoảng dừng có chủ đích**: chữ rõ nét, hình đứng yên đủ để đọc (0,6–2s tùy lượng chữ). Không thêm chuyển động liên tục vào mọi đối tượng chỉ để tránh đứng yên — renderer **không còn “drift” mặc định** (theme.drift = 0).
- Đứng yên > 4s mới bị QA nhắc kiểm tra; dưới mức đó là quyết định thiết kế.

## 2. Easing

| Loại | Easing | Ghi chú |
|---|---|---|
| vào khung | `out` (cubic) / `quart` | nhanh rồi chậm, dừng mềm |
| ra khung | `in` | nhẹ, nhanh gọn |
| di chuyển/biến đổi giữa hai trạng thái | `inout` | camera, thẻ mở rộng, đối tượng đổi vị trí |
| nhấn mạnh vật nhỏ | `back` (overshoot nhỏ) | chỉ cho icon/số ngắn, không cho cả khối chữ |
| vẽ đường | `out` / `inout` | `inout` khi camera bám theo đầu nét |

Không áp một kiểu bounce/fade/slide cho cả video. Mỗi cảnh chọn tối đa 2 kiểu vào chính.

## 3. Camera

- Chỉ pan/zoom khi cần hướng sự chú ý hoặc giải thích quan hệ không gian.
- Renderer: mỗi key camera bắt đầu từ **vị trí thật** của camera tại thời điểm bắt đầu (key chồng thời gian không gây nhảy); zoom nội suy theo **log** để cảm giác tốc độ đều khi phóng từ 0,4× đến 150×.
- Khi nhiều chặng nối nhau (bám theo tuyến), đặt `ease: "linear"` cho chặng giữa và `inout` cho chặng đầu/cuối để vận tốc liên tục. QA `camera_jerk` cảnh báo chỗ vận tốc đổi đột ngột.
- Giữ hướng Bắc gần như lên trên: chỉ xoay nhẹ có chủ đích (≤ ±3°) quanh điểm đang giải thích; không xoay 360°, không nghiêng tới mức khó nhận diện địa lý, không rung/lắc giả chuyển động.

### 3a. Camera phải có diễn tiến (bắt buộc với cảnh bản đồ)

Mỗi cảnh: **Establish** (khu vực, vị trí cần hiểu) → **Focus** (pan/zoom tới chủ thể) → **Explain** (đẩy vào/trôi nhẹ, đổi khung trong lúc diễn giải) → **Resolve** (lùi ra hoặc chuyển sang chủ thể sau).
- Kit: `s.story(khung_rộng, khung_chủ_thể, t_est, t_focus[, resolve, t_res])`; `s.look(box, t, dur)` cho từng nhịp.
- Kit tự thêm nhịp Explain: cảnh bản đồ mà camera đứng yên > 2,2s → đẩy vào +6% và xoay ±2° (đổi chiều mỗi cảnh) tới cuối cảnh.
- Kit tự nối tiếp: key sau không khởi hành trước khi key trước tới nơi (chồng nhau = khựng giữa đường).
- Quãng xa (châu lục ↔ châu lục): đi đường ngắn và đúng hướng (dùng bản lặp kinh độ +360 khi đi qua Thái Bình Dương), dur ≥ 1,5s.
- Khi camera đổi: chữ/nhãn luôn thẳng (renderer giữ thẳng mọi text/icon/callout), marker/tuyến bám toạ độ, chủ thể ở trong vùng an toàn.
- Được giữ hình để đọc, nhưng không để nhiều cảnh liên tiếp chỉ đứng im với chữ nhỏ.
- Chuyển động camera hỗ trợ nội dung, không dùng để che thiếu minh họa.

## 4. Chuyển cảnh dựa trên đối tượng chung

Ưu tiên theo thứ tự:
1. **Điểm/vật chung**: điểm trên bản đồ thành tâm zoom; đồng xu/biểu tượng đi tiếp sang cảnh sau (dùng `persist`/`until_s` + `animate` vị trí).
2. **Thẻ mở thành cảnh**: rect `animate` w/h/r từ nhỏ → khung giải thích; nội dung là con (`parent`) của thẻ.
3. **Camera lia** trong cùng không gian (bản đồ, sơ đồ lớn).
4. Chuyển cảnh phủ (`transition_in`: `wipe`, `bars`, `fade`, `flip`) chỉ khi đổi chương/đổi mood.

## 5. Tính tất định và lỗi kỹ thuật

- Mọi frame là hàm thuần của (timeline, t): dựng lại cùng frame phải giống hệt (QA `determinism`).
- Phân biệt lỗi render và lỗi thiết kế trước khi sửa:
  - hình “giật”: kiểm tra QA camera_jerk, timestamp frame, frame lặp bất thường (render_video đo chuỗi frame giống nhau), điểm nối key camera;
  - chữ “nhảy”: kiểm tra word_times đủ mốc và bố cục đã chốt (vtext);
  - “đơ”: khoảng không có sự kiện nào gắn với lời đọc → sửa storyboard (thêm hành động đúng ý), không thêm rung lắc.
