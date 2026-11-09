# Quy tắc dựng chung (cắt, âm, phụ đề, hình, chuyển cảnh)

Rút từ quy trình EditAtlas (thử trên 15 phim thật), viết lại cho C-Cut. Áp cho mọi skill. Luật riêng của skill / người dùng luôn ưu tiên hơn file này.

## Quy trình
1. **Soi nguồn trước**: ffprobe (kích thước, fps, xoay, HDR, có tiếng không, tỉ lệ điểm ảnh) + ảnh ghép xem nội dung. Không đoán nội dung từ tên file, không sửa file gốc.
2. **Đổi mọi chữ cảm tính thành số** trước khi dựng: "nhanh" = bao nhiêu frame, "to" = bao nhiêu px, "nhỏ" = bao nhiêu dB.
3. **Dựng nháp độ phân giải thấp** từ danh sách chỉnh → kiểm → sửa danh sách → dựng lại; tối đa 3 vòng rồi mới dựng bản cuối.
4. **Kiểm trước khi đưa**: từng điểm cắt, đoạn đen / đứng hình, lặng, độ to, phụ đề. Báo cái đã đo và cái chưa đánh giá được.

## Cắt
- Cắt ở ranh giới từ, không cắt giữa từ; đệm 30–200 ms quanh từ.
- Khoảng lặng ≥ 400 ms là điểm cắt sạch nhất; khe < 150 ms rủi ro. Giữ khoảng ngừng mang ý nghĩa, giữ hơi thở tự nhiên.
- Fade âm 10–30 ms ở mọi mối nối để không lụp bụp. Tiếng cười / phản ứng để chạy hết.
- Câu nói lại nhiều lần: mặc định giữ lần sạch CUỐI CÙNG (thường là lần người nói đã sửa xong).
- Che jump cut bằng punch-in 110–125% (mắt ở 1/3 trên), trở về khung rộng ở ý kế tiếp — hoặc chèn b-roll.
- Giờ nguồn và giờ timeline tách riêng; phụ đề + lớp phủ dùng giờ timeline.

## Nhịp theo dạng video
| Dạng | Cấu trúc | Nhịp |
|---|---|---|
| Talking head | câu mở nêu lợi ích ngay → mỗi ý một đoạn → tóm + CTA | cắt lặng > 400 ms; đổi khung / chèn hình mỗi 4–8s |
| Short dọc | hook 3s đầu → nội dung nhanh → kết gọn hoặc vòng về đầu | cảnh 1–3s; 2–3s có thay đổi trên màn |
| Giải thích (explainer) | câu hỏi / vấn đề → từng bước, mỗi ý một khung → ví dụ → điều cần nhớ | hình đổi theo từng ý; số liệu giữ đủ lâu để đọc 2 lần |
| Review sản phẩm | câu phán / câu bất ngờ nhất trên cận sản phẩm → mở hộp, gọi tên bộ phận → 2–3 điểm, mỗi điểm một cận cảnh → 1 nhược điểm thật → phán + giá người review nói + CTA | 30–60s; 3–6s đổi khung / chèn cận sản phẩm; giữ sản phẩm đứng yên đủ để nhìn |
| Quảng cáo sản phẩm | vấn đề / hook → sản phẩm giải quyết → bằng chứng → giá / ưu đãi + kêu gọi mua | 15–30s; cảnh sản phẩm 1–3s; packshot cuối giữ 2–3s |
| Hướng dẫn màn hình | kết quả sẽ đạt → các bước đánh số → lỗi hay gặp → tóm tắt | cắt chờ tải; zoom vào vùng đang thao tác; dừng đủ ở mỗi kết quả |

Cấm chung: mở đầu bằng logo dài; giữ mỗi lời khen khi người review có nêu nhược điểm; thêm giá / thông số người nói không nói;
dùng stock thay cho chính sản phẩm / chuyến đi của người dùng; lộ mật khẩu, email, dữ liệu khách trong quay màn hình.
Kiểm chung: tắt tiếng xem — phụ đề còn hiểu được không; tắt hình nghe — lời còn khớp không; xem trên kích thước điện thoại.

## Âm thanh
- SFX ít, MỖI tiếng gắn với một thứ nhìn thấy trên hình.
- Chuỗi dòng tiêu đề vào liên tiếp: tiếng pop / tick / chime ngắn đúng frame dòng xuất hiện, thấp hơn giọng ~10 dB; tối đa 2–3 tiếng mỗi cụm tiêu đề, chỉ cho dòng quan trọng.
- Tiếng nhấn dưới giọng nói: chọn âm ngắn (< 0.5s hoặc 0.5–2s); tiếng impact dài là âm điện ảnh, không hợp nằm dưới lời.
- Âm thư viện không cùng mức: so LUFS, bắt đầu ~10 dB dưới giọng; âm có đỉnh > 0 dBFS phải hạ trước khi dùng.
- Nhạc nền: hạ 8–12 dB dưới giọng (ducking), fade 200 ms trước khi giọng vào; chọn bài gần đúng độ dài, kết ở cuối câu nhạc với fade 1–2s.
- Chuẩn hoá MỘT lần trên bản mix cuối: online ~ −14 LUFS (C-Cut hiện đặt ~ −16 LUFS, giữ theo app), true peak ≤ −1 dBTP.
- FFmpeg: `amix` tự hạ từng đầu vào trừ khi `normalize=0`; `adelay` cần `all=1`; clip không có tiếng phải thêm `anullsrc` trước khi `amix` / `acrossfade`.

## Phụ đề
- Lấy mốc từng từ rồi ĐỌC LẠI: máy chép lời hay sai tên riêng — không chắc thì hỏi / đưa vào confirm.
- Tối đa 2 dòng ~38–42 ký tự, ngắt theo nghĩa, hai dòng cân nhau; giữ mỗi cụm hết câu + 150 ms.
- Kiểu từng-từ-một cần ≥ 0.2s / từ mới đọc kịp; nói nhanh hơn → dùng kiểu cả cụm.
- Đo chữ bằng font thật trước khi đặt hộp / highlight từng từ (đếm ký tự bị lệch).
- Font phải có đủ dấu tiếng Việt, nếu không chữ tự rơi sang font khác mà không báo.
- Dọc 9:16: tránh 15% trên và 25% dưới (nút nền tảng). Đốt phụ đề SAU CÙNG để lớp phủ không che.
- Kiểu theo nền tảng: phim / phỏng vấn → phụ đề sạch hoặc có hộp; điện thoại → từng từ hoặc từ đang nói đổi màu; hội thoại nhanh → mỗi người một màu.

## Hình và chuyển động
- Mọi giá trị chuyển động là hàm của frame: không đồng hồ thật, không ngẫu nhiên không seed.
- Ưu tiên chuyển động có ease hơn tuyến tính; ưu tiên vật di chuyển hơn chỉ mờ dần. Đừng fade mọi thứ ở mọi nhịp.
- Mỗi khung một chủ thể chính; chữ trong vùng an toàn tiêu đề (90% khung + vùng an toàn nền tảng).
- Không thêm nhãn góc, bộ đếm, thanh tiến độ nếu người dùng không yêu cầu.
- Chắc chắn font đã nạp trước khi render.

## Chuyển cảnh (FFmpeg)
- `zoompan` làm rối fps / timebase: theo sau bằng `setpts=N/FRAME_RATE/TB` với fps thật, kiểm độ dài từng đoạn trước khi nối.
- `xfade` đòi cùng kích thước, fps, pix_fmt, timebase: đưa mỗi clip qua `scale, setsar=1, fps, format=yuv420p, settb=AVTB`.
- offset = độ dài đã có − độ dài chuyển cảnh; mỗi mối nối làm tổng ngắn lại. Crossfade âm cùng độ dài.
- Chuyển cảnh < 1 frame có thể cắt cụt video không báo lỗi; cắt thẳng thì dùng `concat` và so độ dài kết quả.
- Loé trắng: tối đa 3 lần / giây.

## Nguồn video
- Sửa tỉ lệ điểm ảnh trước (`scale=iw*sar:ih,setsar=1`); 4:3 đặt vào 16:9 bằng `pad`, không kéo dãn.
- Dò điểm cắt bằng `select='gt(scene,0.3)'` trước khi tin một mốc lấy từ thumbnail.
- Dọc từ nguồn ngang: crop 9:16 bám người; crop giữa làm mất người / chữ → dùng nền mờ (bản phóng to, mờ σ≈40, tối ~12%) + clip vừa chiều ngang.
- Stock: lấy file nhỏ nhất ≥ kích thước xuất (không upscale), chuẩn fps; soi như clip người dùng (hay dài, không tiếng, đổi cảnh giữa chừng). Ghi công tác giả.
