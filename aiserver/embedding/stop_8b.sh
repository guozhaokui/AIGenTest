#!/bin/bash
# =============================================================================
# 停止 8B 嵌入和重排序服务
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
echo -e "${CYAN}║    停止 8B 嵌入 & 重排序服务              ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# 停止 Qwen3-Embedding-8B
echo -e "${YELLOW}停止 Qwen3-Embedding-8B...${NC}"
if [ -f "$LOG_DIR/qwen3_8b_embed.pid" ]; then
    PID=$(cat "$LOG_DIR/qwen3_8b_embed.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo -e "${GREEN}  ✓ 已停止 (PID: $PID)${NC}"
    else
        echo -e "${YELLOW}  ⚠ 进程已不存在${NC}"
    fi
    rm -f "$LOG_DIR/qwen3_8b_embed.pid"
else
    # 尝试通过进程名停止
    pkill -f "qwen3_8b_embed.py" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ 已停止${NC}"
    else
        echo -e "${YELLOW}  ⚠ 未运行${NC}"
    fi
fi

# 停止 Qwen3-Reranker-8B
echo -e "${YELLOW}停止 Qwen3-Reranker-8B...${NC}"
if [ -f "$LOG_DIR/qwen3_8b_rerank.pid" ]; then
    PID=$(cat "$LOG_DIR/qwen3_8b_rerank.pid")
    if kill -0 $PID 2>/dev/null; then
        kill $PID
        echo -e "${GREEN}  ✓ 已停止 (PID: $PID)${NC}"
    else
        echo -e "${YELLOW}  ⚠ 进程已不存在${NC}"
    fi
    rm -f "$LOG_DIR/qwen3_8b_rerank.pid"
else
    # 尝试通过进程名停止
    pkill -f "qwen3_8b_rerank.py" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ 已停止${NC}"
    else
        echo -e "${YELLOW}  ⚠ 未运行${NC}"
    fi
fi

echo ""
echo -e "${GREEN}完成${NC}"

