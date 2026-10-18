# Quy tắc riêng từng lĩnh vực (v1.2.2)

Lĩnh vực lấy từ `options.json` → ghi `"category"` ở gốc edit.json. Một video nhiều ngành: ghi `"category"` ở TỪNG đoạn.
Giá trị: `bds` · `cong_nghe` · `my_pham` · `am_thuc` · `san_pham` (sản phẩm khác). App tự áp phần kỹ thuật (thư mục `thagent/review/niche.py`);
Claude chịu trách nhiệm mạch kể, chọn cảnh, chữ.

Phần chung vẫn giữ cho mọi ngành: cắt sạch, nhịp nói, khối số liệu, zoom có chủ đích, SFX nhẹ, check cắt dồn, phụ đề theo nghĩa.

## Công nghệ (`cong_nghe`) — điện thoại, laptop, ổ cứng, tai nghe…

- Mạch: mở hộp → thiết kế/cầm nắm → thông số → thử thực tế → kết luận ưu/nhược.
- Thông số (dung lượng, MB/s, mAh, inch, Hz, giá) → `stat`. So sánh A/B CÓ TRONG LỜI hoặc brief → khối `compare`:
  `{"role": "compare", "title": "So với đời trước", "cols": ["Máy mới", "Đời trước"], "rows": [["Màn hình", "6,7 inch", "6,1 inch"], ["Pin", "5.000 mAh", "4.500 mAh"]], "win": [1, 1], "at": …, "dur": 5–7}`
  (`win`: cột thắng từng hàng tô màu nhấn; 0 = không tô). Bản dọc: dải trên/dưới mặt; bản ngang: ô bên.
- Cận cổng/nút/chi tiết đúng lúc nhắc; quay màn hình → cutaway toàn khung hoặc PiP.
- Cấm: tự bịa kết quả đo/benchmark; dùng ảnh hãng hoặc máy khác thay cho máy đang review (cùng dòng khác đời cũng không).

## Mỹ phẩm – skincare (`my_pham`)

- Mạch: sản phẩm (bao bì, thành phần) → kết cấu (cận, swatch, nhỏ ra tay) → thoa lên da → cảm nhận → giá, dung tích.
- Thành phần + nồng độ (“Niacinamide 10%”), dung tích, giá → `emph`/`stat`. Cận kết cấu: spotlight/zoom đúng vùng tay/da.
- **Khoá màu**: app không nâng sáng, không chỉnh ấm (giữ đúng tông da, màu son/kem). Không làm mịn da, không lọc màu.
- **Công dụng** (quảng cáo mỹ phẩm có quy định):
  - chữ trên hình chứa hứa hẹn công dụng (“trị mụn”, “trắng da”, “xoá nám”, “sau 7 ngày”, “100%”, “cam kết”…) mà người nói KHÔNG nói → check LỖI (chặn);
  - lời người nói có khẳng định mạnh → check CẢNH BÁO: không nhấn thêm trên hình, ghi báo cáo “cần căn cứ”.
- Cấm: before/after tự tạo; ghép da người khác làm kết quả; thêm công dụng không có trong lời/brief có căn cứ.

## Ẩm thực (`am_thuc`) — quán, món, công thức

- Mạch: quán/món → cận món (hơi nóng, nước dùng) → thao tác (múc, rưới, thêm rau) → miếng ăn đầu tiên + phản ứng → giá, địa chỉ, giờ mở cửa → nhận xét.
- Giá món / giờ mở cửa / địa chỉ → `stat` hoặc `info`. Khoảnh khắc ăn thử giữ lâu hơn (≥ 1,5s), không cắt ngang lúc nhai.
- **Tiếng hiện trường**: cảnh minh hoạ có tiếng (xèo xèo, rót, cắn giòn) → app tự trộn −18 dB dưới lời (`"audio": "mute"` nếu tạp âm).
- Màu: app ấm nhẹ trung thực (`tone.warm` 0,04) — không đổi màu món, không tăng bão hoà quá.
- Cấm: ảnh/clip món không phải của quán; tự thêm lời khen; cảnh món khác loại (ramen thay phở…).

## Bất động sản (`bds`) / Sản phẩm khác (`san_pham`)

Như các bản trước (styles.md, edit-rules.md): BĐS đúng căn/đúng dự án, không ghép hai không gian; ngược sáng → nâng vùng tối nhẹ.
