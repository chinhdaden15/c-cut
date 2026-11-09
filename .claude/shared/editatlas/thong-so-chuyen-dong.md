# Thông số chuyển động (frame ở 30 fps) — tra khi tự thiết kế cảnh `custom` / HyperFrames / GSAP

Mỗi dòng: tên kỹ thuật (tên chuẩn trong nghề, để tra cứu) — cách làm bằng số. Rút gọn từ thư viện EditAtlas (2.010 kỹ thuật), viết lại.
Quy đổi GSAP: 30 frame = 1s → `duration: frames/30`. HyperFrames chỉ animate transform + opacity (không top/left/boxShadow).
HyperFrames chụp từng frame bằng cách TUA timeline: không dùng `tl.call`, `classList`, `setTimeout` để đổi trạng thái (khi tua sẽ không chạy) —
muốn đổi màu / bật sáng thì đặt sẵn một lớp phủ rồi tween `opacity`; số chạy dùng `onUpdate` của một tween (an toàn khi tua).

## Chữ vào / ra
| Kỹ thuật | Thông số |
|---|---|
| Fade In / Out | opacity 0→1 trong 18f ease-out / 1→0 trong 15f ease-in, không dịch chuyển |
| Slide In / Out | dịch 8% bề ngang + opacity, 16f ease-out cubic (ra 14f ease-in) |
| Pop In | scale 0.6 → 1.08 → 1, lò xo damping thấp, 14f |
| Scale In | scale 0.85→1 + opacity 0→1, 20f ease-out, KHÔNG nảy (dùng cho thẻ nghiêm túc) |
| Keyword Punch | chữ khoá vào ở 130%, về 100% trong 4f + rung khung nhẹ — đúng frame từ được nói |
| Snap Zoom | scale 1→1.5 trong 5f, ease gắt + motion blur, rồi giữ |
| Bounce In | rơi từ trên, nảy 2–3 lần giảm dần, 24f |
| Elastic In | trượt vào bằng lò xo damping thấp / stiffness cao, thấy 2 dao động |
| Mask Reveal | khối màu quét ngang để lại chữ phía sau, 22f |
| Letterbox Reveal | hai thanh đen tách từ tâm chữ ra, 18f, chữ đứng yên |
| Per-Word Stagger | mỗi từ đi lên 24px + opacity trong 12f, lệch nhau 4f |
| Per-Line Stagger | mỗi dòng lộ ra từ hộp clip 16f, lệch 8f |
| Editorial Headline | kẻ một đường mảnh trước, rồi dòng tiêu đề serif lộ từ hộp clip, lệch 6f |
| Outline Text Draw | chữ thành path, stroke-dashoffset từ đủ dài → 0, mỗi ký tự lệch 2f |
| Stroke to Fill | vẽ viền trước, rồi dày viền + fill hiện trong 12f |
| Typewriter | ~18 ký tự/giây, bước cứng, không fade |
| Cursor Typing | như typewriter + con trỏ khối theo ký tự cuối, nháy mỗi 16f khi đứng |
| Scramble Text | ký tự chưa chốt thay ngẫu nhiên (có seed) mỗi 2f, chốt trái→phải trong 24f |
| Slot Machine Text | mỗi ô cuộn dọc có blur, dừng trái→phải với nảy nhẹ |
| Word Swap | câu đứng yên, từ đích cuộn dọc qua danh sách, mỗi từ giữ 20f, khung co giãn theo bề rộng |
| Text Morph | hai từ chuyển nhau bằng blur + threshold trong 18f |
| Text Shadow Extrusion | 12 bản bóng cứng lệch 1px chéo, mọc dần trong 12f (chữ khối 3D) |
| Neon Flicker | chữ viền + glow nhiều lớp, tắt/bật 3 lần trong 20f rồi ổn định |
| Text Glitch | chùm 2–4f: tách RGB 6px + lệch 2–3 lát ngang, giữa các chùm sạch |
| Text Pulse | scale 1→1.06 + glow tăng, lặp mỗi 30f |
| Disintegrate Out | chữ vỡ thành hạt theo mặt nạ noise, trôi phải + lên, mờ trong 30f |
| Word Highlight | khối màu quét sau từ khoá trái→phải trong 10f; bút dạ: nét thô cũng 10f |

## Số và dữ liệu
| Kỹ thuật | Thông số |
|---|---|
| Animated Counter / Number Ticker | đếm tới giá trị với ease-out, chữ số tabular (bề rộng cố định), dấu phân cách đúng ngôn ngữ |
| Odometer | các cột số cuộn liên tục; cột cao chỉ nhích khi cột thấp tràn |
| Counter Roll | mỗi ô cuộn qua các ký tự ứng viên tới ký tự đúng, ease-out |
| Percentage Count-Up | số và thanh khớp nhau tuyệt đối, ease-out |
| Progress Bar / Ring | đầy tới % với ease phi tuyến, nhãn % khớp; vòng: cung chạy + số giữa |
| Bar Chart | cột mọc từ đáy, lệch 3f, rồi nhãn giá trị đếm lên |
| Line Chart | trục + nhãn trước, rồi vẽ đường theo x với chấm dẫn đầu |
| Donut | các cung vẽ lần lượt, số chính ở giữa |
| Stat Card | thẻ pop → số đếm → nhãn + nguồn |
| Price Pop | giá cũ gạch trước (nếu có) → giá mới bật lò xo |
| Discount Tag Drop | nhãn rơi treo dây, đung đưa tắt dần |
| Timeline Build | vẽ trục → mốc lần lượt, nhãn so le hai bên |
| Flowchart / Network | lộ nút theo đường chính (nhánh nhạt hơn); mạng lưới: nút giữa trước, nở theo từng bước, vẽ cạnh trước nút con |
| Venn | hai vòng trượt vào chồng nhau, phần giao sáng cuối cùng |
| Map Pins / Route | ghim rơi nảy + vòng sóng + nhãn; tuyến: cắt dần đường + marker chạy, camera bám |

## Giao diện, đạo cụ, chú thích
| Kỹ thuật | Thông số |
|---|---|
| Notification Stack | thẻ mới vào trên cùng, thẻ cũ thu 0.96 và dịch xuống |
| Toast | trượt vào góc trên phải, giữ 60f, trượt ra, không đè nội dung chính |
| Cursor Click | con trỏ tới đích, thu 0.85 khi bấm, vòng gợn tại điểm bấm (16f), rồi giao diện phản hồi |
| Search Query | gõ truy vấn → trạng thái tải ngắn → kết quả hiện lệch nhau |
| File Upload | file rơi vào → thanh tải đầy phi tuyến → tick |
| Error Shake | lắc ngang ±8px tắt dần trong 14f, viền đỏ + thông báo |
| Checklist Reveal | lộ danh sách, tick từng mục đúng lúc nói |
| Numbered Steps | số pop → vẽ đường nối → lộ chữ, từng bước |
| Card Flip | xoay Y 180° có phối cảnh, đổi mặt ở 90° |
| Card Stack Shuffle | lá trên ra bên → vòng ra sau xấp, các lá khác nhích lên |
| Bento Grid | các thẻ bo góc khác cỡ pop lệch nhau theo thứ tự đọc |
| Feature Cards Cascade | thẻ trượt lên vào chỗ, lệch 6f |
| Callout Pointer | chấm pop tại điểm → vẽ đường dẫn → lộ nhãn, không che chủ thể |
| Sticker Bounce | sticker bật lò xo gần điểm, có đuôi nhỏ, lắc nhẹ; kiểu scrapbook: nghiêng nhẹ + viền trắng, chạy "on 2s" (12 hình/giây) |
| Highlight Circle | vẽ vòng tròn không hoàn hảo quanh vùng trong ~14f |
| Arrow Draw | nét vẽ tay hơi cong, đầu mũi tên vẽ sau cùng |
| Lower Third | thanh trượt vào → tên → chức danh từ trái, lệch 4f, giữ, ra ngược |
| End Card | logo → CTA → link lệch nhau, giữ 4s, chừa chỗ giao diện nền tảng |
| CTA Button | nút pop, đập nhẹ mỗi 40f, có thể thêm con trỏ bấm |
| Logo Stamp | scale 1.6→1 trong 5f + rung khung + tóe mực nhỏ |
| Logo Light Sweep | vệt sáng hẹp mềm quét qua alpha logo trong 20f |
| Glassmorphism | nền sau mờ 20px, tấm fill trắng 15% + viền mảnh |
| Camera Shake | lệch theo noise có seed biên độ 20px tắt dần trong 15f, phóng 1.06 giấu mép |

## Camera trên người nói
| Kỹ thuật | Thông số |
|---|---|
| Punch-In | ở điểm cắt phóng 110–125% trong 1f, mắt ở 1/3 trên, về rộng ở ý sau |
| Digital Push In / Pull Out | scale 1.0↔1.08 quanh chủ thể (push tuyến tính, pull ease-out); không vượt độ nét nguồn |
| Ken Burns | ảnh tĩnh: scale 1.0→1.12 + lia chậm về chủ thể, tuyến tính, nguồn độ phân giải cao |
| Speed Ramp | 100% → 25% quanh khoảnh khắc rồi trở lại, vận tốc có ease; tiếng xử lý riêng |
| Freeze Frame | giữ frame + tiêu đề hoặc tiếng nhấn |
| Vertical Blur Fill | clip vừa bề ngang trên bản phóng kín 9:16 mờ σ40, tối 12% |
| Speaker Stack | hai người từ khung rộng xếp trên/dưới 1080×960 mỗi nửa, mắt ở phần trên mỗi nửa |

## Phụ đề
| Kiểu | Thông số |
|---|---|
| Clean Subtitle | chữ trắng ~5% chiều cao khung, viền tối 2px, giữa đáy cách 7%; ≤ 2 dòng 38 ký tự; giữ cụm + 150 ms |
| Boxed | chữ trắng trên hộp đen 60% ôm chữ, đệm 10px |
| Active Word Color | ≤ 6 từ trắng, từ đang nói chuyển vàng đúng frame đầu của từ, không fade, chữ không xê dịch |
| Active Word Box | cụm đứng yên, khối màu bo góc chạy sau từ đang nói (đo bằng font thật, đệm 8px) |
| Word Pop | một từ IN HOA mỗi lần, chữ đậm ~9% chiều cao, viền dày, scale 70→112→100% trong 130 ms, ở 1/3 dưới |
| Word Bounce | từ rơi 1.4 dòng vào chỗ trong 110 ms, nén 118% tới 75%, ổn định 90 ms; từ trước giữ nguyên tới hết cụm |
| Typewriter Caption | lộ từng ký tự theo thời gian nói, font monospace trên hộp tối; ký tự chưa hiện vẫn chiếm chỗ (trong suốt) để chữ không xô |

## Chuyển cảnh
| Kỹ thuật | Thông số |
|---|---|
| Whip Pan | hai clip trượt rất nhanh cùng hướng + blur hướng, cắt ở đỉnh blur; 8–12f |
| Zoom Out Transition | clip A scale 1→0.6, clip B 2.5→1 với radial blur tại điểm cắt |
| White Flash | lên trắng trong 2f tại cắt, tắt trong 6f trên clip B; ≤ 3 lần/giây |
| Flash Cut | chèn clip B 2–6f vào giữa A, có thể thêm 1 frame trắng trước |
| Cut on Beat | cắt trên phách đã dò; trễ thì dời sớm 1–2f |
| Cut on Action | cắt giữa một chuyển động, bỏ 2–3f đầu cảnh vào để chuyển động liền |
| Smash Cut | cắt phắt từ ồn sang tĩnh (hoặc ngược), tiếng cắt cùng frame không fade |
| Shape Mask Wipe | hình (tròn, sao…) phóng từ 0 tới phủ khung, clip B nằm trong |
| Circle Expansion | vòng tròn từ 0 phủ hết đường chéo khung trong 18f, ease-in-out |
| Sticker Peel | bóc từ góc, mặt sau giấy trắng + bóng mềm |
| Light Leak | lớp loé sáng chế độ screen, đỉnh đúng điểm cắt |

## VFX nền, khí quyển
| Kỹ thuật | Thông số |
|---|---|
| Neon Glow | lõi trắng + các lớp mờ màu 4 / 12 / 30px cộng sáng |
| Glow Pulse | bán kính + độ sáng glow theo sin, hoặc theo phách |
| Particle Burst | 100–300 hạt phát trong 1 frame, vận tốc toả ra + lực cản |
| Confetti | mảnh chữ nhật màu, cản không khí, xoay lật, trọng lực |
| Particle Dissolve | ăn mòn alpha theo ngưỡng noise chạy, phát hạt ở mép |
| Aura Field | alpha người nở ra + noise trôi lên, cộng sáng SAU người |
| HUD Grid | lưới xanh mảnh, góc ngoặc, số đọc — không dữ liệu giả trên cảnh thật |
| RGB Split | R lệch +8px, B −8px theo X |
| Digital Glitch | lệch lát + dời khối + tách RGB, chùm 2–4f, có seed |
| Film Grain | noise thay đổi theo thời gian (~12), mạnh ở trung tính, thêm SAU khi scale |
| Gate Weave | lệch ±2px theo noise tần thấp, phóng 1.01 |
| Vignette | `vignette=PI/5`, nhẹ, lấy tâm ở chủ thể |
| Day for Night | giảm 2 stop, ngả xanh lạnh, giảm bão hoà, tối trời |
| Color Grading | sau khi cân màu áp look ~60%, giữ màu da |
| Comic Filter | posterize + viền dày + halftone ở vùng tối |
| Starfield | 3 lớp sao thị sai trôi rất chậm, lấp lánh nhẹ |
