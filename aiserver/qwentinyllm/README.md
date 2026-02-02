# Qwen3 Tiny LLM 服务

基于 Qwen3-0.6B 的轻量级 LLM 推理服务，专门用于知识库的文本判断任务。

## 功能

1. **无意义短语判断**: 判断 N-gram 是否有语义价值
2. **相似句子判断**: 判断两个句子是否语义相似
3. **文本质量评估**: 评估文本的信息量和重要性
4. **N-gram 重要性评分**: 为 N-gram 打分，用于向量生成筛选

## 特点

- 🚀 **轻量级**: 基于 0.6B 参数模型，显存占用 < 2GB
- ⚡ **快速**: GTX 1660 Super 推理速度 ~20-30 tokens/秒
- 🎯 **专用**: 针对知识库场景优化的 prompt
- 🔧 **易用**: RESTful API，支持批量处理

## 硬件要求

- **最低**: GTX 1660 Super (6GB 显存)
- **推荐**: RTX 3060 (12GB 显存) 或更高
- **CPU**: 4 核心以上
- **内存**: 8GB 以上

## 安装

```bash
cd D:\work\AIGenTest\aiserver\qwentinyllm

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 配置

编辑 `config.py` 设置：

```python
# 模型配置
MODEL_NAME = "Qwen/Qwen3-0.6B"  # 或使用 ModelScope 路径
USE_MODELSCOPE = True  # 是否从 ModelScope 下载

# 服务配置
HOST = "0.0.0.0"
PORT = 6015

# 推理配置
DEVICE = "cuda"  # cuda 或 cpu
PRECISION = "fp16"  # fp16, int8, int4
MAX_LENGTH = 512
TEMPERATURE = 0.3
```

## 启动服务

```bash
python service.py
```

服务将在 `http://localhost:6015` 启动。

## API 使用

### 1. 健康检查

```bash
curl http://localhost:6015/health
```

### 2. 判断无意义短语

```bash
curl -X POST http://localhost:6015/api/judge/meaningless \
  -H "Content-Type: application/json" \
  -d '{
    "text": "的 是 在"
  }'

# 响应
{
  "is_meaningless": true,
  "confidence": 0.95,
  "reason": "通用停用词组合，无实际语义"
}
```

### 3. 判断句子相似度

```bash
curl -X POST http://localhost:6015/api/judge/similarity \
  -H "Content-Type: application/json" \
  -d '{
    "text1": "FAISS 是一个向量数据库",
    "text2": "FAISS 是向量数据库"
  }'

# 响应
{
  "is_similar": true,
  "similarity_score": 0.92,
  "can_merge": true
}
```

### 4. N-gram 重要性评分

```bash
curl -X POST http://localhost:6015/api/judge/importance \
  -H "Content-Type: application/json" \
  -d '{
    "ngram": "向量数据库",
    "context": "使用 FAISS 向量数据库进行检索"
  }'

# 响应
{
  "importance_score": 0.88,
  "should_vectorize": true,
  "category": "technical_term"
}
```

### 5. 批量判断

```bash
curl -X POST http://localhost:6015/api/judge/batch \
  -H "Content-Type: application/json" \
  -d '{
    "task": "meaningless",
    "texts": ["向量数据库", "的 是", "FAISS 检索", "在 了"]
  }'

# 响应
{
  "results": [
    {"text": "向量数据库", "is_meaningless": false, "score": 0.95},
    {"text": "的 是", "is_meaningless": true, "score": 0.98},
    {"text": "FAISS 检索", "is_meaningless": false, "score": 0.92},
    {"text": "在 了", "is_meaningless": true, "score": 0.96}
  ]
}
```

## 集成到 MemGraph

### 1. 在 N-gram 索引时过滤

```python
# MemGraph/src/knowledge_indexer.py
import httpx

async def should_generate_vector(ngram_text: str) -> bool:
    """使用 Qwen Tiny LLM 判断是否应该生成向量"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:6015/api/judge/importance",
            json={"ngram": ngram_text}
        )
        result = response.json()
        return result["should_vectorize"]
```

### 2. 在向量去重时判断相似度

```python
async def can_merge_vectors(text1: str, text2: str) -> bool:
    """判断两个文本是否可以合并向量"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:6015/api/judge/similarity",
            json={"text1": text1, "text2": text2}
        )
        result = response.json()
        return result["can_merge"]
```

## 性能

### GTX 1660 Super (6GB)

- **加载时间**: ~5-10 秒
- **推理速度**: ~20-30 tokens/秒
- **显存占用**: ~2 GB (FP16)
- **单次判断**: ~100-200ms
- **批量判断**: ~50ms/条 (batch=10)

## 目录结构

```
qwentinyllm/
├── README.md           # 本文档
├── requirements.txt    # Python 依赖
├── config.py          # 配置文件
├── model_loader.py    # 模型加载器
├── judge_engine.py    # 判断引擎
├── service.py         # FastAPI 服务
├── prompts.py         # Prompt 模板
├── test_api.py        # API 测试
└── start_service.sh   # 启动脚本
```

## 注意事项

1. **首次运行**: 会下载模型（~1.2GB），需要时间
2. **显存不足**: 可以使用 INT8 或 INT4 量化
3. **性能优化**: 建议使用批量接口减少开销
4. **Prompt 调优**: 可以修改 `prompts.py` 优化判断效果

## 故障排查

### Q: 模型下载失败

A: 使用 ModelScope 镜像或手动下载：

```bash
# 使用 ModelScope
pip install modelscope
modelscope download --model Qwen/Qwen3-0.6B
```

### Q: 显存不足

A: 使用量化版本：

```python
# config.py
PRECISION = "int8"  # 或 "int4"
```

### Q: 推理速度慢

A: 使用批量接口，或考虑升级显卡
