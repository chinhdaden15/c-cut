# Chữ và đồ họa — ba vai trò tách riêng

## 0. Ba vai trò, không thay hành động bằng chữ

Phụ đề ≠ chữ nhấn ≠ nhãn sản phẩm. Khi lời nói về sản phẩm (“làm nổi bật cái khăn này”), SẢN PHẨM phải là điểm nổi bật nhất (spotlight + nhãn)
đúng lúc đó — không thay bằng việc viết chữ “Làm nổi bật”. Bớt chữ nhấn khi hình (spotlight, sơ đồ) đã thể hiện ý (check cảnh báo).

## 1. Phụ đề (`"subtitles": true`, app tự sinh từ lời của các đoạn `talk`)

- Chia theo CỤM NGHĨA (không theo số từ cố định): ngắt ở dấu câu, chỗ ngừng, trước liên từ (và, nhưng, thì, sau đó, để, khi, vì, nên, thay vì…);
  câu ngắn hơi dài vẫn để nguyên; không kết cụm bằng “một/những/các/cái/của/cho/vào/với…”; không tách thuật ngữ (`keep_terms`, vd “motion graphic”,
  tên sản phẩm) hay số + đơn vị; không để 1–2 từ lẻ thành cụm riêng.
- Máy chép lời viết hoa đầu câu giữa dòng mà thiếu dấu chấm (“vào Sau đó”, “tôi Thay thế”) → app tự thêm dấu chấm; câu cuối video có dấu chấm.
  Từ sai (“chám” → “trám”) sửa bằng `replace`/`fixes` sau khi đối chiếu ngữ cảnh/audio.
- Vị trí phụ đề: MỘT vị trí cho cả đoạn (không nhảy), luôn trong vùng an toàn; app tự né mặt + vật đang nhấn — dưới (78%) → thấp hơn (70%) →
  dải trên (~17%, thường là trần/khoảng trống) khi sản phẩm chiếm vùng dưới. Không đẩy phụ đề xuống thanh giao diện nền tảng.
- Mỗi cụm hiện đủ thời gian đọc (≥ 0,8s hoặc ~17 ký tự/giây), mờ hẳn trước khi cụm sau hiện.
- Cả cụm nghĩa hiện cùng lúc, **từ đang đọc đổi màu** (dễ đọc, không nhảy chữ), ngắt theo cụm nghĩa tiếng Việt (dấu câu, chỗ ngừng, chữ hoa đầu câu; tối đa 6 từ dọc / 9 từ ngang).
- **Soát chữ chép sai** (từ cần soát trong `media`: tên riêng, số, đơn vị, tin cậy thấp): sửa trên phụ đề bằng `"replace": {"sai": "đúng"}`
  hoặc `"fixes": [{"src", "t", "to"}]` theo brief/ghi chú/hình — không để tên sản phẩm/thương hiệu/giá sai trên phụ đề. Tiếng giữ nguyên.
- Vị trí ổn định (dọc ~78% chiều cao, ngang ~86%), chữ trắng viền đen → đọc được trên mọi nền; cụm trước mờ hẳn trước khi cụm sau hiện.
- Không che mặt, tay, sản phẩm, thao tác quan trọng: nếu một đoạn có sản phẩm/tay ở vùng phụ đề → chỉnh crop (`crop.cy`) để sản phẩm lên cao,
  hoặc tắt phụ đề đoạn đó. Không nhảy vị trí liên tục.

## 1b. Nhãn sản phẩm (`role: "label"`, cần `track`) và vòng nhấn (`role: "focus"`)

- Nhãn đi cùng ĐÚNG vật: đặt sát vật ở vùng trống (trên vật, hết chỗ thì dưới), chấm neo trên mép vật + đường dẫn ngắn, khung ôm chữ;
  hiện khi cần giải thích, tắt khi chuyển ý. Không đặt nhãn sản phẩm ở góc màn hình xa vật (trông như tiêu đề chung).
- Vòng nhấn: một điểm nhấn đúng lúc người dẫn chỉ tay (lấy mốc từ `hands`), kết thúc khi lời chuyển sang ý khác.

## 1c. Spotlight (`role: "spotlight"`, cần `track`)

- Giữ nguyên độ sáng/màu sản phẩm trong vùng chọn; làm tối vùng ngoài bằng lớp đen `dim` 0,25–0,40 (nền cháy sáng cần ~0,38).
- Vùng sáng = ô bo góc ôm sản phẩm + đệm (`pad` ~22px), mép mềm; viền mảnh theo đúng vùng sáng (`frame`, mặc định bật).
- Theo đúng vị trí/kích thước vật TỪNG KHUNG (track làm mượt đối xứng — không trễ); mất dấu → tắt ở khung đó (không chiếu nhầm mặt/tay/nền).
- Nhãn, đường dẫn, phụ đề nằm TRÊN lớp tối. Fade vào/ra ~0,24s. Chỉ trong đoạn cần tập trung (đúng lúc lời + động tác chỉ tay nói về sản phẩm).
- `product_terms` (vd ["khăn"]): check cảnh báo lời nhắc sản phẩm mà không có spotlight/viền/nhãn lúc đó (ngoại lệ hợp lý: lúc vật đang chuyển động chưa bám được).

## 1d. Sơ đồ minh họa ý (`role: "diagram"`)

- Khi lời giải thích một quy trình/khái niệm (và hình người nói không thêm thông tin), phủ một sơ đồ ngắn, các nút hiện ĐÚNG lúc lời nhắc tới:
  `{"role": "diagram", "title": "…", "at", "dur", "items": [{"text": "Video nguồn", "icon": "video-camera", "at": …}, …]}` — lời vẫn chạy bên dưới,
  trở lại người nói ở điểm phù hợp. Không chỉ hiện một chữ (“Thay thế”) rồi coi là xong. Không tự tạo cảnh trải nghiệm/công dụng không có trong nguồn.
- Không mặc định mọi lần nhìn khỏi camera đều phải cắt bỏ hay che — chỉ minh họa khi giúp hiểu ý.

## 1e. Chữ nhấn không chạm mặt/tóc

App tự chọn vị trí chữ nhấn (trên đầu → giữa trên → dưới mặt) theo khung mặt + tóc suốt thời gian hiện; QA file xuất báo lỗi nếu chữ nhấn/nhãn chạm mặt.

## 2. Thông tin (`texts[].role = "info"`)

- Tên sản phẩm/phiên bản, diện tích, công năng, giá, thông số — CÓ NGUỒN (lời người dẫn, brief, thông số người dùng gửi).
- Hiện khi hình tương ứng có mặt (nói phòng ngủ → nhãn khi đang thấy phòng ngủ). Thẻ gọn ở góc (dọc: trên trái; ngang: dưới trái).
- Không lấy số liệu từ video tham khảo. Nguồn mâu thuẫn → báo rõ trong báo cáo, KHÔNG tự chọn một giá trị rồi trình bày như chắc chắn.

## 3. Chữ nhấn (`texts[].role = "emph"`, `sub` = dòng nhỏ phía trên, `hl` = cụm tô màu)

- Hook, thông điệp, phản ứng, kết luận quan trọng — không animate mọi từ. Hiệu ứng theo mức thể hiện (styles.md).
- Đặt ở dải trên (không đè mặt/tay ở giữa khung). Câu kết đủ thời gian đọc (check chặn).

## Quy tắc chữ chung

- Đo bằng font thật; giữ liền tên riêng, thuật ngữ, số + đơn vị; tránh một từ ngắn rơi xuống dòng cuối.
- App kiểm chữ chồng nhau/cắt khung trên CHÍNH file xuất (trong lúc chuyển động).

## PiP / chia khung / callout

- PiP (`cutaways[].kind = "pip"`): hình nhỏ góc trên phải trong lúc vẫn thấy người dẫn — dùng khi cần đối chiếu (màn hình thao tác + người nói,
  swatch + mặt). Không bắt mọi cảnh có icon, bảng thông tin hay sơ đồ.
