#!/bin/bash
set -e

echo "=================================================="
echo "    抖音专属好友自动回复 Bot - VPS 一键环境初始化"
echo "=================================================="

# 1. 检测系统包管理器并安装基础依赖
if command -v apt-get >/dev/null 2>&1; then
    echo "[*] 检测到 Debian/Ubuntu 系统，正在更新并安装 Python3 及基础库..."
    sudo apt-get update -y
    sudo apt-get install -y python3 python3-pip python3-venv curl wget
elif command -v yum >/dev/null 2>&1; then
    echo "[*] 检测到 CentOS/RHEL 系统..."
    sudo yum update -y
    sudo yum install -y python3 python3-pip curl wget
fi

# 2. 创建并激活 Python 独立虚拟环境 (避免系统包环境冲突)
if [ ! -d "venv" ]; then
    echo "[*] 正在创建 Python 虚拟环境 (venv)..."
    python3 -m venv venv
fi

echo "[*] 激活虚拟环境..."
source venv/bin/activate

# 3. 安装项目依赖
echo "[*] 正在安装 Python 依赖项..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. 安装 Playwright 浏览器内核及其在 Linux 下的完整系统依赖 (至关重要)
echo "[*] 正在下载 Chromium 及 Linux 系统底层渲染库 (可能需要 1~2 分钟)..."
python -m playwright install --with-deps chromium

echo "=================================================="
echo "[+] 环境初始化完成！"
echo "[*] 你可以通过运行以下命令直接启动管理面板："
echo "    source venv/bin/activate && python server.py"
echo "=================================================="
