@echo off
chcp 65001 >nul
echo ========================================================
echo       抖音专属好友风格化自动回复 Bot 启动器
echo ========================================================
echo.
echo 正在检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10+ 并勾选 Add to PATH。
    pause
    exit /b 1
)

echo 正在启动 Web 控制台与后台守护进程...
echo 访问地址: http://127.0.0.1:8000
echo 按 Ctrl + C 可终止程序。
echo.
python -X utf8 server.py
pause
