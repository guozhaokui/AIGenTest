#!/bin/bash
# 运行滑动窗口+白化测试
# 用法:
#   ./run_sliding_test.sh                         # 默认文本，窗口8，步长4
#   ./run_sliding_test.sh 10 5                    # 默认文本，窗口10，步长5
#   ./run_sliding_test.sh input.txt 8 4           # 指定文本文件

LOCAL_DIR="/mnt/d/work/AIGenTest/memory_system/AI讨论"
REMOTE_DIR="/mnt/hdd/guo/AIGenTest/memory_system/AI讨论"
REMOTE_HOST="linux21"
CONDA_ENV="/mnt/hdd/anaconda3/envs/hidream"

# 同步脚本
echo "同步脚本..."
cat "$LOCAL_DIR/test_sliding_window.py" | ssh $REMOTE_HOST "mkdir -p $REMOTE_DIR && cat > $REMOTE_DIR/test_sliding_window.py"

# 解析参数
if [ -f "$1" ]; then
    # 第一个参数是文件
    INPUT_FILE="$1"
    WINDOW_SIZE="${2:-8}"
    STEP="${3:-4}"

    echo "同步输入文件: $INPUT_FILE"
    cat "$INPUT_FILE" | ssh $REMOTE_HOST "cat > $REMOTE_DIR/test_input.txt"
    RUN_CMD="python $REMOTE_DIR/test_sliding_window.py $REMOTE_DIR/test_input.txt $WINDOW_SIZE $STEP $REMOTE_DIR/sliding_window_plot.png"
else
    # 第一个参数是窗口大小（或默认）
    WINDOW_SIZE="${1:-8}"
    STEP="${2:-4}"
    RUN_CMD="python $REMOTE_DIR/test_sliding_window.py - $WINDOW_SIZE $STEP $REMOTE_DIR/sliding_window_plot.png"
fi

echo "窗口大小: $WINDOW_SIZE, 步长: $STEP"

# 运行
echo "运行测试..."
ssh $REMOTE_HOST "source /home/ubuntu/anaconda3/etc/profile.d/conda.sh && conda activate $CONDA_ENV && cd $REMOTE_DIR && $RUN_CMD 2>&1"

# 取回结果
echo ""
echo "取回结果图片..."
ssh $REMOTE_HOST "cat $REMOTE_DIR/sliding_window_plot.png" > "$LOCAL_DIR/sliding_window_plot.png"

echo ""
echo "完成! 图片保存在: $LOCAL_DIR/sliding_window_plot.png"
