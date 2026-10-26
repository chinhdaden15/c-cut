# plan.stage — hiệu ứng quanh / sau lưng nhân vật (Talking Head)

(Tự sinh từ thagent/stage.py — không sửa tay.)

```
Lớp "sân khấu" quanh / sau lưng nhân vật cho Talking Head — làm video sinh động hơn ngoài chữ + callout ở giữa.

plan.stage = [{"id", "kind", "start", "end" (frame timeline), "tone": "gold"|"red"|"blue", …tham số theo kind}]
Mọi thứ "sau lưng" vẽ vào lớp behind (nhân vật tách nền đè lên) → không bao giờ che mặt; thứ phía trước (icon trước, khung HUD)
chỉ nằm ở mép / hai bên, tránh mặt.

Kind (tham số):
  giant_text  text — chữ khổng lồ viền neon 3 dòng sau lưng, trượt ngang ngược chiều (từ khoá của đoạn) — LOÉ 1.5s
  orbit_icons icons ["3d:<id>", …] (2–5) — icon 3D lơ lửng hai bên, cái sau lưng mờ (độ sâu), cái trước rõ
  bokeh       — hạt sáng trôi + ánh sáng màu loang phía sau (nền cho đoạn nói dài)
  marquee     text — 2 băng chữ nghiêng chạy ngược chiều sau lưng (tên sản phẩm, slogan, CTA) — LOÉ 1.5s
  spotlight   — nền tối + đèn rọi vào người + tia tốc độ (hook, câu bẻ lái)
  big_number  text ("30%", "#1", "3X"), angle (mặc định -10) — số khổng lồ nằm xéo sau lưng, to tràn khung — LOÉ 1.5s
Chữ sau lưng (giant_text, marquee, big_number) chỉ loé 1.5s rồi mất dù end dài hơn — nhấn đúng từ đang nói, đặt start ngay lúc nói.
Lúc hiệu ứng vào app TỰ nhấn: zoom khung hình (punch đẩy vào rồi nhả; spotlight thì zoom lùi), loé sáng nhẹ, SFX hợp kiểu
(tắt bằng "accent": false). Không cần thêm zoom/flash/SFX tay cho các mốc này.
Nhịp: mỗi đoạn ý chính 1 kiểu (~6–10s đổi), không 2 kiểu nền (bokeh/spotlight) cùng lúc.
```
