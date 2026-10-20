# entities.json — chủ thể có tên (dự án, địa danh…) + ảnh thật

(Tự sinh từ thagent/entities.py — không sửa tay.)

```
Chủ thể có tên trong lời nói (dự án, khu đô thị, toà nhà, thương hiệu, địa danh, người…) → ảnh PHẢI là ảnh thật của đúng chủ thể.

Claude ghi {pdir}/entities.json (bắt buộc khi video có ảnh tải từ mạng; không có chủ thể nào → []):
[{"name": "Vinhomes Central Park", "aka": ["Vinhomes Tân Cảng", "Tân Cảng"],      tên + cách gọi khác đúng như người nói
  "photos": ["w_vhcp_1.jpg", "w_vhcp_2.jpg"],                                     ảnh THẬT của chính chủ thể (assets_web/, có URL nguồn)
  "no_photo": null}]                                                              tìm kỹ không có ảnh thật → ghi lý do (chuỗi)
Kiểm (dùng chung Talking Head + Voice to Motion):
- lời nhắc chủ thể trong một cảnh có ảnh → cảnh đó phải có ≥1 ảnh trong photos của chủ thể (no_photo → cảnh báo, không giả ảnh nơi khác);
- ảnh trong photos: có trong assets_web, nguồn là URL, được dựng như ảnh thật (Talking Head: tên w_*; Voice to Motion: real=True);
- ảnh minh hoạ chung không được gắn nhãn tên chủ thể; tên riêng nghe thấy trong cảnh có ảnh mà chưa khai → cảnh báo.
Ảnh nội thất / tiện ích / khái niệm nói chung chung (không gọi tên chủ thể) vẫn dùng ảnh minh hoạ như cũ.
```
