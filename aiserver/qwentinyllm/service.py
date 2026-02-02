"""
FastAPI 服务
提供 RESTful API 接口用于文本判断
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import List, Optional
from pathlib import Path
import uvicorn
import asyncio
from contextlib import asynccontextmanager

import config
from model_loader import get_model_loader
from judge_engine import get_judge_engine


# ==================== 数据模型 ====================

class MeaninglessRequest(BaseModel):
    text: str = Field(..., description="待判断的文本")


class MeaninglessResponse(BaseModel):
    is_meaningless: bool
    confidence: float
    reason: str


class SimilarityRequest(BaseModel):
    text1: str = Field(..., description="句子1")
    text2: str = Field(..., description="句子2")


class SimilarityResponse(BaseModel):
    is_similar: bool
    similarity_score: float
    can_merge: bool
    reason: str


class ImportanceRequest(BaseModel):
    ngram: str = Field(..., description="N-gram 文本")
    context: Optional[str] = Field("", description="上下文（可选）")


class ImportanceResponse(BaseModel):
    importance_score: float
    should_vectorize: bool
    category: str
    reason: str


class QualityRequest(BaseModel):
    text: str = Field(..., description="待评估的文本")


class QualityResponse(BaseModel):
    quality_score: float
    information_density: float
    completeness: float
    retrieval_value: float
    should_index: bool
    reason: str


class BatchRequest(BaseModel):
    task: str = Field(..., description="任务类型: meaningless")
    texts: List[str] = Field(..., description="文本列表")


class BatchResponse(BaseModel):
    results: List[dict]


class ModelInfo(BaseModel):
    status: str
    model_name: Optional[str] = None
    precision: Optional[str] = None
    device: Optional[str] = None
    gpu_name: Optional[str] = None
    gpu_memory_allocated: Optional[str] = None
    gpu_memory_total: Optional[str] = None


# ==================== 应用初始化 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    print("🚀 启动 Qwen3 Tiny LLM 服务...")
    print(f"📍 服务地址: http://{config.HOST}:{config.PORT}")

    # 加载模型
    print("⏳ 正在加载模型...")
    model_loader = get_model_loader()
    await asyncio.get_event_loop().run_in_executor(None, model_loader.load_model)

    # 初始化判断引擎
    print("⏳ 正在初始化判断引擎...")
    judge_engine = get_judge_engine()

    print("✅ 服务启动完成！")

    yield

    print("👋 服务关闭")


app = FastAPI(
    title="Qwen3 Tiny LLM 服务",
    description="基于 Qwen3-0.6B 的轻量级 LLM 推理服务，用于知识库文本判断",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """根路径 - 重定向到测试页面"""
    return FileResponse(str(static_dir / "test.html"))

@app.get("/api")
async def api_info():
    """API信息"""
    return {
        "service": "Qwen3 Tiny LLM",
        "version": "1.0.0",
        "model": config.MODEL_NAME,
        "endpoints": [
            "/health",
            "/info",
            "/api/judge/meaningless",
            "/api/judge/similarity",
            "/api/judge/importance",
            "/api/judge/quality",
            "/api/judge/batch"
        ]
    }


@app.get("/health")
async def health():
    """健康检查"""
    model_loader = get_model_loader()
    if model_loader.model is None:
        return {"status": "loading"}
    return {"status": "ok"}


@app.get("/info", response_model=ModelInfo)
async def info():
    """获取模型信息"""
    model_loader = get_model_loader()
    return model_loader.get_model_info()


@app.post("/api/judge/meaningless", response_model=MeaninglessResponse)
async def judge_meaningless(request: MeaninglessRequest):
    """
    判断文本是否无意义

    适用场景：
    - 过滤 N-gram 中的纯停用词组合
    - 去除无语义价值的短语
    """
    try:
        judge_engine = get_judge_engine()
        result = await asyncio.get_event_loop().run_in_executor(
            None, judge_engine.judge_meaningless, request.text
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/judge/similarity", response_model=SimilarityResponse)
async def judge_similarity(request: SimilarityRequest):
    """
    判断两个句子是否相似

    适用场景：
    - 向量去重前的语义判断
    - 合并表述略有差异但语义相同的文本
    """
    try:
        judge_engine = get_judge_engine()
        result = await asyncio.get_event_loop().run_in_executor(
            None, judge_engine.judge_similarity, request.text1, request.text2
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/judge/importance", response_model=ImportanceResponse)
async def judge_importance(request: ImportanceRequest):
    """
    判断 N-gram 的重要性

    适用场景：
    - 决定是否为某个 N-gram 生成向量
    - 评估关键词的检索价值
    """
    try:
        judge_engine = get_judge_engine()
        result = await asyncio.get_event_loop().run_in_executor(
            None, judge_engine.judge_importance, request.ngram, request.context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/judge/quality", response_model=QualityResponse)
async def judge_quality(request: QualityRequest):
    """
    评估文本质量

    适用场景：
    - 决定是否索引某段文本
    - 评估文本的信息量和检索价值
    """
    try:
        judge_engine = get_judge_engine()
        result = await asyncio.get_event_loop().run_in_executor(
            None, judge_engine.judge_quality, request.text
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/judge/batch", response_model=BatchResponse)
async def judge_batch(request: BatchRequest):
    """
    批量判断

    适用场景：
    - 批量过滤无意义短语
    - 提高处理效率

    支持的任务类型：
    - meaningless: 批量判断是否无意义
    """
    try:
        if request.task != "meaningless":
            raise HTTPException(
                status_code=400,
                detail=f"不支持的任务类型: {request.task}"
            )

        if len(request.texts) > config.MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"批量大小超过限制: {len(request.texts)} > {config.MAX_BATCH_SIZE}"
            )

        judge_engine = get_judge_engine()
        results = await asyncio.get_event_loop().run_in_executor(
            None, judge_engine.batch_judge_meaningless, request.texts
        )

        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 启动服务 ====================

if __name__ == "__main__":
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  Qwen3 Tiny LLM 服务                         ║
╠══════════════════════════════════════════════════════════════╣
║  模型: {config.MODEL_NAME:<50} ║
║  精度: {config.PRECISION:<50} ║
║  设备: {config.DEVICE:<50} ║
║  地址: http://{config.HOST}:{config.PORT:<43} ║
╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        workers=config.WORKERS,
        log_level="info"
    )
