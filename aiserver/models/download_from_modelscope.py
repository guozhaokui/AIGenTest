#!/usr/bin/env python3
"""
从 ModelScope 下载模型的脚本

用法:
    python download_from_modelscope.py <model_id> [--cache_dir <目录>]

示例:
    python download_from_modelscope.py facebook/dinov3-vit7b16-pretrain-lvd1689m
    python download_from_modelscope.py facebook/dinov3-vit7b16-pretrain-lvd1689m --cache_dir /custom/path
"""

import argparse
import os
import sys

def download_model(model_id: str, cache_dir: str = None):
    """
    从 ModelScope 下载模型
    
    Args:
        model_id: ModelScope 上的模型 ID，例如 "facebook/dinov3-vit7b16-pretrain-lvd1689m"
        cache_dir: 模型下载保存目录，默认为当前脚本所在目录
    """
    try:
        from modelscope import snapshot_download
    except ImportError:
        print("错误: 未安装 modelscope 库，请先安装:")
        print("  pip install modelscope")
        sys.exit(1)
    
    if cache_dir is None:
        # 默认保存到脚本所在目录
        cache_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"开始下载模型: {model_id}")
    print(f"保存目录: {cache_dir}")
    print("-" * 50)
    
    try:
        model_dir = snapshot_download(
            model_id=model_id,
            cache_dir=cache_dir,
            revision='master'  # 使用主分支
        )
        print("-" * 50)
        print(f"✓ 下载完成!")
        print(f"模型保存路径: {model_dir}")
        return model_dir
    except Exception as e:
        print(f"✗ 下载失败: {e}")
        sys.exit(1)


def main():

    download_model("Qwen/Qwen-Image-Layered", "/mnt/hdd/guo/AIGenTest/aiserver/models")


if __name__ == "__main__":
    main()

