"""Kiểm tra bản đã đóng gói: nạp đủ thư viện dựng video, chạy thử model. Chạy bằng ccut-py, CCUT_HOME=build/res/seed."""
import tempfile
from pathlib import Path

import av, cv2, faster_whisper, mediapipe as mp, numpy, onnxruntime as ort  # noqa: F401
import vieneu.v3turbo, vieneu._v3_turbo_engine.onnx_runtime_lite, vieneu.base, sea_g2p, kaldi_native_fbank, soxr, soundfile  # noqa: F401,E401  giọng đọc
from thagent import voice  # noqa: F401
from thagent import matting, pointing, gaze, clips, render, preflight, stills, transcribe, sfx, typography, cleancut, updater, agent, tools  # noqa: F401
from thagent.paths import ROOT

ort.InferenceSession(str(matting.RVM_MODEL), providers=["CPUExecutionProvider"])
mp.solutions.face_detection.FaceDetection(model_selection=0).close()
mp.solutions.hands.Hands(static_image_mode=True).close()
p = Path(tempfile.mkdtemp()) / "vi.json"
p.write_text('{"t": "chép lời tiếng Việt ấ ộ ữ"}')
assert "ấ" in p.read_text()
print("SMOKE OK", ROOT)
