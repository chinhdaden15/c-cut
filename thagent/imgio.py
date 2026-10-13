"""Đọc/ghi ảnh an toàn với đường dẫn có dấu (cv2.imread/imwrite trên Windows không mở được “Dự Án Mới\\...”)
và với định dạng OpenCV không đọc được (webp lạ, avif, gif…) → thử thêm Pillow."""
from __future__ import annotations

import os

import cv2
import numpy as np


def imread(path, flags=cv2.IMREAD_COLOR):
    """→ ảnh BGR (như cv2.imread) hoặc None nếu không đọc được."""
    path = os.fspath(path)
    try:
        img = cv2.imdecode(np.fromfile(path, np.uint8), flags)
        if img is not None:
            return img
    except Exception:
        pass
    try:
        from PIL import Image
        with Image.open(path) as im:
            return cv2.cvtColor(np.asarray(im.convert("RGB")), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def must_read(path):
    img = imread(path)
    if img is None:
        raise RuntimeError(f"không đọc được ảnh {os.path.basename(os.fspath(path))} — file hỏng hoặc không phải ảnh, tải ảnh khác")
    return img


def imwrite(path, img, params=None) -> bool:
    path = os.fspath(path)
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".jpg", img, params or [])
    if ok:
        buf.tofile(path)
    return bool(ok)
