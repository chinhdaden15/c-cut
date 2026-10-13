"""TGC.Thuê.118_N3D.B — cho thuê văn phòng tại The Global City (Talking Head Style).
1 font Montserrat (Black chữ chính / SemiBold chữ dẫn); 3 tông gold/red/blue.
Lớp trước: ngực trở xuống; lớp sau: vai trở lên; không chồng câu cùng lớp; chữ dẫn rơi từng từ + tick.
Nhân vật nói gần như liên tục 21→97s nên dùng 7 đoạn Motion Graphics phá luật 15s + minh hoạ tiện ích.
Sửa ASR (xem confirm.json): “The Global”→The Global City; “thuần tiện”→thuận tiện; số liệu 14m/9 phòng/các mốc phút chờ xác nhận."""
import re

from thagent import pipeline as P, timeline as T
from thagent import neon
from thagent.schema import EditSegment as E, Plan, SoundEvent, TextGroup as G, TextSpan as S, VideoFxEvent, VisualEvent

c = P.Ctx("bta")
dur = c.project.source.duration
pl = c.project.plan or Plan()
c.project.plan = pl
jump_zoom = []
if c.project.style.get("voice_preprocessed"):   # nguồn đã cắt thô sẵn → giữ nguyên 1 đoạn
    pl.segments = [E(id="s00", source_in=0.0, source_out=round(dur - 0.02, 3), reason="nguồn đã cắt thô sẵn", order=0)]
else:                                           # Cắt sạch: lặng/đầu/đuôi/đếm/ừ à/lắp bắp; phóng 108% xen kẽ giấu jump cut
    from thagent import cleancut as K
    segs, cuts, jump_zoom = K.clean_cut(c.project.words, dur, c.project.proxy)
    # người dùng muốn giữ chỗ nào: bỏ cut tương ứng rồi chạy lại (xem K.report)
    pl.segments = segs + cuts
    print(K.report(segs, cuts))
T.build_mapping(pl)
F = lambda t: T.src_to_tl_near(pl, t)   # mọi mốc giây NGUỒN → frame timeline sau cắt
W = c.project.words
norm = lambda x: re.sub(r"[^\w]", "", x.lower())


def word_frames(text, near):
    """frame bắt đầu của từng từ trong `text`, khớp chuỗi từ transcript gần thời điểm `near`."""
    toks = [norm(t) for t in text.split()]
    best = None
    for i in range(len(W) - len(toks) + 1):
        if [norm(w.text) for w in W[i:i + len(toks)]] == toks:
            if best is None or abs(W[i].source_start - near) < abs(W[best].source_start - near):
                best = i
    if best is None or abs(W[best].source_start - near) > 2.5:
        raise ValueError(f"không khớp lời: {text} @ {near}")
    return [F(w.source_start) for w in W[best:best + len(toks)]]


def sprite_hw(text, role, size):
    """kích thước NÉT CHỮ (không tính quầng sáng) để dàn dòng sát nhau."""
    m = neon._mask(text, role, size)
    ys, xs = (m > 0.05).nonzero()
    return int(ys.max() - ys.min() + 1), int(xs.max() - xs.min() + 1)


FRONT, BACK = "front_of_subject", "behind_subject"
# (id, lớp, tông, start_s, end_s, lead(text, near) | None, main(text, size, at_s), pill(text, at_s, tông) | None, element)
specs = [
    ("h1", FRONT, "gold", 0.0, 4.5, None, ("9 MÁY LẠNH", 120, 0.05), ("thang máy · vệ sinh mọi tầng", 1.0, "gold"), "check"),
    ("h2", BACK, "blue", 4.5, 8.0, ("đã được trang bị hệ thống", 4.6), ("CHỮA CHÁY", 170, 5.88), None, "sparkle"),
    ("h2b", FRONT, "gold", 6.3, 8.6, None, ("9 PHÒNG LÀM VIỆC", 96, 6.4), None, "check"),
    ("h3", BACK, "blue", 8.0, 12.0, None, ("ĐIỆN THÔNG MINH", 96, 8.74), None, "sparkle"),
    ("r1", BACK, "gold", 20.5, 24.5, None, ("LÝ DO 1", 170, 21.74), None, "sparkle"),
    ("c1g", FRONT, "blue", 31.3, 36.3, ("chỉ cần mang thiết bị vào là", 31.18), ("VẬN HÀNH NGAY", 104, 33.12), None, "check"),
    ("c2g", BACK, "gold", 33.9, 36.3, None, ("ĐIỀU 2", 150, 34.18), None, "sparkle"),
    ("d1", FRONT, "gold", 44.4, 48.0, ("Trong vòng", 44.44), ("1-2 PHÚT DI CHUYỂN", 100, 45.06), ("tới trường học", 45.9, "gold"), "road"),
    ("f1", FRONT, "gold", 70.3, 73.0, ("Khi xem cái layout căn này", 70.48), ("LAYOUT VĂN PHÒNG", 80, 71.08), None, "briefcase"),
    ("cta1", FRONT, "blue", 97.0, 101.0, ("nếu quý anh chị đang", 97.76), ("CÓ NHU CẦU THUÊ", 88, 98.76), None, "key"),
    ("cta2", FRONT, "gold", 101.0, dur - 0.05, None, ("LIÊN HỆ TUẤN ANH", 96, 101.56), ("gửi vị trí phù hợp nhu cầu", 103.1, "gold"), "handshake"),
]

DECOR_ICON = set(neon.UICONS)
pl.text_groups, pl.sounds, pl.fx = [], [], list(jump_zoom)
warn = []
for gid, layer, tone, s0, s1, lead, main, pill, decor in specs:
    start = F(s0)
    mtext, msize, mat = main
    mh, mw = sprite_hw(mtext, "display", msize)
    spans = []
    if lead:
        lt, near = lead
        wf = word_frames(lt, near)
        lead_size = 56
        lh, lw = sprite_hw(lt, "semi", lead_size)
        if lw > 880:   # chỉ thu nhỏ dòng dẫn, giữ cỡ chữ chính
            lead_size = int(lead_size * 880 / lw)
            lh, lw = sprite_hw(lt, "semi", lead_size)
        spans.append(S(text=lt, style="neon", neon_role="semi", size=lead_size, palette="white", motion="words",
                       dy=-(mh / 2 + lh / 2 + 16), word_delays=[3 * j for j in range(len(wf))]))   # rơi nhanh, được phép trước lời
    spans.append(S(text=mtext, style="neon", neon_role="display", size=msize, palette=tone, motion="pop", echo=True,
                   delay_frames=(3 * (len(lead[0].split()) - 1) + 8) if lead else 0))   # chữ chính vào ngay sau dòng dẫn rồi giữ
    pop_d = spans[-1].delay_frames
    if pill:
        ptxt, pat, ptone = pill
        spans.append(S(text=ptxt, style="pill", size=44, palette=ptone, motion="wipe",
                       dy=mh / 2 + 44, delay_frames=pop_d + 8))   # nhãn vào ngay sau chữ chính
    # element trang trí: chỉ đặt ở chỗ TRỐNG cạnh chữ chính; không đủ chỗ → cạnh dòng dẫn; vẫn không đủ → bỏ
    side = 1 if len(pl.text_groups) % 2 == 0 else -1
    lw_lead = sprite_hw(lead[0], "semi", 56)[1] if lead else 0
    def place(size):
        room = 540 - 50 - mw / 2
        if room >= size + 20:
            return side * (mw / 2 + 20 + size / 2), -mh * 0.30
        room2 = 540 - 50 - lw_lead / 2
        if lead and room2 >= size + 20:
            return side * (lw_lead / 2 + 20 + size / 2), -(mh / 2 + 40)
        return None
    if layer == BACK and pill:
        decor = None
    if decor is None:
        pass
    elif decor in DECOR_ICON:
        sz = 100
        p_ = place(sz)
        if p_:
            spans.append(S(text=decor, style="icon", size=sz, palette=tone, motion="icon", dx=p_[0], dy=p_[1], delay_frames=pop_d + 4))
    else:
        sz = {"sparkle": 64, "ring": 70, "dots": 80, "chevrons": 96}[decor]
        p_ = place(sz)
        if p_:
            spans.append(S(text=decor, style="icon", size=sz, palette=tone, motion="float", dx=p_[0], dy=p_[1], delay_frames=pop_d + 4))
    if decor is not None and mw / 2 + 60 < 540 - 60:   # lấp lánh nhỏ phía đối diện, chỉ khi còn chỗ
        spans.append(S(text="sparkle", style="icon", size=40, palette=tone, motion="float",
                       dx=-side * (mw / 2 + 34), dy=mh * 0.45, delay_frames=pop_d + 8))
    g = G(id=gid, preset="staggered_phrase", zone="above_head" if layer == BACK else "chest", layer=layer,
          anchor_x=0.5, spans=spans, start=start, end=F(s1), enter_frames=9, exit_frames=7)
    g.hit = start + pop_d + 5
    pl.text_groups.append(g)

# không chồng câu trong cùng lớp: nhóm sau vào thì nhóm trước rời
for layer in (FRONT, BACK):
    gs = sorted([g for g in pl.text_groups if g.layer == layer], key=lambda g: g.start)
    last_of = lambda g: max(g.start + (max(s.word_delays) if s.word_delays else s.delay_frames) + 9
                            for s in g.spans if s.style != "icon")
    for a, b in zip(gs, gs[1:]):
        if a.end > b.start:
            a.end = b.start
        need = last_of(a) + 30 + a.exit_frames
        if a.end < need:
            b_main = b.start + next(x for x in b.spans if x.motion == "pop").delay_frames
            new = min(need, b_main - 4, b.end - 40)
            if new > b.start:
                sh = new - b.start
                for x in b.spans:
                    x.delay_frames = max(0, x.delay_frames - sh)
                    x.word_delays = [max(0, d - sh) for d in x.word_delays]
                b.start = new; b.hit = max(b.hit, new)
                a.end = new
    for g in gs:
        last = max(g.start + (max(s.word_delays) if s.word_delays else s.delay_frames) + 9 for s in g.spans if s.style != "icon")
        hold = (g.end - g.exit_frames - last) / 30
        if hold < 1.5:
            warn.append(f"{g.id}: giữ {hold:.2f}s")

# tick mỗi từ, đúng frame từ hiện (sau khi giãn)
for g in pl.text_groups:
    for x in g.spans:
        for k, d in enumerate(x.word_delays):
            pl.sounds.append(SoundEvent(id=f"tick_{g.id}_{k}", asset="u_tick", linked_event=g.id, hit=g.start + d + 2, gain_db=-11, priority=0))

# SFX (không whoosh): pop tại chữ chính; flash cho tiêu đề lớp sau
for g in pl.text_groups:
    main = next(s for s in g.spans if s.motion == "pop")
    if g.layer == BACK:
        asset, gain, pri = "u_flash", -11, 3
        pl.fx.append(VideoFxEvent(id=f"fl_{g.id}", type="flash", start=g.hit - 1, end=g.hit + 6, params={"opacity": 0.12}))
    else:
        asset, gain, pri = ("u_hit", -10, 2)
    pl.sounds.append(SoundEvent(id=f"sfx_{g.id}", asset=asset, linked_event=g.id, hit=g.hit, gain_db=gain, priority=pri))
    g.sfx = f"sfx_{g.id}"
for gid in ("h1", "h2b", "c1g", "d1", "f1", "cta2"):          # punch-in rõ tại chữ chính
    g = next(x for x in pl.text_groups if x.id == gid)
    pl.fx.append(VideoFxEvent(id=f"zm_{gid}", type="zoom", start=g.hit - 2, end=g.end - 7, params={"scale": 1.14, "cx": 0.5, "cy": 0.33}))
for gid in ("h2", "h3", "r1", "c2g", "cta1"):        # zoom-out: bắt đầu gần rồi lùi ra
    g = next(x for x in pl.text_groups if x.id == gid)
    pl.fx.append(VideoFxEvent(id=f"zo_{gid}", type="zoom", start=g.start, end=g.end, params={"scale": 1.12, "mode": "out", "cx": 0.5, "cy": 0.33}))

# highlight vật nhân vật chỉ vào (work/pointing.json, box đã duyệt bằng ảnh tĩnh)
for hid, a, b, box, lab, shape in [("hl_aircon", 0.0, 0.75, [0.09, 0.18, 0.44, 0.14], "", "rect"),
                                   ("hl_thangmay", 0.8, 2.5, [0.40, 0.23, 0.36, 0.72], "THANG MÁY", "rect"),
                                   ("hl_tudien", 10.0, 11.8, [0.0, 0.50, 0.36, 0.22], "TỦ ĐIỆN", "rect")]:
    pl.fx.append(VideoFxEvent(id=hid, type="highlight", start=F(a), end=F(b), params={"box": box, "label": lab, "tone": "gold", "shape": shape}))

pl.visuals = []   # chưa có ảnh/tư liệu thật của căn này (xem confirm.json c10); MG dùng đồ hoạ vector

exec(open(c.dir / "design_mg.py", encoding="utf-8").read())   # design_mg.py nằm cùng thư mục dự án

# ===== CHÍNH SÁCH SFX (tiết chế, dịu tai, không đè tiếng chữ rơi) =====
import json, random
POOLS = json.loads(open("assets/sfx/manifest.json").read())["_pools"]
rng = random.Random(7); last = None
for snd in pl.sounds:
    if snd.asset in ("u_pop", "u_hit", "u_card", "u_check", "u_mgtrans"):
        snd.asset = "u_soft" if snd.asset in ("u_pop", "u_hit", "u_check") else "DROP"
        if snd.asset == "u_soft":
            snd.gain_db = -16
    if snd.asset == "u_tick":
        snd.gain_db, snd.priority = -11, 5
pl.sounds = [x for x in pl.sounds if x.asset != "DROP"]
ticks = sorted(x.hit for x in pl.sounds if x.asset == "u_tick")
import bisect
def near_tick(h, r=6):
    i = bisect.bisect_left(ticks, h - r)
    return i < len(ticks) and ticks[i] <= h + r
for x in pl.sounds:
    if x.asset == "u_flash" and near_tick(x.hit):
        for d in range(1, 7):
            if not near_tick(x.hit + d):
                x.hit += d; break
keep, last_hit = [], -999
for x in sorted(pl.sounds, key=lambda x: (x.hit, -x.priority)):
    if x.asset == "u_tick":
        keep.append(x); continue
    if x.asset in ("u_soft", "u_flash") and near_tick(x.hit) and not x.id.endswith("_in"):   # không đè tiếng chữ rơi
        continue
    if x.hit - last_hit < 10 and x.asset == "u_soft":  # giãn cách các âm nhẹ
        continue
    keep.append(x); last_hit = x.hit
pl.sounds = keep
for x in pl.sounds:                                   # xoay vòng 3 âm nhẹ, không lặp ngay
    if x.asset == "u_soft":
        x.asset = rng.choice([a for a in POOLS["soft"] if a != last]); last = x.asset

pl.notes = ["TGC.Thuê.118_N3D.B: cho thuê văn phòng The Global City; 10 nhóm chữ neon + 7 đoạn Motion Graphics."] + warn
c.save()
print(len(pl.text_groups), "groups;", len(pl.sounds), "sfx;", len(pl.mg), "MG")
print("\n".join(warn) or "hold OK")
