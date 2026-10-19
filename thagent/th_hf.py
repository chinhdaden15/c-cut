"""Talking Head × HyperFrames (công cụ dựng dùng chung thagent.hyper): text nhấn, tiêu đề, phụ đề thiết kế, overlay.

plan.hf = [{"id": "cap1", "start": <frame timeline>, "end": <frame>, "layer": "front" | "behind_subject",
            "spec": {"layers": [ … chuẩn thagent/hyper/spec.py, giây tính từ start … ]}}]
- Kích thước/fps/thời lượng lấy từ plan (không ghi trong spec). Mỗi mục render MỘT clip mov có alpha (lưu đệm theo mã băm).
- Ghép trong render.composite: "behind_subject" vào lớp SAU nhân vật (alpha người vẫn đè lên — giữ quy tắc chữ sau đầu),
  "front" vào lớp trước; vẽ trước chữ/thẻ của Talking Head trong cùng lớp. Logic cắt lời/biên tập không đổi.
- Phụ đề theo lời: words_tl(pid, start_f, end_f) → [(chữ, giây tính từ start)] theo timeline ĐÃ cắt (đúng mapping nguồn→timeline).
- HyperFrames chưa sẵn sàng: plan.hf không có phương án tương đương trong bộ vẽ Talking Head → preflight báo LỖI (bị chặn), không âm thầm bỏ.
"""
from __future__ import annotations

from pathlib import Path


def spec_for(plan, it: dict, out: Path) -> dict:
    sp = dict(it.get("spec") or {})
    sp.update(job_id=f"th-{it['id']}", width=plan.width, height=plan.height, fps=plan.fps,
              duration=round((int(it["end"]) - int(it["start"])) / plan.fps, 3), background="transparent",
              output={"path": str(out), "format": "mov"})
    return sp


def check(plan) -> list[tuple[str, str]]:
    if not getattr(plan, "hf", None):
        return []
    from .capabilities import status
    from .hyper import spec as S
    out = []
    st = status("hyperframes")
    if not st.get("ok"):
        return [("error", f"plan.hf có {len(plan.hf)} lớp HyperFrames nhưng công cụ CHƯA SẴN SÀNG ({'; '.join(st.get('problems', []))}) "
                          "— Talking Head không có bộ vẽ tương đương cho các lớp này → bị chặn")]
    for it in plan.hf:
        if it.get("layer", "front") not in ("front", "behind_subject"):
            out.append(("error", f"hf {it.get('id')}: layer phải là front|behind_subject"))
        if int(it["end"]) <= int(it["start"]) or int(it["end"]) > plan.duration_frames:
            out.append(("error", f"hf {it.get('id')}: khung {it['start']}–{it['end']} ngoài timeline (0–{plan.duration_frames})"))
            continue
        for lv, m in S.validate(S.normalize(spec_for(plan, it, Path("/tmp/x.mov")))):
            out.append((lv, f"hf {it['id']}: {m}"))
    return out


def prerender(plan, work: Path, log=print) -> list[dict]:
    from .hyper.job import Job
    items = []
    for it in getattr(plan, "hf", None) or []:
        out = Path(work) / "hf" / f"{it['id']}.mov"
        st = Job(spec_for(plan, it, out), Path(work) / "hf_jobs").run(progress=log)
        items.append({"path": st["output"], "start": int(it["start"]) / plan.fps, "dur": (int(it["end"]) - int(it["start"])) / plan.fps,
                      "layer": it.get("layer", "front"), "id": it["id"]})
    return items


def words_tl(pid: str, start_f: int, end_f: int) -> list[tuple[str, float]]:
    """chữ nói trong [start_f, end_f) của timeline ĐÃ CẮT + giây tính từ start_f (dùng cho word_times của phụ đề)."""
    from . import pipeline as P
    from . import timeline as T
    c = P.Ctx(pid)
    pl = c.project.plan
    T.build_mapping(pl)
    out = []
    for w in c.project.words:
        f = T.src_to_tl(pl, w.source_start)
        if f is None:
            continue
        if start_f <= f < end_f:
            out.append((w.text, round((f - start_f) / pl.fps, 3)))
    return out
