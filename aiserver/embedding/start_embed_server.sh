#!/bin/bash
# 嵌入服务器启动脚本（仅启动嵌入计算服务）
# 用于远程 GPU 服务器

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
CONDA_ENV="hidream"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║       嵌入服务器 (远程 GPU)               ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 显示本机 IP
echo -e "${YELLOW}本机 IP 地址:${NC}"
hostname -I | awk '{print "  " $1}'
echo ""

# 创建日志目录
mkdir -p "$LOG_DIR"

# 初始化 conda
if ! command -v conda &> /dev/null; then
    echo -e "${RED}错误: 未找到 conda${NC}"
    exit 1
fi

source /mnt/hdd/anaconda3/etc/profile.d/conda.sh
conda activate $CONDA_ENV
echo -e "${GREEN}✓ Conda 环境: $CONDA_ENV${NC}"

# 启动文本嵌入服务 (6011)
if pgrep -f "qwen3_embed.py" > /dev/null; then
    echo -e "${YELLOW}⚡ 文本嵌入服务 (6011): 已在运行${NC}"
else
    echo -e "启动文本嵌入服务 (端口 6011)..."
    nohup python "$SCRIPT_DIR/qwen3_embed.py" > "$LOG_DIR/qwen3_embed.log" 2>&1 &
    echo -e "${GREEN}  ✓ PID: $!${NC}"
fi

# 启动图片嵌入服务 (6010)
if pgrep -f "siglip2_embed.py" > /dev/null; then
    echo -e "${YELLOW}⚡ 图片嵌入服务 (6010): 已在运行${NC}"
else
    echo -e "启动图片嵌入服务 (端口 6010)..."
    nohup python "$SCRIPT_DIR/siglip2_embed.py" > "$LOG_DIR/siglip2_embed.log" 2>&1 &
    echo -e "${GREEN}  ✓ PID: $!${NC}"
fi

# 启动 BGE 文本嵌入服务 (6012)
if pgrep -f "bge_embed.py" > /dev/null; then
    echo -e "${YELLOW}⚡ BGE 嵌入服务 (6012): 已在运行${NC}"
else
    echo -e "启动 BGE 嵌入服务 (端口 6012)..."
    nohup python "$SCRIPT_DIR/bge_embed.py" > "$LOG_DIR/bge_embed.log" 2>&1 &
    echo -e "${GREEN}  ✓ PID: $!${NC}"
fi

# 启动 Qwen3 重排序服务 (6013) - 可选，消耗更多显存
if [ "$1" = "--with-rerank" ]; then
    if pgrep -f "qwen3_rerank.py" > /dev/null; then
        echo -e "${YELLOW}⚡ 重排序服务 (6013): 已在运行${NC}"
    else
        echo -e "启动重排序服务 (端口 6013)..."
        nohup python "$SCRIPT_DIR/qwen3_rerank.py" > "$LOG_DIR/qwen3_rerank.log" 2>&1 &
        echo -e "${GREEN}  ✓ PID: $!${NC}"
    fi
fi

echo ""
echo -e "${YELLOW}等待服务启动 (20秒)...${NC}"
sleep 20

# 状态检查
echo ""
echo -e "${CYAN}服务状态:${NC}"

check_service() {
    local name=$1
    local port=$2
    if curl -s --max-time 3 "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ $name (端口 $port): 运行中${NC}"
    else
        echo -e "${RED}  ✗ $name (端口 $port): 未响应${NC}"
        echo "    查看日志: tail -f $LOG_DIR/*.log"
    fi
}

check_service "图片嵌入服务 (SigLIP-2)" 6010
check_service "文本嵌入服务 (Qwen3)" 6011
check_service "文本嵌入服务 (BGE)" 6012
if [ "$1" = "--with-rerank" ]; then
    check_service "重排序服务 (Qwen3)" 6013
fi

# 显示连接信息
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}远程连接信息:${NC}"
echo "  图片嵌入 (SigLIP-2): http://${SERVER_IP}:6010"
echo "  文本嵌入 (Qwen3):    http://${SERVER_IP}:6011"
echo "  文本嵌入 (BGE):      http://${SERVER_IP}:6012"
if [ "$1" = "--with-rerank" ]; then
    echo "  重排序 (Qwen3):      http://${SERVER_IP}:6013"
fi
echo ""
echo -e "${YELLOW}在客户端配置文件中使用以上地址${NC}"
echo ""
echo "日志目录: $LOG_DIR"
echo "停止服务: ./stop_all.sh"
echo ""

