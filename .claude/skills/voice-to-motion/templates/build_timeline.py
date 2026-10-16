"""Builder mẫu Voice to Motion — chép vào thư mục dự án rồi THAY phần nội dung theo lời của file.
Chạy: .venv/bin/python <dự-án>/build_timeline.py            (ghi cả timeline_9x16.json và timeline_16x9.json)
      .venv/bin/python <dự-án>/build_timeline.py 9x16       (chỉ một tỷ lệ — khi người dùng nói “Dựng dọc”/“Dựng ngang”)

Bố cục dọc/ngang, cỡ chữ, căn lề, hiệu ứng vào/ra, camera bản đồ: kit tự tính theo tỷ lệ. Chỉ viết NỘI DUNG + MỐC.
Khối có sẵn (s = K.scene(...)):
  chữ      s.title(text, t, size="xl|l|m|s", hl="cụm tô màu") · s.lead(t0, t1) câu dẫn chạy theo lời · s.tag("TUY NHIÊN", t)
  hình     s.icons([(icon, nhãn, t), …], connect=True) · s.cards([(icon, chữ, t), …]) · s.compare((icon, nhãn), (icon, nhãn), t_a, t_b)
           s.stat(1.5, t, "nhãn", prefix="▲ ", suffix="%") · s.bullets([(chữ, t), …]) · s.meter(0.8, t, "nhãn") · s.bars([(nhãn, số)], t)
           s.quote(câu, t, source=…, highlight=…) · s.image(src, t, label, source) · s.arrow(id_a, id_b, t)
  bản đồ   K.world_map() | K.provinces([...]) (lớp nền, gọi 1 lần) · K.map_until(t) (sau t: đồ họa riêng, bỏ nền bản đồ)
           s.region("VNM", t) tô dần theo ranh giới, mỗi nước một màu (K.color) · s.region(["CHN","IND"], t) hai màu khác nhau
           s.focus(region_id, t) giảm nhấn phần còn lại · s.halo(lonlat, t) vòng dẫn mắt (không phải ranh giới) · s.backdrop() phủ nền
           s.place(lonlat, "MỸ", t, inside={"iso": "USA"}) tên trắng viền tối · s.pin · s.callout(…) ← CHỈ vật nhỏ: đường, dự án, cầu, nút giao
           s.route(src, feature, t, d) · s.route_label(…) · s.look(box, t, dur) · s.story(khung_rộng, khung_chủ_thể, t_est, t_focus[, resolve, t_res])
  camera   Establish → Focus → Explain (kit tự trôi/xoay nhẹ ±2° khi cảnh bản đồ đứng yên > 2,2s) → Resolve. Không rung, không xoay vòng.
  âm thanh SFX tự sinh theo chuyển động; muốn nhấn riêng: s.sound(t, "impact"|"money"|…)
Icon: tên Uicons solid-rounded (dollar, bank, chart-line-up, house, users, heart, leaf, clock, percentage, globe, …).
Mốc: K.find("cụm từ") = giây bắt đầu nói; K.find("cụm", after=t) tìm sau t; K.find("cụm", end=True) = giây nói xong.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # dự án nằm ngoài thư mục app vẫn chạy được
sys.path.insert(0, ".")
from thagent.v2m.kit import build

# kinh/vĩ độ + khung (lon0, lat0, lon1, lat1) dùng trong bài (ví dụ)
# Mỹ ghi kinh độ +360 (bản lặp phía đông) → camera đi từ châu Á sang Mỹ qua Thái Bình Dương, quãng ngắn và đúng hướng,
# thay vì quét ngược 200° qua châu Phi. Hình học địa lý giữ nguyên.
VN_BOX, ASIA_BOX, CHN_IND = (101, 7, 118, 24), (62, 4, 140, 52), (66, 6, 125, 50)
US_BOX, PACIFIC, DC = (234, 23, 294, 50), (95, -15, 300, 62), (-77.04 + 360, 38.9)


def content(K):
    f = K.find
    # ---------- THAY TỪ ĐÂY: nội dung theo lời của file ----------
    K.world_map()
    # S1 — Establish VN → Resolve ra thế giới → Focus Mỹ (camera có diễn tiến, lãnh thổ tô dần)
    s = K.scene(0, f("Tại đây"), "mở đầu: VN → Mỹ")
    s.look(VN_BOX, 0.01, 0.01)
    s.region("VNM", 0.15, until_s=f("nửa vòng") + 0.4)
    s.place((105.8, 16.0), "VIỆT NAM", 0.9, size=40, inside={"iso": "VNM"}, until_s=f("nửa vòng") + 0.2)
    s.title("MUỐN HIỂU GIÁ VÀNG\nỞ VIỆT NAM", 0.1, size="m", hl="GIÁ VÀNG", ry=0.3)
    s.look(PACIFIC, f("nửa vòng") + 0.3, 1.5)                          # Resolve: lùi ra thế giới
    s.look(US_BOX, f("nước Mỹ") + 0.5, 1.3)                          # Focus: sang chủ thể mới
    us = s.region("USA", f("nước Mỹ"), until_s=f("Bây giờ"))
    s.place((-99.0 + 360, 39.5), "MỸ", f("nước Mỹ") + 0.4, size=56, inside={"iso": "USA"}, until_s=f("Bây giờ"))

    # S2 — FED (Washington) → đô la → vàng: halo dẫn mắt + giảm nhấn phần còn lại, camera tiến vào bờ Đông
    s = K.scene(f("Tại đây"), f("Khi lợi suất"), "FED → USD → vàng")
    s.look((264, 30, 290, 46), f("chính sách"), 1.4)
    s.halo(DC, f("dự trữ"))
    s.focus(us, f("dự trữ"), 0.5)
    s.title("LÃI SUẤT FED", f("chính sách"), size="l", hl="FED", ry=0.25)
    s.icons([("bank", "Lãi suất FED", f("lãi suất")), ("dollar", "Đồng đô la", f("đồng đô la")),
             ("coins", "Sức hút của vàng", f("sức hấp dẫn"))], connect=True)

    # S3 — ý không gắn vị trí → cảnh đồ họa riêng (phủ nền), hai vế đổi trạng thái theo lời
    s = K.scene(f("Khi lợi suất"), f("Bây giờ"), "lợi suất vs vàng")
    s.backdrop()
    s.tag("KHI LỢI SUẤT TĂNG", f("Khi lợi suất"), ry=0.2, color=K.th["alt"])
    s.lead(f("vàng có thể"), f("bản thân"), ry=0.75)
    a, b = s.compare(("chart-line-up", "Lợi suất ▲"), ("coins", "Vàng: không trả lãi"), f("lợi suất"), f("không trả lãi"))
    s.animate(a, f("vàng có thể"), 0.5, {"scale": 1.15})          # lợi suất hút tiền…
    s.animate(b, f("áp lực"), 0.6, {"opacity": 0.5, "scale": 0.9})  # …vàng chịu áp lực

    # S4 — châu Á: Establish → Focus Trung Quốc + Ấn Độ (2 màu khác nhau) → Explain trôi nhẹ
    s = K.scene(f("Bây giờ"), f("Cuối cùng"), "nhu cầu châu Á", transition=None)
    s.story(ASIA_BOX, CHN_IND, f("châu Á") + 0.3, f("Trung Quốc") + 0.3, est_dur=1.8)
    s.region(["CHN", "IND"], f("Trung Quốc"))
    s.place((103.0, 34.0), "TRUNG QUỐC", f("Trung Quốc") + 0.6, size=40, inside={"iso": "CHN"})
    s.place((79.0, 22.5), "ẤN ĐỘ", f("Ấn Độ") + 0.4, size=40, inside={"iso": "IND"})
    s.title("NHU CẦU VÀNG\nTOÀN CẦU", f("nhu cầu"), size="m", hl="TOÀN CẦU", ry=0.22)

    # S5 — về Việt Nam: camera bay về, tô VN, giảm nhấn khu vực, 3 yếu tố theo lời
    s = K.scene(f("Cuối cùng"), f("Vì thế"), "yếu tố trong nước")
    s.look(VN_BOX, f("Việt Nam") + 0.1, 1.4)
    vn = s.region("VNM", f("Việt Nam") + 0.3, dim=0.45)
    s.place((105.8, 16.0), "VIỆT NAM", f("Giá vàng"), size=40, inside={"iso": "VNM"})
    s.title("GIÁ VÀNG TRONG NƯỚC", f("Giá vàng"), size="m", ry=0.25)
    s.bullets([("Tỷ giá", f("tỷ giá")), ("Cung – cầu", f("cung cầu")), ("Chênh lệch mua – bán", f("tranh lệch"))])
    K.map_until(f("Vì thế"))                                          # từ đây nội dung không gắn vị trí → đồ họa riêng

    # S6 — kết luận: thế giới tăng ≠ người mua trong nước có lời (đối tượng đổi trạng thái)
    s = K.scene(f("Vì thế"), f("Trong thời gian"), "≠ chắc có lời")
    s.title("VÀNG THẾ GIỚI TĂNG\n≠ CHẮC CHẮN CÓ LỜI", f("vàng thế giới"), size="m", hl="≠ CHẮC CHẮN CÓ LỜI", ry=0.3)
    a, b = s.compare(("globe", "Vàng thế giới ▲", K.th["good"]), ("wallet", "Người mua\ntrong nước", K.th["muted"]),
                     f("thế giới"), f("người mua"), vs="→")
    s.animate(b, f("chắc chắn"), 0.4, {"scale": 0.92})
    q = s.add({"type": "icon", "name": "question", "size": 54, "color": K.th["alt"], "parent": b, "x": 70, "y": -70})
    s.reveal(q, f("chắc chắn"), "pop", 0.3)

    # S7 — hai kịch bản: lần lượt sáng lên, kịch bản trước lùi xuống khi nói kịch bản sau
    s = K.scene(f("Trong thời gian"), f("Một thị trường"), "hai kịch bản")
    s.tag("THỜI GIAN TỚI", f("Trong thời gian"), ry=0.2)
    a, b = s.compare(("arrow-trend-up", "Bất ổn, lãi suất giảm\n→ vàng được hỗ trợ"), ("arrow-trend-down", "Lợi suất tăng\n→ áp lực quay lại"),
                     f("nếu bất"), f("Nếu lợi"), vs="")
    s.animate(a, f("được hỗ"), 0.4, {"scale": 1.12})
    s.animate(a, f("Nếu lợi"), 0.5, {"scale": 0.95, "opacity": 0.55})
    s.animate(b, f("áp lực"), 0.4, {"scale": 1.12})

    # S8 — tổng kết: 3 lực lần lượt hiện → gom lại dưới câu kết, giữ bố cục hoàn chỉnh đủ đọc
    s = K.scene(f("Một thị trường"), K.T, "kết")
    ids = s.icons([("bank", "Lãi suất Mỹ", f("Một thị trường")), ("earth-asia", "Nhu cầu châu Á", f("nhưng")),
                   ("money-bill-wave", "Tỷ giá trong nước", f("nhiều lực"))], connect=True)
    for n, i in enumerate(ids):
        s.animate(i, f("khắp") + 0.1 * n, 0.5, {"scale": 0.86})
    s.title("MỘT THỊ TRƯỜNG VÀNG\nNHIỀU LỰC TÁC ĐỘNG", f("Một thị trường"), size="l", hl="NHIỀU LỰC TÁC ĐỘNG", ry=0.4)
    s.sound(f("nhiều lực"), "impact")
    s.exit = False                                                    # cảnh kết giữ nguyên tới hết
    # ---------- HẾT phần nội dung ----------


build(__file__, content, theme="dark")    # theme: dark (tin tức/tài chính) | warm (sức khỏe/giáo dục/đời sống) | map (BĐS/hạ tầng)
