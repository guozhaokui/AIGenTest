"""
BGE 文本嵌入服务
使用 BAAI/bge-large-zh-v1.5 模型
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
app = FastAPI(title="BGE Text Embedding API")

# Model configuration
MODEL_PATH = "/mnt/hdd/models/bge-large-zh"
MODEL_NAME = "bge-large-zh"
MODEL_VERSION = "1.0"
DIMENSION = 1024  # BGE-Large 输出维度

# Global model and tokenizer
model = None
tokenizer = None


def load_model():
    """加载 BGE 模型"""
    global model, tokenizer
    print(f"Loading BGE model from {MODEL_PATH}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        model = AutoModel.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.float16,
        )
        model.to("cuda")
        model.eval()
        print("BGE model loaded successfully.")
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
    """启动时加载模型"""
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
def embed_text(req: TextRequest):
    """
    单个文本嵌入
    
    BGE 推荐对查询文本添加前缀 "为这个句子生成表示以用于检索相关文章："
    但为了通用性，这里不添加前缀，由调用方决定
    """
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        embedding = compute_embeddings([req.text])[0]
        return {
            "embedding": embedding.tolist(),
            "dimension": DIMENSION,
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/texts")
def embed_texts(req: TextsRequest):
    """批量文本嵌入"""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    if len(req.texts) == 0:
        raise HTTPException(status_code=400, detail="Empty texts list")
    
    if len(req.texts) > 32:
        raise HTTPException(status_code=400, detail="Maximum 32 texts per request")
    
    try:
        embeddings = compute_embeddings(req.texts)
        return {
            "embeddings": embeddings.tolist(),
            "dimension": DIMENSION,
            "model": MODEL_NAME,
            "version": MODEL_VERSION,
            "count": len(req.texts)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def compute_embeddings(texts: List[str]) -> np.ndarray:
    """
    计算文本嵌入
    
    使用 mean pooling，与 BGE 官方一致
    """
    # Tokenize
    encoded_input = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt"
    )
    
    # Move to GPU
    encoded_input = {k: v.to("cuda") for k, v in encoded_input.items()}
    
    # Compute embeddings
    with torch.no_grad():
        outputs = model(**encoded_input)
        # BGE 使用 [CLS] token 的输出，或者 mean pooling
        # 官方推荐使用 [CLS]
        embeddings = outputs.last_hidden_state[:, 0]
    
    # Normalize
    embeddings = embeddings.float().cpu().numpy()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    return embeddings


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_embed_bge
    
    port = port_embed_bge()
    print(f"启动 BGE 文本嵌入服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

