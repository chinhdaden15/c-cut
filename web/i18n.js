/* C-Cut — giao diện song ngữ (Tiếng Việt mặc định, English là ngôn ngữ 2).
   Cách làm: giao diện viết bằng tiếng Việt; khi chọn English, mọi chữ trên màn hình (cả chữ sinh ra lúc chạy) được dịch
   theo từ điển dưới đây — khớp nguyên câu trước, rồi tới mẫu có số / tên (RX). Câu chưa có trong từ điển giữ nguyên. */
(function () {
  const KEY = 'ccut_lang';
  let lang = null;
  try { lang = localStorage.getItem(KEY); } catch (e) {}
  if (!lang) lang = /^vi\b/i.test(navigator.language || 'vi') ? 'vi' : 'en';
  window.CCUT_LANG = lang;
  const sync = l => fetch('/api/ccut/settings', { method: 'PUT', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ ui_lang: l }) }).catch(() => {});
  window.setLang = l => { try { localStorage.setItem(KEY, l); } catch (e) {} sync(l).finally(() => location.reload()); };
  setTimeout(() => sync(lang), 1500);          // báo cho máy biết ngôn ngữ → Claude trả lời đúng ngôn ngữ

  const T = {
    // ---- thanh trên / chung
    'Cập nhật': 'Update', 'Để sau': 'Later', 'Chưa có dự án': 'No project', '＋ Dự án': '＋ Project', 'Đang kiểm tra…': 'Checking…',
    'Mất kết nối với C-Cut — app đã tắt. Chạy lại': 'Lost connection to C-Cut — the app has closed. Start it again',
    '(hoặc': '(or', '), trang sẽ tự kết nối lại.': '), this page will reconnect automatically.',
    'Dự án đang mở': 'Current project', 'Tạo dự án mới hoặc mở dự án cũ': 'Create a new project or open an existing one',
    'Đang cập nhật': 'Updating', 'Đóng': 'Close', 'Lưu': 'Save', 'Xoá': 'Delete', 'Sửa': 'Edit', 'Chọn': 'Choose', 'Đổi': 'Change',
    'Bỏ': 'Remove', 'Gửi': 'Send', 'Chép': 'Copy', 'Sao chép': 'Copy', 'Nhập': 'Import', 'Kiểm tra lại': 'Check again',
    '← Quay lại': '← Back', 'vừa xong': 'just now', 'chưa dùng': 'never used', 'lúc ': 'at ',
    // ---- nhập video / kịch bản
    'Video gốc': 'Source video', 'Kéo thả file hoặc thư mục vào đây': 'Drag and drop files or folders here',
    'Chọn file': 'Choose file', 'Chọn thư mục': 'Choose folder', 'Chọn file…': 'Choose file…',
    'Có kịch bản': 'I have a script', 'Chỉ có ý tưởng': 'Just an idea', 'Từ bài báo': 'From a news article',
    'Chọn file kịch bản': 'Choose script file', 'Độ dài video (giây)': 'Video length (seconds)',
    'Cả dọc lẫn ngang': 'Vertical and horizontal', 'Dọc 9:16': 'Vertical 9:16', 'Ngang 16:9': 'Horizontal 16:9',
    'Nhân bản giọng': 'Clone voice', 'Thêm vào hàng chờ': 'Add to queue', '+ Thêm style (.zip)': '+ Add style (.zip)',
    'Nhập ý tưởng video': 'Enter a video idea', 'Dán link bài báo': 'Paste a news article link',
    'Dán kịch bản hoặc chọn file': 'Paste a script or choose a file', 'Đang mở bài báo…': 'Opening the article…',
    'Dán kịch bản vào đây, hoặc chọn file .txt / .docx / .srt': 'Paste the script here, or choose a .txt / .docx / .srt file',
    'Dán kịch bản (một hoặc nhiều video — mỗi video bắt đầu bằng “Video 1:”, “Video 2:”…)': 'Paste a script (one or more videos — start each with “Video 1:”, “Video 2:”…)',
    'Mô tả video bạn muốn, vd: “Video giới thiệu cây son kem lì mới, nhấn mạnh đầu cọ mềm và giữ màu 8 tiếng”': 'Describe the video you want, e.g. “Launch video for a new matte lipstick, highlighting the soft applicator and 8-hour wear”',
    'Dán link bài báo (VnExpress, Tuổi Trẻ, Thanh Niên…). Trang không mở được thì dán tiêu đề + nội dung bài (dòng đầu là tiêu đề). Có thể dặn thêm, vd “nhấn mạnh con số”': 'Paste a news article link. If the page cannot be opened, paste the title + article text (first line = title). You can add instructions, e.g. “emphasise the numbers”',
    'Dán kịch bản, hoặc LINK bài báo (giọng đọc của bài) — phụ đề lấy đúng chữ trong bài, dựng theo khuôn tin tức': 'Paste the script, or a news article LINK (voice of the article) — subtitles follow the article text, built as a news video',
    'Nghe thử giọng': 'Preview voice', 'Tìm style…': 'Search styles…', 'Tự chọn': 'Auto',
    // ---- review
    'Lĩnh vực': 'Category', 'Bất động sản': 'Real estate', 'Công nghệ': 'Technology', 'Mỹ phẩm – skincare': 'Cosmetics – skincare',
    'Ẩm thực': 'Food', 'Sản phẩm khác': 'Other products', 'Phong cách': 'Style', 'Tour bất động sản': 'Property tour',
    'Review trực tiếp': 'Direct review', 'Review tinh tế': 'Refined review', 'Mức thể hiện': 'Energy level', 'Nhẹ nhàng': 'Calm',
    'Cân bằng': 'Balanced', 'Năng động': 'Energetic', 'Font chữ (1 font cho cả clip)': 'Font (one font for the whole clip)',
    'Mặc định (Montserrat)': 'Default (Montserrat)', 'Tỷ lệ': 'Aspect ratio', 'Thời lượng (giây)': 'Duration (seconds)',
    'Phụ đề theo lời': 'Subtitles from speech', 'Ghi chú': 'Notes', 'Bắt buộc giữ': 'Must keep', 'Cần loại': 'Remove',
    'Brief, thông số, giá… (có nguồn)': 'Brief, specs, prices… (with sources)', 'Câu/cảnh phải có': 'Lines/shots that must appear',
    'Đoạn/nội dung bỏ đi': 'Parts/content to drop', '+ Video tham khảo': '+ Reference video', ' video tham khảo': ' reference videos',
    'Tư liệu dựng: thêm ở mục 1 (cả thư mục = 1 review). Video chỉ để tham khảo phong cách: thư mục con': 'Footage: add it in step 1 (a whole folder = 1 review). Videos only for style reference: subfolder',
    'hoặc nút dưới.': 'or the button below.',
    'Chữ Montserrat của app.': 'The app’s Montserrat font.', 'Font này chỉ có chữ HOA: chữ phụ viết thường cũng sẽ hiện IN HOA.': 'This font only has CAPITALS: secondary lowercase text will also show in CAPITALS.',
    'Chữ nhấn IN HOA, chữ phụ viết thường.': 'Highlighted text in CAPITALS, secondary text in lowercase.',
    // ---- xuất / chạy
    'Nơi xuất': 'Export to', 'Khổ theo clip gốc · 30fps · MP4': 'Same frame as source · 30fps · MP4', 'Bắt đầu dựng': 'Start editing',
    'Tạm dừng': 'Pause', 'Dừng': 'Stop', '▶ Tiếp tục': '▶ Resume', '⏸ Tạm dừng': '⏸ Pause', 'Đang dừng…': 'Stopping…',
    'Chưa có dữ liệu.': 'No data yet.', 'Xem trước': 'Preview', 'Video đã xuất sẽ hiện ở đây — mỗi video một ô để xem.': 'Exported videos appear here — one tile per video.',
    '⤢ Phóng to': '⤢ Enlarge', '⬇ Lưu': '⬇ Save', 'Ảnh tĩnh ở các điểm nhấn sẽ hiện sau bước Kiểm tra.': 'Stills of key moments appear after the Check step.',
    'Dòng thời gian': 'Timeline', 'Nói': 'Speech', 'Tiến trình': 'Progress', 'Chưa chạy': 'Not started', 'Nguồn và bản quyền': 'Sources and credits',
    'Phóng to (Esc để thu lại)': 'Enlarge (Esc to shrink)', 'Lưu video về máy': 'Save video to this computer',
    'Mở thư mục chứa video đã xuất': 'Open the export folder', 'Nhập': 'Import', 'Chép lời': 'Transcribe', 'Tách nền': 'Remove background',
    'Kế hoạch': 'Plan', 'Kiểm tra': 'Check', 'Xuất': 'Export', 'Chờ Claude lập kế hoạch': 'Waiting for Claude to plan', 'Đã dừng': 'Stopped',
    'chờ': 'waiting', 'đang dựng': 'editing', 'lỗi': 'error', 'đã dừng': 'stopped', 'chờ Claude': 'waiting for Claude',
    'Claude đang lập kế hoạch': 'Claude is planning', 'chờ giới hạn Claude làm mới': 'waiting for the Claude limit to reset',
    'Claude đang tự sửa lỗi kiểm tra': 'Claude is fixing check errors', 'BẢN QUYỀN': 'LICENCE', 'cần mua skill — bấm 🔑': 'skill purchase needed — click 🔑',
    'không kênh': 'no channel', 'Kênh: Claude tự nhận': 'Channel: detected by Claude', 'Không kênh (nền xanh)': 'No channel (blue background)',
    'Đã chọn kênh — xuất lần sau dùng nền kênh này': 'Channel selected — next export uses this channel’s background',
    'Claude sẽ tự nhận kênh': 'Claude will detect the channel', 'Nền Motion Graphics theo kênh': 'Motion Graphics background by channel',
    'Đã có kịch bản — bấm để xem/sửa': 'Has a script — click to view/edit', 'Thêm kịch bản để đối chiếu': 'Add a script to cross-check',
    '📄 kịch bản': '📄 script', '+ kịch bản': '+ script', 'Kịch bản': 'Script', 'Kịch bản ·': 'Script ·', 'Kịch bản: ': 'Script: ',
    'Chưa có kịch bản': 'No script', 'Dán kịch bản cho video này': 'Paste the script for this video',
    'Đã lưu kịch bản': 'Script saved', 'Đã xoá kịch bản': 'Script deleted', 'Không đọc được file: ': 'Could not read file: ',
    'Sẽ đọc lại bằng giọng AI: ': 'Will re-read with an AI voice: ', 'Tải bộ giọng đọc trước': 'Download the voice pack first',
    'Chưa tải bộ giọng đọc': 'Voice pack not downloaded', ' (giọng của bạn)': ' (your voice)',
    '(bấm để chép toàn bộ lỗi)': '(click to copy the full error)', 'Đã chép lỗi — dán gửi cho người hỗ trợ': 'Error copied — paste it to support',
    'Đã chép nguồn': 'Sources copied', 'Đã tiếp tục dựng': 'Editing resumed', 'Đã tạm dừng — bấm Tiếp tục để chạy tiếp đúng chỗ': 'Paused — click Resume to continue from here',
    'Đang cài style…': 'Installing style…', 'Đã thêm style': 'Style added', 'Đã đổi tên dự án': 'Project renamed',
    'Đang dựng — dừng trước khi tạo dự án mới': 'Editing in progress — stop first before creating a new project',
    'Claude sẽ đối chiếu lời nói trong clip với kịch bản: sửa chính tả, tên riêng, số liệu theo kịch bản; chỗ nói khác, bỏ sót hoặc nói thêm Claude tự quyết và báo lại trong khung chat.': 'Claude compares the speech in the clip with the script: fixes spelling, names and numbers to match the script; where the speaker differs, skips or adds, Claude decides and reports in the chat.',
    'Giọng đọc trong file không hay? App lấy link / nội dung bài (hoặc kịch bản) ở trên làm lời, đọc bằng giọng AI rồi dựng như Text to Video.': 'Not happy with the voice in the file? The app uses the link / article (or script) above as the text, reads it with an AI voice and builds it like Text to Video.',
    'Đọc lại bằng giọng AI': 'Re-read with an AI voice',
    // ---- thư mục
    'Thư mục ·': 'Folder ·', 'Các video trong thư mục này là:': 'The videos in this folder are:', 'Video riêng': 'Separate videos',
    'mỗi file dựng thành 1 video': 'each file becomes 1 video', 'Các đoạn của 1 video': 'Parts of 1 video', 'Claude chọn take, ghép, có b-roll': 'Claude picks takes, joins them, adds b-roll',
    'các đoạn của 1 video': 'parts of 1 video', 'video riêng': 'separate videos', 'đoạn': 'parts', 'đoạn → 1 video': 'parts → 1 video', ' review riêng': ' separate reviews',
    'Kịch bản (không bắt buộc) — có thì Claude ghép đúng thứ tự và chính tả theo kịch bản': 'Script (optional) — if given, Claude follows its order and spelling',
    'Dán kịch bản nếu có. Để trống: Claude tự nghe các đoạn, gom các lần nói lại, chọn take tốt nhất và sắp thứ tự theo mạch lời nói.': 'Paste a script if you have one. Leave empty: Claude listens to the parts, groups retakes, picks the best take and orders them by the flow of speech.',
    // ---- Claude
    'Đang kiểm tra Claude…': 'Checking Claude…', 'Thêm video và bấm Bắt đầu dựng — Claude sẽ nhận việc ở bước Kế hoạch.': 'Add a video and click Start editing — Claude takes over at the Plan step.',
    'Góp ý cho Claude…': 'Feedback for Claude…', 'Kéo để đổi độ rộng khung Claude · bấm đúp để về mặc định': 'Drag to resize the Claude panel · double-click to reset',
    'Claude đang làm việc…': 'Claude is working…', 'Chưa có tin nhắn.': 'No messages yet.', 'Chưa có dự án — thêm video và bấm Bắt đầu dựng': 'No project yet — add a video and click Start editing',
    'Làm mới giới hạn': 'Refresh limits', 'Giới hạn 5 giờ': '5-hour limit', 'Giới hạn 7 ngày': '7-day limit', 'Model dựng': 'Editing model',
    'Chưa lấy được giới hạn.': 'Could not read limits yet.', 'Đã chạm giới hạn — Claude tạm dừng tới khi làm mới.': 'Limit reached — Claude pauses until it resets.',
    'Claude sẵn sàng · ': 'Claude ready · ', 'Đang làm · ': 'Working · ',
    // ---- cài đặt
    'Cài đặt': 'Settings', 'Dự án': 'Project', 'Công cụ': 'Tools', 'Thông báo': 'Notifications', 'Nền kênh': 'Channel backgrounds',
    'Nơi lưu dữ liệu làm việc của dự án (mặc định khi tạo dự án mới)': 'Where project working data is stored (default for new projects)',
    'Nơi xuất mặc định': 'Default export folder', 'Ngôn ngữ nói trong clip': 'Spoken language in the clip', 'Tự nhận (khuyên dùng)': 'Auto-detect (recommended)',
    'Tiếng Việt': 'Vietnamese',
    'Google Maps API key (bản đồ vệ tinh — bật Map Tiles API trong Google Cloud; để trống = bản đồ đường phố OpenStreetMap)': 'Google Maps API key (satellite maps — enable the Map Tiles API in Google Cloud; leave empty = OpenStreetMap street map)',
    'Model Claude khi dựng': 'Claude model for editing', 'Sonnet 5.5 — nhanh (khuyên dùng)': 'Sonnet 5.5 — fast (recommended)',
    'Opus 5.5 — kỹ hơn, chậm hơn, tốn giới hạn hơn': 'Opus 5.5 — more thorough, slower, uses more of your limit',
    'Thiết lập lần đầu…': 'First-time setup…', 'Ngôn ngữ giao diện': 'Interface language',
    'Nền Motion Graphics theo kênh của video. Mỗi kênh 5 nền, cứ': 'Motion Graphics backgrounds by video channel. Each channel has 5 backgrounds; every',
    'video xuất xong thì đổi sang nền kế tiếp, xoay vòng.': 'exported videos it switches to the next one, in rotation.',
    'Cho phần mềm khác trên máy này (CN.AI…) điều khiển C-Cut. Xoá hoặc đổi khoá là phần mềm đang dùng khoá đó mất quyền ngay.': 'Let other software on this computer (CN.AI…) control C-Cut. Deleting or rotating a key revokes that software’s access immediately.',
    'Bật API': 'Enable API', 'Địa chỉ API': 'API address', 'Khoá API': 'API keys', '+ Tạo khoá': '+ Create key', 'Đổi khoá': 'Rotate key', 'Bấm lần nữa': 'Click again',
    'Dán địa chỉ và khoá vào phần mềm cần kết nối. Chỉ dùng được trên máy này, khi C-Cut đang mở.': 'Paste the address and key into the software that connects. Works only on this computer while C-Cut is open.',
    '— phần mềm có khoá đúng được phép gọi': '— software with a valid key may call it', '— đang tắt, mọi lệnh gọi từ ngoài đều bị từ chối': '— off, all external calls are rejected',
    'Chưa có khoá nào.': 'No keys yet.', 'Đã bật API': 'API enabled', 'Đã tắt API': 'API disabled', 'Đã sao chép': 'Copied',
    ' · <span style="color:var(--ok)">khoá mới — sao chép dán vào phần mềm</span>': ' · <span style="color:var(--ok)">new key — copy it into your software</span>',
    'Âm báo khi xong / lỗi': 'Sound when done / on error', 'Thông báo hệ thống': 'System notifications', 'Đã lưu cài đặt': 'Settings saved', 'Đã lưu': 'Saved',
    'Đang kiểm tra công cụ…': 'Checking tools…', 'Chưa có thông báo.': 'No notifications yet.',
    // ---- dự án
    '＋ Dự án mới': '＋ New project', '📂 Mở dự án cũ': '📂 Open project', 'Mở thư mục dự án khác…': 'Open another project folder…',
    'Tạo dự án mới. Thư mục dưới đây chỉ chứa': 'Create a new project. The folder below only holds', 'dữ liệu làm việc': 'working data',
    '(file tạm, ảnh, kế hoạch, lịch sử chat) — thoát app vẫn còn. Video thành phẩm được xuất riêng ra': '(temporary files, images, plans, chat history) — kept after you quit. Finished videos are exported separately to',
    ', đặt theo tên dự án.': ', named after the project.', 'Tên dự án': 'Project name', 'Nơi lưu dữ liệu làm việc': 'Working data folder', 'Tạo dự án': 'Create project',
    'Chưa có dự án nào ở thư mục này.': 'No projects in this folder yet.', 'đang mở': 'open', 'Dự Án Mới': 'New Project',
    // ---- thiết lập lần đầu
    'Thiết lập lần đầu': 'First-time setup', 'C-Cut đã có sẵn Python, ffmpeg, font, SFX và style. Chỉ còn vài thứ cần có trên máy bạn:': 'C-Cut already includes Python, ffmpeg, fonts, SFX and styles. Only a few things are needed on your computer:',
    'Bắt đầu dùng': 'Get started', 'Cài Claude': 'Install Claude', 'Đã cài.': 'Installed.', 'Đăng nhập Claude': 'Sign in to Claude', 'Đăng nhập': 'Sign in',
    'Cài Claude trước.': 'Install Claude first.', 'Tải model chép lời (~3 GB, một lần)': 'Download the transcription model (~3 GB, once)', 'Đã có.': 'Ready.',
    'Công cụ dựng HyperFrames (tự cài)': 'HyperFrames rendering tool (installs itself)', 'Mở cửa sổ cài đặt': 'Open the installer window', 'Cài Git for Windows': 'Install Git for Windows',
    'Đã đủ — có thể bắt đầu.': 'All set — you can start.', 'Làm xong từng bước rồi bấm Kiểm tra lại.': 'Complete each step, then click Check again.',
    'Đã chép lệnh': 'Command copied', 'Đã mở cửa sổ — làm theo hướng dẫn trong đó': 'Window opened — follow the instructions there',
    'Đăng xuất tài khoản Claude hiện tại và đăng nhập tài khoản khác?': 'Sign out of the current Claude account and sign in with another?',
    'Đang dựng — dừng trước khi đổi tài khoản': 'Editing in progress — stop first before switching accounts',
    'Đã đăng xuất — đăng nhập tài khoản mới trong cửa sổ vừa mở, rồi bấm Kiểm tra lại': 'Signed out — sign in with the new account in the window that opened, then click Check again',
    // ---- bản quyền
    'Bản quyền skill': 'Skill licences', 'Mỗi skill được dùng thử 2 video; mua một lần dùng vĩnh viễn trên máy này.': 'Each skill can be tried on 2 videos; buy once to use it forever on this computer.',
    'Đã có mã bản quyền (mua qua fanpage / được tặng)': 'I have a licence code (bought via the fanpage / gifted)', 'Kích hoạt': 'Activate',
    'Mua bằng chuyển khoản': 'Buy by bank transfer', 'Tạo mã QR chuyển khoản': 'Create a transfer QR code',
    'Quét mã bằng app ngân hàng — số tiền và nội dung đã điền sẵn. Skill tự mở khoá khi tiền về (thường dưới 1 phút).': 'Scan with your banking app — amount and reference are pre-filled. The skill unlocks when the payment arrives (usually under 1 minute).',
    'Đang chờ tiền về…': 'Waiting for payment…', 'Đồng bộ lại': 'Sync again', 'Đã đồng bộ': 'Synced', 'Miễn phí': 'Free', 'Đã mua': 'Owned', 'Hết lượt thử': 'No trials left',
    'Bạn đã sở hữu toàn bộ skill.': 'You own all skills.', 'Chưa mở bán hoặc chưa kết nối được máy chủ — thử “Đồng bộ lại”.': 'Not on sale yet or the server is unreachable — try “Sync again”.',
    'Email hoặc số Zalo (để nhận lại mã khi cần — không bắt buộc)': 'Email or Zalo number (to recover your code if needed — optional)',
    'Đã nhận tiền — skill đã mở khoá trên máy này.': 'Payment received — the skill is unlocked on this computer.', 'Chưa có style': 'No styles yet', 'Không thấy style.': 'No style found.',
    // ---- giọng đọc
    'Giọng đọc': 'Voices', 'Tải bộ giọng đọc': 'Download voice pack', 'Giọng có sẵn đọc được tiếng Việt và tiếng Anh, chạy ngay trên máy (không cần mạng sau khi tải).': 'Built-in voices read Vietnamese and English and run on this computer (no internet needed after download).',
    'Đọc thử câu của bạn': 'Try your own sentence', 'Chậm': 'Slow', 'Vừa': 'Normal', 'Rất nhanh': 'Very fast', 'Đọc thử': 'Read aloud', 'Nhân bản giọng của bạn': 'Clone your voice',
    'Chọn file thu âm hoặc video có tiếng (10–30 giây nói tự nhiên, nơi yên tĩnh là tốt nhất).': 'Choose a recording or a video with speech (10–30 seconds of natural speech, ideally in a quiet place).',
    'Đây là giọng của tôi, hoặc tôi được người có giọng này cho phép dùng. Tôi không dùng giọng nhân bản để mạo danh hay lừa dối người khác.': 'This is my voice, or I have permission from its owner. I will not use the cloned voice to impersonate or deceive anyone.',
    'Nhập câu bất kỳ, tiếng Việt hoặc tiếng Anh…': 'Type any sentence, in Vietnamese or English…', 'Tên giọng (vd: Giọng của tôi)': 'Voice name (e.g. My voice)',
    'Hàng chờ trống — thêm video, kịch bản hoặc file giọng trước': 'The queue is empty — add a video, script or voice file first', 'Giọng của bạn': 'Your voice', '▶ Nghe thử': '▶ Preview', 'Nghe thử': 'Preview', 'Đang tạo…': 'Generating…', 'Đang nhân bản…': 'Cloning…', 'Xoá giọng này?': 'Delete this voice?',
    'Nhập câu cần đọc': 'Type a sentence to read', 'Chọn file thu âm': 'Choose a recording', 'Đặt tên cho giọng': 'Name the voice',
    'Cần xác nhận quyền dùng giọng': 'Please confirm you have the right to use this voice',
    'Công cụ đủ': 'Tools ready', 'Chưa kiểm tra công cụ': 'Tools not checked yet', 'Đã đăng nhập': 'Signed in', 'Đổi tài khoản': 'Switch account',
    'Cài ngay': 'Install now', 'App tự cài khi mở (tự tải Node.js nếu máy chưa có).': 'The app installs it on launch (downloads Node.js if missing).',
    'Dựng chữ động, sơ đồ, biểu đồ, nhãn/spotlight bằng HTML.': 'Builds kinetic text, diagrams, charts and labels/spotlights in HTML.',
    'Trình duyệt sẽ mở để đăng nhập tài khoản Claude.': 'A browser window will open to sign in to your Claude account.', 'Đã đăng nhập:': 'Signed in:',
    'Kịch bản hoặc yêu cầu → giọng đọc (6 giọng có sẵn / giọng nhân bản) → video kết hợp video minh hoạ thật + motion graphic; xuất cả dọc 9:16 lẫn ngang 16:9': 'Script or request → voice-over (built-in or cloned voices) → video combining real footage + motion graphics; exports both vertical 9:16 and horizontal 16:9',
    'Dựng video review từ bộ footage của bạn (bất động sản, sản phẩm): chọn take, ghép lời với B-roll, phụ đề + chữ thông tin, xuất dọc và/hoặc ngang': 'Builds review videos from your footage (real estate, products): picks takes, matches speech with B-roll, subtitles + info text, exports vertical and/or horizontal',
    'Mọi lĩnh vực · chữ neon 3 màu · Motion Graphics nền xanh mỗi ~15s': 'Any topic · 3-colour neon text · Motion Graphics every ~15s',
    'Motion graphic 100% từ voice (file âm thanh, hoặc lấy tiếng từ video): bản đồ, sơ đồ, typography; xuất cả dọc 9:16 lẫn ngang 16:9': '100% motion graphics from a voice-over (audio file, or audio from a video): maps, diagrams, typography; exports both vertical 9:16 and horizontal 16:9',
    // ---- tên giọng
    'Nam · giọng hướng dẫn': 'Male · guide voice', 'Nam · giọng 2': 'Male · voice 2', 'Nam · giọng 3': 'Male · voice 3', 'Nam · ông già ngộ đạo': 'Male · wise old man',
    'Nữ · Ngọc Huyền (Bắc, tự nhiên)': 'Female · Ngọc Huyền (Northern, natural)', 'Nữ · giọng 2': 'Female · voice 2', 'Nữ · Quỳnh Anh (Bắc, kể chuyện)': 'Female · Quỳnh Anh (Northern, storytelling)',
    'English · Adam (nam, Mỹ)': 'English · Adam (male, US)', 'English · Heart (nữ, Mỹ)': 'English · Heart (female, US)', 'English · Bella (nữ, Mỹ)': 'English · Bella (female, US)',
  };
  const RX = [
    [/^Thiếu (\d+) công cụ$/, '$1 tools missing'], [/^(\d+) mục cần chú ý$/, '$1 items need attention'],
    [/^Claude sẵn sàng · (.+)$/, 'Claude ready · $1'], [/^Đang làm · (.+)$/, 'Working · $1'], [/^số liệu (.+)$/, 'data $1'],
    [/^Làm mới sau (.+) \((\d+:\d+) T(\d)\)$/, 'Resets in $1 ($2)'], [/^Làm mới sau (.+)$/, 'Resets in $1'],
    [/^(\d+) phút trước$/, '$1 min ago'], [/^Sẵn sàng — bản ghim (.*)\. Mọi style video dùng chung\.$/, 'Ready — pinned version $1. Shared by all video styles.'],
    [/^(\d+) phút$/, '$1 min'], [/^(\d+) giây$/, '$1 s'], [/^ ?(\d+) phút trước$/, '$1 min ago'], [/^(\d+) giờ trước$/, '$1 h ago'], [/^(\d+) ngày trước$/, '$1 days ago'],
    [/^(\d+) ngày (\d+) giờ$/, '$1 d $2 h'], [/^(\d+) giờ (\d+) phút$/, '$1 h $2 min'], [/^Đã dùng$/, 'Used'],
    [/^Đã mở dự án (.+)$/, 'Opened project $1'], [/^Đã tạo dự án (.+)$/, 'Created project $1'], [/^Đã thêm (.+)$/, 'Added $1'], [/^Đã lưu: (.+)$/, 'Saved: $1'],
    [/^Đang nhận (.+)…$/, 'Receiving $1…'], [/^Đã kích hoạt (.+)$/, 'Activated $1'], [/^Đã thêm giọng “(.+)”$/, 'Added voice “$1”'],
    [/^Kênh: (.+)$/, 'Channel: $1'], [/^Kênh: tự nhận · (.*)$/, 'Channel: auto · $1'], [/^Việc do (.+) gửi qua API$/, 'Job sent by $1 via API'],
    [/^(.+) đang điều khiển C-Cut qua API$/, '$1 is controlling C-Cut via the API'], [/^Thử còn (\d+)\/(\d+)$/, 'Trials left $1/$2'],
    [/^Có bản mới v(.+)$/, 'New version v$1'], [/^Mã máy: (.+)$/, 'Device ID: $1'], [/^Đã nhập kịch bản \((\d+) ký tự\)$/, 'Script imported ($1 characters)'],
    [/^Cập nhật C-Cut lên v(.+)\? App sẽ tự tắt, cài rồi mở lại\. Dự án và cài đặt giữ nguyên\.$/, 'Update C-Cut to v$1? The app will close, install and reopen. Projects and settings are kept.'],
    [/^Đang tải bộ giọng đọc… \(khoảng (\d+) MB, chỉ tải 1 lần\)$/, 'Downloading the voice pack… (about $1 MB, one time only)'],
    [/^Bộ giọng đọc chưa được tải \(khoảng (\d+) MB, chỉ tải 1 lần\)\.$/, 'The voice pack is not downloaded yet (about $1 MB, one time only).'],
    [/^Claude đã làm (\d+) phút$/, 'Claude worked $1 min'], [/^còn ~(.+)$/, '~$1 left'], [/^Nền (\d+)$/, 'Background $1'], [/^● đang dùng$/, '● in use'],
    [/^Đã xoá khoá “(.+)” — phần mềm dùng khoá này mất quyền ngay$/, 'Deleted key “$1” — software using it lost access immediately'],
    [/^Đã đổi khoá — khoá cũ hết hiệu lực, khoá mới đã sao chép$/, 'Key rotated — the old key is revoked, the new key is copied'],
    [/^(\d+) loại SFX$/, '$1 SFX types'], [/^Nói dài nhất (.+)$/, 'Longest talk $1'], [/^Chữ (\d+)$/, 'Text $1'],
    [/^dùng (.+)$/, 'used $1'], [/^Đọc câu (\d+)\/(\d+)$/, 'Reading sentence $1/$2'],
  ];
  // trạng thái / thông báo gửi từ máy (job.activity, toast lỗi…) — dịch theo cụm thường gặp, phần còn lại giữ nguyên
  const PH = [
    ['Hết giới hạn Claude — tự làm tiếp lúc', 'Claude limit reached — resumes automatically at'], ['Kiểm tra giọng đọc (chép lời lại)', 'Checking the voice (re-transcribing)'],
    ['Dựng chữ động, sơ đồ, biểu đồ, nhãn/spotlight bằng HTML.', 'Builds kinetic text, diagrams, charts and labels/spotlights in HTML.'],
    ['không thấy ffmpeg', 'ffmpeg not found'], ['Đọc câu', 'Reading sentence'], ['Kiểm tra lại câu', 'Re-checking sentence'], ['Phụ đề theo kịch bản', 'Subtitles from script'],
    ['Đang xuất', 'Exporting'], ['Đang dựng', 'Editing'], ['Đang tải', 'Downloading'], ['Đang chép lời', 'Transcribing'], ['Đang kiểm tra', 'Checking'],
    ['Claude chưa viết xong lời bản tin — xem khung chat', 'Claude has not finished the news script — see the chat'],
    ['Claude dừng giữa chừng', 'Claude stopped midway'], ['xem khung chat', 'see the chat'], ['Xuất xong', 'Export finished'],
    [' phút trước', ' min ago'], [' giờ trước', ' h ago'], [' ngày trước', ' days ago'], [' phút', ' min'], [' giờ', ' h'], [' ngày', ' d'], [' giây', ' s'],
  ];
  const tr = s => {
    if (lang !== 'en' || !s) return s;
    const lead = s.match(/^\s*/)[0], tail = s.match(/\s*$/)[0], core = s.trim();
    if (!core || !/[À-ỹĐđ]/.test(core)) return s;
    if (T[core] != null) return lead + T[core] + tail;
    if (T[s] != null) return T[s];
    let out = core;
    for (const [r, v] of RX) if (r.test(core)) { out = core.replace(r, v); break; }
    for (const [a, b] of PH) if (out.includes(a)) out = out.split(a).join(b);
    return lead + out + tail;
  };
  window.tr = tr;
  if (lang !== 'en') return;
  document.documentElement.lang = 'en';
  const ATTR = ['placeholder', 'title', 'aria-label'];
  const walk = root => {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      const p = n.parentNode;
      if (!p || /^(SCRIPT|STYLE|TEXTAREA)$/.test(p.nodeName) || p.closest && p.closest('.msg, .chatmsg, #msgs > :not(.empty)')) continue;   // lời Claude giữ nguyên
      const v = tr(n.nodeValue);
      if (v !== n.nodeValue) n.nodeValue = v;
    }
    (root.querySelectorAll ? root.querySelectorAll('[placeholder],[title],[aria-label],option') : []).forEach(e => {
      ATTR.forEach(a => { const v = e.getAttribute(a); if (v) { const t = tr(v); if (t !== v) e.setAttribute(a, t); } });
    });
  };
  const go = () => {
    walk(document.body);
    new MutationObserver(ms => {
      for (const m of ms) {
        if (m.type === 'characterData') { const v = tr(m.target.nodeValue); if (v !== m.target.nodeValue) m.target.nodeValue = v; }
        else if (m.type === 'attributes') { const e = m.target, v = e.getAttribute(m.attributeName); if (v) { const t = tr(v); if (t !== v) e.setAttribute(m.attributeName, t); } }
        else m.addedNodes.forEach(x => x.nodeType === 3 ? (x.nodeValue = tr(x.nodeValue)) : x.nodeType === 1 && walk(x));
      }
    }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTR });
  };
  const _alert = window.alert, _confirm = window.confirm;
  window.alert = m => _alert(tr(String(m)));
  window.confirm = m => _confirm(tr(String(m)));
  document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', go) : go();
})();
