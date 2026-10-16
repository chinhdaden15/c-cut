# Bố cục, xuống dòng và typography tiếng Việt

## 1. Vùng khung dọc 1080×1920

| Vùng | Toạ độ (px) | Dùng cho |
|---|---|---|
| An toàn UI nền tảng | x 60–1020, y 150–1600 | mọi chữ quan trọng phải nằm trong vùng này |
| Tiêu đề | y 220–520 | câu dẫn + điểm nhấn của cảnh |
| Minh họa chính | y 560–1380 | bản đồ, sơ đồ, nhân vật, vật thể |
| Chú thích / nguồn | y 1420–1600 (nguồn có thể tới 1860, cỡ ≥ 20px) | chú giải, nhãn phụ, “minh họa”, nguồn |

- Mỗi cảnh có **một trọng tâm thị giác**. Chữ và hình cùng tranh trọng tâm thì giảm một bên (mờ, nhỏ, lùi).
- Nội dung chính nên chiếm ≥ 55% chiều cao vùng minh họa. Cảnh có “chữ nhỏ giữa nền trống” là lỗi thiết kế: phóng to cụm chính, thêm minh họa hành động hoặc đổi bố cục, không chỉ thêm chuyển động.
- Khi chọn một nhánh của sơ đồ để giải thích tiếp, **dựng lại nhánh đó thành cảnh chi tiết** (bố cục mới, cỡ chữ đọc được). Không mặc định zoom cả sơ đồ cũ — zoom làm cắt các nút còn lại và chữ chạm viền.
- Không giảm chữ dưới mức đọc được để nhét vừa: đổi bố cục, chia cụm, hoặc chia nhịp xuất hiện.

## 2. Xuống dòng theo ngữ nghĩa (bắt buộc)

Renderer có `thagent/v2m/vtext.py` — ngắt dòng bằng quy hoạch động **ở cỡ chữ gốc**, chốt trước khi animate:

- giữ liền: cụm trong `keep`, cụm `highlight.match`, tên riêng viết hoa liên tiếp, số + đơn vị (“4 tỷ”, “10,4 %”, “15 tháng 10”), từ ghép thường gặp (danh sách `COMPOUNDS`);
- không ngắt ngay sau từ gắn với phần sau (của, các, những, một, với, cho, về…); ngắt trước giới từ/liên từ là tự nhiên; ngắt sau dấu phẩy được ưu tiên;
- tránh dòng cuối mồ côi một từ ngắn; cân đối độ dài nhưng **ưu tiên đúng nghĩa**;
- không mở dòng mới bằng dấu “–”; ngắt **sau** “–” giữa hai tên (“Bến Lức – / Long Thành”) được phép.

Quy tắc khi lập timeline:
- Luôn đặt `max_w` cho chữ có thể dài; truyền `keep` cho thuật ngữ/tên tuyến/địa danh nhiều âm tiết của video đó.
- Muốn tự quyết, dùng `\n` (ví dụ “GIÁ TRỊ NẰM Ở\nSỰ KẾT NỐI”). Một từ đứng riêng chỉ khi là nhấn mạnh có chủ đích, kèm cỡ chữ lớn hơn, `allow_orphan: true`.
- `word_times` phải có **đủ mốc cho mọi từ** (QA báo lỗi nếu thiếu). Từ hiện dần **trong bố cục đã chốt**; không bao giờ để câu nhảy dòng khi thêm từ.
- Kiểm tra: `python -m thagent.v2m check <dự-án>` liệt kê lỗi “ngắt giữa cụm cần giữ liền”, “dòng cuối mồ côi”.

Ví dụ đúng: “Hôm nay chúng ta sẽ / nói về tích phân”. Sai: “Hôm nay chúng ta sẽ nói về tích / phân”.

## 2b. Không chạm, vẫn hiểu (tự tránh va chạm)

- Chữ, nhãn và shape **không được chạm nhau**; khoảng cách tối thiểu 10px giữa các khối (kể cả padding hộp).
- Trên bản đồ, nhãn điểm/tuyến dùng `callout` (tự tránh tuyến, tiêu đề, chữ khác). Nhãn chữ thường có `avoid: true`: renderer thử vị trí quanh điểm neo (trên, dưới, phải, trái, chéo; xa dần), chọn chỗ trống đầu tiên, **giữ vị trí cũ qua các frame** nếu vẫn trống (không nhảy), tự kẻ đường dẫn về điểm neo khi phải dời xa > 20px.
- Thứ tự ưu tiên = thứ tự vẽ (layer, rồi thứ tự khai báo): khai báo nhãn quan trọng trước để nó giữ vị trí đẹp nhất.
- Giới hạn hiện tại: tránh chữ và shape; chưa tránh nét đường/tuyến → đặt `offset` của nhãn tuyến ra phía không có tuyến khác.

## 3. Hệ thống chữ

| Cấp | Font (role) | Cỡ ở khung 1080 | Màu | Dùng |
|---|---|---|---|---|
| Điểm nhấn (headline) | `black` / `display` | 84–130 | trắng hoặc màu nhấn chính | 2–6 từ, ý chính của cảnh |
| Chữ dẫn | `semi` / `bold` | 44–60 | trắng 90% / xám sáng | câu dẫn trước điểm nhấn |
| Nhãn | `bold` | 30–40 | trắng, nền `plate` khi trên bản đồ | địa danh, nút, tên tuyến |
| Chú thích / nguồn | `medium` | 22–30 | xám sáng (tương phản ≥ 4.5:1) | “minh họa”, nguồn, chú giải |

- Tối đa 2 họ font (Montserrat + Be Vietnam Pro có sẵn, đủ dấu). Phân cấp bằng độ đậm, cỡ, màu, khoảng cách.
- Đo kích thước bằng font thật (renderer làm), tính cả dấu, line-height (1.02–1.2), padding.
- Chữ nhỏ nhất trên điện thoại ≥ 22px (QA cảnh báo dưới mức này); nhãn bản đồ ≥ 26px.

## 4. Bộ hiệu ứng chữ (component trong `d_text`)

| Thuộc tính | Hiệu ứng | Khi nào |
|---|---|---|
| `word_style: "mask"` | từng từ trượt lên trong mặt nạ dòng | điểm nhấn gọn, nghiêm túc |
| `word_style: "up"` (mặc định) | dịch lên + nhòe nhẹ, rõ nét khi xong | câu dẫn |
| `word_style: "fade"` | mờ dần + dịch rất nhẹ | chú thích, mood nhẹ |
| `word_style: "scale"` | phóng nhẹ có overshoot | con số, từ khoá ngắn |
| reveal `blur` / `up` / `left` / `mask_up` | vào theo cụm (event) | tiêu đề cả khối |
| `highlight: {match, color, t, punch}` | đổi màu từ khoá đúng thời điểm `t`, `punch` = nhấn scale nhẹ | từ khoá trong câu |
| `marker: {match, t, color, mode: under/behind}` | dải nhấn chạy dưới/sau cụm chữ | cụm cần nhớ |
| event `pulse` | nhấn scale một lần | gọi lại một đối tượng |

- Không dùng một hiệu ứng cho mọi câu; không áp hiệu ứng mạnh lên mọi từ. Điểm nhấn nổi hơn chữ dẫn (to hơn, màu nhấn, hiệu ứng rõ hơn).
- Blur/glow không được che dấu tiếng Việt: chữ phải rõ nét hoàn toàn trước giai đoạn đọc.
- Chữ hoàn chỉnh phải có đủ thời gian đọc: ≈ số ký tự / 14 giây, tối thiểu 0,9s (QA tính). **Câu kết** hoàn tất hiệu ứng sớm, còn ≥ max(1,6s, ký tự/14) trước khi voice hết — nếu từ cuối được đọc quá sát cuối file, cho cả câu vào ngay ở đầu câu thoại (theo cụm), không chờ từng từ.
