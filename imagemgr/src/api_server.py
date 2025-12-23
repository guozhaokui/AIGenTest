"""
图片管理 API 服务
提供图片上传、查询、搜索等功能
"""
import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Form
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from database import Database
from storage import StorageManager
from vector_index import VectorIndexManager, VectorIndex
from embedding_client import EmbeddingClient


# 配置
BASE_DIR = Path(__file__).parent.parent
STORAGE_DIR = BASE_DIR / "storage"
VECTOR_INDEX_DIR = BASE_DIR / "vector_index"
DB_PATH = BASE_DIR / "data" / "imagemgr.db"
CONFIG_PATH = BASE_DIR / "config" / "embedding_services.yaml"

# 索引配置 - 图片
IMAGE_INDEX_NAME = "siglip2_image_v1"
IMAGE_INDEX_DIMENSION = 1152
IMAGE_MODEL_NAME = "siglip2-so400m-patch16-512"
IMAGE_MODEL_VERSION = "1.0"

# 索引配置 - 文本（多模型）
TEXT_INDEXES = {
    "qwen3_text_v1": {
        "dimension": 2560,
        "model_name": "Qwen3-4B",
        "model_version": "1.0",
        "service_name": "qwen3_embed_local"
    },
    "bge_text_v1": {
        "dimension": 1024,
        "model_name": "bge-large-zh",
        "model_version": "1.0",
        "service_name": "bge_local"
    }
}

# 初始化组件
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
db = Database(str(DB_PATH))
storage = StorageManager(str(STORAGE_DIR))
vector_manager = VectorIndexManager(str(VECTOR_INDEX_DIR))
embedding_client = EmbeddingClient(str(CONFIG_PATH) if CONFIG_PATH.exists() else None)

# 获取或创建索引 - 图片
image_index = vector_manager.get_or_create_index(
    IMAGE_INDEX_NAME, IMAGE_INDEX_DIMENSION, IMAGE_MODEL_NAME, IMAGE_MODEL_VERSION
)

# 获取或创建索引 - 文本（多个）
text_indexes = {}
for index_name, config in TEXT_INDEXES.items():
    text_indexes[index_name] = vector_manager.get_or_create_index(
        index_name, config["dimension"], config["model_name"], config["model_version"]
    )

# 兼容旧代码：默认文本索引（BGE 效果更好）
text_index = text_indexes.get("bge_text_v1")

# FastAPI 应用
app = FastAPI(
    title="图片管理服务",
    description="图片上传、查询、向量搜索 API",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 请求/响应模型 ====================

class TextSearchRequest(BaseModel):
    """文本搜索请求"""
    query: str
    top_k: int = 100  # 默认返回100条结果
    index: Optional[str] = None  # 指定使用的索引，默认搜索所有索引
    rerank: bool = False  # 是否使用重排序


class ImageSearchRequest(BaseModel):
    """以图搜图请求（Base64）"""
    image_base64: str
    top_k: int = 100  # 默认返回100条结果


class AddDescriptionRequest(BaseModel):
    """添加描述请求"""
    method: str
    content: str


class SearchResult(BaseModel):
    """搜索结果"""
    sha256: str
    score: float
    matched_by: str


# ==================== API 端点 ====================

@app.get("/health")
def health_check():
    """健康检查"""
    image_service_ok = embedding_client.check_image_service()
    
    # 检查所有文本嵌入服务
    text_services_status = {}
    for service in embedding_client.get_all_text_services():
        svc_name = service["service_name"]
        endpoint = service.get("endpoint", "")
        try:
            import requests
            resp = requests.get(f"{endpoint}/health", timeout=(2, 3))
            text_services_status[svc_name] = "ok" if resp.status_code == 200 else "unavailable"
        except:
            text_services_status[svc_name] = "unavailable"
    
    # 统计各索引数量
    text_index_counts = {name: idx.count() for name, idx in text_indexes.items()}
    
    return {
        "status": "ok",
        "database": "ok",
        "image_embedding_service": "ok" if image_service_ok else "unavailable",
        "text_embedding_services": text_services_status,
        "image_count": db.count_images(),
        "image_index_count": image_index.count(),
        "text_index_counts": text_index_counts
    }


@app.get("/api/indexes")
def list_indexes():
    """获取可用的索引列表"""
    return {
        "image_indexes": [
            {
                "name": IMAGE_INDEX_NAME,
                "model": IMAGE_MODEL_NAME,
                "dimension": IMAGE_INDEX_DIMENSION,
                "count": image_index.count()
            }
        ],
        "text_indexes": [
            {
                "name": name,
                "model": config["model_name"],
                "dimension": config["dimension"],
                "service": config["service_name"],
                "count": text_indexes[name].count()
            }
            for name, config in TEXT_INDEXES.items()
        ]
    }


@app.get("/api/search/text-indexes")
def get_text_indexes():
    """
    获取可用的文本搜索索引列表
    
    用于前端选择使用哪个嵌入模型进行文本搜索
    """
    indexes = []
    for name, config in TEXT_INDEXES.items():
        indexes.append({
            "id": name,
            "name": config["model_name"],
            "description": f"{config['model_name']} ({config['dimension']}维)",
            "dimension": config["dimension"],
            "service": config["service_name"]
        })
    
    return {
        "indexes": indexes,
        "default": "qwen3_text_v1"  # 默认使用 Qwen3
    }


@app.post("/api/images")
async def upload_image(
    file: UploadFile = File(...),
    source: str = Form(None)
):
    """
    上传图片
    
    - 计算 SHA256
    - 检查是否已存在
    - 保存图片和缩略图
    - 计算图片嵌入并加入索引
    """
    try:
        # 读取文件
        content = await file.read()
        sha256 = storage.compute_sha256_from_bytes(content)
        
        # 检查是否已存在
        if db.image_exists(sha256):
            return JSONResponse(
                status_code=200,
                content={
                    "message": "图片已存在",
                    "sha256": sha256,
                    "exists": True
                }
            )
        
        # 保存图片
        image_path, meta = storage.save_image_from_bytes(content, sha256)
        
        # 添加数据库记录
        db.add_image(
            sha256=sha256,
            width=meta["width"],
            height=meta["height"],
            file_size=meta["file_size"],
            format=meta["format"],
            source=source
        )
        
        # 计算图片嵌入
        embedding = embedding_client.get_image_embedding(image_path=str(image_path))
        
        if embedding is not None:
            # 保存嵌入到文件
            storage.save_embedding(sha256, "image", embedding)
            
            # 添加到向量索引
            entry_id = image_index.add(embedding, sha256, "image")
            
            # 记录到数据库
            db.add_vector_entry(
                sha256, "image", IMAGE_MODEL_NAME, IMAGE_MODEL_VERSION, IMAGE_INDEX_NAME
            )
            
            # 更新状态为 ready
            db.update_image_status(sha256, "ready")
        else:
            # 嵌入服务不可用，标记为 pending
            db.update_image_status(sha256, "pending")
        
        return {
            "message": "上传成功",
            "sha256": sha256,
            "width": meta["width"],
            "height": meta["height"],
            "file_size": meta["file_size"],
            "format": meta["format"],
            "status": db.get_image(sha256)["status"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/images/{sha256}")
def get_image_info(sha256: str):
    """获取图片信息"""
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 获取描述
    descriptions = db.get_descriptions(sha256)
    
    return {
        **image,
        "descriptions": descriptions
    }


@app.get("/api/images/{sha256}/file")
def get_image_file(sha256: str):
    """获取原始图片文件"""
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    image_bytes = storage.get_image_bytes(sha256)
    if not image_bytes:
        raise HTTPException(status_code=404, detail="图片文件不存在")
    
    # 根据格式确定 MIME 类型
    format_lower = image["format"].lower()
    mime_type = f"image/{format_lower}"
    if format_lower == "jpg":
        mime_type = "image/jpeg"
    
    return Response(content=image_bytes, media_type=mime_type)


@app.get("/api/images/{sha256}/thumbnail")
def get_thumbnail(sha256: str):
    """获取缩略图"""
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    thumbnail_bytes = storage.get_thumbnail_bytes(sha256)
    if not thumbnail_bytes:
        raise HTTPException(status_code=404, detail="缩略图不存在")
    
    return Response(content=thumbnail_bytes, media_type="image/jpeg")


@app.delete("/api/images/{sha256}")
def delete_image(sha256: str, hard: bool = False):
    """删除图片"""
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 从向量索引移除
    image_index.remove(sha256)
    text_index.remove(sha256)
    
    # 从数据库删除
    db.delete_image(sha256, hard=hard)
    
    # 硬删除时删除文件
    if hard:
        storage.delete_image_dir(sha256)
    
    return {"message": "删除成功", "sha256": sha256, "hard": hard}


@app.get("/api/images")
def list_images(
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source: str = None,
    status: str = None
):
    """列出图片"""
    images = db.list_images(offset=offset, limit=limit, source=source, status=status)
    total = db.count_images(source=source, status=status)
    
    return {
        "images": images,
        "total": total,
        "offset": offset,
        "limit": limit
    }


# ==================== 描述管理 ====================

@app.post("/api/images/{sha256}/descriptions")
def add_description(sha256: str, req: AddDescriptionRequest):
    """添加图片描述，使用所有启用的文本嵌入模型"""
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 保存描述
    storage.save_description(sha256, req.method, req.content)
    db.add_description(sha256, req.method, req.content)
    
    # 使用所有文本嵌入服务计算嵌入
    all_embeddings = embedding_client.get_all_text_embeddings(req.content)
    
    embedding_results = []
    for service_name, emb_info in all_embeddings.items():
        embedding = emb_info["embedding"]
        model_name = emb_info["model_name"]
        model_version = emb_info["model_version"]
        
        # 查找对应的索引
        index_name = None
        for idx_name, idx_config in TEXT_INDEXES.items():
            if idx_config["service_name"] == service_name:
                index_name = idx_name
                break
        
        if index_name and index_name in text_indexes:
            # 保存嵌入（带模型后缀区分）
            emb_filename = f"{req.method}_{model_name.replace('-', '_')}"
            storage.save_embedding(sha256, emb_filename, embedding)
            
            # 添加到对应的向量索引
            text_indexes[index_name].add(embedding, sha256, req.method)
            
            # 记录到数据库
            db.add_vector_entry(sha256, req.method, model_name, model_version, index_name)
            
            embedding_results.append({
                "model": model_name,
                "index": index_name,
                "dimension": len(embedding)
            })
    
    # 更新描述嵌入状态
    if embedding_results:
        db.update_description_embedding(sha256, req.method, True)
    
    return {
        "message": "描述添加成功",
        "sha256": sha256,
        "method": req.method,
        "embeddings": embedding_results,
        "embedding_count": len(embedding_results)
    }


@app.get("/api/images/{sha256}/descriptions")
def get_descriptions(sha256: str):
    """获取图片的所有描述"""
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    descriptions = db.get_descriptions(sha256)
    
    # 读取描述内容
    result = []
    for desc in descriptions:
        content = storage.get_description(sha256, desc["method"])
        result.append({
            **desc,
            "content": content
        })
    
    return {"descriptions": result}


class VlmGenerateRequest(BaseModel):
    """VLM 生成描述请求（通用）"""
    sha256: Optional[str] = None  # 库中图片的 sha256（与 image_base64 二选一）
    image_base64: Optional[str] = None  # Base64 编码的图片（与 sha256 二选一）
    vlm_service: Optional[str] = None  # VLM 服务名称，不指定则使用默认
    prompt: Optional[str] = None  # 提示词（预设名称或自定义文本）


class SaveDescriptionRequest(BaseModel):
    """保存描述请求"""
    method: str  # 描述类型，如 "vlm", "manual" 等
    content: str  # 描述内容
    compute_embedding: bool = True  # 是否计算文本嵌入


@app.post("/api/vlm/generate")
def vlm_generate_caption(req: VlmGenerateRequest):
    """
    通用 VLM 描述生成接口
    
    支持两种输入方式：
    1. sha256: 指定库中已有图片的 sha256
    2. image_base64: 直接传入 base64 编码的图片
    
    返回生成的描述文本，不保存到数据库
    """
    import base64
    import tempfile
    import os
    
    temp_file = None
    
    try:
        # 确定图片来源
        if req.sha256:
            # 从库中获取图片
            image = db.get_image(req.sha256)
            if not image:
                raise HTTPException(status_code=404, detail="图片不存在")
            
            image_path = storage.get_image_path(req.sha256)
            if not image_path.exists():
                raise HTTPException(status_code=400, detail="图片文件不存在")
            
            image_path_str = str(image_path)
            
        elif req.image_base64:
            # 从 base64 解码并保存为临时文件
            try:
                # 去除可能的 data URL 前缀
                base64_data = req.image_base64
                if ',' in base64_data:
                    base64_data = base64_data.split(',', 1)[1]
                
                image_data = base64.b64decode(base64_data)
                
                # 创建临时文件
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
                temp_file.write(image_data)
                temp_file.close()
                
                image_path_str = temp_file.name
                
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Base64 解码失败: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail="必须提供 sha256 或 image_base64")
        
        # 调用 VLM 生成描述
        caption = generate_caption_with_vlm(
            image_path_str,
            prompt_name=req.prompt,
            vlm_service=req.vlm_service
        )
        
        if not caption:
            raise HTTPException(status_code=500, detail="VLM 服务调用失败或返回空结果")
        
        return {
            "caption": caption,
            "sha256": req.sha256,  # 如果是库中图片，返回 sha256
            "vlm_service": req.vlm_service or VLM_CONFIG.get("default_service", "default")
        }
        
    finally:
        # 清理临时文件
        if temp_file and os.path.exists(temp_file.name):
            os.unlink(temp_file.name)


@app.post("/api/images/{sha256}/descriptions/save")
def save_description_with_embedding(sha256: str, req: SaveDescriptionRequest):
    """
    保存描述并可选计算文本嵌入
    
    用于保存 VLM 生成的描述或手动输入的描述
    如果 compute_embedding=True，会同时计算文本嵌入
    """
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 保存描述
    storage.save_description(sha256, req.method, req.content)
    db.add_description(sha256, req.method, req.content)
    
    embedding_results = []
    
    # 可选：计算文本嵌入
    if req.compute_embedding:
        all_embeddings = embedding_client.get_all_text_embeddings(req.content)
        
        for service_name, emb_info in all_embeddings.items():
            emb = emb_info["embedding"]
            model_name = emb_info["model_name"]
            model_version = emb_info["model_version"]
            
            index_name = None
            for idx_name, idx_config in TEXT_INDEXES.items():
                if idx_config["service_name"] == service_name:
                    index_name = idx_name
                    break
            
            if index_name and index_name in text_indexes:
                emb_filename = f"{req.method}_{model_name.replace('-', '_')}"
                storage.save_embedding(sha256, emb_filename, emb)
                text_indexes[index_name].add(emb, sha256, req.method)
                
                try:
                    db.add_vector_entry(sha256, req.method, model_name, model_version, index_name)
                except:
                    pass
                
                embedding_results.append({
                    "model": model_name,
                    "index": index_name
                })
        
        if embedding_results:
            db.update_description_embedding(sha256, req.method, True)
    
    return {
        "message": "描述保存成功",
        "sha256": sha256,
        "method": req.method,
        "content": req.content,
        "embeddings": embedding_results
    }


# ==================== 重新计算嵌入 ====================

@app.post("/api/images/{sha256}/recompute-embedding")
def recompute_embedding(sha256: str, include_text: bool = False):
    """
    重新计算图片的嵌入向量
    
    - 重新计算图片嵌入并更新向量索引
    - 如果 include_text=True，同时重新计算所有描述的文本嵌入
    """
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    results = {
        "sha256": sha256,
        "image_embedding": None,
        "text_embeddings": []
    }
    
    # 删除旧的向量数据库记录（避免唯一约束冲突）
    db.delete_vector_entries(sha256)
    
    # 1. 重新计算图片嵌入
    image_path = storage.get_image_path(sha256)
    if image_path and image_path.exists():
        # 从向量索引移除旧的
        image_index.remove(sha256)
        
        # 计算新嵌入
        embedding = embedding_client.get_image_embedding(image_path=str(image_path))
        
        if embedding is not None:
            # 保存嵌入到文件
            storage.save_embedding(sha256, "image", embedding)
            
            # 添加到向量索引
            image_index.add(embedding, sha256, "image")
            
            # 更新数据库记录
            db.add_vector_entry(
                sha256, "image", IMAGE_MODEL_NAME, IMAGE_MODEL_VERSION, IMAGE_INDEX_NAME
            )
            
            # 更新状态为 ready
            db.update_image_status(sha256, "ready")
            
            results["image_embedding"] = {
                "status": "success",
                "model": IMAGE_MODEL_NAME,
                "dimension": len(embedding)
            }
        else:
            db.update_image_status(sha256, "pending")
            results["image_embedding"] = {
                "status": "failed",
                "error": "图片嵌入服务不可用"
            }
    else:
        results["image_embedding"] = {
            "status": "failed",
            "error": "图片文件不存在"
        }
    
    # 2. 可选：重新计算文本嵌入
    if include_text:
        descriptions = db.get_descriptions(sha256)
        
        for desc in descriptions:
            method = desc["method"]
            content = storage.get_description(sha256, method)
            
            if not content:
                results["text_embeddings"].append({
                    "method": method,
                    "status": "skipped",
                    "error": "描述内容为空"
                })
                continue
            
            # 从所有文本索引移除旧的
            for index_name, idx in text_indexes.items():
                idx.remove(sha256)
            
            # 使用所有文本嵌入服务计算嵌入
            all_embeddings = embedding_client.get_all_text_embeddings(content)
            
            method_results = []
            for service_name, emb_info in all_embeddings.items():
                emb = emb_info["embedding"]
                model_name = emb_info["model_name"]
                model_version = emb_info["model_version"]
                
                # 查找对应的索引
                index_name = None
                for idx_name, idx_config in TEXT_INDEXES.items():
                    if idx_config["service_name"] == service_name:
                        index_name = idx_name
                        break
                
                if index_name and index_name in text_indexes:
                    # 保存嵌入
                    emb_filename = f"{method}_{model_name.replace('-', '_')}"
                    storage.save_embedding(sha256, emb_filename, emb)
                    
                    # 添加到向量索引
                    text_indexes[index_name].add(emb, sha256, method)
                    
                    # 记录到数据库
                    db.add_vector_entry(sha256, method, model_name, model_version, index_name)
                    
                    method_results.append({
                        "model": model_name,
                        "index": index_name,
                        "dimension": len(emb)
                    })
            
            if method_results:
                db.update_description_embedding(sha256, method, True)
                results["text_embeddings"].append({
                    "method": method,
                    "status": "success",
                    "embeddings": method_results
                })
            else:
                results["text_embeddings"].append({
                    "method": method,
                    "status": "failed",
                    "error": "所有文本嵌入服务都不可用"
                })
    
    return results


# ==================== 搜索 ====================

@app.post("/api/search/text")
def search_by_text(req: TextSearchRequest):
    """
    文本搜索
    
    - 使用文本嵌入模型计算查询向量
    - 在文本索引中搜索
    - 按 sha256 去重返回结果
    
    Args:
        query: 搜索文本
        top_k: 返回结果数量
        index: 指定索引 (qwen3_text_v1 / bge_text_v1)，不指定则使用所有索引
    """
    # 如果指定了索引，验证是否存在
    if req.index and req.index not in text_indexes:
        raise HTTPException(
            status_code=400, 
            detail=f"索引 {req.index} 不存在，可选: {list(text_indexes.keys())}"
        )
    
    # 确定要搜索的索引列表
    if req.index:
        # 指定了索引，只搜索该索引
        indexes_to_search = {req.index: TEXT_INDEXES[req.index]}
    else:
        # 未指定索引，搜索所有索引
        indexes_to_search = TEXT_INDEXES
    
    # 收集所有索引的搜索结果
    all_results = []
    used_models = []
    
    for index_name, index_config in indexes_to_search.items():
        service_name = index_config.get("service_name")
        model_name = index_config.get("model_name")
        
        # 使用对应服务获取文本嵌入
        query_embedding = embedding_client.get_text_embedding_by_service(req.query, service_name)
        if query_embedding is None:
            print(f"警告: 文本嵌入服务 {service_name} 不可用，跳过索引 {index_name}")
            continue
        
        # 在对应索引中搜索
        search_index = text_indexes[index_name]
        results = search_index.search_deduplicated(query_embedding, req.top_k)
        
        # 为每个结果添加索引和模型信息
        for r in results:
            r["index"] = index_name
            r["model"] = model_name
            all_results.append(r)
        
        used_models.append({
            "index": index_name,
            "model": model_name,
            "result_count": len(results)
        })
    
    if not all_results:
        raise HTTPException(status_code=503, detail="所有文本嵌入服务都不可用")
    
    # 按分数排序，去重（同一图片保留最高分）
    seen_sha256 = {}
    for r in sorted(all_results, key=lambda x: x["score"], reverse=True):
        sha256 = r["sha256"]
        if sha256 not in seen_sha256:
            seen_sha256[sha256] = r
        else:
            # 如果同一图片在另一个索引中分数更高，更新
            if r["score"] > seen_sha256[sha256]["score"]:
                seen_sha256[sha256] = r
    
    # 取 top_k 个结果
    deduplicated = list(seen_sha256.values())[:req.top_k]
    
    # 补充图片信息和获取描述文本
    enriched_results = []
    for r in deduplicated:
        image = db.get_image(r["sha256"])
        if image:
            # 获取匹配的描述内容
            matched_text = storage.get_description(r["sha256"], r["matched_by"])
            enriched_results.append({
                **r,
                "matched_text": matched_text or "",
                "width": image["width"],
                "height": image["height"]
            })
    
    # 如果启用重排序，使用 LLM 精排
    reranked = False
    print(f"[Rerank] 请求参数 req.rerank={req.rerank}, 结果数量={len(enriched_results)}")
    if req.rerank and enriched_results:
        # 提取描述文本用于重排序
        documents = [r.get("matched_text", "") for r in enriched_results]
        print(f"[Rerank] 调用重排序服务, query={req.query[:50]}..., documents数量={len(documents)}")
        rerank_results = embedding_client.rerank(req.query, documents, req.top_k)
        
        print(f"[Rerank] 重排序返回: {rerank_results is not None}, 结果数量={len(rerank_results) if rerank_results else 0}")
        if rerank_results:
            # 根据重排序结果重新排列
            reranked_enriched = []
            for rr in rerank_results:
                original_idx = rr["original_index"]
                if original_idx < len(enriched_results):
                    result = enriched_results[original_idx].copy()
                    result["rerank_score"] = rr["score"]
                    result["vector_score"] = result.pop("score")  # 保留原向量分数
                    reranked_enriched.append(result)
            enriched_results = reranked_enriched
            reranked = True
            print(f"[Rerank] 重排序完成, 最终结果数量={len(enriched_results)}")
        else:
            print("[Rerank] 重排序服务返回空结果")
    
    return {
        "query": req.query, 
        "indexes_searched": used_models,
        "reranked": reranked,
        "results": enriched_results
    }


@app.post("/api/search/image")
async def search_by_image(file: UploadFile = File(...), top_k: int = Form(10)):
    """
    以图搜图
    
    - 使用图片嵌入模型计算查询向量
    - 在图片索引中搜索
    """
    try:
        # 读取图片
        content = await file.read()
        
        # 获取图片嵌入
        query_embedding = embedding_client.get_image_embedding(image_bytes=content)
        if query_embedding is None:
            raise HTTPException(status_code=503, detail="图片嵌入服务不可用")
        
        # 搜索
        results = image_index.search_deduplicated(query_embedding, top_k)
        
        # 补充图片信息
        enriched_results = []
        for r in results:
            image = db.get_image(r["sha256"])
            if image:
                enriched_results.append({
                    **r,
                    "width": image["width"],
                    "height": image["height"]
                })
        
        return {"results": enriched_results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/search/image/base64")
def search_by_image_base64(req: ImageSearchRequest):
    """以图搜图（Base64 方式）"""
    import base64
    
    try:
        # 解码图片
        image_bytes = base64.b64decode(req.image_base64)
        
        # 获取图片嵌入
        query_embedding = embedding_client.get_image_embedding(image_bytes=image_bytes)
        if query_embedding is None:
            raise HTTPException(status_code=503, detail="图片嵌入服务不可用")
        
        # 搜索
        results = image_index.search_deduplicated(query_embedding, req.top_k)
        
        # 补充图片信息
        enriched_results = []
        for r in results:
            image = db.get_image(r["sha256"])
            if image:
                enriched_results.append({
                    **r,
                    "width": image["width"],
                    "height": image["height"]
                })
        
        return {"results": enriched_results}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search/similar/{sha256}")
def search_similar_images(sha256: str, top_k: int = 100):
    """
    通过已有图片的 sha256 搜索相似图片
    
    - 读取图片的已保存嵌入向量
    - 在图片索引中搜索相似图片
    - 排除自身
    """
    # 检查图片是否存在
    image = db.get_image(sha256)
    if not image:
        raise HTTPException(status_code=404, detail=f"图片不存在: {sha256}")
    
    # 读取已保存的嵌入向量
    embedding = storage.get_embedding(sha256, "image")
    if embedding is None:
        raise HTTPException(status_code=400, detail="图片嵌入向量不存在，请先计算嵌入")
    
    # 搜索相似图片（多取一个，因为可能包含自身）
    results = image_index.search_deduplicated(embedding, top_k + 1)
    
    # 过滤掉自身并补充图片信息
    enriched_results = []
    for r in results:
        if r["sha256"] == sha256:
            continue  # 跳过自身
        
        img = db.get_image(r["sha256"])
        if img:
            enriched_results.append({
                **r,
                "width": img["width"],
                "height": img["height"],
                "matched_by": "image"
            })
        
        if len(enriched_results) >= top_k:
            break
    
    return {
        "source_sha256": sha256,
        "results": enriched_results,
        "total": len(enriched_results)
    }


# ==================== VLM 配置 ====================

@app.get("/api/vlm/config")
def get_vlm_config():
    """获取 VLM 服务配置"""
    return {
        "services": [
            {
                "id": name,
                "name": svc.get("name", name),
                "description": svc.get("description", ""),
                "is_enabled": svc.get("is_enabled", True)
            }
            for name, svc in VLM_SERVICES.items()
        ],
        "default_service": VLM_CONFIG.get("default_service", "default"),
        "prompts": VLM_CONFIG.get("prompts", {}),
        "default_prompt": VLM_CONFIG.get("default_prompt", "default")
    }


@app.get("/api/vlm/services")
def get_vlm_services():
    """获取可用的 VLM 服务列表"""
    return {
        "services": [
            {
                "id": name,
                "name": svc.get("name", name),
                "description": svc.get("description", ""),
                "is_enabled": svc.get("is_enabled", True)
            }
            for name, svc in VLM_SERVICES.items()
            if svc.get("is_enabled", True)
        ],
        "default": VLM_CONFIG.get("default_service", "default")
    }


@app.get("/api/vlm/prompts")
def get_vlm_prompts():
    """获取可用的提示词列表"""
    prompts = VLM_CONFIG.get("prompts", {})
    return {
        "prompts": [
            {"name": name, "text": text[:100] + "..." if len(text) > 100 else text}
            for name, text in prompts.items()
        ],
        "default": VLM_CONFIG.get("default_prompt", "default")
    }


# ==================== 统计 ====================

@app.get("/api/stats")
def get_stats():
    """获取统计信息"""
    return {
        "total_images": db.count_images(),
        "ready_images": db.count_images(status="ready"),
        "pending_images": db.count_images(status="pending"),
        "failed_images": db.count_images(status="failed"),
        "image_index_count": image_index.count(),
        "text_index_count": text_index.count()
    }


# ==================== 批量处理 ====================

# 用于保护数据库和存储操作的锁（确保线程安全）
_db_lock = threading.Lock()

class BatchImportRequest(BaseModel):
    """批量导入请求"""
    directory: str
    source: Optional[str] = None
    recursive: bool = False
    generate_caption: bool = False
    caption_method: str = "vlm"
    caption_prompt: Optional[str] = None  # 提示词名称或自定义提示词
    vlm_service: Optional[str] = None  # VLM 服务名称
    force_reimport: bool = False  # 强制重新导入（即使已存在也重新处理）
    concurrency: int = 4  # 并发数量（1-16）


class BatchImportResult(BaseModel):
    """批量导入结果"""
    total_files: int
    imported: int
    skipped: int
    failed: int
    details: List[dict]


# ==================== VLM 服务配置 ====================

def load_vlm_config():
    """从配置文件加载 VLM 配置（支持多个 VLM 服务）"""
    import yaml
    
    default_services = {
        "default": {
            "name": "Default VLM",
            "endpoint": "http://localhost:6050",
            "timeout": 60,
            "is_enabled": True,
            "description": "默认 VLM 服务"
        }
    }
    
    default_config = {
        "default_service": "default",
        "prompts": {
            "default": "请详细描述这张图片的内容，包括主要物体、场景、颜色、风格等特征。"
        },
        "default_prompt": "default"
    }
    
    if not CONFIG_PATH.exists():
        return {"services": default_services, "config": default_config}
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 加载 VLM 服务列表
        vlm_services = config.get("vlm_services", default_services)
        
        # 加载 VLM 全局配置
        vlm_config = config.get("vlm", {})
        for key, value in default_config.items():
            if key not in vlm_config:
                vlm_config[key] = value
        
        return {"services": vlm_services, "config": vlm_config}
    except Exception as e:
        print(f"加载 VLM 配置失败: {e}")
        return {"services": default_services, "config": default_config}


# 加载 VLM 配置
VLM_DATA = load_vlm_config()
VLM_SERVICES = VLM_DATA["services"]
VLM_CONFIG = VLM_DATA["config"]


def get_vlm_service(service_name: str = None) -> dict:
    """
    获取 VLM 服务配置
    
    Args:
        service_name: VLM 服务名称，如果为 None 使用默认服务
    
    Returns:
        服务配置字典
    """
    if service_name is None:
        service_name = VLM_CONFIG.get("default_service", "default")
    
    if service_name in VLM_SERVICES:
        return VLM_SERVICES[service_name]
    
    # 返回第一个启用的服务
    for name, svc in VLM_SERVICES.items():
        if svc.get("is_enabled", True):
            return svc
    
    # 返回默认配置
    return {
        "name": "Default",
        "endpoint": "http://localhost:6050",
        "timeout": 60,
        "is_enabled": True
    }


def get_vlm_prompt(prompt_name: str = None) -> str:
    """
    获取 VLM 提示词
    
    Args:
        prompt_name: 提示词名称（default/short/detailed/tags/objects）
                    或者自定义提示词文本
                    如果为 None，使用配置中的 default_prompt
    
    Returns:
        提示词文本
    """
    prompts = VLM_CONFIG.get("prompts", {})
    
    if prompt_name is None:
        prompt_name = VLM_CONFIG.get("default_prompt", "default")
    
    # 如果在预设列表中，返回对应的提示词
    if prompt_name in prompts:
        return prompts[prompt_name]
    
    # 否则就是自定义提示词，直接返回
    # 如果是未知的预设名称（很短且不在预设中），也当作自定义返回
    return prompt_name if prompt_name else prompts.get("default", "请描述这张图片。")


def generate_caption_with_vlm(image_path: str, prompt_name: str = None, 
                              vlm_service: str = None) -> Optional[str]:
    """
    使用 VLM 服务生成图片描述
    
    Args:
        image_path: 图片路径
        prompt_name: 提示词名称或自定义提示词
        vlm_service: VLM 服务名称，如果为 None 使用默认服务
    
    Returns:
        生成的描述文本，失败返回 None
    """
    import requests
    import base64
    
    # 获取 VLM 服务配置
    service = get_vlm_service(vlm_service)
    
    # 检查服务是否启用
    if not service.get("is_enabled", True):
        print(f"VLM 服务 {service.get('name', 'unknown')} 未启用")
        return None
    
    endpoint = service.get("endpoint", "http://localhost:6050")
    timeout = service.get("timeout", 60)
    prompt = get_vlm_prompt(prompt_name)
    
    try:
        # 读取图片并编码
        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        
        # 调用 VLM 服务
        response = requests.post(
            f"{endpoint}/caption",
            json={
                "image_base64": image_base64,
                "prompt": prompt
            },
            timeout=timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("caption") or data.get("text") or data.get("response")
        else:
            print(f"VLM 服务返回错误: {response.status_code}")
            return None
    
    except Exception as e:
        print(f"调用 VLM 服务失败: {e}")
        return None


def import_single_image(file_path: Path, source: str = None, generate_caption: bool = False, 
                        caption_method: str = "vlm", caption_prompt: str = None,
                        vlm_service: str = None, force_reimport: bool = False) -> dict:
    """
    导入单张图片
    
    Args:
        force_reimport: 强制重新导入，即使图片已存在也重新计算嵌入
    
    Returns:
        导入结果字典
    """
    result = {
        "file": str(file_path),
        "status": "unknown",
        "sha256": None,
        "message": ""
    }
    
    try:
        # 读取文件
        content = file_path.read_bytes()
        sha256 = storage.compute_sha256_from_bytes(content)
        result["sha256"] = sha256
        
        # 检查是否已存在
        already_exists = db.image_exists(sha256)
        if already_exists and not force_reimport:
            result["status"] = "skipped"
            result["message"] = "图片已存在"
            return result
        
        if already_exists and force_reimport:
            # 强制重新导入：删除旧的向量记录，重新计算嵌入
            db.delete_vector_entries(sha256)
            image_index.remove(sha256)
            for idx in text_indexes.values():
                idx.remove(sha256)
            
            # 获取已存在的图片信息
            existing = db.get_image(sha256)
            meta = {
                "width": existing["width"],
                "height": existing["height"],
                "file_size": existing["file_size"],
                "format": existing["format"]
            }
            image_path = storage.get_image_path(sha256)
            result["message"] = "重新导入"
        else:
            # 新图片：保存文件
            image_path, meta = storage.save_image_from_bytes(content, sha256)
            
            # 添加数据库记录
            db.add_image(
                sha256=sha256,
                width=meta["width"],
                height=meta["height"],
                file_size=meta["file_size"],
                format=meta["format"],
                source=source
            )
            result["message"] = "新导入"
        
        # 计算图片嵌入 (这是I/O密集型操作，不需要加锁)
        embedding = embedding_client.get_image_embedding(image_path=str(image_path))
        
        # 数据库和索引操作需要加锁
        with _db_lock:
            if embedding is not None:
                # 保存嵌入到文件
                storage.save_embedding(sha256, "image", embedding)
                
                # 添加到向量索引
                image_index.add(embedding, sha256, "image")
                
                # 记录到数据库
                db.add_vector_entry(
                    sha256, "image", IMAGE_MODEL_NAME, IMAGE_MODEL_VERSION, IMAGE_INDEX_NAME
                )
                
                db.update_image_status(sha256, "ready")
            else:
                db.update_image_status(sha256, "pending")
        
        # 可选：生成描述
        if generate_caption:
            # VLM 调用不需要加锁（I/O密集型）
            caption = generate_caption_with_vlm(str(image_path), prompt_name=caption_prompt, 
                                                vlm_service=vlm_service)
            if caption:
                # 计算文本嵌入（I/O密集型）
                all_embeddings = embedding_client.get_all_text_embeddings(caption)
                
                # 数据库和索引操作需要加锁
                with _db_lock:
                    # 保存描述
                    storage.save_description(sha256, caption_method, caption)
                    db.add_description(sha256, caption_method, caption)
                    
                    for service_name, emb_info in all_embeddings.items():
                        emb = emb_info["embedding"]
                        model_name = emb_info["model_name"]
                        model_version = emb_info["model_version"]
                        
                        # 查找对应的索引
                        index_name = None
                        for idx_name, idx_config in TEXT_INDEXES.items():
                            if idx_config["service_name"] == service_name:
                                index_name = idx_name
                                break
                        
                        if index_name and index_name in text_indexes:
                            emb_filename = f"{caption_method}_{model_name.replace('-', '_')}"
                            storage.save_embedding(sha256, emb_filename, emb)
                            text_indexes[index_name].add(emb, sha256, caption_method)
                            db.add_vector_entry(sha256, caption_method, model_name, model_version, index_name)
                    
                    db.update_description_embedding(sha256, caption_method, True)
                result["caption"] = caption[:100] + "..." if len(caption) > 100 else caption
        
        result["status"] = "imported"
        result["message"] = "导入成功"
        result["width"] = meta["width"]
        result["height"] = meta["height"]
        
    except Exception as e:
        result["status"] = "failed"
        result["message"] = str(e)
    
    return result


@app.post("/api/batch/import")
def batch_import_directory(req: BatchImportRequest):
    """
    批量导入目录中的图片
    
    - 扫描指定目录（可递归）
    - 导入所有图片并计算嵌入
    - 可选：使用 VLM 生成描述
    """
    import glob
    
    dir_path = Path(req.directory)
    if not dir_path.exists():
        raise HTTPException(status_code=400, detail=f"目录不存在: {req.directory}")
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是目录: {req.directory}")
    
    # 收集图片文件
    image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
    image_files = []
    
    if req.recursive:
        for ext in image_extensions:
            image_files.extend(dir_path.rglob(f"*{ext}"))
            image_files.extend(dir_path.rglob(f"*{ext.upper()}"))
    else:
        for ext in image_extensions:
            image_files.extend(dir_path.glob(f"*{ext}"))
            image_files.extend(dir_path.glob(f"*{ext.upper()}"))
    
    # 去重
    image_files = list(set(image_files))
    
    # 导入统计
    imported = 0
    skipped = 0
    failed = 0
    details = []
    
    for file_path in image_files:
        result = import_single_image(
            file_path, 
            source=req.source, 
            generate_caption=req.generate_caption,
            caption_method=req.caption_method,
            caption_prompt=req.caption_prompt,
            vlm_service=req.vlm_service,
            force_reimport=req.force_reimport
        )
        details.append(result)
        
        if result["status"] == "imported":
            imported += 1
        elif result["status"] == "skipped":
            skipped += 1
        else:
            failed += 1
    
    return {
        "total_files": len(image_files),
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "details": details
    }


from fastapi.responses import StreamingResponse
import json
import time


@app.post("/api/batch/import/stream")
def batch_import_directory_stream(req: BatchImportRequest):
    """
    批量导入目录（流式响应，实时报告进度）
    
    使用 SSE 返回实时进度：
    - event: progress - 每处理一个文件发送进度
    - event: complete - 处理完成发送汇总
    
    支持并发处理：通过 concurrency 参数控制并发数
    """
    dir_path = Path(req.directory)
    if not dir_path.exists():
        raise HTTPException(status_code=400, detail=f"目录不存在: {req.directory}")
    if not dir_path.is_dir():
        raise HTTPException(status_code=400, detail=f"路径不是目录: {req.directory}")
    
    # 限制并发数范围
    concurrency = max(1, min(16, req.concurrency))
    
    def generate():
        import queue
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # 收集图片文件
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
        image_files = []
        
        if req.recursive:
            for ext in image_extensions:
                image_files.extend(dir_path.rglob(f"*{ext}"))
                image_files.extend(dir_path.rglob(f"*{ext.upper()}"))
        else:
            for ext in image_extensions:
                image_files.extend(dir_path.glob(f"*{ext}"))
                image_files.extend(dir_path.glob(f"*{ext.upper()}"))
        
        image_files = list(set(image_files))
        total = len(image_files)
        
        # 发送初始化事件
        yield f"event: init\ndata: {json.dumps({'total': total, 'concurrency': concurrency})}\n\n"
        
        if total == 0:
            yield f"event: complete\ndata: {json.dumps({'total_files': 0, 'imported': 0, 'skipped': 0, 'failed': 0, 'elapsed': 0, 'avg_speed': 0})}\n\n"
            return
        
        imported = 0
        skipped = 0
        failed = 0
        start_time = time.time()
        completed_count = 0
        
        # 定义处理单个文件的函数
        def process_file(file_path, index):
            item_start = time.time()
            result = import_single_image(
                file_path, 
                source=req.source, 
                generate_caption=req.generate_caption,
                caption_method=req.caption_method,
                caption_prompt=req.caption_prompt,
                vlm_service=req.vlm_service,
                force_reimport=req.force_reimport
            )
            return {
                "index": index,
                "file_path": file_path,
                "result": result,
                "time": round(time.time() - item_start, 2)
            }
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # 提交所有任务
            futures = {
                executor.submit(process_file, file_path, i): i 
                for i, file_path in enumerate(image_files)
            }
            
            # 按完成顺序处理结果
            for future in as_completed(futures):
                try:
                    res = future.result()
                    result = res["result"]
                    file_path = res["file_path"]
                    item_time = res["time"]
                    
                    if result["status"] == "imported":
                        imported += 1
                    elif result["status"] == "skipped":
                        skipped += 1
                    else:
                        failed += 1
                    
                    completed_count += 1
                    
                    # 计算进度和速度
                    elapsed = time.time() - start_time
                    speed = completed_count / elapsed if elapsed > 0 else 0
                    eta = (total - completed_count) / speed if speed > 0 else 0
                    
                    progress_data = {
                        "current": completed_count,
                        "total": total,
                        "percent": round(completed_count / total * 100, 1),
                        "imported": imported,
                        "skipped": skipped,
                        "failed": failed,
                        "speed": round(speed, 2),
                        "eta": round(eta, 1),
                        "elapsed": round(elapsed, 1),
                        "item": {
                            "file": str(file_path.name),
                            "status": result["status"],
                            "message": result.get("message", ""),
                            "time": item_time
                        }
                    }
                    
                    yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
                except Exception as e:
                    completed_count += 1
                    failed += 1
                    logger.error(f"处理文件时出错: {e}")
                    
                    elapsed = time.time() - start_time
                    speed = completed_count / elapsed if elapsed > 0 else 0
                    eta = (total - completed_count) / speed if speed > 0 else 0
                    
                    yield f"event: progress\ndata: {json.dumps({'current': completed_count, 'total': total, 'percent': round(completed_count / total * 100, 1), 'imported': imported, 'skipped': skipped, 'failed': failed, 'speed': round(speed, 2), 'eta': round(eta, 1), 'elapsed': round(elapsed, 1), 'item': {'file': 'unknown', 'status': 'error', 'message': str(e), 'time': 0}})}\n\n"
        
        # 发送完成事件
        total_elapsed = time.time() - start_time
        complete_data = {
            "total_files": total,
            "imported": imported,
            "skipped": skipped,
            "failed": failed,
            "elapsed": round(total_elapsed, 1),
            "avg_speed": round(total / total_elapsed, 2) if total_elapsed > 0 else 0
        }
        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


def _process_single_image(img: dict, method: str, prompt_name: Optional[str], vlm_service: Optional[str]):
    """处理单张图片的描述生成（供并发调用）"""
    sha256 = img["sha256"]
    
    # 获取图片路径
    image_path = storage.get_image_path(sha256)
    if not image_path.exists():
        return {"sha256": sha256, "status": "failed", "message": "图片文件不存在"}
    
    # 生成描述（这是最耗时的操作，可以并发）
    caption = generate_caption_with_vlm(str(image_path), prompt_name=prompt_name, 
                                        vlm_service=vlm_service)
    if not caption:
        return {"sha256": sha256, "status": "failed", "message": "VLM 服务失败"}
    
    # 数据库和存储操作需要加锁
    with _db_lock:
        # 保存描述
        storage.save_description(sha256, method, caption)
        db.add_description(sha256, method, caption)
        
        # 计算文本嵌入
        all_embeddings = embedding_client.get_all_text_embeddings(caption)
        
        for service_name, emb_info in all_embeddings.items():
            emb = emb_info["embedding"]
            model_name = emb_info["model_name"]
            model_version = emb_info["model_version"]
            
            index_name = None
            for idx_name, idx_config in TEXT_INDEXES.items():
                if idx_config["service_name"] == service_name:
                    index_name = idx_name
                    break
            
            if index_name and index_name in text_indexes:
                emb_filename = f"{method}_{model_name.replace('-', '_')}"
                storage.save_embedding(sha256, emb_filename, emb)
                text_indexes[index_name].add(emb, sha256, method)
                
                try:
                    db.add_vector_entry(sha256, method, model_name, model_version, index_name)
                except:
                    pass  # 忽略重复记录
        
        db.update_description_embedding(sha256, method, True)
    
    return {
        "sha256": sha256, 
        "status": "success", 
        "caption": caption[:100] + "..." if len(caption) > 100 else caption
    }


@app.post("/api/batch/generate-captions")
def batch_generate_captions(
    source: Optional[str] = None,
    method: str = "vlm",
    overwrite: bool = False,
    limit: int = Query(100, ge=1, le=1000),
    prompt: Optional[str] = None,
    vlm_service: Optional[str] = None,
    concurrency: int = Query(4, ge=1, le=16, description="并发数量")
):
    """
    批量为已有图片生成描述（支持并发）
    
    - source: 只处理指定来源的图片
    - method: 描述方法标记（默认 vlm）
    - overwrite: 是否覆盖已有描述
    - limit: 最多处理数量
    - prompt: 提示词名称（default/short/detailed/tags/objects）或自定义提示词
    - vlm_service: VLM 服务名称（如 qwen3vl），不指定使用默认服务
    - concurrency: 并发请求数量（默认 4，建议设置为后端 VLM 实例数）
    """
    # 获取需要处理的图片
    images = db.list_images(offset=0, limit=limit, source=source, status="ready")
    
    # 过滤已有描述的图片
    images_to_process = []
    skipped = 0
    
    for img in images:
        sha256 = img["sha256"]
        if not overwrite:
            existing = db.get_descriptions(sha256)
            if any(d["method"] == method for d in existing):
                skipped += 1
                continue
        images_to_process.append(img)
    
    processed = 0
    failed = 0
    results = []
    
    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # 提交所有任务
        future_to_img = {
            executor.submit(_process_single_image, img, method, prompt, vlm_service): img
            for img in images_to_process
        }
        
        # 收集结果
        for future in as_completed(future_to_img):
            result = future.result()
            results.append(result)
            if result["status"] == "success":
                processed += 1
            else:
                failed += 1
    
    return {
        "total": len(images),
        "processed": processed,
        "skipped": skipped,
        "failed": failed,
        "concurrency": concurrency,
        "results": results
    }


@app.get("/api/batch/pending")
def get_pending_images(limit: int = Query(100, ge=1, le=1000)):
    """获取待处理的图片（嵌入未计算）"""
    images = db.list_images(offset=0, limit=limit, status="pending")
    return {
        "count": len(images),
        "images": images
    }


@app.post("/api/batch/recompute-embeddings")
def batch_recompute_embeddings(
    source: Optional[str] = None,
    status: Optional[str] = None,
    include_text: bool = False,
    limit: int = Query(100, ge=1, le=1000)
):
    """
    批量重新计算嵌入
    
    - source: 只处理指定来源的图片
    - status: 只处理指定状态的图片
    - include_text: 是否同时更新文本嵌入
    - limit: 最多处理数量
    """
    images = db.list_images(offset=0, limit=limit, source=source, status=status)
    
    processed = 0
    failed = 0
    results = []
    
    for img in images:
        sha256 = img["sha256"]
        
        try:
            # 删除旧的向量记录
            db.delete_vector_entries(sha256)
            
            # 计算图片嵌入
            image_path = storage.get_image_path(sha256)
            if not image_path.exists():
                failed += 1
                results.append({"sha256": sha256, "status": "failed", "message": "文件不存在"})
                continue
            
            image_index.remove(sha256)
            embedding = embedding_client.get_image_embedding(image_path=str(image_path))
            
            if embedding is not None:
                storage.save_embedding(sha256, "image", embedding)
                image_index.add(embedding, sha256, "image")
                db.add_vector_entry(sha256, "image", IMAGE_MODEL_NAME, IMAGE_MODEL_VERSION, IMAGE_INDEX_NAME)
                db.update_image_status(sha256, "ready")
            else:
                db.update_image_status(sha256, "pending")
                failed += 1
                results.append({"sha256": sha256, "status": "failed", "message": "嵌入服务不可用"})
                continue
            
            # 可选：重新计算文本嵌入
            if include_text:
                descriptions = db.get_descriptions(sha256)
                for desc in descriptions:
                    method = desc["method"]
                    content = storage.get_description(sha256, method)
                    if not content:
                        continue
                    
                    for idx_name, idx in text_indexes.items():
                        idx.remove(sha256)
                    
                    all_embeddings = embedding_client.get_all_text_embeddings(content)
                    for service_name, emb_info in all_embeddings.items():
                        emb = emb_info["embedding"]
                        model_name = emb_info["model_name"]
                        model_version = emb_info["model_version"]
                        
                        index_name = None
                        for idx_name, idx_config in TEXT_INDEXES.items():
                            if idx_config["service_name"] == service_name:
                                index_name = idx_name
                                break
                        
                        if index_name and index_name in text_indexes:
                            emb_filename = f"{method}_{model_name.replace('-', '_')}"
                            storage.save_embedding(sha256, emb_filename, emb)
                            text_indexes[index_name].add(emb, sha256, method)
                            db.add_vector_entry(sha256, method, model_name, model_version, index_name)
                    
                    db.update_description_embedding(sha256, method, True)
            
            processed += 1
            results.append({"sha256": sha256, "status": "success"})
        
        except Exception as e:
            failed += 1
            results.append({"sha256": sha256, "status": "failed", "message": str(e)})
    
    return {
        "total": len(images),
        "processed": processed,
        "failed": failed,
        "results": results
    }


@app.post("/api/batch/generate-captions/stream")
def batch_generate_captions_stream(
    source: Optional[str] = None,
    method: str = "vlm",
    overwrite: bool = False,
    limit: int = Query(100, ge=1, le=1000),
    prompt: Optional[str] = None,
    vlm_service: Optional[str] = None,
    concurrency: int = Query(4, ge=1, le=16, description="并发数量")
):
    """批量生成描述（流式响应，支持并发，实时报告进度）"""
    import queue
    
    def generate():
        images = db.list_images(offset=0, limit=limit, source=source, status="ready")
        total = len(images)
        
        yield f"event: init\ndata: {json.dumps({'total': total, 'concurrency': concurrency})}\n\n"
        
        # 过滤已有描述的图片
        images_to_process = []
        skipped_images = []
        
        for img in images:
            sha256 = img["sha256"]
            if not overwrite:
                existing = db.get_descriptions(sha256)
                if any(d["method"] == method for d in existing):
                    skipped_images.append(img)
                    continue
            images_to_process.append(img)
        
        skipped = len(skipped_images)
        processed = 0
        failed = 0
        start_time = time.time()
        results_queue = queue.Queue()
        
        # 先报告跳过的图片
        for i, img in enumerate(skipped_images):
            sha256 = img["sha256"]
            progress_data = {
                "current": i + 1,
                "total": total,
                "percent": round((i + 1) / total * 100, 1),
                "processed": 0,
                "skipped": i + 1,
                "failed": 0,
                "speed": 0,
                "eta": 0,
                "elapsed": round(time.time() - start_time, 1),
                "item": {
                    "sha256": sha256[:16] + "...",
                    "status": "skipped",
                    "message": "已有描述",
                    "time": 0
                }
            }
            yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
        
        if not images_to_process:
            complete_data = {
                "total": total,
                "processed": 0,
                "skipped": skipped,
                "failed": 0,
                "elapsed": round(time.time() - start_time, 1),
                "avg_speed": 0,
                "concurrency": concurrency
            }
            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
            return
        
        # 使用线程池并发处理
        def worker(img, index):
            sha256 = img["sha256"]
            item_start = time.time()
            result = _process_single_image(img, method, prompt, vlm_service)
            result["index"] = index
            result["time"] = round(time.time() - item_start, 2)
            results_queue.put(result)
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # 提交所有任务
            futures = []
            for i, img in enumerate(images_to_process):
                future = executor.submit(worker, img, skipped + i)
                futures.append(future)
            
            # 收集结果并实时报告
            completed = 0
            while completed < len(images_to_process):
                try:
                    result = results_queue.get(timeout=0.5)
                    completed += 1
                    
                    if result["status"] == "success":
                        processed += 1
                    else:
                        failed += 1
                    
                    current = skipped + completed
                    elapsed = time.time() - start_time
                    speed = completed / elapsed if elapsed > 0 else 0
                    remaining = len(images_to_process) - completed
                    eta = remaining / speed if speed > 0 else 0
                    
                    progress_data = {
                        "current": current,
                        "total": total,
                        "percent": round(current / total * 100, 1),
                        "processed": processed,
                        "skipped": skipped,
                        "failed": failed,
                        "speed": round(speed, 2),
                        "eta": round(eta, 1),
                        "elapsed": round(elapsed, 1),
                        "item": {
                            "sha256": result["sha256"][:16] + "...",
                            "status": result["status"],
                            "message": result.get("message", result.get("caption", ""))[:50],
                            "time": result["time"]
                        }
                    }
                    yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
                except queue.Empty:
                    continue
        
        complete_data = {
            "total": total,
            "processed": processed,
            "skipped": skipped,
            "failed": failed,
            "elapsed": round(time.time() - start_time, 1),
            "avg_speed": round(len(images_to_process) / (time.time() - start_time), 2) if images_to_process else 0,
            "concurrency": concurrency
        }
        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


@app.post("/api/batch/recompute-embeddings/stream")
def batch_recompute_embeddings_stream(
    source: Optional[str] = None,
    status: Optional[str] = None,
    include_text: bool = False,
    limit: int = Query(100, ge=1, le=1000)
):
    """批量重新计算嵌入（流式响应，实时报告进度）"""
    
    def generate():
        images = db.list_images(offset=0, limit=limit, source=source, status=status)
        total = len(images)
        
        yield f"event: init\ndata: {json.dumps({'total': total})}\n\n"
        
        processed = 0
        failed = 0
        start_time = time.time()
        
        for i, img in enumerate(images):
            sha256 = img["sha256"]
            item_start = time.time()
            item_status = "processing"
            item_message = ""
            
            try:
                db.delete_vector_entries(sha256)
                image_path = storage.get_image_path(sha256)
                
                if not image_path.exists():
                    failed += 1
                    item_status = "failed"
                    item_message = "文件不存在"
                else:
                    image_index.remove(sha256)
                    embedding = embedding_client.get_image_embedding(image_path=str(image_path))
                    
                    if embedding is not None:
                        storage.save_embedding(sha256, "image", embedding)
                        image_index.add(embedding, sha256, "image")
                        db.add_vector_entry(sha256, "image", IMAGE_MODEL_NAME, IMAGE_MODEL_VERSION, IMAGE_INDEX_NAME)
                        db.update_image_status(sha256, "ready")
                        
                        if include_text:
                            descriptions = db.get_descriptions(sha256)
                            for desc in descriptions:
                                desc_method = desc["method"]
                                content = storage.get_description(sha256, desc_method)
                                if not content:
                                    continue
                                
                                for idx_name, idx in text_indexes.items():
                                    idx.remove(sha256)
                                
                                all_embeddings = embedding_client.get_all_text_embeddings(content)
                                for service_name, emb_info in all_embeddings.items():
                                    emb = emb_info["embedding"]
                                    model_name = emb_info["model_name"]
                                    model_version = emb_info["model_version"]
                                    
                                    index_name = None
                                    for idx_name, idx_config in TEXT_INDEXES.items():
                                        if idx_config["service_name"] == service_name:
                                            index_name = idx_name
                                            break
                                    
                                    if index_name and index_name in text_indexes:
                                        emb_filename = f"{desc_method}_{model_name.replace('-', '_')}"
                                        storage.save_embedding(sha256, emb_filename, emb)
                                        text_indexes[index_name].add(emb, sha256, desc_method)
                                        db.add_vector_entry(sha256, desc_method, model_name, model_version, index_name)
                                
                                db.update_description_embedding(sha256, desc_method, True)
                        
                        processed += 1
                        item_status = "success"
                        item_message = "更新完成"
                    else:
                        db.update_image_status(sha256, "pending")
                        failed += 1
                        item_status = "failed"
                        item_message = "嵌入服务不可用"
            
            except Exception as e:
                failed += 1
                item_status = "failed"
                item_message = str(e)
            
            current = i + 1
            elapsed = time.time() - start_time
            speed = current / elapsed if elapsed > 0 else 0
            eta = (total - current) / speed if speed > 0 else 0
            
            progress_data = {
                "current": current,
                "total": total,
                "percent": round(current / total * 100, 1),
                "processed": processed,
                "failed": failed,
                "speed": round(speed, 2),
                "eta": round(eta, 1),
                "elapsed": round(elapsed, 1),
                "item": {
                    "sha256": sha256[:16] + "...",
                    "status": item_status,
                    "message": item_message,
                    "time": round(time.time() - item_start, 2)
                }
            }
            yield f"event: progress\ndata: {json.dumps(progress_data)}\n\n"
        
        complete_data = {
            "total": total,
            "processed": processed,
            "failed": failed,
            "elapsed": round(time.time() - start_time, 1),
            "avg_speed": round(total / (time.time() - start_time), 2) if total > 0 else 0
        }
        yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=6060)

