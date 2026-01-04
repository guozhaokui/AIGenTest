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
DIMENSION = 4096  # Qwen3-8B hidden_size，支持 MRL 可输出 32-4096 任意维度
MAX_LENGTH = 32768  # 官方支持 32K context length

# 是否使用 INT8 量化（节省显存）
USE_QUANTIZATION = True
# 是否使用 flash_attention_2 加速（需要 pip install flash-attn --no-build-isolation）
USE_FLASH_ATTENTION = False  # 没有安装 flash-attn 时设为 False

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
    print(f"Using flash_attention_2: {USE_FLASH_ATTENTION}")
    
    try:
        # 注意：官方要求 padding_side='left'
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True, padding_side='left')
        
        # 构建模型加载参数
        model_kwargs = {
            "trust_remote_code": True,
        }
        
        # 使用 flash_attention_2 加速（官方推荐）
        if USE_FLASH_ATTENTION:
            model_kwargs["attn_implementation"] = "flash_attention_2"
        
        if USE_QUANTIZATION:
            # 使用 INT8 量化
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            model_kwargs["quantization_config"] = quantization_config
            model_kwargs["device_map"] = "auto"
            model = AutoModel.from_pretrained(MODEL_PATH, **model_kwargs)
        else:
            # 不使用量化（需要约 16GB 显存）
            model_kwargs["torch_dtype"] = torch.float16  # 官方推荐 float16
            model = AutoModel.from_pretrained(MODEL_PATH, **model_kwargs)
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
    instruction: Optional[str] = None  # 可选的任务指令（仅用于 query，document 不需要）
    is_query: bool = True  # True 表示是 query（需要 instruction），False 表示是 document
    output_dimension: Optional[int] = None  # 可选的输出维度（MRL 支持，32-4096）


class TextsRequest(BaseModel):
    """批量文本请求"""
    texts: List[str]
    instruction: Optional[str] = None  # 可选的任务指令（仅用于 query）
    is_query: bool = True  # True 表示是 query，False 表示是 document
    output_dimension: Optional[int] = None  # 可选的输出维度（MRL 支持，32-4096）


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
    构造带任务指令的输入（Qwen3-Embedding 官方格式）
    注意：Query: 后面没有空格
    """
    return f"Instruct: {task_description}\nQuery:{query}"


@app.post("/embed/text")
async def embed_text(req: TextRequest):
    """
    计算单个文本的嵌入向量
    
    Args:
        text: 输入文本
        instruction: 可选的任务指令（如 "Given a web search query, retrieve relevant passages that answer the query"）
        is_query: True 表示是 query（会应用 instruction），False 表示是 document（不需要 instruction）
        output_dimension: 可选的输出维度（MRL 支持，32-4096）
    
    Returns:
        embedding: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        # 只有 query 才需要 instruction，document 不需要
        instruction = req.instruction if req.is_query else None
        embedding = compute_embedding(req.text, instruction, req.output_dimension)
        
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
        instruction: 可选的任务指令（仅用于 query）
        is_query: True 表示是 query 列表，False 表示是 document 列表
        output_dimension: 可选的输出维度（MRL 支持，32-4096）
    
    Returns:
        embeddings: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        # 只有 query 才需要 instruction，document 不需要
        instruction = req.instruction if req.is_query else None
        embeddings = compute_embeddings_batch(req.texts, instruction, req.output_dimension)
        
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


def truncate_embedding(embedding: np.ndarray, output_dimension: Optional[int] = None) -> np.ndarray:
    """
    MRL (Matryoshka Representation Learning) 支持：截断到指定维度并重新归一化
    
    Args:
        embedding: 原始嵌入向量
        output_dimension: 目标维度（32-4096），None 表示使用原始维度
    
    Returns:
        截断并归一化的嵌入向量
    """
    if output_dimension is None or output_dimension >= len(embedding):
        return embedding
    
    if output_dimension < 32:
        output_dimension = 32  # 最小维度
    
    # 截断到指定维度
    truncated = embedding[:output_dimension]
    # 重新归一化
    norm = np.linalg.norm(truncated)
    if norm > 0:
        truncated = truncated / norm
    # 处理 nan/inf
    truncated = np.nan_to_num(truncated, nan=0.0, posinf=1.0, neginf=-1.0)
    
    return truncated


def compute_embedding(text: str, instruction: Optional[str] = None, output_dimension: Optional[int] = None) -> np.ndarray:
    """
    计算单个文本的嵌入向量
    
    Args:
        text: 输入文本
        instruction: 可选的任务指令（仅用于 query，document 传 None）
        output_dimension: 可选的输出维度（MRL 支持，32-4096）
    
    Returns:
        归一化的嵌入向量
    """
    # 如果有任务指令，使用指令格式（仅用于 query）
    if instruction:
        text = get_detailed_instruct(instruction, text)
    
    # Tokenize
    inputs = tokenizer(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH  # 官方支持 32K
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
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    else:
        # 零向量情况，返回随机单位向量
        embedding = np.random.randn(embedding.shape[0]).astype(np.float32)
        embedding = embedding / np.linalg.norm(embedding)
    
    # 处理 nan/inf 值
    embedding = np.nan_to_num(embedding, nan=0.0, posinf=1.0, neginf=-1.0)
    
    # MRL: 截断到指定维度
    embedding = truncate_embedding(embedding, output_dimension)
    
    return embedding


def compute_embeddings_batch(texts: List[str], instruction: Optional[str] = None, output_dimension: Optional[int] = None) -> np.ndarray:
    """
    批量计算文本的嵌入向量
    
    Args:
        texts: 输入文本列表
        instruction: 可选的任务指令（仅用于 query，document 传 None）
        output_dimension: 可选的输出维度（MRL 支持，32-4096）
    
    Returns:
        归一化的嵌入向量矩阵 (N, dimension)
    """
    # 如果有任务指令，使用指令格式（仅用于 query）
    if instruction:
        texts = [get_detailed_instruct(instruction, t) for t in texts]
    
    # Tokenize
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=MAX_LENGTH  # 官方支持 32K
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
    # 避免除以零
    norms = np.where(norms == 0, 1, norms)
    embeddings = embeddings / norms
    
    # 处理 nan/inf 值
    embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=1.0, neginf=-1.0)
    
    # MRL: 截断到指定维度
    if output_dimension is not None and output_dimension < embeddings.shape[1]:
        if output_dimension < 32:
            output_dimension = 32
        embeddings = embeddings[:, :output_dimension]
        # 重新归一化
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        embeddings = embeddings / norms
        # 处理 nan/inf 值
        embeddings = np.nan_to_num(embeddings, nan=0.0, posinf=1.0, neginf=-1.0)
    
    return embeddings


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_embed_8b
    
    port = port_embed_8b()
    print(f"启动 Qwen3-Embedding-8B 服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

