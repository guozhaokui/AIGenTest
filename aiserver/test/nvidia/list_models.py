#!/usr/bin/env python3
"""获取 NVIDIA NIM 可用模型列表"""

import os
from pathlib import Path
from dotenv import load_dotenv
import requests

# 加载环境变量
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / '.env'
load_dotenv(dotenv_path=env_path)

NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')

if not NVIDIA_API_KEY:
    print("错误: NVIDIA_API_KEY 未配置")
    exit(1)

# 调用 NVIDIA API 获取模型列表
url = "https://integrate.api.nvidia.com/v1/models"
headers = {
    "Authorization": f"Bearer {NVIDIA_API_KEY}",
    "Content-Type": "application/json"
}

print("正在获取 NVIDIA NIM 可用模型列表...\n")

try:
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        models = data.get('data', [])

        print(f"找到 {len(models)} 个模型:\n")
        print("=" * 80)

        for model in models:
            model_id = model.get('id', 'N/A')
            owned_by = model.get('owned_by', 'N/A')
            print(f"ID: {model_id}")
            print(f"拥有者: {owned_by}")
            print("-" * 80)

    else:
        print(f"错误: HTTP {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"错误: {e}")

print("\n提示: 你可以将这些模型 ID 添加到 app.py 的 AVAILABLE_MODELS 列表中")
