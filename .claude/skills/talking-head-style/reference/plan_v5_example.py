"""MẪU CHUẨN — bản Agency v5 người dùng chốt 2026-10-29 (clip tiếng Anh 62s, out/th_callouts/agency_v5.mp4). Copy rồi thay nội dung theo lời của video mới."""
import json
from thagent import pipeline as P, timeline as T
from thagent.schema import EditSegment as E, Plan, TextGroup as G, TextSpan as S, SoundEvent

c = P.Ctx("<id>")
c.project.style["voice_preprocessed"] = True
dur = c.project.source.duration
pl = Plan(); pl.width, pl.height = 1080, 1920
pl.segments = [E(id="s00", source_in=0.0, source_out=round(dur - 0.02, 3), reason="nguồn giữ nguyên", order=0)]
T.build_mapping(pl)
pl.captions = True


def grp(gid, a, b, lines, tone, layer="front_of_subject"):
    sp = [S(text=t, style="neon", neon_role="display", size=sz, palette=tone, motion="pop", echo=True,
            dy=sum(x[1] * 1.02 for x in lines[:i]), delay_frames=d) for i, (t, sz, d) in enumerate(lines)]
    g = G(id=gid, preset="staggered_phrase", zone="chest", layer=layer, anchor_x=0.5, spans=sp, start=a, end=b,
          enter_frames=9, exit_frames=7)
    g.hit = a + lines[0][2] + 5
    pl.sounds.append(SoundEvent(id=f"sfx_{gid}", asset="soft_00", linked_event=gid, hit=g.hit, gain_db=-16, priority=2))
    g.sfx = f"sfx_{gid}"
    for x in sp:
        x.echo = x.size >= 100          # chữ dài cỡ nhỏ: bỏ bóng lặp (tràn mép)
    pl.text_groups.append(g)


grp("g_hook", 30, 85, [("THE BEST", 126, 3), ("CONTENT AGENCY", 80, 27)], "gold")
grp("g_hire", 240, 290, [("FULL-TIME", 126, 3), ("EDITORS", 126, 26)], "blue")
grp("g_pay", 428, 474, [("HOW MUCH", 126, 2), ("DO WE PAY?", 126, 21)], "red")
grp("g_first", 952, 980, [("FIRSTLY", 130, 2)], "gold")
grp("g_cta", 1846, 1869, [("WORK", 130, 3), ("WITH YOU", 130, 3)], "blue")
pl.text_groups[-1].exit_frames = 0

pl.stage = [
    {"id": "st_prem", "kind": "giant_text", "text": "PREMIUM", "tone": "gold", "start": 153, "end": 196},
    {"id": "st_best", "kind": "giant_text", "text": "BEST", "tone": "gold", "start": 330, "end": 378},
    {"id": "st_key", "kind": "giant_text", "text": "KEY", "tone": "gold", "start": 818, "end": 860},
    {"id": "st_must", "kind": "giant_text", "text": "MUST", "tone": "red", "start": 1398, "end": 1430},
    {"id": "st_story", "kind": "giant_text", "text": "STORYTELLING", "tone": "blue", "start": 1564, "end": 1610},
    {"id": "st_amz", "kind": "giant_text", "text": "AMAZING", "tone": "gold", "start": 1794, "end": 1800},
]
pl.callouts = [
    {"id": "co_scale", "kind": "icon_keyword", "icon": "3d:rocket", "text": "SCALE", "sub": "for business owners", "tone": "gold", "glass": True, "start": 104, "end": 152, "zoom": "punch"},
    {"id": "co_dep", "kind": "trio", "items": [{"text": "TASK", "icon": "3d:f-clapper-board", "tone": "gold"}, {"text": "EXPERIENCE", "icon": "3d:trophy", "tone": "gold"}, {"text": "SKILLS", "icon": "3d:color-palette", "tone": "gold"}], "at": [668, 702, 772], "tone": "gold", "glass": True, "start": 640, "end": 792},
    {"id": "co_work", "kind": "two_tier", "lead": "you must know how to", "text": "PUT IT TO WORK", "icon": "3d:f-film-frames", "tone": "blue", "glass": True, "start": 1650, "end": 1730, "zoom": "out"},
]
B = dict(bg="blur", tone="gold")
pl.mg2 = [
    dict(id="m_pay", kind="money", start=520, end=637, value_from=500, value_to=2000, decimals=0, prefix="$", locale="en", hit_at=2.27, title="A MONTH", sub="depends on your role", icon="3d:money", **B),
    dict(id="m_key", kind="doc", start=862, end=948, title="TO JOIN THE TEAM", heading="KEY RESPONSIBILITIES", highlight="and qualifications", icon="3d:f-open-book", **B),
    dict(id="m_reels", kind="compare", start=1016, end=1125, a={"label": "Reels from", "value": "10 SEC", "sub": "short"}, b={"label": "up to", "value": "2 MIN", "sub": "long"}, **B),
    dict(id="m_handle", kind="checklist", start=1129, end=1368, title="YOU CAN HANDLE", items=["Tight deadlines", "Multiple styles", "Many projects at once"], at=[2.2, 4.4, 6.7], **B),
    dict(id="m_tools", kind="notif", start=1431, end=1560, items=[{"icon": "projects/agency/assets_web/logo_ae.png", "title": "After Effects", "text": "motion & edits"}, {"icon": "projects/agency/assets_web/logo_adobe.png", "title": "Adobe", "text": "editing tools"}, {"icon": "3d:color-palette", "title": "Graphic design", "text": "most importantly"}], at=[0.3, 0.9, 2.6], **B),
]
pl.notes = ["Agency — tuyển editor (EN), thử công thức B.TA mới."]
c.project.plan = pl
c.project.renders = []
c.save()
print("ok")
