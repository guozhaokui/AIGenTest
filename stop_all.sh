#!/bin/bash
# AIGenTest 一键停止脚本
# 停止所有服务：嵌入服务、图片管理、后端、前端

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       AIGenTest 一键停止脚本             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

stop_service() {
    local name=$1
    local pattern=$2
    
    pids=$(pgrep -f "$pattern" 2>/dev/null)
    if [ -n "$pids" ]; then
        echo -e "${YELLOW}停止 $name...${NC}"
        for pid in $pids; do
            kill $pid 2>/dev/null
            echo -e "${GREEN}  ✓ 已停止 PID: $pid${NC}"
        done
    else
        echo -e "  $name: 未在运行"
    fi
}

# 停止前端
stop_service "前端开发服务器" "vite.*frontend"
stop_service "前端开发服务器" "node.*vite"

# 停止后端
stop_service "Node.js 后端" "node.*backend.*server.js"
stop_service "Node.js 后端" "node.*server.js.*3000"

# 停止图片管理服务
stop_service "图片管理服务" "api_server.py"

# 停止嵌入服务
stop_service "图片嵌入服务" "siglip2_embed.py"
stop_service "文本嵌入服务" "qwen3_embed.py"

echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""

# 检查端口
echo -e "${YELLOW}端口状态检查:${NC}"

check_port() {
    local port=$1
    local name=$2
    if lsof -i:$port > /dev/null 2>&1; then
        echo -e "${RED}  ⚠ 端口 $port ($name): 仍被占用${NC}"
        lsof -i:$port | grep LISTEN | awk '{print "    PID: " $2 " (" $1 ")"}'
    else
        echo -e "${GREEN}  ✓ 端口 $port ($name): 已释放${NC}"
    fi
}

check_port 5173 "前端"
check_port 3000 "后端"
check_port 6020 "图片管理"
check_port 6010 "图片嵌入"
check_port 6011 "文本嵌入"

echo ""
echo -e "${GREEN}所有服务已停止${NC}"
echo ""

