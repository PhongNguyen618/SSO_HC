@echo off
echo ===================================================
echo   SSO_HC Sport Web App - Setup Environment
echo ===================================================
echo.

echo [1/3] Khoi tao moi truong ao Python (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi tao venv! Vui long kiem tra xem Python da duoc cai dat chua.
    pause
    exit /b %errorlevel%
)

echo [2/3] Dang cai dat cac thu vien tu requirements.txt...
.venv\Scripts\pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi cai dat cac thu vien.
    pause
    exit /b %errorlevel%
)

echo [3/3] Dang khoi tao co so du lieu SQLite...
.venv\Scripts\python backend\database.py
if %errorlevel% neq 0 (
    echo [ERROR] Loi khi khoi tao co so du lieu SQLite.
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo   Cai dat thanh cong! Nhan nut bat ky de thoat.
echo   Sau do hay chay file run.bat de khoi dong server.
echo ===================================================
pause
