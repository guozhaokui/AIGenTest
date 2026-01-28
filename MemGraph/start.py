#!/usr/bin/env python3
"""
MemGraph 启动脚本
"""
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.server import start_server

if __name__ == "__main__":
    start_server()
