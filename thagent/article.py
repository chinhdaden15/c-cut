"""Video TIN TỨC từ link bài báo (Text to Video / Voice to Motion).

  python -m thagent.article fetch <link>                 đọc thử: tiêu đề, sapo, ngày, nguồn, số đoạn, ảnh
  python -m thagent.article prepare <dự-án> <link>       article.json + ảnh trong bài + ảnh chụp trang thật (phóng từng đoạn)
                                                         + logo báo → assets_web/  (ảnh xem nhanh: assets_web/_bao/sheet.jpg)

fetch(): HTML tĩnh (JSON-LD NewsArticle → og:* → thẻ h1 / p). Bài trống (trang dựng bằng JavaScript) → đọc lại qua Chrome chạy
ngầm của app. Trang chặn (401/403/429/451) hoặc cần đăng nhập / bài trả phí → ArticleError nói rõ để người dùng dán nội dung.
Không vượt tường phí, không giả đăng nhập.
"""
from __future__ import annotations

import html as _html
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
URL_RE = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.I)
MIN_BODY = 350              # ký tự lời bài tối thiểu — ít hơn = không đọc được bài (trả phí / cần đăng nhập / chặn)

# tên báo hiển thị đúng cách viết (theo tên miền)
SOURCES = {
    "vnexpress.net": "VnExpress", "e.vnexpress.net": "VnExpress International", "tuoitre.vn": "Tuổi Trẻ",
    "thanhnien.vn": "Thanh Niên", "dantri.com.vn": "Dân trí", "vietnamnet.vn": "VietNamNet", "znews.vn": "Znews",
    "zingnews.vn": "Znews", "cafef.vn": "CafeF", "cafebiz.vn": "CafeBiz", "vneconomy.vn": "VnEconomy", "laodong.vn": "Lao Động",
    "nld.com.vn": "Người Lao Động", "tienphong.vn": "Tiền Phong", "vtv.vn": "VTV", "vov.vn": "VOV", "baochinhphu.vn": "Báo Chính phủ",
    "nhandan.vn": "Nhân Dân", "qdnd.vn": "Quân đội Nhân dân", "24h.com.vn": "24h", "kenh14.vn": "Kenh14", "genk.vn": "GenK",
    "soha.vn": "Soha", "vietnamplus.vn": "VietnamPlus", "plo.vn": "Pháp Luật TP.HCM", "sggp.org.vn": "Sài Gòn Giải Phóng",
    "baomoi.com": "Báo Mới", "vtc.vn": "VTC News", "vietnamfinance.vn": "VietnamFinance", "ndh.vn": "NDH", "vnreview.vn": "VnReview",
    "tinhte.vn": "Tinh tế", "thesaigontimes.vn": "Kinh tế Sài Gòn", "baodautu.vn": "Báo Đầu tư", "congan.com.vn": "Công an TP.HCM",
    "cand.com.vn": "Công an Nhân dân", "giadinh.suckhoedoisong.vn": "Gia đình & Xã hội", "suckhoedoisong.vn": "Sức khỏe & Đời sống",
    "bbc.com": "BBC", "reuters.com": "Reuters", "apnews.com": "AP", "cnn.com": "CNN", "bloomberg.com": "Bloomberg",
    "theverge.com": "The Verge", "techcrunch.com": "TechCrunch", "nytimes.com": "The New York Times",
}
BLOCKED_HINT = ("Trang này không cho app tự mở (cần đăng nhập, bài trả phí hoặc chặn truy cập tự động). "
                "Mở bài trên trình duyệt, chép tiêu đề + nội dung bài rồi dán vào ô kịch bản (dòng đầu là tiêu đề, "
                "có thể giữ link ở cuối để ghi nguồn).")


class ArticleError(Exception):
    pass


# ---------------- tìm link trong ô kịch bản ----------------
def find_url(text: str | None) -> str | None:
    """ô kịch bản / ý tưởng chủ yếu là link bài báo (link + ≤ 25 từ dặn thêm) → link đó. Kịch bản dài kèm link nguồn → None."""
    if not text:
        return None
    urls = URL_RE.findall(text)
    if not urls:
        return None
    rest = URL_RE.sub(" ", text)
    rest = re.sub(r"\[[^\]]*\]\(\s*\)", " ", rest)
    return urls[0].rstrip(".,;)") if len(rest.split()) <= 25 else None


def note_of(text: str | None) -> str:
    """lời dặn thêm đi kèm link (vd “làm ngắn 45 giây, giọng sôi nổi”)."""
    return re.sub(r"\s+", " ", URL_RE.sub(" ", text or "")).strip()


# ---------------- tải trang ----------------
def _get(url: str, timeout=20) -> tuple[str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "vi,en;q=0.8",
                                               "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            final = r.geturl()
            cs = r.headers.get_content_charset()
    except urllib.error.HTTPError as e:
        if e.code in (401, 402, 403, 407, 429, 451):
            raise ArticleError(f"Không mở được link (mã {e.code}). " + BLOCKED_HINT)
        if e.code == 404:
            raise ArticleError("Link không tồn tại (404) — kiểm tra lại link bài báo.")
        raise ArticleError(f"Không mở được link (mã {e.code}). " + BLOCKED_HINT)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ArticleError(f"Không kết nối được tới trang ({getattr(e, 'reason', e)}). Kiểm tra mạng / link, hoặc dán nội dung bài.")
    if not cs:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4000], re.I)
        cs = m.group(1).decode() if m else "utf-8"
    try:
        return raw.decode(cs, "replace"), final
    except LookupError:
        return raw.decode("utf-8", "replace"), final


def _chrome_dom(url: str) -> str:
    """trang dựng bằng JavaScript: lấy DOM sau khi chạy script (Chrome chạy ngầm của app)."""
    from .brandkit import _chrome
    r = subprocess.run([_chrome(), "--headless", "--disable-gpu", "--virtual-time-budget=8000", f"--user-agent={UA}",
                        "--dump-dom", url], capture_output=True, timeout=90)
    return r.stdout.decode("utf-8", "replace")


# ---------------- bóc nội dung ----------------
SKIP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form", "button", "nav", "footer", "header", "aside", "select", "template"}
VOID = {"img", "br", "hr", "meta", "link", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
JUNK = re.compile(r"^(xem thêm|đọc thêm|tin liên quan|bài liên quan|xem tiếp|>>|chia sẻ|theo dõi|quảng cáo|ảnh:|video:|nguồn:)", re.I)


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int, dict]] = []       # (tag, id, attrs)
        self.n = 0
        self.blocks: list[dict] = []                         # p / h2 / h3 / li: text + đường cha
        self.imgs: list[dict] = []
        self.ld: list[str] = []
        self.meta: dict[str, str] = {}
        self.h1 = ""
        self._cur = None
        self._ld = None
        self._skip = 0
        self._cap = None
        self._h1 = None

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "meta":
            k = a.get("property") or a.get("name") or a.get("itemprop")
            if k and a.get("content") and k.lower() not in self.meta:
                self.meta[k.lower()] = a["content"]
            return
        if tag == "script" and "ld+json" in a.get("type", ""):
            self._ld = []
        if tag in VOID:
            if tag == "img" and not self._skip:
                src = a.get("data-src") or a.get("data-original") or a.get("data-lazy-src") or a.get("src") or ""
                if not src and a.get("srcset"):
                    src = a["srcset"].split(",")[-1].strip().split(" ")[0]
                if src and not src.startswith("data:"):
                    self.imgs.append({"src": src, "alt": a.get("alt", ""), "path": [i for _, i, _ in self.stack],
                                      "w": a.get("width", ""), "cap": ""})
            return
        self.n += 1
        self.stack.append((tag, self.n, a))
        if tag in SKIP_TAGS:
            self._skip += 1
        cls = a.get("class", "")
        if tag == "figcaption" or (tag in ("p", "div", "span") and re.search(r"(caption|desc_img|image-caption|fig-cap)", cls, re.I)):
            self._cap = []
        if tag == "h1" and not self.h1:
            self._h1 = []
        if tag in ("p", "h2", "h3", "li") and not self._skip and self._cur is None:
            self._cur = {"tag": tag, "parts": [], "path": [i for _, i, _ in self.stack[:-1]], "cls": cls,
                         "style": a.get("style", "")}

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        while self.stack:
            t, i, a = self.stack.pop()
            if t in SKIP_TAGS:
                self._skip = max(0, self._skip - 1)
            if t == "script" and self._ld is not None:
                self.ld.append("".join(self._ld)); self._ld = None
            if self._cap is not None and (t == "figcaption" or t in ("p", "div", "span")):
                txt = re.sub(r"\s+", " ", "".join(self._cap)).strip()
                if txt and self.imgs and not self.imgs[-1]["cap"]:
                    self.imgs[-1]["cap"] = txt
                if t == "figcaption" or txt:
                    self._cap = None
            if t == "h1" and self._h1 is not None:
                self.h1 = re.sub(r"\s+", " ", "".join(self._h1)).strip(); self._h1 = None
            if self._cur is not None and t == self._cur["tag"]:
                txt = re.sub(r"\s+", " ", "".join(self._cur["parts"])).strip()
                if txt:
                    self.blocks.append({**self._cur, "text": txt, "cap": False})
                self._cur = None
            if t == tag:
                break

    def handle_data(self, d):
        if self._ld is not None:
            self._ld.append(d)
        if self._skip:
            return
        if self._h1 is not None:
            self._h1.append(d)
        if self._cap is not None:
            self._cap.append(d)
            if self._cur is not None:
                self._cur["cap"] = True
        if self._cur is not None:
            self._cur["parts"].append(d)


def _ld_article(chunks: list[str]) -> dict:
    def walk(x):
        if isinstance(x, list):
            for y in x:
                yield from walk(y)
        elif isinstance(x, dict):
            yield x
            for k in ("@graph", "mainEntity"):
                if k in x:
                    yield from walk(x[k])
    for c in chunks:
        try:
            data = json.loads(c.strip())
        except Exception:
            try:
                data = json.loads(re.sub(r"[\x00-\x1f]", " ", c.strip()))
            except Exception:
                continue
        for d in walk(data):
            t = d.get("@type")
            t = " ".join(t) if isinstance(t, list) else str(t or "")
            if any(k in t for k in ("NewsArticle", "Article", "BlogPosting", "Report")):
                return d
    return {}


def _img_url(x) -> str:
    if isinstance(x, list):
        x = x[0] if x else ""
    if isinstance(x, dict):
        x = x.get("url") or x.get("contentUrl") or ""
    return str(x or "")


def _date(s: str) -> tuple[str, str]:
    """(ISO, dd/mm/yyyy)"""
    if not s:
        return "", ""
    s = s.strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d.isoformat(), d.strftime("%d/%m/%Y")
    except ValueError:
        pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return s, f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        return s, f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    return s, ""


def source_name(url: str, fallback: str = "") -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")
    if host in SOURCES:
        return SOURCES[host]
    for d, n in SOURCES.items():
        if host.endswith("." + d):
            return n
    if fallback and not re.search(r"\.(vn|com|net|org)$", fallback.lower()):
        return fallback
    return host.split(".")[0].capitalize() if host else (fallback or "Nguồn")


def _clean(t: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(t or "")).strip()


def parse(html_text: str, url: str) -> dict:
    p = _P()
    try:
        p.feed(html_text)
        p.close()
    except Exception:
        pass
    ld = _ld_article(p.ld)
    m = p.meta
    title = _clean(ld.get("headline") or m.get("og:title") or p.h1 or m.get("twitter:title") or "")
    if p.h1 and len(p.h1) > len(title) * 0.6 and len(p.h1) <= 220:
        title = _clean(p.h1)                                      # tiêu đề hiển thị trên trang (og:title hay kèm “ - Tên báo”)
    site = source_name(url, _clean((ld.get("publisher") or {}).get("name", "") if isinstance(ld.get("publisher"), dict) else "")
                       or m.get("og:site_name", ""))
    title = re.sub(rf"\s*[-|–]\s*{re.escape(site)}\s*$", "", title, flags=re.I)
    desc = _clean(ld.get("description") or m.get("og:description") or m.get("description") or "")
    desc = re.sub(r"\s*-\s*[\w .]+$", "", desc) if re.search(r"\s-\s(VnExpress|Tuổi Trẻ|Thanh Niên|Dân trí)\w*$", desc) else desc
    iso, shown = _date(ld.get("datePublished") or m.get("article:published_time") or m.get("pubdate") or m.get("datepublished")
                       or m.get("date") or m.get("dc.date.issued") or "")
    author = ld.get("author")
    if isinstance(author, list):
        author = ", ".join(a.get("name", "") if isinstance(a, dict) else str(a) for a in author)
    elif isinstance(author, dict):
        author = author.get("name", "")
    likes = None
    for st in (ld.get("interactionStatistic") or []) if isinstance(ld.get("interactionStatistic"), list) else [ld.get("interactionStatistic") or {}]:
        if isinstance(st, dict) and st.get("userInteractionCount"):
            kind = str(st.get("interactionType", ""))
            likes = likes or {}
            key = "likes" if "Like" in kind else "comments" if "Comment" in kind else "shares" if "Share" in kind else "tuong_tac"
            try:
                likes[key] = int(st["userInteractionCount"])
            except Exception:
                pass

    # thân bài: cha trực tiếp chứa nhiều chữ nhất trong các đoạn dài (lên 1 bậc nếu chữ rải nhiều khung)
    long_ = [b for b in p.blocks if b["tag"] == "p" and len(b["text"]) >= 40 and not b["cap"]]
    score: dict[int, int] = {}
    for b in long_:
        if b["path"]:
            score[b["path"][-1]] = score.get(b["path"][-1], 0) + len(b["text"])
    body_ids: set[int] = set()
    if score:
        best = max(score, key=score.get)
        total = sum(len(b["text"]) for b in long_)
        body_ids = {best}
        if score[best] < 0.5 * total:                            # đoạn nằm rải trong nhiều div con → dùng ông
            par = [b["path"][-2] for b in long_ if len(b["path"]) >= 2 and b["path"][-1] == best]
            if par:
                gp = par[0]
                body_ids = {b["path"][-1] for b in long_ if gp in b["path"]} | {gp}
    paras = []
    for b in p.blocks:
        if not b["path"] or b["path"][-1] not in body_ids or b["cap"]:
            continue
        t = _clean(b["text"])
        if not t or JUNK.match(t) or t == desc:
            continue
        if b["tag"] == "li" and len(t) < 25:
            continue
        paras.append({"tag": b["tag"], "text": t})
    # dòng tác giả cuối bài (ngắn, không dấu chấm) → tách ra
    while paras and len(paras[-1]["text"].split()) <= 6 and not re.search(r"[.!?…:]$", paras[-1]["text"]):
        author = author or paras[-1]["text"]
        paras.pop()
    if desc and paras and paras[0]["text"].startswith(desc[:40]):
        paras.pop(0)
    # ảnh trong bài (cùng khung thân bài) + ảnh chính
    main_img = urllib.parse.urljoin(url, _img_url(ld.get("image")) or m.get("og:image", "") or "")
    imgs, seen = [], set()
    for im in p.imgs:
        if not body_ids or not (set(im["path"]) & body_ids or any(i in body_ids for i in im["path"])):
            continue
        u = urllib.parse.urljoin(url, _html.unescape(im["src"]))
        key = re.sub(r"\?.*$", "", u)
        if key in seen or re.search(r"(logo|icon|avatar|sprite|blank|pixel|1x1|ads?[_/-])", u, re.I):
            continue
        seen.add(key)
        imgs.append({"url": u, "caption": _clean(im["cap"] or im["alt"])})
    return {"url": url, "source": site, "title": title, "sapo": desc, "date": shown, "date_iso": iso,
            "author": _clean(author or ""), "image": main_img, "images": imgs[:12], "paragraphs": paras,
            "interaction": likes, "keywords": _clean(m.get("keywords") or m.get("news_keywords") or ""),
            "section": _clean(m.get("article:section") or "")}


def body_text(a: dict) -> str:
    return "\n".join(p["text"] for p in a.get("paragraphs", []))


def fetch(url: str) -> dict:
    url = url.strip()
    if not re.match(r"https?://", url, re.I):
        url = "https://" + url
    html_text, final = _get(url)
    a = parse(html_text, final)
    if len(body_text(a)) < MIN_BODY:                              # trang dựng bằng JS → thử DOM sau khi chạy script
        try:
            dom = _chrome_dom(final)
            b = parse(dom, final) if dom else None
            if b and len(body_text(b)) > len(body_text(a)):
                a = {**b, **{k: v for k, v in a.items() if v and k in ("title", "sapo", "date", "date_iso", "image", "author")}}
        except Exception:
            pass
    if len(body_text(a)) < MIN_BODY:
        raise ArticleError(("Mở được trang nhưng không thấy nội dung bài" + (f" “{a['title'][:60]}”" if a.get("title") else "")
                            + ". " + BLOCKED_HINT))
    a["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return a


def from_text(text: str, url: str | None = None) -> dict:
    """người dùng dán nội dung bài (trang chặn / cần đăng nhập): dòng đầu = tiêu đề, đoạn sau = thân bài."""
    url = url or find_any_url(text)
    lines = [ln.strip() for ln in URL_RE.sub("", text).splitlines() if ln.strip()]
    if not lines:
        raise ArticleError("chưa có nội dung bài")
    title, rest = lines[0].lstrip("# ").strip(), lines[1:]
    sapo = rest.pop(0) if rest and len(rest[0]) < 400 and len(rest) > 2 else ""
    return {"url": url or "", "source": source_name(url) if url else "", "title": title, "sapo": sapo, "date": "", "date_iso": "",
            "author": "", "image": "", "images": [], "paragraphs": [{"tag": "p", "text": t} for t in rest], "interaction": None,
            "keywords": "", "section": "", "pasted": True}


def find_any_url(text: str) -> str | None:
    m = URL_RE.search(text or "")
    return m.group(0).rstrip(".,;)") if m else None


def looks_like_article(text: str) -> bool:
    """nội dung bài báo dán kèm link nguồn (không phải kịch bản lời đọc): có link + ≥ 120 từ + câu văn báo."""
    return bool(find_any_url(text)) and len(URL_RE.sub(" ", text).split()) >= 120


# ---------------- chuẩn bị tư liệu cho dự án ----------------
def _slug(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower()).replace("đ", "d")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")[:40] or "bao"


def _download(url: str, dst: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": url})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = r.read()
        import cv2
        import numpy as np
        im = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if im is None or min(im.shape[:2]) < 200:
            return False
        dst.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dst), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return True
    except Exception:
        return False


MEASURE_JS = r"""
<script>
(function(){
  function norm(s){return (s||'').replace(/\s+/g,' ').trim().toLowerCase().slice(0,80)}
  function go(){
    var want = __WANT__, out = {paras: [], page_h: 0, title: null, sapo: null};
    var els = Array.prototype.slice.call(document.querySelectorAll('p,h1,h2,h3,li'));
    var sx = window.scrollX, sy = window.scrollY;
    function box(e){var r=e.getBoundingClientRect();return [Math.round(r.left+sx),Math.round(r.top+sy),Math.round(r.width),Math.round(r.height)]}
    for (var i=0;i<want.length;i++){
      var w = want[i], hit = null;
      for (var j=0;j<els.length;j++){ if (norm(els[j].innerText).indexOf(w) === 0 && els[j].getBoundingClientRect().height>4){hit=els[j];break} }
      out.paras.push(hit?box(hit):null);
    }
    var h1 = document.querySelector('h1'); if (h1) out.title = box(h1);
    out.page_h = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);
    var pre = document.createElement('pre'); pre.id='__ccut_pos'; pre.style.cssText='position:absolute;left:0;top:0;width:1px;height:1px;overflow:hidden';
    pre.textContent = JSON.stringify(out); document.body.appendChild(pre);
  }
  if (document.readyState === 'complete') go(); else window.addEventListener('load', go);
})();
</script>"""


def _local_copy(html_text: str, url: str, want: list[str]) -> Path:
    """bản trang cục bộ để chụp + đo: bỏ script của trang (quảng cáo, popup), ảnh lười tải → tải luôn, base = trang gốc."""
    h = re.sub(r"<script\b(?![^>]*ld\+json)[^>]*>.*?</script>", "", html_text, flags=re.S | re.I)
    h = re.sub(r"<noscript\b[^>]*>(.*?)</noscript>", r"\1", h, flags=re.S | re.I)
    h = re.sub(r'\s(?:data-src|data-original|data-lazy-src)="([^"]+)"', r' src="\1"', h)
    h = re.sub(r'\sdata-srcset="([^"]+)"', r' srcset="\1"', h)
    h = re.sub(r'\sloading="lazy"', "", h)
    base = f'<base href="{_html.escape(url)}">'
    h = re.sub(r"<head([^>]*)>", lambda m: f"<head{m.group(1)}>{base}", h, count=1, flags=re.I) if re.search(r"<head", h, re.I) else base + h
    js = MEASURE_JS.replace("__WANT__", json.dumps(want, ensure_ascii=False))
    h = re.sub(r"</body>", lambda _m: js + "</body>", h, count=1, flags=re.I) if re.search(r"</body>", h, re.I) else h + js
    f = Path(tempfile.mkdtemp()) / "trang.html"
    f.write_text(h, encoding="utf-8")
    return f


def _norm_js(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()[:80]


def pageshots(pdir, a: dict, html_text: str | None = None, width: int = 1280) -> dict:
    """ảnh chụp trang báo THẬT + vị trí từng đoạn → assets_web/_bao/trang.jpg, dau_trang.jpg (tiêu đề + sapo + ảnh chính),
    doan_NN.jpg (vùng quanh đoạn NN, đoạn đang nói tô dạ quang) — để phóng vào đúng đoạn đang nói."""
    import cv2
    import numpy as np
    from .brandkit import _chrome
    pdir = Path(pdir)
    d = pdir / "assets_web" / "_bao"
    d.mkdir(parents=True, exist_ok=True)
    html_text = html_text or _get(a["url"])[0]
    want = [_norm_js(p["text"]) for p in a["paragraphs"]]
    local = _local_copy(html_text, a["url"], want)
    ch = _chrome()
    r = subprocess.run([ch, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},1000",
                        "--virtual-time-budget=9000", f"--user-agent={UA}", "--dump-dom", local.as_uri()],
                       capture_output=True, timeout=120)
    m = re.search(r'<pre id="__ccut_pos"[^>]*>(.*?)</pre>', r.stdout.decode("utf-8", "replace"), re.S)
    if not m:
        raise ArticleError("không đo được vị trí các đoạn trên trang (bỏ qua ảnh chụp trang)")
    pos = json.loads(_html.unescape(m.group(1)))
    H = int(min(max(pos.get("page_h") or 3000, 1200), 12000))
    shot = d / "trang.png"
    subprocess.run([ch, "--headless", "--disable-gpu", "--hide-scrollbars", f"--window-size={width},{H}",
                    "--force-device-scale-factor=2",                    # chữ nét khi phóng vào đoạn đang nói
                    "--virtual-time-budget=9000", f"--user-agent={UA}", f"--screenshot={shot}", local.as_uri()],
                   capture_output=True, timeout=240)
    img = cv2.imread(str(shot))
    if img is None:
        raise ArticleError("không chụp được trang")
    ih, iw = img.shape[:2]
    ds = iw / width                                                    # toạ độ đo theo px CSS → px ảnh
    sc = lambda b: [int(round(v * ds)) for v in b] if b else None      # noqa: E731
    pos["paras"] = [sc(b) for b in pos["paras"]]
    pos["title"] = sc(pos.get("title"))
    cv2.imwrite(str(d / "trang.jpg"), img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    shot.unlink(missing_ok=True)
    boxes = [b for b in pos["paras"] if b]
    col = (min(b[0] for b in boxes), max(b[0] + b[2] for b in boxes)) if boxes else (int(iw * 0.2), int(iw * 0.8))
    pad = int((col[1] - col[0]) * 0.14)                                 # lề rộng: camera phóng vào không cắt mất chữ mép
    cx0, cx1 = max(0, col[0] - pad), min(iw, col[1] + pad)
    cw = cx1 - cx0
    ch_ = int(cw * 0.72)                                        # khung ảnh ~ tỉ lệ khối ảnh của kit (dọc 0,72 · ngang 0,6)
    out = {"page": "assets_web/_bao/trang.jpg", "w": iw, "h": ih, "paras": []}
    t = pos.get("title")
    if t:                                                        # đầu trang: tiêu đề + sapo + ảnh chính
        y0 = max(0, t[1] - int(60 * ds))
        crop = img[y0:min(ih, y0 + ch_), cx0:cx1]
        cv2.imwrite(str(d / "dau_trang.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        out["head"] = "assets_web/_bao/dau_trang.jpg"
    for i, b in enumerate(pos["paras"]):
        if not b or b[3] <= 0 or b[1] + b[3] > ih:
            out["paras"].append(None)
            continue
        x, y, w, h = b
        top = int(min(max(0, y + h / 2 - ch_ / 2), max(0, ih - ch_)))
        crop = img[top:top + ch_, cx0:cx1].copy()
        # tô dạ quang đoạn đang nói (nhân màu → chữ vẫn đen rõ) + vạch nhấn bên trái
        m_ = int(8 * ds)
        ry0, ry1 = int(y - top - m_), int(y - top + h + m_)
        rx0, rx1 = int(x - cx0 - m_ * 1.5), int(x - cx0 + w + m_ * 1.5)
        ry0, ry1 = max(0, ry0), min(crop.shape[0], ry1)
        rx0, rx1 = max(0, rx0), min(crop.shape[1], rx1)
        reg = crop[ry0:ry1, rx0:rx1].astype(np.float32)
        crop[ry0:ry1, rx0:rx1] = (reg * np.array([0.55, 0.93, 1.0], np.float32)).astype(np.uint8)   # BGR: vàng nhạt
        cv2.rectangle(crop, (max(0, rx0 - int(14 * ds)), ry0), (max(0, rx0 - int(7 * ds)), ry1), (0, 140, 255), -1)
        f = d / f"doan_{i + 1:02d}.jpg"
        cv2.imwrite(str(f), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
        out["paras"].append({"file": f"assets_web/_bao/{f.name}", "box": [x, y, w, h],
                             "focus": [round((x + w / 2 - cx0) / cw, 3), round((y + h / 2 - top) / ch_, 3)]})
    return out


def prepare(pdir, url: str | None = None, a: dict | None = None, log=print) -> dict:
    """article.json + ảnh trong bài (news_*.jpg) + ảnh chụp trang + logo báo → assets_web/. Trả article dict."""
    pdir = Path(pdir)
    aw = pdir / "assets_web"
    aw.mkdir(parents=True, exist_ok=True)
    html_text = None
    if a is None:
        log(f"Đọc bài báo: {url}")
        a = fetch(url)
    srcs_f = aw / "illus_sources.json"
    srcs = json.loads(srcs_f.read_text(encoding="utf-8")) if srcs_f.exists() else {}
    if a.get("image") and _download(a["image"], aw / "news_chinh.jpg"):
        a["image_file"] = "assets_web/news_chinh.jpg"
        srcs["news_chinh.jpg"] = f"{a.get('source', '')} · {a['url']}"
        (aw / "_bao").mkdir(parents=True, exist_ok=True)              # bản dùng cho thumbnail (phần khuôn, không tính lượt dùng ảnh)
        (aw / "_bao" / "anh_chinh.jpg").write_bytes((aw / "news_chinh.jpg").read_bytes())
        a["thumb_file"] = "assets_web/_bao/anh_chinh.jpg"
    main_key = re.sub(r"\?.*$", "", a.get("image") or "").rsplit("/", 1)[-1]
    a["images"] = [im for im in a.get("images", []) if not main_key or re.sub(r"\?.*$", "", im["url"]).rsplit("/", 1)[-1] != main_key]
    def thumb(f):
        import cv2
        im = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
        return None if im is None else cv2.resize(im, (160, max(8, int(im.shape[0] * 160 / im.shape[1]))), interpolation=cv2.INTER_AREA)

    def same(x, y) -> bool:                    # cùng ảnh dù khác cỡ / khác cách cắt (ảnh đại diện thường cắt 16:9 từ ảnh trong bài)
        import cv2
        if x is None or y is None:
            return False
        a_, b_ = (x, y) if x.shape[0] <= y.shape[0] else (y, x)
        a_ = a_[4:-4, 12:-12]
        b_ = cv2.resize(b_, (b_.shape[1], b_.shape[0]))
        if a_.shape[0] > b_.shape[0] or a_.shape[1] > b_.shape[1]:
            return False
        return float(cv2.matchTemplate(b_, a_, cv2.TM_CCOEFF_NORMED).max()) > 0.85
    seen = [thumb(aw / "news_chinh.jpg")] if a.get("image_file") else []
    keep, n = [], 0
    for im in a.get("images", []):
        f = aw / f"news_anh_{n + 1:02d}.jpg"
        if not _download(im["url"], f):
            continue
        th = thumb(f)
        if any(same(th, o) for o in seen):
            f.unlink(missing_ok=True)
            continue
        seen.append(th); n += 1
        im["file"] = f"assets_web/{f.name}"
        srcs[f.name] = f"{a.get('source', '')} · {a['url']}"
        keep.append(im)
    a["images"] = keep
    if a.get("url") and not a.get("pasted"):
        try:
            log("Chụp trang bài báo")
            a["page"] = pageshots(pdir, a, html_text)
            for k in ("trang.jpg", "dau_trang.jpg"):
                srcs[f"_bao/{k}"] = a["url"]
        except Exception as e:
            log(f"Không chụp được trang báo: {e}")
    if a.get("source") and a.get("url"):
        try:
            from . import brandkit as BK
            host = urllib.parse.urlparse(a["url"]).netloc.removeprefix("www.")
            lg = BK.logo(pdir, a["source"], host)
            a["logo"] = str(Path(lg).relative_to(pdir)) if Path(lg).is_absolute() else str(lg)
        except Exception as e:
            log(f"Không lấy được logo {a.get('source')}: {e}")
    srcs_f.write_text(json.dumps(srcs, ensure_ascii=False, indent=1), encoding="utf-8")
    (pdir / "article.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    _sheet(pdir, a)
    return a


def _sheet(pdir, a):
    """ảnh xem nhanh tư liệu bài báo (Claude Read để chọn): ảnh chính, ảnh trong bài, đầu trang, vài đoạn."""
    import cv2
    import numpy as np
    pdir = Path(pdir)
    files = [a.get("image_file")] + [im.get("file") for im in a.get("images", [])] + [(a.get("page") or {}).get("head")] + \
            [p["file"] for p in ((a.get("page") or {}).get("paras") or []) if p][:6]
    tiles = []
    for f in [x for x in files if x]:
        im = cv2.imread(str(pdir / f))
        if im is None:
            continue
        h = 220
        im = cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h))[:, :400]
        im = cv2.copyMakeBorder(im, 26, 4, 4, 4, cv2.BORDER_CONSTANT, value=(20, 20, 20))
        cv2.putText(im, Path(f).name, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 220, 255), 1)
        im = cv2.copyMakeBorder(im, 0, 0, 0, 408 - im.shape[1], cv2.BORDER_CONSTANT, value=(20, 20, 20))
        tiles.append(im)
    if not tiles:
        return
    rows = [tiles[i:i + 4] for i in range(0, len(tiles), 4)]
    rows[-1] += [np.full_like(tiles[0], 20)] * (4 - len(rows[-1]))
    out = pdir / "assets_web" / "_bao" / "sheet.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), np.vstack([np.hstack(r) for r in rows]), [cv2.IMWRITE_JPEG_QUALITY, 85])


def _tok_norm(w: str) -> str:
    w = unicodedata.normalize("NFC", w.lower())
    return re.sub(r"[^\w%]", "", w)


def retext_audio(pdir, a: dict, log=print) -> float:
    """Voice to Motion có GIỌNG ĐỌC của bài (vd bản audio của báo): chữ phụ đề lấy theo chữ trong bài (tên riêng, số, chính tả),
    giữ mốc thời gian của bản chép lời. Giọng đọc tóm tắt khác bài → chỉ sửa những chỗ khớp (cụm ≤ 6 từ kẹp giữa hai đoạn khớp).
    Trả tỉ lệ từ khớp với bài."""
    import difflib
    pdir = Path(pdir)
    f = pdir / "transcript.json"
    tr = json.loads(f.read_text(encoding="utf-8"))
    words = tr.get("words") or []
    art = []
    for tok in " ".join([a.get("title", ""), a.get("sapo", ""), body_text(a)]).split():
        if art and not re.search(r"\w", tok):                    # dấu đứng riêng (“-”, “–”) → dính vào từ trước, không thành “từ”
            art[-1] += " " + tok if tok in "-–—" else tok
        else:
            art.append(tok)
    if not words or not art:
        return 0.0
    A_ = [_tok_norm(w["text"]) for w in words]
    B_ = [_tok_norm(w) for w in art]
    sm = difflib.SequenceMatcher(None, A_, B_, autojunk=False)
    new = [dict(w) for w in words]
    hit = 0
    ops = sm.get_opcodes()
    for k, (op, i1, i2, j1, j2) in enumerate(ops):
        if op == "equal":
            for d in range(i2 - i1):
                new[i1 + d]["text"] = art[j1 + d]
                hit += 1
        elif op == "replace" and 0 < i2 - i1 <= 6 and 0 < j2 - j1 <= 6 and 0 < k < len(ops) - 1 \
                and ops[k - 1][0] == "equal" and ops[k + 1][0] == "equal":
            t0, t1 = words[i1]["start"], words[i2 - 1]["end"]
            n = j2 - j1
            seg = [(t0 + (t1 - t0) * q / n, t0 + (t1 - t0) * (q + 1) / n) for q in range(n)]
            rep = [{**words[i1], "text": art[j1 + q], "start": round(seg[q][0], 3), "end": round(seg[q][1], 3), "conf": 0.8}
                   for q in range(n)]
            new[i1] = rep                                   # cụm thay thế đặt ở ô đầu, các ô còn lại bỏ (chỉ số không lệch)
            for q in range(1, i2 - i1):
                new[i1 + q] = None
    out = []
    for w in new:
        if w is None:
            continue
        out.extend(w if isinstance(w, list) else [w])
    ratio = hit / max(len(words), 1)
    if ratio < 0.3:
        log(f"Giọng đọc chỉ khớp {ratio:.0%} chữ trong bài → giữ chữ chép lời")
        return ratio
    for i, w in enumerate(out):
        w["i"] = i
    sl = []
    for s in tr.get("sentences") or []:
        ws = [w["text"] for w in out if s["start"] - 0.01 <= w["start"] < s["end"] + 0.01]
        sl.append({**s, "text": " ".join(ws) or s.get("text", "")})
    (pdir / "transcript_asr.json").write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    tr.update(words=out, sentences=sl or tr.get("sentences"), text_from="article")
    f.write_text(json.dumps(tr, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"Phụ đề theo chữ bài báo (khớp {ratio:.0%} lời đọc)")
    return ratio


def summary(a: dict) -> str:
    n = len(a.get("paragraphs", []))
    words = len(body_text(a).split())
    return (f"{a.get('source')} · {a.get('date') or 'không rõ ngày'} · “{a.get('title')}” · {n} đoạn / {words} từ · "
            f"{len(a.get('images', []))} ảnh trong bài" + (f" · tương tác {a['interaction']}" if a.get("interaction") else ""))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "fetch":
        try:
            a = fetch(sys.argv[2])
        except ArticleError as e:
            raise SystemExit(f"LỖI: {e}")
        print(summary(a))
        print("SAPO:", a["sapo"])
        for i, p in enumerate(a["paragraphs"], 1):
            print(f"{i:02d}. {p['text'][:160]}")
        return
    if len(sys.argv) >= 4 and sys.argv[1] == "prepare":
        try:
            a = prepare(sys.argv[2], sys.argv[3])
        except ArticleError as e:
            raise SystemExit(f"LỖI: {e}")
        print(summary(a))
        print(f"{sys.argv[2]}/article.json · ảnh xem nhanh {sys.argv[2]}/assets_web/_bao/sheet.jpg")
        return
    print(__doc__)


if __name__ == "__main__":
    main()
