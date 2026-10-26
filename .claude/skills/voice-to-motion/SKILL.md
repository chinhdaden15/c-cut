---
name: voice-to-motion
version: 1.4.0
description: Dựng hoặc chỉnh sửa video motion graphic minh họa từ voice thu sẵn, ưu tiên tiếng Việt và bất động sản. Dùng khi người dùng yêu cầu biến file voice/audio thành video giải thích, infographic động, bản đồ/sơ đồ có diễn hoạt hoặc sửa một đoạn của video đã dựng. Tự phân tích, lập storyboard nội bộ, dựng, kiểm tra và xuất final mà không dừng duyệt. Không tự kích hoạt để tạo voice từ kịch bản, phân tích mẫu đơn thuần hoặc xây app khi chưa được yêu cầu.
---

# Voice to Motion

## Mục tiêu và phạm vi

Biến voice có sẵn thành video motion graphic diễn giải đúng nội dung. Dùng cách tổ chức thông tin của Người Quan Sát làm nền, phối typography và biến đổi shape theo các mẫu Rehman/Danush đã phân tích. Giữ nguyên nội dung và thứ tự lời nói; mặc định làm sạch voice như Talking Head (cắt vấp, lắp bắp, từ đệm, khoảng lặng thừa), tăng tốc khi được yêu cầu. Tự chạy đến final; không dừng duyệt transcript, storyboard hoặc đoạn thử.

Đây là hướng dẫn vận hành cho AI có công cụ dựng/render; không phải ứng dụng hoặc renderer đã được triển khai. Không tuyên bố cài đặt app, dựng xong video hoặc nghe được âm thanh nếu chưa thực hiện và kiểm chứng. Không giả lập thành công khi môi trường thiếu công cụ.

**Phiên bản 1.4.0** — xem `CHANGELOG.md`.

**Motion Graphics bố cục + chuyển động (v1.4.0, ưu tiên)**: cho số liệu, liệt kê, so sánh, câu hỏi, tài liệu, thông báo… dùng `s.mg(kind, t0, t1, …)` (mẫu dùng chung với Talking Head — định dạng `.claude/shared/schemas/talking-head-mg2.md`; bg mặc định "none" để thấy nền cảnh) thay vì tự xếp khối rời; `at=[giây…]` để từng mục hiện đúng lúc nói; `kind="custom"` khi cần thiết kế riêng theo chủ đề (html/css/GSAP). Mỗi video ≥ 3 mẫu khác nhau, không lặp liền nhau.
**Nền đơn giản (v1.4.0, bắt buộc)**: `K.scene(..., bg={"style": "gradient"|"charcoal"|"dots"|"spot"|"cream", "color": "#…", "color2": "#…"})` hoặc `theme.bg_style` — chọn 1–2 kiểu cho cả video, đổi màu theo chủ đề; "cream" chỉ với theme chữ tối. Không dùng nền nhiều chi tiết (skyline, nến chứng khoán, mạch…) — rối, khó đọc chữ.
**Icon 3D (v1.4.0)**: `"3d:<id>"` từ kho chung (`python -m thagent.tools icon3d <từ khoá tiếng Anh>`) cho icon lớn / mẫu MG; icon phải nhận ra ngay đúng vật (vd giá nhà → nhà / tiền giấy).

**Ảnh & b-roll (v1.3.0, bắt buộc)**: xen ảnh thật và video b-roll (bo góc, thu nhỏ) giữa icon/sơ đồ; ảnh phải ĐÚNG CHÍNH XÁC nghĩa đen và bối cảnh (nhất là giáo dục, BĐS, y tế, tài chính), tự kiểm từng ảnh; chủ thể có thật chỉ dùng ảnh thật — `references/images-and-broll.md`.

**Nhịp theo lời (v1.2.3, bắt buộc)**: cảnh 4–8s, ≤ 3s một thay đổi hình theo từ khóa, mỗi ý có hình bổ nghĩa, không khung trống, khối sống nhẹ, phụ đề chạy theo lời — `references/motion-system.md` §6; check chặn lỗi.

**Bản đồ & camera (v1.2.2, bắt buộc)**: camera có diễn tiến Establish → Focus → Explain → Resolve; lãnh thổ tô dần theo ranh giới thật; mỗi nước một màu, tên trắng viền tối; dẫn mắt bằng tô/halo + giảm nhấn; ý không gắn vị trí → cảnh đồ họa riêng; không bao giờ lặp quốc gia trong khung — chi tiết `references/maps.md` §5, `references/motion-system.md` §3a.

**Bộ khung dựng sẵn** (`templates/build_timeline.py` + `thagent/v2m/kit.py`): LUÔN bắt đầu bằng cách chép khung này vào dự án, chỉ thay phần nội dung (cảnh, khối, mốc lời). Bố cục dọc/ngang, cỡ chữ, callout, camera bản đồ do kit tính — không tự đặt toạ độ.

**Thư mục**: mỗi file âm thanh/video ở cấp ngoài cùng = MỘT video riêng (không có trường hợp nhiều file thành một nội dung); mỗi file xuất dọc + ngang (hoặc theo tỷ lệ người dùng dặn). Ảnh ở thư mục gốc và mọi file trong thư mục con (b-roll, ảnh trám) = tư liệu dùng chung, app chép vào `tu_lieu/` của từng dự án kèm ảnh xem trước `tu_lieu/_xem/`.

**Đầu vào**: file âm thanh (mp3, wav, m4a, aac, flac, ogg) dựng bình thường; **file video** (mp4, mov, mkv…) → chỉ lấy tiếng (`init` tách audio, bỏ hình) khi người dùng chọn Voice to Motion.

**SFX** (`references/sound-design.md`): kho riêng `assets/sfx_v2m` (âm thật từ thư viện của người dùng, 15 vai trò); mặc định renderer tự gắn SFX theo chuyển động thật của từng bản, có thể khai báo tay theo vai trò.

**Voice** (`references/voice-cleanup.md`): mặc định làm sạch như Talking Head — `clean` cắt vấp, lắp bắp, từ đệm, khoảng lặng thừa (giữ nguyên nội dung và thứ tự câu); “giữ nguyên voice” → `restore`. Tăng/giảm tốc: `speed <dự-án> 1.1` (giọng giữ cao độ).

**Định dạng đầu ra** (`references/formats.md`): **mặc định xuất CẢ dọc 9:16 (1080×1920) lẫn ngang 16:9 (1920×1080) trong một lượt** — luôn viết `timeline_9x16.json` và `timeline_16x9.json`, rồi `render <dự-án>` (hai bản dựng song song, QA riêng từng bản).
- “Dựng dọc” → chỉ `render <dự-án> 9x16` · “Dựng ngang” → chỉ `render <dự-án> 16x9` · “Xuất cả dọc lẫn ngang” / không nói gì → `render <dự-án>`.
- Mỗi tỷ lệ có bố cục riêng (`timeline_9x16.json`, `timeline_16x9.json`) viết từ một builder dùng `thagent.v2m.layout.Frame(fmt)`; không kéo giãn/crop/viền đen. Renderer thực thi skill: `thagent/v2m` (`references/renderer-api.md`).

Đọc trước khi dựng, theo thứ tự:
1. `references/style-and-motion.md` — phong cách nền.
2. `references/layout-typography.md` — vùng khung, **xuống dòng theo nghĩa tiếng Việt (bắt buộc)**, hệ thống chữ, bộ hiệu ứng chữ.
3. `references/motion-system.md` — pha của cảnh, easing, camera, chuyển cảnh dựa trên đối tượng chung.
4. `references/contrast-shape-illustration.md` — tương phản, shape, chọn cách minh họa theo loại ý (không mặc định một câu = một icon).
5. `references/maps.md` — khi có bản đồ: nguồn dữ liệu, lớp, LOD theo zoom, nhãn gắn tuyến, Hoàng Sa – Trường Sa.
6. `references/sound-design.md` — vai trò từng SFX, mật độ, giới hạn nghe.
7. `references/formats.md` — dọc/ngang: vùng bố cục, camera bản đồ theo tỷ lệ, câu lệnh của người dùng.
8. `references/voice-cleanup.md` — làm sạch voice (cắt vấp/lặng) và tốc độ.
9. `references/case-studies.md` — các lỗi đã gặp và nguyên nhân thật; dùng làm ca kiểm tra.

Đọc `references/style-and-motion.md` trước khi dựng. Đọc `references/timeline-and-qa.md` khi lập timeline, kiểm tra hoặc sửa video. Đọc `references/real-estate-assets.md` nếu nội dung liên quan dự án, địa điểm, bản đồ, mặt bằng hay số liệu. Dùng `references/test-script.md` chỉ khi người dùng yêu cầu bài thử; không thay thế voice thật bằng kịch bản mẫu. Khi được yêu cầu xây app thực thi skill, đọc thêm `references/app-contract.md`.

## Đầu vào và mặc định

- Nhận file âm thanh (WAV/MP3/M4A/AAC/FLAC/OGG) hoặc file video (chỉ lấy tiếng); kiểm tra định dạng thực tế, thời lượng, số kênh và khả năng giải mã.
- Nhận tùy chọn: transcript chuẩn, ảnh/video dự án, bản đồ, logo, font, màu thương hiệu, nguồn số liệu, tỉ lệ khung hình và thư mục dự án cũ.
- Nếu thiếu voice, chỉ yêu cầu file voice. Không tự tạo TTS: tạo giọng đọc thuộc giai đoạn 2, cần yêu cầu riêng.
- Mặc định xuất hai bản: dọc 9:16 1080×1920 và ngang 16:9 1920×1080, 30 fps, MP4 H.264/AAC (chỉ một bản khi người dùng nói “Dựng dọc”/“Dựng ngang”); coi đây là mặc định triển khai có thể đổi, không phải thông số đã đo từ video mẫu.
- Dùng tiếng Việt đúng dấu. Ưu tiên font người dùng cung cấp; nếu không có, chọn font tiếng Việt có quyền sử dụng và thực sự có trong môi trường. Không đoán tên font gốc từ ảnh raster.
- Chọn một palette thống nhất cho cả video. Chọn tối đa hai họ font, dùng weight/style để phân cấp. Không đổi màu thương hiệu tùy tiện giữa các cảnh.
- Chỉ xuất file; không tự đăng mạng xã hội. Tuân thủ giới hạn chi phí/công cụ của môi trường. Chế độ tự động không thay thế các quyền truy cập hoặc xác nhận bắt buộc của nhà cung cấp.

## Quy trình tự động

### 1. Kiểm tra năng lực và nguồn

Xác định công cụ có thể thực sự đọc media, nhận dạng tiếng nói, tạo/nhập tài nguyên, dựng layer và render. Ưu tiên renderer có timeline và đối tượng chỉnh sửa được. Không dùng mô hình sinh video để vẽ chữ, logo, bản đồ hay biểu đồ cần chính xác. Có thể dùng công cụ sinh ảnh cho minh họa khái niệm được phép, theo hướng dẫn công cụ đang có.

Nếu có pipeline khả dụng, chạy đến final. Nếu không có renderer hoặc quyền thực thi cần thiết, báo chính xác thành phần thiếu, giữ lại storyboard/tài nguyên đã làm và không gọi bản kế hoạch là video hoàn chỉnh. Không tự xây một app lớn khi người dùng chỉ yêu cầu dựng video.

### 2. Đọc voice và chia ý

Tạo transcript có thời gian theo từ/cụm; đối chiếu transcript người dùng nếu có. Kiểm tra tên dự án, địa danh, đơn vị, số tiền, phần trăm, từ phủ định và điều kiện. Không lấy lỗi ASR làm nội dung đúng. Nếu chưa xác minh được chữ, tránh dùng chữ đó làm headline và ghi lại giới hạn; giữ voice nguyên trạng.

Chia voice thành các nhịp ý: giới thiệu, liệt kê, so sánh, quy trình, nguyên nhân, bằng chứng, kết luận. Giữ câu nói và thứ tự gốc. Chỉ cắt bằng `clean` (vấp, lắp bắp, từ đệm, khoảng lặng thừa — xem `references/voice-cleanup.md`); không bỏ câu, không xếp lại hook, không tự tăng tốc khi người dùng không yêu cầu. Tạo sức hút mở đầu bằng hình, text và chuyển động trong đúng lời mở đầu có sẵn. Không tự thêm CTA hoặc lời khẳng định ngoài voice.

### 3. Lập storyboard nội bộ

Cho mỗi đoạn, ghi: ý nghĩa, từ/cụm neo thời gian, hình thức minh họa, trạng thái đầu, chuỗi hành động, trạng thái cuối, bố cục, tài nguyên, camera, text, âm thanh và nối cảnh.

Chọn hình thức dựa trên quan hệ cần giải thích:
- Liệt kê: thẻ/nút xuất hiện tuần tự trong bố cục có sẵn chỗ trống.
- So sánh: hai đối tượng trên cùng tiêu chí; giữ nền và thang đo nhất quán.
- Quy trình/dòng di chuyển: các nút và đường đi có hướng rõ ràng.
- Địa lý: bản đồ thật, điểm và tuyến có căn cứ.
- Số liệu: biểu đồ có đơn vị, nguồn; phân biệt số liệu thật với minh họa khái niệm.
- Nhấn ý trừu tượng: chữ nhấn và ẩn dụ hình ảnh phù hợp.

Thiết kế cảnh theo diễn tiến của ý thay vì thay hình ngẫu nhiên theo từng từ. Với các ý liên quan, giữ cùng không gian và di chuyển tiêu điểm. Không ép mọi câu vào cùng một template. Không bắt buộc nhồi cả ba phong cách trong clip ngắn.

### 4. Chuẩn bị tài nguyên

Lập manifest tài nguyên: id, loại, nguồn, tác giả/quyền dùng nếu biết, quan hệ với nội dung, trạng thái xác minh và nơi dùng. Ưu tiên file người dùng cung cấp và nguồn chính thức. Thực hiện chính sách trong `references/real-estate-assets.md`.

Khi thiếu tài nguyên thật, tìm nguồn phù hợp bằng công cụ khả dụng. Nếu chưa xác minh được, thay bằng text hoặc sơ đồ khái niệm trung tính; bỏ phần minh họa mang tính khẳng định chưa có nguồn. Ghi vào báo cáo cuối, không tự tạo dự án, tọa độ, đường đi, giá hoặc chứng cứ.

### 5. Dựng hình và motion

Tạo các đối tượng riêng: text, shape, ảnh, mask, đường nối, bản đồ, biểu đồ, camera. Giữ ID ổn định để sửa sau này. Dựng bố cục tĩnh trước, rồi diễn hoạt từng bước và kiểm tra ở trạng thái bắt đầu/giữa/kết thúc.

Gắn chuyển động vào thời điểm voice nhắc ý; dành đủ thời gian giữ cho người xem hiểu. Dùng chuyển động shape/camera có liên hệ giữa hai cảnh. Dùng nhòe khi đang di chuyển nhanh, đưa chữ về rõ nét ở trạng thái đọc. Hạn chế flash và rung; ưu tiên khả năng đọc và mạch giải thích.

Đối với clip chỉ voice, dùng toàn bộ khung để kể chuyện. Không tự thêm người dẫn. Nếu người dùng có người thật trong cảnh: text/hình trên đầu nằm sau lớp nhân vật; text/hình từ ngực xuống nằm trước; tránh che mặt, miệng và dữ liệu cần đọc.

### 6. Âm thanh

Giữ voice làm lớp ưu tiên. Không đổi cao độ/âm sắc giọng; chỉnh nhịp chỉ qua `clean` (cắt vấp/lặng) và `speed` (khi được yêu cầu). Luôn giữ bản gốc.

Gắn SFX vào sự kiện có chủ đích: bắt đầu chuyển cảnh, đối tượng đến vị trí, từ khóa nhấn, đường nối hoàn tất. Chọn âm thanh có quyền sử dụng và đã kiểm tra. Không gắn SFX vào mọi từ hoặc mọi đối tượng. Để khoảng nghỉ và tự động giảm nhạc nền dưới voice nếu dùng nhạc. Kiểm tra peak, clipping và chồng âm; không khẳng định cân bằng âm nghe tốt chỉ từ waveform.

Chưa có xác minh nghe trực tiếp SFX của bốn video tham khảo. Coi whoosh/click/pop/impact là đề xuất thiết kế, không phải bản sao âm thanh đã nhận dạng. Nếu môi trường không nghe được, kiểm tra kỹ thuật được đến đâu ghi rõ đến đó, không bịa nhận định âm sắc.

### 6b. Quy tắc cứng v1.1 (renderer + QA đã thực thi)

- Chữ: đặt `max_w` + `keep` cho thuật ngữ/tên riêng; renderer ngắt dòng theo nghĩa ở cỡ gốc rồi chốt; `word_times` đủ mốc cho mọi từ.
- Mỗi cảnh: xuất hiện → hành động/nhấn mạnh → tiếp nhận → chuyển tiếp; các bước chồng thời gian; khoảng dừng để đọc là chủ đích (không drift giả).
- Một trọng tâm thị giác mỗi cảnh; nhánh được chọn → dựng lại thành cảnh chi tiết, không zoom cả sơ đồ cũ.
- Bản đồ: nhãn có `lod`; tên tuyến dùng `routelabel`; tuyến đang nói nổi bật, tuyến cũ giảm nhấn; hai tuyến gần nhau khác ≥ 2 thuộc tính.
- Chữ trên bản đồ/ảnh: `plate: "auto"`. Không hộp màu gần nền.
- Không biểu đồ/cột gợi tỷ lệ khi không có số; không sơ đồ vòng khi quan hệ không phải vòng; không trình bày lời quảng bá như lời chứng thực khách hàng.
- SFX theo vai trò (click điểm đến, whoosh chuyển vùng, impact thông điệp), không cho mọi từ.

### 7. Tự kiểm tra, sửa, xuất

Chạy `check <dự-án>` → `check --deep` → `render`; đọc `qa.json`; xem `sheet.jpg` và ảnh liên tiếp quanh chuyển cảnh. Lỗi chặn bàn giao liệt kê trong `references/timeline-and-qa.md`. Lặp sửa – dựng tới khi `qa.json.status` đạt và không còn lỗi khi xem bằng mắt.

Áp dụng `references/timeline-and-qa.md`. Render preview nội bộ, kiểm tra và sửa lỗi có bằng chứng; không đưa bước duyệt thành điểm dừng. Xuất MP4 chỉ khi renderer hoàn tất và file giải mã được. Giữ dự án có thể chỉnh, timeline, transcript và manifest cùng phiên bản đầu ra.

Gửi final kèm mô tả ngắn và các giới hạn thực sự còn tồn tại. Không tuyên bố mọi kiểm tra đều đạt nếu chưa thực hiện. Nếu lỗi chặn tính đúng đắn còn tồn tại, ghi trạng thái chưa hoàn tất và giải thích cụ thể.

## Sửa theo câu tự nhiên

Nhận yêu cầu như “15–20 giây chữ nhỏ”, “giảm SFX”, “đổi cảnh này sang bản đồ”. Ánh xạ vào scene/object ID và khoảng thời gian; giữ các phần không bị ảnh hưởng. Tăng phiên bản, lưu bản trước, cập nhật manifest/timeline và render lại. Không chép đè voice gốc. Chỉ hỏi lại khi tham chiếu mơ hồ có thể gây sửa nhầm quan trọng; các lựa chọn thiết kế thông thường tự quyết định.
