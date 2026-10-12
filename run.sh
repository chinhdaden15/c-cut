#!/bin/zsh
# Mở C-Cut (macOS): tự cài phần còn thiếu, tắt bản C-Cut cũ đang chạy (nếu có), rồi chạy UI tại http://127.0.0.1:8765
cd "$(dirname "$0")"
export PATH="$PWD/bin:$PATH"
PY=python3
.venv/bin/python kit/install.py --check >/dev/null 2>&1 || $PY kit/install.py || { echo "Cài đặt chưa xong — xem kit/.installed.json"; exit 1; }
OLD=$(lsof -t -nP -iTCP:8765 -sTCP:LISTEN 2>/dev/null)
if [ -n "$OLD" ]; then
  if ps -o command= -p $OLD | grep -q "thagent.server"; then
    echo "Tắt C-Cut cũ đang chạy (PID $OLD)…"; kill $OLD; sleep 2
  else
    echo "Cổng 8765 đang bị chương trình khác dùng (PID $OLD). Tắt chương trình đó rồi chạy lại."; exit 1
  fi
fi
echo "C-Cut đang chạy — mở http://127.0.0.1:8765 (Ctrl+C để tắt)"
( sleep 2; open "http://127.0.0.1:8765" ) &
exec .venv/bin/python -m uvicorn thagent.server:app --host 127.0.0.1 --port 8765 --log-level warning
