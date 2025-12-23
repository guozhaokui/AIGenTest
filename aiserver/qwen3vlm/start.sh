#!/bin/bash
#
# Qwen3-VL VLM 服务启动脚本
# 使用 conda 环境 qwen
#

# 配置
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-6050}"
GPU="${GPU:-1}"
MODEL_PATH="${MODEL_PATH:-/data1/MLLM/qwen2.5vl/Qwen/Qwen/Qwen3-VL-8B-Instruct}"

# 切换到脚本目录
cd "$(dirname "$0")"

# 激活 conda 环境
echo "🔄 激活 conda 环境: qwen"
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || source /opt/conda/etc/profile.d/conda.sh 2>/dev/null
conda activate qwen

if [ $? -ne 0 ]; then
    echo "❌ 无法激活 conda 环境 qwen"
    echo "请确保已创建 qwen 环境: conda create -n qwen python=3.10"
    exit 1
fi

echo "✅ 已激活 conda 环境: $(conda info --envs | grep '*' | awk '{print $1}')"

# 启动服务
exec python vlm_service.py \
    --host "$HOST" \
    --port "$PORT" \
    --gpu "$GPU" \
    --model-path "$MODEL_PATH" \
    "$@"

