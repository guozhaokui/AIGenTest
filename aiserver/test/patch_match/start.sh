#!/bin/bash
# 启动 Patch Match 可视化服务

cd "$(dirname "$0")"

# 激活 conda 环境
source /mnt/hdd/anaconda3/bin/activate hidream

echo "Starting Patch Match Visualization Server..."
echo "Open http://localhost:6080 in your browser"

python server.py

