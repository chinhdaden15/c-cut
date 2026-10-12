"""Đường dẫn gốc. Bản dev: thư mục repo. Bản cài đặt: app đặt CCUT_HOME (dữ liệu, ghi được) và CCUT_RES (tài nguyên đi kèm, chỉ đọc)."""
import os
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("CCUT_HOME") or _REPO)
RES = Path(os.environ.get("CCUT_RES") or _REPO)
FROZEN = bool(os.environ.get("CCUT_RES"))
