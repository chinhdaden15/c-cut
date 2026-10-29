"""Talking Head — công thức đã chốt (bản Agency v5, 2026-10-29), app TỰ áp trước stills / preflight / render
để Claude trong app (hoặc kế hoạch cũ) ra đúng kết quả mà không phải chỉnh tay:

khi bật phụ đề (mặc định):
- chữ nhấn chỉ còn CHỮ CHÍNH: bỏ dòng dẫn nhỏ (< 80) và nhãn pill — phụ đề theo ý làm dòng dẫn;
- mỗi dòng chữ nhấn hiện ĐÚNG mốc từ đó trong lời; nhóm TẮT khi người nói sang từ kế tiếp sau cụm nhấn;
- callout không mờ khi đang nói dở một từ: end ≥ cuối từ đang nói lúc bắt đầu mờ + 10 frame;
- chữ sau lưng (giant_text / big_number / marquee) vào đúng mốc từ;
- cảnh money / chart: tự tìm mốc NÓI số cuối (hit_at), đơn vị tiền theo lời ($ / € / £), video tiếng Anh → kiểu 2,000.
check() = lỗi chặn dựng cho những gì app không tự sửa được (thẻ câu hỏi thiếu ảnh, tên phần mềm / hãng thiếu logo thật,
chữ chính dài một dòng, số tiền không khớp lời, chưa có phude.json)."""
from __future__ import annotations

import re
from pathlib import Path

_K = lambda w: re.sub(r"[^\w]", "", str(w).lower())
LEAD_MAX = 80                 # span chữ < 80 = dòng dẫn nhỏ
CALLOUT_EXIT = 8              # callout mờ dần ~8 frame trước end
BRANDS = ["after effects", "premiere", "photoshop", "illustrator", "lightroom", "adobe", "capcut", "canva", "figma",
          "davinci", "final cut", "tiktok", "youtube", "facebook", "instagram", "zalo", "shopee", "lazada", "chatgpt",
          "excel", "notion", "google", "iphone", "samsung", "apple", "microsoft", "netflix", "spotify"]
CUR = {"$": "$", "€": "€", "£": "£", "¥": "¥"}


LOGO = {"after effects": "Adobe_After_Effects_CC_icon.svg", "premiere": "Adobe_Premiere_Pro_CC_icon.svg",
        "photoshop": "Adobe_Photoshop_CC_icon.svg", "illustrator": "Adobe_Illustrator_CC_icon.svg",
        "lightroom": "Adobe_Photoshop_Lightroom_CC_logo.svg", "adobe": "Adobe_Creative_Cloud_rainbow_icon.svg", "capcut": "Capcut-icon.svg",
        "figma": "Figma-logo.svg", "davinci": "DaVinci_Resolve_17_logo.svg", "tiktok": "Tiktok_icon.svg",
        "youtube": "YouTube_full-color_icon_(2017).svg", "facebook": "2023_Facebook_icon.svg", "instagram": "Instagram_logo_2022.svg",
        "zalo": "Icon_of_Zalo.svg", "chatgpt": "ChatGPT-Logo.svg", "excel": "Microsoft_Office_Excel_(2019–present).svg",
        "notion": "Notion-logo.svg", "google": "Google_%22G%22_logo.svg", "apple": "Apple_logo_black.svg", "samsung": "Samsung_Logo.svg",
        "microsoft": "Microsoft_logo.svg", "netflix": "Netflix_2015_N_logo.svg", "spotify": "Spotify_icon.svg",
        "shopee": "Shopee.svg", "lazada": "Lazada_(2019).svg"}


def fetch_logo(brand: str, pdir) -> str | None:
    """logo THẬT từ Wikimedia Commons → {pdir}/assets_web/logo_<tên>.png (nguồn ghi logo_sources.json). None nếu không tải được."""
    import json, urllib.parse, urllib.request
    pdir = Path(pdir)
    dst = pdir / "assets_web" / f"logo_{re.sub(r'[^a-z0-9]+', '_', brand.lower()).strip('_')}.png"
    if dst.exists():
        return str(dst)
    ua = {"User-Agent": "Mozilla/5.0 ccut"}
    name = LOGO.get(brand.lower())
    try:
        if not name:                                       # chưa có trong bảng → tìm trên Commons
            q = urllib.parse.urlencode({"action": "query", "list": "search", "srnamespace": 6, "format": "json", "srlimit": 1,
                                        "srsearch": f"{brand} logo filetype:svg"})
            r = json.loads(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q, headers=ua), timeout=20).read())
            hits = r.get("query", {}).get("search") or []
            if not hits:
                return None
            name = hits[0]["title"].removeprefix("File:").replace(" ", "_")
        url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{urllib.parse.quote(urllib.parse.unquote(name))}?width=512"
        data = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=30).read()
        if not data.startswith(b"\x89PNG"):
            return None
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        src = dst.parent / "logo_sources.json"
        d = json.loads(src.read_text()) if src.exists() else {}
        d[dst.name] = f"https://commons.wikimedia.org/wiki/File:{urllib.parse.unquote(name)}"
        src.write_text(json.dumps(d, ensure_ascii=False, indent=1))
        return str(dst)
    except Exception:
        return None


def _is_img(icon) -> bool:
    return bool(icon) and Path(str(icon)).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and Path(str(icon)).exists()


def _brand(txt: str):
    return next((b for b in BRANDS if re.search(rf"\b{re.escape(b)}\b", txt.lower())), None)


def _tl_words(plan, words):
    from . import timeline as T
    T.build_mapping(plan)
    out = []
    for w in words or []:
        a = T.src_to_tl(plan, w.source_start)
        if a is None:
            continue
        b = T.src_to_tl(plan, w.source_end)
        out.append((a, b if b is not None else a + 8, w.text.strip()))
    out.sort()
    return out


def _find(tw, text, near, win=120):
    """vị trí (chỉ số) chuỗi từ `text` trong lời gần frame `near`; None nếu không khớp."""
    toks = [_K(t) for t in str(text).replace("–", " ").split() if _K(t)]
    if not toks:
        return None
    keys = [_K(x[2]) for x in tw]
    best = None
    for i in range(len(tw) - len(toks) + 1):
        if keys[i:i + len(toks)] == toks and abs(tw[i][0] - near) <= win:
            if best is None or abs(tw[i][0] - near) < abs(tw[best][0] - near):
                best = i
    return None if best is None else (best, best + len(toks) - 1)


def _lang(pdir) -> str:
    try:
        from . import fonts as FT
        FT.use_project(Path(pdir))
        return FT.current()
    except Exception:
        return "vi"


def apply(plan, words, pdir=None) -> list[str]:
    """đưa kế hoạch về đúng công thức đã chốt (sửa tại chỗ, chạy lại nhiều lần vẫn vậy). → nhật ký thay đổi."""
    log = []
    tw = _tl_words(plan, words)
    if not tw:
        return log
    fps = plan.fps
    if plan.captions:
        for g in plan.text_groups:
            if not g.enabled:
                continue
            keep = [s for s in g.spans if not (s.style == "pill" or (s.style != "icon" and s.size < LEAD_MAX))]
            if len(keep) != len(g.spans):
                log.append(f"{g.id}: bỏ dòng dẫn nhỏ / nhãn — phụ đề làm dòng dẫn")
                g.spans = keep
            mains = [s for s in g.spans if s.style != "icon"]
            if not mains:
                g.enabled = False
                log.append(f"{g.id}: không còn chữ chính → tắt nhóm")
                continue
            near = g.start + min(s.delay_frames for s in mains)
            hits, last = [], None
            for s in mains:
                m = _find(tw, s.text, near)
                hits.append(m)
                if m:
                    last = m[1] if last is None else max(last, m[1])
            if not any(hits):
                continue
            appear = [tw[m[0]][0] if m else None for m in hits]
            for i in range(1, len(appear)):                # dòng nói liền nhau (< 10 frame) → hiện cùng lúc như một cụm
                if appear[i] is not None and appear[i - 1] is not None and appear[i] - appear[i - 1] < 10:
                    appear[i] = appear[i - 1]
            a0 = min(x for x in appear if x is not None)
            start = max(0, a0 - 3)
            prev = 0
            for s, ap in zip(mains, appear):
                d = (ap - start) if ap is not None else prev + 6
                s.delay_frames = max(0, d)
                prev = s.delay_frames
            done = start + max(s.delay_frames for s in mains) + 9
            nxt = tw[last + 1][0] if last + 1 < len(tw) else plan.duration_frames
            end = max(nxt + g.exit_frames, done + int(0.25 * fps) + g.exit_frames)
            end = min(end, plan.duration_frames)
            if (g.start, g.end) != (start, end):
                log.append(f"{g.id}: {g.start}–{g.end} → {start}–{end} (hiện đúng lúc nói, tắt khi sang lời mới)")
            g.start, g.end, g.hit = start, end, start + min(s.delay_frames for s in mains) + 5
    # callout: không mờ khi đang nói dở từ
    blocks = sorted([int(c["start"]) for c in plan.callouts] + [int(m["start"]) for m in plan.mg2 if m.get("enabled", True)])
    for c in plan.callouts:
        e = int(c.setdefault("end0", int(c["end"])))          # tính từ mốc GỐC → chạy lại nhiều lần không kéo dài thêm
        cur = [w for w in tw if w[0] <= e - CALLOUT_EXIT < w[1] + 2]
        if cur:
            need = cur[-1][1] + 10
            cap = min([b for b in blocks if b > int(c["start"])] + [plan.duration_frames])
            ne = min(max(e, need), cap)
            if ne != int(c["end"]):
                c["end"] = ne
                log.append(f"{c['id']}: end {e} → {ne} (giữ tới hết từ đang nói)")
    # chữ sau lưng vào đúng mốc từ
    for st in plan.stage:
        if st.get("kind") in ("giant_text", "big_number", "marquee") and st.get("text"):
            m = _find(tw, str(st["text"]).split()[0], int(st["start"]), 45)
            if m and tw[m[0]][0] != int(st["start"]):
                d = tw[m[0]][0] - int(st["start"])
                st["start"] = tw[m[0]][0]; st["end"] = int(st["end"]) + d
                log.append(f"{st['id']}: vào đúng lúc nói “{st['text']}”")
    # số chạy khớp lời
    en = _lang(pdir) == "en" if pdir else False
    for sc in plan.mg2:
        if sc.get("kind") not in ("money", "chart") or not sc.get("enabled", True):
            continue
        a0, b0 = int(sc["start"]), int(sc["end"])
        unit = str(sc.get("unit", "")).strip()
        mul = {"k": 1e3, "K": 1e3, "nghìn": 1e3, "ngàn": 1e3}.get(unit)
        if mul and float(sc.get("value_to", 0)) * mul < 10000:   # < 5 chữ số → để nguyên (500, 2,000), không rút 0.5K
            for k_ in ("value_from", "value_to"):
                sc[k_] = round(float(sc.get(k_, 0)) * mul)
            sc["unit"], sc["decimals"] = "", 0
            log.append(f"{sc['id']}: số < 5 chữ số để nguyên ({sc['value_from']:,} → {sc['value_to']:,}), không rút gọn")
        # ≥ 5 chữ số → rút gọn theo NGÔN NGỮ video: tiếng Anh K / M / B (2B), tiếng Việt nghìn / triệu / tỷ (2 tỷ)
        EN_U = {"nghìn": "K", "ngàn": "K", "triệu": "M", "tr": "M", "tỷ": "B", "tỉ": "B"}
        VI_U = {"k": "nghìn", "m": "triệu", "b": "tỷ", "bn": "tỷ"}
        u = str(sc.get("unit", "")).strip()
        if en and u.lower() in EN_U:
            sc["unit"] = EN_U[u.lower()]; log.append(f"{sc['id']}: tiếng Anh → đơn vị {sc['unit']}")
        elif not en and u.lower() in VI_U:
            sc["unit"] = VI_U[u.lower()]; log.append(f"{sc['id']}: tiếng Việt → đơn vị {sc['unit']}")
        elif not u and float(sc.get("value_to", 0)) >= 10000:
            vt_ = float(sc["value_to"])
            sc_, un = next(((d, n) for d, n in ((1e9, ("B", "tỷ")), (1e6, ("M", "triệu")), (1e3, ("K", "nghìn"))) if vt_ >= d))
            for k_ in ("value_from", "value_to"):
                sc[k_] = round(float(sc.get(k_, 0)) / sc_, 2)
            sc["unit"] = un[0] if en else un[1]
            sc["decimals"] = 0 if float(sc["value_to"]).is_integer() else 1
            log.append(f"{sc['id']}: ≥ 5 chữ số → {sc['value_to']:g} {sc['unit']}")
        if en and not sc.get("locale"):
            sc["locale"] = "en"; log.append(f"{sc['id']}: video tiếng Anh → số kiểu 2,000")
        vt = float(sc.get("value_to", 0))
        for f0, _, t in tw:
            if not (a0 - 60 <= f0 < b0):
                continue
            num = re.sub(r"[^\d.]", "", t.replace(",", ""))
            try:
                ok = num and abs(float(num) - vt) < 1e-6
            except ValueError:
                ok = False
            if ok:
                if "hit_at" not in sc:
                    sc["hit_at"] = round(max(0.8, (f0 - a0) / fps), 2)
                    log.append(f"{sc['id']}: số chạm đúng lúc nói “{t}” ({sc['hit_at']}s)")
                cur_ = next((CUR[ch] for ch in t if ch in CUR), None)
                if cur_ and sc.get("kind") == "money" and not sc.get("prefix"):
                    sc["prefix"] = cur_; log.append(f"{sc['id']}: đơn vị “{cur_}” theo lời")
                break
    # tên phần mềm / hãng → tự tải LOGO THẬT
    if pdir:
        for x in list(plan.mg2) + list(plan.callouts):
            for it in [i for i in (x.get("items") or []) if isinstance(i, dict)] + [x]:
                b = _brand(" ".join(str(it.get(k, "")) for k in ("title", "text", "heading")))
                if b and not _is_img(it.get("icon")):
                    p = fetch_logo(b, pdir)
                    if p:
                        it["icon"] = str(Path(p).resolve().relative_to(Path.cwd())) if Path(p).resolve().is_relative_to(Path.cwd()) else p
                        log.append(f"{x['id']}: logo thật “{b}”")
    return log


def check(plan, words, pdir) -> list[tuple[str, str]]:
    """lỗi chặn dựng (app không tự sửa được)."""
    out = []
    add = lambda m: out.append(("error", m))
    tw = _tl_words(plan, words)
    pdir = Path(pdir)
    if plan.captions and not (pdir / "phude.json").exists() and "heuristic" not in (plan.planner or ""):   # kế hoạch Claude viết
        add("bật phụ đề mà chưa có phude.json — Claude chia lời thành cụm theo Ý (2–3 từ đủ nghĩa, đúng chữ + thứ tự transcript)")
    for g in plan.text_groups:
        if not g.enabled:
            continue
        mains = [s for s in g.spans if s.style != "icon" and s.style != "pill" and (s.size >= LEAD_MAX or plan.captions)]
        if len(mains) == 1 and len(mains[0].text) > 12:
            add(f"{g.id}: chữ chính “{mains[0].text}” dài một dòng — chia 2 dòng chữ to (2 span cùng cỡ ~110–130)")
    for sc in plan.mg2:
        if not sc.get("enabled", True):
            continue
        k = sc.get("kind")
        if k == "question" and not sc.get("image"):
            add(f"mg2 {sc['id']}: thẻ câu hỏi thiếu ảnh minh hoạ (bắt buộc)")
        if k in ("money", "chart") and "hit_at" not in sc:
            add(f"mg2 {sc['id']}: không tìm thấy lúc NÓI số {sc.get('value_to')} trong lời — value_to phải đúng số được nói, hoặc đặt hit_at")
    # tên phần mềm / hãng → logo thật
    def items(x):
        for it in (x.get("items") or []):
            if isinstance(it, dict):
                yield " ".join(str(it.get(k, "")) for k in ("title", "text")), it.get("icon")
        yield " ".join(str(x.get(k, "")) for k in ("text", "title", "heading")), x.get("icon")
    for x in list(plan.mg2) + list(plan.callouts):
        for txt, icon in items(x):
            b = _brand(txt)
            if b and not _is_img(icon):
                add(f"{x['id']}: nhắc “{b}” mà icon không phải LOGO THẬT — tải logo đúng (Wikimedia) vào assets_web, icon = đường dẫn ảnh")
    return out
