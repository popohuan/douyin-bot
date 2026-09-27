#!/bin/bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

echo "========================================================"
echo "      抖音专属好友风格化自动回复 Bot 启动器 (Linux)"
echo "========================================================"

if ! command -v python3 &> /dev/null; then
    echo "[错误] 未检测到 python3，请先安装 Python 3.10+"
    exit 1
fi

echo "正在启动后台服务..."
echo "访问地址: http://0.0.0.0:8000"
echo "按 Ctrl + C 可终止。"
echo ""

python3 -X utf8 server.py
