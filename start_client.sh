#!/bin/bash
# AIGenTest 客户端启动脚本
# 在本地电脑上运行，连接远程嵌入服务器
# 
# 启动内容：图片管理服务、Node.js 后端、前端
# 不启动：嵌入服务（由远程 GPU 服务器提供）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     AIGenTest 客户端启动脚本              ║${NC}"
echo -e "${CYAN}║     (连接远程嵌入服务器)                  ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 创建日志目录
mkdir -p "$LOG_DIR"

# ==================== 检查配置 ====================
echo -e "${YELLOW}检查嵌入服务配置...${NC}"

CONFIG_FILE="$SCRIPT_DIR/imagemgr/config/embedding_services.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}错误: 配置文件不存在${NC}"
    echo "  请先配置嵌入服务地址:"
    echo "  1. cp imagemgr/config/embedding_services_remote.yaml.example imagemgr/config/embedding_services.yaml"
    echo "  2. 编辑 embedding_services.yaml，将 SERVER_IP 替换为实际 IP"
    exit 1
fi

# 提取 endpoint 地址
IMAGE_ENDPOINT=$(grep -A5 "siglip2" "$CONFIG_FILE" | grep "endpoint:" | head -1 | awk '{print $2}')
TEXT_ENDPOINT=$(grep -A5 "qwen3" "$CONFIG_FILE" | grep "endpoint:" | head -1 | awk '{print $2}')

echo "  图片嵌入服务: $IMAGE_ENDPOINT"
echo "  文本嵌入服务: $TEXT_ENDPOINT"

# 检查远程服务是否可用
echo ""
echo -e "${YELLOW}检查远程嵌入服务...${NC}"

check_remote() {
    local name=$1
    local url=$2
    if curl -s --max-time 5 "${url}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ $name: 可用${NC}"
        return 0
    else
        echo -e "${RED}  ✗ $name: 无法连接${NC}"
        return 1
    fi
}

EMBED_OK=true
check_remote "图片嵌入服务" "$IMAGE_ENDPOINT" || EMBED_OK=false
check_remote "文本嵌入服务" "$TEXT_ENDPOINT" || EMBED_OK=false

if [ "$EMBED_OK" = false ]; then
    echo ""
    echo -e "${RED}警告: 远程嵌入服务不可用${NC}"
    echo "  请确保服务器已启动嵌入服务"
    read -p "是否继续启动? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ==================== 创建必要目录 ====================
mkdir -p "$SCRIPT_DIR/imagemgr/data"
mkdir -p "$SCRIPT_DIR/imagemgr/storage"
mkdir -p "$SCRIPT_DIR/imagemgr/vector_index"
mkdir -p "$SCRIPT_DIR/imagemgr/logs"
mkdir -p "$SCRIPT_DIR/logs"

# ==================== Node.js 后端（自动启动 imagemgr）====================
echo ""
echo -e "${CYAN}[1/2] 启动 Node.js 后端 + 图片管理服务...${NC}"

if lsof -i:3000 > /dev/null 2>&1; then
    echo -e "${YELLOW}  ⚡ Node.js 后端 (3000): 已在运行${NC}"
else
    echo -e "  启动 Node.js 后端（会自动启动 Python imagemgr）..."
    cd "$SCRIPT_DIR/backend"
    nohup node server.js > "$LOG_DIR/backend.log" 2>&1 &
    echo -e "${GREEN}  ✓ Node.js 后端 PID: $!${NC}"
    cd "$SCRIPT_DIR"
fi

# ==================== 前端开发服务器 ====================
echo ""
echo -e "${CYAN}[2/2] 启动前端开发服务器...${NC}"

if lsof -i:5173 > /dev/null 2>&1; then
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
echo -e "${YELLOW}等待服务启动 (5秒)...${NC}"
sleep 5

# ==================== 状态检查 ====================
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              服务状态检查                 ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}远程服务 (GPU 服务器):${NC}"
check_remote "  图片嵌入" "$IMAGE_ENDPOINT"
check_remote "  文本嵌入" "$TEXT_ENDPOINT"

echo ""
echo -e "${YELLOW}本地服务:${NC}"

check_local() {
    local name=$1
    local port=$2
    local endpoint=${3:-/health}
    
    if curl -s --max-time 3 "http://localhost:$port$endpoint" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ $name (端口 $port): 运行中${NC}"
    else
        echo -e "${RED}  ✗ $name (端口 $port): 未响应${NC}"
    fi
}

check_local "图片管理服务" 6020
check_local "Node.js 后端" 3000 "/api/health"

if lsof -i:5173 > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ 前端服务 (端口 5173): 运行中${NC}"
else
    echo -e "${RED}  ✗ 前端服务 (端口 5173): 未响应${NC}"
fi

# ==================== 完成 ====================
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}访问地址: http://localhost:5173${NC}"
echo ""
echo "日志目录: $LOG_DIR"
echo "停止服务: ./stop_all.sh"
echo ""

