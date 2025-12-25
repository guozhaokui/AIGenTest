"""
Qwen3-Embedding-8B 文本嵌入服务
使用阿里通义千问专用嵌入模型，效果优于通用语言模型

支持 INT8 量化以节省显存（约 8GB）
"""
import sys
from pathlib import Path

# 添加 aiserver 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from transformers import AutoTokenizer, AutoModel, BitsAndBytesConfig
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
from pydantic import BaseModel
from typing import List, Optional

from config import model_path_embed_8b

# Initialize FastAPI app
app = FastAPI(title="Qwen3-Embedding-8B Text Embedding API")

# Model configuration - 从 config.yaml 读取
MODEL_PATH = model_path_embed_8b()
MODEL_NAME = "Qwen3-Embedding-8B"
MODEL_VERSION = "1.0"
DIMENSION = 4096  # Qwen3-8B hidden_size

# 是否使用 INT8 量化（节省显存）
USE_QUANTIZATION = True

# Global model and tokenizer
model = None
tokenizer = None


def last_token_pool(last_hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    """
    使用 Last Token Pooling 获取句子嵌入
    对于 causal LM，最后一个 token 包含整个序列的信息
    """
    left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
    if left_padding:
        return last_hidden_states[:, -1]
    else:
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = last_hidden_states.shape[0]
        return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]


def load_model():
    """加载 Qwen3-Embedding-8B 模型"""
    global model, tokenizer
    print(f"Loading Qwen3-Embedding-8B from {MODEL_PATH}...")
    print(f"Using quantization: {USE_QUANTIZATION}")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        
        if USE_QUANTIZATION:
            # 使用 INT8 量化
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            model = AutoModel.from_pretrained(
                MODEL_PATH,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True,
            )
        else:
            # 不使用量化（需要约 16GB 显存）
            model = AutoModel.from_pretrained(
                MODEL_PATH,
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
            )
            model.to("cuda")
        
        model.eval()
        print("Qwen3-Embedding-8B loaded successfully.")
        
        # 打印显存使用
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"GPU memory allocated: {memory_allocated:.2f} GB")
            
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e


class TextRequest(BaseModel):
    """单个文本请求"""
    text: str
    instruction: Optional[str] = None  # 可选的任务指令


class TextsRequest(BaseModel):
    """批量文本请求"""
    texts: List[str]
    instruction: Optional[str] = None  # 可选的任务指令


@app.on_event("startup")
async def startup_event():
    load_model()


@app.get("/health")
def health_check():
    """健康检查"""
    memory_allocated = 0
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
    
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "version": MODEL_VERSION,
        "dimension": DIMENSION,
        "quantization": USE_QUANTIZATION,
        "memory_gb": round(memory_allocated, 2),
        "device": str(next(model.parameters()).device) if model else "not loaded"
    }


def get_detailed_instruct(task_description: str, query: str) -> str:
    """
    构造带任务指令的输入（Qwen3-Embedding 推荐格式）
    """
    return f"Instruct: {task_description}\nQuery: {query}"


@app.post("/embed/text")
async def embed_text(req: TextRequest):
    """
    计算单个文本的嵌入向量
    
    Args:
        text: 输入文本
        instruction: 可选的任务指令（如 "Retrieve relevant documents"）
    
    Returns:
        embedding: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        embedding = compute_embedding(req.text, req.instruction)
        
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
        instruction: 可选的任务指令
    
    Returns:
        embeddings: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        embeddings = compute_embeddings_batch(req.texts, req.instruction)
        
        return JSONResponse(content={
            "embeddings": embeddings.tolist(),
            "dimension": embeddings.shape[1],
            "count": len(req.texts),
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        })
    
    except Exception as e:
        print(f"Error embedding texts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def compute_embedding(text: str, instruction: Optional[str] = None) -> np.ndarray:
    """
    计算单个文本的嵌入向量
    
    Args:
        text: 输入文本
        instruction: 可选的任务指令
    
    Returns:
        归一化的嵌入向量
    """
    # 如果有任务指令，使用指令格式
    if instruction:
        text = get_detailed_instruct(instruction, text)
    
    # Tokenize
    inputs = tokenizer(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=8192  # Qwen3-Embedding 支持长文本
    )
    
    # Move to device
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # 计算嵌入
    with torch.no_grad():
        outputs = model(**inputs)
        embedding = last_token_pool(outputs.last_hidden_state, inputs['attention_mask'])
    
    # 归一化
    embedding = embedding[0].float().cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def compute_embeddings_batch(texts: List[str], instruction: Optional[str] = None) -> np.ndarray:
    """
    批量计算文本的嵌入向量
    
    Args:
        texts: 输入文本列表
        instruction: 可选的任务指令
    
    Returns:
        归一化的嵌入向量矩阵 (N, dimension)
    """
    # 如果有任务指令，使用指令格式
    if instruction:
        texts = [get_detailed_instruct(instruction, t) for t in texts]
    
    # Tokenize
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=8192
    )
    
    # Move to device
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    # 计算嵌入
    with torch.no_grad():
        outputs = model(**inputs)
        embeddings = last_token_pool(outputs.last_hidden_state, inputs['attention_mask'])
    
    # 归一化
    embeddings = embeddings.float().cpu().numpy()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    return embeddings


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_embed_8b
    
    port = port_embed_8b()
    print(f"启动 Qwen3-Embedding-8B 服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

