#!/bin/bash
# Qwen-Image-Layered Web 服务启动脚本

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 设置环境变量
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-0}
export HF_ENDPOINT=${HF_ENDPOINT:-https://hf-mirror.com}

# 默认参数
HOST="0.0.0.0"
PORT=7861
PRELOAD=false
SHARE=false
INT8=false

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --preload)
            PRELOAD=true
            shift
            ;;
        --share)
            SHARE=true
            shift
            ;;
        --gpu)
            export CUDA_VISIBLE_DEVICES="$2"
            shift 2
            ;;
        --int8)
            INT8=true
            shift
            ;;
        -h|--help)
            echo "用法: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  --host HOST    服务地址 (默认: 0.0.0.0)"
            echo "  --port PORT    服务端口 (默认: 7861)"
            echo "  --gpu IDS      指定 GPU，如 0,1,2 (默认: 0)"
            echo "  --preload      启动时预加载模型"
            echo "  --share        创建公网链接"
            echo "  --int8         启用 INT8 量化（减少约 50% 显存）"
            echo "  -h, --help     显示帮助信息"
            echo ""
            echo "示例:"
            echo "  $0 --gpu 1,2,3 --preload           # 使用 3 张 GPU，预加载"
            echo "  $0 --gpu 0,1 --int8 --preload      # 使用 2 张 GPU + INT8 量化"
            exit 0
            ;;
        *)
            echo "未知参数: $1"
            echo "使用 --help 查看帮助"
            exit 1
            ;;
    esac
done

echo "=============================================="
echo "🎨 Qwen-Image-Layered Web 服务"
echo "=============================================="
echo "GPU: CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
echo "INT8 量化: $INT8"
echo "地址: http://$HOST:$PORT"
echo "=============================================="

# 构建启动命令
CMD="python qwen_image_layered_server.py --host $HOST --port $PORT"

if [ "$PRELOAD" = true ]; then
    CMD="$CMD --preload"
fi

if [ "$SHARE" = true ]; then
    CMD="$CMD --share"
fi

if [ "$INT8" = true ]; then
    CMD="$CMD --int8"
fi

echo "执行命令: $CMD"
echo ""

# 启动服务
exec $CMD

