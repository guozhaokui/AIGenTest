#!/usr/bin/env python3
"""
Qwen3-VL Vision Language Model 服务
基于 transformers + FastAPI，提供 OpenAI 兼容的 API

使用方法:
    conda activate qwen
    python vlm_service.py [--port 8080] [--gpu 0]
"""

import argparse
import base64
import os
import re
import time
import torch
import uvicorn
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import List, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import requests as http_requests

# 默认模型路径
DEFAULT_MODEL_PATH = "/data1/MLLM/qwen2.5vl/Qwen/Qwen/Qwen3-VL-8B-Instruct"

# 全局模型和处理器
model = None
processor = None


class ImageUrl(BaseModel):
    url: str


class ContentItem(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[ImageUrl] = None
    image: Optional[str] = None  # 兼容 Qwen 格式


class Message(BaseModel):
    role: str
    content: Union[str, List[ContentItem]]


class ChatRequest(BaseModel):
    model: str = "qwen3-vl"
    messages: List[Message]
    max_tokens: Optional[int] = 1024
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.8
    top_k: Optional[int] = 20
    stream: Optional[bool] = False


class Choice(BaseModel):
    index: int
    message: Message
    finish_reason: str


class Usage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage


def load_model(model_path: str):
    """加载模型"""
    global model, processor
    
    print(f"🔄 正在加载模型: {model_path}")
    
    from transformers import AutoModelForVision2Seq, AutoProcessor
    
    # 使用 AutoModelForVision2Seq 自动加载正确的模型类
    # Qwen3-VL 使用 Qwen3VLForConditionalGeneration
    # Qwen2.5-VL 使用 Qwen2_5_VLForConditionalGeneration
    
    # 尝试使用 flash_attention_2
    try:
        model = AutoModelForVision2Seq.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            device_map="auto",
            trust_remote_code=True,
        )
        print("✅ 使用 Flash Attention 2")
    except Exception as e:
        print(f"⚠️ Flash Attention 不可用，使用默认注意力: {e}")
        model = AutoModelForVision2Seq.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            trust_remote_code=True,
        )
    
    processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)
    
    # 尝试使用 torch.compile 优化（PyTorch 2.0+）
    try:
        model = torch.compile(model, mode="reduce-overhead")
        print("✅ 已启用 torch.compile 优化")
    except Exception as e:
        print(f"⚠️ torch.compile 不可用: {e}")
    
    print(f"✅ 模型加载完成! 模型类型: {type(model).__name__}")
    return model, processor


def convert_messages_to_qwen_format(messages: List[Message]) -> list:
    """将 OpenAI 格式的消息转换为 Qwen 格式"""
    qwen_messages = []
    
    for msg in messages:
        qwen_msg = {"role": msg.role, "content": []}
        
        if isinstance(msg.content, str):
            qwen_msg["content"] = [{"type": "text", "text": msg.content}]
        else:
            for item in msg.content:
                if item.type == "text":
                    qwen_msg["content"].append({
                        "type": "text",
                        "text": item.text
                    })
                elif item.type == "image_url" and item.image_url:
                    qwen_msg["content"].append({
                        "type": "image",
                        "image": item.image_url.url
                    })
                elif item.type == "image" and item.image:
                    qwen_msg["content"].append({
                        "type": "image",
                        "image": item.image
                    })
        
        qwen_messages.append(qwen_msg)
    
    return qwen_messages


def generate_response(messages: List[Message], **kwargs) -> tuple:
    """生成回复"""
    from qwen_vl_utils import process_vision_info
    
    # 转换消息格式
    qwen_messages = convert_messages_to_qwen_format(messages)
    
    # 准备输入
    text = processor.apply_chat_template(
        qwen_messages, 
        tokenize=False, 
        add_generation_prompt=True
    )
    
    image_inputs, video_inputs = process_vision_info(qwen_messages)
    
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model.device)
    
    # 生成参数
    gen_kwargs = {
        "max_new_tokens": kwargs.get("max_tokens", 1024),
        "temperature": kwargs.get("temperature", 0.7),
        "top_p": kwargs.get("top_p", 0.8),
        "top_k": kwargs.get("top_k", 20),
        "do_sample": kwargs.get("temperature", 0.7) > 0,
    }
    
    # 生成
    with torch.no_grad():
        generated_ids = model.generate(**inputs, **gen_kwargs)
    
    # 解码输出
    generated_ids_trimmed = [
        out_ids[len(in_ids):] 
        for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    
    output_text = processor.batch_decode(
        generated_ids_trimmed, 
        skip_special_tokens=True, 
        clean_up_tokenization_spaces=False
    )[0]
    
    # 计算 token 数量
    prompt_tokens = inputs.input_ids.shape[1]
    completion_tokens = generated_ids_trimmed[0].shape[0]
    
    return output_text, prompt_tokens, completion_tokens


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    model_path = os.environ.get("MODEL_PATH", DEFAULT_MODEL_PATH)
    load_model(model_path)
    yield


app = FastAPI(title="Qwen3-VL API", lifespan=lifespan)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Caption API (兼容 imagemgr) ====================

class CaptionRequest(BaseModel):
    """图片描述请求（兼容 imagemgr 调用格式）"""
    image_base64: str
    prompt: Optional[str] = "请详细描述这张图片的内容，包括主要物体、场景、颜色、风格等特征。"
    max_tokens: Optional[int] = 512
    temperature: Optional[float] = 0.7


class CaptionResponse(BaseModel):
    """图片描述响应"""
    caption: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None


@app.post("/caption")
async def generate_caption(request: CaptionRequest):
    """
    生成图片描述 API（兼容 imagemgr 调用）
    
    请求格式:
        {"image_base64": "...", "prompt": "描述这张图片"}
    
    响应格式:
        {"caption": "图片描述内容"}
    """
    try:
        # 构造 base64 URL
        image_url = f"data:image/jpeg;base64,{request.image_base64}"
        
        # 构建消息
        messages = [
            Message(
                role="user",
                content=[
                    ContentItem(type="image_url", image_url=ImageUrl(url=image_url)),
                    ContentItem(type="text", text=request.prompt)
                ]
            )
        ]
        
        # 生成回复
        output_text, prompt_tokens, completion_tokens = generate_response(
            messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        
        return CaptionResponse(
            caption=output_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 基础端点 ====================

@app.get("/")
async def root():
    return {
        "message": "Qwen3-VL VLM Service",
        "model": DEFAULT_MODEL_PATH,
        "endpoints": {
            "caption": "/caption (兼容 imagemgr)",
            "chat": "/v1/chat/completions",
            "models": "/v1/models"
        }
    }


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": "qwen3-vl",
                "object": "model",
                "created": 1700000000,
                "owned_by": "qwen"
            }
        ]
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatRequest):
    """聊天补全 API"""
    try:
        output_text, prompt_tokens, completion_tokens = generate_response(
            request.messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            top_p=request.top_p,
            top_k=request.top_k,
        )
        
        response = ChatResponse(
            id=f"chatcmpl-{int(time.time())}",
            created=int(time.time()),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=Message(role="assistant", content=output_text),
                    finish_reason="stop"
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens
            )
        )
        
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def main():
    parser = argparse.ArgumentParser(description="Qwen3-VL VLM 服务")
    
    parser.add_argument(
        "--host", 
        type=str, 
        default="0.0.0.0",
        help="监听地址 (默认: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=6050,
        help="监听端口 (默认: 6050)"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"模型路径 (默认: {DEFAULT_MODEL_PATH})"
    )
    parser.add_argument(
        "--gpu",
        type=str,
        default="1",
        help="使用的 GPU 设备号 (默认: 1)"
    )
    
    args = parser.parse_args()
    
    # 设置 GPU（如果环境变量未设置则使用参数）
    if "CUDA_VISIBLE_DEVICES" not in os.environ:
        os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    os.environ["MODEL_PATH"] = args.model_path
    
    print("=" * 60)
    print("🚀 Qwen3-VL VLM 服务")
    print("=" * 60)
    print(f"📦 模型: {args.model_path}")
    print(f"🌐 地址: http://{args.host}:{args.port}")
    print(f"🎮 GPU: {args.gpu}")
    print("=" * 60)
    print()
    print("API 端点:")
    print(f"  POST http://{args.host}:{args.port}/caption  (imagemgr 兼容)")
    print(f"  POST http://{args.host}:{args.port}/v1/chat/completions")
    print(f"  GET  http://{args.host}:{args.port}/v1/models")
    print()
    print("按 Ctrl+C 停止服务")
    print("=" * 60)
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
