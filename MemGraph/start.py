#!/usr/bin/env python3
"""
MemGraph 启动脚本
"""
import sys
import os
from pathlib import Path

# 禁用代理，避免 localhost 请求被拦截
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent))

from src.server import start_server

if __name__ == "__main__":
    start_server()
