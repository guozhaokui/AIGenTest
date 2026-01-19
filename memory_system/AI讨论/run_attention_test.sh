#!/bin/bash
# 运行Attention分析测试

LOCAL_DIR="/mnt/d/work/AIGenTest/memory_system/AI讨论"
REMOTE_DIR="/mnt/hdd/guo/AIGenTest/memory_system/AI讨论"
REMOTE_HOST="linux21"
CONDA_ENV="/mnt/hdd/anaconda3/envs/hidream"

# 同步脚本
echo "同步脚本..."
cat "$LOCAL_DIR/test_attention.py" | ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR && cat > $REMOTE_DIR/test_attention.py"

# 运行
echo "运行测试..."
ssh $REMOTE_HOST "source /home/ubuntu/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && cd $REMOTE_DIR && python test_attention.py - attention_analysis.png 2>&1"

# 取回结果
echo ""
echo "取回结果图片..."
ssh $REMOTE_HOST "cat $REMOTE_DIR/attention_analysis.png" > "$LOCAL_DIR/attention_analysis.png"
ssh $REMOTE_HOST "cat $REMOTE_DIR/attention_analysis_heatmap.png" > "$LOCAL_DIR/attention_analysis_heatmap.png" 2>/dev/null

echo ""
echo "完成!"
