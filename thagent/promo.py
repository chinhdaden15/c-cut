"""Nhận diện PHIM DỰNG SẴN của chủ đầu tư / nhãn hàng trong bộ tư liệu người dùng đưa vào.

Phim dựng sẵn = có lời thuyết minh nhưng KHÔNG thấy người nói trên hình (lồng tiếng) + cắt cảnh dày như phim quảng cáo.
→ chỉ được lấy HÌNH làm b-roll minh hoạ cho lời của người dùng; KHÔNG lấy tiếng / lời thuyết minh làm mạch video.

Khác với “lời sau máy” (người dùng tự quay, vừa đi vừa nói, không thấy mặt): ít điểm cắt (1 cảnh liền) → vẫn là lời
của người dùng, dùng được.
"""
from __future__ import annotations

import re
import subprocess

NARR_FACE = 0.25        # tỉ lệ khung có mặt người trong lúc đang nói < mức này → lời đọc không thấy người nói
CUTS_PER_MIN = 6.0      # ≥ 6 điểm cắt / phút → phim đã dựng (tự quay một mạch thường 0–2)
MIN_TALK = 3.0          # có ít nhất 3s lời mới tính là có thuyết minh

NOTE = ("PHIM DỰNG SẴN (chủ đầu tư / nhãn hàng): lời thuyết minh không phải của người dùng — chỉ lấy HÌNH làm b-roll "
        "minh hoạ cho lời người dùng, tắt tiếng; không làm đoạn nói / giọng lồng.")


def cut_count(path: str, duration: float) -> int:
    """số điểm chuyển cảnh (ffmpeg scene > 0.3, ảnh thu nhỏ 4 khung/s — nhanh)."""
    try:
        r = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-an", "-vf",
                            "fps=4,scale=160:-2,select='gt(scene,0.3)',showinfo", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=max(60, duration * 2))
        return len(re.findall(r"pts_time:", r.stderr))
    except Exception:
        return 0


def face_in_speech(spans: list[tuple[float, float]], samples: list[tuple[float, bool]]) -> float:
    """tỉ lệ mẫu có mặt người nằm trong các khoảng đang nói."""
    hit = [f for t, f in samples if any(a <= t <= b for a, b in spans)]
    return round(sum(1 for f in hit if f) / len(hit), 2) if hit else 0.0


def classify(talk_s: float, duration: float, face_ratio: float, cuts: int) -> str | None:
    """'phim_dung_san' | 'loi_sau_may' | None (không phải trường hợp lời không thấy mặt)."""
    if talk_s < MIN_TALK or face_ratio >= NARR_FACE:
        return None
    per_min = cuts / max(duration / 60, 0.25)
    return "phim_dung_san" if per_min >= CUTS_PER_MIN else "loi_sau_may"
