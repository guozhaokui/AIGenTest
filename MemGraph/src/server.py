"""
FastAPI 服务端
提供知识图谱搜索的HTTP接口
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
from pathlib import Path
import shutil
import numpy as np

from .config import SERVICE_PORT, SERVICE_HOST, RECORDS_DIR, BASE_DIR
from .knowledge_indexer import KnowledgeIndexer
from .activation_search import ActivationSearch
from .query_logger import QueryLogger
from .graph_expander import GraphExpander


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
graph_expander: Optional[GraphExpander] = None
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
    global indexer, search_engine, graph_expander, _initialized

    if _initialized:
        return

    try:
        print("Lazy initializing MemGraph...")

        indexer = KnowledgeIndexer()
        search_engine = ActivationSearch(indexer)
        graph_expander = GraphExpander(indexer, search_engine)

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


class UpdateLessonRequest(BaseModel):
    doc_id: int
    role: Optional[str] = None
    project: Optional[str] = None
    directory: Optional[str] = None
    problem: Optional[str] = None
    solution: str
    tags: Optional[List[str]] = None


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
            body = content

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

            # 解析文档内容（无论是否有 frontmatter）
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

    # 清理文件名中的非法字符（Windows: \ / : * ? " < > |）
    slug = req.problem[:30]
    for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        slug = slug.replace(char, '-')
    slug = slug.replace(' ', '-')

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

    # 立即返回响应，然后在后台异步索引
    import asyncio

    # 创建后台任务进行索引
    async def background_index():
        try:
            await indexer.index_document_smart(document)
        except Exception as e:
            print(f"后台索引失败: {e}")

    # 启动后台任务（不等待完成）
    asyncio.create_task(background_index())

    return {
        "success": True,
        "doc_id": 0,  # 后台索引，暂时返回0
        "action": "indexing",  # 表示正在后台索引
        "message": "文档已保存，正在后台索引",
        "path": relative_path,
        "full_path": str(full_file_path)
    }


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """上传文件并自动加上meta数据（时间戳）"""
    await ensure_initialized()

    from datetime import datetime
    import os

    # 验证文件
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    # 生成保存路径
    now = datetime.now()
    date_str = now.strftime("%Y/%m")  # 例如：2026/01

    # 创建 uploads 子目录
    upload_dir = RECORDS_DIR / "uploads" / date_str
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 生成文件名（添加时间戳前缀避免重名）
    timestamp_prefix = now.strftime("%d_%H-%M-%S")
    original_filename = file.filename
    safe_filename = f"{timestamp_prefix}_{original_filename}"

    file_path = upload_dir / safe_filename
    relative_path = f"uploads/{date_str}/{safe_filename}"

    # 保存文件
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")
    finally:
        await file.close()

    # 读取文件内容（如果是文本文件）
    file_content = ""
    file_ext = os.path.splitext(original_filename)[1].lower()

    # 支持的文本文件扩展名
    text_extensions = ['.txt', '.md', '.py', '.js', '.json', '.csv', '.xml', '.html', '.css', '.yaml', '.yml', '.log']

    if file_ext in text_extensions:
        try:
            file_content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"Warning: Failed to read file content: {e}")
            file_content = f"[无法读取文件内容: {str(e)}]"
    else:
        file_content = f"[二进制文件: {file_ext}]"

    # 创建文档记录
    document = {
        'path': relative_path,
        'role': 'AI',
        'project': '',
        'directory': str(upload_dir),
        'timestamp': now.isoformat(),
        'tags': ['上传文件', file_ext.lstrip('.')],
        'problem': f"上传文件: {original_filename}",
        'solution': file_content
    }

    # 使用智能索引（自动去重和更新检测）
    result = await indexer.index_document_smart(document)

    return {
        "success": True,
        "doc_id": result['doc_id'],
        "action": result['action'],  # 'added', 'updated', 或 'skipped'
        "message": result['message'],
        "path": relative_path,
        "full_path": str(file_path),
        "filename": original_filename,
        "size": file_path.stat().st_size,
        "timestamp": now.isoformat(),
        "file_type": file_ext
    }


@app.post("/update")
async def update_lesson(req: UpdateLessonRequest):
    """更新已有文档并重新索引"""
    await ensure_initialized()

    from datetime import datetime

    # 获取原文档信息
    cursor = indexer.conn.execute(
        'SELECT path, role, project, directory, timestamp FROM documents WHERE id = ?',
        (req.doc_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Document {req.doc_id} not found")

    old_path, old_role, old_project, old_directory, old_timestamp = row

    # 合并新旧值 (保留旧值如果新值未提供)
    role = req.role if req.role is not None else old_role
    project = req.project if req.project is not None else old_project
    directory = req.directory if req.directory is not None else old_directory
    problem = req.problem if req.problem is not None else ""
    tags = req.tags if req.tags is not None else []

    # 使用原路径更新文件
    full_file_path = RECORDS_DIR / old_path

    # 生成新的Markdown内容
    markdown_content = f"""---
role: {role}
project: {project or ''}
directory: {directory or ''}
timestamp: {old_timestamp}
tags: [{', '.join(tags)}]
---

## 问题

{problem}

## 解决方法

{req.solution}
"""

    # 写入文件
    full_file_path.write_text(markdown_content, encoding='utf-8')

    # 更新文档索引
    document = {
        'path': old_path,
        'role': role,
        'project': project or '',
        'directory': directory or '',
        'timestamp': old_timestamp,
        'tags': tags,
        'problem': problem,
        'solution': req.solution
    }

    # 重新索引文档 (会自动删除旧的向量和N-gram)
    await indexer.reindex_document(req.doc_id, document)

    return {
        "success": True,
        "doc_id": req.doc_id,
        "path": old_path,
        "full_path": str(full_file_path)
    }


@app.delete("/document/{doc_id}")
async def delete_document(doc_id: int):
    """删除文档（包括文件、数据库记录和向量）"""
    await ensure_initialized()

    import os

    # 1. 获取文档信息
    cursor = indexer.conn.execute(
        'SELECT path, problem FROM documents WHERE id = ?',
        (doc_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    doc_path, problem = row

    # 2. 删除物理文件（如果存在）
    full_file_path = RECORDS_DIR / doc_path
    file_deleted = False
    if full_file_path.exists():
        try:
            full_file_path.unlink()
            file_deleted = True
            print(f"✓ 删除文件: {full_file_path}")
        except Exception as e:
            print(f"⚠️  删除文件失败: {e}")

    # 3. 从 FAISS 映射中删除
    if doc_id in indexer.doc_id_to_index:
        old_faiss_idx = indexer.doc_id_to_index[doc_id]
        del indexer.doc_id_to_index[doc_id]
        del indexer.index_to_doc_id[old_faiss_idx]
        print(f"✓ 删除 FAISS 映射 (idx={old_faiss_idx})")

    # 4. 删除数据库记录
    cursor1 = indexer.conn.execute('DELETE FROM document_vectors WHERE doc_id = ?', (doc_id,))
    deleted_vectors = cursor1.rowcount

    cursor2 = indexer.conn.execute('DELETE FROM ngrams WHERE doc_id = ?', (doc_id,))
    deleted_ngrams = cursor2.rowcount

    cursor3 = indexer.conn.execute('DELETE FROM document_tags WHERE doc_id = ?', (doc_id,))
    deleted_tags = cursor3.rowcount

    indexer.conn.execute('DELETE FROM documents WHERE id = ?', (doc_id,))

    indexer.conn.commit()
    print(f"✓ 删除数据库记录 (向量:{deleted_vectors}, ngrams:{deleted_ngrams}, 标签:{deleted_tags})")

    # 5. 保存更新后的索引
    indexer._save_index()

    return {
        "success": True,
        "doc_id": doc_id,
        "problem": problem[:50] + "..." if len(problem) > 50 else problem,
        "file_deleted": file_deleted,
        "stats": {
            "vectors": deleted_vectors,
            "ngrams": deleted_ngrams,
            "tags": deleted_tags
        }
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

    # 为每个结果添加细粒度匹配信息
    query_vector = None
    try:
        import asyncio
        # 设置10秒超时，避免长时间等待嵌入服务
        query_vector = await asyncio.wait_for(
            indexer.embedding_client.embed_text(req.query),
            timeout=10.0
        )
        # 归一化查询向量
        norm = np.linalg.norm(query_vector)
        if norm > 0:
            query_vector = query_vector / norm
        print(f"✓ Generated query embedding for fine-grained matching")
    except asyncio.TimeoutError:
        print(f"⚠️ Query embedding timeout (10s), skipping fine-grained matching")
    except Exception as e:
        print(f"⚠️ Failed to generate query embedding: {e}, skipping fine-grained matching")

    if query_vector is not None:
        for result in results:
            doc_id = result.get('doc_id')
            if doc_id:
                # 获取文档的所有向量片段
                cursor = indexer.conn.execute('''
                    SELECT content, granularity, faiss_idx
                    FROM document_vectors
                    WHERE doc_id = ? AND granularity IN ('paragraph', 'sentence')
                    ORDER BY position
                ''', (doc_id,))

                segments = []
                for row in cursor.fetchall():
                    content, granularity, faiss_idx = row
                    if faiss_idx is not None:
                        try:
                            seg_vector = indexer.get_vector(faiss_idx)
                            if seg_vector is not None:
                                # 计算相似度
                                similarity = float(np.dot(query_vector, seg_vector) /
                                                 (np.linalg.norm(query_vector) * np.linalg.norm(seg_vector)))
                                segments.append({
                                    'content': content,
                                    'granularity': granularity,
                                    'similarity': similarity
                                })
                        except:
                            pass

                # 按相似度排序
                segments.sort(key=lambda x: x['similarity'], reverse=True)
                result['segments'] = segments[:10]  # 最多返回10个最相似的片段

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
        "results": results,
        "search_time_ms": search_time_ms
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

        # 不清空索引，利用hash机制增量更新
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
# 图扩展接口
# ============================================================================

class GraphSearchRequest(BaseModel):
    query: str
    initial_k: int = 5
    expand_layers: int = 0
    nodes_per_layer: int = 3


class NodeExpandRequest(BaseModel):
    doc_id: int
    top_k: int = 5
    min_similarity: float = 0.7  # 最小相似度阈值，默认70%


class EdgeDetailsRequest(BaseModel):
    doc_id1: int
    doc_id2: int
    top_k: int = 10


class NodeRelationsRequest(BaseModel):
    doc_id: int
    top_k_per_vector: int = 3
    min_similarity: float = 0.3


@app.post("/graph/search")
async def graph_search(req: GraphSearchRequest):
    """搜索并动态扩展图节点

    Args:
        query: 搜索查询
        initial_k: 初始返回的主节点数
        expand_layers: 扩展层数（0=不扩展，1=扩展1层，2=扩展2层）
        nodes_per_layer: 每层扩展的节点数

    Returns:
        {
            "layer0": [主节点列表],
            "layer1": [第1层关联节点],
            "layer2": [第2层关联节点],
            ...
        }
    """
    await ensure_initialized()

    try:
        result = await graph_expander.search_and_expand(
            query=req.query,
            initial_k=req.initial_k,
            expand_layers=req.expand_layers,
            nodes_per_layer=req.nodes_per_layer
        )

        return {
            "success": True,
            "query": req.query,
            "layers": result
        }
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.post("/graph/expand")
async def expand_node(req: NodeExpandRequest):
    """从指定节点扩展一层关联节点

    Args:
        doc_id: 文档ID
        top_k: 返回的关联节点数
        min_similarity: 最小相似度阈值（0-1之间，默认0.7即70%）

    Returns:
        关联节点列表
    """
    await ensure_initialized()

    try:
        # 获取节点信息
        node_info = graph_expander.get_document_info(req.doc_id)
        if not node_info:
            raise HTTPException(status_code=404, detail=f"Document {req.doc_id} not found")

        # 扩展节点（使用相似度阈值）
        related_nodes = graph_expander.expand_from_node(
            req.doc_id,
            req.top_k,
            req.min_similarity
        )

        return {
            "success": True,
            "node": node_info,
            "related_nodes": related_nodes,
            "count": len(related_nodes),
            "min_similarity": req.min_similarity  # 返回使用的阈值
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


@app.get("/graph/node/{doc_id}")
async def get_node_info(doc_id: int):
    """获取节点详细信息

    Args:
        doc_id: 文档ID

    Returns:
        节点详细信息
    """
    await ensure_initialized()

    node_info = graph_expander.get_document_info(doc_id)
    if not node_info:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    # 获取文档的向量数量
    vectors = graph_expander.get_document_vectors(doc_id)
    node_info['vector_count'] = len(vectors)

    return {
        "success": True,
        "node": node_info
    }


@app.post("/graph/node-relations")
async def get_node_relations(req: NodeRelationsRequest):
    """从一个节点出发，发现所有关联节点及其详细匹配信息

    这是核心接口：
    1. 遍历源节点的所有子向量
    2. 对每个子向量搜索相似向量
    3. 反向查找相似向量属于哪些文档
    4. 返回所有关联节点及其匹配详情

    Args:
        doc_id: 源文档ID
        top_k_per_vector: 每个子向量最多返回多少个相似向量
        min_similarity: 最小相似度阈值

    Returns:
        {
            "success": true,
            "doc_id": 源文档ID,
            "relations": {
                "123": [  // 目标文档ID
                    {
                        "source_vec_content": "源向量内容",
                        "source_vec_granularity": "paragraph",
                        "target_vec_content": "目标向量内容",
                        "target_vec_granularity": "sentence",
                        "similarity": 0.89
                    },
                    ...
                ],
                ...
            },
            "related_count": 关联节点数量
        }
    """
    await ensure_initialized()

    try:
        relations = graph_expander.get_node_relations(
            req.doc_id,
            req.top_k_per_vector,
            req.min_similarity
        )

        # 获取关联节点的基本信息
        related_nodes = {}
        for target_doc_id in relations.keys():
            doc_info = graph_expander.get_document_info(target_doc_id)
            if doc_info:
                related_nodes[target_doc_id] = {
                    'doc_id': target_doc_id,
                    'problem': doc_info.get('problem', ''),
                    'path': doc_info.get('path', ''),
                    'tags': doc_info.get('tags', ''),
                    'match_count': len(relations[target_doc_id])
                }

        return {
            "success": True,
            "doc_id": req.doc_id,
            "relations": relations,
            "related_nodes": related_nodes,
            "related_count": len(relations)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/graph/edge-details")
async def get_edge_details(req: EdgeDetailsRequest):
    """获取两个节点之间的详细向量匹配信息（兼容旧接口）

    Args:
        doc_id1: 第一个文档ID
        doc_id2: 第二个文档ID
        top_k: 返回最多多少对匹配向量

    Returns:
        匹配向量对列表
    """
    await ensure_initialized()

    try:
        matches = graph_expander.get_edge_details(req.doc_id1, req.doc_id2, req.top_k)

        return {
            "success": True,
            "doc_id1": req.doc_id1,
            "doc_id2": req.doc_id2,
            "matches": matches,
            "count": len(matches)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
