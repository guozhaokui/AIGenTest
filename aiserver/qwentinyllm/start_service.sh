#!/bin/bash

echo "========================================"
echo "  Qwen3 Tiny LLM 服务启动脚本"
echo "========================================"
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "[错误] 未找到虚拟环境"
    echo "请先运行: python -m venv venv"
    echo "然后运行: source venv/bin/activate"
    echo "最后安装依赖: pip install -r requirements.txt"
    exit 1
fi

# 激活虚拟环境
echo "[1/2] 激活虚拟环境..."
source venv/bin/activate

# 启动服务
echo "[2/2] 启动服务..."
echo ""
python service.py
