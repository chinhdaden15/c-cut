"""C-Cut core package."""
import os as _os

# Bản đóng gói (PyInstaller) không thấy chứng chỉ gốc của hệ thống → mọi urlopen lỗi
# CERTIFICATE_VERIFY_FAILED. Trỏ OpenSSL tới bộ chứng chỉ certifi (vẫn kiểm tra SSL đầy đủ).
if not _os.environ.get("SSL_CERT_FILE"):
    try:
        import certifi as _certifi
        if _os.path.isfile(_certifi.where()):
            _os.environ["SSL_CERT_FILE"] = _certifi.where()
    except Exception:
        pass
