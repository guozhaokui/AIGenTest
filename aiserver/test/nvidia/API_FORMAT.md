# NVIDIA NIM API 格式文档

本文档记录 NVIDIA NIM API 的使用格式，基于 OpenAI 兼容接口。

## 目录

- [基本配置](#基本配置)
- [聊天 API](#聊天-api)
- [流式输出](#流式输出)
- [思考内容（Reasoning）](#思考内容reasoning)
- [工具调用（Function Calling）](#工具调用function-calling)
- [模型列表](#模型列表)

---

## 基本配置

### API 端点
```
https://integrate.api.nvidia.com/v1
```

### Python 客户端初始化
```python
from openai import OpenAI

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="nvapi-xxx"  # 你的 NVIDIA API Key
)
```

### 环境变量
```bash
NVIDIA_API_KEY=nvapi-xxx
```

---

## 聊天 API

### 请求格式
```python
completion = client.chat.completions.create(
    model="meta/llama-3.1-8b-instruct",  # 模型 ID
    messages=[
        {"role": "system", "content": "你是一个有帮助的助手"},
        {"role": "user", "content": "你好"}
    ],
    temperature=0.7,      # 温度 (0-1)
    max_tokens=1024,      # 最大输出 token
    stream=False          # 是否流式
)
```

### 响应格式
```python
# completion 对象结构
{
    "id": "chatcmpl-xxx",
    "model": "meta/llama-3.1-8b-instruct",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "你好！有什么我可以帮助你的吗？"
        },
        "finish_reason": "stop"
    }],
    "usage": {
        "prompt_tokens": 10,
        "completion_tokens": 15,
        "total_tokens": 25
    }
}
```

### Python 访问响应
```python
# 获取回复内容
content = completion.choices[0].message.content

# 获取 token 使用量
usage = completion.usage
```

---

## 流式输出

### 请求格式
```python
stream = client.chat.completions.create(
    model="meta/llama-3.1-8b-instruct",
    messages=[{"role": "user", "content": "你好"}],
    stream=True  # 启用流式
)
```

### 处理流式响应
```python
for chunk in stream:
    if chunk.choices and len(chunk.choices) > 0:
        delta = chunk.choices[0].delta

        # 获取增量内容
        if delta.content:
            print(delta.content, end="", flush=True)
```

### 流式响应 chunk 格式
```python
{
    "id": "chatcmpl-xxx",
    "model": "meta/llama-3.1-8b-instruct",
    "choices": [{
        "index": 0,
        "delta": {
            "content": "你"  # 增量内容
        },
        "finish_reason": null
    }]
}
```

---

## 思考内容（Reasoning）

推理模型（如 DeepSeek R1、Kimi K2 Thinking）会返回思考过程。

### 支持的模型
- `deepseek-ai/deepseek-r1`
- `deepseek-ai/deepseek-r1-0528`
- `moonshotai/kimi-k2-thinking`
- `qwen/qwen3-next-80b-a3b-thinking`
- `qwen/qwq-32b`

### 非流式响应
思考内容在 `message.model_extra['reasoning_content']` 中：

```python
completion = client.chat.completions.create(
    model="deepseek-ai/deepseek-r1-0528",
    messages=[{"role": "user", "content": "23 * 47 = ?"}],
    stream=False
)

message = completion.choices[0].message

# 获取思考内容
reasoning = message.model_extra.get('reasoning_content')
print("思考过程:", reasoning)

# 获取最终答案
content = message.content
print("答案:", content)
```

### 流式响应
思考内容在 `delta.model_extra['reasoning_content']` 中：

```python
stream = client.chat.completions.create(
    model="deepseek-ai/deepseek-r1-0528",
    messages=[{"role": "user", "content": "23 * 47 = ?"}],
    stream=True
)

reasoning_content = ""
answer_content = ""

for chunk in stream:
    if chunk.choices and len(chunk.choices) > 0:
        delta = chunk.choices[0].delta

        # 获取思考内容增量
        if hasattr(delta, 'model_extra') and delta.model_extra:
            reasoning = delta.model_extra.get('reasoning_content')
            if reasoning:
                reasoning_content += reasoning
                print(f"[思考] {reasoning}", end="", flush=True)

        # 获取答案内容增量
        if delta.content:
            answer_content += delta.content
            print(delta.content, end="", flush=True)
```

### 响应结构示例
```python
# message 对象
{
    "role": "assistant",
    "content": "23 × 47 = 1081",
    "model_extra": {
        "reasoning_content": "首先，我需要计算 23 乘以 47..."
    }
}
```

---

## 工具调用（Function Calling）

### 定义工具
```python
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
    }
]
```

### 请求格式
```python
completion = client.chat.completions.create(
    model="meta/llama-3.1-70b-instruct",
    messages=[{"role": "user", "content": "北京今天天气怎么样？"}],
    tools=tools,
    tool_choice="auto"  # "auto" | "none" | {"type": "function", "function": {"name": "xxx"}}
)
```

### 响应格式（有工具调用时）
```python
message = completion.choices[0].message

# 检查是否有工具调用
if message.tool_calls:
    for tool_call in message.tool_calls:
        print(f"工具 ID: {tool_call.id}")
        print(f"函数名: {tool_call.function.name}")
        print(f"参数: {tool_call.function.arguments}")  # JSON 字符串
```

### tool_calls 结构
```python
{
    "role": "assistant",
    "content": null,
    "tool_calls": [{
        "id": "call_abc123",
        "type": "function",
        "function": {
            "name": "get_weather",
            "arguments": "{\"city\": \"北京\", \"unit\": \"celsius\"}"
        }
    }]
}
```

### 返回工具结果
```python
# 第一次调用后，如果模型请求工具调用，需要返回结果
messages = [
    {"role": "user", "content": "北京今天天气怎么样？"},
    {
        "role": "assistant",
        "content": null,
        "tool_calls": [{
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": "{\"city\": \"北京\"}"
            }
        }]
    },
    {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "{\"temperature\": 25, \"weather\": \"晴天\"}"
    }
]

# 继续对话
completion = client.chat.completions.create(
    model="meta/llama-3.1-70b-instruct",
    messages=messages
)
```

---

## 模型列表

### 获取所有可用模型
```python
models = client.models.list()

for model in models.data:
    print(f"ID: {model.id}")
    print(f"拥有者: {model.owned_by}")
```

### 推荐模型

#### 推理模型（支持思考过程）
| 模型 ID | 说明 |
|---------|------|
| `deepseek-ai/deepseek-r1` | DeepSeek R1，类似 OpenAI o1 |
| `deepseek-ai/deepseek-r1-0528` | DeepSeek R1 特定版本 |
| `moonshotai/kimi-k2-thinking` | Kimi K2 推理模型 |
| `qwen/qwen3-next-80b-a3b-thinking` | Qwen3 推理模型 |
| `qwen/qwq-32b` | QwQ 推理模型 |

#### 通用大模型
| 模型 ID | 说明 |
|---------|------|
| `deepseek-ai/deepseek-v3.2` | DeepSeek 最新版本 |
| `meta/llama-4-maverick-17b-128e-instruct` | Llama 4 (128专家) |
| `meta/llama-3.3-70b-instruct` | Llama 3.3 70B |
| `mistralai/mistral-large-3-675b-instruct-2512` | Mistral Large 3 |
| `qwen/qwen3-235b-a22b` | Qwen3 235B |
| `google/gemma-3-27b-it` | Gemma 3 27B |

#### 小型高效模型
| 模型 ID | 说明 |
|---------|------|
| `meta/llama-3.1-8b-instruct` | Llama 3.1 8B |
| `qwen/qwen2.5-7b-instruct` | Qwen 2.5 7B |
| `google/gemma-3-4b-it` | Gemma 3 4B |
| `microsoft/phi-4-mini-instruct` | Phi-4 Mini |

#### 代码模型
| 模型 ID | 说明 |
|---------|------|
| `qwen/qwen3-coder-480b-a35b-instruct` | Qwen3 Coder 480B |
| `qwen/qwen2.5-coder-32b-instruct` | Qwen 2.5 Coder 32B |
| `mistralai/devstral-2-123b-instruct-2512` | Devstral 2 123B |

---

## 错误处理

### 常见错误
```python
try:
    completion = client.chat.completions.create(...)
except openai.APIError as e:
    print(f"API 错误: {e}")
except openai.RateLimitError as e:
    print(f"速率限制: {e}")
except openai.AuthenticationError as e:
    print(f"认证失败: {e}")
```

### HTTP 状态码
| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求格式错误 |
| 401 | API Key 无效 |
| 429 | 请求频率超限 |
| 500 | 服务器错误 |

---

## 参考链接

- [NVIDIA NIM 官网](https://build.nvidia.com/models)
- [NVIDIA NIM 文档](https://docs.nvidia.com/nim/)
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
