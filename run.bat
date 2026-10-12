@echo off
REM Mở Talking Head Agent (Windows): tự cài phần còn thiếu rồi chạy UI tại http://127.0.0.1:8765
cd /d "%~dp0"
set "PATH=%CD%\bin;%PATH%"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe kit\install.py --check >nul 2>&1 || py -3.11 kit\install.py || python kit\install.py
) else (
  py -3.11 kit\install.py || python kit\install.py
)
if errorlevel 1 ( echo Cai dat chua xong - xem kit\.installed.json & pause & exit /b 1 )
.venv\Scripts\python.exe -m uvicorn thagent.server:app --host 127.0.0.1 --port 8765
