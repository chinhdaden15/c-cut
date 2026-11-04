"""Font theo ngôn ngữ của dự án (mọi skill): chữ Latin/Việt dùng font của style; chữ viết khác (Trung, Nhật, Hàn, Thái, Ả Rập,
Hindi, Nga…) tự đổi sang họ font Noto (Google Fonts, giấy phép OFL — dùng thương mại miễn phí), tải 1 lần khi dự án cần.

- Ngôn ngữ dự án: {thư mục dự án}/language.json {"language": "zh"} — app ghi khi chép lời (Whisper tự nhận).
  use_project(pdir) đặt ngôn ngữ cho các lệnh dựng (biến môi trường CCUT_LANG, lệnh con kế thừa).
- pick(tên font, độ đậm) → (đường dẫn font vẽ được chữ đó, độ đậm) — các bộ vẽ chữ (typography, neon, v2m) gọi.
- clean(text): ngôn ngữ không cách chữ (Trung, Nhật, Thái, Lào, Khmer, Myanmar) → bỏ dấu cách giữa các chữ khi VẼ
  (dữ liệu vẫn tách theo từ để ngắt dòng, căn mốc thời gian).
- css(): font dự phòng + @font-face cho HyperFrames (trình duyệt tự chọn font theo từng ký tự).
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from pathlib import Path

from .paths import ROOT

NOTO_DIR = ROOT / "assets" / "fonts" / "noto"
_CJK = "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/{k}/NotoSans{k}-{w}.otf"
_NOTO = "https://github.com/notofonts/notofonts.github.io/raw/main/fonts/{f}/hinted/ttf/{f}-{w}.ttf"

# ngôn ngữ → họ font Noto (None = font của style đã đủ: Latin + tiếng Việt)
SCRIPT = {
    "zh": ("cjk", "SC"), "yue": ("cjk", "TC"), "ja": ("cjk", "JP"), "ko": ("cjk", "KR"),
    "th": ("noto", "NotoSansThai"), "lo": ("noto", "NotoSansLao"), "km": ("noto", "NotoSansKhmer"), "my": ("noto", "NotoSansMyanmar"),
    "ar": ("noto", "NotoSansArabic"), "fa": ("noto", "NotoSansArabic"), "ur": ("noto", "NotoSansArabic"), "ps": ("noto", "NotoSansArabic"),
    "he": ("noto", "NotoSansHebrew"), "yi": ("noto", "NotoSansHebrew"),
    "hi": ("noto", "NotoSansDevanagari"), "mr": ("noto", "NotoSansDevanagari"), "ne": ("noto", "NotoSansDevanagari"),
    "sa": ("noto", "NotoSansDevanagari"), "bn": ("noto", "NotoSansBengali"), "as": ("noto", "NotoSansBengali"),
    "ta": ("noto", "NotoSansTamil"), "te": ("noto", "NotoSansTelugu"), "kn": ("noto", "NotoSansKannada"), "ml": ("noto", "NotoSansMalayalam"),
    "gu": ("noto", "NotoSansGujarati"), "pa": ("noto", "NotoSansGurmukhi"), "si": ("noto", "NotoSansSinhala"),
    "ka": ("noto", "NotoSansGeorgian"), "hy": ("noto", "NotoSansArmenian"), "am": ("noto", "NotoSansEthiopic"),
    "bo": ("noto", "NotoSerifTibetan"),
    # Cyrillic, Hy Lạp: Noto Sans (đủ Latin + Cyrillic + Greek)
    **{k: ("noto", "NotoSans") for k in ("ru", "uk", "be", "bg", "sr", "mk", "kk", "ky", "tg", "mn", "ba", "tt", "el")},
}
NOSPACE = {"zh", "yue", "ja", "th", "lo", "km", "my", "bo"}
RTL = {"ar", "fa", "ur", "ps", "he", "yi"}
_NS = r"฀-໿က-႟ក-៿ༀ-࿿　-ヿ㐀-鿿豈-﫿＀-￯"
_NS_GAP = re.compile(rf"(?<=[{_NS}]) +(?=[{_NS}])")


def current() -> str:
    return (os.environ.get("CCUT_LANG") or "vi").lower()


def set_language(pdir, lang: str | None) -> None:
    """ghi ngôn ngữ dự án (sau khi chép lời) + tải font nếu cần."""
    lang = (lang or "vi").lower()
    Path(pdir).mkdir(parents=True, exist_ok=True)
    (Path(pdir) / "language.json").write_text(json.dumps({"language": lang}), encoding="utf-8")
    os.environ["CCUT_LANG"] = lang
    try:
        ensure(lang)
    except Exception:
        pass


def use_project(pdir) -> str:
    try:
        lang = json.loads((Path(pdir) / "language.json").read_text(encoding="utf-8")).get("language") or "vi"
    except Exception:
        lang = "vi"
    os.environ["CCUT_LANG"] = lang
    if lang in SCRIPT:
        try:
            ensure(lang)
        except Exception:
            pass
    try:                                       # Review: font người dùng chọn trong app (1 font cho cả clip)
        fid = json.loads((Path(pdir) / "review" / "options.json").read_text(encoding="utf-8")).get("font") or ""
    except Exception:
        fid = ""
    fp = font_path(fid)
    if fp:
        os.environ["CCUT_FONT"] = str(fp)
    else:
        os.environ.pop("CCUT_FONT", None)
    return lang


def _files(lang: str) -> list[tuple[str, Path]]:
    kind, k = SCRIPT[lang]
    out = []
    for w in ("Regular", "Bold"):
        if kind == "cjk":
            out.append((_CJK.format(k=k, w=w), NOTO_DIR / f"NotoSans{k}-{w}.otf"))
        else:
            out.append((_NOTO.format(f=k, w=w), NOTO_DIR / f"{k}-{w}.ttf"))
    return out


def ensure(lang: str) -> list[Path]:
    if lang not in SCRIPT:
        return []
    NOTO_DIR.mkdir(parents=True, exist_ok=True)
    got = []
    for url, f in _files(lang):
        if not f.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "C-Cut"})
            tmp = f.with_suffix(f.suffix + ".part")
            tmp.write_bytes(urllib.request.urlopen(req, timeout=120).read())
            tmp.replace(f)
        got.append(f)
    return got


def _bold(fname: str, wght) -> bool:
    return bool((wght and wght >= 600) or re.search(r"bold|black|heavy|semibold|extra", fname, re.I)
                or re.search(r"montserrat|anton", fname, re.I))


def pick(path: str | Path, wght=None) -> tuple[str, object]:
    """font của style → font vẽ được chữ của ngôn ngữ dự án (Noto) nếu cần; giữ nguyên với tiếng Việt / Latin."""
    lang = current()
    if lang not in SCRIPT:
        return str(path), wght
    reg, bold = [f for _, f in _files(lang)]
    want = bold if _bold(Path(path).name, wght) else reg
    if not want.exists():
        try:
            ensure(lang)
        except Exception:
            return str(path), wght
    return str(want), None


def clean(text: str) -> str:
    """bỏ dấu cách giữa các chữ của ngôn ngữ không cách chữ (dữ liệu tách theo từ, khi vẽ thì liền)."""
    return _NS_GAP.sub("", text) if current() in NOSPACE else text


def joiner(lang: str | None = None) -> str:
    return "" if (lang or current()) in NOSPACE else " "


def css() -> tuple[list[str], list[str]]:
    """(tên họ font dự phòng, @font-face) cho trang HyperFrames của ngôn ngữ hiện tại."""
    lang = current()
    if lang not in SCRIPT:
        return [], []
    return [f"CCut Noto {lang}"], []


# ---------------- vẽ chữ: không cách chữ, phải sang trái ----------------
_DIGITS = re.compile(r"[0-9.,%:/+\-]+")
_ARABIC = {"ar", "fa", "ur", "ps"}


def complex_script() -> bool:
    """chữ cần vẽ nguyên cụm (không vẽ từng ký tự): mọi chữ viết ngoài Latin/Việt/Cyrillic/Hy Lạp."""
    lang = current()
    return lang in SCRIPT and SCRIPT[lang][1] != "NotoSans"


def rtl() -> bool:
    return current() in RTL


def shape_word(w: str) -> str:
    """một từ → dạng vẽ được: Ả Rập nối chữ + đảo thứ tự hiển thị; Do Thái đảo; số giữ trái→phải."""
    if not rtl():
        return w
    if current() in _ARABIC:
        try:
            import arabic_reshaper
            w = arabic_reshaper.reshape(w)
        except Exception:
            pass
    out = w[::-1]
    return _DIGITS.sub(lambda m: m.group(0)[::-1], out)


def shape_line(text: str) -> str:
    """cả dòng: bỏ cách chữ (Trung/Nhật/Thái…) hoặc đảo thứ tự từ + định hình (Ả Rập/Do Thái)."""
    text = clean(text)
    if not rtl():
        return text
    return "\n".join(" ".join(shape_word(w) for w in reversed(ln.split(" "))) for ln in text.split("\n"))


# ---------------- nhãn ảnh theo ngôn ngữ ----------------
LABELS = {
    "vi": ("Hình ảnh minh họa", "Hình ảnh thực tế"), "en": ("Illustrative image", "Actual image"),
    "zh": ("示意图", "实拍图"), "yue": ("示意圖", "實拍圖"), "ja": ("イメージ画像", "実際の写真"), "ko": ("참고 이미지", "실제 사진"),
    "th": ("ภาพประกอบ", "ภาพจริง"), "id": ("Gambar ilustrasi", "Gambar asli"), "ms": ("Gambar ilustrasi", "Gambar sebenar"),
    "fr": ("Image d'illustration", "Image réelle"), "de": ("Symbolbild", "Echtes Foto"), "es": ("Imagen ilustrativa", "Imagen real"),
    "pt": ("Imagem ilustrativa", "Imagem real"), "it": ("Immagine illustrativa", "Immagine reale"), "ru": ("Иллюстрация", "Реальное фото"),
    "ar": ("صورة توضيحية", "صورة حقيقية"), "hi": ("प्रतीकात्मक चित्र", "वास्तविक चित्र"), "km": ("រូបភាពឧទាហរណ៍", "រូបភាពពិត"),
    "lo": ("ຮູບປະກອບ", "ຮູບຕົວຈິງ"), "tl": ("Larawang paglalarawan", "Totoong larawan"),
}


def label(real: bool = False) -> str:
    a, b = LABELS.get(current(), LABELS["en"] if current() != "vi" else LABELS["vi"])
    return b if real else a


# ---------------- font chữ nhấn do người dùng chọn (skill Review) ----------------
# 14 font đã duyệt cho reel F&B/review. KHÔNG đóng gói kèm app (font Việt hoá, chưa rõ giấy phép):
# app chỉ hiện font nào ĐÃ CÀI trên máy; không có → Montserrat mặc định.
DISPLAY_FONTS = [
    ("gesco", "HF Gesco", "1FTV-HF-Gesco-id0oy5.ttf"), ("impact", "Impact", "UTM Impact.ttf"),
    ("bebas", "Bebas", "UTM Bebas.ttf"), ("fjalla", "Fjalla One", "SVN-Fjalla One.otf"),
    ("barlow_bi", "Barlow Condensed Black Italic", "BarlowCondensed-BlackItalic.ttf"),
    ("gilroy", "Gilroy XBold", "SVN-Gilroy XBold.otf"), ("helvetica", "Helvetica Neue Heavy", "SVN-Helvetica Neue Heavy.ttf"),
    ("avo", "Avo Bold", "UTM AvoBold.ttf"), ("heavitas", "Heavitas", "1FTV-Heavitas.otf"),
    ("trajan", "Trajan Pro Bold", "UTM Trajan Pro Bold.ttf"), ("abril", "Abril Fatface", "SVN-Abril Fatface.ttf"),
    ("ettlora", "Ettlora", "1FTV-VIP-Ettlora.ttf"), ("romalika", "Romalika", "1FTV-VIP-Romalika.otf"),
    ("josefin", "Josefin Sans Bold", "JosefinSans-Bold.ttf"),
]


CAPS_STYLE = {"trajan"}     # chữ thường là chữ hoa nhỏ (small caps) → vẫn trông IN HOA


def _font_dirs() -> list[Path]:
    h = Path.home()
    return [ROOT / "assets" / "fonts", h / "Library" / "Fonts", Path("/Library/Fonts"),
            h / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts", Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
            h / ".local" / "share" / "fonts", h / ".fonts"]


def font_path(fid: str) -> Path | None:
    f = next((x[2] for x in DISPLAY_FONTS if x[0] == fid), None)
    if not f:
        return None
    return next((d / f for d in _font_dirs() if (d / f).exists()), None)


def caps_only(path) -> bool:
    """font chỉ có chữ HOA (chữ thường vẽ ra y như chữ hoa) → chữ phụ viết thường vẫn hiện IN HOA."""
    from PIL import ImageFont
    f = ImageFont.truetype(str(path), 80)
    m = lambda c: (f.getbbox(c), bytes(f.getmask(c)))
    return all(m(c) == m(c.upper()) for c in "aegn")


def display_fonts() -> list[dict]:
    out = []
    for fid, name, _ in DISPLAY_FONTS:
        p = font_path(fid)
        if p:
            try:
                co = caps_only(p)
            except Exception:
                continue
            out.append({"id": fid, "name": name, "caps_only": co or fid in CAPS_STYLE})
    return out


def display() -> str | None:
    """đường dẫn font chữ nhấn của dự án (None = font mặc định của style)."""
    p = os.environ.get("CCUT_FONT")
    return p if p and Path(p).exists() else None


def preview_png(fid: str) -> bytes:
    """ảnh mẫu: chữ nhấn IN HOA "CẢM ƠN" + chữ phụ viết thường "đây là C-Cut"."""
    import io
    from PIL import Image, ImageDraw, ImageFont
    p = font_path(fid)
    if not p:
        raise FileNotFoundError(fid)
    im = Image.new("RGB", (720, 250), (24, 24, 28))
    d = ImageDraw.Draw(im)
    big, small = ImageFont.truetype(str(p), 92), ImageFont.truetype(str(p), 46)
    for (x, y, t, f, c) in ((360, 95, "CẢM ƠN", big, (255, 200, 50)), (360, 178, "đây là C-Cut", small, (255, 255, 255))):
        w = f.getlength(t)
        if w > 680:
            f = ImageFont.truetype(str(p), int(f.size * 680 / w)); w = f.getlength(t)
        d.text((x - w / 2 + 3, y + 4), t, font=f, fill=(0, 0, 0), anchor="ls")
        d.text((x - w / 2, y), t, font=f, fill=c, anchor="ls")
    b = io.BytesIO(); im.save(b, "PNG")
    return b.getvalue()
