#!/usr/bin/env python3
"""测试推理模型的思考内容格式"""

import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / '.env'
load_dotenv(dotenv_path=env_path)

NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# 测试的模型
test_models = [
    "deepseek-ai/deepseek-r1-0528",
    "moonshotai/kimi-k2-thinking",
]

question = "23 * 47 是多少？请一步步计算"

for model_id in test_models:
    print(f"\n{'='*60}")
    print(f"测试模型: {model_id}")
    print(f"{'='*60}")

    try:
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": question}],
            temperature=0.6,
            max_tokens=2048,
        )

        response = completion.choices[0].message

        print(f"\n--- 原始 content ---")
        print(repr(response.content[:2000] if response.content else "None"))

        # 检查是否有其他属性
        print(f"\n--- message 对象属性 ---")
        for attr in dir(response):
            if not attr.startswith('_'):
                val = getattr(response, attr, None)
                if val is not None and not callable(val):
                    print(f"{attr}: {type(val).__name__} = {repr(val)[:200]}")

        # 检查 completion 对象
        print(f"\n--- completion 对象检查 ---")
        print(f"model: {completion.model}")
        if hasattr(completion, 'usage'):
            print(f"usage: {completion.usage}")

    except Exception as e:
        print(f"错误: {e}")

print("\n" + "="*60)
print("测试完成")
