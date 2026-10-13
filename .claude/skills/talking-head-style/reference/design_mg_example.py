# v1.1d (TGC thuê 118): ảnh clip chỉ khi đúng vật, còn lại i_* minh họa có nhãn; ảnh ≥1.8s; dòng dẫn rơi nhanh từ đầu cảnh, chữ chính vào ngay sau rồi giữ.
# Motion Graphics cho TGC.Thuê.118_N3D.B — được exec trong design.py (dùng F, word_frames, pl, SoundEvent, VideoFxEvent).
# 7 đoạn graphic trám vào mạch nói liên tục 15→95s: tiêu đề dự án, 2 lý do (hoàn thiện + vị trí),
# tiện ích xung quanh, Smart Home, 9 phòng làm việc, văn phòng + phòng họp. Đồ hoạ vector, không ảnh dự án.


def WD(text, near, y=430, size=50):
    return {"type": "words", "text": text, "word_frames": word_frames(text, near), "x": 540, "y": y, "size": size}


def BIG(text, at, y=560, size=120, color="#111111"):
    return {"type": "big", "text": text, "t": F(at), "x": 540, "y": y, "size": size, "color": color}


def TAG(text, at, tone="gold", x=540, y=None, size=64):
    return {"type": "tag", "text": text, "t": F(at), "x": x, "y": y, "tone": tone, "size": size}


def ICON(name, at, x=540, y=1120, size=280, tone="gold"):
    return {"type": "icon", "name": name, "t": F(at), "x": x, "y": y, "size": size, "tone": tone}


def CHECKS(items, at, x=170, y=900, tone="gold", size=50, gap=130):
    return {"type": "checks", "t": F(at), "x": x, "y": y, "tone": tone, "size": size, "gap": gap,
            "items": [(t, F(tt)) for t, tt in items]}


def BAR(at):
    return {"type": "barcode", "t": F(at), "x": 540, "y": 250}


def PH(file, at, x=540, y=1160, w=880, h=460, label="", rot=0.0, from_dx=0, from_dy=140):
    return {"type": "photo", "file": B + file, "t": F(at), "x": x, "y": y, "w": w, "h": h, "label": label, "rot": rot,
            "from_dx": from_dx, "from_dy": from_dy}


B = str(c.dir / "assets_web") + "/"   # c = P.Ctx(pid) trong design.py
# ảnh: c_* = khung hình cắt từ chính video; w_* = ảnh The Global City trên web (vneconomy, plo, mekongasean)
# mỗi ảnh có kw = từ đang nói lúc ảnh vào; không lặp cùng ảnh trong 30s


def PHS(*items, x=540, y=1160, w=880, h=500):
    """xấp 2–3 ảnh nối tiếp: (file, at, kw, label)"""
    return {"type": "photos", "x": x, "y": y, "w": w, "h": h,
            "items": [{"file": B + f, "t": F(t), "kw": kw, "label": lab} for f, t, kw, lab in items]}


def SC(a, b, *els):
    return {"start": F(a), "end": F(b), "elements": [BAR(a), *els]}


# Nguồn ảnh: c_* = cắt từ clip, CHỈ khi clip quay đúng vật đang nói (thang máy, máy lạnh, tủ điện/smart home, mặt tiền);
# w_* = ảnh dự án trên báo, cho bên ngoài/toàn cảnh; i_* = ảnh minh họa Unsplash/Pexels cho nội thất không có trong clip
# (tự ghi “Hình ảnh minh họa”). Mỗi ảnh hiện ≥1.8s.
MG_SEGS = [
    {"id": "mg1", "start": F(15.0), "end": F(20.2), "seed": 4, "scenes": [
        SC(15.0, 17.6, WD("văn phòng tại", 14.76), BIG("THE GLOBAL CITY", 15.6, size=110), TAG("VĂN PHÒNG CHO THUÊ", 16.3),
           PHS(("w_tgc3.jpg", 15.3, "global", "The Global City · toàn cảnh"))),
        SC(17.6, 20.2, WD("thì đây là một sự lựa chọn", 16.4), BIG("ĐÁNG XEM", 18.24, size=180), TAG("ngay giai đoạn hiện tại", 18.9),
           PHS(("c_mattien.jpg", 17.8, "lựa chọn", "Căn 118"))),
    ]},
    {"id": "mg2", "start": F(20.2), "end": F(36.3), "seed": 5, "scenes": [
        SC(20.2, 22.7, BIG("LÝ DO 1", 20.7, size=190), PHS(("i_vanphong.jpg", 20.4, "lý do", ""))),
        SC(22.7, 27.8, WD("căn này đã được", 22.34), BIG("HOÀN THIỆN ĐẦY ĐỦ", 23.42, size=100), TAG("thang máy · máy lạnh mọi phòng", 24.8),
           PHS(("c_thangmay.jpg", 23.6, "thang", "Thang máy"), ("c_amtran.jpg", 25.6, "lạnh", "Máy lạnh âm trần"))),
        SC(27.8, 30.3, WD("và đã được ngăn", 27.28), BIG("9 PHÒNG RIÊNG BIỆT", 28.3, size=104),
           PHS(("i_phonglv1.jpg", 28.0, "phòng", "Phòng làm việc riêng"))),
        SC(30.3, 33.7, WD("chỉ cần mang thiết bị vào là", 31.18), BIG("VẬN HÀNH NGAY", 33.12, size=120),
           PHS(("i_nhanvien.jpg", 30.5, "thuê", "")), ICON("key", 33.3, x=880, y=900, size=130)),
        SC(33.7, 36.3, BIG("ĐIỀU 2", 34.18, size=190), TAG("vị trí", 35.84),
           PHS(("w_soho_dem.jpg", 34.0, "điều", "The Global City về đêm"))),
    ]},
    {"id": "mg3", "start": F(36.3), "end": F(48.0), "seed": 1, "scenes": [
        SC(36.3, 39.0, WD("Căn này nằm trên", 36.32), BIG("TRỤC ĐƯỜNG 14M", 37.3, size=112),
           PHS(("w_duong_cay.jpg", 36.6, "đường", "Đường nội khu The Global City")), ICON("road", 38.0, x=880, y=900, size=130)),
        SC(39.0, 41.6, WD("anh chị có thể di chuyển ra", 39.06), BIG("TRUNG TÂM THƯƠNG MẠI", 40.4, size=92), TAG("ngay gần nhà", 41.0),
           PHS(("w_soho_ngay.jpg", 39.3, "thương mại", "Khu thương mại SOHO"))),
        SC(41.6, 44.4, BIG("3 PHÚT TỚI TRƯỜNG HỌC", 41.8, size=92), TAG("ở phía trước nhà", 43.4),
           PHS(("i_truong1.jpg", 41.9, "trường", "")), ICON("school", 43.0, x=880, y=900, size=130)),
        SC(44.4, 48.0, WD("Trong vòng", 44.44), BIG("1-2 PHÚT DI CHUYỂN", 45.06, size=100), TAG("tới trường học", 45.9),
           PHS(("i_truong2.jpg", 44.7, "phút", ""))),
    ]},
    {"id": "mg4", "start": F(48.0), "end": F(61.5), "seed": 2, "scenes": [
        SC(48.0, 51.0, WD("thì anh chị ra công viên nhạc nước", 47.68), BIG("2 PHÚT DI CHUYỂN", 49.4, size=120), TAG("từ căn nhà", 50.0),
           PHS(("w_nhacnuoc1.jpg", 48.2, "nhạc", "Nhạc nước The Global City"))),
        SC(51.0, 54.5, WD("đối với các anh chị thuê", 52.5), BIG("LỢI THẾ LỚN", 52.0, size=140), TAG("tiếp khách · làm việc", 53.0),
           PHS(("i_tiepkhach1.jpg", 51.3, "lợi thế", ""))),
        SC(54.5, 58.9, WD("xây dựng cái hình ảnh", 56.42), BIG("THƯƠNG HIỆU", 57.3, size=130), TAG("tại The Global City", 58.0),
           PHS(("i_letan.jpg", 54.8, "khách|làm việc", ""), ("w_tgc3.jpg", 57.0, "thương hiệu", "The Global City"))),
        SC(58.9, 61.5, WD("Ngoài ra căn này còn được", 59.02), BIG("TRANG BỊ THÊM", 60.4, size=130),
           PHS(("c_dienthongminh.jpg", 59.2, "trang bị", "Công tắc thông minh"))),
    ]},
    {"id": "mg5", "start": F(61.5), "end": F(73.0), "seed": 3, "scenes": [
        SC(61.5, 64.0, WD("hệ thống điện", 61.08), BIG("SMART HOME", 61.88, size=160),
           PHS(("c_tudien.jpg", 61.7, "smart", "Tủ điện · công tắc thông minh"))),
        SC(64.0, 67.3, WD("ở tất cả các vị trí trong ngôi nhà", 62.48), BIG("CHIẾU SÁNG", 65.3, size=150), TAG("điều khiển thông minh", 66.2),
           PHS(("i_chieusang.jpg", 64.3, "chiếu", ""))),
        SC(67.3, 70.3, WD("các thiết bị vận hành cơ bản", 66.12), BIG("THUẬN TIỆN", 68.0, size=150),
           PHS(("i_goclamviec.jpg", 67.6, "quản lý", ""))),
        SC(70.3, 73.0, WD("Khi xem cái", 70.48), BIG("LAYOUT VĂN PHÒNG", 71.08, size=96),
           PHS(("i_phonglv2.jpg", 70.6, "layout", ""))),
    ]},
    {"id": "mg6", "start": F(73.0), "end": F(88.2), "seed": 6, "scenes": [
        SC(73.0, 76.4, WD("chủ nhà đã hoàn thiện theo hướng", 73.28), BIG("CHUẨN VĂN PHÒNG", 75.6, size=96),
           PHS(("i_vanphong.jpg", 73.3, "hoàn thiện", ""))),
        SC(76.4, 80.6, WD("rất là rõ ràng", 76.06), BIG("9 PHÒNG LÀM VIỆC", 77.1, size=120), TAG("vệ sinh riêng biệt", 78.8),
           PHS(("i_phongtrong.jpg", 76.7, "phòng", "Phòng làm việc"), ("i_wc.jpg", 78.7, "vệ sinh", "Khu vệ sinh"))),
        SC(80.6, 85.6, WD("bố trí nhân sự làm việc ở tất cả các phòng", 82.26), BIG("BỐ TRÍ LINH HOẠT", 83.2, size=96),
           PHS(("i_nhanvien.jpg", 80.9, "bố trí", ""), ("i_phonglv1.jpg", 83.2, "phòng", ""))),
        SC(85.6, 88.2, WD("Và bên cạnh đó kết hợp", 85.74), BIG("TIỆN DI CHUYỂN", 86.8, size=120),
           PHS(("i_phonghop1.jpg", 85.9, "kết hợp", ""))),
    ]},
    {"id": "mg7", "start": F(88.2), "end": F(97.0), "seed": 4, "scenes": [
        SC(88.2, 91.2, WD("giữa văn phòng và phòng họp", 87.26), BIG("GẦN NHAU HƠN", 89.72, size=130),
           PHS(("i_phonghop2.jpg", 88.4, "họp", "Phòng họp"))),
        SC(91.2, 94.1, WD("một trong những yếu tố quan trọng", 91.16), BIG("THANG MÁY", 93.64, size=160),
           PHS(("c_thangmay.jpg", 91.4, "thang", "Thang máy"), w=600, h=600)),
        SC(94.1, 97.0, WD("giúp cho mình di chuyển ở các tầng", 94.34), BIG("THUẬN TIỆN HƠN", 96.12, size=120),
           PHS(("i_letan.jpg", 94.4, "tầng", "Sảnh"))),
    ]},
]
for seg in MG_SEGS:   # dòng dẫn rơi nhanh ngay đầu cảnh (được phép trước lời), chữ lớn vào ngay sau và giữ tới hết cảnh
    for sc in seg["scenes"]:
        st = sc["start"] + 10
        lead_end = st
        for el in sc["elements"]:
            if el["type"] == "words":
                el["word_frames"] = [st + 3 * j for j in range(len(el["text"].split()))]
                lead_end = el["word_frames"][-1] + 6
        bt = None
        for el in sc["elements"]:
            if el["type"] == "big":
                el["t"] = bt = max(sc["start"] + 8, min(el["t"], lead_end + 2))
        for el in sc["elements"]:
            if el["type"] == "tag":
                el["t"] = max(bt + 12, min(el["t"], bt + 30)) if bt is not None else max(el["t"], sc["start"])
            elif el["type"] == "checks":
                el["items"] = [(t, max(tf, sc["start"] + 12)) for t, tf in el["items"]]
            elif el["type"] == "photos":
                for it in el["items"]:
                    it["t"] = max(it["t"], sc["start"])
            elif "t" in el and el["type"] not in ("big", "tag"):
                el["t"] = max(el["t"], sc["start"])
pl.mg = MG_SEGS

# SFX cho MG (tiết chế): vào đoạn = flash; chữ lớn = 1 âm nhẹ; dấu tích = âm nhẹ; chữ rơi = tick
for seg in MG_SEGS:
    pl.sounds.append(SoundEvent(id=f"sfx_{seg['id']}_in", asset="u_flash", linked_event=seg["id"], hit=seg["start"] + 2, gain_db=-10, priority=9))
    pl.fx.append(VideoFxEvent(id=f"fl_{seg['id']}", type="flash", start=seg["start"], end=seg["start"] + 7, params={"opacity": 0.35}))
    pl.fx.append(VideoFxEvent(id=f"fl_{seg['id']}_out", type="flash", start=seg["end"] - 3, end=seg["end"] + 4, params={"opacity": 0.25}))
    for sc in seg["scenes"]:
        for k, el in enumerate(sc["elements"]):
            sid = f"sfx_{seg['id']}_{sc['start']}_{k}"
            if el["type"] == "big":
                pl.sounds.append(SoundEvent(id=sid, asset="u_soft", linked_event=seg["id"], hit=el["t"] + 5, gain_db=-16, priority=2))
            elif el["type"] == "words":
                for j, wf in enumerate(el["word_frames"]):
                    pl.sounds.append(SoundEvent(id=f"{sid}_{j}", asset="u_tick", linked_event=seg["id"], hit=max(wf, sc["start"]) + 2, gain_db=-11, priority=5))
            elif el["type"] == "checks":
                for j, (_, t) in enumerate(el["items"]):
                    pl.sounds.append(SoundEvent(id=f"{sid}_{j}", asset="u_soft", linked_event=seg["id"], hit=t + 5, gain_db=-17, priority=1))
# bỏ text/ảnh/zoom/âm của talking head nằm trong MG (MG che toàn khung)
inside = lambda a, b: any(seg["start"] - 3 <= a and b <= seg["end"] + 3 for seg in MG_SEGS)
pl.text_groups = [g for g in pl.text_groups if not any(g.start < seg["end"] and g.end > seg["start"] and g.start >= seg["start"] for seg in MG_SEGS)]
for g in pl.text_groups:
    for seg in MG_SEGS:
        if g.start < seg["start"] < g.end:
            g.end = seg["start"]
ids = {g.id for g in pl.text_groups} | {v.id for v in pl.visuals} | {s["id"] for s in MG_SEGS}
pl.sounds = [s for s in pl.sounds if s.linked_event in ids and (s.linked_event.startswith("mg") or not inside(s.hit, s.hit))]
pl.fx = [e for e in pl.fx if e.id.startswith("fl_mg") or not inside(e.start, e.start)]
