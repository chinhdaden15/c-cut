"""Voice to Motion — renderer motion graphic từ voice (skill `voice-to-motion`).

Độc lập với phần Talking Head: chỉ dùng chung font, icon, ffmpeg, chép lời.
  timeline.json (dữ liệu, chỉnh sửa được)  →  render.py (dựng từng frame)  →  audio.py (trộn voice + SFX)  →  qa.py
Lệnh: python -m thagent.v2m <init|words|render|stills|qa|revise> …
"""
