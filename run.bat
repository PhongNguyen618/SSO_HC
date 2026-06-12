@echo off
echo ===================================================
echo   SSO_HC Sport Web App - Start Server
echo ===================================================
echo.
echo Dang khoi dong Web Server...
echo Sau khi server khoi dong thanh cong, hay truy cap:
echo http://127.0.0.1:8000
echo.
echo ===================================================
echo.

.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Web Server bi tat hoac gap loi khi khoi chay.
    pause
)
