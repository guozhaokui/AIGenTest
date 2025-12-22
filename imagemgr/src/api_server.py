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
    top_k: int = 10
    index: Optional[str] = None  # 指定使用的索引，默认使用 qwen3


class ImageSearchRequest(BaseModel):
    """以图搜图请求（Base64）"""
    image_base64: str
    top_k: int = 10


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
    
    # 补充图片信息
    enriched_results = []
    for r in deduplicated:
        image = db.get_image(r["sha256"])
        if image:
            # 获取匹配的描述内容
            matched_text = storage.get_description(r["sha256"], r["matched_by"])
            enriched_results.append({
                **r,
                "matched_text": matched_text,
                "width": image["width"],
                "height": image["height"]
            })
    
    return {
        "query": req.query, 
        "indexes_searched": used_models,
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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=6060)

