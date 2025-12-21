#!/bin/bash
# AIGenTest 一键启动脚本
# 启动所有服务：嵌入服务、图片管理、后端、前端

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
CONDA_ENV="hidream"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       AIGenTest 一键启动脚本             ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 创建日志目录
mkdir -p "$LOG_DIR"

# ==================== 初始化 Conda ====================
echo -e "${BLUE}[1/5] 初始化 Conda 环境...${NC}"
if ! command -v conda &> /dev/null; then
    echo -e "${RED}错误: 未找到 conda${NC}"
    exit 1
fi

source /mnt/hdd/anaconda3/etc/profile.d/conda.sh
conda activate $CONDA_ENV
echo -e "${GREEN}  ✓ Conda 环境: $CONDA_ENV${NC}"

# ==================== 嵌入服务 ====================
echo ""
echo -e "${BLUE}[2/5] 启动嵌入服务...${NC}"

# 文本嵌入服务 (6011)
if pgrep -f "qwen3_embed.py" > /dev/null; then
    echo -e "${YELLOW}  ⚡ 文本嵌入服务 (6011): 已在运行${NC}"
else
    echo -e "  启动文本嵌入服务..."
    mkdir -p "$SCRIPT_DIR/aiserver/embedding/logs"
    nohup python "$SCRIPT_DIR/aiserver/embedding/qwen3_embed.py" \
        > "$SCRIPT_DIR/aiserver/embedding/logs/qwen3_embed.log" 2>&1 &
    echo -e "${GREEN}  ✓ 文本嵌入服务 PID: $!${NC}"
fi

# 图片嵌入服务 (6010)
if pgrep -f "siglip2_embed.py" > /dev/null; then
    echo -e "${YELLOW}  ⚡ 图片嵌入服务 (6010): 已在运行${NC}"
else
    echo -e "  启动图片嵌入服务..."
    nohup python "$SCRIPT_DIR/aiserver/embedding/siglip2_embed.py" \
        > "$SCRIPT_DIR/aiserver/embedding/logs/siglip2_embed.log" 2>&1 &
    echo -e "${GREEN}  ✓ 图片嵌入服务 PID: $!${NC}"
fi

# ==================== 图片管理服务 ====================
echo ""
echo -e "${BLUE}[3/5] 启动图片管理服务...${NC}"

# 创建必要目录
mkdir -p "$SCRIPT_DIR/imagemgr/data"
mkdir -p "$SCRIPT_DIR/imagemgr/storage"
mkdir -p "$SCRIPT_DIR/imagemgr/vector_index"
mkdir -p "$SCRIPT_DIR/imagemgr/logs"

if pgrep -f "imagemgr.*api_server.py" > /dev/null || pgrep -f "api_server.py" | xargs -I{} sh -c 'grep -l imagemgr /proc/{}/cwd 2>/dev/null' | grep -q .; then
    echo -e "${YELLOW}  ⚡ 图片管理服务 (6020): 已在运行${NC}"
else
    # 检查端口是否被占用
    if lsof -i:6020 > /dev/null 2>&1; then
        echo -e "${YELLOW}  ⚡ 端口 6020 已被占用${NC}"
    else
        echo -e "  启动图片管理服务..."
        cd "$SCRIPT_DIR/imagemgr/src"
        nohup python api_server.py > "$SCRIPT_DIR/imagemgr/logs/api_server.log" 2>&1 &
        echo -e "${GREEN}  ✓ 图片管理服务 PID: $!${NC}"
        cd "$SCRIPT_DIR"
    fi
fi

# ==================== Node.js 后端 ====================
echo ""
echo -e "${BLUE}[4/5] 启动 Node.js 后端...${NC}"

if pgrep -f "node.*backend.*server.js" > /dev/null || lsof -i:3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}  ⚡ Node.js 后端 (3000): 已在运行${NC}"
else
    echo -e "  启动 Node.js 后端..."
    cd "$SCRIPT_DIR/backend"
    nohup node server.js > "$LOG_DIR/backend.log" 2>&1 &
    echo -e "${GREEN}  ✓ Node.js 后端 PID: $!${NC}"
    cd "$SCRIPT_DIR"
fi

# ==================== 前端开发服务器 ====================
echo ""
echo -e "${BLUE}[5/5] 启动前端开发服务器...${NC}"

if pgrep -f "vite.*frontend" > /dev/null || lsof -i:5173 > /dev/null 2>&1; then
    echo -e "${YELLOW}  ⚡ 前端服务 (5173): 已在运行${NC}"
else
    echo -e "  启动前端开发服务器..."
    cd "$SCRIPT_DIR/frontend"
    nohup npx vite --host > "$LOG_DIR/frontend.log" 2>&1 &
    echo -e "${GREEN}  ✓ 前端服务 PID: $!${NC}"
    cd "$SCRIPT_DIR"
fi

# ==================== 等待服务启动 ====================
echo ""
echo -e "${YELLOW}等待服务启动 (15秒)...${NC}"
sleep 15

# ==================== 状态检查 ====================
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              服务状态检查                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

check_service() {
    local name=$1
    local port=$2
    local endpoint=${3:-/health}
    
    if curl -s --max-time 3 "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ $name (端口 $port): 运行中${NC}"
        return 0
    else
        echo -e "${RED}  ✗ $name (端口 $port): 未响应${NC}"
        return 1
    fi
}

check_service "图片嵌入服务" 6010
check_service "文本嵌入服务" 6011
check_service "图片管理服务" 6020
check_service "Node.js 后端" 3000 "/api/health"

# 前端检查 (Vite 没有 health 端点，检查端口)
if lsof -i:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ 前端开发服务器 (端口 5173): 运行中${NC}"
else
    echo -e "${RED}  ✗ 前端开发服务器 (端口 5173): 未响应${NC}"
fi

# ==================== 完成 ====================
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}服务地址:${NC}"
echo "  • 前端界面:     http://localhost:5173"
echo "  • 后端 API:     http://localhost:3000/api"
echo "  • 图片管理 API: http://localhost:6020/api"
echo ""
echo -e "${YELLOW}日志目录:${NC}"
echo "  • 后端/前端:    $LOG_DIR/"
echo "  • 嵌入服务:     $SCRIPT_DIR/aiserver/embedding/logs/"
echo "  • 图片管理:     $SCRIPT_DIR/imagemgr/logs/"
echo ""
echo -e "${YELLOW}停止所有服务: ./stop_all.sh${NC}"
echo ""

