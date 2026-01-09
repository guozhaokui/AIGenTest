#!/bin/bash
# 停止 LTX-2 服务

echo "停止 LTX-2 视频生成服务..."
pkill -f "ltx2_server.py"
echo "已停止"

