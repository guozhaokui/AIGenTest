"""
FastAPI 服务端
提供知识图谱搜索的HTTP接口
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from pathlib import Path

from .config import SERVICE_PORT, SERVICE_HOST, RECORDS_DIR, BASE_DIR
from .knowledge_indexer import KnowledgeIndexer
from .activation_search import ActivationSearch


app = FastAPI(
    title="MemGraph API",
    description="激活式知识图谱搜索引擎",
    version="3.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
STATIC_DIR = BASE_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 全局变量
indexer: Optional[KnowledgeIndexer] = None
search_engine: Optional[ActivationSearch] = None


# ============================================================================
# 请求模型
# ============================================================================

class RecordLessonRequest(BaseModel):
    role: str = "AI"
    project: Optional[str] = None
    directory: Optional[str] = None
    problem: str
    solution: str
    tags: List[str] = []


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    min_score: float = 0.1
    use_vector: bool = True
    filter_tags: List[str] = []
    filter_project: Optional[str] = None


class TagSearchRequest(BaseModel):
    tag: str
    limit: int = 10


class RecentRequest(BaseModel):
    limit: int = 10


# ============================================================================
# 启动和关闭事件
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """启动时初始化索引"""
    global indexer, search_engine

    print("Initializing MemGraph...")

    indexer = KnowledgeIndexer()
    search_engine = ActivationSearch(indexer)

    # 如果有记录目录，同步现有文档
    if RECORDS_DIR.exists():
        await sync_existing_documents()

    stats = indexer.get_stats()
    print(f"MemGraph initialized: {stats['documents']} documents indexed")


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    global indexer, search_engine

    if indexer:
        indexer.close()

    if search_engine and search_engine.embedding_client:
        await search_engine.embedding_client.close()

    print("MemGraph shutdown complete")


async def sync_existing_documents():
    """同步现有的Markdown文档"""
    if not RECORDS_DIR.exists():
        return

    import re
    from datetime import datetime

    documents = []

    for md_file in RECORDS_DIR.rglob("*.md"):
        try:
            content = md_file.read_text(encoding='utf-8')

            # 解析frontmatter
            metadata = {}
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2]

                    # 解析元数据
                    for line in frontmatter.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()

                            if key == 'tags':
                                # 解析标签数组
                                value = [t.strip() for t in value.strip('[]').split(',')]
                            metadata[key] = value

                    # 解析问题和解决方案
                    problem_match = re.search(r'## 问题\s*\n+(.*?)(?=\n##|\Z)', body, re.DOTALL)
                    solution_match = re.search(r'## 解决[方法办]*\s*\n+(.*)', body, re.DOTALL)

                    metadata['problem'] = problem_match.group(1).strip() if problem_match else ''
                    metadata['solution'] = solution_match.group(1).strip() if solution_match else ''

            relative_path = md_file.relative_to(RECORDS_DIR)

            document = {
                'path': str(relative_path).replace('\\', '/'),
                'role': metadata.get('role', 'AI'),
                'project': metadata.get('project', ''),
                'directory': metadata.get('directory', ''),
                'timestamp': metadata.get('timestamp', datetime.now().isoformat()),
                'tags': metadata.get('tags', []) if isinstance(metadata.get('tags'), list) else [],
                'problem': metadata.get('problem', ''),
                'solution': metadata.get('solution', '')
            }

            documents.append(document)

        except Exception as e:
            print(f"Failed to parse {md_file}: {e}")

    if documents:
        print(f"Syncing {len(documents)} existing documents...")
        await indexer.index_documents(documents)
        print("Sync completed")


# ============================================================================
# API 端点
# ============================================================================

@app.get("/")
async def root():
    """根路径重定向到Web界面"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "service": "MemGraph",
        "version": "3.0.0"
    }


@app.get("/stats")
async def get_stats():
    """获取统计信息"""
    stats = indexer.get_stats()
    return stats


@app.post("/record")
async def record_lesson(req: RecordLessonRequest):
    """记录新的经验教训"""
    import uuid
    from datetime import datetime

    # 生成文件路径
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    slug = req.problem[:30].replace(' ', '-')
    filename = f"{timestamp}_{slug}.md"

    document = {
        'path': filename,
        'role': req.role,
        'project': req.project or '',
        'directory': req.directory or '',
        'timestamp': now.isoformat(),
        'tags': req.tags,
        'problem': req.problem,
        'solution': req.solution
    }

    doc_id = await indexer.index_document(document)

    return {
        "success": True,
        "doc_id": doc_id,
        "path": filename
    }


@app.post("/search")
async def search_lessons(req: SearchRequest):
    """搜索经验教训"""
    results = await search_engine.search(req.query, {
        'limit': req.limit,
        'min_score': req.min_score,
        'use_vector': req.use_vector,
        'filter_tags': req.filter_tags,
        'filter_project': req.filter_project
    })

    return {
        "query": req.query,
        "count": len(results),
        "results": results
    }


@app.post("/search/tag")
async def search_by_tag(req: TagSearchRequest):
    """按标签搜索"""
    results = search_engine.search_by_tag(req.tag, req.limit)

    return {
        "tag": req.tag,
        "count": len(results),
        "results": results
    }


@app.post("/recent")
async def list_recent(req: RecentRequest):
    """获取最近的记录"""
    results = search_engine.get_recent(req.limit)

    return {
        "count": len(results),
        "results": results
    }


@app.get("/tags")
async def list_tags():
    """列出所有标签"""
    cursor = indexer.conn.execute(
        'SELECT DISTINCT tag FROM document_tags ORDER BY tag'
    )
    tags = [row[0] for row in cursor.fetchall()]

    return {
        "count": len(tags),
        "tags": tags
    }


@app.post("/rebuild")
async def rebuild_index():
    """重建索引"""
    indexer.clear_all()
    await sync_existing_documents()
    stats = indexer.get_stats()

    return {
        "success": True,
        "stats": stats
    }


# ============================================================================
# 调试接口
# ============================================================================

@app.get("/debug/vectors")
async def debug_vectors():
    """获取所有向量的详细信息"""
    import numpy as np

    if not indexer.index or indexer.index.ntotal == 0:
        return {
            "total_vectors": 0,
            "dimension": 0,
            "index_type": "empty",
            "vectors": []
        }

    vectors = []

    # 反向映射：faiss_index -> doc_id
    index_to_doc = {v: k for k, v in indexer.doc_id_to_index.items()}

    for faiss_idx in range(indexer.index.ntotal):
        # 获取向量
        vec = indexer.index.reconstruct(faiss_idx)

        # 获取对应的文档ID
        doc_id = index_to_doc.get(faiss_idx)

        # 获取文档信息
        path = None
        if doc_id:
            cursor = indexer.conn.execute(
                'SELECT path FROM documents WHERE id = ?',
                (doc_id,)
            )
            row = cursor.fetchone()
            if row:
                path = row[0]

        vectors.append({
            "faiss_index": faiss_idx,
            "doc_id": doc_id,
            "path": path,
            "norm": float(np.linalg.norm(vec)),
            "preview": [float(x) for x in vec[:10]],  # 前10维
            "full_vector": str([float(x) for x in vec])
        })

    return {
        "total_vectors": indexer.index.ntotal,
        "dimension": indexer.index.d,
        "index_type": str(type(indexer.index).__name__),
        "vectors": vectors
    }


@app.get("/debug/documents")
async def debug_documents():
    """获取所有文档及其向量映射状态"""
    cursor = indexer.conn.execute('''
        SELECT id, path, role, project, timestamp
        FROM documents
        ORDER BY timestamp DESC
    ''')

    documents = []
    for row in cursor.fetchall():
        doc_id = row[0]

        # 检查是否有FAISS向量
        has_faiss = doc_id in indexer.doc_id_to_index
        faiss_index = indexer.doc_id_to_index.get(doc_id)

        # 获取标签
        tag_cursor = indexer.conn.execute(
            'SELECT tag FROM document_tags WHERE doc_id = ?',
            (doc_id,)
        )
        tags = [t[0] for t in tag_cursor.fetchall()]

        # 获取问题预览
        problem_cursor = indexer.conn.execute(
            'SELECT problem FROM documents WHERE id = ?',
            (doc_id,)
        )
        problem_row = problem_cursor.fetchone()
        problem_preview = problem_row[0][:100] if problem_row and problem_row[0] else '-'

        documents.append({
            "doc_id": doc_id,
            "path": row[1],
            "role": row[2],
            "project": row[3] or '-',
            "timestamp": row[4],
            "tags": tags,
            "has_faiss_vector": has_faiss,
            "faiss_index": faiss_index,
            "problem_preview": problem_preview
        })

    return {
        "total_documents": len(documents),
        "documents": documents
    }


@app.get("/debug/ngrams")
async def debug_ngrams():
    """获取N-gram统计信息"""
    # 按类型统计
    cursor = indexer.conn.execute('''
        SELECT gram_type, COUNT(*) as count
        FROM ngrams
        GROUP BY gram_type
    ''')

    by_type = {}
    for row in cursor.fetchall():
        by_type[row[0]] = row[1]

    # Top N-gram
    cursor = indexer.conn.execute('''
        SELECT content, gram_type, COUNT(DISTINCT doc_id) as doc_count, COUNT(*) as total_count
        FROM ngrams
        GROUP BY content, gram_type
        ORDER BY doc_count DESC, total_count DESC
        LIMIT 50
    ''')

    top_ngrams = []
    for row in cursor.fetchall():
        top_ngrams.append({
            "content": row[0],
            "gram_type": row[1],
            "doc_count": row[2],
            "total_count": row[3]
        })

    return {
        "by_type": by_type,
        "top_ngrams": top_ngrams
    }


@app.post("/debug/test-embedding")
async def debug_test_embedding():
    """测试嵌入服务"""
    import time

    try:
        start = time.time()
        test_text = "这是一个测试文本"

        embedding = await search_engine.embedding_client.embed_text(test_text)

        elapsed = (time.time() - start) * 1000

        return {
            "success": True,
            "dimension": len(embedding),
            "time_ms": round(elapsed, 2),
            "preview": [float(x) for x in embedding[:10]]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# 启动服务
# ============================================================================

def start_server():
    """启动服务"""
    print(f"""
╔════════════════════════════════════════════════════════════╗
║                   MemGraph 服务启动                        ║
╠════════════════════════════════════════════════════════════╣
║  服务地址: http://{SERVICE_HOST}:{SERVICE_PORT}             ║
║  文档地址: http://localhost:{SERVICE_PORT}/docs             ║
╠════════════════════════════════════════════════════════════╣
║  特性:                                                     ║
║    • 激活式搜索                                            ║
║    • FAISS向量检索                                         ║
║    • 多粒度N-gram                                          ║
║    • Qwen3-8B嵌入                                          ║
╚════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "src.server:app",
        host=SERVICE_HOST,
        port=SERVICE_PORT,
        reload=False
    )


if __name__ == "__main__":
    start_server()
