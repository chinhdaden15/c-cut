# Giữ chân người xem (bắt buộc cho Text to Video + Voice to Motion)

Mục tiêu: video ngắn mạng xã hội mà người xem **không lướt qua**. Đúng nội dung vẫn chưa đủ: mỗi giây phải có lý do để xem tiếp.
App kiểm (`qa.engagement`, lỗi chặn xuất). Các mục đánh dấu **[app kiểm]** sẽ bị trả lại nếu sai.

## 1. Ba giây đầu: hook
- **[app kiểm]** Trong 1 giây đầu phải có chữ lớn (`s.title(..., size="xl")`, ≥ 96px) hoặc hình phủ khung (`s.photo_bg`).
- Khung đầu tiên không được trống. Chữ hook phải hiện ngay từ 0.0–0.2s, không chờ lời đọc tới.
- Hook nêu **nỗi đau hoặc lợi ích**, ngắn 3–6 chữ, một hoặc hai từ đổi màu nhấn. Ví dụ: “NGẠI DỰNG VIDEO?”, “30 GIÂY CÓ VIDEO”.
- Có chuyển động mạnh ngay frame đầu: chữ đập vào (`style="pop"`), camera đẩy nhẹ, hoặc b-roll đang chuyển động. Kèm SFX `impact` / `whoosh`.

## 2. Mỗi cảnh: một điểm nhấn lớn
- **[app kiểm]** Mỗi cảnh có ít nhất một khối lớn: chữ khoá ≥ 100px, icon 3D ≥ 260px, số khổng lồ (`s.stat`), mẫu `s.mg(...)`, hoặc ảnh/video phủ khung.
- Một dải tiêu đề nhỏ trên đầu với vài icon nhỏ giữa khung trống là **lỗi**. Nội dung chính chiếm ≥ 55% chiều cao khung dọc và nằm giữa khung.
- Một trọng tâm thị giác mỗi lúc. Mục đang nói to và rõ, mục cũ lùi lại (`s.spotlight`).

## 2b. Minh hoạ ĐÚNG LỜI: hình thật hoặc cảnh hoạt hình, không đặt icon cho có
- **[app kiểm]** Video > 15 giây: ≥ 50% thời lượng là **video/ảnh thật phủ khung** (`s.photo_bg("assets_web/v_x.mp4")`) hoặc **cảnh hoạt hình toàn khung** (`s.mg(...)` 6 mẫu bên dưới).
- **[app kiểm]** Tối đa 25% số cảnh chỉ minh hoạ bằng icon. Icon chỉ là chi tiết phụ.
- Đọc câu nói, hỏi: “người xem cần THẤY gì?” rồi chọn theo bảng (lời nói tới cái gì thì hình phải DIỄN cái đó):

| Lời nói tới… | Cảnh | Gọi |
|---|---|---|
| bản đồ, vùng miền, chi nhánh, giao hàng, toàn quốc, tuyến đường | vẽ bản đồ: viền tự vẽ, ghim rơi xuống, tuyến cong nối điểm | `s.mg("mapdraw", t0, countries=["VNM"], pins=[{"name":"Hà Nội","at":t}], routes=[[0,1]], title=…)` |
| công nghệ, AI, phần mềm, hệ thống, tự động | lõi chip phát sáng + mạch điện toả ra + thẻ HUD bật theo lời | `s.mg("tech", t0, center="assets_web/logo.png"\|"3d:…"\|"AI", items=[…], at=[…], title=…)` |
| gõ lệnh, nhập kịch bản, chỉ vài dòng, bấm là xong | cửa sổ app gõ chữ, bấm nút, tiến trình %, video bay ra | `s.mg("prompt", t0, app="C-Cut", logo=…, text="…", at=[gõ, bấm, xong])` |
| đăng TikTok/YouTube, mạng xã hội, dọc + ngang, lượt xem | điện thoại (tim bay, view chạy) + laptop | `s.mg("devices", t0, image=…, labels=[…], views=…, at=[…])` |
| A biến thành B, quy trình đầu vào → xử lý → kết quả | dây chuyền: nút vào → máy xử lý (vòng quay) → nút ra, hạt sáng chảy | `s.mg("pipeline", t0, input={"wave":True,"label":…}, engine={"logo":…}, output={…}, at=[…])` |
| câu khẳng định, lợi ích, câu chốt, hook | chữ động toàn khung, từng cụm đập vào theo lời | `s.mg("kinetic", t0, lines=[{"text":…,"at":t,"hl":"TỪ"}])` (mỗi dòng ≤ 12 ký tự khung dọc) |
| người, vật, nơi chốn, thao tác cụ thể | **b-roll thật** phủ khung + chữ khoá đè | `brollsearch` → `broll … mixkit:<mã>` → `s.photo_bg(…mp4, dim=0.35–0.5)` |

- `at` trong `s.mg` là GIÂY VOICE (`K.find("từ")`), kit tự đổi. Cảnh `mapdraw`/`kinetic` có chữ trùng lời → `s.captions = False`.
- Không lặp một mẫu hoạt hình 2 cảnh liền. Xen kẽ: b-roll → hoạt hình → b-roll → chữ động…
- Mẫu chưa có (biểu đồ, tiền → `chart`/`money`; khác hẳn → `kind="custom"` tự viết html/GSAP): chỉ dùng transform/opacity (lint HyperFrames chặn animate top/left/box-shadow).

## 3. Nhịp
- **[app kiểm]** Cảnh dài tối đa 6 giây. Dài hơn thì tách theo ý hoặc theo câu.
- **[app kiểm]** Tối đa 3 giây không có thay đổi hình. Thay đổi phải gắn với từ đang đọc: khối mới vào, số chạy, chữ khoá bật, đổi màu, camera zoom, đổi b-roll.
- Khoảng 4 giây một lần có “nhấn” rõ: chữ khoá to + `s.pulse` + SFX vai trò.
- Đặt một khoảnh khắc “à ra vậy” ở giữa video: lật trước/sau, số lớn hiện ra, so sánh hai bên.

## 4. Đổi kiểu cảnh, không lặp
- **[app kiểm]** Không có 3 cảnh liền nhau cùng một kiểu hình. Luân phiên các kiểu sau:
  | Kiểu | Dùng khi | Gọi |
  |---|---|---|
  | B-roll phủ khung + chữ khoá đè | vật/cảnh cụ thể, người dùng, thao tác | `s.photo_bg("assets_web/v_x.mp4", dim=0.35)` + `s.keyword` |
  | Cảnh hoạt hình đúng lời | bản đồ, công nghệ, gõ lệnh, thiết bị, quy trình | `s.mg("mapdraw"\|"tech"\|"prompt"\|"devices"\|"pipeline")` (mục 2b) |
  | Chữ động toàn khung (kinetic) | câu khẳng định, lợi ích | `s.mg("kinetic", lines=[…])` hoặc `s.title(..., size="xl", hl=...)` |
  | Số khổng lồ | con số, thời gian, giá | `s.stat` / `s.mg("money" \| "chart")` |
  | So sánh / trước–sau | cũ vs mới, có vs không | `s.compare` / `s.before_after` / `s.mg("compare")` |
  | Danh sách tick | “không cần A, không phải B” | `s.mg("checklist", at=[...])` / `s.checklist` |
  | Hàng icon 3D lớn | 2–3 thứ song song | `s.icons([...])` (tối đa 3 icon, tự to) / `s.mg("iconrow")` |
  | Logo/giao diện app thật | nói tới app của chính mình | ảnh `packaging/icon.png` bo góc lớn, ảnh chụp màn hình app |
- Một câu không bắt buộc ứng với một icon. Chọn hình theo quan hệ ý (so sánh, quy trình, số, lợi ích).

## 4b. Âm thanh, chuyển cảnh, icon (hiện đại)
- **Nhạc nền BẮT BUỘC** cho video quảng bá / giới thiệu / mạng xã hội: `.venv/bin/python -m thagent.v2m musicsearch "<thể loại>"`
  (tech-house, upbeat, corporate, cinematic, energetic, hip-hop…) → chọn theo không khí → `music <dự-án> mixkit:<mã>` →
  trong builder `K.music("assets_web/m_<mã>.mp3", gain_db=-20)` (app tự hạ nhạc dưới giọng nói).
- **SFX:** app tự rải theo chuyển động (swoosh mỗi lần chuyển cảnh, boom + riser cho chữ lớn mở đầu / câu kết, blip thưa cho thẻ,
  glitch/data cho cảnh công nghệ, bản đồ). Tự đặt thêm: `s.sound(t, "boom")` cho cú đập chính (hook, câu chốt), không quá 1 boom / 4s.
  Không dùng pop/click dày đặc.
- **Chuyển cảnh:** mặc định `zoom` (phóng nhanh qua điểm cắt). Cảnh công nghệ / đổi không khí mạnh: `K.scene(..., transition="glitch")`.
- **Icon:** trong cảnh hoạt hình ưu tiên icon nét `"ui:<tên>"` (Uicons solid-rounded: microphone, clapperboard-play, sparkles, share,
  home, graduation-cap, robot, microchip, rocket, brain, globe, map-marker, mobile, laptop…) — tô gradient + kính tròn; logo thật giữ nguyên.
  Icon 3D (`3d:`) chỉ khi cần vật thể cụ thể.
- **Khổ ngang:** cảnh phủ kín khung (b-roll / hoạt hình toàn khung) tự căn GIỮA cả khung; phụ đề luôn giữa dưới.
  Cột chữ trái + hình phải chỉ dùng cho cảnh giải thích có hình bên phải (`s.layout = "split"`).

## 5. Nền
- **[app kiểm]** Video trên 15 giây không được dùng một nền phẳng từ đầu đến cuối. Đổi nền theo đoạn ý (2 màu chủ đạo, kiểu `gradient` / `spot` / `dots`) và chen b-roll/ảnh phủ khung ≥ 20% thời lượng.
- Text to Video với chủ đề cụ thể: hình thật ≥ 40% (đã kiểm riêng).

## 6. Phụ đề
- App tự vẽ phụ đề kiểu mạng xã hội: cụm 4–6 từ, chữ đậm có viền, **từ đang đọc đổi màu nhấn**. Không tự vẽ phụ đề riêng.
- Cảnh có chữ khoá trùng hệt lời đang đọc thì tắt phụ đề cảnh đó (`s.captions = False`) để không lặp chữ.
- Tên riêng, thương hiệu (C-Cut…) phải đúng chính tả. Có kịch bản thì app đã thay chữ chép lời bằng chữ kịch bản. Gặp chữ lạ trong transcript (vd “Secod”) thì đối chiếu kịch bản, không đưa lên màn hình.

## 7. Kết
- Khoảng 4–5 giây cuối là thẻ kết: logo/icon thật lớn (≥ 320px) + lời kêu gọi chữ xl + mũi tên hoặc nút. Nhịp chậm lại, giữ ≥ 2 giây sau khi hiện đủ.
- Chỉ dùng lời kêu gọi có trong voice/kịch bản.

## 8. Tự soát trước khi ghi plan_ready.json
Xem `stills` (đầu–giữa–cuối mỗi cảnh) và tự hỏi:
1. Dừng ở frame 0.5s, người xem có hiểu video nói gì và muốn xem tiếp không?
2. Có cảnh nào chỉ có tiêu đề nhỏ với khoảng trống không?
3. Có 2 cảnh nào nhìn gần như giống nhau không?
4. Mỗi cảnh có thứ gì “đọng lại” không: một con số, một chữ khoá, một hình ảnh?
Có câu trả lời sai thì sửa, không xuất.
