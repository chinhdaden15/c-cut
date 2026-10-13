"""Phiên Claude Code cho mỗi dự án (chạy nền, stream-json). Đăng nhập bằng tài khoản Claude của người dùng.

- Lịch sử chat: <dự án>/<video>/chat.json. Mỗi lần mở app là dự án mới → phiên Claude mới.
- Claude chỉ LẬP KẾ HOẠCH + preflight + ảnh tĩnh; app làm bước xuất (render là bước cuối).
- Giao tiếp với app qua file: confirm.json (nhật ký các chỗ Claude đã tự quyết, chỉ để người dùng xem), plan_ready.json (kế hoạch xong).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import pipeline as P

ROOT = P.ROOT
ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch",
           "Bash(.venv/bin/python:*)", "Bash(ffmpeg:*)", "Bash(ffprobe:*)", "Bash(curl:*)",
           "Bash(ls:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(file:*)"]

SYSTEM = """Bạn là agent biên tập video của app C-Cut, làm việc trong thư mục app (cwd).
Dự án hiện tại: id `{pid}`, thư mục `{pdir}`. Style đã chọn: skill `{style}` — ĐỌC .claude/skills/{style}/SKILL.md và style.json trước, làm đúng mọi quy tắc trong đó.
Dữ liệu đã có: {pdir}/project.json (nguồn, transcript), {pdir}/work/transcript.json, {pdir}/work/anchors.json, proxy, alpha.

QUY TẮC TỐC ĐỘ (bắt buộc — mục tiêu clip 1 phút xong trong ~10 phút):
- KHÔNG đọc/tham khảo dự án khác trong projects/ (mọi mẫu cần dùng nằm ở .claude/skills/{style}/reference/).
- KHÔNG tự viết script phụ (_where.py, frames.py, fix_asr.py, fetch_imgs.py...). Dùng lệnh có sẵn:
    PYTHONPATH=. .venv/bin/python -m thagent.tools where {pid}            đường dẫn, thời lượng
    PYTHONPATH=. .venv/bin/python -m thagent.tools words {pid} [t0 t1]    transcript kèm giây
    PYTHONPATH=. .venv/bin/python -m thagent.tools fix {pid} '[{{"t":32.7,"to":"chính"}}]'   sửa chữ (n=gộp n từ)
    PYTHONPATH=. .venv/bin/python -m thagent.tools frames {pid} 3.2 10 25.5   ảnh ghép khung → Read work/frames.jpg
    PYTHONPATH=. .venv/bin/python -m thagent.tools img {pid} <url> i_ten.jpg [nguồn]   tải ảnh minh họa
- gaze.json, pointing.json, anchors, Cắt sạch đã do app/mẫu tính sẵn — không tính lại.
- Thứ tự cố định, mỗi bước 1 lần: sửa chữ → design.py từ mẫu (Cắt sạch tự chạy) → preflight → stills → plan_ready. Không lặp vòng thử nghiệm.

Nhiệm vụ của bạn (KHÔNG render video — app tự xuất sau khi bạn xong):
0. ĐỐI CHIẾU KỊCH BẢN (bắt buộc với mọi style): nếu có {pdir}/script.txt thì gióng từng câu transcript với kịch bản.
   - Kịch bản là nguồn chuẩn cho chính tả, tên riêng, số liệu, đơn vị → sửa transcript theo kịch bản, giữ nguyên timestamp từng từ.
   - Nhân vật nói KHÁC kịch bản (thêm/bớt/đổi ý, nói sai số) → tự chọn phương án hợp lý nhất theo ngữ cảnh (số liệu ưu tiên kịch bản), ghi lại vào confirm.json.
   - Đoạn kịch bản bị bỏ không nói, đoạn nói ngoài kịch bản, câu nói lặp/nói vấp → tự quyết cắt/giữ, ghi lại vào confirm.json.
   - Chữ trên màn hình (lead/main/MG) lấy đúng chính tả theo kịch bản. Ghi tóm tắt vào {pdir}/script_check.json
     {{"match_pct": .., "fixed": [..], "diffs": [..], "missing": [..], "extra": [..]}}.
   Không có script.txt → bỏ qua bước này, sửa theo ngữ cảnh như bước 1.
GHÉP NHIỀU ĐOẠN (chỉ khi app yêu cầu viết edl.json — dự án gồm nhiều file quay của 1 video):
   - Đọc {pdir}/clips/index.json (loại đoán: talk/mixed/broll, khoảng nói + tỉ lệ nhìn máy, khoảng lặng có/không người),
     Read ảnh {pdir}/clips/*_sheet.jpg (nhãn cam=nhìn máy, mat=có mặt nhưng không nhìn máy, -=không người), chi tiết từng từ ở clips/<đoạn>.json.
   - Đi theo thứ tự kịch bản; mỗi câu chọn TAKE TỐT NHẤT (nói đủ, không vấp, nhìn máy, thường là take sau cùng). in/out cắt sát từ đầu/cuối (đệm ~0.1s).
   - Đoạn nói nhưng không nhìn máy (nhìn điện thoại/kịch bản, quay sang nhìn bảng/màn hình trình chiếu, quay đi — mọi trường hợp
     không nhìn thẳng ống kính, theo nhãn cam của clips/*.json) → cam=false: CHỈ LẤY TIẾNG, hình phải che kín bằng broll (đoạn quay không người/không nói,
     chọn khớp ý câu nói) và/hoặc cover (= Motion Graphics minh họa). Ưu tiên: b-roll của dự án > MG > ảnh minh họa web.
   - Đoạn nhìn máy cũng có thể chèn broll ngắn khi câu nói tả cảnh/tiện ích. Không dùng 1 khúc b-roll 2 lần.
   - Câu kịch bản không có take nào, b-roll không dùng tới, take còn nghi ngờ → ghi confirm.json. KHÔNG dừng chờ duyệt.
   - Ghi {pdir}/edl.json theo schema ở đầu thagent/clips.py, "ready": true. App tự kiểm tra; nếu báo lỗi thì sửa và ghi lại.
   - Sau khi app ghép xong: {pdir}/covers.json liệt kê các khoảng (giây trên video mới) kind=broll/mg/audio_only.
     kind=mg và audio_only phải có MG phủ kín; trên khoảng broll/mg chỉ dùng chữ lớp front_of_subject (không có người để tách nền).
1. Đọc transcript, sửa lỗi chép lời theo ngữ cảnh. Mỗi chỗ sửa/nghi vấn (tên riêng, số liệu, điều kiện) ghi vào {pdir}/confirm.json dạng
   [{{"id":"c1","text":"“Đời Global City” → The Global City","status":"auto"}}] — đây là NHẬT KÝ, không chờ duyệt: tự quyết theo nhận định của bạn và làm tiếp ngay; người dùng sẽ góp ý khi xem bản hoàn thiện.
2. Tìm đoạn nhân vật không nói vào máy: đọc {pdir}/work/gaze.json (cam=false khi nhìn điện thoại/quay đi) + xem ảnh để chắc; các đoạn đó che kín bằng MG.
   Mỗi cảnh MG phải có ảnh (lưu {pdir}/assets_web/). CLIP chỉ khi clip quay ĐÚNG vật đang nói (thang máy, máy lạnh, điện smart home, chữa cháy) → cắt khung c_*; nội thất/chung chung clip không có (phòng làm việc, WC, phòng họp, tiếp khách, trường, TTTM) → ảnh minh họa i_* (Unsplash/Pexels qua Bing, đúng bối cảnh VĂN PHÒNG chứ không kiểu ở nhà), app tự ghi nhãn “Hình ảnh minh họa”, nguồn lưu assets_web/illus_sources.json; ảnh ĐÚNG dự án w_* chỉ khi nói bên ngoài/toàn cảnh/bản đồ. Không cố cắt clip cho vừa ý.
   Dùng PHS (type "photos"), mỗi ảnh ghi "kw" = từ đang nói; không dùng lại cùng ảnh trong 30s. Mỗi ảnh hiện ≥1.8s (preflight báo lỗi), cảnh ngắn chỉ 1 ảnh; cảnh MG ≥2.5s, gộp cảnh vụn. Dòng dẫn rơi nhanh 3 frame/từ ngay đầu cảnh/nhóm (được phép chạy trước lời), chữ chính vào ngay sau dòng dẫn và đứng yên tới hết — không bám từng từ để khỏi khựng.
   MG vào/ra bằng tấm trượt ngang đè lên video; các đoạn MG liền nhau nối thẳng (không lộ cảnh giữa).
2b. Vật nhân vật chỉ tay/giới thiệu: đọc {pdir}/work/pointing.json (t0,t1,box,said), xem ảnh tĩnh để chỉnh box cho trúng vật, rồi thêm
   VideoFxEvent(type="highlight", params={{"box":[x,y,w,h] (0–1, khung gốc), "label":"THANG MÁY", "tone":"gold", "shape":"rect|ring"}}) — viền sáng + làm tối xung quanh.
   Số bị ASR nghe nhầm thành chữ (“Chín”→“Chính máy lạnh”) app đã tự sửa qua fix_numbers và đánh dấu cần xác nhận; số liệu phải là chữ chính cả cụm (9 MÁY LẠNH).
3. Viết {pdir}/design.py và {pdir}/design_mg.py từ mẫu .claude/skills/{style}/reference/ (đổi "bta" thành "{pid}", viết lại toàn bộ nội dung theo transcript mới). Chạy: .venv/bin/python {pdir}/design.py (PYTHONPATH=. qua lệnh: PYTHONPATH=. .venv/bin/python ...).
4. Chạy .venv/bin/python -m thagent.preflight {pid} cho đến 0 lỗi 0 cảnh báo.
5. Chạy .venv/bin/python -m thagent.stills {pid} rồi Read {pdir}/stills/sheet.jpg để tự duyệt bố cục; sửa đến khi đạt.
6. Khi xong: ghi {pdir}/plan_ready.json = {{"ready": true, "summary": "<1-2 câu>"}} và báo ngắn gọn cho người dùng, kèm danh sách ngắn các chỗ đã tự sửa/tự quyết (từ confirm.json).
Khi người dùng góp ý: sửa kế hoạch, chạy lại preflight + stills, ghi lại plan_ready.json (app sẽ xuất lại).
Trả lời người dùng bằng tiếng Việt, ngắn gọn, báo việc vừa xong. Không bịa ảnh dự án; thiếu tư liệu thì tự chọn hướng hợp lý (ảnh web dự án + minh họa có nhãn) và ghi lại vào confirm.json."""


STATUS_FILE = ROOT / "claude_status.json"   # model đang dùng + giới hạn tài khoản (5 giờ / 7 ngày)


def _save_status(**kw):
    st = claude_status()
    st.update({k: v for k, v in kw.items() if v})
    if kw.get("limits"):
        st["limits_at"] = time.time()
    STATUS_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def claude_status() -> dict:
    try:
        return json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


LIMITS = {"running": False}


def refresh_limits() -> bool:
    """1 lượt Haiku rất ngắn để đọc giới hạn 5 giờ / 7 ngày (rate_limit_event), ~5s. Đồng thời là phép thử Claude chạy được."""
    exe = shutil.which("claude")
    if not exe:
        _set_health("Chưa cài Claude Code — xem ⚙ › Công cụ")
        return False
    if LIMITS["running"]:
        return False
    LIMITS["running"] = True
    err = "Không gọi được Claude"
    try:
        r = subprocess.run([exe, "-p", "ok", "--model", "haiku", "--output-format", "stream-json", "--verbose",
                            "--max-turns", "1", "--tools", ""], cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60, stdin=subprocess.DEVNULL,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in r.stdout.splitlines():
            if '"rate_limit_event"' in line:
                _save_status(limits=json.loads(line).get("rate_limit_info"))
                _set_health(None)
                return True
        err = (r.stderr.strip() or r.stdout.strip())[-200:] or err
        if "login" in err.lower() or "auth" in err.lower():
            err = "Claude chưa đăng nhập — mở ⚙ › Công cụ để đăng nhập"
    except Exception as e:
        err = f"Không gọi được Claude: {e}"[:200]
    finally:
        LIMITS["running"] = False
    _set_health(err)
    return False


def _set_health(err):
    st = claude_status()
    st["error"], st["checked_at"] = err, time.time()
    STATUS_FILE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def limits_loop(every=300):
    """khi mở app làm mới ngay, sau đó mỗi 5 phút — trừ khi Claude đang làm (lúc đó số liệu đến kèm từng lượt trả lời)."""
    def run():
        while True:
            if not any(s.busy for s in SESSIONS.values()):
                refresh_limits()
            time.sleep(every)
    threading.Thread(target=run, daemon=True).start()


class Session:
    def __init__(self, pid: str, style: str):
        self.pid, self.style = pid, style
        self.dir = P.PROJECTS / pid
        self.chat_file = self.dir / "chat.json"
        data = json.loads(self.chat_file.read_text(encoding="utf-8")) if self.chat_file.exists() else {}
        self.messages: list[dict] = data.get("messages", [])
        self.session_id: str | None = data.get("session_id")
        self.proc: subprocess.Popen | None = None
        self.busy = False
        self.activity = ""
        self.lock = threading.Lock()
        self.model = ""
        self.last_evt = time.time()       # lần cuối Claude gửi gì đó (để phát hiện treo)
        self.err_tail = ""
        self.restarts = 0

    # ---------- lưu ----------
    def _save(self):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.chat_file.write_text(json.dumps({"session_id": self.session_id, "messages": self.messages[-400:]},
                                             ensure_ascii=False, indent=1), encoding="utf-8")

    def _add(self, role: str, text: str, kind: str = "text"):
        self.messages.append({"t": time.time(), "role": role, "kind": kind, "text": text})
        self._save()

    # ---------- tiến trình claude ----------
    def _start(self):
        exe = shutil.which("claude")
        if not exe:
            raise RuntimeError("Chưa cài Claude Code — xem Cài đặt › Công cụ")
        cmd = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED,
               "--append-system-prompt", SYSTEM.format(pid=self.pid, pdir=str(self.dir), style=self.style)]
        from .ccut_api import load_settings
        self.model = load_settings().get("build_model") or "sonnet"
        cmd += ["--model", self.model, "--add-dir", str(self.dir.parent)]   # thư mục dự án có thể nằm ngoài thư mục app
        if self.session_id:
            cmd += ["--resume", self.session_id]
        self.proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.last_evt = time.time()
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._err_reader, args=(self.proc,), daemon=True).start()

    def _err_reader(self, proc):
        # đọc stderr liên tục: để nguyên thì bộ đệm đầy → Claude đứng chờ (treo ở bước Kế hoạch trên Windows)
        for line in proc.stderr:
            self.err_tail = (self.err_tail + line)[-2000:]

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def working_child(self) -> bool:
        """Claude đang chạy một lệnh (preflight, ảnh tĩnh…) → im lặng là bình thường."""
        try:
            import psutil
            return bool(self.alive() and psutil.Process(self.proc.pid).children(recursive=True))
        except Exception:
            return False

    def watchdog(self, limit=180) -> bool:
        """Im quá `limit` giây mà không chạy lệnh nào → báo + khởi động lại, tiếp tục việc dở. True nếu đã khởi động lại."""
        if not self.busy or time.time() - self.last_evt < limit or self.working_child():
            return False
        self.restarts += 1
        self._add("claude", f"Claude không phản hồi {limit // 60} phút — app tự khởi động lại Claude (lần {self.restarts})."
                  + (f" Lỗi: {self.err_tail.strip()[-200:]}" if self.err_tail.strip() else ""), kind="error")
        self.stop()
        time.sleep(1)
        self.send("Phiên trước bị gián đoạn. Tiếp tục đúng việc đang dở theo quy trình (xem file trong thư mục dự án), "
                  "xong thì ghi plan_ready.json.", show=False)
        return True

    def _reader(self, proc):
        for line in proc.stdout:
            self.last_evt = time.time()
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("type")
            if t == "system" and d.get("subtype") == "init":
                self.session_id = d.get("session_id") or self.session_id
                self._save()
                self.model = d.get("model") or self.model
                _save_status(model=d.get("model"))
            elif t == "rate_limit_event":
                _save_status(limits=d.get("rate_limit_info"))
            elif t == "assistant":
                for b in d["message"]["content"]:
                    if b.get("type") == "text" and b["text"].strip():
                        self._add("claude", b["text"].strip())
                    elif b.get("type") == "tool_use":
                        self.activity = _describe(b)
                        self._add("claude", self.activity, kind="tool")
            elif t == "result":
                self.busy = False
                self.activity = ""
                if d.get("is_error"):
                    self._add("claude", f"Lỗi phiên Claude: {d.get('result') or d.get('subtype')}", kind="error")
        proc.wait()
        if self.proc is proc:
            self.busy = False
            self.activity = ""
            if proc.returncode not in (0, None) and not getattr(proc, "_stopped", False):
                self._add("claude", "Claude dừng bất thường" + (": " + self.err_tail.strip()[-300:] if self.err_tail.strip() else
                          f" (mã {proc.returncode})"), kind="error")
            self.proc = None

    def send(self, text: str, show: bool = True):
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                self._start()
            if show:
                self._add("user", text)
            self.busy = True
            self.last_evt = time.time()
            msg = {"type": "user", "message": {"role": "user", "content": text}}
            self.proc.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()

    def stop(self):
        p = self.proc
        if p and p.poll() is None:
            p._stopped = True
            try:     # dừng cả cây (claude + lệnh nó đang chạy), không đụng tới cửa sổ app
                import psutil
                for ch in psutil.Process(p.pid).children(recursive=True):
                    ch.kill()
            except Exception:
                pass
            p.kill()
        self.proc = None
        self.busy = False
        self.activity = ""

    def warm(self):
        """mở sẵn tiến trình Claude (chưa giao việc) để vào bước Kế hoạch là chạy ngay."""
        with self.lock:
            if not self.alive():
                self._start()

    # ---------- file giao tiếp ----------
    def confirms(self) -> list[dict]:
        f = self.dir / "confirm.json"
        try:
            return [c for c in json.loads(f.read_text(encoding="utf-8")) if c.get("status", "open") == "open"]
        except Exception:
            return []

    def set_confirm(self, cid: str, status: str):
        f = self.dir / "confirm.json"
        try:
            items = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return
        for c in items:
            if c.get("id") == cid:
                c["status"] = status
        f.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

    def plan_ready(self) -> dict | None:
        f = self.dir / "plan_ready.json"
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            return d if d.get("ready") else None
        except Exception:
            return None


def _describe(b: dict) -> str:
    name, inp = b.get("name", ""), b.get("input", {}) or {}
    if name == "Bash":
        c = inp.get("command", "")
        for key, lab in (("preflight", "Đang kiểm tra kế hoạch (preflight)"), ("thagent.stills", "Đang tạo ảnh tĩnh để duyệt"),
                         ("design", "Đang dựng kế hoạch chữ / graphic"), ("curl", "Đang tải tư liệu"), ("ffmpeg", "Đang xử lý media")):
            if key in c:
                return lab
        return "Đang chạy lệnh"
    return {"Read": "Đang đọc " + Path(inp.get("file_path", "")).name, "Write": "Đang viết " + Path(inp.get("file_path", "")).name,
            "Edit": "Đang sửa " + Path(inp.get("file_path", "")).name, "WebSearch": "Đang tìm: " + inp.get("query", ""),
            "WebFetch": "Đang đọc trang web", "Glob": "Đang tìm file", "Grep": "Đang tìm trong file"}.get(name, name)


SESSIONS: dict[str, Session] = {}


def stop_all():
    for s in SESSIONS.values():
        s.stop()


def reset_all():
    stop_all()
    SESSIONS.clear()


def get(pid: str, style: str) -> Session:
    if pid not in SESSIONS:
        SESSIONS[pid] = Session(pid, style)
    return SESSIONS[pid]
