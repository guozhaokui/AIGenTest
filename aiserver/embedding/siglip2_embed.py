"""
SigLIP-2 图片嵌入服务
用于计算图片的视觉嵌入向量
"""
import torch
from transformers import AutoModel, AutoProcessor
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
from PIL import Image
from io import BytesIO
import numpy as np
from typing import Optional
import base64
from pydantic import BaseModel

# Initialize FastAPI app
app = FastAPI(title="SigLIP-2 Image Embedding API")

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


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_siglip2
    
    port = port_siglip2()
    print(f"启动 SigLIP2 图片嵌入服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

