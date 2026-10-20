# Ảnh minh họa và video b-roll (v1.3.0 — bắt buộc)

Motion graphic không chỉ có icon/chữ: xen ảnh thật và video b-roll để trực quan, đỡ nhàm. Phối xen kẽ ảnh – sơ đồ – icon – số liệu;
không để nhiều cảnh liền nhau chỉ toàn icon. Mức gợi ý: mỗi ý chính / ~15–20s có ít nhất 1 ảnh hoặc b-roll.

## 1. ĐÚNG CHÍNH XÁC trước, đẹp sau

Ảnh sai nghĩa còn tệ hơn không có ảnh. Đặc biệt với lĩnh vực cần chính xác — **giáo dục, bất động sản, y tế, tài chính, pháp lý**:
- Ảnh phải cho thấy **đúng thứ đang nói**, theo nghĩa đen, không ẩn dụ. Ví dụ sai: “chủ nhà” → cái búa tòa án; “khách thuê” → bắt tay khắc trên đá;
  “đúng nhu cầu” → mặt tiền nhà bất kỳ.
- Đúng **bối cảnh**: BĐS cho thuê doanh nghiệp → văn phòng/showroom/mặt bằng thương mại thật (ưu tiên bối cảnh Việt Nam), không phải phòng khách gia đình;
  giáo dục → đúng cấp học, đúng hoạt động (lớp học, phòng thí nghiệm…); y tế → đúng chuyên khoa, thiết bị.
- Đúng **thời đại, địa phương, khán giả**: ưu tiên ảnh Việt Nam / châu Á khi nội dung ở Việt Nam.
- **Không chắc đúng → không dùng ảnh**; dùng sơ đồ/icon/số liệu thay thế.

**Bắt buộc tự kiểm từng ảnh**: tải xong → Read ảnh → mô tả ngắn ảnh thật sự thể hiện gì → đối chiếu câu đang nói. Ghi vào
`assets_web/illus_check.json`: `{"i_ten.jpg": {"noi_dung_anh": "…", "cau_noi": "…", "khop": true}}`. `khop: false` → thay ảnh khác.

## 2. Ảnh đúng chủ thể vs ảnh minh họa

- **Chủ thể có thật** (dự án, phân khu, thương hiệu, địa điểm, người, sự kiện): chỉ dùng ảnh THẬT của chính chủ thể đó, nguồn rõ ràng
  (website chủ đầu tư, báo chí, trang chính thức) → `real=True`, nhãn trên video: “Hình ảnh thực tế”.
  **Dự án / phân khu BĐS có tên → BẮT BUỘC ảnh thật từ chủ đầu tư**: tìm trên website chủ đầu tư, trang dự án chính thức,
  bài báo về dự án (Báo Đầu Tư, VnExpress, CafeLand…) — ảnh phối cảnh hoặc ảnh chụp thực tế của chính dự án đó.
  TUYỆT ĐỐI không thay bằng ảnh minh họa chung (nhà phố khác, phố cổ…) khi lời đang nói tên dự án.
  Tìm kỹ mà vẫn không có ảnh thật → dùng bản đồ vị trí / sơ đồ / chữ tên dự án, KHÔNG dùng ảnh của nơi khác.
  **App kiểm (check)**: ghi `entities.json` ở thư mục dự án — `[{"name": "Vinhomes Central Park", "aka": ["Vinhomes Tân Cảng"], "photos": ["w_vhcp_1.jpg"], "no_photo": null}]`;
  ảnh trong `photos` dựng với `real=True`, nguồn là URL trang; cảnh đang nói tên chủ thể phải có ảnh của nó (không có ảnh thật → `"no_photo": "lý do"`,
  dùng bản đồ/chữ tên). Không có chủ thể nào → `[]`. Nội thất/tiện ích/khái niệm nói chung chung vẫn dùng ảnh minh họa.
- **Ảnh minh họa** (khái niệm, cảnh chung): nhãn trên video: “Hình ảnh minh họa”.
- **Trên video KHÔNG ghi nguồn** — chỉ ghi “Hình ảnh minh họa” / “Hình ảnh thực tế” (người dùng tự ghi nguồn khi đăng bài).
  Nguồn vẫn BẮT BUỘC lưu khi tải (`assets_web/illus_sources.json`) để app hiện ở mục “Nguồn và bản quyền”.
- Mỗi ảnh/b-roll hiện ≥ 1,8s; cảnh ngắn chỉ 1 ảnh. Không dùng ảnh có watermark, chữ lớn, logo bên thứ ba.

## 3. Thứ tự lấy nguồn

1. **Thư mục người dùng gửi** (b-roll, ảnh trám — app chép vào `tu_lieu/`, xem trước ở `tu_lieu/_xem/`; dùng bằng `s.photo("tu_lieu/<file>", …)`): xem trước bằng ảnh tĩnh/khung hình, dùng khi ĐÚNG nội dung đang nói (ưu tiên số 1 — đúng bối cảnh nhất).
2. **Ảnh thật của chủ thể** (khi nói về chủ thể có thật).
3. **Kho ảnh có giấy phép**: Openverse (`https://api.openverse.org/v1/images/?q=…&license_type=commercial`), Unsplash, Pexels, Wikimedia Commons.
   Tải: `.venv/bin/python -m thagent.tools img <dự-án> <url> i_ten.jpg "<tác giả / nguồn (giấy phép)>"`.
4. **Video b-roll ngoài — ƯU TIÊN Pinterest, không được thì Pexels** (người dùng đã chọn cả hai, Pinterest trước):
   - Tìm: WebSearch “<từ khóa tiếng Anh/Việt> video” giới hạn `pinterest.com` → lấy link pin video; không có/không tải được → `pexels.com` (link `pexels.com/video/…`).
   - Tải: `.venv/bin/python -m thagent.v2m broll <dự-án> <url> v_ten.mp4 "<nguồn>"` — chuẩn hoá H.264, bỏ tiếng, ≤1080p, ≤30s,
     lưu `assets_web/`, nguồn vào `illus_sources.json`, ảnh xem trước 4 khung `assets_web/_xem/v_ten.jpg`.
   - BẮT BUỘC Read ảnh xem trước, kiểm ĐÚNG nội dung (cùng quy tắc chính xác như ảnh); có watermark/chữ lớn/logo lạ → bỏ.
   - Dùng: `s.photo("v_ten.mp4", t, …)` → khung bo góc, thu nhỏ; `in=` chọn đoạn đẹp nhất.

## 4. Khối dựng sẵn (kit)

| Khối | Dùng khi |
|---|---|
| `s.photo(src, t, label, real=False, style="scale"|"mask_left")` | một ảnh/b-roll lớn bo góc, zoom/trượt chậm (Ken Burns), nhãn “Hình ảnh minh họa/thực tế” |
| `s.photos([(src, nhãn, t), …])` | 2–3 ảnh/b-roll lần lượt theo lời, ảnh mới chồng lên, ảnh cũ lùi |
| `s.before_after(a, b, t_a, t_b, labels)` | trước/sau, ảnh sau quét mở |
| `s.photo_bg(src)` | ảnh làm nền cả khung (tối đi) cho câu mở/kết, chữ lớn đè lên |
| `s.photo_pin(photo_id, rx, ry, "chi tiết", t)` | chấm chú thích một chi tiết trong ảnh |

**Video b-roll**: truyền file `.mp4/.mov` vào `s.photo` / `s.photos` → khung video **bo góc, thu nhỏ vừa phải như ảnh**, KHÔNG phủ kín khung;
`in=` giây bắt đầu trong clip, `rate=` < 1 để chậm lại. Clip ngắn hơn thời gian hiện thì dừng ở khung cuối — chọn đoạn đủ dài.
Tất cả khối tự bố cục riêng cho 9:16 và 16:9.
