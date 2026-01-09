#!/bin/bash
# ============================================================
# LTX-2 视频生成服务启动脚本
# ⚠️ 只能在 8x3090 服务器上运行
# ============================================================

# 激活 conda 环境
source /home/layabox01/anaconda3/bin/activate ltx

# 切换到服务目录
cd /data1/guo/AIGenTest/aiserver/gen_video_ltx2

# 启动服务
echo "启动 LTX-2 视频生成服务..."
echo "端口: 6020"
echo "环境: 8x3090 / conda: ltx"

python ltx2_server.py --port 6070


