#!/usr/bin/env python3
"""测试 NVIDIA NIM API 的工具调用（Function Calling）功能"""

import os
import json
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

# 定义测试工具
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，如 北京、上海"
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "温度单位"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "在网上搜索信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# 测试的模型（选择支持工具调用的模型）
test_models = [
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.1-70b-instruct",
    "mistralai/mistral-7b-instruct-v0.3",
    "deepseek-ai/deepseek-v3.2",
    "qwen/qwen2.5-7b-instruct",
]

question = "北京今天天气怎么样？"

print("=" * 70)
print("测试 NVIDIA NIM API 工具调用（Function Calling）功能")
print("=" * 70)

for model_id in test_models:
    print(f"\n{'='*60}")
    print(f"模型: {model_id}")
    print(f"{'='*60}")

    try:
        # 测试工具调用
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": question}],
            tools=tools,
            tool_choice="auto",
            temperature=0.1,
            max_tokens=1024,
        )

        message = completion.choices[0].message

        print(f"\n--- 响应 ---")
        print(f"role: {message.role}")
        print(f"content: {message.content}")

        # 检查是否有工具调用
        if message.tool_calls:
            print(f"\n✅ 支持工具调用!")
            print(f"tool_calls 数量: {len(message.tool_calls)}")
            for i, tc in enumerate(message.tool_calls):
                print(f"\n  工具调用 #{i+1}:")
                print(f"    id: {tc.id}")
                print(f"    type: {tc.type}")
                print(f"    function.name: {tc.function.name}")
                print(f"    function.arguments: {tc.function.arguments}")
        else:
            print(f"\n⚠️ 没有工具调用（模型可能不支持或选择不调用）")

        # 检查 finish_reason
        finish_reason = completion.choices[0].finish_reason
        print(f"\nfinish_reason: {finish_reason}")

    except Exception as e:
        print(f"\n❌ 错误: {e}")

print("\n" + "=" * 70)
print("工具调用测试完成")
print("=" * 70)

# 额外测试：检查模型列表 API
print("\n\n" + "=" * 70)
print("测试模型列表 API")
print("=" * 70)

try:
    models = client.models.list()
    print(f"\n获取到 {len(models.data)} 个模型")

    # 显示前几个模型的信息
    print("\n示例模型信息:")
    for model in list(models.data)[:3]:
        print(f"  - {model.id}")
        if hasattr(model, 'owned_by'):
            print(f"    owned_by: {model.owned_by}")
except Exception as e:
    print(f"错误: {e}")

print("\n" + "=" * 70)
print("所有测试完成")
print("=" * 70)
