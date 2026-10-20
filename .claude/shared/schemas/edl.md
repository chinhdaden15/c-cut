# edl.json — ghép nhiều đoạn thành 1 video (Talking Head)

(Tự sinh từ thagent/clips.py — không sửa tay.)

```
Dự án nhiều đoạn (TH2): nhiều file quay → 1 video, ghép theo kịch bản.

1. analyze(): mỗi đoạn → chép lời từng từ + mặt/hướng nhìn mỗi 0.5s + ảnh tổng hợp → projects/<id>/clips/
2. Claude viết projects/<id>/edl.json (thứ tự câu, take, b-roll, đoạn chỉ lấy tiếng).
3. validate() + assemble(): ghép bản thô 1080x1920@30 (zoom nhẹ ở chỗ nối khác góc), transcript ánh xạ sẵn,
   covers.json = các khoảng hình b-roll / cần Motion Graphics trên timeline mới.

edl.json:
{"ready": true,
 "segments": [{"clip": "IMG_1.MOV", "in": 12.3, "out": 18.9, "line": "câu kịch bản", "cam": true,
               "broll": [{"clip": "IMG_7.MOV", "in": 2.0, "at": 1.5, "dur": 3.0, "desc": "hồ bơi"}],
               "cover": [{"at": 4.5, "dur": 2.4, "desc": "MG: 3 tiện ích"}]}],
 "notes": "..."}
- in/out: giây trong file đoạn nói. at: giây tính từ đầu segment. cam=false → phải che kín bằng broll/cover.
```
