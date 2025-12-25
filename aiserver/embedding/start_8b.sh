#!/bin/bash
# =============================================================================
# 启动 8B 嵌入和重排序服务
# 使用 conda qwen 环境
# =============================================================================

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
echo -e "${CYAN}║    启动 8B 嵌入 & 重排序服务              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 创建日志目录
mkdir -p "$LOG_DIR"

# 初始化 conda
echo -e "${YELLOW}初始化 conda 环境...${NC}"
if [ -f ~/anaconda3/etc/profile.d/conda.sh ]; then
    source ~/anaconda3/etc/profile.d/conda.sh
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
elif [ -f /opt/conda/etc/profile.d/conda.sh ]; then
    source /opt/conda/etc/profile.d/conda.sh
else
    echo -e "${RED}错误: 未找到 conda${NC}"
    exit 1
fi

conda activate qwen
if [ $? -ne 0 ]; then
    echo -e "${RED}错误: 无法激活 conda 环境 qwen${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Conda 环境: qwen${NC}"

# 启动 Qwen3-Embedding-8B 服务
echo ""
echo -e "${CYAN}[1/2] 启动 Qwen3-Embedding-8B 服务...${NC}"
if pgrep -f "qwen3_8b_embed.py" > /dev/null; then
    echo -e "${YELLOW}  ⚡ Qwen3-Embedding-8B: 已在运行${NC}"
else
    nohup python "$SCRIPT_DIR/qwen3_8b_embed.py" > "$LOG_DIR/qwen3_8b_embed.log" 2>&1 &
    echo $! > "$LOG_DIR/qwen3_8b_embed.pid"
    echo -e "${GREEN}  ✓ PID: $!${NC}"
fi

# 启动 Qwen3-Reranker-8B 服务
echo ""
echo -e "${CYAN}[2/2] 启动 Qwen3-Reranker-8B 服务...${NC}"
if pgrep -f "qwen3_8b_rerank.py" > /dev/null; then
    echo -e "${YELLOW}  ⚡ Qwen3-Reranker-8B: 已在运行${NC}"
else
    nohup python "$SCRIPT_DIR/qwen3_8b_rerank.py" > "$LOG_DIR/qwen3_8b_rerank.log" 2>&1 &
    echo $! > "$LOG_DIR/qwen3_8b_rerank.pid"
    echo -e "${GREEN}  ✓ PID: $!${NC}"
fi

# 等待服务启动
echo ""
echo -e "${YELLOW}等待服务启动 (30秒)...${NC}"
sleep 30

# 从配置获取端口（简单解析 yaml）
PORT_EMBED=$(grep -A1 "embed_8b:" "$SCRIPT_DIR/../config.yaml" | grep "port:" | awk '{print $2}')
PORT_RERANK=$(grep -A1 "rerank_8b:" "$SCRIPT_DIR/../config.yaml" | grep "port:" | awk '{print $2}')

# 状态检查
echo ""
echo -e "${CYAN}服务状态:${NC}"

check_service() {
    local name=$1
    local port=$2
    if curl -s --max-time 5 "http://localhost:$port/health" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✓ $name (端口 $port): 运行中${NC}"
    else
        echo -e "${RED}  ✗ $name (端口 $port): 未响应${NC}"
        echo "    查看日志: tail -f $LOG_DIR/*.log"
    fi
}

check_service "Qwen3-Embedding-8B" "$PORT_EMBED"
check_service "Qwen3-Reranker-8B" "$PORT_RERANK"

# 显示连接信息
SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo -e "${CYAN}══════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}远程连接信息:${NC}"
echo "  Qwen3-Embedding-8B: http://${SERVER_IP}:${PORT_EMBED}"
echo "  Qwen3-Reranker-8B:  http://${SERVER_IP}:${PORT_RERANK}"
echo ""
echo "日志目录: $LOG_DIR"
echo "停止服务: ./stop_8b.sh"

