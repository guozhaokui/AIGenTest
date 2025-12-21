#!/bin/bash
# AIGenTest 服务状态查看脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         AIGenTest 服务状态               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

check_service() {
    local name=$1
    local port=$2
    local endpoint=${3:-/health}
    
    printf "%-20s" "$name"
    
    if curl -s --max-time 2 "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}● 运行中${NC}  端口: $port"
        return 0
    else
        if lsof -i:$port > /dev/null 2>&1; then
            echo -e "${YELLOW}◐ 启动中${NC}  端口: $port"
        else
            echo -e "${RED}○ 未运行${NC}  端口: $port"
        fi
        return 1
    fi
}

echo -e "${YELLOW}Python 服务:${NC}"
check_service "图片嵌入服务" 6010
check_service "文本嵌入服务" 6011
check_service "图片管理服务" 6020

echo ""
echo -e "${YELLOW}Node.js 服务:${NC}"
check_service "后端 API" 3000 "/api/health"

echo ""
echo -e "${YELLOW}前端服务:${NC}"
printf "%-20s" "前端开发服务器"
if lsof -i:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}● 运行中${NC}  端口: 5173"
else
    echo -e "${RED}○ 未运行${NC}  端口: 5173"
fi

echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""
echo "访问地址: http://localhost:5173"
echo "启动所有: ./start_all.sh"
echo "停止所有: ./stop_all.sh"
echo ""

