---
name: talking-head-style
version: 1.3.1
description: Phong cách dựng video Talking Head “Talking Head Style” (mọi lĩnh vực, tiếng Việt, dọc 9:16) đã được người dùng duyệt — chữ neon Montserrat 3 màu (vàng cam/đỏ/xanh), chữ dẫn rơi từng từ + tick, xếp lớp sau đầu/trước ngực, icon Flaticon gradient phát sáng, Motion Graphics nền xanh mỗi ~15s, SFX tiết chế, preflight trước render. Dùng khi người dùng chọn “Talking Head Style”, nói “dựng theo Talking Head Style”, “dựng video talking head như bản B.TA”, hoặc đưa video người nói vào app và muốn dựng full.
---

# Talking Head Style

Bản chuẩn đã duyệt: `projects/bta/renders/v009_v6_clean/bta_v6_clean.mp4`.
Mọi thông số máy đọc: [style.json](style.json). Mẫu code đã duyệt (copy rồi sửa cho video mới):
[reference/design_example.py](reference/design_example.py) (chữ, SFX, zoom, ảnh trên đầu) và
[reference/design_mg_example.py](reference/design_mg_example.py) (Motion Graphics).
Hai mẫu đó là video BĐS — **chỉ học cấu trúc và nhịp, không học nội dung**. Ví dụ ngắn lĩnh vực khác: [reference/domain_examples.md](reference/domain_examples.md).

**Mọi lĩnh vực:** trước khi lập kế hoạch, đọc transcript và xác định lĩnh vực + khán giả + chủ thể chính (thương hiệu/sản phẩm/địa điểm/người/sự kiện),
ghi mục đầu `confirm.json` `{"id":"domain","text":"Lĩnh vực: … · Khán giả: … · Chủ thể: …","status":"auto"}`. Chữ, ảnh, icon, bối cảnh minh họa theo đúng lĩnh vực đó.

Giọng nói và ý nghĩa nguyên bản là nền tảng. Không đổi số, đơn vị, điều kiện, tên riêng.

## Quy trình (theo đúng thứ tự — render là bước CUỐI)

1. **Nhận nguồn** — `P.step_ingest` (proxy 1080×1920@30, tự tonemap HDR). Hỏi/ghi nhận: nguồn đã lọc tạp âm + cắt thô chưa? Nếu rồi → `style["voice_preprocessed"]=True`, 1 đoạn giữ nguyên, không khử tạp âm. Nếu chưa → **Cắt sạch** (`thagent/cleancut.py`, template tự gọi; ngưỡng lặng theo độ to CHÍNH clip): bỏ đầu trước chữ đầu, đuôi sau câu kết (+1.5s, cắt đoạn tắt máy), rút lặng còn 0.3s giữa câu / 0.15s giữa từ, bỏ hiệu lệnh “1 2 3 diễn / 2 3 nói / 3 2 1” + câu hỏng ngay trước, từ đệm ừ/à/ờ, ậm ừ không thành lời, chữ kéo dài, nói vấp 1 từ (“Đến… Đến bây giờ”), lắp bắp cụm ≥2 từ; đoạn giữ thứ lẻ phóng 108% để giấu jump cut. Nói lại nhiều lần cùng câu → giữ lần trôi chảy nhất (tự chấm, cắt các lần kia bằng EditSegment keep=False). In `K.report` vào chat để người dùng biết đã cắt gì; muốn giữ chỗ nào thì bỏ cut đó. Mọi mốc giây trong design là giây NGUỒN, `F` tự đổi sang timeline sau cắt.
2. **Chép lời** — `P.step_transcribe` (faster-whisper large-v3, timestamp từng từ). Đọc toàn bộ, **sửa lỗi ASR theo ngữ cảnh + nguồn chính thức** (tên riêng, thuật ngữ ngành, số liệu…), tự quyết rồi ghi nhật ký vào confirm.json (không chờ duyệt — người dùng góp ý khi xem bản hoàn thiện).
   - **Đối chiếu kịch bản** (nếu người dùng nhập `projects/<id>/script.txt`): kịch bản là chuẩn cho chính tả/tên riêng/số liệu; chỗ nhân vật nói khác kịch bản, đoạn bỏ sót, đoạn nói thêm, câu nói vấp/lặp → đưa vào `confirm.json`, không tự quyết. Ghi `script_check.json`.
   - **Nhiều đoạn → 1 video** (app gửi thư mục chế độ “các đoạn của 1 video”): trước tiên viết `edl.json` (chọn take tốt nhất theo kịch bản, đoạn không nhìn máy — kể cả quay sang nhìn bảng trình chiếu — chỉ lấy tiếng + che b-roll/MG); app ghép thành `work/assembled.mov` và `covers.json` — khoảng `mg`/`audio_only` bắt buộc có MG, khoảng b-roll chỉ dùng chữ `front_of_subject`.
3. **Tách nhân vật + neo** — `P.step_matting` (RVM alpha + đỉnh đầu/mặt).
4. **Tìm đoạn không nói vào máy** — app đã ghi `work/gaze.json` (chưa có thì chạy `python -m thagent.gaze <id>`) rồi **xem contact sheet vùng mặt mỗi giây** để kết luận: cúi nhìn điện thoại/kịch bản, quay đi. Các đoạn này bắt buộc che bằng Motion Graphics/ảnh minh họa. **Ngoại lệ — đang TRÌNH DIỄN vật** (`demo=true` trong gaze.json: tay cầm/chỉ vật trong khung — cúi xem sách, mở hộp, cầm sản phẩm): GIỮ HÌNH NGƯỜI, không MG (preflight lỗi nếu MG che), nhấn bằng chữ nổi bật + callout (pointer/arrow_label chỉ vào vật); app đặt callout tránh mặt và vùng vật. App đoán sai → `work/gaze_override.json` `[{"t0","t1","kind":"demo"|"away"}]`. Ảnh cắt từ clip `c_*` chỉ là cận cảnh vật, không có mặt người nói.
5. **Lập kế hoạch** (viết `projects/<id>/design.py` + `design_mg.py` từ mẫu):
   - Nhóm chữ: `(id, lớp, tông, start, end, lead(text, near), main(TEXT, size, at), pill|None, element)`; lead là **nguyên văn chuỗi từ trong transcript** (hàm `word_frames` sẽ báo lỗi nếu không khớp).
   - **Nội dung chữ (preflight kiểm tự động):**
     - Số liệu = ý nổi bật → chữ chính **cả cụm đủ nghĩa**: `DIỆN TÍCH 30M²`, `3 VIÊN/NGÀY`, `200 GRAM BỘT`, `GIẢM 40%`, `4 TỶ USD` — không để số đứng riêng.
     - **Không lặp chữ:** dòng dẫn là phần nói TRƯỚC chữ chính và dừng ngay trước nó. Sai: “một sự lựa chọn đáng xem” + `ĐÁNG XEM`. Đúng: “một sự lựa chọn” + `ĐÁNG XEM`.
     - **Liệt kê** (điều/lý do/bước thứ N): chỉ chữ chính `ĐIỀU 2` / `LÝ DO 1`, **không có dòng dẫn**.
   - Tông màu theo nghĩa: gold = thường, red = cảnh báo/mức độ/sai lầm, blue = tin tưởng/giải pháp.
   - Tiêu đề lớn mở đầu/kết và câu “bẻ lái” → lớp sau (trên vai/đầu). Còn lại → trước ngực.
     **Chữ sau đầu không được bị che hết:** quay cận, đỉnh đầu sát mép trên → không đủ chỗ trên đầu thì đặt nhóm đó **trước ngực** (lớp trước người) ngay từ đầu. App tự đưa xuống nếu chữ bị đầu che quá nửa (preflight ghi dòng info) — xem stills để chắc chữ đọc được.
   - **MỞ ĐẦU & KẾT (bắt buộc, app kiểm): đoạn mở đầu (hook = câu nói đầu, 2–6s) và đoạn kết (khoảng CTA ~5s cuối; câu cuối bắt đầu sớm hơn thì tính từ đầu câu, tối đa 6s) CHỈ có hình nhân vật + chữ (chữ hook xuất hiện trong 1s đầu; đoạn kết là chữ CTA lớn, nổi bật, nhấn mạnh) — KHÔNG Motion Graphics, KHÔNG ảnh/thẻ ảnh/b-roll; MG và ảnh chỉ nằm giữa hai đoạn này. Nhân vật không nhìn máy ở câu đầu/cuối (cúi đọc kịch bản) → chọn take/câu khác làm hook/kết hoặc cắt bỏ khúc đó, không che MG.**
   - **Motion Graphics bản mới (`plan.mg2`, `.claude/shared/schemas/talking-head-mg2.md`) — DÙNG THAY cho design_mg.py / plan.mg:** cảnh có bố cục + chuyển động (HyperFrames): `chart`, `money`, `notif`, `question`, `photos`, `doc`, `iconrow`, `chips`, `compare`, `checklist`, hoặc `custom` (tự thiết kế theo chủ đề). Nền chỉ 6 kiểu đơn giản `blur|gradient|cream|charcoal|dots|spot` (1–2 kiểu cho cả video, màu theo chủ đề). Nhịp ~10s/cảnh (preflight lỗi nếu nói > 12s không MG, trừ đoạn trình diễn vật), ≥ 4 kiểu, không lặp liền nhau. Icon 3D phải nhận ra ngay đúng vật.
   - **Phụ đề toàn bộ lời nói (app tự thêm):** từng từ / cụm (tiếng Việt tách từ đúng: “sử dụng”, “tẩy trang”), ngay dưới cằm giữa khung, tự ẩn khi chữ nhấn / callout hiện, không hiện trong các đoạn MG. Claude KHÔNG tự làm phụ đề. Tắt: `plan.captions = False`.
   - **Vị trí chữ nhấn:** dải cổ → ngang nách (ngay dưới cằm, trên ngực trên), không đẩy xuống ngực dưới / bụng.
   - **Luật cuốn hút (preflight LỖI):** mọi đoạn nói đều có thứ gì đó trên hình (không trống > 1.5s); ~5s một thứ MỚI xuất hiện; `plan.stage` ≥ 1/15s nói; `plan.callouts` ≥ 1/10s nói; người nói liệt kê → hiện danh sách đúng lúc. Mốc `at` của MG2 = GIÂY từ đầu cảnh.
   - **Từ liệt kê** (first/second/tip/thứ nhất…) = CHỮ CHÍNH to hoặc tiêu đề lớn của cảnh MG; chữ chính giữ ≥ 1.5s (lỗi). Thẻ câu hỏi MG2 bắt buộc có ảnh minh hoạ. Hiệu ứng sau lưng mặc định là chữ / số khổng lồ viền sáng; icon bay chỉ khi nói đúng vật. Chip MG ở khổ dọc đặt giữa khung dưới cằm.
   - **Khung tự nhận theo clip gốc:** quay ngang → dựng 1920×1080 (xuất 16:9), quay dọc → 1080×1920; không kéo dãn, không chọn tay.
   - (MG kiểu cũ — chỉ cho dự án cũ) Motion Graphics: đặt sao cho **không đoạn nói liên tục nào > ~15s**, ưu tiên đoạn mô tả và đoạn không nói vào máy; mỗi đoạn 3.5–13s, các cảnh 1.5–4s; sáng tạo theo nội dung. **Mỗi cảnh MG bắt buộc có ẢNH (PH)**: CLIP chỉ khi clip quay ĐÚNG vật/cảnh đang nói → cắt khung c_*; thứ clip không có (khái niệm, cảnh chung) → ảnh minh họa i_* (Unsplash/Pexels qua Bing, ĐÚNG BỐI CẢNH CHỦ ĐỀ và khán giả — vd y tế: phòng khám/bác sĩ, ẩm thực: món/bếp, công nghệ: thiết bị, BĐS văn phòng: không gian văn phòng chứ không kiểu ở nhà), app tự ghi nhãn “Hình ảnh minh họa”, nguồn lưu assets_web/illus_sources.json; ảnh ĐÚNG CHỦ THỂ w_* (thương hiệu, sản phẩm, địa điểm, dự án, người, sự kiện có thật — nguồn thật có URL, nhãn tên chủ thể) khi nói tới chính chủ thể đó. Không cố cắt clip cho vừa ý.; icon chỉ là phụ trang trí, icon đứng một mình là vô nghĩa.
     **ẢNH CHỦ THỂ CÓ TÊN (bắt buộc, app kiểm): ghi entities.json — mọi dự án/khu đô thị/toà nhà/thương hiệu/địa danh có tên được nói (name + aka đúng cách người nói gọi, photos = ảnh THẬT w_* của chính chủ thể tải từ web chủ đầu tư/trang dự án/báo, nguồn là URL trang; Read từng ảnh để chắc đúng nơi đó). Cảnh MG lúc đang nói tên chủ thể phải có ảnh trong photos của nó; ảnh minh hoạ i_* KHÔNG được gắn nhãn tên chủ thể. Tìm kỹ không có ảnh thật → "no_photo": "lý do", dùng bản đồ/chữ tên, không lấy ảnh nơi khác, ghi confirm.json. Nội thất/tiện ích/khái niệm nói chung chung (không gọi tên chủ thể) vẫn dùng ảnh minh hoạ i_*. Không có chủ thể nào → entities.json = [].** (định dạng: `.claude/shared/schemas/entities.md`)
     **TÌM ẢNH ĐÚNG NGUỒN (app kiểm):** `tools imgsearch <pid> "<tên đúng>"` hoặc WebSearch tìm bài báo/trang chủ đầu tư rồi `tools imgpage <pid> <link>` → Read ảnh ghép đánh số → `tools img <pid> #số w_ten.jpg` (nguồn tự ghi). Tên riêng nghe thấy quanh cảnh có ảnh mà chưa khai là LỖI (không phải chủ thể → `not_entity`); tên chép lời nghe sai → sửa chép lời + khai cả cách nghe sai trong `aka`. Mọi ảnh web: Read rồi ghi THẬT nội dung vào `assets_web/illus_check.json`; lời/chữ nói vật cụ thể (sân bay, sông, biển, hồ bơi, công viên, metro, cầu, trường, bệnh viện, cao tốc) → ảnh phải có đúng vật đó. Mỗi ảnh chỉ dùng một lần trong video.
     **Xấp ảnh theo lời** (`PHS`, type `photos`): mỗi ảnh có `kw` = từ đang nói khi ảnh vào (preflight kiểm ±4s); **không dùng lại cùng ảnh trong 30s**. **Nhịp:** Mỗi ảnh hiện ≥1.8s (preflight báo lỗi), cảnh ngắn chỉ 1 ảnh; cảnh MG ≥2.5s, gộp cảnh vụn. Dòng dẫn rơi nhanh 3 frame/từ ngay đầu cảnh/nhóm (được phép chạy trước lời), chữ chính vào ngay sau dòng dẫn và đứng yên tới hết — không bám từng từ để khỏi khựng.
     **Chuyển cảnh MG = tấm trượt ngang đè lên video** (vào từ phải, ra sang trái); đoạn MG liền nhau tự nối, không lộ cảnh cầm điện thoại ở giữa.
   - **Highlight vật được chỉ tay** — CHỈ khi nhân vật thật sự chỉ vào một vật NHÌN THẤY RÕ và lời nói gọi đúng vật đó (giơ/khua tay khi nói KHÔNG phải chỉ vật; không chắc → không khoanh; nhãn = tên vật nhìn thấy, không lấy tên dự án/thương hiệu đang nói). `work/pointing.json` (`python -m thagent.pointing <id>`) chỉ là GỢI Ý cử chỉ tay + box; xem ảnh tĩnh, chỉ khi đúng là chỉ vật mới chỉnh box cho trúng vật rồi thêm `VideoFxEvent(type="highlight", params={"box":[x,y,w,h], "label":"THANG MÁY", "tone":"gold", "shape":"rect"})`: viền sáng vẽ dần + làm tối xung quanh. Box theo toạ độ khung gốc (trước zoom).
   - **Số bị ASR nghe nhầm** (“Chín máy lạnh” → “Chính máy lạnh”, “Ba viên” → “Bà viên”): `fix_numbers` tự đổi thành số và đưa vào confirm; số liệu luôn làm chữ chính cả cụm.
     **Mỗi cảnh bắt buộc có ≥1 minh họa** (ảnh/icon lớn/mũi tên/sơ đồ/checklist) — không cảnh chỉ có chữ. Thẻ nhấn ý `TAG` cỡ 64, bỏ trống `y` để tự nằm sát dưới chữ lớn. Dòng dẫn dài tự cắt từng đoạn 1 dòng trong vùng an toàn.
   - Ảnh: đúng chủ thể (thương hiệu/sản phẩm/địa điểm/dự án/người/sự kiện) → nguồn thật có URL, nhãn tên chủ thể; minh họa chung → Unsplash/Pexels/Pinterest qua Bing Images, nhãn “Ảnh minh họa”. Google Images/Flaticon web chặn bot → không vượt CAPTCHA/bộ lọc; icon dùng Uicons đã có trong `assets/uicons` (~3.400 icon, mọi chủ đề): ghi đúng tên Uicons solid-rounded như `heart`, `syringe`, `pills`, `dumbbell-fitness` (tra trong `assets/uicons/solid.css`, bỏ tiền tố `fi-sr-`); preflight báo lỗi nếu tên không có.
   - **Chữ nổi bật dày ~4s/lần (preflight lỗi nếu khoảng nào > 5s)** — tính cả nhóm chữ, callout, cảnh MG. Video chủ yếu nói, ít ví dụ → `plan.callouts` (định dạng + 25 mẫu: `.claude/shared/schemas/talking-head-callouts.md`):
     chữ + icon (`icon_keyword`, `two_tier`, `step`, `quote`, `warning`, `trio`, `checklist`, `before_after`, `stat_pair`, `big_number`, `card`, `dos_donts`, `circle_word`, `icon_badge`), chỉ vật (`pointer`, `arrow_label`), kẹp ảnh (`photo_card`, `photo_circle`, `polaroid`, `photo_split`, `photo_strip`, `photo_compare`, `photo_behind`, `thought`, `phone`).
     Gợi ý theo lĩnh vực: BĐS `before_after` giá / `photo_card` căn hộ; sức khoẻ `warning` + `checklist`; tài chính `big_number` / `stat_pair`; mỹ phẩm `photo_compare` / `step`; ẩm thực `polaroid` / `trio` nguyên liệu; công nghệ `phone` / `icon_badge`; giáo dục `step` / `quote`; kinh doanh `stat_pair` / `dos_donts`; du lịch `photo_strip` / `photo_circle`.
     **App tự đặt vị trí: luôn trong khung an toàn (trên 150, dưới 330, hai bên 70 px) và KHÔNG BAO GIỜ trước mặt nhân vật** (khung mặt từ anchors + lề); không vừa → tự thu nhỏ; vẫn không vừa → preflight lỗi, rút chữ/bớt mục/đổi mẫu. Không lặp một mẫu 3 lần liền. Callout ảnh theo đúng luật ảnh ở trên và không nằm trong đoạn mở đầu/kết. SFX khi callout / cảnh MG vào: app tự thêm (khai tay linked_event = id thì dùng âm khai tay). **Sân khấu quanh / sau lưng** (`plan.stage`, `.claude/shared/schemas/talking-head-stage.md`): `giant_text`, `big_number` (số khổng lồ nằm xéo), `marquee` (chữ sau lưng — chỉ LOÉ 1.5s đúng lúc nói rồi mất), `orbit_icons` (icon 3D bay quanh, có độ sâu), `bokeh`, `spotlight` (hook / bẻ lái) — mỗi đoạn ý chính 1 kiểu, ~6–10s đổi; app tự zoom + loé sáng + SFX lúc vào; không dùng khung góc / nhãn chương / thanh tiến độ / vòng hào quang; sau lưng thì nhân vật luôn đè lên, phía trước chỉ ở mép. Callout chữ + icon mặc định đặt trong **khung kính mờ** `"glass": true` (nền video sau khung mờ thật, khung nở + vệt sáng quét mặt kính khi vào) với **icon 3D** từ kho chung `"icon": "3d:<id>"` (tra `python -m thagent.tools icon3d <từ khoá>`; 3D CHỈ cho icon — khung, chữ luôn phẳng). Chữ nhấn có **vệt sáng lướt qua** (kiểu CC Light Sweep) lúc vào, thêm lần bằng `"sweep_at"`. Callout vào bằng pop từng phần (app tự diễn hoạt); zoom nhấn nhá gắn vào callout ý chính `"zoom": "punch"|"out"` ~mỗi 10–12s, xen kẽ (preflight cảnh báo nếu thiếu); mục liệt kê đặt `"at"` đúng lúc nói.
   - Zoom punch 1.14 ở 6–7 ý chính, zoom-out 1.12 ở 5–6 nhóm.
   - SFX theo `style.json → sfx` (tick cho chữ rơi, âm nhẹ cho chữ chính/tích, flash cho chuyển cảnh/tiêu đề sau đầu, tiền tối đa 1 lần). Không whoosh.
6. **Preflight** — `python -m thagent.preflight <id>` phải **0 lỗi, 0 cảnh báo** (hoặc cảnh báo đã giải thích được với người dùng). Kiểm: âm bị loại/đè tiếng chữ rơi, mật độ âm, số frame nguồn, tràn khung, element đè chữ (theo nét thật), chồng nhóm cùng lớp, giữ chữ chính ≥1.5s, quy tắc 15s, lặp chữ dẫn/chính, liệt kê có dòng dẫn, số liệu chưa nổi bật, cảnh MG chưa có ảnh, ảnh không khớp lời (kw), ảnh lặp trong 30s, ảnh hiện <1.8s, cảnh MG <2.5s, lặp chữ dẫn/chính (≥60% từ), cuối video cắt khi còn đang nói, cúi nhìn trong lúc MG đang trượt, đoạn nói không nhìn máy chưa được che (gaze.json), thẻ MG ra ngoài vùng an toàn.
7. **Xem ảnh tĩnh** tại các điểm nhấn và mọi chỗ vừa sửa (script still: đọc frame proxy + alpha, vẽ nhóm/thẻ/MG đúng như renderer). Sửa đến khi sạch.
8. **Render một lần** — `P.step_render(c, None, "<label>")`. Kiểm `qa.json`: số frame = timeline, AV lệch < 2 frame, ~-16 LUFS, TP ≤ -1 dBTP.
9. **Báo cáo** — đường dẫn MP4, các chỗ sửa ASR cần xác nhận, nguồn ảnh (bản quyền), ghi nguồn “Uicons by Flaticon”, những gì chưa nghe/nhìn được. Trạng thái là bản xem trước cho tới khi người dùng duyệt.

**Tốc độ:** người dùng nói “tăng tốc 1.1” → `python -m thagent.tools speed <id> 1.1` (0.8–1.5), app tăng cả hình + tiếng lúc xuất, giọng giữ cao độ; không đổi timing chữ/MG.

Sửa theo góp ý: chỉnh plan → preflight → stills → render. Chỉ sửa tiếng (SFX, lọc nhiễu) thì **trộn lại audio và ghép vào hình cũ**, không render lại hình.

## Quy tắc không được vi phạm

- Một họ font (Montserrat); không chữ viết tay/cách điệu; chữ dẫn SemiBold (Light biến mất trên nền sáng).
- Tiếng chữ rơi (tick) nhỏ ≤ -17 dB và chỉ kêu ~1/2 số chữ (renderer tự áp) — dùng nhiều nghe nhức đầu.
- Chỉ 3 tông gold/red/blue. Trên nền MG xanh: thẻ/icon dùng gold (red cho cảnh báo).
- Dòng dẫn → CHỮ CHÍNH → nhãn, khoảng cách tính theo nét chữ thật (16px / 44px) — không rời rạc.
- Không chồng câu trong cùng lớp; nhóm mới vào thì nhóm cũ rời; mỗi nhóm giữ ≥1s sau khi hiện đủ.
- Element chỉ ở chỗ trống, không bao giờ đè chữ; cụm lớp sau có nhãn thì không thêm element.
- Cụm lớp sau có nhãn: đặt cả cụm trên đỉnh đầu cao nhất trong thời gian hiển thị (pc10), tự thu nhỏ nếu thiếu chỗ.
- Không âm nào đè tiếng chữ rơi; âm nhẹ cách nhau ≥10 frame; SFX tiết chế, dịu tai.
- Không sinh ảnh chủ thể có thật (sản phẩm, địa điểm, dự án, người, bản đồ) bằng AI; không dùng ảnh chủ thể khác thay thế; thiếu tư liệu → báo người dùng.
- Không dùng `-shortest` khi mux; luôn để hình và tiếng dài đúng timeline.

## Vị trí code

| Việc | File |
|---|---|
| Pipeline/checkpoint | `thagent/pipeline.py` |
| Chữ neon, words, pill, icon Uicons | `thagent/neon.py`, `thagent/typography.py` |
| Bố cục, xếp lớp, zoom, mix âm, mux | `thagent/render.py` |
| Motion Graphics | `thagent/mg.py` |
| Lọc tiếng máy tần cao | `thagent/declean.py` |
| Preflight | `thagent/preflight.py` |
| Thư viện/nhóm SFX (+ norm_db) | `assets/sfx/manifest.json`, `thagent/sfx.py` |
