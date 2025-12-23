#!/usr/bin/env python3
"""
Qwen3-VL VLM 服务 (vLLM 版本)
使用 vLLM 实现高性能推理，支持连续批处理

安装: pip install vllm

使用方法:
    conda activate qwen
    python vlm_service_vllm.py [--port 6050] [--gpu 1]
"""

import argparse
import base64
import os
import time
from io import BytesIO
from typing import List, Optional, Union

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image

# 默认模型路径
DEFAULT_MODEL_PATH = "/data1/MLLM/qwen2.5vl/Qwen/Qwen/Qwen3-VL-8B-Instruct"

# 全局 vLLM 引擎
llm = None
processor = None


class ImageUrl(BaseModel):
    url: str


class ContentItem(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None
    image: Optional[str] = None


class Message(BaseModel):
    role: str
    content: Union[str, List[ContentItem]]


class ChatRequest(BaseModel):
    model: str = "qwen3-vl"
    messages: List[Message]
    max_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.8
    stream: Optional[bool] = False


class CaptionRequest(BaseModel):
    image_base64: str
    prompt: Optional[str] = "请详细描述这张图片的内容。"
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7


class CaptionResponse(BaseModel):
    caption: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


def load_vllm_model(model_path: str, tensor_parallel_size: int = 1):
    """加载 vLLM 模型"""
    global llm, processor
    
    print(f"🔄 正在加载 vLLM 模型: {model_path}")
    
    try:
        from vllm import LLM, SamplingParams
        from transformers import AutoProcessor as TFProcessor
        
        # 加载 vLLM 引擎
        llm = LLM(
            model=model_path,
            trust_remote_code=True,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=0.9,
            max_model_len=8192,
            dtype="bfloat16",
        )
        
        # 加载处理器
        processor = TFProcessor.from_pretrained(model_path, trust_remote_code=True)
        
        print("✅ vLLM 模型加载完成!")
        return llm, processor
        
    except ImportError:
        print("❌ vLLM 未安装，请运行: pip install vllm")
        raise
    except Exception as e:
        print(f"❌ 加载 vLLM 模型失败: {e}")
        raise


def decode_image(image_url: str) -> Image.Image:
    """解码图片 URL 或 base64"""
    import re
    import requests
    
    if image_url.startswith("data:"):
        match = re.match(r"data:image/\w+;base64,(.+)", image_url)
        if match:
            image_data = base64.b64decode(match.group(1))
            return Image.open(BytesIO(image_data)).convert("RGB")
    elif image_url.startswith("http"):
        response = requests.get(image_url, timeout=30)
        return Image.open(BytesIO(response.content)).convert("RGB")
    
    raise ValueError("无法解码图片")


app = FastAPI(title="Qwen3-VL API (vLLM)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Qwen3-VL VLM Service (vLLM)",
        "model": DEFAULT_MODEL_PATH,
        "backend": "vLLM",
        "endpoints": {
            "caption": "/caption",
            "chat": "/v1/chat/completions"
        }
    }


@app.post("/caption")
async def generate_caption(request: CaptionRequest):
    """生成图片描述 (批处理优化)"""
    from vllm import SamplingParams
    
    try:
        # 解码图片
        image_data = base64.b64decode(request.image_base64)
        image = Image.open(BytesIO(image_data)).convert("RGB")
        
        # 构建消息
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": request.prompt}
                ]
            }
        ]
        
        # 准备输入
        text = processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        
        # 采样参数
        sampling_params = SamplingParams(
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=0.8,
        )
        
        # 生成
        outputs = llm.generate(
            [{"prompt": text, "multi_modal_data": {"image": image}}],
            sampling_params
        )
        
        output_text = outputs[0].outputs[0].text
        
        return CaptionResponse(
            caption=output_text,
            prompt_tokens=len(outputs[0].prompt_token_ids),
            completion_tokens=len(outputs[0].outputs[0].token_ids)
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": "qwen3-vl", "object": "model", "owned_by": "qwen"}]
    }


def main():
    parser = argparse.ArgumentParser(description="Qwen3-VL VLM 服务 (vLLM)")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=6050)
    parser.add_argument("--model-path", type=str, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--gpu", type=str, default="1")
    parser.add_argument("--tensor-parallel", type=int, default=1, 
                        help="张量并行数（使用多个 GPU）")
    
    args = parser.parse_args()
    
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    
    print("=" * 60)
    print("🚀 Qwen3-VL VLM 服务 (vLLM 高性能版)")
    print("=" * 60)
    print(f"📦 模型: {args.model_path}")
    print(f"🌐 地址: http://{args.host}:{args.port}")
    print(f"🎮 GPU: {args.gpu}")
    print(f"⚡ 后端: vLLM (连续批处理)")
    print("=" * 60)
    
    # 加载模型
    load_vllm_model(args.model_path, args.tensor_parallel)
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

