#!/usr/bin/env python3
"""
知识查询Web服务 (FastAPI版本)

提供API接口：
1. 文档索引
2. 记忆管理
3. 向量检索
4. 智能问答
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv
import openai
from datetime import datetime
import uvicorn
import json

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.vector_store import VectorStore, Document
from core.embedding import create_embedding_provider

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 配置
DOCS_DEFAULT_PATH = "/mnt/e/TEST/work/日志"  # 默认文档路径

# 全局变量
vector_store: Optional[VectorStore] = None
nvidia_client: Optional[openai.OpenAI] = None
current_docs_path: Optional[str] = None


# ==================== 请求/响应模型 ====================

class ScanRequest(BaseModel):
    """扫描文档请求"""
    path: str = DOCS_DEFAULT_PATH


class IndexRequest(BaseModel):
    """索引文档请求"""
    files: List[str]  # 文件路径列表


class QueryRequest(BaseModel):
    """查询问答请求"""
    question: str
    model: str = "deepseek-ai/deepseek-v3.2"
    top_k: int = 3


class DeleteRequest(BaseModel):
    """删除文档请求"""
    source: str  # 文件名


class FileInfo(BaseModel):
    """文件信息"""
    name: str
    path: str
    size: int
    modified: str
    length: int
    indexed: bool = False


class IndexResult(BaseModel):
    """索引结果"""
    file: str
    success: bool
    chunks: Optional[int] = None
    error: Optional[str] = None


class ContextDoc(BaseModel):
    """上下文文档"""
    index: int
    source: str
    content: str
    similarity: float


class QueryResponse(BaseModel):
    """查询响应"""
    question: str
    answer: Optional[str]
    context: List[ContextDoc]
    model: str


class ModelInfo(BaseModel):
    """模型信息"""
    id: str
    name: str
    recommended: bool


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # "user" 或 "assistant"
    content: str


class ChatRequest(BaseModel):
    """纯聊天请求"""
    message: str
    model: str = "deepseek-ai/deepseek-v3.2"
    history: Optional[List[ChatMessage]] = []
    system_prompt: Optional[str] = None


class ChatResponse(BaseModel):
    """聊天响应"""
    message: str
    model: str


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="知识查询服务",
    description="基于向量检索和LLM的智能问答系统",
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


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup_event():
    """初始化服务"""
    global vector_store, nvidia_client

    print("\n" + "=" * 60)
    print("知识查询Web服务 (FastAPI)")
    print("=" * 60)

    # 初始化向量存储
    print("初始化向量存储...")
    vector_store = VectorStore(
        path=".memory_db/web_vectors",
        collection_name="knowledge_base"
    )

    # 初始化NVIDIA API
    print("初始化NVIDIA API...")
    api_key = os.getenv('NVIDIA_API_KEY')
    if api_key:
        nvidia_client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        print("✓ NVIDIA API已初始化")
    else:
        print("⚠️ 未找到NVIDIA_API_KEY")

    print("✓ 服务初始化完成")
    print("=" * 60 + "\n")


# ==================== API 端点 ====================

@app.get("/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "vector_store": vector_store is not None,
        "nvidia_api": nvidia_client is not None,
        "embedding_service": vector_store.embedding.health_check() if vector_store else False
    }


@app.get("/api/knowledge/status")
def get_status():
    """获取系统状态"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="向量存储未初始化")

    return {
        "success": True,
        "data": {
            "vector_store": {
                "total_documents": vector_store.count(),
                "dimension": vector_store.embedding.get_dimension(),
            },
            "nvidia_api": nvidia_client is not None,
            "current_docs_path": current_docs_path,
            "embedding_service": {
                "available": vector_store.embedding.health_check(),
                "type": "BGE-Remote"
            }
        }
    }


@app.post("/api/knowledge/scan")
def scan_documents(request: ScanRequest):
    """扫描文档目录"""
    path = Path(request.path)
    if not path.exists():
        return {
            "success": False,
            "error": f"目录不存在: {request.path}"
        }

    # 扫描markdown文件
    md_files = list(path.glob('*.md'))

    files_info = []
    for md_file in md_files:
        try:
            stat = md_file.stat()
            content = md_file.read_text(encoding='utf-8')

            files_info.append({
                "name": md_file.name,
                "path": str(md_file),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "length": len(content),
                "indexed": False  # TODO: 检查是否已索引
            })
        except Exception as e:
            print(f"读取文件失败 {md_file}: {e}")

    return {
        "success": True,
        "data": {
            "path": request.path,
            "total": len(files_info),
            "files": files_info
        }
    }


@app.post("/api/knowledge/index")
def index_documents(request: IndexRequest):
    """索引文档"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="向量存储未初始化")

    if not request.files:
        return {
            "success": False,
            "error": "未提供文件列表"
        }

    global current_docs_path

    results = []
    total_chunks = 0

    for file_path in request.files:
        try:
            path = Path(file_path)
            if not path.exists():
                results.append({
                    "file": path.name,
                    "success": False,
                    "error": "文件不存在"
                })
                continue

            # 读取文件
            content = path.read_text(encoding='utf-8')

            # 添加到向量存储（自动分块）
            doc_ids = vector_store.add_document(
                content=content,
                metadata={
                    "source": path.name,
                    "path": str(path),
                    "type": "markdown",
                    "indexed_at": datetime.now().isoformat()
                },
                chunk=True
            )

            total_chunks += len(doc_ids)
            current_docs_path = str(path.parent)

            results.append({
                "file": path.name,
                "success": True,
                "chunks": len(doc_ids)
            })

        except Exception as e:
            results.append({
                "file": Path(file_path).name,
                "success": False,
                "error": str(e)
            })

    return {
        "success": True,
        "data": {
            "results": results,
            "total_files": len(request.files),
            "success_count": sum(1 for r in results if r["success"]),
            "total_chunks": total_chunks,
            "total_documents": vector_store.count()
        }
    }


@app.post("/api/knowledge/query")
def query_knowledge(request: QueryRequest):
    """查询知识库"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="向量存储未初始化")

    if not request.question:
        return {
            "success": False,
            "error": "未提供问题"
        }

    try:
        # 1. 向量检索
        results = vector_store.search(request.question, top_k=request.top_k)

        # 构建上下文
        context_docs = []
        for i, result in enumerate(results, 1):
            context_docs.append({
                "index": i,
                "source": result.metadata.get("source", "unknown"),
                "content": result.content,
                "similarity": result.similarity
            })

        # 2. 生成回答（如果配置了NVIDIA API）
        answer = None
        if nvidia_client:
            context = "\n\n".join([
                f"【文档{doc['index']}】来源: {doc['source']}\n{doc['content']}"
                for doc in context_docs
            ])

            prompt = f"""基于以下文档内容回答问题。

【文档内容】
{context}

【用户问题】
{request.question}

【回答要求】
1. 只基于文档内容回答，不要添加文档外的信息
2. 如果文档中没有相关信息，明确说明
3. 回答要简洁明了
4. 标注信息来源（哪个文档）

【回答】"""

            completion = nvidia_client.chat.completions.create(
                model=request.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3
            )

            answer = completion.choices[0].message.content

        return {
            "success": True,
            "data": {
                "question": request.question,
                "answer": answer,
                "context": context_docs,
                "model": request.model
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/models")
def list_models():
    """获取可用的模型列表"""
    models = [
        {"id": "deepseek-ai/deepseek-v3.2", "name": "DeepSeek V3.2", "recommended": True},
        {"id": "deepseek-ai/deepseek-r1-0528", "name": "DeepSeek R1 (推理)", "recommended": True},
        {"id": "moonshotai/kimi-k2-thinking", "name": "Kimi K2 Thinking", "recommended": True},
        {"id": "z-ai/glm4.7", "name": "GLM-4.7", "recommended": True},
        {"id": "minimaxai/minimax-m2.1", "name": "MiniMax M2.1", "recommended": True},
        {"id": "meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "recommended": False},
        {"id": "qwen/qwen3-235b-a22b", "name": "Qwen3 235B", "recommended": False},
        {"id": "meta/llama-3.1-8b-instruct", "name": "Llama 3.1 8B (快速)", "recommended": False},
    ]

    return {
        "success": True,
        "data": models
    }


@app.post("/api/knowledge/chat")
def chat(request: ChatRequest):
    """
    纯聊天接口（不依赖知识库）

    直接调用LLM进行对话，支持多轮对话历史
    """
    if not nvidia_client:
        raise HTTPException(status_code=503, detail="NVIDIA API未配置")

    if not request.message.strip():
        return {
            "success": False,
            "error": "消息不能为空"
        }

    try:
        # 构建消息列表
        messages = []

        # 添加系统提示（如果有）
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })

        # 添加历史对话
        if request.history:
            for msg in request.history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # 添加当前消息
        messages.append({
            "role": "user",
            "content": request.message
        })

        # 调用LLM
        completion = nvidia_client.chat.completions.create(
            model=request.model,
            messages=messages,
            max_tokens=2048,
            temperature=0.7
        )

        answer = completion.choices[0].message.content

        return {
            "success": True,
            "data": {
                "message": answer,
                "model": request.model
            }
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/chat/stream")
def chat_stream(request: ChatRequest):
    """
    流式聊天接口（不依赖知识库）

    使用 Server-Sent Events 实时返回 LLM 生成的内容
    """
    if not nvidia_client:
        raise HTTPException(status_code=503, detail="NVIDIA API未配置")

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    def generate():
        try:
            # 构建消息列表
            messages = []

            # 添加系统提示（如果有）
            if request.system_prompt:
                messages.append({
                    "role": "system",
                    "content": request.system_prompt
                })

            # 添加历史对话
            if request.history:
                for msg in request.history:
                    messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })

            # 添加当前消息
            messages.append({
                "role": "user",
                "content": request.message
            })

            print(f"[Stream] 开始流式生成，模型: {request.model}")

            # 调用LLM流式API
            stream = nvidia_client.chat.completions.create(
                model=request.model,
                messages=messages,
                max_tokens=2048,
                temperature=0.7,
                stream=True  # 启用流式响应
            )

            chunk_count = 0
            # 逐块发送数据
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta

                    # 获取内容
                    content = delta.content if hasattr(delta, 'content') else None

                    # 获取思考内容（从 model_extra 中的 reasoning_content 字段）
                    reasoning = None
                    if hasattr(delta, 'model_extra') and delta.model_extra:
                        reasoning = delta.model_extra.get('reasoning_content')

                    # 发送数据（确保至少有一个不为空）
                    if content or reasoning:
                        chunk_count += 1
                        event_data = {
                            "content": content,
                            "reasoning": reasoning
                        }
                        data_str = f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                        print(f"[Stream] Chunk {chunk_count}: content={bool(content)}, reasoning={bool(reasoning)}")
                        yield data_str

            # 发送完成信号
            print(f"[Stream] 完成，共 {chunk_count} 个chunk")
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = json.dumps({'error': str(e)})
            yield f"data: {error_msg}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
            "Transfer-Encoding": "chunked"
        }
    )


@app.post("/api/knowledge/clear")
def clear_knowledge():
    """清空知识库"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="向量存储未初始化")

    try:
        vector_store.clear()
        global current_docs_path
        current_docs_path = None

        return {
            "success": True,
            "message": "知识库已清空"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/delete")
def delete_documents(request: DeleteRequest):
    """删除指定文档"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="向量存储未初始化")

    if not request.source:
        return {
            "success": False,
            "error": "未提供文件名"
        }

    try:
        # 按元数据删除
        count = vector_store.delete_by_metadata({"source": request.source})

        return {
            "success": True,
            "data": {
                "deleted_count": count,
                "remaining_count": vector_store.count()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/knowledge/stats")
def get_stats():
    """获取统计信息"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="向量存储未初始化")

    stats = vector_store.stats()

    return {
        "success": True,
        "data": stats
    }


# ==================== 主函数 ====================

def main():
    """启动服务"""
    port = int(os.getenv('KNOWLEDGE_API_PORT', 5001))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )


if __name__ == '__main__':
    main()
