"""Lệnh có sẵn cho Claude khi lập kế hoạch — dùng thay vì tự viết script phụ.
  python -m thagent.tools where  <pid>                         đường dẫn + thời lượng + số từ
  python -m thagent.tools words  <pid> [t0 t1]                 transcript kèm giây (lọc khoảng)
  python -m thagent.tools fix    <pid> '<json>'                sửa chữ: [{"t":32.73,"to":"chính"}, {"t":40.1,"to":"insulin","n":2}]
                                                               (từ gần giây t nhất; n = gộp n từ liên tiếp thành 1)
  python -m thagent.tools frames <pid> t1 t2 ...               ảnh ghép các khung ở giây nguồn → work/frames.jpg (Read để xem)
  python -m thagent.tools img    <pid> <url> <tên_file> [nguồn] tải ảnh vào assets_web/, ghi nguồn vào illus_sources.json
  python -m thagent.tools speed  <pid> 1.1                     tốc độ cả video lúc xuất (0.8–1.5; 1 = gốc), giọng giữ cao độ
"""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request

from . import pipeline as P


def where(pid):
    c = P.Ctx(pid)
    print(json.dumps({"pdir": str(c.path()), "proxy": c.project.proxy, "duration": c.project.source.duration,
                      "words": len(c.project.words), "alpha": str(c.path("work", "alpha.mp4"))}, ensure_ascii=False))


def words(pid, t0=0, t1=1e9):
    c = P.Ctx(pid)
    print(" ".join(f"{w.text}@{w.source_start:.2f}" for w in c.project.words if float(t0) <= w.source_start <= float(t1)))


def fix(pid, spec):
    c = P.Ctx(pid)
    W = c.project.words
    for f in json.loads(spec):
        i = min(range(len(W)), key=lambda k: abs(W[k].source_start - f["t"]))
        n = int(f.get("n", 1))
        old = " ".join(w.text for w in W[i:i + n])
        W[i].text = f["to"]
        if n > 1:
            W[i].source_end = W[i + n - 1].source_end
            del W[i + 1:i + n]
        print(f"{W[i].source_start:.2f}: “{old}” → “{f['to']}”")
    for s in c.project.sentences:          # câu lấy lại chữ từ các từ đã sửa
        ws = [w for w in W if s.source_start - 0.01 <= w.source_start < s.source_end]
        if ws:
            s.text = " ".join(w.text for w in ws)
    tj = c.path("work", "transcript.json")
    d = json.loads(tj.read_text(encoding="utf-8"))
    d["words"] = [w.model_dump() for w in W]
    tj.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    c.save()


def frames(pid, *ts):
    c = P.Ctx(pid)
    out = c.path("work", "frames.jpg")
    ins, fl = [], []
    for k, t in enumerate(ts):
        ins += ["-ss", str(t), "-i", c.project.proxy]
        fl.append(f"[{k}:v]trim=end_frame=1,scale=270:-2[f{k}]")
    n = len(ts)
    cols = min(n, 6)
    rows = (n + cols - 1) // cols
    lay = "|".join(f"{(k % cols) * 270}_{(k // cols) * 480}" for k in range(n))
    fc = ";".join(fl) + ";" + "".join(f"[f{k}]" for k in range(n)) + (
        f"xstack=inputs={n}:layout={lay}:fill=black[o]" if n > 1 else "null[o]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[o]", "-frames:v", "1", str(out)],
                   check=True)
    print(out, f"({cols}x{rows}, mỗi ô 270px, trái→phải, trên→dưới: " + ", ".join(f"{float(t):.1f}s" for t in ts) + ")")


def img(pid, url, name, source=""):
    c = P.Ctx(pid)
    d = c.path("assets_web")
    d.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    (d / name).write_bytes(urllib.request.urlopen(req, timeout=30).read())
    from . import imgio
    im = imgio.imread(d / name)
    if im is None:
        (d / name).unlink(missing_ok=True)
        raise SystemExit(f"LỖI: {url} không phải ảnh (trang web/bị chặn) — chọn link ảnh khác (đuôi .jpg/.png)")
    imgio.imwrite(d / name, im, [1, 92])   # chuẩn hóa về đúng định dạng theo đuôi file (webp/avif → jpg…)
    sj = d / "illus_sources.json"
    src = json.loads(sj.read_text(encoding="utf-8")) if sj.exists() else {}
    src[name] = source or url
    sj.write_text(json.dumps(src, ensure_ascii=False, indent=1), encoding="utf-8")
    print(d / name)


def speed(pid, v):
    c = P.Ctx(pid)
    if c.project.plan is None:
        raise SystemExit("chưa có plan — chạy design.py trước")
    c.project.plan.speed = min(1.5, max(0.8, float(v)))
    c.save()
    print(f"tốc độ xuất ×{c.project.plan.speed:g} — app áp lúc xuất, không cần đổi timing chữ/MG")


def main():
    # bản đóng gói (nuitka) không chạy được `-m` theo kiểu __main__ → app gọi thẳng main()
    if len(sys.argv) < 2 or sys.argv[1] not in CMDS:
        print(__doc__)
        return
    cmd, *a = sys.argv[1:]
    CMDS[cmd](*a)


CMDS = {"where": where, "words": words, "fix": fix, "frames": frames, "img": img, "speed": speed}

if __name__ == "__main__":
    main()
