#!/bin/bash

LOCAL_DIR="/mnt/d/work/AIGenTest/memory_system/AI讨论"
REMOTE_DIR="/mnt/hdd/guo/AIGenTest/memory_system/AI讨论"
REMOTE_HOST="linux21"
CONDA_ENV="/mnt/hdd/anaconda3/envs/hidream"
SCRIPT_NAME="test_relation_in_embedding.py"
OUTPUT_IMG="relation_embedding_test.png"

# 同步脚本
echo "同步脚本..."
cat "$LOCAL_DIR/$SCRIPT_NAME" | ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR && cat > $REMOTE_DIR/$SCRIPT_NAME"

# 运行
echo "运行测试..."
ssh $REMOTE_HOST "source /home/ubuntu/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && cd $REMOTE_DIR && python $SCRIPT_NAME 2>&1"

# 取回结果
echo ""
echo "取回结果图片..."
ssh $REMOTE_HOST "cat $REMOTE_DIR/$OUTPUT_IMG" > "$LOCAL_DIR/$OUTPUT_IMG"

echo ""
echo "完成! 查看 $OUTPUT_IMG"
