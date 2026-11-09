# Ý tưởng hình theo lời: biến câu nói thành một vật có diễn biến

Rút từ ~80 mẫu dựng talking head 9:16 (EditAtlas, 11/2026), viết lại cho C-Cut. Dùng cho Talking Head (callout / stage / mg2 `custom` / plan.hf),
Voice to Motion và Text to Video (`s.mg("custom")`, HyperFrames).

## 1. Nguyên lý cốt lõi (khác hẳn kiểu "đặt icon cho có")
1. **Mỗi ý chính = MỘT VẬT ẨN DỤ có diễn biến**, không phải một thẻ chữ + icon. Vật đó *biến đổi theo đúng từng từ* người nói:
   pin tụt dần theo các ngày trong tuần → "kiệt sức" thì pin nứt, bốc khói; lịch 7 ngày → "cuối tuần" sáng T7/CN → "buổi tối" chuyển đêm.
2. **Neo vào TỪ, không neo vào giây.** Mỗi trạng thái của vật đổi đúng frame đầu của từ khoá (tra `words`). Một cảnh thường có 3–5 "nhịp đổi" theo từ.
3. **Chỉ một vật chính / một lúc**, đặt ở khoảng trống: dưới cằm (kết thúc trước dải phụ đề), hai cột bên, hoặc sau đầu (chỉ khi có alpha người tốt).
4. **Diễn biến có kết**: vật phải đi tới một trạng thái "chốt" (đóng dấu, tick xanh, số dừng, vỡ, rơi, khoá) trùng câu chốt, rồi rời đi gọn.
5. **Không bịa**: mọi chữ / số trên vật lấy từ lời nói hoặc brief. Không có số → không vẽ số. Giao diện giả (app, web, thông báo) không mang logo / font của thương hiệu thật.

## 2. Thư viện ý tưởng theo loại câu nói
Cột "Diễn biến" ghi từ khoá → trạng thái. Dùng làm điểm xuất phát rồi đổi vật theo lĩnh vực của video (BĐS, sức khoẻ, ẩm thực…).

### Con số, giá, chỉ số
| Ý tưởng | Diễn biến theo lời |
|---|---|
| Bảng lật sân bay | mỗi con số được nói → hàng ô lật qua ký tự ngẫu nhiên rồi dừng trái → phải, ô vừa dừng loé vàng; giữ ≥ 1s để đọc |
| Đồng hồ công-tơ-mét kính | số cuộn từng cột lên đúng giá được nói; sau đó thẻ phụ trượt vào trả lời ý kế |
| Số khổng lồ bị gạch | "rất lớn" → 1.000.000 to sau đầu, camera lùi nhẹ; "chỉ vài trăm" → gạch đỏ, điện thoại trồi lên, số người theo dõi cuộn tới con số thật |
| Bảng phấn tính toán | bảng xanh trượt lên dưới cằm, viết từng nét phép tính đúng lời (`2h × 20$ = 40$`), bụi phấn mỗi nét |
| Hoá đơn in nhiệt | tờ hoá đơn đẩy lên từ đáy, gõ từng mục được kể, dòng cuối in phương án đắt rồi gạch bỏ |
| Biểu đồ tròn biến hình | vòng tròn quét từ tỉ lệ cũ sang tỉ lệ mới, số giữa đếm theo; đồng xu rơi vào phần tăng |
| Mưa nhãn giá | sản phẩm rơi lên kệ dưới cằm → nhãn giá rơi hai bên, đung đưa trên dây; tổng "ĐÃ CHỐT" chạy lên |
| Biển báo đường | biển xanh "VĂN PHÒNG · 30 PHÚT" lật sang 45 → "1 GIỜ" đỏ khi kể việc đi trễ; bảng gạch đếm giờ trên tường |

### Thời gian, công sức, kiệt sức
| Ý tưởng | Diễn biến |
|---|---|
| Pin cạn | pin dưới cằm tụt 100% → vàng → đỏ theo các ngày được kể; chip giờ chạy tới số giờ; "kiệt sức" → pin nứt, khói, khung ngả đỏ |
| Dải lịch 7 ngày | "cuối tuần" sáng T7/CN; "buổi tối" khung + dải chuyển đêm có sao; việc rơi vào các ô tối; chốt gập thành "1 / tháng" |
| Lưới tuần cháy | lưới tuần mở trên đầu, ngày nghỉ sáng → mọi ngày kín → huy hiệu 80h đỏ → lưới cháy thành tàn; "đừng làm thế" xoá sạch |
| Vòng chờ tải | đồng hồ trên tường thành vòng xoay chờ; phòng tối dần; thẻ dự án kẹt ở % thấp; "bực mình" vòng đỏ + 3 tin nhắn giục |
| Băng VHS tạm dừng | khung như băng gia đình: PLAY + bộ đếm; "đau" → thanh máu đỏ + nhiễu; "nghỉ" → PAUSE; "hồi phục" → thanh đầy, REC |

### Thất bại, cảnh báo, từ chối
| Ý tưởng | Diễn biến |
|---|---|
| Con dấu phán quyết | chữ KHÔNG đóng mực đúng từ "không" + rung khung + tóe mực; sau đó biểu đồ kính vẽ độ khó giảm dần |
| Chồng thông báo rơi | 10 thông báo "đã gửi" chồng nhanh dần; "không ai trả lời" → cả chồng rơi, bộ đếm về 0, khung mất màu |
| Tắt đèn – đèn neon | từ trầm → đèn phòng tắt chớp; camera lùi vào tối; biển neon sau lưng bật từng chữ |
| Cửa cuốn đóng | "khách lớn" → chữ vàng to sau đầu; "vấn đề" → rút màu; "đóng cửa" → cửa cuốn kéo xuống sau lưng, biển ĐÓNG CỬA đung đưa |
| Rớt hạng / glitch | biểu đồ đang lên → thanh "CẬP NHẬT" xé ngang, tách RGB → "tụt hạng" đường gãy xuống, huy hiệu #1 rơi, hình cắt lát |
| Tan thành bụi | các yêu cầu phát sinh bò quanh người; hoá đơn QUÁ HẠN + số ngày tăng; "biến mất" → người tan trái → phải thành bụi |

### So sánh, lựa chọn, chuyển đổi
| Ý tưởng | Diễn biến |
|---|---|
| Hai vòng giao nhau | camera lùi; vòng BẠN và KHÁCH trượt vào từ hai bên, chồng nhau đúng từ "gặp nhau", phần chung sáng + pháo giấy |
| Rút lá bài | xấp đề xuất trồi lên → xào khi nói "lọc" → xoè → một lá viền vàng nhấc lên đúng "lợi thế", các lá khác xám |
| Thẻ biến hình | hai thẻ A vs B; "biến dịch vụ thành sản phẩm" → thẻ B vào giữa, đổi chữ từng ký tự, đổi icon + màu |
| Lột lớp vỏ | "công ty" → tường xám + logo, người cũng xám; "phía sau" → góc tường cong lên; "là chính bạn" → lột như sticker, bảng tên rơi xuống |
| Công tắc chế độ | công tắc lật A → B; sticker "chỉ làm thêm" bị đóng dấu KHÔNG NGHIÊM TÚC rồi bóc; danh thiếp chức danh xoay qua mọi vai |
| Thanh trượt quy mô | thanh trượt vung tới "hàng trăm người" rồi bật về, khoá vùng "3–4 người"; ghim MỤC TIÊU rơi xuống |

### Danh sách, bước, kế hoạch
| Ý tưởng | Diễn biến |
|---|---|
| Checklist kính | mỗi bước được nói → viết ra + vòng tròn đầy thành tick; vòng tiến độ 1/3 → 3/3 |
| Ghép hình | các mảnh (tên từng phần) trôi vào lệch → "khớp" thì ráp lại → "trơn tru" sóng sáng chạy qua mối nối → tick |
| Tường giấy nhớ | bảng "hôm nay: không có gì" → giấy nhớ chồng lộn xộn → "lập kế hoạch" thì nhảy vào 3 cột CẦN LÀM / ĐANG / XONG |
| Bento chia ô | khung người gập vào một ô bo góc của lưới bento; các ô khác hiện đúng thứ được nói (vòng %, khối dựng, dòng code) |
| Máy quay xèng | máy xèng dưới cằm quay ra mã mẹo; "nói không" → ra N-O-!, đèn chạy, băng rôn MẸO THƯỞNG |
| Danh sách giá trị | tiêu đề dựng dần, mỗi mục là một hàng đánh số màu + icon riêng; số đếm 1/5 → 5/5; giá nói cuối, chữ nhỏ |

### Kết nối, mạng lưới, hành trình
| Ý tưởng | Diễn biến |
|---|---|
| Mạng vai trò | mỗi vai được nói thành một nút kính quanh người, dây nối chạy sau đầu; "chuyển việc" → gói dữ liệu chạy trên dây; chốt cả lưới sáng |
| Chòm sao | "một mình" → phòng tối, một ngôi sao nhấp nháy cạnh đầu; mỗi mối quan hệ một sao + đường nối; sao băng mang việc giữa hai nút |
| Bản đồ hành trình | phòng mờ thành bản đồ chấm; đường bay nét đứt vẽ qua đầu, máy bay bay sau lưng; "tự do" → thẻ lên máy bay + dấu DUYỆT |
| Vòng lặp mũi tên | hai mũi tên vòng chở hai vật; "cái nào trước" → quay nhoè + dấu hỏi nảy; "không ai biết" → dừng, dấu nhún vai |
| Đội hai người | hai avatar dưới cằm; vai người kia đổi liên tục; "hợp tác" → cầu nối; "chuyền việc" → thẻ dự án bay qua lại |

### Phát triển, thành tựu, kêu gọi
| Ý tưởng | Diễn biến |
|---|---|
| Lên cấp game | HUD cấp + thanh XP + ô kỹ năng; "luôn thay đổi" → huy hiệu MỚI; "nâng cấp" → thanh XP đầy, tia vàng sau lưng, LÊN CẤP |
| Tìm kiếm – xếp hạng | thanh tìm kiếm gõ chủ đề, kết quả hiện, trang của người nói ở #9 → "viết nội dung" → kéo lên #1 viền vàng |
| Form tự điền | thẻ đăng ký tự điền theo lời: nút bấm, tiểu sử tự gõ, ảnh đại diện tải lên, "ứng tuyển" → 3 nút bay vào danh sách ĐÃ GỬI |
| Con trỏ bấm | trang web dưới cằm; đồng hồ thời gian xem chạy; "bấm quảng cáo" → con trỏ lao từ ô này sang ô khác, mỗi lần bấm gợn sóng + "+$" |
| Dốc đà (CTA) | quả bóng #1 trên dốc; "bắt đầu lăn" → bóng chạy; hai chữ KINH NGHIỆM / TỰ TIN rơi hai bên; "ĐÀ" → bóng phóng + vệt tốc độ → nút CTA được bấm |
| Lồng mở | song lồng đồng chắn khung + ổ khoá "9–5"; "muốn hơn" → khoá rung; "tự do" → khoá bật, song cong rồi bay ra, chim bay lên, phòng ấm lại |
| Tài liệu bay vào web | xấp tài liệu xoè trên tường; "đưa lên web" → từng trang xoay theo cung vào trình duyệt, đáp thành thẻ lưới; dấu tick xanh |

### Biến đổi cả khung (dùng tiết chế: hook, câu bẻ lái)
| Ý tưởng | Diễn biến |
|---|---|
| Chữ tượng đài | một từ thành chữ khối đùn 3D sau người; đổi chất liệu theo từng câu (đá, bùn chảy, nứt, vàng) |
| Đám đông bản sao | "tất cả mọi người" → phòng sau lấp đầy bản sao xám lệch nhịp; người nói vẫn sáng + màu, mũi tên vẽ tay "bạn" |
| Sân khấu đèn rọi | phòng tối như sân khấu; hai đèn quét tới đúng "chính mẹo này" → khoá vào người + loé; chữ phát sáng trên đầu |
| Bản vẽ kỹ thuật | phòng thành giấy blueprint, người vẫn màu thật; sơ đồ tổ chức vẽ quanh người; chốt mọi ô lật thành "BẠN" |
| Trang truyện tranh | khung halftone + viền mực, ô chen cảnh, chữ nổ "KHÔNG!" đỏ, hộp dẫn "Trong khi đó…" |
| Poster sticker | người thành sticker cắt viền trên poster cam halftone; dải máy in nhãn in tên; dấu hỏi dán lên |
| Phim cũ → màu | quá khứ chỉnh như phim cũ (sepia, hạt, viền tối) + bảng clapper góc; cắt sang hiện tại thì màu trở lại |

### Dựng theo nhịp cắt (review, ẩm thực, sản phẩm — không có người nói vào máy)
- **Cắt dập nhịp**: mỗi cắt trúng phách, zoom giật ngắn + nghiêng xen kẽ + tách RGB 2 frame; cách một cắt thêm loé trắng.
- **Lia nhanh giấu cắt**: cảnh cũ trượt đi nhoè chuyển động, cảnh mới vào từ phía đối diện rồi dừng.
- **Một động từ mỗi cảnh**: một động từ chữ thường nghiêng trồi lên từ mặt nạ đúng lúc cắt, gạch mảnh màu nhấn, rời ở cắt sau.
- **Chú thích đường dẫn**: vòng trắng mảnh đáp lên chi tiết, đường kẻ tóc chạy tới nhãn chữ hoa giãn cách + dòng nghiêng ghi chú.
- **Chữ rỗng đập vào**: mỗi cảnh một từ hành động, chữ viền đặc hẹp đập vào → nhịp sau tô đầy vàng + rung nhẹ.
- **Vệt sáng mặt kính / loé phim**: vệt phản chiếu chạy qua sản phẩm bóng đúng phách; hoặc loé sáng phim ấm mỗi cắt thứ hai + hạt.

## 3. Cấu trúc một mẫu (khi tự thiết kế cảnh dài)
- **Nhịp tỉ lệ**: mở (~10%: vật chính đập vào đúng từ khoá) → thân (~65%: mỗi ý một trạng thái / một đạo cụ) → khép (~25%: trạng thái chốt, dọn sạch).
  Nhịp tuỳ chọn không đủ điều kiện (người nói không nhắc) → bỏ, chia thời gian cho nhịp bắt buộc.
- **Mỗi nhịp ghi**: từ neo · trạng thái vật · 0–1 SFX (UI pop / clink / whoosh nhẹ / impact sâu) · lỗi có thể gặp + cách xử lý.
- **Kiểm chốt** (trước render): mọi chữ / số khớp lời; không gì ra ngoài vùng an toàn quá 1 frame; không gì che mặt;
  chữ đặt sau người không bị che quá 1/4 thời gian hiện; không lộ chữ in sẵn của nguồn; mix ≤ −1 dBTP.

## 4. Luật đặt quanh người nói (9:16, khung 1080×1920)
- Vùng an toàn ≈ x 60–960, y 240–1480 (chừa nút nền tảng + dải phụ đề). Vật dưới cằm phải kết thúc trước ~y 1300 để không chạm phụ đề.
- Chữ đặt SAU người: nếu đầu / thân che quá ~1/3 → dời sang tường trống, hoặc lùi camera từ mép dưới (lấp phần trống bằng bản mờ tối của chính khung), hoặc đưa ra trước.
- Alpha người nhấp nháy ở tóc / tay / kính → bỏ lớp sau-người ở khoảnh khắc đó.
- Khung quay quá chặt: thu khung người thành một ô (bento) hoặc lùi từ mép dưới với nền mờ.
- Nguồn có chữ in sẵn: che dòng dưới bằng dải kính mờ đúng thời gian; chữ đè ngang mặt → giữ frame sạch liền kề + loé trắng ngắn.
- Mỗi video chọn MỘT phong cách chữ / màu cho cả clip, không đổi giữa chừng.

## 5. Chưa nên dùng nếu người dùng không yêu cầu
Thanh tiến độ, bộ đếm góc, nhãn chương (Talking Head Style đã cấm), giao diện giả mạo thương hiệu thật, và hiệu ứng che mặt người nói.
