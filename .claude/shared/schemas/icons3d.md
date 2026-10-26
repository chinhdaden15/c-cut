# Kho icon 3D dùng chung (mọi skill)

(Tự sinh từ thagent/icons3d.py — không sửa tay.)

```
Kho icon 3D dùng chung cho mọi skill (không riêng skill nào).

Nguồn (miễn phí, dùng thương mại được):
- 3dicons — Vijay Verma, CC0 (https://3dicons.co): ~120 icon vật thể/khái niệm, kiểu "premium" (ánh kim vàng/đen — mặc định)
  hoặc "color" (màu tươi). Id dạng `clock`, `trophy`, `money-bag`…
- Microsoft Fluent Emoji 3D — MIT (https://github.com/microsoft/fluentui-emoji): ~1.000 hình đồ vật, đồ ăn, nhà cửa, phương tiện,
  y tế, thiên nhiên, biểu tượng… (bỏ mặt cười, người, cờ cho khỏi trẻ con). Id dạng `f-house`, `f-pill`, `f-stethoscope`…

assets/icons3d/index.json (có trong mã nguồn): [{"id", "src", "title", "keywords", "group"}]. Ảnh PNG tải lúc build bộ cài
(fetch_all) và tự tải khi thiếu (path). Tra icon: `python -m thagent.tools icon3d <từ khoá tiếng Anh>` hoặc find().
Trong callout: "icon": "3d:<id>" (vd "3d:trophy", "3d:f-house"); "icon_style": "premium"|"color" cho 3dicons.

python -m thagent.icons3d index     dựng lại index.json từ hai nguồn (máy dev)
python -m thagent.icons3d fetch     tải đủ PNG vào assets/icons3d (build bộ cài / dùng offline)
python -m thagent.icons3d find kw   tra theo từ khoá
```
