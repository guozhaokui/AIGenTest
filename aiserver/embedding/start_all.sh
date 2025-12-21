#!/bin/bash
# 嵌入服务一键启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
CONDA_ENV="hidream"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "  嵌入服务启动脚本"
echo "======================================"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 检查 conda
if ! command -v conda &> /dev/null; then
    echo -e "${RED}错误: 未找到 conda${NC}"
    exit 1
fi

# 初始化 conda
source /mnt/hdd/anaconda3/etc/profile.d/conda.sh

# 激活环境
echo -e "${YELLOW}激活 conda 环境: $CONDA_ENV${NC}"
conda activate $CONDA_ENV

# 检查是否已有服务在运行
if pgrep -f "qwen3_embed.py" > /dev/null; then
    echo -e "${YELLOW}警告: 文本嵌入服务已在运行${NC}"
else
    echo -e "${GREEN}启动文本嵌入服务 (端口 6011)...${NC}"
    nohup python "$SCRIPT_DIR/qwen3_embed.py" > "$LOG_DIR/qwen3_embed.log" 2>&1 &
    echo "  PID: $!"
fi

if pgrep -f "siglip2_embed.py" > /dev/null; then
    echo -e "${YELLOW}警告: 图片嵌入服务已在运行${NC}"
else
    echo -e "${GREEN}启动图片嵌入服务 (端口 6010)...${NC}"
    nohup python "$SCRIPT_DIR/siglip2_embed.py" > "$LOG_DIR/siglip2_embed.log" 2>&1 &
    echo "  PID: $!"
fi

echo ""
echo "等待服务启动..."
sleep 10

# 检查服务状态
echo ""
echo "======================================"
echo "  服务状态检查"
echo "======================================"

# 检查文本嵌入服务
if curl -s http://localhost:6011/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 文本嵌入服务 (6011): 运行中${NC}"
else
    echo -e "${RED}✗ 文本嵌入服务 (6011): 启动失败${NC}"
    echo "  查看日志: tail -f $LOG_DIR/qwen3_embed.log"
fi

# 检查图片嵌入服务
if curl -s http://localhost:6010/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 图片嵌入服务 (6010): 运行中${NC}"
else
    echo -e "${RED}✗ 图片嵌入服务 (6010): 启动失败${NC}"
    echo "  查看日志: tail -f $LOG_DIR/siglip2_embed.log"
fi

echo ""
echo "日志目录: $LOG_DIR"
echo "停止服务: ./stop_all.sh"

