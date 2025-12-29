#!/bin/bash
# SAM 3D Body Web 服务启动脚本

cd "$(dirname "$0")"

# 设置环境
export PYTHONPATH=/data1/guo/AIGenTest/aiserver/third_party/sam-3d-body:$PYTHONPATH

# 激活 conda 环境
source ~/anaconda3/etc/profile.d/conda.sh
conda activate sam3d

# 安装 gradio（如果没有）
pip install gradio -q

echo "========================================"
echo "  SAM 3D Body Web 服务"
echo "========================================"
echo ""
echo "启动服务中..."
echo "访问地址: http://localhost:7860"
echo ""

# 启动服务（预加载模型）
python web_server.py --host 0.0.0.0 --port 7860 --preload

