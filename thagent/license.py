"""Bản quyền skill C-Cut: mọi skill bán (PAID) dùng thử 2 video/skill/máy, mua thì mở khoá vĩnh viễn trên 1 máy.

- Mã thiết bị: băm mã phần cứng có sẵn của máy (Windows MachineGuid, Mac IOPlatformUUID) → cài lại app/Windows vẫn ra đúng mã.
- Máy chủ (license-server/, Cloudflare Worker) KÝ mọi quyền dùng bằng Ed25519; app chỉ giữ khoá công khai → không giả được mã/lượt thử,
  kể cả khi trỏ app sang máy chủ khác. Mã đã mua dùng được offline, nhưng có mạng là app hỏi lại máy chủ (≥10 phút/lần) theo danh sách mã
  CÒN HIỆU LỰC đã ký kèm nonce → thu hồi / gỡ khỏi máy / khoá máy có hiệu lực ngay lần hỏi sau; quá OFFLINE_DAYS không hỏi được → phải nối mạng.
- Chặn ở 2 chỗ: đầu việc (can_start — hết lượt thì báo ngay, không tốn công Claude) và trong hàm XUẤT video của skill (require).
  1 lượt thử = 1 dự án được xuất; xuất lại cùng dự án không trừ thêm.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
from base64 import urlsafe_b64decode
from pathlib import Path

from .paths import ROOT

SERVER = (os.environ.get("CCUT_LICENSE_URL") or "https://ccut-license.dvchinh155.workers.dev").rstrip("/")   # mọi phản hồi đều đã ký
PUBLIC_KEY = bytes.fromhex("c3885110c50b9b67aacca1ff0f0734e166eebe9c432e90a57863a19b7a41994a")   # Ed25519 — CỐ ĐỊNH, không cho đổi qua biến môi trường
FREE: set[str] = set()                     # không còn skill miễn phí (skill người dùng tự tạo bằng newskill không thuộc PAID → tự do)
PAID = {"talking-head-style": "Skill Talking Head", "review-editor": "Skill Review", "voice-to-motion": "Skill Voice to Motion",
        "text-to-video": "Skill Text to Video"}
COMBO = "all"
STORE = Path(os.environ.get("CCUT_LICENSE_STORE") or ROOT / "license.json")   # nội dung đã ký → đổi chỗ lưu không mở khoá được gì
_LOCK = threading.Lock()
RECHECK_S = 600                            # skill đã mua: hỏi lại máy chủ tối đa 10 phút/lần khi bắt đầu / xuất
OFFLINE_DAYS = 7                           # không hỏi được máy chủ quá chừng này ngày → cần mạng để xác minh lại


class LicenseError(RuntimeError):
    """thông báo cho người dùng — bắt đầu bằng 'BẢN QUYỀN:' để giao diện mở màn mua."""


# ---------------- Ed25519 (chỉ kiểm chữ ký; theo RFC 8032) ----------------
_p = 2 ** 255 - 19
_q = 2 ** 252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _recover_x(y: int, sign: int):
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p)
    if x2 % _p == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p:
        x = x * _I % _p
    if (x * x - x2) % _p:
        return None
    return _p - x if (x & 1) != sign else x


_gy = 4 * pow(5, _p - 2, _p) % _p
_gx = _recover_x(_gy, 0)
_G = (_gx, _gy, 1, _gx * _gy % _p)


def _add(P, Q):
    a, b = (P[1] - P[0]) * (Q[1] - Q[0]) % _p, (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    c, d = 2 * P[3] * Q[3] * _d % _p, 2 * P[2] * Q[2] % _p
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f, g * h, f * g, e * h)


def _mul(s: int, P):
    Q = (0, 1, 1, 0)
    while s:
        if s & 1:
            Q = _add(Q, P)
        P = _add(P, P)
        s >>= 1
    return Q


def _decompress(b: bytes):
    if len(b) != 32:
        return None
    y = int.from_bytes(b, "little")
    sign, y = y >> 255, y & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _p)


def _compress(P) -> bytes:
    zi = pow(P[2], _p - 2, _p)
    x, y = P[0] * zi % _p, P[1] * zi % _p
    return (y | ((x & 1) << 255)).to_bytes(32, "little")


def _h(b: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b).digest(), "little") % _q


def verify_sig(pub: bytes, msg: bytes, sig: bytes) -> bool:
    if len(sig) != 64:
        return False
    A, R = _decompress(pub), _decompress(sig[:32])
    s = int.from_bytes(sig[32:], "little")
    if not A or not R or s >= _q:
        return False
    sB, hA = _mul(s, _G), _mul(_h(sig[:32] + pub + msg), A)
    RhA = _add(R, hA)
    return (sB[0] * RhA[2] - RhA[0] * sB[2]) % _p == 0 and (sB[1] * RhA[2] - RhA[1] * sB[2]) % _p == 0


def _sign(seed: bytes, msg: bytes) -> bytes:
    """ký (chỉ dùng cho bộ kiểm — app không có khoá bí mật)."""
    h = hashlib.sha512(seed).digest()
    a = (int.from_bytes(h[:32], "little") & ((1 << 254) - 8)) | (1 << 254)
    A = _compress(_mul(a, _G))
    r = _h(h[32:] + msg)
    Rs = _compress(_mul(r, _G))
    return Rs + ((r + _h(Rs + A + msg) * a) % _q).to_bytes(32, "little")


def _b64(s: str) -> bytes:
    return urlsafe_b64decode(s + "=" * (-len(s) % 4))


def read_token(tok: str) -> dict | None:
    """giải + kiểm chữ ký mã do máy chủ cấp; sai → None. (đệm theo chuỗi mã — kiểm chữ ký Python thuần ~0,2s/lần)"""
    p = _read(tok)
    return dict(p) if p else None


@functools.lru_cache(maxsize=256)
def _read(tok: str):
    try:
        body, sig = tok.split(".")
        raw = _b64(body)
        return json.loads(raw) if verify_sig(PUBLIC_KEY, raw, _b64(sig)) else None
    except Exception:
        return None


# ---------------- thiết bị + lưu trữ ----------------
_DEV: str | None = None


def device_id() -> str:
    global _DEV
    if _DEV:
        return _DEV
    raw = ""
    try:
        if os.name == "nt":
            import winreg
            k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0,
                               winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            raw = winreg.QueryValueEx(k, "MachineGuid")[0]
        elif sys.platform == "darwin":
            out = subprocess.run(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"], capture_output=True, text=True, timeout=10).stdout
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            raw = m.group(1) if m else ""
        elif Path("/etc/machine-id").exists():
            raw = Path("/etc/machine-id").read_text().strip()
    except Exception:
        raw = ""
    if not raw:                                     # máy không đọc được mã phần cứng → mã ngẫu nhiên lưu ở thư mục người dùng
        f = Path.home() / ".ccut_device"
        if not f.exists():
            f.write_text(uuid.uuid4().hex)
        raw = "f:" + f.read_text().strip()
    _DEV = hashlib.sha256(f"c-cut-device:{raw}".encode()).hexdigest()
    return _DEV


def _load() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(d: dict):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STORE)


def _info() -> dict:
    try:
        from .ccut_api import APP_VERSION
    except Exception:
        APP_VERSION = "?"
    return {"device": device_id(), "os": f"{platform.system()} {platform.machine()}", "app": APP_VERSION}


def _http(method: str, path: str, body: dict | None = None, timeout: float = 12) -> dict:
    if not SERVER:
        raise LicenseError("BẢN QUYỀN: máy chủ bản quyền chưa được cấu hình")
    ctx = None
    try:
        import ssl
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(SERVER + path, data=data, method=method,
                                 headers={"content-type": "application/json", "user-agent": "C-Cut"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read())
        except Exception:
            return {"ok": False, "error": f"máy chủ báo lỗi {e.code}"}


# ---------------- quyền dùng ----------------
def _licenses(d: dict) -> list[dict]:
    me, out = device_id(), []
    for tok in d.get("tokens", []):
        p = read_token(tok)
        if p and p.get("t") == "lic" and p.get("device") == me and p.get("key") not in d.get("revoked", []):
            out.append(p)
    return out


def owns(skill: str) -> bool:
    return any(p["product"] in (skill, COMBO) for p in _licenses(_load()))


def _grant(d: dict, skill: str, project: str) -> bool:
    p = read_token(d.get("grants", {}).get(f"{skill}/{project}", ""))
    return bool(p and p.get("t") == "trial" and p.get("device") == device_id() and p.get("skill") == skill and p.get("project") == project)


def _project(pdir_or_pid) -> str:
    return re.sub(r"[^\w.-]", "_", Path(str(pdir_or_pid)).name)[:128]


def sync(timeout: float = 12) -> dict:
    """lấy từ máy chủ: mã đã mua của máy này (cài lại app tự khôi phục), mã bị thu hồi, lượt thử đã dùng."""
    nonce = uuid.uuid4().hex
    r = _http("POST", "/v1/status", {**_info(), "nonce": nonce}, timeout)
    if not r.get("ok"):
        raise LicenseError("BẢN QUYỀN: " + str(r.get("error", "máy chủ không phản hồi")))
    st = read_token(r.get("state", ""))
    if not (st and st.get("t") == "st" and st.get("device") == device_id() and st.get("nonce") == nonce):
        raise LicenseError("BẢN QUYỀN: phản hồi máy chủ không hợp lệ")
    keys = set(st.get("keys") or [])
    with _LOCK:
        d = _load()
        # máy chủ là nguồn đúng: chỉ giữ mã còn hiệu lực của máy này (bỏ mã đã thu hồi / gỡ khỏi máy / máy bị khoá)
        d["tokens"] = sorted({tok for tok in [*d.get("tokens", []), *r.get("tokens", [])]
                              if (p := read_token(tok)) and p.get("key") in keys})
        d.update(revoked=r.get("revoked", []), trials=r.get("trials", {}), trial_limit=r.get("trial_limit", 2),
                 blocked=bool(st.get("blocked")), synced=time.time(), verified=time.time())
        _save(d)
    return d


def _recheck(skill: str) -> None:
    """skill đã mua (theo mã lưu trên máy): hỏi lại máy chủ nếu lâu chưa hỏi. Mất mạng → vẫn dùng trong OFFLINE_DAYS ngày."""
    d = _load()
    last = float(d.get("verified") or 0)
    if last > time.time() + 300:            # sửa tay license.json để khỏi hỏi lại → coi như chưa xác minh
        last = 0
    if time.time() - last < RECHECK_S:
        return
    try:
        sync(timeout=8)
    except LicenseError:
        if time.time() - last > OFFLINE_DAYS * 86400:
            raise LicenseError(f"BẢN QUYỀN: cần kết nối mạng để xác minh {PAID[skill]} (đã {OFFLINE_DAYS} ngày chưa xác minh)")
    except Exception:
        if time.time() - last > OFFLINE_DAYS * 86400:
            raise LicenseError(f"BẢN QUYỀN: cần kết nối mạng để xác minh {PAID[skill]} (đã {OFFLINE_DAYS} ngày chưa xác minh)")


def summary() -> dict:
    """trạng thái hiển thị (không gọi mạng): mỗi skill bán → owned / used / limit."""
    d = _load()
    lic = _licenses(d)
    lim = int(d.get("trial_limit", 2))
    skills = {s: {"name": n, "owned": any(p["product"] in (s, COMBO) for p in lic), "used": int(d.get("trials", {}).get(s, 0)),
                  "limit": lim} for s, n in PAID.items()}
    return {"device": device_id()[:12], "configured": bool(SERVER), "skills": skills, "free": sorted(FREE),
            "combo": any(p["product"] == COMBO for p in lic), "blocked": d.get("blocked", False), "synced": d.get("synced")}


def can_start(skill: str, project) -> None:
    """đầu việc: skill bán + chưa mua + hết lượt thử → báo ngay. Lỗi mạng → để bước xuất quyết định."""
    if skill not in PAID:
        return
    if owns(skill):
        _recheck(skill)
        if owns(skill):
            return
        if _load().get("blocked"):
            raise LicenseError("BẢN QUYỀN: máy này đã bị khoá — liên hệ người bán")
    pr = _project(project)
    d = _load()
    if _grant(d, skill, pr):
        return
    try:
        d = sync(timeout=8)
    except LicenseError:
        return
    if d.get("blocked"):
        raise LicenseError("BẢN QUYỀN: máy này đã bị khoá — liên hệ người bán")
    if owns(skill):
        return
    if int(d.get("trials", {}).get(skill, 0)) >= int(d.get("trial_limit", 2)):
        raise LicenseError(f"BẢN QUYỀN: đã hết {d.get('trial_limit', 2)} video dùng thử {PAID[skill]} — mua để dùng tiếp")


def require(skill: str, project, log=print) -> str:
    """trước khi XUẤT video: free | licensed | trial. Không được phép → LicenseError."""
    if skill not in PAID:
        return "free"
    if owns(skill):
        _recheck(skill)
        if owns(skill):
            return "licensed"
        if _load().get("blocked"):
            raise LicenseError("BẢN QUYỀN: máy này đã bị khoá — liên hệ người bán")
    pr = _project(project)
    if _grant(_load(), skill, pr):
        return "trial"
    try:
        r = _http("POST", "/v1/trial", {**_info(), "skill": skill, "project": pr})
    except LicenseError:
        raise
    except Exception:
        raise LicenseError(f"BẢN QUYỀN: cần kết nối mạng để dùng thử {PAID[skill]} (đã mua thì không cần mạng)")
    if r.get("blocked"):
        raise LicenseError("BẢN QUYỀN: máy này đã bị khoá — liên hệ người bán")
    if not r.get("ok"):
        raise LicenseError(f"BẢN QUYỀN: đã hết {r.get('limit', 2)} video dùng thử {PAID[skill]} — mua để dùng tiếp")
    p = read_token(r.get("grant", ""))
    if not (p and p.get("t") == "trial" and p.get("device") == device_id() and p.get("skill") == skill and p.get("project") == pr):
        raise LicenseError("BẢN QUYỀN: phản hồi máy chủ không hợp lệ")
    with _LOCK:
        d = _load()
        d.setdefault("grants", {})[f"{skill}/{pr}"] = r["grant"]
        d.setdefault("trials", {})[skill] = r.get("used", 0)
        d["trial_limit"] = r.get("limit", 2)
        _save(d)
    log(f"Dùng thử {PAID[skill]}: video {r.get('used')}/{r.get('limit')}")
    return "trial"


def _keep(tok: str) -> dict:
    p = read_token(tok or "")
    if not (p and p.get("t") == "lic" and p.get("device") == device_id()):
        raise LicenseError("BẢN QUYỀN: mã máy chủ trả về không hợp lệ")
    with _LOCK:
        d = _load()
        d["tokens"] = sorted(set(d.get("tokens", [])) | {tok})
        d["revoked"] = [k for k in d.get("revoked", []) if k != p["key"]]
        d["verified"] = time.time()
        _save(d)
    return p


def activate(key: str) -> dict:
    r = _http("POST", "/v1/activate", {**_info(), "key": key.strip()})
    if not r.get("ok"):
        raise LicenseError("BẢN QUYỀN: " + str(r.get("error", "không kích hoạt được")))
    p = _keep(r["token"])
    return {"product": p["product"], "name": r.get("name", p["product"])}


def products() -> list[dict]:
    r = _http("GET", "/v1/products", timeout=8)
    return r.get("products", [])


def order(product: str, contact: str = "") -> dict:
    r = _http("POST", "/v1/order", {**_info(), "product": product, "contact": contact})
    if not r.get("ok"):
        raise LicenseError("BẢN QUYỀN: " + str(r.get("error", "không tạo được đơn")))
    return r


def order_status(oid: str) -> dict:
    if not re.fullmatch(r"[\w-]{8,64}", oid):
        raise LicenseError("BẢN QUYỀN: mã đơn không hợp lệ")
    r = _http("GET", f"/v1/order/{oid}", timeout=8)
    if r.get("token"):
        _keep(r["token"])
    return {"status": r.get("status"), "key": r.get("key"), "activated": bool(r.get("token"))}
