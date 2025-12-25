"""
AI 服务轻量网关
纯 Python 实现，在客户端电脑上运行
根据服务类型转发到不同的 GPU 服务器

配置来源：aiserver/config.yaml
"""
import sys
from pathlib import Path

# 添加 aiserver 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# 从统一配置模块加载
from config import (
    get_config, get_default, get_gateway_port,
    url_siglip2, url_embed_4b, url_embed_bge, url_rerank_4b,
    url_embed_8b, url_rerank_8b, url_vlm, url_zimage, url_trellis
)

app = FastAPI(title="AI Gateway", description="AI 服务统一网关")

# =============================================================================
# 从 config.yaml 加载配置
# =============================================================================

SERVICES = {
    "embed_image":    url_siglip2(),
    "embed_text_4b":  url_embed_4b(),
    "embed_text_bge": url_embed_bge(),
    "rerank_4b":      url_rerank_4b(),
    "embed_text_8b":  url_embed_8b(),
    "rerank_8b":      url_rerank_8b(),
    "vlm":            url_vlm(),
    "zimage":         url_zimage(),
    "trellis":        url_trellis(),
}

# 默认服务
DEFAULT_EMBED_TEXT = f"embed_text_{get_default('text_embedding').replace('embed_', '')}"
DEFAULT_RERANK = get_default('rerank')

# 超时设置（秒）
TIMEOUT = httpx.Timeout(300.0, connect=10.0)

# =============================================================================
# 请求模型
# =============================================================================

class TextRequest(BaseModel):
    text: str
    instruction: Optional[str] = None

class TextsRequest(BaseModel):
    texts: List[str]
    instruction: Optional[str] = None

class RerankRequest(BaseModel):
    query: str
    documents: List[str]
    top_k: Optional[int] = None

class ImageBase64Request(BaseModel):
    image_base64: str

class GenerateImageRequest(BaseModel):
    prompt: str
    height: int = 1024
    width: int = 1024
    num_inference_steps: int = 9
    guidance_scale: float = 0.0
    seed: int = 42

# =============================================================================
# 健康检查
# =============================================================================

@app.get("/health")
async def health():
    """网关健康检查"""
    config = get_config()
    return {
        "status": "ok", 
        "gateway": "python-fastapi",
        "config": "aiserver/config.yaml"
    }

@app.get("/health/all")
async def health_all():
    """检查所有服务状态"""
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in SERVICES.items():
            try:
                resp = await client.get(f"{url}/health")
                if resp.status_code == 200:
                    results[name] = {"status": "ok", "url": url}
                else:
                    results[name] = {"status": "error", "code": resp.status_code}
            except Exception as e:
                results[name] = {"status": "offline", "error": str(e)[:50]}
    return results

@app.get("/services")
async def list_services():
    """列出所有服务"""
    return {
        "services": SERVICES,
        "defaults": {
            "text_embedding": DEFAULT_EMBED_TEXT,
            "rerank": DEFAULT_RERANK
        }
    }

# =============================================================================
# 嵌入服务 - 图片
# =============================================================================

@app.post("/embed/image")
async def embed_image(file: UploadFile = File(...)):
    """图片嵌入（上传文件）"""
    url = f"{SERVICES['embed_image']}/embed/image"
    content = await file.read()
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        files = {"file": (file.filename, content, file.content_type)}
        resp = await client.post(url, files=files)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

@app.post("/embed/image/base64")
async def embed_image_base64(req: ImageBase64Request):
    """图片嵌入（Base64）"""
    url = f"{SERVICES['embed_image']}/embed/image/base64"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=req.dict())
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# =============================================================================
# 嵌入服务 - 文本
# =============================================================================

@app.post("/embed/text")
async def embed_text(req: TextRequest):
    """文本嵌入（使用默认模型）"""
    return await _forward_embed_text(req, DEFAULT_EMBED_TEXT)

@app.post("/embed/text/qwen3-8b")
async def embed_text_8b(req: TextRequest):
    """文本嵌入 - Qwen3-Embedding-8B"""
    return await _forward_embed_text(req, "embed_text_8b")

@app.post("/embed/text/qwen3-4b")
async def embed_text_4b(req: TextRequest):
    """文本嵌入 - Qwen3-4B"""
    return await _forward_embed_text(req, "embed_text_4b")

@app.post("/embed/text/bge")
async def embed_text_bge(req: TextRequest):
    """文本嵌入 - BGE"""
    return await _forward_embed_text(req, "embed_text_bge")

async def _forward_embed_text(req: TextRequest, service: str):
    """转发文本嵌入请求"""
    url = f"{SERVICES[service]}/embed/text"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=req.dict())
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

@app.post("/embed/texts")
async def embed_texts(req: TextsRequest):
    """批量文本嵌入（使用默认模型）"""
    return await _forward_embed_texts(req, DEFAULT_EMBED_TEXT)

async def _forward_embed_texts(req: TextsRequest, service: str):
    """转发批量文本嵌入请求"""
    url = f"{SERVICES[service]}/embed/texts"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=req.dict())
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# =============================================================================
# 重排序服务
# =============================================================================

@app.post("/rerank")
async def rerank(req: RerankRequest):
    """重排序（使用默认模型）"""
    return await _forward_rerank(req, DEFAULT_RERANK)

@app.post("/rerank/qwen3-8b")
async def rerank_8b(req: RerankRequest):
    """重排序 - Qwen3-Reranker-8B"""
    return await _forward_rerank(req, "rerank_8b")

@app.post("/rerank/qwen3-4b")
async def rerank_4b(req: RerankRequest):
    """重排序 - Qwen3-4B"""
    return await _forward_rerank(req, "rerank_4b")

async def _forward_rerank(req: RerankRequest, service: str):
    """转发重排序请求"""
    url = f"{SERVICES[service]}/rerank"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=req.dict())
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# =============================================================================
# VLM 服务
# =============================================================================

@app.post("/vlm/caption")
async def vlm_caption(file: UploadFile = File(...), prompt: Optional[str] = Form(None)):
    """VLM 图片描述"""
    url = f"{SERVICES['vlm']}/caption"
    content = await file.read()
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        files = {"file": (file.filename, content, file.content_type)}
        data = {"prompt": prompt} if prompt else {}
        resp = await client.post(url, files=files, data=data)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

@app.post("/vlm/chat")
async def vlm_chat(request: Dict[str, Any]):
    """VLM 聊天接口"""
    url = f"{SERVICES['vlm']}/v1/chat/completions"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=request)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# =============================================================================
# 图片生成服务
# =============================================================================

@app.post("/generate/image")
async def generate_image(req: GenerateImageRequest):
    """Z-Image 图片生成"""
    url = f"{SERVICES['zimage']}/generate"
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(url, json=req.dict())
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.content

# =============================================================================
# 3D 生成服务
# =============================================================================

@app.post("/generate/3d")
async def generate_3d(file: UploadFile = File(...)):
    """Trellis 3D 模型生成"""
    url = f"{SERVICES['trellis']}/generate"
    content = await file.read()
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        files = {"image": (file.filename, content, file.content_type)}
        resp = await client.post(url, files=files)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()

# =============================================================================
# 启动
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = get_gateway_port()
    
    print(f"""
╔════════════════════════════════════════════════════════════════════╗
║                        AI 服务网关                                  ║
╠════════════════════════════════════════════════════════════════════╣
║  配置文件: aiserver/config.yaml                                    ║
║  网关地址: http://localhost:{port}                                  ║
╠════════════════════════════════════════════════════════════════════╣
║  后端服务:                                                         ║""")
    for name, url in SERVICES.items():
        print(f"║    {name:15} → {url:30}   ║")
    print(f"""╠════════════════════════════════════════════════════════════════════╣
║  默认: 嵌入={DEFAULT_EMBED_TEXT}, 重排序={DEFAULT_RERANK}          ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)
