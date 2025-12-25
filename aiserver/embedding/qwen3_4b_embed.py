"""
Qwen3-4B 文本嵌入服务
复用 Z-Image-Turbo 的 text_encoder，使用倒数第二层作为嵌入

使用指令增强（Instruction-based Embedding）提升检索效果
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

# 指令前缀（提升检索效果）
# 测试发现 "关于" 效果最好，区分度 0.147（比 "为了语义搜索" 的 0.117 高 25%）
INSTRUCTION_PREFIX = "关于"

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
    使用倒数第二层的隐藏状态
    
    注意：添加指令前缀以提升检索效果
    使用 last token pooling（对于 causal LM 更合适）
    
    Args:
        text: 输入文本
    
    Returns:
        归一化的嵌入向量
    """
    # 添加指令前缀
    text_with_instruction = f"{INSTRUCTION_PREFIX}{text}"
    
    # 直接对文本编码
    inputs = tokenizer(
        text_with_instruction,
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
        
        # Last token pooling（对于 causal LM，最后一个 token 包含整个序列的信息）
        # 找到每个序列的最后一个有效 token 位置
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = hidden_states.shape[0]
        embedding = hidden_states[torch.arange(batch_size), sequence_lengths]
    
    # 归一化
    embedding = embedding[0].float().cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def compute_text_embeddings_batch(texts: List[str]) -> np.ndarray:
    """
    批量计算文本的嵌入向量
    
    注意：添加指令前缀以提升检索效果
    使用 last token pooling
    
    Args:
        texts: 输入文本列表
    
    Returns:
        归一化的嵌入向量矩阵 (N, dimension)
    """
    # 添加指令前缀
    texts_with_instruction = [f"{INSTRUCTION_PREFIX}{t}" for t in texts]
    
    # 直接对文本编码
    inputs = tokenizer(
        texts_with_instruction,
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
        
        # Last token pooling
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = hidden_states.shape[0]
        embeddings = hidden_states[torch.arange(batch_size), sequence_lengths]
    
    # 归一化
    embeddings = embeddings.float().cpu().numpy()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    return embeddings


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_embed_4b
    
    port = port_embed_4b()
    print(f"启动 Qwen3-4B 文本嵌入服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
