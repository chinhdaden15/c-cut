# Tự kiểm tra và bàn giao

## Tự động (app)

| Kiểm | Khi | Công cụ |
|---|---|---|
| Nguồn tồn tại, timecode hợp lệ, không dùng đoạn đen/outro, cắt không rơi giữa từ, take không lặp, crop không mất mặt, chữ đủ thời gian đọc, câu kết đủ đọc | trước dựng | `check` (lỗi chặn dựng) |
| Điểm nối theo nhịp nói (đệm đầu/cuối, nghỉ 200–800ms, còn tiếng tại điểm cắt), lời nhắc sản phẩm có spotlight/nhãn, reframe giữ trọn mặt + vật, chữ nhấn lặp khi spotlight/sơ đồ | trước dựng | `check`, `joins` |
| Nhãn/vòng nhấn có track phủ đủ, đoạn nhòe/thao tác chuẩn bị lộ (cảnh báo), kết hụt (dừng < 0,4s sau từ cuối), reframe phóng quá nét | trước dựng | `check` |
| Kích thước, fps, thời lượng, khung đen, lặng dài, độ to/đỉnh, chữ chồng/cắt khung trong lúc chuyển động, **phụ đề có tiếng nói đúng lúc** (năng lượng tiếng ±0,3s — chỉ là cảnh báo, cần nghe), chữ nhấn/nhãn chạm mặt, spotlight mất dấu, phụ đề đổi quá nhanh, điểm nối | sau dựng, TỪNG tỷ lệ | `render` → `review/versions/vNNN/qa_<fmt>.json` |

## Claude tự kiểm (bằng ảnh `media`/`frames`/`stills`) — chỉ đánh dấu đạt khi đã xem thật

- Đúng sản phẩm, căn nhà, phiên bản; B-roll đúng ý và đúng đối tượng.
- Lời giữ đúng nghĩa (không mất phủ định/điều kiện/đối tượng); không lặp take ngoài chủ đích.
- Không cắt mất hành động quan trọng; khẩu hình khớp khi người dẫn xuất hiện (app giữ nguyên đồng bộ hình–tiếng của cùng file nguồn).
- Không chữ chồng, rơi từ, thiếu dấu, sai số liệu; không crop mất chủ thể; không đoạn đen/outro nền tảng; không thiếu asset.
- Hai tỷ lệ đều xem stills riêng.

## Báo cáo — tách rõ chức năng ĐÃ CHẠY THẬT

Liệt kê từng chức năng đã dùng trong bản này (reframe, bám vật, nhãn sát vật, vòng nhấn, cắt gọn khung nhòe, chỉnh ngược sáng, cutaway, PiP…)
và lỗi nào thuộc NGUỒN (ngược sáng, nhòe, rung sẵn) vs do DỰNG. Xuất được MP4 ≠ đã hoàn thành review.

## Báo cáo (`review/report.md`, ngắn)

1. Đã làm: phong cách, mức thể hiện, thời lượng (và lý do nếu tự chọn), mạch các đoạn.
2. Đã kiểm: liệt kê tiêu chí đã kiểm THẬT + kết quả qa của từng tỷ lệ.
3. Còn thiếu / chưa kiểm được: asset thiếu (`missing`), thông tin mâu thuẫn, “âm thanh chưa nghe kiểm chứng”.
