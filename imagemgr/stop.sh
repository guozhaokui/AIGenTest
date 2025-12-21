#!/bin/bash
# 图片管理服务停止脚本

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "  图片管理服务停止脚本"
echo "======================================"

if pgrep -f "api_server.py" > /dev/null; then
    echo -e "${YELLOW}停止图片管理服务...${NC}"
    pkill -f "api_server.py"
    sleep 2
    echo -e "${GREEN}✓ 已停止${NC}"
else
    echo "图片管理服务未运行"
fi

