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
from .query_logger import QueryLogger


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
query_logger: QueryLogger = QueryLogger()
_initialized = False

# 重建进度跟踪
rebuild_progress = {
    "in_progress": False,
    "current": 0,
    "total": 0,
    "message": "",
    "phase": ""  # "scanning" or "indexing"
}


async def ensure_initialized():
    """确保服务已初始化（延迟初始化）"""
    global indexer, search_engine, _initialized

    if _initialized:
        return

    try:
        print("Lazy initializing MemGraph...")

        indexer = KnowledgeIndexer()
        search_engine = ActivationSearch(indexer)

        # 启动时不自动同步，让用户手动点击"重建索引"
        # 如果有记录目录，同步现有文档
        # if RECORDS_DIR.exists():
        #     print(f"Syncing documents from {RECORDS_DIR}...")
        #     await sync_existing_documents()

        stats = indexer.get_stats()
        print(f"MemGraph initialized: {stats['documents']} documents indexed")

        _initialized = True

    except Exception as e:
        print(f"❌ Failed to initialize MemGraph: {e}")
        import traceback
        traceback.print_exc()
        raise


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

# 注释掉 startup 事件，改用 lazy initialization
# @app.on_event("startup")
# async def startup_event():
#     """启动时初始化索引"""
#     pass


@app.on_event("shutdown")
async def shutdown_event():
    """关闭时清理资源"""
    global indexer, search_engine

    if indexer:
        indexer.close()

    if search_engine and search_engine.embedding_client:
        await search_engine.embedding_client.close()

    print("MemGraph shutdown complete")


async def sync_existing_documents(progress_callback=None):
    """同步现有的Markdown文档

    Args:
        progress_callback: 可选的进度回调函数 (current, total, message)
    """
    if not RECORDS_DIR.exists():
        return

    import re
    from datetime import datetime

    documents = []

    # 首先收集所有文件
    all_files = list(RECORDS_DIR.rglob("*.md"))
    total_files = len(all_files)

    if progress_callback:
        progress_callback(0, total_files, f"开始扫描 {total_files} 个文档...")

    print(f"Found {total_files} markdown files to process")

    for idx, md_file in enumerate(all_files, 1):
        try:
            if progress_callback:
                progress_callback(idx, total_files, f"解析: {md_file.name}")

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

                    # 解析文档内容
                    # 策略1: 如果有标准的 "## 问题" 和 "## 解决方案" 格式，优先使用
                    problem_match = re.search(r'## 问题\s*\n+(.*?)(?=\n##|\Z)', body, re.DOTALL)
                    solution_match = re.search(r'## 解决[方法办]*\s*\n+(.*)', body, re.DOTALL)

                    if problem_match or solution_match:
                        # 标准格式
                        metadata['problem'] = problem_match.group(1).strip() if problem_match else ''
                        metadata['solution'] = solution_match.group(1).strip() if solution_match else ''
                    else:
                        # 策略2: 通用文档格式
                        # problem = 文件名（去掉日期和扩展名）或第一个一级标题
                        # solution = 整个 body（包含所有标题和内容）

                        # 尝试提取第一个一级标题作为 problem
                        first_h1 = re.search(r'^#\s+(.+?)$', body, re.MULTILINE)
                        if first_h1:
                            metadata['problem'] = first_h1.group(1).strip()
                        else:
                            # 从文件名提取（去掉日期时间前缀）
                            filename = md_file.stem
                            problem_from_filename = re.sub(r'^\d{4}[/-]\d{2}[/-]\d{2}[_-]\d{2}[-:]\d{2}[-:]\d{2}[_-]?', '', filename)
                            metadata['problem'] = problem_from_filename if problem_from_filename else filename

                        # solution 包含整个文档内容
                        metadata['solution'] = body.strip()

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
        total_docs = len(documents)
        print(f"Syncing {total_docs} existing documents...")

        if progress_callback:
            progress_callback(0, total_docs, f"开始索引 {total_docs} 个文档...")

        # 批量索引但提供进度反馈
        doc_ids = []
        for idx, doc in enumerate(documents, 1):
            try:
                # 批量索引时不立即保存，也不生成 N-gram 向量（最后统一生成）
                doc_id = await indexer.index_document(doc, save_index=False, generate_ngram_vectors=False)
                doc_ids.append(doc_id)

                if progress_callback:
                    progress_callback(idx, total_docs, f"索引: {doc['path']}")

                if idx % 5 == 0:
                    print(f"  Indexed {idx}/{total_docs} documents...")
            except Exception as e:
                print(f"Failed to index {doc.get('path')}: {e}")

        # 批量生成所有 N-gram 向量（去重后统一生成）
        if progress_callback:
            progress_callback(total_docs, total_docs, "批量生成 N-gram 向量...")

        print("Batch generating N-gram vectors...")
        await indexer.batch_generate_all_ngram_vectors()

        # 最后统一保存FAISS索引
        print("Saving FAISS index...")
        indexer._save_index()
        print("Sync completed")

        if progress_callback:
            progress_callback(total_docs, total_docs, "索引完成！")


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
    await ensure_initialized()
    stats = indexer.get_stats()
    return stats


@app.post("/record")
async def record_lesson(req: RecordLessonRequest):
    """记录新的经验教训"""
    await ensure_initialized()

    import uuid
    from datetime import datetime

    # 生成文件路径
    now = datetime.now()
    date_str = now.strftime("%Y/%m")  # 例如：2026/01
    timestamp = now.strftime("%d_%H-%M-%S")  # 例如：28_12-21-49
    slug = req.problem[:30].replace(' ', '-').replace('/', '-').replace('\\', '-')
    filename = f"{timestamp}_{slug}.md"
    relative_path = f"{date_str}/{filename}"

    # 创建目录
    file_path = RECORDS_DIR / date_str
    file_path.mkdir(parents=True, exist_ok=True)

    # 写入Markdown文件
    full_file_path = file_path / filename
    markdown_content = f"""---
role: {req.role}
project: {req.project or ''}
directory: {req.directory or ''}
timestamp: {now.isoformat()}
tags: [{', '.join(req.tags)}]
---

## 问题

{req.problem}

## 解决方法

{req.solution}
"""

    full_file_path.write_text(markdown_content, encoding='utf-8')

    document = {
        'path': relative_path,
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
        "path": relative_path,
        "full_path": str(full_file_path)
    }


@app.post("/search")
async def search_lessons(req: SearchRequest):
    """搜索经验教训"""
    await ensure_initialized()

    import time
    start_time = time.time()

    results = await search_engine.search(req.query, {
        'limit': req.limit,
        'min_score': req.min_score,
        'use_vector': req.use_vector,
        'filter_tags': req.filter_tags,
        'filter_project': req.filter_project
    })

    search_time_ms = (time.time() - start_time) * 1000

    # 记录查询日志
    top_score = None
    if results and len(results) > 0:
        top_score = results[0].get('score', None)

    query_logger.log_query(
        query=req.query,
        result_count=len(results),
        search_time_ms=search_time_ms,
        options={
            'limit': req.limit,
            'min_score': req.min_score,
            'use_vector': req.use_vector
        },
        top_score=top_score
    )

    return {
        "query": req.query,
        "count": len(results),
        "results": results
    }


@app.post("/search/tag")
async def search_by_tag(req: TagSearchRequest):
    """按标签搜索"""
    await ensure_initialized()
    results = search_engine.search_by_tag(req.tag, req.limit)

    return {
        "tag": req.tag,
        "count": len(results),
        "results": results
    }


@app.post("/recent")
async def list_recent(req: RecentRequest):
    """获取最近的记录"""
    await ensure_initialized()
    results = search_engine.get_recent(req.limit)

    return {
        "count": len(results),
        "results": results
    }


@app.get("/tags")
async def list_tags():
    """列出所有标签"""
    await ensure_initialized()
    cursor = indexer.conn.execute(
        'SELECT DISTINCT tag FROM document_tags ORDER BY tag'
    )
    tags = [row[0] for row in cursor.fetchall()]

    return {
        "count": len(tags),
        "tags": tags
    }


# ============================================================================
# 查询日志相关端点
# ============================================================================

@app.get("/queries/recent")
async def get_recent_queries(limit: int = 100):
    """获取最近的查询记录"""
    queries = query_logger.get_recent_queries(limit)
    return {
        "count": len(queries),
        "queries": queries
    }


@app.get("/queries/stats")
async def get_query_stats():
    """获取查询统计信息"""
    return query_logger.get_stats()


@app.get("/queries/export")
async def export_queries():
    """导出所有唯一查询（用于性能测试）"""
    queries = query_logger.export_queries()
    return {
        "count": len(queries),
        "queries": queries
    }


@app.post("/queries/clear")
async def clear_query_log():
    """清空查询日志"""
    query_logger.clear_log()
    return {"success": True, "message": "Query log cleared"}


@app.post("/rebuild")
async def rebuild_index():
    """重建索引（异步启动，返回立即）"""
    global rebuild_progress

    await ensure_initialized()

    if rebuild_progress["in_progress"]:
        return {
            "success": False,
            "error": "重建索引正在进行中，请稍后再试"
        }

    # 启动后台任务
    import asyncio
    asyncio.create_task(rebuild_index_task())

    return {
        "success": True,
        "message": "重建索引已启动，请查询 /rebuild/progress 获取进度"
    }


async def rebuild_index_task():
    """后台重建索引任务"""
    global rebuild_progress

    try:
        rebuild_progress["in_progress"] = True
        rebuild_progress["current"] = 0
        rebuild_progress["total"] = 0
        rebuild_progress["message"] = "开始重建索引..."
        rebuild_progress["phase"] = "preparing"

        def progress_callback(current, total, message):
            rebuild_progress["current"] = current
            rebuild_progress["total"] = total
            rebuild_progress["message"] = message
            if current <= total and total > 0:
                if current == 0:
                    rebuild_progress["phase"] = "scanning"
                elif message.startswith("索引"):
                    rebuild_progress["phase"] = "indexing"

        indexer.clear_all()
        await sync_existing_documents(progress_callback)

        stats = indexer.get_stats()
        rebuild_progress["message"] = f"完成！索引了 {stats['documents']} 个文档"
        rebuild_progress["phase"] = "completed"

    except Exception as e:
        rebuild_progress["message"] = f"错误: {str(e)}"
        rebuild_progress["phase"] = "error"
        print(f"Rebuild error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 3秒后重置状态
        import asyncio
        await asyncio.sleep(3)
        rebuild_progress["in_progress"] = False


@app.get("/rebuild/progress")
async def get_rebuild_progress():
    """获取重建进度"""
    return rebuild_progress


# ============================================================================
# 调试接口
# ============================================================================

@app.get("/debug/vectors")
async def debug_vectors():
    """获取所有向量的详细信息"""
    await ensure_initialized()
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
        # 获取向量（使用缓存避免崩溃）
        vec = indexer.get_vector(faiss_idx)

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
    await ensure_initialized()
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
    await ensure_initialized()
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
    await ensure_initialized()
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


class VectorSearchRequest(BaseModel):
    query: str
    top_k: int = 20


class DebugSearchRequest(BaseModel):
    query: str
    limit: int = 10
    min_score: float = 0.0


@app.post("/debug/search-full")
async def debug_search_full(req: DebugSearchRequest):
    """
    完整的调试搜索，包含 n-gram 匹配详情
    """
    await ensure_initialized()
    try:
        results = await search_engine.search(req.query, {
            'limit': req.limit,
            'min_score': req.min_score,
            'use_vector': True
        })

        return {
            "query": req.query,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "query": req.query,
            "results": []
        }


@app.post("/debug/vector-similarity")
async def debug_vector_similarity(req: VectorSearchRequest):
    """
    根据查询问题，显示所有向量的相似度排序
    用于调试向量检索效果
    """
    await ensure_initialized()
    import numpy as np
    import time

    if not indexer.index or indexer.index.ntotal == 0:
        return {
            "error": "FAISS 索引为空",
            "query": req.query,
            "results": []
        }

    try:
        # 1. 生成查询向量
        start = time.time()
        query_embedding = await search_engine.embedding_client.embed_text(req.query)
        embed_time = (time.time() - start) * 1000

        # 归一化
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        query_embedding = query_embedding.reshape(1, -1)

        # 2. 计算所有文档的相似度
        results = []

        # 反向映射：faiss_index -> doc_id
        index_to_doc = {v: k for k, v in indexer.doc_id_to_index.items()}

        for faiss_idx in range(indexer.index.ntotal):
            # 获取文档向量（使用缓存避免崩溃）
            doc_vector = indexer.get_vector(faiss_idx)
            doc_vector = doc_vector.reshape(1, -1)

            # 计算余弦相似度
            similarity = float(np.dot(query_embedding, doc_vector.T)[0][0])

            # 获取文档信息
            doc_id = index_to_doc.get(faiss_idx)
            if doc_id:
                cursor = indexer.conn.execute('''
                    SELECT path, role, project, problem, solution
                    FROM documents
                    WHERE id = ?
                ''', (doc_id,))
                row = cursor.fetchone()

                if row:
                    # 获取标签
                    tag_cursor = indexer.conn.execute(
                        'SELECT tag FROM document_tags WHERE doc_id = ?',
                        (doc_id,)
                    )
                    tags = [t[0] for t in tag_cursor.fetchall()]

                    results.append({
                        "faiss_index": faiss_idx,
                        "doc_id": doc_id,
                        "similarity": round(similarity, 4),
                        "path": row[0],
                        "role": row[1],
                        "project": row[2] or '-',
                        "tags": tags,
                        "problem_preview": row[3][:200] if row[3] else '-',
                        "solution_preview": row[4][:200] if row[4] else '-',
                        "vector_norm": float(np.linalg.norm(doc_vector))
                    })

        # 3. 按相似度排序
        results.sort(key=lambda x: x['similarity'], reverse=True)

        # 4. 限制返回数量
        results = results[:req.top_k]

        search_time = (time.time() - start) * 1000

        return {
            "query": req.query,
            "query_embedding_norm": float(norm),
            "embed_time_ms": round(embed_time, 2),
            "search_time_ms": round(search_time, 2),
            "total_documents": indexer.index.ntotal,
            "returned_count": len(results),
            "results": results
        }

    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "query": req.query,
            "results": []
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
