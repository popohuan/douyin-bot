@echo off
chcp 65001 >nul
title 抖音账号扫码登录向导 (弹窗浏览器模式)

echo ============================================================
echo         抖音账号扫码登录向导 (弹窗浏览器模式)
echo ============================================================
echo.
echo 正在拉起 Chrome 浏览器并唤起登录二维码...
echo.

python -X utf8 login_browser.py

echo.
pause
