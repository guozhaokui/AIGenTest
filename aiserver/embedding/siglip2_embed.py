"""
SigLIP-2 图片和文本嵌入服务
用于计算图片的视觉嵌入向量和文本嵌入向量
支持跨模态搜索（文搜图、图搜图）
"""
import torch
from transformers import AutoModel, AutoProcessor
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
from PIL import Image
from io import BytesIO
import numpy as np
from typing import Optional, List
import base64
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI(title="SigLIP-2 Image & Text Embedding API")

# Model configuration
MODEL_PATH = "/mnt/hdd/models/siglip2-so400m-patch16-512"  # 1.14B 最强版本
MODEL_NAME = "siglip2-so400m-patch16-512"
MODEL_VERSION = "1.0"
DIMENSION = 1152  # SigLIP-2 so400m 输出维度

# Global model and processor
model = None
processor = None


def load_model():
    """加载 SigLIP-2 模型"""
    global model, processor
    print(f"Loading SigLIP-2 model from {MODEL_PATH}...")
    try:
        processor = AutoProcessor.from_pretrained(MODEL_PATH)
        model = AutoModel.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
        )
        model.to("cuda")
        model.eval()
        print("SigLIP-2 model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e


class ImageBase64Request(BaseModel):
    """Base64 编码的图片请求"""
    image_base64: str


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
        "capabilities": ["image_embedding", "text_embedding", "cross_modal_search"],
        "device": str(next(model.parameters()).device) if model else "not loaded"
    }


@app.post("/embed/image")
async def embed_image_upload(file: UploadFile = File(...)):
    """
    计算上传图片的嵌入向量
    
    Args:
        file: 上传的图片文件
    
    Returns:
        embedding: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        # 读取图片
        contents = await file.read()
        image = Image.open(BytesIO(contents)).convert("RGB")
        
        # 计算嵌入
        embedding = compute_image_embedding(image)
        
        return JSONResponse(content={
            "embedding": embedding.tolist(),
            "dimension": len(embedding),
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        })
    
    except Exception as e:
        print(f"Error embedding image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/embed/image/base64")
async def embed_image_base64(req: ImageBase64Request):
    """
    计算 Base64 编码图片的嵌入向量
    
    Args:
        image_base64: Base64 编码的图片数据
    
    Returns:
        embedding: 嵌入向量列表
        dimension: 向量维度
        model: 模型名称
    """
    try:
        # 解码 Base64
        image_data = base64.b64decode(req.image_base64)
        image = Image.open(BytesIO(image_data)).convert("RGB")
        
        # 计算嵌入
        embedding = compute_image_embedding(image)
        
        return JSONResponse(content={
            "embedding": embedding.tolist(),
            "dimension": len(embedding),
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        })
    
    except Exception as e:
        print(f"Error embedding image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def compute_image_embedding(image: Image.Image) -> np.ndarray:
    """
    计算图片嵌入向量
    
    Args:
        image: PIL Image 对象
    
    Returns:
        归一化的嵌入向量
    """
    # 预处理图片
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    
    # 计算嵌入
    with torch.no_grad():
        outputs = model.get_image_features(**inputs)
    
    # 归一化 (先转 float32 再转 numpy，避免 bfloat16 不支持的问题)
    embedding = outputs[0].float().cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def compute_text_embedding(text: str) -> np.ndarray:
    """
    计算文本嵌入向量
    
    Args:
        text: 输入文本
    
    Returns:
        归一化的嵌入向量
    """
    # 预处理文本
    inputs = processor(text=text, return_tensors="pt", padding=True, truncation=True, max_length=64)
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    
    # 计算嵌入
    with torch.no_grad():
        outputs = model.get_text_features(**inputs)
    
    # 归一化
    embedding = outputs[0].float().cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)
    
    return embedding


def compute_text_embeddings_batch(texts: List[str]) -> np.ndarray:
    """
    批量计算文本嵌入向量
    
    Args:
        texts: 输入文本列表
    
    Returns:
        归一化的嵌入向量矩阵 (N, dimension)
    """
    # 预处理文本
    inputs = processor(text=texts, return_tensors="pt", padding=True, truncation=True, max_length=64)
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    
    # 计算嵌入
    with torch.no_grad():
        outputs = model.get_text_features(**inputs)
    
    # 归一化
    embeddings = outputs.float().cpu().numpy()
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / norms
    
    return embeddings


# ==================== 文本嵌入 API ====================

@app.post("/embed/text")
async def embed_text(req: TextRequest):
    """
    计算单个文本的嵌入向量
    
    SigLIP2 的文本嵌入与图片嵌入在同一向量空间，
    可用于文字搜索图片（跨模态检索）
    
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
            "count": len(req.texts),
            "model": MODEL_NAME,
            "version": MODEL_VERSION
        })
    
    except Exception as e:
        print(f"Error embedding texts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_siglip2
    
    port = port_siglip2()
    print(f"启动 SigLIP2 图片嵌入服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

