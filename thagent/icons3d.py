"""Kho icon 3D dùng chung cho mọi skill (không riêng skill nào).

Nguồn (miễn phí, dùng thương mại được):
- 3dicons — Vijay Verma, CC0 (https://3dicons.co): ~120 icon vật thể/khái niệm, kiểu "premium" (ánh kim vàng/đen — mặc định)
  hoặc "color" (màu tươi). Id dạng `clock`, `trophy`, `money-bag`…
- Microsoft Fluent Emoji 3D — MIT (https://github.com/microsoft/fluentui-emoji): ~1.000 hình đồ vật, đồ ăn, nhà cửa, phương tiện,
  y tế, thiên nhiên, biểu tượng… (bỏ mặt cười, người, cờ cho khỏi trẻ con). Id dạng `f-house`, `f-pill`, `f-stethoscope`…

assets/icons3d/index.json (có trong mã nguồn): [{"id", "src", "title", "keywords", "group"}]. Ảnh PNG tải lúc build bộ cài
(fetch_all) và tự tải khi thiếu (path). Tra icon: `python -m thagent.tools icon3d <từ khoá tiếng Anh>` hoặc find().
Trong callout: "icon": "3d:<id>" (vd "3d:trophy", "3d:f-house"); "icon_style": "premium"|"color" cho 3dicons.

python -m thagent.icons3d index     dựng lại index.json từ hai nguồn (máy dev)
python -m thagent.icons3d fetch     tải đủ PNG vào assets/icons3d (build bộ cài / dùng offline)
python -m thagent.icons3d find kw   tra theo từ khoá
"""
from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from .paths import ROOT

DIR = ROOT / "assets" / "icons3d"
INDEX = DIR / "index.json"
VJY = "https://3dicons.sgp1.cdn.digitaloceanspaces.com/v1/dynamic/{style}/{id}-dynamic-{style}.png"
FLU = "https://raw.githubusercontent.com/microsoft/fluentui-emoji/main/assets/{name}/3D/{file}_3d.png"
KEEP = {"Objects", "Symbols", "Travel & Places", "Animals & Nature", "Food & Drink", "Activities"}
STYLES = ("premium", "color")
_IDX: list[dict] | None = None


def _get(url: str, timeout=60) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "C-Cut"}), timeout=timeout).read()


def build_index() -> list[dict]:
    import concurrent.futures as cf
    out = []
    tree = json.loads(_get("https://api.github.com/repos/realvjy/3dicons/git/trees/develop?recursive=1"))["tree"]
    slugs = [t["path"].split("/")[-1][:-3] for t in tree if t["path"].startswith("content/3dicons-meta/") and t["path"].endswith(".md")]

    def vjy(s):
        md = _get(f"https://raw.githubusercontent.com/realvjy/3dicons/develop/content/3dicons-meta/{s}.md").decode()
        meta = dict(re.findall(r"^([\w-]+):\s*(.+)$", md, re.M))
        return {"id": s, "src": "3dicons", "title": meta.get("title", s), "keywords": [s.replace("-", " "), meta.get("title", s).lower()],
                "group": meta.get("category", "")}
    tree = json.loads(_get("https://api.github.com/repos/microsoft/fluentui-emoji/git/trees/main?recursive=1"))["tree"]
    names = sorted({t["path"].split("/")[1] for t in tree if re.match(r"assets/[^/]+/3D/[^/]+_3d\.png$", t["path"])})

    def flu(n):
        m = json.loads(_get(FLU.split("/{name}")[0] + "/" + urllib.parse.quote(n) + "/metadata.json"))
        if m.get("group") not in KEEP:
            return None
        f = next(t["path"] for t in tree if t["path"].startswith(f"assets/{n}/3D/") and t["path"].endswith("_3d.png"))
        return {"id": "f-" + re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-"), "src": "fluent", "title": n, "name": n,
                "file": f.split("/")[-1][:-7], "keywords": sorted(set(m.get("keywords", []) + [n.lower()])), "group": m["group"]}
    with cf.ThreadPoolExecutor(16) as ex:
        out += list(ex.map(vjy, slugs))
        out += [x for x in ex.map(flu, names) if x]
    DIR.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
    return out


def index() -> list[dict]:
    global _IDX
    if _IDX is None:
        _IDX = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else []
    return _IDX


def get(icon_id: str) -> dict | None:
    return next((x for x in index() if x["id"] == icon_id), None)


def exists(icon_id: str) -> bool:
    return get(icon_id) is not None


def _url_file(e: dict, style: str) -> tuple[str, Path]:
    if e["src"] == "3dicons":
        style = style if style in STYLES else STYLES[0]
        return VJY.format(style=style, id=e["id"]), DIR / "3dicons" / style / f"{e['id']}.png"
    return FLU.format(name=urllib.parse.quote(e["name"]), file=urllib.parse.quote(e["file"])), DIR / "fluent" / f"{e['id']}.png"


def path(icon_id: str, style: str = "premium") -> Path:
    """đường dẫn PNG (RGBA); chưa có thì tải về kho chung."""
    e = get(icon_id)
    if not e:
        raise KeyError(f"không có icon 3D “{icon_id}” — tra bằng: python -m thagent.tools icon3d <từ khoá>")
    tries = [style] + [s for s in STYLES if s != style] if e["src"] == "3dicons" else [style]
    for i, st in enumerate(tries):                      # 3dicons thiếu một kiểu (vd crown premium) → dùng kiểu kia
        url, f = _url_file(e, st)
        if f.exists():
            return f
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            tmp = f.with_suffix(".part")
            tmp.write_bytes(_get(url))
            tmp.replace(f)
            return f
        except Exception:
            if i == len(tries) - 1:
                raise
    return f


def fetch_all(log=print) -> int:
    import concurrent.futures as cf
    jobs = [(e["id"], s) for e in index() for s in (STYLES if e["src"] == "3dicons" else ("",))]

    def one(j):
        try:
            path(*j)
            return 1
        except Exception as ex:
            log(f"icon 3D {j[0]}: {ex}")
            return 0
    with cf.ThreadPoolExecutor(16) as ex:
        n = sum(ex.map(one, jobs))
    log(f"kho icon 3D: {n}/{len(jobs)} ảnh")
    return n


def find(q: str, limit: int = 20) -> list[dict]:
    """tra theo từ khoá tiếng Anh; 3dicons (đẹp/sang hơn) đứng trước khi điểm bằng nhau."""
    ws = [w for w in re.split(r"\W+", q.lower()) if w]
    scored = []
    for e in index():
        hay = " ".join([e["id"], e["title"].lower()] + [k.lower() for k in e["keywords"]])
        s = sum(2 for w in ws if re.search(rf"\b{re.escape(w)}\b", e["title"].lower() + " " + e["id"]))
        s += sum(3 if re.search(rf"\b{re.escape(w)}\b", hay) else 1 if w in hay else 0 for w in ws)
        if s:
            scored.append((-s, e["src"] != "3dicons", len(e["title"]), e["id"], e))
    return [x[-1] for x in sorted(scored)[:limit]]


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "index":
        print(len(build_index()), "icon")
    elif cmd == "fetch":
        fetch_all()
    elif cmd == "find":
        for e in find(" ".join(sys.argv[2:])):
            print(f"3d:{e['id']:<28} {e['title']}  [{e['group']}]")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
