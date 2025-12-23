#!/bin/bash
# 嵌入服务停止脚本

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "======================================"
echo "  嵌入服务停止脚本"
echo "======================================"

# 停止文本嵌入服务
if pgrep -f "qwen3_embed.py" > /dev/null; then
    echo -e "${YELLOW}停止文本嵌入服务...${NC}"
    pkill -f "qwen3_embed.py"
    echo -e "${GREEN}✓ 已停止${NC}"
else
    echo "文本嵌入服务未运行"
fi

# 停止图片嵌入服务
if pgrep -f "siglip2_embed.py" > /dev/null; then
    echo -e "${YELLOW}停止图片嵌入服务...${NC}"
    pkill -f "siglip2_embed.py"
    echo -e "${GREEN}✓ 已停止${NC}"
else
    echo "图片嵌入服务未运行"
fi

# 停止 BGE 嵌入服务
if pgrep -f "bge_embed.py" > /dev/null; then
    echo -e "${YELLOW}停止 BGE 嵌入服务...${NC}"
    pkill -f "bge_embed.py"
    echo -e "${GREEN}✓ 已停止${NC}"
else
    echo "BGE 嵌入服务未运行"
fi

# 停止重排序服务
if pgrep -f "qwen3_rerank.py" > /dev/null; then
    echo -e "${YELLOW}停止重排序服务...${NC}"
    pkill -f "qwen3_rerank.py"
    echo -e "${GREEN}✓ 已停止${NC}"
else
    echo "重排序服务未运行"
fi

echo ""
echo "所有嵌入服务已停止"

