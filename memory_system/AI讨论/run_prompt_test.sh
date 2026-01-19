#!/bin/bash

LOCAL_DIR="/mnt/d/work/AIGenTest/memory_system/AI讨论"
REMOTE_DIR="/home/layabox/laya/guo/AIGenTest/memory_system/AI讨论"
REMOTE_HOST="linux81"
CONDA_ENV="qwen"
SCRIPT_NAME="test_prompt_relation.py"

# 同步脚本
echo "同步脚本到 linux81..."
cat "$LOCAL_DIR/$SCRIPT_NAME" | ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR && cat > $REMOTE_DIR/$SCRIPT_NAME"

# 运行
echo "在 linux81 上运行提示词测试..."
ssh $REMOTE_HOST "source ~/miniconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && cd $REMOTE_DIR && python $SCRIPT_NAME 2>&1"

echo ""
echo "完成!"
