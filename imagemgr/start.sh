#!/bin/bash
# 图片管理服务启动脚本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
CONDA_ENV="hidream"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "======================================"
echo "  图片管理服务启动脚本"
echo "======================================"

# 创建必要目录
mkdir -p "$LOG_DIR"
mkdir -p "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/storage"
mkdir -p "$SCRIPT_DIR/vector_index"

# 检查 conda
if ! command -v conda &> /dev/null; then
    echo -e "${RED}错误: 未找到 conda${NC}"
    exit 1
fi

# 初始化 conda
source /mnt/hdd/anaconda3/etc/profile.d/conda.sh
conda activate $CONDA_ENV

# 检查嵌入服务是否运行
echo -e "${YELLOW}检查嵌入服务...${NC}"

if curl -s http://localhost:6010/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 图片嵌入服务 (6010): 运行中${NC}"
else
    echo -e "${RED}✗ 图片嵌入服务 (6010): 未运行${NC}"
    echo "  请先启动嵌入服务: cd ../aiserver/embedding && ./start_all.sh"
fi

if curl -s http://localhost:6011/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 文本嵌入服务 (6011): 运行中${NC}"
else
    echo -e "${RED}✗ 文本嵌入服务 (6011): 未运行${NC}"
    echo "  请先启动嵌入服务: cd ../aiserver/embedding && ./start_all.sh"
fi

echo ""

# 检查是否已有服务在运行
if pgrep -f "api_server.py" > /dev/null; then
    echo -e "${YELLOW}警告: 图片管理服务已在运行${NC}"
    exit 0
fi

# 启动服务
echo -e "${GREEN}启动图片管理服务 (端口 6020)...${NC}"
cd "$SCRIPT_DIR/src"
nohup python api_server.py > "$LOG_DIR/api_server.log" 2>&1 &
echo "  PID: $!"

echo ""
echo "等待服务启动..."
sleep 5

# 检查服务状态
if curl -s http://localhost:6020/health > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 图片管理服务 (6020): 运行中${NC}"
    curl -s http://localhost:6020/health | python3 -m json.tool
else
    echo -e "${RED}✗ 图片管理服务 (6020): 启动失败${NC}"
    echo "  查看日志: tail -f $LOG_DIR/api_server.log"
fi

echo ""
echo "日志目录: $LOG_DIR"
echo "停止服务: ./stop.sh"

