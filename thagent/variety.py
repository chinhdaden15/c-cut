"""Talking Head — đổi mới giữa các video mà vẫn giữ nét chung (2026-10-29).

LÕI CỐ ĐỊNH (th_rules.py): font, 3 tông, phụ đề neo, chữ nhấn đúng mốc, luật số tiền, logo thật, khung kính.
PHẦN THAY ĐỔI theo "công thức nhịp" (plan.recipe) — mỗi khổ một bộ riêng:
- khổ NGANG tiết chế chữ sau lưng (≤ 1 lần / 30s, chỉ hook / câu bẻ lái), thay bằng callout bên cạnh, lower-third, MG chia đôi;
- khổ DỌC có bộ sáng tạo riêng (chữ động phủ khung, thẻ trên đầu, sân khấu…).
SFX theo bộ âm (plan.sfx_pack) — một video một bộ cho đồng nhất; âm tổng hợp tạm (impact_soft, pop_soft, shimmer, whoosh) không dùng nữa;
mật độ: âm vào của callout / sân khấu cách nhau ≥ 2.5s, mỗi callout tối đa 3 tiếng mục.
Lịch sử: ~/.ccut/th_history.json lưu công thức + kiểu đã dùng của các video gần nhất → Claude được nhắc tránh lặp, preflight cảnh báo
nếu giống video trước > 60%."""
from __future__ import annotations

import json
import time
from pathlib import Path

BEHIND = ("giant_text", "big_number", "marquee")      # chữ / số sau lưng

RECIPES = {
    "portrait": {
        "toi_gian": dict(name="Tối giản", desc="ít sân khấu, nhấn bằng chữ chính + zoom; MG nền cream/blur; hợp chia sẻ kiến thức, cảm xúc",
                         stage_every=25, behind_every=25, stage=["spotlight", "giant_text"], callouts=["two_tier", "quote", "icon_keyword", "circle_word"],
                         mg=["doc", "question", "photos", "compare"], bg=["cream", "blur"], pack="mem"),
        "bien_tap": dict(name="Biên tập", desc="nhiều thẻ thông tin, checklist, so sánh; MG charcoal/dots; hợp hướng dẫn, review, tài chính",
                         stage_every=20, behind_every=30, stage=["big_number", "bokeh", "marquee"], callouts=["checklist", "stat_pair", "before_after", "card", "dos_donts"],
                         mg=["chart", "checklist", "compare", "iconrow", "notif"], bg=["charcoal", "dots"], pack="cong_nghe"),
        "nang_luong": dict(name="Năng lượng", desc="nhịp nhanh, chữ khổng lồ, icon bay, punch dày; hợp hook mạnh, bán hàng, giới trẻ",
                           stage_every=12, behind_every=15, stage=["giant_text", "orbit_icons", "marquee", "big_number"], callouts=["icon_badge", "big_number", "trio", "warning"],
                           mg=["money", "chips", "iconrow", "chart", "photos"], bg=["gradient", "spot"], pack="nang_dong"),
        "dien_anh": dict(name="Điện ảnh", desc="tối, đèn rọi, bokeh, ít mà sâu; zoom-out chậm; hợp câu chuyện, thương hiệu, BĐS cao cấp",
                         stage_every=20, behind_every=30, stage=["spotlight", "bokeh", "giant_text"], callouts=["quote", "photo_card", "polaroid", "two_tier"],
                         mg=["photos", "doc", "question", "compare"], bg=["charcoal", "spot"], pack="dien_anh"),
        "doi_thoai": dict(name="Đối thoại", desc="như đang trò chuyện: thẻ tin nhắn, điện thoại, ý nghĩ; hợp mạng xã hội, đời sống",
                          stage_every=20, behind_every=30, stage=["orbit_icons", "marquee", "spotlight"], callouts=["phone", "thought", "photo_circle", "icon_keyword"],
                          mg=["notif", "question", "chips", "photos"], bg=["blur", "gradient"], pack="mem"),
    },
    "landscape": {
        "tin_tuc": dict(name="Bản tin", desc="lower-third + thẻ thông tin cạnh người; MG chia đôi; chữ sau lưng chỉ ở hook",
                        stage_every=30, behind_every=30, stage=["spotlight", "bokeh"], callouts=["card", "stat_pair", "icon_keyword", "checklist"],
                        mg=["chart", "doc", "compare", "notif"], bg=["charcoal", "dots"], pack="cong_nghe"),
        "bai_giang": dict(name="Bài giảng", desc="callout dạng bước / trích dẫn ở khoảng trống bên cạnh, sơ đồ; ít hiệu ứng",
                          stage_every=40, behind_every=40, stage=["spotlight"], callouts=["step", "quote", "checklist", "two_tier"],
                          mg=["checklist", "iconrow", "doc", "question"], bg=["cream", "blur"], pack="mem"),
        "phong_su": dict(name="Phóng sự", desc="ảnh kẹp bên cạnh (polaroid, strip), b-roll, zoom-out chậm; tông điện ảnh",
                         stage_every=30, behind_every=40, stage=["bokeh", "spotlight"], callouts=["photo_card", "polaroid", "photo_strip", "quote"],
                         mg=["photos", "compare", "doc"], bg=["charcoal", "spot"], pack="dien_anh"),
        "thuyet_trinh": dict(name="Thuyết trình", desc="số liệu lớn cạnh người, chart, checklist; nhịp đều",
                             stage_every=30, behind_every=30, stage=["big_number", "spotlight"], callouts=["big_number", "stat_pair", "before_after", "icon_badge"],
                             mg=["chart", "money", "chips", "compare"], bg=["gradient", "dots"], pack="nang_dong"),
    },
}

# bộ âm: vai trò → asset (assets/sfx). Âm tổng hợp tạm không còn trong bộ nào.
PACKS = {
    "mem": dict(name="Mềm", card="card_00", pop=["soft_00", "soft_02"], impact="hit_01", flash="u_flash", mg_in="mgtrans_00", check=["check_00", "check_01"]),
    "cong_nghe": dict(name="Công nghệ", card="u_card", pop=["u_pop", "pop_08"], impact="hit_03", flash="u_flash", mg_in="mgtrans_02", check=["check_02", "check_03"]),
    "nang_dong": dict(name="Năng động", card="card_02", pop=["pop_02", "pop_05"], impact="hit_04", flash="u_flash", mg_in="mgtrans_01", check=["check_04", "check_05"]),
    "dien_anh": dict(name="Điện ảnh", card="card_03", pop=["soft_01", "soft_00"], impact="hit_05", flash="u_flash", mg_in="mgtrans_03", check=["check_00", "check_02"]),
}
SYNTH_DROP = ("shimmer_light", "whoosh_short", "u_swish")
ENTRY_GAP_S = 2.5
ITEMS_PER_CALLOUT = 3


def orient(plan) -> str:
    return "landscape" if plan.width > plan.height else "portrait"


def recipe(plan) -> dict | None:
    return RECIPES[orient(plan)].get(getattr(plan, "recipe", "") or "")


def history_file() -> Path:
    return Path.home() / ".ccut" / "th_history.json"


def history(n=5) -> list[dict]:
    try:
        return json.loads(history_file().read_text(encoding="utf-8"))[-n:]
    except Exception:
        return []


def fingerprint(plan) -> dict:
    on = lambda xs: [x for x in xs or [] if x.get("enabled", True)]
    return {"recipe": getattr(plan, "recipe", ""), "pack": getattr(plan, "sfx_pack", ""), "orient": orient(plan),
            "stage": sorted({s.get("kind") for s in on(plan.stage)}), "callouts": sorted({c.get("kind") for c in on(plan.callouts)}),
            "mg": sorted({m.get("kind") for m in on(plan.mg2)}), "bg": sorted({m.get("bg") or "" for m in on(plan.mg2)} - {""})}


def _feat(fp: dict) -> set:
    return {f"r:{fp.get('recipe')}", f"p:{fp.get('pack')}"} | {f"{k}:{x}" for k in ("stage", "callouts", "mg", "bg") for x in fp.get(k) or []}


def similarity(a: dict, b: dict) -> float:
    A, B = _feat(a), _feat(b)
    return len(A & B) / max(1, len(A | B))


def record(plan, pid: str) -> None:
    """lưu dấu vân tay video vừa xuất (bản full) — tối đa 20 video gần nhất."""
    try:
        f = history_file(); f.parent.mkdir(parents=True, exist_ok=True)
        h = [x for x in history(20) if x.get("pid") != pid]
        h.append(dict(fingerprint(plan), pid=pid, t=time.strftime("%Y-%m-%d %H:%M")))
        f.write_text(json.dumps(h[-20:], ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def _pick(plan, pid=None) -> str:
    """chưa chọn công thức → lấy công thức ít dùng gần đây nhất cho khổ này."""
    rs = list(RECIPES[orient(plan)])
    used = [x.get("recipe") for x in history(10) if x.get("pid") != pid and x.get("orient") == orient(plan)]
    last = {r: i for i, r in enumerate(used)}
    return min(rs, key=lambda r: last.get(r, -1))


def apply(plan, fps: int, pid: str | None = None) -> list[str]:
    """chọn công thức / bộ âm nếu thiếu; giãn chữ sau lưng theo công thức (khổ ngang ≤ 1 / 30s). Idempotent."""
    msg = []
    if not recipe(plan):
        old = getattr(plan, "recipe", "")
        plan.recipe = _pick(plan, pid)
        plan.notes = [n for n in plan.notes if n != "recipe:auto"] + ["recipe:auto"]
        msg.append(f"công thức nhịp: {RECIPES[orient(plan)][plan.recipe]['name']}" + (f" (không có '{old}' cho khổ này)" if old else " (tự chọn, ít dùng gần đây)"))
    r = recipe(plan)
    if getattr(plan, "sfx_pack", "") not in PACKS:
        plan.sfx_pack = r["pack"]
    if orient(plan) == "portrait" and "recipe:auto" in plan.notes:
        return msg                                     # kế hoạch cũ chưa chọn công thức: khổ dọc giữ nguyên sân khấu đã duyệt
    gap, last = r["behind_every"] * fps, None
    for st in sorted(plan.stage, key=lambda s: int(s["start"])):
        if st.get("kind") not in BEHIND or not st.get("enabled", True):
            continue
        hook = int(st["start"]) < 6 * fps or st.get("turn")
        if last is not None and int(st["start"]) - last < gap and not hook:
            st["enabled"] = False
            msg.append(f"tắt chữ sau lưng {st.get('id')} — công thức {r['name']}: cách lần trước < {r['behind_every']}s")
            continue
        last = int(st["start"])
    return msg


def check(plan, pid: str | None = None) -> list[tuple[str, str]]:
    out = []
    prev = [x for x in history(5) if x.get("pid") != pid]
    if prev:
        s = similarity(fingerprint(plan), prev[-1])
        if s > 0.6:
            out.append(("warning", f"video giống video trước ({prev[-1].get('pid')}) {s:.0%} — đổi công thức nhịp / kiểu callout / MG / nền cho khác"))
    return out


def stage_every(plan) -> int:
    r = recipe(plan)
    return r["stage_every"] if r else 15


def remap(sounds: list, plan, fps: int) -> list:
    """đổi âm tự động sang bộ âm của video + giảm mật độ. Âm khai tay (plan.sounds) giữ nguyên."""
    pk = PACKS.get(getattr(plan, "sfx_pack", "") or "", PACKS["mem"])
    manual = {s.id for s in plan.sounds}
    out, items, last_entry = [], {}, -10 ** 9
    for s in sorted(sounds, key=lambda s: s.hit):
        if s.id in manual or s.asset in ("u_tick", "u_money") or s.asset.startswith("tick_"):
            out.append(s); continue
        a = s.asset
        if a in SYNTH_DROP:
            continue
        if a == "impact_soft" or a.startswith("hit_"):
            a = pk["impact"]
        elif a.startswith("mgtrans_"):
            a = pk["mg_in"]
        elif a.startswith("card_") or a == "u_card":
            a = pk["card"]
        elif a.startswith("check_"):
            a = pk["check"][len(out) % 2]
        elif a.startswith(("pop_", "soft_")) or a == "u_pop":
            a = pk["pop"][len(out) % 2]
        s.asset = a
        entry = s.id in (f"co_{s.linked_event}", f"stage_{s.linked_event}")
        if entry:
            if s.hit - last_entry < ENTRY_GAP_S * fps:
                continue
            last_entry = s.hit
        if s.id.startswith("co_") and not entry:
            items[s.linked_event] = items.get(s.linked_event, 0) + 1
            if items[s.linked_event] > ITEMS_PER_CALLOUT:
                continue
        out.append(s)
    return out


def prompt_block() -> str:
    h = history(5)
    lines = ["\n## ĐỔI MỚI GIỮA CÁC VIDEO (bắt buộc)",
             "Lõi cố định giữ nguyên (font, 3 tông, phụ đề neo, chữ nhấn đúng mốc, số tiền, logo thật, khung kính).",
             "Chọn MỘT công thức nhịp hợp nội dung → `plan.recipe`; dùng chủ yếu các kiểu sân khấu / callout / MG / nền trong công thức đó,",
             "được thêm kiểu khác nhưng không lặp bố cục của video trước. Khổ ngang: chữ sau lưng ≤ 1 lần / 30s (hook, câu bẻ lái `\"turn\": true`).",
             "Bộ âm `plan.sfx_pack` mặc định theo công thức (mem | cong_nghe | nang_dong | dien_anh); app tự đổi âm + giãn mật độ."]
    for o, rs in RECIPES.items():
        lines.append(f"Khổ {'dọc' if o == 'portrait' else 'ngang'}:")
        lines += [f"- `{k}` {r['name']}: {r['desc']} — sân khấu {', '.join(r['stage'])}; callout {', '.join(r['callouts'])}; MG {', '.join(r['mg'])}; nền {'/'.join(r['bg'])}"
                  for k, r in rs.items()]
    if h:
        lines.append("Video GẦN ĐÂY (tránh lặp công thức + bộ kiểu này):")
        lines += [f"- {x.get('t')} {x.get('pid')}: {x.get('recipe')} · âm {x.get('pack')} · sân khấu {x.get('stage')} · callout {x.get('callouts')} · MG {x.get('mg')}" for x in h]
    return "\n".join(lines) + "\n"
