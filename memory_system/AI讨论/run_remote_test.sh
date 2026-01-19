#!/bin/bash
# 远程运行层变化率测试脚本
# 用法:
#   ./run_remote_test.sh                    # 使用默认测试文本
#   ./run_remote_test.sh test_input.txt     # 使用指定的文本文件

LOCAL_DIR="/mnt/d/work/AIGenTest/memory_system/AI讨论"
REMOTE_DIR="/mnt/hdd/guo/AIGenTest/memory_system/AI讨论"
REMOTE_HOST="linux21"
CONDA_ENV="/mnt/hdd/anaconda3/envs/hidream"

# 同步脚本到远程
echo "同步脚本到远程..."
cat "$LOCAL_DIR/test_layer_change_rate.py" | ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR && cat > $REMOTE_DIR/test_layer_change_rate.py"

# 如果有输入文件参数，也同步过去
if [ -n "$1" ]; then
    INPUT_FILE="$1"
    REMOTE_INPUT="$REMOTE_DIR/test_input.txt"
    echo "同步输入文件: $INPUT_FILE"
    cat "$INPUT_FILE" | ssh $REMOTE_HOST "cat > $REMOTE_INPUT"
    RUN_CMD="python $REMOTE_DIR/test_layer_change_rate.py $REMOTE_INPUT $REMOTE_DIR/change_rate_plot.png"
else
    RUN_CMD="python $REMOTE_DIR/test_layer_change_rate.py"
fi

# 运行测试
echo "运行测试..."
ssh $REMOTE_HOST "source /home/ubuntu/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && cd $REMOTE_DIR && $RUN_CMD 2>&1"

# 取回结果图片
echo ""
echo "取回结果图片..."
ssh $REMOTE_HOST "cat $REMOTE_DIR/change_rate_plot.png" > "$LOCAL_DIR/change_rate_plot.png"

echo ""
echo "完成! 图片保存在: $LOCAL_DIR/change_rate_plot.png"
