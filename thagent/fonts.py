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
