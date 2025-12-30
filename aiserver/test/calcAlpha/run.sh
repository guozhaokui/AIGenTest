#!/bin/bash
# Alpha计算服务启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 默认端口
PORT=${1:-5000}
HOST=${2:-0.0.0.0}

echo "========================================"
echo "启动 Alpha计算服务"
echo "端口: $PORT"
echo "========================================"

# 启动服务
python alpha_server.py --host "$HOST" --port "$PORT"

