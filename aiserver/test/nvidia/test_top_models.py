#!/usr/bin/env python3
"""测试首选模型的各种能力"""

import os
import json
import time
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

# 首选模型
TOP_MODELS = [
    ("z-ai/glm4.7", "GLM-4.7"),
    ("minimaxai/minimax-m2.1", "MiniMax M2.1"),
    ("moonshotai/kimi-k2-thinking", "Kimi K2 Thinking"),
    ("deepseek-ai/deepseek-r1-0528", "DeepSeek R1"),
    ("deepseek-ai/deepseek-v3.2", "DeepSeek V3.2"),
]

# 工具定义
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名称"}
                },
                "required": ["city"]
            }
        }
    }
]


def test_basic_chat(model_id, model_name):
    """测试基本聊天"""
    print(f"\n  [基本聊天]", end=" ")
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "用一句话介绍你自己"}],
            max_tokens=100,
            temperature=0.7
        )
        elapsed = time.time() - start
        content = completion.choices[0].message.content[:50]
        print(f"✅ ({elapsed:.1f}s) {content}...")
        return True
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        return False


def test_reasoning(model_id, model_name):
    """测试推理能力（思考过程）"""
    print(f"\n  [推理/思考]", end=" ")
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "7 * 8 = ?"}],
            max_tokens=500,
            temperature=0.1
        )
        elapsed = time.time() - start
        message = completion.choices[0].message

        # 检查是否有思考内容
        reasoning = None
        if hasattr(message, 'model_extra') and message.model_extra:
            reasoning = message.model_extra.get('reasoning_content')

        if reasoning:
            print(f"✅ 有思考过程 ({elapsed:.1f}s)")
            print(f"      思考: {reasoning[:60]}...")
            print(f"      答案: {message.content[:40]}")
        else:
            print(f"⚠️ 无思考过程 ({elapsed:.1f}s)")
            print(f"      答案: {message.content[:60]}")
        return True
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        return False


def test_tool_calling(model_id, model_name):
    """测试工具调用"""
    print(f"\n  [工具调用]", end=" ")
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "北京天气如何？"}],
            tools=tools,
            tool_choice="auto",
            max_tokens=200,
            temperature=0.1
        )
        elapsed = time.time() - start
        message = completion.choices[0].message

        if message.tool_calls:
            tc = message.tool_calls[0]
            print(f"✅ 支持 ({elapsed:.1f}s)")
            print(f"      函数: {tc.function.name}")
            print(f"      参数: {tc.function.arguments}")
        else:
            print(f"⚠️ 未调用工具 ({elapsed:.1f}s)")
            if message.content:
                print(f"      回复: {message.content[:50]}...")
        return True
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        return False


def test_streaming(model_id, model_name):
    """测试流式输出"""
    print(f"\n  [流式输出]", end=" ")
    try:
        start = time.time()
        stream = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "数到5"}],
            max_tokens=50,
            stream=True
        )

        chunks = 0
        content = ""
        reasoning = ""

        for chunk in stream:
            chunks += 1
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                if delta.content:
                    content += delta.content
                if hasattr(delta, 'model_extra') and delta.model_extra:
                    r = delta.model_extra.get('reasoning_content')
                    if r:
                        reasoning += r

        elapsed = time.time() - start

        if reasoning:
            print(f"✅ ({elapsed:.1f}s, {chunks} chunks, 有思考流)")
        else:
            print(f"✅ ({elapsed:.1f}s, {chunks} chunks)")
        print(f"      内容: {content[:50]}...")
        return True
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        return False


def test_chinese(model_id, model_name):
    """测试中文能力"""
    print(f"\n  [中文能力]", end=" ")
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "用成语形容春天"}],
            max_tokens=100,
            temperature=0.7
        )
        elapsed = time.time() - start
        content = completion.choices[0].message.content
        print(f"✅ ({elapsed:.1f}s) {content[:50]}...")
        return True
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        return False


def test_code(model_id, model_name):
    """测试代码能力"""
    print(f"\n  [代码能力]", end=" ")
    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "写一个Python冒泡排序，只要代码"}],
            max_tokens=300,
            temperature=0.1
        )
        elapsed = time.time() - start
        content = completion.choices[0].message.content
        has_code = "def" in content or "for" in content
        print(f"✅ ({elapsed:.1f}s) {'有代码' if has_code else '无代码'}")
        print(f"      {content[:60].replace(chr(10), ' ')}...")
        return True
    except Exception as e:
        print(f"❌ {str(e)[:50]}")
        return False


def main():
    print("=" * 70)
    print("NVIDIA NIM 首选模型能力测试")
    print("=" * 70)

    results = {}

    for model_id, model_name in TOP_MODELS:
        print(f"\n{'='*70}")
        print(f"📦 {model_name} ({model_id})")
        print("=" * 70)

        results[model_name] = {
            "basic": test_basic_chat(model_id, model_name),
            "reasoning": test_reasoning(model_id, model_name),
            "tool": test_tool_calling(model_id, model_name),
            "stream": test_streaming(model_id, model_name),
            "chinese": test_chinese(model_id, model_name),
            "code": test_code(model_id, model_name),
        }

        time.sleep(1)  # 避免频率限制

    # 汇总结果
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"\n{'模型':<20} {'基本':<6} {'推理':<6} {'工具':<6} {'流式':<6} {'中文':<6} {'代码':<6}")
    print("-" * 70)

    for model_name, tests in results.items():
        row = f"{model_name:<20}"
        for test_name in ["basic", "reasoning", "tool", "stream", "chinese", "code"]:
            status = "✅" if tests.get(test_name) else "❌"
            row += f" {status:<6}"
        print(row)

    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
