"""
QA 搜索 WebServer
提供问题搜索 API，返回最相似的 QA 对
"""
import json
import sys
from pathlib import Path
import pickle
import numpy as np
import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

# 添加 aiserver 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import url_embed_8b

# 配置
INDEX_DIR = Path(__file__).parent / "index"
STATIC_DIR = Path(__file__).parent / "static"
EMBED_URL = url_embed_8b()
SERVER_PORT = 8088

# 全局变量
question_index = None
answer_index = None
metadata = None
config = None

app = FastAPI(title="QA 搜索服务")


def load_index():
    """加载 FAISS 索引和元数据"""
    global question_index, answer_index, metadata, config
    
    try:
        import faiss
    except ImportError:
        print("错误: 请先安装 faiss-cpu 或 faiss-gpu")
        sys.exit(1)
    
    print("加载索引...")
    
    # 检查索引文件是否存在
    if not (INDEX_DIR / "question.index").exists():
        print("错误: 索引文件不存在，请先运行 build_index.py")
        sys.exit(1)
    
    # 加载 FAISS 索引
    question_index = faiss.read_index(str(INDEX_DIR / "question.index"))
    answer_index = faiss.read_index(str(INDEX_DIR / "answer.index"))
    
    # 加载元数据
    with open(INDEX_DIR / "metadata.pkl", "rb") as f:
        metadata = pickle.load(f)
    
    # 加载配置
    with open(INDEX_DIR / "config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    
    print(f"索引加载完成: {config['total_count']} 条记录")


def embed_query(text: str) -> np.ndarray:
    """对查询文本进行嵌入"""
    response = requests.post(
        f"{EMBED_URL}/embed/text",
        json={"text": text, "instruction": "Retrieve relevant QA pairs for the query"},
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    return np.array(result["embedding"], dtype=np.float32).reshape(1, -1)


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str
    top_k: int = 100
    search_type: str = "question"  # question, answer, both


class SearchResult(BaseModel):
    """搜索结果"""
    id: int
    instruction: str
    input: str
    output: str
    score: float
    source_file: str


@app.on_event("startup")
async def startup_event():
    load_index()


@app.get("/")
async def index():
    """返回前端页面"""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "total_records": config["total_count"] if config else 0,
        "dimension": config["dimension"] if config else 0,
        "embed_model": config["embed_model"] if config else "unknown"
    }


@app.post("/search")
async def search(req: SearchRequest):
    """
    搜索相似 QA 对
    
    Args:
        query: 查询文本
        top_k: 返回前 K 条结果
        search_type: 搜索类型 (question/answer/both)
    """
    try:
        # 对查询进行嵌入
        query_embedding = embed_query(req.query)
        
        results = []
        
        if req.search_type in ["question", "both"]:
            # 在问题索引中搜索
            scores, indices = question_index.search(query_embedding, req.top_k)
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx >= 0:  # FAISS 可能返回 -1 表示无结果
                    item = metadata[idx]
                    results.append({
                        "id": item["id"],
                        "instruction": item["instruction"],
                        "input": item["input"],
                        "output": item["output"],
                        "score": float(score),
                        "source_file": item["source_file"],
                        "match_type": "question"
                    })
        
        if req.search_type in ["answer", "both"]:
            # 在答案索引中搜索
            scores, indices = answer_index.search(query_embedding, req.top_k)
            for i, (score, idx) in enumerate(zip(scores[0], indices[0])):
                if idx >= 0:
                    item = metadata[idx]
                    results.append({
                        "id": item["id"],
                        "instruction": item["instruction"],
                        "input": item["input"],
                        "output": item["output"],
                        "score": float(score),
                        "source_file": item["source_file"],
                        "match_type": "answer"
                    })
        
        # 按分数排序并去重
        if req.search_type == "both":
            seen_ids = set()
            unique_results = []
            results.sort(key=lambda x: x["score"], reverse=True)
            for r in results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    unique_results.append(r)
            results = unique_results[:req.top_k]
        
        return JSONResponse(content={
            "query": req.query,
            "total": len(results),
            "results": results
        })
    
    except Exception as e:
        print(f"搜索错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search")
async def search_get(
    query: str = Query(..., description="查询文本"),
    top_k: int = Query(100, description="返回前 K 条结果"),
    search_type: str = Query("question", description="搜索类型")
):
    """GET 方式搜索"""
    return await search(SearchRequest(query=query, top_k=top_k, search_type=search_type))


if __name__ == "__main__":
    # 确保 static 目录存在
    STATIC_DIR.mkdir(exist_ok=True)
    
    print(f"启动 QA 搜索服务，端口: {SERVER_PORT}")
    print(f"嵌入服务: {EMBED_URL}")
    print(f"前端地址: http://localhost:{SERVER_PORT}/")
    
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT)

