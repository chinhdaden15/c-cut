# Âm thanh

## Cắt sạch bên trong đoạn nói (v1.2.1)

`clean` dùng đúng bộ Cắt sạch của Talking Head (lặng thừa → giữ ~0,15–0,3s, từ đệm, nói vấp, câu nói lại, chữ kéo dài) với biên lặng đo bằng sóng âm thật.
Đoạn con khoá biên (`lock_cut`) để `fixjoins` không nới lại phần đã cắt. Chữ mà máy chép lời đặt mốc lấn vào chỗ cắt (thực tế là lặng) vẫn giữ trên phụ đề.

## SFX (v1.2.1)

Kho chung Voice to Motion (`thagent.v2m.sfxkit`), đỉnh âm đặt đúng khoảnh khắc hành động, −15 … −23 dB dưới lời, trộn trước khi cân độ to.

## Điểm nối theo nhịp nói tự nhiên (v1.2)

- Kiểm TỪNG điểm nối bằng audio gốc + transcript + đường năng lượng: `.venv/bin/python -m thagent.review joins {pdir}` (đệm đầu/cuối, khoảng nghỉ,
  còn tiếng tại điểm cắt) → ảnh `review/joins.jpg` (1s trước + 1s sau mỗi điểm nối, mốc từ, vạch cắt).
- `fixjoins` nới in/out theo quy tắc: đệm trước ~120ms (nới tới 200ms nếu năng lượng cho thấy phụ âm đầu bắt đầu sớm hơn mốc), đệm sau ~220ms
  (nới tới 400ms tới khi tiếng tắt — giữ đuôi từ, hơi thở), không lấn từ kề; chỉ NỚI, không thu phần giữ hình đã chủ ý; dời mốc at của chữ/cutaway/reframe.
- Từ kề (của câu bị bỏ) nằm sát → cắt tại CHỖ LẶNG NHẤT giữa hai từ (đường năng lượng), không cắt sát mốc từ kế — mốc lệch dễ dính đầu từ bị bỏ.
- Nghỉ ở điểm nối: giữa ý ~200–400ms; chuyển ý lớn ~400–650ms (`"pause": "lon"` ở đoạn sau). < 120ms = lỗi chặn; > 800ms = hụt nhịp → rút lặng dư.
- Khoảng nghỉ là ROOM TONE THẬT (đệm của chính nguồn) — không chèn lặng số, không lặp âm, không kéo giãn tiếng nói để bù.
- Microfade (15–20ms) chỉ chống tiếng click; không cứu được từ đã bị cắt mất. Không crossfade làm hai câu nói chồng lên nhau.
- Đầu file nguồn bắt đầu ngay khi nói (không còn đệm) = giới hạn nguồn → cảnh báo, ghi báo cáo.
- Nghe lại từng điểm nối trong ngữ cảnh trước/sau. **Không nghe được → báo rõ giới hạn**, chỉ khẳng định số đo và hình waveform.


App dựng tiếng từ nguồn theo edit.json:
- Lời người dẫn (đoạn `talk`) giữ trọn kể cả khi hình chuyển sang B-roll; fade 15–20ms ở mỗi điểm nối (không tiếng bật).
- J/L-cut theo `j`/`l` (nối liền lời qua cảnh minh họa).
- Tiếng hiện trường: đoạn `broll` với `audio: "nat"` (`nat_db`, mặc định −14 dB); cutaway có `nat_db` → trộn nhỏ dưới lời. Giữ khi tăng cảm giác
  thật (tiếng mở hộp, cắm cáp, xào nấu); `audio: "mute"` khi tạp âm.
- Khử nhiễu vừa phải (afftdn nhẹ) + lọc trầm < 70 Hz; cân về −16 LUFS, đỉnh ≤ −1,5 dB → các take cùng mức âm.
- Nhạc (`music.src`, `gain_db` ~ −20): tự giảm (sidechain) khi có lời. SFX chỉ ở điểm nhấn/chuyển cảnh/thao tác — không rải đều.
- Micro rời: cần đồng bộ với footage (chưa tự động trong bản 1.0 — báo trong báo cáo nếu có file tiếng riêng).
- App đo trên file xuất: độ to, đỉnh, đoạn lặng > 2s. **Môi trường không nghe trực tiếp được** — báo cáo phải ghi rõ “chưa nghe kiểm chứng”,
  chỉ khẳng định số đo.
