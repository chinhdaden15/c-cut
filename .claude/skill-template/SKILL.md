---
name: {{slug}}
version: 1.0.0
description: {{description}}
---

# {{name}}

**Phiên bản 1.0.0** — tạo bằng `python -m thagent.newskill`.

## Nhiệm vụ

{{description}}

(Viết quy trình riêng của skill ở đây: đầu vào, các bước, quy tắc nội dung, đầu ra, cách tự kiểm.)

## Công cụ dựng dùng chung (app tự cấp — KHÔNG chép tài liệu/runtime vào skill)

App gắn danh sách công cụ dựng dùng chung (vd HyperFrames) vào phiên agent của MỌI skill video, kèm trạng thái sẵn sàng.
Xem bản đang có: `.venv/bin/python -m thagent.capabilities {{slug}}`. Hướng dẫn chung nằm ở `.claude/shared/` (dùng chung mọi skill).
- Chỉ ghi ở đây cách skill NÀY dùng công cụ cho hợp (ghi ngắn trong style.json → "tool_notes": {"hyperframes": "…"}).
- Không bắt mọi việc chạy qua một công cụ: ASR, cắt lời, âm thanh, tracking, tách nền, AI tạo voice/ảnh/video, geo → công cụ riêng của app.
- Công cụ chưa sẵn sàng → phương án tương đương; không có → báo rõ phần bị chặn. Không âm thầm bỏ hiệu ứng.
- Skill không phải video: style.json "video": false. Giới hạn công cụ: "shared_tools": ["hyperframes"].

## Bàn giao

Ghi `{pdir}/result.json` = {"ok", "outputs", "checked", "blocked"} — chỉ ghi đã kiểm những gì thực sự kiểm.
