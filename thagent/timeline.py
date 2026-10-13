"""Ánh xạ thời gian nguồn ↔ timeline sau cắt. Mọi module dùng các hàm ở đây,
không tự cộng trừ timestamp. Khoảng frame dùng quy ước [start, end)."""
from __future__ import annotations

from .schema import EditSegment, Plan


def sec_to_frame(t: float, fps: int) -> int:
    return int(round(t * fps))


def build_mapping(plan: Plan) -> Plan:
    """Tính timeline_in/out cho các segment keep theo `order`; cập nhật duration."""
    fps = plan.fps
    cur = 0
    for s in sorted([s for s in plan.segments if s.keep], key=lambda s: s.order):
        n = sec_to_frame(s.source_out, fps) - sec_to_frame(s.source_in, fps)
        s.timeline_in, s.timeline_out = cur, cur + max(n, 0)
        cur += max(n, 0)
    for s in plan.segments:
        if not s.keep:
            s.timeline_in = s.timeline_out = -1
    plan.duration_frames = cur
    return plan


def kept(plan: Plan) -> list[EditSegment]:
    return sorted([s for s in plan.segments if s.keep], key=lambda s: s.order)


def src_to_tl(plan: Plan, t: float) -> int | None:
    """Thời điểm nguồn (giây) → frame timeline, None nếu nằm trong đoạn bị cắt.
    Nếu một đoạn nguồn được dùng nhiều lần (Hook), trả về lần xuất hiện đầu."""
    f = sec_to_frame(t, plan.fps)
    for s in kept(plan):
        a, b = sec_to_frame(s.source_in, plan.fps), sec_to_frame(s.source_out, plan.fps)
        if a <= f < b:
            return s.timeline_in + (f - a)
    return None


def src_to_tl_near(plan: Plan, t: float) -> int:
    """Như src_to_tl nhưng mốc rơi vào đoạn bị cắt thì dời tới đầu đoạn giữ kế tiếp (hết thì cuối timeline)."""
    f = src_to_tl(plan, t)
    if f is not None:
        return f
    nxt = [s for s in kept(plan) if s.source_in >= t]
    return min(nxt, key=lambda s: s.source_in).timeline_in if nxt else plan.duration_frames


def src_to_tl_in_role(plan: Plan, t: float, role: str) -> int | None:
    f = sec_to_frame(t, plan.fps)
    for s in kept(plan):
        if s.role != role:
            continue
        a, b = sec_to_frame(s.source_in, plan.fps), sec_to_frame(s.source_out, plan.fps)
        if a <= f < b:
            return s.timeline_in + (f - a)
    return None


def tl_to_src_frame(plan: Plan, f: int) -> int | None:
    for s in kept(plan):
        if s.timeline_in <= f < s.timeline_out:
            return sec_to_frame(s.source_in, plan.fps) + (f - s.timeline_in)
    return None


def tc(f: int, fps: int = 30) -> str:
    return f"{f // fps // 60:02d}:{f // fps % 60:02d}.{f % fps:02d}f"
