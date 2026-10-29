# plan.mg2 — Motion Graphics bố cục + chuyển động (Talking Head, HyperFrames)

(Tự sinh từ thagent/mg2.py — không sửa tay.)

```
Motion Graphics thế hệ 2 cho Talking Head — cảnh có BỐ CỤC + CHUYỂN ĐỘNG (HyperFrames), nền đơn giản tinh tế.

plan.mg2 = [{"id", "kind", "start", "end" (frame timeline), "bg", "tone": "gold"|"blue"|"red", "colors": [c1, c2] (tuỳ chọn), …tham số}]
Cảnh 2.5–8s. App render mỗi cảnh một lần (HyperFrames, lưu đệm), ghép vào video; khổ dọc/ngang tự bố trí theo khung dự án.

Nền ("bg") — chỉ 6 kiểu đã duyệt (đơn giản, chữ dễ đọc; chọn 1–2 kiểu cho cả video, đổi màu theo chủ đề bằng "colors"):
  blur      video gốc làm mờ + tối (liền mạch với cảnh quay)      gradient  2 mảng màu loang trôi chậm + hạt grain
  cream     nền kem sáng, chữ tối (sạch, sang)                    charcoal  than chì tối + vignette + vệt sáng rất nhẹ
  dots      lưới chấm mờ dần ra mép                               spot      một màu chủ đạo + đèn rọi mềm sau nội dung
  none      không nền — CHỒNG lên người nói (chỉ cho iconrow, chips, custom kiểu chồng)

Kind (tham số):
  chart      value_from, value_to, suffix "%", label, title, sub, icon        — đồ thị tự vẽ, số chạy
  money      value_from, value_to, decimals, unit "tỷ" | prefix "$", locale "en" (2,000), title, sub, badge, icon — số tiền chạy + thẻ phụ
  notif      items [{icon, title, text}] (2–4)                                 — chồng thông báo trượt xuống
  question   image (ẢNH MINH HOẠ đúng ý câu hỏi — bắt buộc), lead "Câu hỏi:", text, sub, icon — thẻ câu hỏi: ảnh trong khung + dấu ? 3D
  photos     title, images [{src, label}] (1–3), note "Hình ảnh minh họa"      — ảnh xếp nghiêng có nhãn
  doc        title, heading, highlight, icon                                   — tài liệu, dòng quan trọng tô sáng
  iconrow    icons [3d:…] (3–5), lead, text                                    — hàng huy hiệu tròn bật lên trên đầu (bg none)
  chips      items [{icon, text}] (2–4), side "left"|"right"                   — chip nhãn cạnh người nói (bg none)
  compare    a {label, value, sub}, b {label, value, sub}                      — trước / sau
  checklist  title, items [text…] (2–5)                                         — tích từng mục
  ("at": [GIÂY tính từ đầu cảnh…, vd [0.5, 1.6, 2.8]] — KHÔNG phải frame — cho notif / iconrow / chips / checklist / photos;
   mỗi mục hiện đúng lúc nói, mục cuối hiện trước khi cảnh hết ≥ 0.8s)
  custom     html, css, js (GSAP: biến `tl`, `sel`) — Claude TỰ THIẾT KẾ theo chủ đề; dùng lớp sẵn .card .t1 .gold .blue .red .sub
             .chip .ic .sweep, biến --s (tỉ lệ khung), {{icon:3d:id}} → ảnh icon 3D. Giữ luật: nền đơn giản, ≤ 3 khối, chữ ≥ 34px×s.
Icon: "3d:<id>" từ kho chung, hoặc đường dẫn ảnh logo thật (nói tên phần mềm / app / hãng → BẮT BUỘC logo đúng, tải từ Wikimedia, lưu assets_web) (tra: python -m thagent.tools icon3d <từ khoá>) — chọn icon NHẬN RA NGAY đúng vật (giá nhà → nhà /
tiền giấy, không dùng túi tiền premium nhìn như quả bom). Ảnh: assets_web/ (luật ảnh như cảnh MG: đúng vật, nhãn minh hoạ, ≥1.8s).
Nhịp: video KHÔNG phải trình diễn vật → có MG khoảng mỗi 10s (preflight lỗi nếu nói > 12s không có MG, trừ đoạn trình diễn);
cảnh nền (≠ none) không nằm trong đoạn mở đầu / kết; mỗi video dùng ít nhất 4 kind khác nhau, không lặp kind liền nhau.
```
