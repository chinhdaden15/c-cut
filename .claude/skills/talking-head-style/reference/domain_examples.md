# Ví dụ ngắn ngoài BĐS — cùng cấu trúc, khác nội dung

`design_example.py` / `design_mg_example.py` là video BĐS: **chỉ học cấu trúc và nhịp** (nhóm chữ, lớp, zoom, SFX, cảnh MG),
không chép chữ, ảnh, icon của nó. Mỗi video mới: xác định lĩnh vực + khán giả + chủ thể trước, ghi `confirm.json` id=`domain`.

## Y tế — “3 sai lầm khi uống vitamin D” (khán giả: người đi làm 25–45)

```python
# (id, lớp, tông, start, end, lead(text, near), main(TEXT, size, at), pill, element)
("g01", BACK, "red",  0.4, 3.0, None, ("3 SAI LẦM", 150, 0.6), None, None),           # tiêu đề sau đầu
("g02", FRONT, "gold", 3.2, 6.0, None, ("SAI LẦM 1", 120, 3.3), None, None),           # liệt kê: KHÔNG dòng dẫn
("g03", FRONT, "red",  6.1, 9.4, ("uống lúc", 6.2), ("BỤNG ĐÓI", 130, 6.9), None, "pills"),
("g04", FRONT, "gold", 9.6, 13.0, ("chỉ cần", 9.7), ("1 VIÊN/NGÀY", 130, 10.2), None, None),   # số liệu cả cụm
("g05", FRONT, "blue", 13.2, 16.5, ("uống cùng", 13.3), ("BỮA CÓ CHẤT BÉO", 110, 13.9), None, "utensils"),
```
- Ảnh MG: minh họa i_* bối cảnh phòng khám / bữa ăn (Unsplash), nhãn “Hình ảnh minh họa”. Ảnh lọ thuốc thương hiệu cụ thể → w_* từ trang chính hãng.
- Không sinh AI ảnh sản phẩm; không lấy ảnh hãng khác thay.
- Tông: red = sai lầm/cảnh báo, blue = cách đúng.

## Ẩm thực — “Phở bò quán X, 45 năm” (khán giả: người thích ăn uống, khách du lịch)

```python
("g01", BACK, "gold", 0.3, 2.8, ("quán phở", 0.4), ("45 NĂM", 150, 1.0), None, None),
("g02", FRONT, "gold", 3.0, 6.2, ("nước dùng ninh", 3.1), ("12 TIẾNG", 130, 3.9), None, "pot"),
("g03", FRONT, "blue", 6.4, 9.0, ("mỗi bát chỉ", 6.5), ("50.000Đ", 130, 7.2), None, None),
```
- Clip quay đúng nồi nước dùng → cắt khung c_*; ảnh quán/món của chính quán X → w_* có nguồn; cảnh phố chung → i_*.
- Icon Uicons tra tên trong `assets/uicons/solid.css` (bỏ `fi-sr-`), preflight báo nếu sai tên.
