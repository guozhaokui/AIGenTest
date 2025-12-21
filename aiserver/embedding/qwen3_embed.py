"""
Qwen3-4B 文本嵌入服务
复用 Z-Image-Turbo 的 text_encoder，使用倒数第二层作为嵌入
"""
import torch
from transformers import AutoTokenizer, AutoModel
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
from pydantic import BaseModel
from typing import List

# Initialize FastAPI app
app = FastAPI(title="Qwen3-4B Text Embedding API")

# Model configuration - 复用 Z-Image-Turbo 的组件
MODEL_PATH = "/mnt/hdd/models/Z-Image-Turbo"
MODEL_NAME = "Qwen3-4B"
MODEL_VERSION = "1.0"
DIMENSION = 2560  # Qwen3-4B hidden_size

# Global model and tokenizer
model = None
tokenizer = None


def load_model():
    """加载 Qwen3 模型（复用 Z-Image-Turbo 的 text_encoder）"""
    global model, tokenizer
    print(f"Loading Qwen3 text encoder from {MODEL_PATH}...")
    try:
        # 加载 tokenizer
        tokenizer = AutoTokenizer.from_pretrained(f"{MODEL_PATH}/tokenizer")
        
        # 加载 text_encoder
        model = AutoModel.from_pretrained(
            f"{MODEL_PATH}/text_encoder",
            torch_dtype=torch.bfloat16,
        )
        model.to("cuda")
        model.eval()
        print("Qwen3 text encoder loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e


class TextRequest(BaseModel):
    """单个文本请求"""
    text: str


class TextsRequest(BaseModel):
    """批量文本请求"""
    texts: List[str]


@app.on_event("startup")
async def startup_event():
    load_model()


@app.get("/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "version": MODEL_VERSION,
        "dimension": DIMENSION,
        "device": str(next(model.parameters()).device) if model else "not loaded"
    }


@app.post("/embed/text")
async def embed_text(req: TextRequest):
    """
    计算单个文本的嵌入向量
    
    Args:
        text: 输入文本
    
    Returns:
        embedding: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        embedding = compute_text_embedding(req.text)
        
        return JSONResponse(content={
            "embedding": embedding.tolist(),
            "dimension": len(embedding),
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        })
    
    except Exception as e:
        print(f"Error embedding text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/texts")
async def embed_texts(req: TextsRequest):
    """
    批量计算文本的嵌入向量
    
    Args:
        texts: 输入文本列表
    
    Returns:
        embeddings: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        embeddings = compute_text_embeddings_batch(req.texts)
        
        return JSONResponse(content={
            "embeddings": embeddings.tolist(),
            "dimension": embeddings.shape[1],
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        })
    
    except Exception as e:
        print(f"Error embedding texts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def compute_text_embedding(text: str) -> np.ndarray:
    """
    计算单个文本的嵌入向量
    使用倒数第二层的隐藏状态，与 Z-Image 保持一致
    
    Args:
        text: 输入文本
    
    Returns:
        归一化的嵌入向量
    """
    # 使用 chat template 格式化（与 Z-Image 一致）
    messages = [{"role": "user", "content": text}]
    formatted_text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=True,
    )
    
    # Tokenize
    inputs = tokenizer(
        formatted_text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512
    )
    input_ids = inputs.input_ids.to("cuda")
    attention_mask = inputs.attention_mask.to("cuda")
    
    # 计算嵌入 - 使用倒数第二层
    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True,
        )
        # 取倒数第二层
        hidden_states = outputs.hidden_states[-2]
        
        # Mean pooling（只对有效 token 进行）
        mask_expanded = attention_mask.unsqueeze(-1).expand(hidden_states.size()).float()
        sum_embeddings = torch.sum(hidden_states * mask_expanded, dim=1)
        sum_mask = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
        embedding = sum_embeddings / sum_mask
    
    # 归一化
    embedding = embedding[0].float().cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def compute_text_embeddings_batch(texts: List[str]) -> np.ndarray:
    """
    批量计算文本的嵌入向量
    
    Args:
        texts: 输入文本列表
    
    Returns:
        归一化的嵌入向量矩阵 (N, dimension)
    """
    # 使用 chat template 格式化
    formatted_texts = []
    for text in texts:
        messages = [{"role": "user", "content": text}]
        formatted_text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True,
        )
        formatted_texts.append(formatted_text)
    
    # Tokenize
    inputs = tokenizer(
        formatted_texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512
    )
    input_ids = inputs.input_ids.to("cuda")
    attention_mask = inputs.attention_mask.to("cuda")
    
    # 计算嵌入 - 使用倒数第二层
    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            output_hidden_states=True,
        )
        hidden_states = outputs.hidden_states[-2]
        
        # Mean pooling
        mask_expanded = attention_mask.unsqueeze(-1).expand(hidden_states.size()).float()
        sum_embeddings = torch.sum(hidden_states * mask_expanded, dim=1)
        sum_mask = torch.clamp(mask_expanded.sum(dim=1), min=1e-9)
        embeddings = sum_embeddings / sum_mask
    
    # 归一化
    embeddings = embeddings.float().cpu().numpy()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    return embeddings


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6011)
