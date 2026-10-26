# plan.callouts — chữ nổi bật + icon / callout / ảnh kẹp (Talking Head)

(Tự sinh từ thagent/callouts.py — không sửa tay.)

```
Callout + chữ nổi bật kèm icon / ảnh cho Talking Head (cùng style neon 3 màu, Montserrat).

plan.callouts = [{"id", "kind", "start", "end" (frame timeline), "tone": "gold"|"red"|"blue", "layer": "front"|"behind",
                  "place": "auto"|"chest"|"low"|"above_head"|"left"|"right",
                  "zoom": "punch"|"out" (nhấn nhá ý chính, ~mỗi 10–12s, xen kẽ), "at": [frame…] (mốc hiện từng mục), …tham số theo kind}]
                  "glass": true|"dark"|"light" (khung KÍNH MỜ — nền video phía sau mờ thật; mặc định nên dùng cho chữ + icon),
                  "sweep_at": [frame…] (thêm lần vệt sáng lướt qua chữ nhấn — lần đầu tự chạy lúc vào, kiểu CC Light Sweep),
                  "icon_style": "premium"|"color" (icon 3D 3dicons)
Icon 3D (kho chung, mọi skill): "icon": "3d:<id>" — tra: python -m thagent.tools icon3d <từ khoá tiếng Anh>. 3D CHỈ dùng cho icon;
khung, chữ luôn phẳng. Icon nét (Uicons, tên trần như "clock") vẫn dùng được cho icon nhỏ.
Vào: từng phần bật lần lượt (pop vượt cỡ + loé sáng), mục trong trio/checklist/stat_pair/photo_strip hiện theo `at` (đặt đúng lúc nói).
App TỰ ĐẶT vị trí: thử lần lượt các chỗ, chọn chỗ NẰM TRONG KHUNG AN TOÀN và KHÔNG CHẠM MẶT trong suốt lúc hiện
(mặt lấy từ work/anchors.json, nới thêm lề); không chỗ nào vừa → tự thu nhỏ. Không bao giờ đặt trước mặt nhân vật.

Kind (tham số):
  chữ + icon   icon_keyword(icon, text, sub) · two_tier(lead, text, icon) · step(step "1/3", text, icon) · quote(lead, text)
               warning(text, sub) · trio(items[{text, icon, tone}], at[frame…]) · checklist(items[{text, icon}], at[frame…])
               before_after(a, b, a_sub, b_sub) · stat_pair(items[{icon, value, label, tone}]) · big_number(text, sub)
               card(icon, text, sub) · dos_donts(bad, good) · circle_word(lead, text, mark "circle"|"underline")
               icon_badge(icon, label)
  chỉ vật      pointer(target [x, y] 0..1 khung dọc, label) · arrow_label(target [x, y], label)
  kẹp ảnh      photo_card(image, text) · photo_circle(image, label) · polaroid(image, script, text) · photo_split(image, lead, text, icon)
               photo_strip(images[3], title, at[frame…]) · photo_compare(a_image, b_image, a_label, b_label)
               photo_behind(image, label — layer behind, trên đầu) · thought(image, text) · phone(image, label)
  Ảnh: assets_web/i_* (minh hoạ — app ghi nhãn “Hình ảnh minh họa”), w_* (ảnh thật của chủ thể), c_* (khung cắt từ clip).
  Icon: tên Uicons như các phần khác (tra bằng neon.icon_exists).
```
