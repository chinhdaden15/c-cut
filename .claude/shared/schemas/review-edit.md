# review/edit.json — bản dựng Review

(Tự sinh từ thagent/review/edit.py — không sửa tay.)

```
Review Editor — bản dựng (edit.json): mạch review tham chiếu tới nguồn, không đụng file gốc.

{
 "category": "bds" | "san_pham",  "style": "tour" | "truc_tiep" | "tinh_te",  "intensity": "nhe" | "can_bang" | "nang_dong",
 "formats": ["9x16", "16x9"],  "fps": 30,  "subtitles": true,  "target_s": null,
 "music": {"src": "assets/…mp3", "gain_db": -20}            (tuỳ chọn; tự giảm khi có lời)
 "segments": [
   {"id": "S01", "src": "F05", "in": 12.30, "out": 18.70, "role": "talk" | "broll" | "action",
    "say": "ý đang nói", "why": "lý do chọn", "take": "G03/T2",           (nhóm take + take được chọn)
    "j": 0.0, "l": 0.0,                       J-cut: tiếng đoạn này vào sớm j giây; L-cut: tiếng đoạn TRƯỚC kéo dài l giây sang đoạn này
    "audio": "voice" | "nat" | "mute",  "nat_db": -14,
    "crop": {"9x16": {"cx": 0.5, "cy": 0.42, "zoom": 1.0, "fit": "crop" | "blur"}, "16x9": {…}},   (thiếu → tự tính theo mặt/giữa)
    "cutaways": [{"src": "F02", "in": 3.0, "at": 1.2, "dur": 2.5, "kind": "full" | "pip", "why": "nói đầu nối → cận đầu nối",
                  "crop": {…}, "nat_db": null}],
    "texts": [{"role": "info" | "emph", "text": "…", "sub": "dòng nhỏ", "at": 0.4, "dur": 3.0, "hl": "cụm tô màu"}]}
 ],
 "replace": {"Seacatch": "C-Cut"},  "fixes": [{"src": "F05", "t": 3.04, "to": "C-Cut"}],   (sửa chữ chép sai trên PHỤ ĐỀ)
 "missing": ["thiếu cảnh mặt tiền", …],  "notes": "…"
}
- in/out: giây trong file nguồn.  at: giây tính từ đầu đoạn (segment).  Phụ đề tự sinh từ lời của đoạn talk (subtitles=true).
```
