# entities.json — chủ thể có tên (dự án, địa danh…) + ảnh thật

(Tự sinh từ thagent/entities.py — không sửa tay.)

```
Chủ thể có tên trong lời nói / chữ trên hình (dự án, khu đô thị, toà nhà, thương hiệu, địa danh, người…) → ảnh PHẢI là ảnh thật của đúng chủ thể.

Claude ghi {pdir}/entities.json (bắt buộc khi video có ảnh tải từ mạng; không có chủ thể nào → []):
[{"name": "Vinhomes Central Park", "aka": ["Vinhomes Tân Cảng", "Tân Cảng"],      tên + cách gọi khác đúng như người nói (cả cách chép lời nghe sai)
  "photos": ["w_vhcp_1.jpg", "w_vhcp_2.jpg"],                                     ảnh THẬT của chính chủ thể (assets_web/, có URL nguồn)
  "no_photo": null},                                                              tìm kỹ không có ảnh thật → ghi lý do (chuỗi)
 {"name": "Global City", "not_entity": "tên hệ sinh thái nói chung, cảnh không có ảnh"}]   tên riêng KHÔNG cần ảnh → ghi lý do
Tìm ảnh thật: python -m thagent.tools imgsearch <dự-án> "<tên dự án + chủ đầu tư>" → Read ảnh ghép → tools img <dự-án> #số w_ten.jpg
Mô tả ảnh (bắt buộc với mọi ảnh web, sau khi Read ảnh): assets_web/illus_check.json
  {"i_ten.jpg": {"noi_dung_anh": "sân bay, nhà ga, máy bay đậu", "cau_noi": "…", "khop": true}}   ghi THẬT những gì thấy trong ảnh
Kiểm (dùng chung Talking Head + Voice to Motion):
- cảnh có ảnh mà lời nói (trong cảnh hoặc ≤2s trước khi cảnh hiện) hay CHỮ TRÊN HÌNH gọi tên chủ thể → cảnh phải có ≥1 ảnh trong photos
  của chủ thể (no_photo → cảnh báo, không giả ảnh nơi khác);
- ảnh trong photos: có trong assets_web, nguồn là URL, được dựng như ảnh thật (Talking Head: tên w_*; Voice to Motion: real=True);
- ảnh minh hoạ chung không được gắn nhãn tên chủ thể; tên riêng nghe thấy quanh cảnh có ảnh mà chưa khai → LỖI (khai chủ thể hoặc not_entity);
- lời/chữ của cảnh nói vật cụ thể (sân bay, sông, biển, hồ bơi, công viên, metro, cầu, trường học, bệnh viện…) → phải có ảnh mà
  noi_dung_anh có đúng vật đó; ảnh web chưa mô tả → lỗi;
- một ảnh web chỉ dùng ở MỘT cảnh trong cả video.
Ảnh nội thất / tiện ích / khái niệm nói chung chung (không gọi tên chủ thể) vẫn dùng ảnh minh hoạ như cũ.
```
