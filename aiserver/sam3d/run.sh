#!/bin/bash
# SAM 3D Body 运行脚本

export PYTHONPATH=/data1/guo/AIGenTest/aiserver/third_party/sam-3d-body:$PYTHONPATH

# 激活环境 (如果在交互式shell中)
# conda activate sam3d

python sam3d_body_demo.py \
    --image /data1/guo/AIGenTest/aiserver/embedding/test/1a6d250ce5022651.jpeg \
    --output result.json \
    --output_image result.png \
    --output_mesh_dir ./meshes \
    --no_detector  # 不使用人体检测器，使用全图