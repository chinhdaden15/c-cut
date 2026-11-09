"""Khoá API cho phần mềm ngoài (CN.AI…) điều khiển C-Cut qua http://127.0.0.1:<cổng>/api/ccut.

- Giao diện C-Cut (cửa sổ app) dùng cookie phiên `ccut_ui` (tạo mỗi lần mở app, HttpOnly, SameSite=Strict) → không cần khoá.
- Phần mềm ngoài gửi khoá trong header `X-CCut-Key: ccut_…` (hoặc `Authorization: Bearer ccut_…`).
  API phải đang BẬT (Cài đặt → API) và khoá phải còn trong danh sách; sai → 401/403.
- Người dùng tạo nhiều khoá (mỗi phần mềm một khoá), đổi khoá (khoá cũ hết hiệu lực ngay), xoá khoá, bật/tắt API.
  Chỉ giao diện C-Cut mới quản lý được khoá (phần mềm ngoài có khoá cũng không tự tạo / xem khoá khác được).
Lưu ở <dữ liệu app>/api_keys.json (chỉ trên máy này).
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .paths import ROOT

FILE = ROOT / "api_keys.json"
UI_TOKEN = secrets.token_urlsafe(32)          # cookie phiên của giao diện — đổi mỗi lần mở app
COOKIE = "ccut_ui"
_LOCK = threading.Lock()
_D: dict | None = None
router = APIRouter(prefix="/api/ccut/apikeys")


def _load() -> dict:
    global _D
    if _D is None:
        try:
            _D = json.loads(FILE.read_text(encoding="utf-8"))
        except Exception:
            _D = {}
        _D.setdefault("enabled", False)
        _D.setdefault("keys", [])
    return _D


def _save():
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(_load(), ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)
    try:
        FILE.chmod(0o600)
    except Exception:
        pass


def _new_key() -> str:
    return "ccut_" + secrets.token_urlsafe(30)


def enabled() -> bool:
    return bool(_load()["enabled"])


def key_from(request: Request) -> str:
    k = (request.headers.get("x-ccut-key") or "").strip()
    if not k:
        auth = request.headers.get("authorization") or ""
        if auth.lower().startswith("bearer "):
            k = auth[7:].strip()
    return k


def match(key: str) -> dict | None:
    if not key:
        return None
    for k in _load()["keys"]:
        if secrets.compare_digest(k["key"], key):
            return k
    return None


def touch(k: dict, client: str = ""):
    """ghi lần dùng gần nhất (ghi file thưa: tối đa 1 lần / 30 giây mỗi khoá)."""
    now = time.time()
    with _LOCK:
        dirty = now - float(k.get("last_used") or 0) > 30 or (client and client != k.get("last_client"))
        k["last_used"] = now
        if client:
            k["last_client"] = client
        if dirty:
            _save()


def is_ui(request: Request) -> bool:
    c = request.cookies.get(COOKIE) or ""
    return bool(c) and secrets.compare_digest(c, UI_TOKEN)


def check(request: Request) -> tuple[bool, int, str]:
    """→ (cho qua?, mã lỗi, thông báo). Giao diện C-Cut luôn qua; phần mềm ngoài cần API bật + khoá đúng."""
    if is_ui(request):
        return True, 200, ""
    path = request.url.path
    if path.startswith("/api/ccut/apikeys"):
        return False, 403, "Chỉ quản lý khoá API được từ giao diện C-Cut (Cài đặt → API)"
    key = key_from(request)
    if not key:
        return False, 401, "Thiếu khoá API — gửi header X-CCut-Key (tạo khoá trong C-Cut: Cài đặt → API)"
    if not enabled():
        return False, 403, "API đang tắt — bật trong C-Cut: Cài đặt → API"
    k = match(key)
    if not k:
        return False, 401, "Khoá API không đúng hoặc đã bị xoá / đổi — lấy khoá mới trong C-Cut: Cài đặt → API"
    touch(k, (request.headers.get("x-ccut-client") or "").strip()[:40])
    return True, 200, ""


def _pub(k: dict) -> dict:
    return {"id": k["id"], "name": k["name"], "key": k["key"], "created": k.get("created"),
            "last_used": k.get("last_used"), "last_client": k.get("last_client")}


def _api_url() -> str:
    try:
        return json.loads((ROOT / "api.json").read_text(encoding="utf-8"))["url"]
    except Exception:
        return ""


@router.get("")
def list_keys(request: Request = None):
    d = _load()
    url = (str(request.base_url).rstrip("/") + "/api/ccut") if request is not None else _api_url()
    return {"enabled": d["enabled"], "url": url.replace("://localhost:", "://127.0.0.1:"), "header": "X-CCut-Key",
            "keys": [_pub(k) for k in d["keys"]]}


class NameReq(BaseModel):
    name: str = ""


class EnableReq(BaseModel):
    enabled: bool


@router.post("")
def create(req: NameReq, request: Request):
    d = _load()
    name = (req.name or "").strip()[:40] or f"Khoá {len(d['keys']) + 1}"
    k = {"id": secrets.token_hex(4), "name": name, "key": _new_key(), "created": time.time(), "last_used": None, "last_client": None}
    with _LOCK:
        d["keys"].append(k)
        if len(d["keys"]) == 1:
            d["enabled"] = True                     # khoá đầu tiên → bật API luôn (người dùng tạo khoá là để dùng)
        _save()
    return list_keys(request) | {"created": _pub(k)}


@router.post("/{kid}/rotate")
def rotate(kid: str, request: Request):
    d = _load()
    k = next((x for x in d["keys"] if x["id"] == kid), None)
    if not k:
        raise HTTPException(404, "Không có khoá này")
    with _LOCK:
        k.update(key=_new_key(), created=time.time(), last_used=None, last_client=None)
        _save()
    return list_keys(request) | {"created": _pub(k)}


@router.put("/{kid}")
def rename(kid: str, req: NameReq, request: Request):
    d = _load()
    k = next((x for x in d["keys"] if x["id"] == kid), None)
    if not k:
        raise HTTPException(404, "Không có khoá này")
    with _LOCK:
        k["name"] = (req.name or "").strip()[:40] or k["name"]
        _save()
    return list_keys(request)


@router.delete("/{kid}")
def delete(kid: str, request: Request):
    d = _load()
    with _LOCK:
        n = len(d["keys"])
        d["keys"] = [x for x in d["keys"] if x["id"] != kid]
        if len(d["keys"]) == n:
            raise HTTPException(404, "Không có khoá này")
        _save()
    return list_keys(request)


@router.put("")
def set_enabled(req: EnableReq, request: Request):
    with _LOCK:
        _load()["enabled"] = bool(req.enabled)
        _save()
    return list_keys(request)
