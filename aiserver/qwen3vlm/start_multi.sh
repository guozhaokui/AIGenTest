#!/bin/bash
#
# 多实例 VLM 服务启动脚本
# 在多个 GPU 上并行运行多个实例
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_PATH="${MODEL_PATH:-/data1/MLLM/qwen2.5vl/Qwen/Qwen/Qwen3-VL-8B-Instruct}"

# 可用的 GPU 列表 (1-7)
GPUS="${GPUS:-1,2,3,4}"
# 负载均衡器端口
LB_PORT="${LB_PORT:-6050}"
# 实例基础端口
BASE_PORT="${BASE_PORT:-6051}"

# 激活 conda 环境
echo "🔄 激活 conda 环境: qwen"
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null || \
source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null || \
source /opt/conda/etc/profile.d/conda.sh 2>/dev/null
conda activate qwen

if [ $? -ne 0 ]; then
    echo "❌ 无法激活 conda 环境 qwen"
    exit 1
fi

cd "$SCRIPT_DIR"

# 解析 GPU 列表
IFS=',' read -ra GPU_ARRAY <<< "$GPUS"
NUM_INSTANCES=${#GPU_ARRAY[@]}

echo "============================================================"
echo "🚀 启动多实例 VLM 服务"
echo "============================================================"
echo "📦 模型: $MODEL_PATH"
echo "🎮 GPU: ${GPUS} (${NUM_INSTANCES} 个实例)"
echo "🌐 负载均衡: http://0.0.0.0:${LB_PORT}"
echo "============================================================"

# 启动各个实例
BACKEND_PORTS=""
for i in "${!GPU_ARRAY[@]}"; do
    GPU="${GPU_ARRAY[$i]}"
    PORT=$((BASE_PORT + i))
    
    echo "▶ 启动实例 $((i+1)): GPU $GPU, 端口 $PORT"
    
    CUDA_VISIBLE_DEVICES=$GPU python vlm_service.py \
        --host 127.0.0.1 \
        --port $PORT \
        --model-path "$MODEL_PATH" \
        --gpu 0 \
        > "logs/instance_${GPU}.log" 2>&1 &
    
    echo $! > "logs/instance_${GPU}.pid"
    
    if [ -z "$BACKEND_PORTS" ]; then
        BACKEND_PORTS="$PORT"
    else
        BACKEND_PORTS="$BACKEND_PORTS,$PORT"
    fi
done

echo ""
echo "等待实例启动..."
sleep 30

# 启动负载均衡器
echo "▶ 启动负载均衡器: 端口 $LB_PORT"
python load_balancer.py \
    --port $LB_PORT \
    --backends $BACKEND_PORTS \
    > "logs/load_balancer.log" 2>&1 &

echo $! > "logs/load_balancer.pid"

echo ""
echo "============================================================"
echo "✅ 服务已启动"
echo "============================================================"
echo "负载均衡器: http://0.0.0.0:${LB_PORT}"
echo "后端实例: ${BACKEND_PORTS}"
echo ""
echo "查看日志: tail -f logs/*.log"
echo "停止服务: ./stop_multi.sh"
echo "============================================================"

# 等待
wait

