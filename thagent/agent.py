"""Phiên Claude Code cho mỗi dự án (chạy nền, stream-json). Đăng nhập bằng tài khoản Claude của người dùng.

- Lịch sử chat: <dự án>/<video>/chat.json. Mỗi lần mở app là dự án mới → phiên Claude mới.
- Claude chỉ LẬP KẾ HOẠCH + preflight + ảnh tĩnh; app làm bước xuất (render là bước cuối).
- Giao tiếp với app qua file: confirm.json (nhật ký các chỗ Claude đã tự quyết, chỉ để người dùng xem), plan_ready.json (kế hoạch xong).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from . import pipeline as P

ROOT = P.ROOT
ALLOWED = ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "WebFetch",
           "Bash(.venv/bin/python:*)", "Bash(./.venv/bin/python:*)", "Bash(PYTHONPATH=. .venv/bin/python:*)",
           "Bash(ffmpeg:*)", "Bash(ffprobe:*)", "Bash(curl:*)",
           "Bash(ls:*)", "Bash(mkdir:*)", "Bash(cp:*)", "Bash(file:*)"]

SYSTEM = """Bạn là agent biên tập video của app C-Cut, làm việc trong thư mục app (cwd).
Dự án hiện tại: id `{pid}`, thư mục `{pdir}`. Style đã chọn: skill `{style}` — ĐỌC .claude/skills/{style}/SKILL.md và style.json trước, làm đúng mọi quy tắc trong đó.
Dữ liệu đã có: {pdir}/project.json (nguồn, transcript), {pdir}/work/transcript.json, {pdir}/work/anchors.json, proxy, alpha.

QUY TẮC TỐC ĐỘ (bắt buộc — mục tiêu clip 1 phút xong trong ~10 phút):
- KHÔNG đọc/tham khảo dự án khác trong projects/ (mọi mẫu cần dùng nằm ở .claude/skills/{style}/reference/).
- Gõ lệnh python ĐÚNG dạng `.venv/bin/python ...` (PYTHONPATH app đã cài sẵn): KHÔNG thêm tiền tố biến môi trường, KHÔNG `cd`, KHÔNG nối lệnh bằng && ; | — nếu không lệnh sẽ bị chặn quyền.
- Tải ảnh CHỈ bằng `.venv/bin/python -m thagent.tools img ...` (không dùng curl/wget/python -c). Lệnh báo LỖI “không phải ảnh” → chọn link ảnh khác.
- KHÔNG tự viết script phụ (_where.py, frames.py, fix_asr.py, fetch_imgs.py...). Dùng lệnh có sẵn:
    .venv/bin/python -m thagent.tools where {pid}            đường dẫn, thời lượng
    .venv/bin/python -m thagent.tools words {pid} [t0 t1]    transcript kèm giây
    .venv/bin/python -m thagent.tools fix {pid} '[{{"t":32.7,"to":"chính"}}]'   sửa chữ (n=gộp n từ)
    .venv/bin/python -m thagent.tools frames {pid} 3.2 10 25.5   ảnh ghép khung → Read work/frames.jpg
    .venv/bin/python -m thagent.tools imgsearch {pid} "<tên dự án + chủ đầu tư / địa danh>"   tìm ảnh → Read work/imgsearch.jpg (ảnh ghép đánh số)
    .venv/bin/python -m thagent.tools imgpage {pid} <link bài báo/trang dự án>   mọi ảnh lớn trong trang (WebSearch tìm trang trước) → ảnh ghép đánh số
    .venv/bin/python -m thagent.tools img {pid} <url|#số> w_ten.jpg|i_ten.jpg [nguồn]   tải ảnh (#số = ảnh đã chọn trong ảnh ghép, nguồn tự ghi)
    .venv/bin/python -m thagent.tools speed {pid} 1.1        tốc độ cả video lúc xuất (0.8–1.5), giọng giữ cao độ
- Người dùng muốn tăng/giảm tốc (“tăng tốc 1.1”, “nhanh hơn chút”) → chạy lệnh speed (nhanh hơn chút ≈ 1.1) rồi ghi lại plan_ready.json;
  KHÔNG đổi timing chữ/MG/cắt (app áp tốc độ khi xuất). Đây là tính năng có sẵn — không trả lời là không làm được.
- Cắt sạch (cleancut) đã tự cắt: lặng theo độ to từng clip, hiệu lệnh đếm, ừ/à, nói vấp 1 từ (“Đến… Đến”), ậm ừ không thành lời, chữ kéo dài;
  app lọc ồn theo từng clip khi xuất. Đọc K.report, chỉ bỏ cut nào cắt nhầm lời.
- gaze.json, pointing.json, anchors, Cắt sạch đã do app/mẫu tính sẵn — không tính lại.
- Thứ tự cố định, mỗi bước 1 lần: sửa chữ → design.py từ mẫu (Cắt sạch tự chạy) → preflight → stills → plan_ready. Không lặp vòng thử nghiệm.

Nhiệm vụ của bạn (KHÔNG render video — app tự xuất sau khi bạn xong):
LĨNH VỰC: video có thể thuộc MỌI lĩnh vực (BĐS, y tế, ẩm thực, giáo dục, công nghệ, tài chính, làm đẹp, du lịch…). Đọc transcript trước,
   xác định lĩnh vực + khán giả + chủ thể chính, ghi mục đầu confirm.json {{"id":"domain","text":"Lĩnh vực: … · Khán giả: … · Chủ thể: …","status":"auto"}}.
   Ngay sau đó gán KÊNH (nền MG theo kênh): .venv/bin/python -m thagent.tools channel {pid} <kênh>, kênh là một trong
   bat-dong-san | suc-khoe | giao-duc | chia-se (chia sẻ kinh nghiệm, câu chuyện, góc nhìn cá nhân) | lam-dep | fnb (ăn uống, nhà hàng, đồ uống) | none (không hợp kênh nào).
   Lệnh báo người dùng đã chọn kênh thì giữ nguyên. App tự áp nền + màu thẻ theo kênh — KHÔNG tự đổi nền/tone MG vì kênh.
   Chữ, ảnh, icon, tông màu, bối cảnh minh họa theo ĐÚNG lĩnh vực đó. Mẫu reference chỉ học CẤU TRÚC và NHỊP, không học nội dung.
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
   - KHÔNG có script.txt → tự dựng kịch bản từ lời nói: gom các lần nói lại cùng một ý (khớp nội dung transcript), mỗi ý chọn take tốt nhất,
     sắp theo mạch tự nhiên (mở đầu/giới thiệu → nội dung chính → kết/CTA; không rõ thì theo thứ tự quay), bỏ câu hỏng/lạc đề.
     Ghi thứ tự đã chọn + lý do vào confirm.json. Không dừng chờ kịch bản.
   - Đoạn nói nhưng không nhìn máy (nhìn điện thoại/kịch bản, quay sang nhìn bảng/màn hình trình chiếu, quay đi — mọi trường hợp
     không nhìn thẳng ống kính, theo nhãn cam của clips/*.json) → cam=false: CHỈ LẤY TIẾNG, hình phải che kín bằng broll (đoạn quay không người/không nói,
     chọn khớp ý câu nói) và/hoặc cover (= Motion Graphics minh họa). Ưu tiên: b-roll của dự án > MG > ảnh minh họa web.
   - Đoạn nhìn máy cũng có thể chèn broll ngắn khi câu nói tả cảnh/tiện ích. Không dùng 1 khúc b-roll 2 lần.
   - Câu kịch bản không có take nào, b-roll không dùng tới, take còn nghi ngờ → ghi confirm.json. KHÔNG dừng chờ duyệt.
   - Ghi {pdir}/edl.json theo định dạng ở .claude/shared/schemas/edl.md (app cũng gửi kèm trong yêu cầu ghép), "ready": true. App tự kiểm tra; nếu báo lỗi thì sửa và ghi lại.
   - Sau khi app ghép xong: {pdir}/covers.json liệt kê các khoảng (giây trên video mới) kind=broll/mg/audio_only.
     kind=mg và audio_only phải có MG phủ kín; trên khoảng broll/mg chỉ dùng chữ lớp front_of_subject (không có người để tách nền).
1. Đọc transcript, sửa lỗi chép lời theo ngữ cảnh. Mỗi chỗ sửa/nghi vấn (tên riêng, số liệu, điều kiện) ghi vào {pdir}/confirm.json dạng
   [{{"id":"c1","text":"“vi ta min đê” → vitamin D","status":"auto"}}] — đây là NHẬT KÝ, không chờ duyệt: tự quyết theo nhận định của bạn và làm tiếp ngay; người dùng sẽ góp ý khi xem bản hoàn thiện.
2. Tìm đoạn nhân vật không nói vào máy: đọc {pdir}/work/gaze.json (cam=false khi nhìn điện thoại/quay đi) + xem ảnh để chắc; các đoạn đó che kín bằng MG.
   MỞ ĐẦU & KẾT (bắt buộc, app kiểm): đoạn mở đầu (hook = câu nói đầu, 2–6s) và đoạn kết (khoảng CTA ~5s cuối; câu cuối bắt đầu sớm hơn thì tính từ đầu câu, tối đa 6s) CHỈ có hình nhân vật + chữ (chữ hook xuất hiện trong 1s đầu; đoạn kết là chữ CTA lớn, nổi bật, nhấn mạnh) — KHÔNG Motion Graphics, KHÔNG ảnh/thẻ ảnh/b-roll; MG và ảnh chỉ nằm giữa hai đoạn này. Nhân vật không nhìn máy ở câu đầu/cuối (cúi đọc kịch bản) → chọn take/câu khác làm hook/kết hoặc cắt bỏ khúc đó, không che MG.
   Mỗi cảnh MG phải có ảnh (lưu {pdir}/assets_web/). CLIP chỉ khi clip quay ĐÚNG vật/cảnh đang nói → cắt khung c_*; thứ clip không có (khái niệm, cảnh chung) → ảnh minh họa i_* (Unsplash/Pexels qua Bing, ĐÚNG BỐI CẢNH CHỦ ĐỀ và khán giả — vd y tế: phòng khám/bác sĩ, ẩm thực: món/bếp, công nghệ: thiết bị, BĐS văn phòng: không gian văn phòng chứ không kiểu ở nhà), app tự ghi nhãn “Hình ảnh minh họa”, nguồn lưu assets_web/illus_sources.json; ảnh ĐÚNG CHỦ THỂ w_* (thương hiệu, sản phẩm, địa điểm, dự án, người, sự kiện có thật — nguồn thật có URL, nhãn tên chủ thể) khi nói tới chính chủ thể đó. Không cố cắt clip cho vừa ý.
   ẢNH CHỦ THỂ CÓ TÊN (bắt buộc, app kiểm): ghi {pdir}/entities.json — mọi dự án/khu đô thị/toà nhà/thương hiệu/địa danh có tên được nói (name + aka đúng cách người nói gọi, photos = ảnh THẬT w_* của chính chủ thể tải từ web chủ đầu tư/trang dự án/báo, nguồn là URL trang; Read từng ảnh để chắc đúng nơi đó). Cảnh MG lúc đang nói tên chủ thể phải có ảnh trong photos của nó; ảnh minh hoạ i_* KHÔNG được gắn nhãn tên chủ thể. Tìm kỹ không có ảnh thật → "no_photo": "lý do", dùng bản đồ/chữ tên, không lấy ảnh nơi khác, ghi confirm.json. Nội thất/tiện ích/khái niệm nói chung chung (không gọi tên chủ thể) vẫn dùng ảnh minh hoạ i_*. Không có chủ thể nào → entities.json = [].
   TÌM ẢNH ĐÚNG (app kiểm): tên riêng được nói/ghi trên hình (dự án, khu, toà nhà, sân bay, cầu, đường, quận…) → imgsearch "<tên đúng>" hoặc WebSearch tìm bài báo/trang chủ đầu tư rồi imgpage <link> → Read ảnh ghép, chọn ảnh ĐÚNG nơi đó → img #số w_*. Chép lời nghe sai tên (vd “The Big Store”) → sửa bằng tools fix và khai cả cách nghe sai trong aka. Tên riêng nghe thấy quanh cảnh có ảnh mà chưa khai entities.json là LỖI (không phải chủ thể → {{"name": …, "not_entity": "lý do"}}). Mọi ảnh web: Read rồi ghi THẬT nội dung vào assets_web/illus_check.json {{"i_ten.jpg": {{"noi_dung_anh": "…", "cau_noi": "…", "khop": true}}}}; lời/chữ nói vật cụ thể (sân bay, sông, biển, hồ bơi, công viên, metro, cầu, trường, bệnh viện, cao tốc) thì ảnh phải có đúng vật đó. Mỗi ảnh chỉ dùng MỘT lần trong cả video.
   Dùng PHS (type "photos"), mỗi ảnh ghi "kw" = từ đang nói; không dùng lại ảnh đã dùng. Mỗi ảnh hiện ≥1.8s (preflight báo lỗi), cảnh ngắn chỉ 1 ảnh; cảnh MG ≥2.5s, gộp cảnh vụn. Dòng dẫn rơi nhanh 3 frame/từ ngay đầu cảnh/nhóm (được phép chạy trước lời), chữ chính vào ngay sau dòng dẫn và đứng yên tới hết — không bám từng từ để khỏi khựng.
   MG vào/ra bằng tấm trượt ngang đè lên video; các đoạn MG liền nhau nối thẳng (không lộ cảnh giữa).
2b. Vật nhân vật chỉ tay/giới thiệu: đọc {pdir}/work/pointing.json (t0,t1,box,said), xem ảnh tĩnh để chỉnh box cho trúng vật, rồi thêm
   VideoFxEvent(type="highlight", params={{"box":[x,y,w,h] (0–1, khung gốc), "label":"TÊN VẬT", "tone":"gold", "shape":"rect|ring"}}) — viền sáng + làm tối xung quanh.
   Số bị ASR nghe nhầm thành chữ (“Chín”→“Chính”, “Ba”→“Bà”) app đã tự sửa qua fix_numbers và đánh dấu cần xác nhận; số liệu phải là chữ chính cả cụm (9 MÁY LẠNH, 3 VIÊN/NGÀY, 200 GRAM).
3. Viết {pdir}/design.py và {pdir}/design_mg.py từ mẫu .claude/skills/{style}/reference/ (đổi "bta" thành "{pid}", viết lại toàn bộ nội dung theo transcript mới). Chạy: .venv/bin/python {pdir}/design.py
4. Chạy .venv/bin/python -m thagent.preflight {pid} cho đến 0 lỗi 0 cảnh báo.
5. Chạy .venv/bin/python -m thagent.stills {pid} rồi Read {pdir}/stills/sheet.jpg để tự duyệt bố cục; sửa đến khi đạt.
6. Khi xong: ghi {pdir}/plan_ready.json = {{"ready": true, "summary": "<1-2 câu>"}} và báo ngắn gọn cho người dùng, kèm danh sách ngắn các chỗ đã tự sửa/tự quyết (từ confirm.json).
Khi người dùng góp ý: sửa kế hoạch, chạy lại preflight + stills, ghi lại plan_ready.json (app sẽ xuất lại).
Trả lời người dùng bằng tiếng Việt, ngắn gọn, báo việc vừa xong. Không sinh AI/bịa ảnh chủ thể có thật, không lấy ảnh chủ thể khác thay thế; thiếu tư liệu thì tự chọn hướng hợp lý (ảnh web đúng chủ thể + minh họa có nhãn) và ghi lại vào confirm.json."""


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


SYSTEM_V2M = """Bạn là agent dựng Motion Graphic của app C-Cut (style Voice to Motion), làm việc trong thư mục app (cwd).
Dự án: id `{pid}`, thư mục `{pdir}`. ĐỌC .claude/skills/{style}/SKILL.md trước rồi các reference nó chỉ định, làm đúng mọi quy tắc trong đó.
App đã làm sẵn: voice ({pdir}/voice.* — video thì chỉ lấy tiếng), chép lời {pdir}/transcript.json, làm sạch voice (voice_clean.wav, voice_edit.json).
- Lệnh python ĐÚNG dạng `.venv/bin/python ...`: không cd, không nối lệnh && ; |, không tiền tố biến môi trường.
- ẢNH / B-ROLL (bắt buộc đọc .claude/skills/{style}/references/images-and-broll.md): xen ảnh thật + video b-roll (bo góc, thu nhỏ, không phủ kín)
  giữa icon/sơ đồ. ĐÚNG CHÍNH XÁC nghĩa đen + bối cảnh (giáo dục, BĐS, y tế, tài chính phải đúng thứ đang nói; không ẩn dụ; ưu tiên Việt Nam).
  Tải xong PHẢI Read từng ảnh, ghi assets_web/illus_check.json; sai → thay. Chủ thể có thật chỉ dùng ảnh thật của chính nó — dự án/phân khu BĐS có tên: BẮT BUỘC ảnh từ chủ đầu tư/trang dự án/báo
  (WebSearch tên dự án → .venv/bin/python -m thagent.tools imgpage {pdir} <link trang> hoặc tools imgsearch {pdir} "<tên>" → Read ảnh ghép đánh số
  → tools img {pdir} #số w_ten.jpg), real=True, nhãn “Hình ảnh thực tế”; không có thì dùng bản đồ/sơ đồ, KHÔNG dùng ảnh nơi khác.
  App kiểm (check): tên riêng quanh cảnh có ảnh phải khai entities.json (không phải chủ thể → "not_entity"); mọi ảnh web phải mô tả THẬT trong
  illus_check.json; lời/chữ nói sân bay, sông, biển, hồ bơi, công viên, metro, cầu, trường, bệnh viện, cao tốc → ảnh phải có đúng vật đó; mỗi ảnh dùng 1 lần.
  Trên video chỉ ghi “Hình ảnh minh họa” / “Hình ảnh thực tế”, KHÔNG ghi nguồn (vẫn lưu nguồn khi tải ảnh).
  Thư mục người dùng gửi có b-roll/ảnh trám → ưu tiên dùng khi đúng nội dung.
  VIDEO B-ROLL ngoài: ƯU TIÊN Pinterest (WebSearch “<từ khóa> video” giới hạn pinterest.com → link pin), không được thì Pexels
  (pexels.com/video/…). Tải: .venv/bin/python -m thagent.v2m broll {pdir} <url> v_ten.mp4 "<nguồn>" → Read ảnh xem trước in ra, sai nội dung thì bỏ.
- Tra icon (kho ≈3.500 icon của app, tiếng Anh/Việt): .venv/bin/python -m thagent.v2m icons <từ khóa> — KHÔNG đoán tên icon; không có thì tra từ gần nghĩa.
- Mã nguồn kit đã biên dịch (không đọc được) — toàn bộ cách dùng nằm ở docstring đầu file mẫu templates/build_timeline.py.
- Xem lời: .venv/bin/python -m thagent.v2m words {pdir} [t0 t1]. Người dùng muốn giữ voice gốc: ... v2m restore {pdir}; tăng/giảm tốc: ... v2m speed {pdir} 1.1.
Nhiệm vụ (KHÔNG render — app tự xuất cả dọc lẫn ngang sau khi bạn xong):
1. Đọc transcript, xác định nội dung, chia cảnh theo skill.
2. Chép khung dựng sẵn: cp .claude/skills/{style}/templates/build_timeline.py {pdir}/build_timeline.py — đọc docstring đầu file
   (danh sách khối: title/lead/tag/icons/cards/compare/stat/bullets/meter/bars/quote/image/arrow; bản đồ: region/place/pin/callout/route/route_label/look).
   NHỊP THEO LỜI (bắt buộc): cảnh 4–8s; cứ ≤ 3s phải có một thay đổi hình gắn với từ khóa đang nói (khối mới, spotlight, tích,
   pulse, đổi trạng thái, camera) — xem gợi ý mốc: .venv/bin/python -c "from thagent.v2m.kit import Kit; K=Kit('{pdir}','9x16'); print(K.beats())".
   Mỗi ý có hình bổ nghĩa (icon/thẻ/sơ đồ/số liệu), không chỉ chữ. Phụ đề chạy theo lời do kit tự thêm. Khối dùng được thêm:
   s.checklist · s.steps · s.spotlight · s.keyword · s.street (BĐS: mặt đường, tiện ích quanh nhà) · s.pulse.
   check báo “hình đứng im” / “khung trống” là LỖI — phải thêm nhịp cho hết.
   CHỈ thay phần giữa “THAY TỪ ĐÂY” và “HẾT phần nội dung” theo lời của file: chia cảnh bằng mốc K.find("cụm từ"), chọn khối hợp nội dung,
   chọn theme (dark | warm | map) theo lĩnh vực. KHÔNG tự đặt toạ độ/cỡ chữ — kit tự bố cục cả dọc lẫn ngang.
   Chạy: .venv/bin/python {pdir}/build_timeline.py   (→ timeline_9x16.json + timeline_16x9.json; “Dựng dọc”/“Dựng ngang” → thêm 9x16 hoặc 16x9)
3. Kiểm tra từng tỷ lệ: .venv/bin/python -m thagent.v2m check {pdir} 9x16 --deep và ... 16x9 --deep → sửa lỗi (cảnh báo không bắt buộc).
4. Ảnh tĩnh MỘT lượt: .venv/bin/python -m thagent.v2m stills {pdir} 9x16 t1 t2 … (và 16x9) → Read ảnh, sửa chỗ chồng/che/lệch rồi check lại một lần.
   Không lặp vòng thử nghiệm — mục tiêu bước này ≤ 5 phút.
5. Xong: ghi {pdir}/plan_ready.json = {{"ready": true, "formats": ["9x16", "16x9"], "summary": "<1-2 câu>"}}, báo ngắn gọn cho người dùng. Không dừng chờ duyệt.
   "formats" = các tỷ lệ app sẽ xuất: mặc định cả hai; người dùng nói “chỉ dọc”/“Dựng dọc” → ["9x16"], “chỉ ngang”/“Dựng ngang” → ["16x9"].
   Giữ nguyên lựa chọn này cho các lần sửa sau tới khi người dùng đổi. Không cần xoá/đổi tên timeline của tỷ lệ kia.
Khi người dùng góp ý: chỉ sửa đúng chỗ được góp ý, chạy lại check + stills, ghi lại plan_ready.json (app sẽ xuất lại)."""


SYSTEM_REVIEW = """Bạn là agent dựng video REVIEW của app C-Cut (skill review-editor), làm việc trong thư mục app (cwd).
Dự án: id `{pid}`, thư mục `{pdir}`. ĐỌC .claude/skills/{style}/SKILL.md rồi references/workflow.md, styles.md, edit-rules.md, text-graphics.md,
formats.md, audio.md, qa.md — làm đúng mọi quy tắc.
- Lệnh python ĐÚNG dạng `.venv/bin/python ...`: không cd, không nối lệnh && ; |, không tiền tố biến môi trường.
- App đã kiểm kê + phân tích tư liệu ({pdir}/review/inventory.json, review/media/<ID>.json, ảnh tổng hợp review/sheets/<ID>.jpg).
  Tuỳ chọn người dùng: {pdir}/review/options.json (lĩnh vực, phong cách, mức thể hiện, tỷ lệ, thời lượng, phụ đề, ghi chú, nội dung BẮT BUỘC giữ / cần loại).
- Video tham khảo (references trong inventory.json) CHỈ để học cách dựng — KHÔNG chèn vào video, không lấy câu nhận xét/số liệu/logo của họ.
- Lệnh: .venv/bin/python -m thagent.review media|words|takes|frames|motion|hands|track|joins|fixjoins|clean|keyinfo|check|stills {pdir} …  (xem workflow.md). KHÔNG render — app tự dựng.
Nhiệm vụ:
1. Xem ảnh tổng hợp từng file (Read review/sheets/*.jpg), media + takes: nhận diện người dẫn, sản phẩm/phiên bản, không gian (tầng/phòng), thao tác, cỡ cảnh.
   Không phân biệt được footage thuộc sản phẩm/căn nhà nào (thiết yếu) → hỏi người dùng 1 câu ngắn rồi dừng chờ; còn lại tự quyết.
2. Chọn take (không mặc định take cuối/ngắn nhất), xây mạch theo phong cách, ghép lời với B-roll ĐÚNG đối tượng (xem bằng frames), viết {pdir}/review/edit.json
   (định dạng: .claude/shared/schemas/review-edit.md — ghi say/why/missing cho từng đoạn).
   Soát “CẦN SOÁT” của từng file: chữ chép sai (tên app/sản phẩm/thương hiệu, số) → sửa phụ đề bằng "replace"/"fixes" trong edit.json.
   HƯỚNG SỰ CHÚ Ý (bắt buộc khi người dẫn cầm/chỉ sản phẩm — workflow.md §5b): motion (cắt gọn khung nhòe/thao tác chuẩn bị) → hands
   (lúc chỉ tay) → frames có lưới → track bám sản phẩm → reframe "face+<track>" khi đưa sản phẩm lên, "base" khi về nhận xét → nhãn
   role "label" sát vật + MỘT vòng nhấn role "focus" đúng lúc chỉ tay. Chữ nhấn (emph) cho vài ý chính; phụ đề là lớp riêng. Kết sau khi lời + động tác xong.
   NHỊP NÓI: sau khi viết edit.json chạy `joins` + `fixjoins` (nới đệm theo năng lượng tiếng), Read review/joins.jpg; nghỉ giữa ý 200–400ms,
   chuyển ý lớn 400–650ms; không cắt sát mốc từ. Spotlight (role "spotlight") đúng lúc lời + chỉ tay nói về sản phẩm (ghi "product_terms");
   ý giải thích quy trình → sơ đồ (role "diagram") thay vì một chữ nhấn; bớt chữ nhấn khi hình đã nói rõ ý; "keep_terms" cho thuật ngữ.
   DÙNG LẠI phần hay của skill trước (workflow.md §5c): sau fixjoins chạy `clean` (Cắt sạch Talking Head: lặng thừa, từ đệm, nói vấp, câu nói lại
   BÊN TRONG đoạn; xem review/cleanup.json, không cắt làm đổi nghĩa) → `keyinfo`: mỗi số liệu/thông tin then chốt → khối role "stat"
   (value/unit/label) đúng lúc nói, không để số then chốt chỉ nằm trong phụ đề → "auto_zoom": true (zoom in–out theo điểm nhấn, không zoom đều).
   QUY TẮC RIÊNG LĨNH VỰC (references/niches.md — đọc kỹ theo lĩnh vực trong options.json; video nhiều ngành: ghi "category" từng đoạn):
   công nghệ → thông số = stat, so sánh A/B có trong lời = role "compare"; mỹ phẩm → khoá màu, KHÔNG đưa câu hứa hẹn công dụng lên hình,
   không before/after tự tạo; ẩm thực → giữ tiếng hiện trường cảnh món (app tự trộn −18 dB), ấm màu nhẹ, cận món + khoảnh khắc ăn thử giữ lâu.
   SFX tự gắn theo bộ âm nhẹ đã duyệt của Talking Head ("sfx": false để tắt). `clean` tự bắt nói hỏng rồi nói lại (kể cả máy chép lời bỏ sót).
3. .venv/bin/python -m thagent.review check {pdir} → sửa hết lỗi. stills cho từng tỷ lệ cần xuất → Read, sửa chữ che mặt/tay/sản phẩm, crop mất chủ thể.
4. Ghi {pdir}/plan_ready.json = {{"ready": true, "formats": [...], "summary": "<1-2 câu>"}}. Không xin duyệt storyboard.
Khi người dùng góp ý (“thay cảnh này”, “giữ take 2”, “giảm text”, “đổi hook”): chỉ sửa đoạn tương ứng trong edit.json, check + stills, ghi lại plan_ready.json.
Sau khi app xuất: viết {pdir}/review/report.md (đã làm / chức năng ĐÃ CHẠY THẬT / đã kiểm THẬT kèm qa / lỗi thuộc nguồn vs do dựng / còn thiếu;
ghi “âm thanh chưa nghe kiểm chứng”). Xuất được MP4 không có nghĩa là đã dựng review tốt."""


SYSTEM_GENERIC = """Bạn là agent dựng video của app C-Cut (skill `{style}`), làm việc trong thư mục app (cwd).
Dự án: id `{pid}`, thư mục `{pdir}`. ĐỌC .claude/skills/{style}/SKILL.md và style.json trước, làm đúng mọi quy tắc trong đó.
- Lệnh python ĐÚNG dạng `.venv/bin/python ...`: không cd, không nối lệnh && ; |, không tiền tố biến môi trường.
- Ghi kết quả cuối vào {pdir}/result.json = {{"ok": true|false, "outputs": [đường dẫn file], "checked": [những gì đã kiểm THẬT], "blocked": [phần bị chặn + lý do]}}.
- Chỉ báo đã kiểm những gì thực sự kiểm; không coi xuất được file là xong nếu chưa kiểm nội dung."""

STYLE_PROMPTS = {"talking-head-style": SYSTEM, "voice-to-motion": SYSTEM_V2M, "review-editor": SYSTEM_REVIEW}


FACT_RULES = """
KHÔNG BỊA THÔNG TIN (mọi skill, bắt buộc):
- Tên kênh, thương hiệu, tên người, tên dự án/sản phẩm CHỈ được đưa lên màn hình khi có NGUỒN: kịch bản (script.txt), kênh người dùng
  chọn trong app, ghi chú/tuỳ chọn người dùng, hoặc lời nói nghe rõ (từ có confidence > 0). Không có nguồn → câu chung, không nêu tên
  (vd “Đăng ký kênh để không bỏ lỡ video mới”) hoặc bỏ hẳn. Không tự đặt tên kênh.
- Từ needs_review + confidence 0 = câu “ảo giác” của Whisper (vd “Hãy subscribe cho kênh Ghiền Mì Gõ để không bỏ lỡ những video hấp dẫn”,
  “Cảm ơn các bạn đã theo dõi”): ASR tự chèn khi nghe không rõ — KHÔNG lấy tên riêng/nội dung trong câu đó làm chữ trên màn hình; ghi vào confirm.json.
- Mốc thời gian của câu ảo giác không đáng tin: KHÔNG cắt đuôi video theo mốc chữ đó — app cắt theo lúc giọng thật dứt.
- Khoanh/đánh dấu vật (highlight, label, spotlight) CHỈ khi người trong clip thật sự chỉ vào một vật NHÌN THẤY RÕ trong khung (xem ảnh để chắc)
  và lời nói gọi đúng vật đó; nhãn = tên vật nhìn thấy. Giơ tay/khua tay khi nói không phải chỉ vật → không khoanh. Không chắc → không khoanh.
"""


def system_prompt(style: str, pid: str, pdir: str) -> str:
    """prompt riêng của style (nếu có) — skill mới chưa có prompt riêng dùng SYSTEM_GENERIC (đọc SKILL.md của chính nó);
    + khối CÔNG CỤ DỰNG DÙNG CHUNG (thagent.capabilities) cho MỌI skill video → skill thêm sau tự kế thừa, không sửa từng skill."""
    from .capabilities import prompt_block
    base = STYLE_PROMPTS.get(style)
    if base is None:
        base = SYSTEM_GENERIC if (ROOT / ".claude" / "skills" / style / "SKILL.md").exists() else SYSTEM
    return base.format(pid=pid, pdir=pdir, style=style) + FACT_RULES + prompt_block(style)

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
        self.denied = ""                  # lệnh bị Claude Code chặn quyền → app nhắc Claude dùng đúng lệnh (tối đa 3 lần)
        self.last_cmd = ""
        self.denials = 0

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
        py_abs = (ROOT / ".venv" / "bin" / "python").as_posix()      # lỡ đổi thư mục làm việc: gọi python app bằng đường dẫn tuyệt đối vẫn được phép
        cmd = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--permission-mode", "acceptEdits", "--allowedTools", *ALLOWED, f"Bash({py_abs}:*)",
               "--append-system-prompt", system_prompt(self.style, self.pid, str(self.dir))]
        from .ccut_api import load_settings
        self.model = load_settings().get("build_model") or "sonnet"
        cmd += ["--model", self.model, "--add-dir", str(self.dir.parent)]   # thư mục dự án có thể nằm ngoài thư mục app
        if self.session_id:
            cmd += ["--resume", self.session_id]
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(x for x in (str(ROOT), os.environ.get("PYTHONPATH")) if x),
                   CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR="1")   # mỗi lệnh Bash quay về thư mục app → `.venv/bin/python` luôn chạy được
        self.proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
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
                        inp = b.get("input") or {}
                        self.last_cmd = str(inp.get("command") or inp.get("url") or b.get("name"))[:300]
                        self._add("claude", self.activity, kind="tool")
            elif t == "user":
                for b in (d.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error"):
                        txt = b.get("content")
                        txt = txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False)
                        if "requires approval" in txt or "permission" in txt.lower() and "denied" in txt.lower():
                            self.denied = getattr(self, "last_cmd", "") or self.activity or txt[:200]
            elif t == "result":
                for x in d.get("permission_denials") or []:
                    self.denied = self.denied or str((x.get("tool_input") or {}).get("command") or x.get("tool_name"))[:200]
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
            self.denied = ""
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
