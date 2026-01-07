#!/usr/bin/env python3
"""测试环境配置"""

import sys
from pathlib import Path

print("=== 环境诊断 ===\n")

# 1. 检查路径
print(f"当前文件: {__file__}")
current_file = Path(__file__).resolve()
print(f"解析后路径: {current_file}")

root_dir = current_file.parent.parent.parent.parent
env_path = root_dir / '.env'

print(f"\n项目根目录: {root_dir}")
print(f".env 路径: {env_path}")
print(f".env 存在: {env_path.exists()}")

if env_path.exists():
    print("\n.env 文件内容预览:")
    with open(env_path, 'r') as f:
        for line in f.readlines()[:5]:
            if 'NVIDIA_API_KEY' in line:
                key_part = line.split('=')[1].strip()[:15] if '=' in line else ''
                print(f"  NVIDIA_API_KEY={key_part}...")
            else:
                print(f"  {line.strip()}")

# 2. 检查依赖
print("\n=== 检查依赖 ===")
try:
    import flask
    print(f"✓ Flask: {flask.__version__}")
except ImportError as e:
    print(f"✗ Flask: {e}")

try:
    import flask_cors
    print(f"✓ Flask-CORS: 已安装")
except ImportError as e:
    print(f"✗ Flask-CORS: {e}")

try:
    import openai
    print(f"✓ OpenAI: {openai.__version__}")
except ImportError as e:
    print(f"✗ OpenAI: {e}")

try:
    import dotenv
    print(f"✓ python-dotenv: 已安装")
except ImportError as e:
    print(f"✗ python-dotenv: {e}")

# 3. 测试加载环境变量
print("\n=== 测试加载环境变量 ===")
try:
    from dotenv import load_dotenv
    import os

    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv('NVIDIA_API_KEY')

    if api_key:
        print(f"✓ NVIDIA_API_KEY 已加载: {api_key[:15]}...")
    else:
        print("✗ NVIDIA_API_KEY 未找到")
except Exception as e:
    print(f"✗ 错误: {e}")

print("\n=== 诊断完成 ===")
