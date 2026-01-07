from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
from openai import OpenAI
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / '.env'
load_dotenv(dotenv_path=env_path)

print(f"Loading .env from: {env_path}")
print(f".env exists: {env_path.exists()}")

app = Flask(__name__)
CORS(app)

# NVIDIA API 配置
NVIDIA_API_KEY = os.getenv('NVIDIA_API_KEY')
if not NVIDIA_API_KEY:
    raise ValueError("NVIDIA_API_KEY not found in environment variables")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY
)

# 可用的模型列表（按用户偏好排序）
AVAILABLE_MODELS = [
    # === 优先推荐 ===
    {
        "id": "z-ai/glm4.7",
        "name": "🔥 GLM-4.7",
        "description": "智谱 GLM-4.7，中文能力强"
    },
    {
        "id": "minimaxai/minimax-m2.1",
        "name": "🔥 MiniMax M2.1",
        "description": "MiniMax 最新版本"
    },
    {
        "id": "moonshotai/kimi-k2-thinking",
        "name": "🔥 Kimi K2 Thinking",
        "description": "月之暗面 Kimi K2 推理模型"
    },
    {
        "id": "deepseek-ai/deepseek-r1-0528",
        "name": "🔥 DeepSeek R1 (0528)",
        "description": "DeepSeek R1 特定版本"
    },
    {
        "id": "deepseek-ai/deepseek-v3.2",
        "name": "🔥 DeepSeek V3.2",
        "description": "DeepSeek 最新版本，强大的通用能力"
    },

    # === 推理模型（Reasoning Models） ===
    {
        "id": "deepseek-ai/deepseek-r1",
        "name": "DeepSeek R1",
        "description": "最新推理模型，类似 OpenAI o1，强大的思维链能力"
    },
    {
        "id": "qwen/qwen3-next-80b-a3b-thinking",
        "name": "🔥 Qwen3 Next 80B Thinking",
        "description": "Qwen3 推理模型，支持深度思考"
    },
    {
        "id": "deepseek-ai/deepseek-r1-distill-qwen-32b",
        "name": "DeepSeek R1 Distill Qwen 32B",
        "description": "R1 蒸馏版本，基于 Qwen 32B"
    },
    {
        "id": "deepseek-ai/deepseek-r1-distill-qwen-14b",
        "name": "DeepSeek R1 Distill Qwen 14B",
        "description": "R1 蒸馏版本，基于 Qwen 14B"
    },
    {
        "id": "deepseek-ai/deepseek-r1-distill-llama-8b",
        "name": "DeepSeek R1 Distill Llama 8B",
        "description": "R1 蒸馏版本，基于 Llama 8B"
    },
    {
        "id": "qwen/qwq-32b",
        "name": "QwQ 32B",
        "description": "Qwen 推理模型"
    },
    {
        "id": "microsoft/phi-4-mini-flash-reasoning",
        "name": "Phi-4 Mini Flash Reasoning",
        "description": "Microsoft 推理模型"
    },

    # === 最新版本大模型 ===
    {
        "id": "deepseek-ai/deepseek-v3.1",
        "name": "DeepSeek V3.1",
        "description": "DeepSeek 上一代旗舰模型"
    },
    {
        "id": "meta/llama-4-maverick-17b-128e-instruct",
        "name": "🔥 Llama 4 Maverick 17B (128 Experts)",
        "description": "Meta 最新 Llama 4，128专家MoE架构"
    },
    {
        "id": "meta/llama-4-scout-17b-16e-instruct",
        "name": "🔥 Llama 4 Scout 17B (16 Experts)",
        "description": "Meta Llama 4，16专家版本"
    },
    {
        "id": "meta/llama-3.3-70b-instruct",
        "name": "Llama 3.3 70B Instruct",
        "description": "Meta Llama 3.3，改进版"
    },
    {
        "id": "mistralai/mistral-large-3-675b-instruct-2512",
        "name": "🔥 Mistral Large 3 675B",
        "description": "Mistral 最新最大模型"
    },
    {
        "id": "mistralai/magistral-small-2506",
        "name": "Magistral Small",
        "description": "Mistral 2025年6月新模型"
    },
    {
        "id": "mistralai/devstral-2-123b-instruct-2512",
        "name": "Devstral 2 123B",
        "description": "Mistral 开发专用模型"
    },
    {
        "id": "mistralai/ministral-14b-instruct-2512",
        "name": "Ministral 14B",
        "description": "Mistral 小型高效模型"
    },
    {
        "id": "mistralai/mistral-small-3.1-24b-instruct-2503",
        "name": "Mistral Small 3.1 24B",
        "description": "Mistral Small 最新版"
    },
    {
        "id": "qwen/qwen3-coder-480b-a35b-instruct",
        "name": "🔥 Qwen3 Coder 480B",
        "description": "Qwen3 代码模型，480B参数"
    },
    {
        "id": "qwen/qwen3-235b-a22b",
        "name": "🔥 Qwen3 235B",
        "description": "Qwen3 大型模型"
    },
    {
        "id": "qwen/qwen3-next-80b-a3b-instruct",
        "name": "Qwen3 Next 80B",
        "description": "Qwen3 Next 系列"
    },
    {
        "id": "google/gemma-3-27b-it",
        "name": "🔥 Gemma 3 27B",
        "description": "Google 最新 Gemma 3"
    },
    {
        "id": "google/gemma-3-12b-it",
        "name": "Gemma 3 12B",
        "description": "Google Gemma 3 中等模型"
    },
    {
        "id": "google/gemma-3-4b-it",
        "name": "Gemma 3 4B",
        "description": "Google Gemma 3 小型模型"
    },
    {
        "id": "microsoft/phi-4-multimodal-instruct",
        "name": "🔥 Phi-4 Multimodal",
        "description": "Microsoft Phi-4 多模态模型"
    },
    {
        "id": "microsoft/phi-4-mini-instruct",
        "name": "Phi-4 Mini",
        "description": "Microsoft Phi-4 小型模型"
    },
    {
        "id": "moonshotai/kimi-k2-instruct",
        "name": "Kimi K2 Instruct",
        "description": "月之暗面 Kimi K2"
    },

    # === NVIDIA 模型 ===
    {
        "id": "nvidia/llama-3.3-nemotron-super-49b-v1.5",
        "name": "🔥 NVIDIA Nemotron Super 49B v1.5",
        "description": "NVIDIA 最新 Nemotron，基于 Llama 3.3"
    },
    {
        "id": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "name": "NVIDIA Nemotron Ultra 253B",
        "description": "NVIDIA 超大型模型"
    },
    {
        "id": "nvidia/llama-3.1-nemotron-70b-instruct",
        "name": "NVIDIA Nemotron 70B",
        "description": "NVIDIA 增强版 Llama 70B"
    },
    {
        "id": "nvidia/llama-3.1-nemotron-51b-instruct",
        "name": "NVIDIA Nemotron 51B",
        "description": "NVIDIA 中型高效模型"
    },
    {
        "id": "nvidia/cosmos-reason2-8b",
        "name": "NVIDIA Cosmos Reason2 8B",
        "description": "NVIDIA 推理模型"
    },

    # === 经典常用模型 ===
    {
        "id": "meta/llama-3.1-405b-instruct",
        "name": "Llama 3.1 405B",
        "description": "Meta 最大的 Llama 3.1 模型"
    },
    {
        "id": "meta/llama-3.1-70b-instruct",
        "name": "Llama 3.1 70B",
        "description": "强大的通用模型"
    },
    {
        "id": "meta/llama-3.1-8b-instruct",
        "name": "Llama 3.1 8B",
        "description": "快速高效的小型模型"
    },
    {
        "id": "mistralai/mistral-large-2-instruct",
        "name": "Mistral Large 2",
        "description": "Mistral 大型模型"
    },
    {
        "id": "mistralai/mixtral-8x22b-instruct-v0.1",
        "name": "Mixtral 8x22B",
        "description": "混合专家模型，高性能"
    },
    {
        "id": "mistralai/mixtral-8x7b-instruct-v0.1",
        "name": "Mixtral 8x7B",
        "description": "经典混合专家模型"
    },
    {
        "id": "qwen/qwen2.5-coder-32b-instruct",
        "name": "Qwen2.5 Coder 32B",
        "description": "强大的代码模型"
    },
    {
        "id": "qwen/qwen2.5-7b-instruct",
        "name": "Qwen2.5 7B",
        "description": "Qwen 2.5 小型模型"
    },
    {
        "id": "google/gemma-2-27b-it",
        "name": "Gemma 2 27B",
        "description": "Google Gemma 2 大型模型"
    },
    {
        "id": "google/gemma-2-9b-it",
        "name": "Gemma 2 9B",
        "description": "高效的中型模型"
    },
    {
        "id": "microsoft/phi-3.5-moe-instruct",
        "name": "Phi-3.5 MoE",
        "description": "Microsoft 混合专家模型"
    },
    {
        "id": "ibm/granite-3.3-8b-instruct",
        "name": "IBM Granite 3.3 8B",
        "description": "IBM 最新 Granite 模型"
    },
    {
        "id": "01-ai/yi-large",
        "name": "Yi Large",
        "description": "零一万物大模型"
    }
]

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/models', methods=['GET'])
def get_models():
    """获取可用的模型列表"""
    return jsonify({"models": AVAILABLE_MODELS})

@app.route('/api/chat', methods=['POST'])
def chat():
    """处理聊天请求"""
    try:
        data = request.json
        model = data.get('model', 'meta/llama-3.1-8b-instruct')
        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 1024)

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        # 调用 NVIDIA API
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False
        )

        message = completion.choices[0].message
        response_content = message.content

        # 获取思考内容（从 model_extra 中的 reasoning_content 字段）
        thinking_content = None
        if hasattr(message, 'model_extra') and message.model_extra:
            thinking_content = message.model_extra.get('reasoning_content')

        # 如果没有 reasoning_content，尝试从 content 中解析 <think> 标签
        if not thinking_content and response_content:
            if '<think>' in response_content and '</think>' in response_content:
                import re
                think_pattern = r'<think>(.*?)</think>'
                matches = re.findall(think_pattern, response_content, re.DOTALL)
                if matches:
                    thinking_content = '\n\n'.join(matches).strip()
                    # 移除思考标签，只保留答案
                    response_content = re.sub(think_pattern, '', response_content, flags=re.DOTALL).strip()

        return jsonify({
            "success": True,
            "message": response_content,
            "thinking": thinking_content,
            "model": model
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """流式聊天请求"""
    try:
        data = request.json
        model = data.get('model', 'meta/llama-3.1-8b-instruct')
        messages = data.get('messages', [])
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 4096)

        if not messages:
            return jsonify({"error": "No messages provided"}), 400

        def generate():
            try:
                # 调用 NVIDIA API（流式）
                stream = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True
                )

                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta

                        # 获取内容
                        content = delta.content if hasattr(delta, 'content') else None

                        # 获取思考内容（从 model_extra）
                        reasoning = None
                        if hasattr(delta, 'model_extra') and delta.model_extra:
                            reasoning = delta.model_extra.get('reasoning_content')

                        # 发送数据
                        if content or reasoning:
                            event_data = {
                                "content": content,
                                "reasoning": reasoning
                            }
                            yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

                # 发送完成信号
                yield f"data: {json.dumps({'done': True})}\n\n"

            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    print(f"Starting NVIDIA NIM Chat Server...")
    print(f"API Key configured: {NVIDIA_API_KEY[:10]}..." if NVIDIA_API_KEY else "No API Key")
    app.run(host='0.0.0.0', port=5000, debug=True)
