# Qwen3 Tiny LLM 服务 - 项目总结

## 项目概述

基于 Qwen3-0.6B 的轻量级 LLM 推理服务，专门用于 MemGraph 知识库的文本判断任务。

## 项目结构

```
qwentinyllm/
├── README.md              # 完整文档（功能、安装、API、集成示例）
├── INSTALL.md            # 快速安装指南
├── PROJECT_SUMMARY.md    # 本文档
├── requirements.txt      # Python 依赖
├── .gitignore           # Git 忽略文件
│
├── config.py            # 配置文件（模型、服务、推理参数）
├── prompts.py           # Prompt 模板（4种判断任务）
├── model_loader.py      # 模型加载器（支持 FP16/INT8/INT4）
├── judge_engine.py      # 判断引擎（核心业务逻辑）
├── service.py           # FastAPI 服务（RESTful API）
│
├── test_api.py          # API 测试脚本
├── start_service.bat    # Windows 启动脚本
└── start_service.sh     # Linux/Mac 启动脚本
```

## 核心功能

### 1. 无意义短语判断 (`/api/judge/meaningless`)
- **用途**: 过滤 N-gram 中的纯停用词组合
- **示例**: "的 是 在" → 无意义 ✓

### 2. 句子相似度判断 (`/api/judge/similarity`)
- **用途**: 向量去重前的语义判断
- **示例**: "FAISS是向量数据库" vs "FAISS是一个向量数据库" → 相似 ✓

### 3. N-gram 重要性评分 (`/api/judge/importance`)
- **用途**: 决定是否为某个 N-gram 生成向量
- **示例**: "向量数据库" → 重要性 0.88，应生成向量 ✓

### 4. 文本质量评估 (`/api/judge/quality`)
- **用途**: 评估文本的信息量和检索价值
- **示例**: "FAISS 是 Facebook AI Research 开发的..." → 质量分 0.85

### 5. 批量判断 (`/api/judge/batch`)
- **用途**: 批量处理，提高效率
- **支持**: 批量无意义短语判断

## 技术特点

### 1. 轻量级设计
- **模型**: Qwen3-0.6B (600M 参数)
- **显存**: < 2GB (FP16)
- **速度**: ~20-30 tokens/秒 (GTX 1660 Super)

### 2. 智能优化
- **快速预过滤**: 使用规则快速处理明显案例
- **JSON 容错解析**: 多种方式解析模型输出
- **降级策略**: 模型失败时使用启发式规则

### 3. 生产就绪
- **异步处理**: FastAPI + asyncio
- **批量支持**: 减少推理开销
- **健康检查**: `/health` 端点
- **CORS**: 支持跨域请求

## 性能指标

### GTX 1660 Super (6GB VRAM)

| 指标 | 数值 |
|------|------|
| 加载时间 | ~5-10 秒 |
| 推理速度 | ~20-30 tokens/秒 |
| 显存占用 | ~2 GB (FP16) |
| 单次判断 | ~100-200ms |
| 批量判断 | ~50ms/条 (batch=10) |

## 集成示例

### 在 MemGraph 中使用

```python
import httpx

# 判断是否应该生成向量
async def should_generate_vector(ngram_text: str) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:6015/api/judge/importance",
            json={"ngram": ngram_text}
        )
        result = response.json()
        return result["should_vectorize"]

# 判断两个文本是否可以合并向量
async def can_merge_vectors(text1: str, text2: str) -> bool:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:6015/api/judge/similarity",
            json={"text1": text1, "text2": text2}
        )
        result = response.json()
        return result["can_merge"]
```

## 快速开始

### 1. 安装

```bash
cd D:\work\AIGenTest\aiserver\qwentinyllm
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 启动

```bash
# Windows
start_service.bat

# Linux/Mac
./start_service.sh

# 或直接运行
python service.py
```

### 3. 测试

```bash
python test_api.py
```

### 4. 使用

```bash
curl -X POST http://localhost:6015/api/judge/meaningless \
  -H "Content-Type: application/json" \
  -d '{"text": "的 是 在"}'
```

## 配置选项

### 模型配置 (`config.py`)

```python
# 模型选择
MODEL_NAME = "Qwen/Qwen3-0.6B"
USE_MODELSCOPE = True  # 使用国内镜像

# 推理配置
DEVICE = "cuda"  # cuda 或 cpu
PRECISION = "fp16"  # fp16, int8, int4

# 生成参数
MAX_LENGTH = 512
TEMPERATURE = 0.3  # 低温度，更确定的输出
TOP_P = 0.9
```

## 判断阈值

```python
# 无意义短语判断
MEANINGLESS_THRESHOLD = 0.7

# 相似度判断
SIMILARITY_THRESHOLD = 0.85

# 重要性评分
IMPORTANCE_THRESHOLD = 0.6
```

## API 端点

| 端点 | 方法 | 功能 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/info` | GET | 模型信息 |
| `/api/judge/meaningless` | POST | 无意义判断 |
| `/api/judge/similarity` | POST | 相似度判断 |
| `/api/judge/importance` | POST | 重要性评分 |
| `/api/judge/quality` | POST | 质量评估 |
| `/api/judge/batch` | POST | 批量判断 |
| `/docs` | GET | API 文档（自动生成） |

## 应用场景

### 1. MemGraph 向量优化
- 过滤无意义 N-gram，减少向量数量
- 合并相似向量，节省存储空间
- 智能选择重要文本生成向量

### 2. 知识库质量控制
- 评估文本质量，过滤低质量内容
- 确保索引的都是有价值的信息

### 3. 批量处理
- 批量过滤无意义短语
- 提高处理效率

## 未来优化方向

1. **模型微调**: 针对特定领域数据微调模型
2. **缓存机制**: 缓存常见判断结果
3. **并发优化**: 支持多请求并发处理
4. **更多任务**: 添加关键词提取、摘要生成等功能

## 性能优化建议

1. **使用批量接口**: 减少网络和模型加载开销
2. **调整 MAX_LENGTH**: 根据实际需求降低最大长度
3. **使用量化**: INT8 或 INT4 降低显存占用
4. **本地部署**: 与 MemGraph 部署在同一台机器

## 故障排查

### 模型加载失败
- 检查网络连接
- 使用 ModelScope 镜像
- 手动下载模型文件

### 显存不足
- 使用 INT8 或 INT4 量化
- 降低 MAX_LENGTH
- 使用 CPU 模式

### 推理速度慢
- 使用批量接口
- 升级显卡
- 降低 MAX_LENGTH

## 联系与支持

- **项目位置**: `D:\work\AIGenTest\aiserver\qwentinyllm`
- **服务端口**: 6015
- **文档**: 查看 `README.md`
- **安装**: 查看 `INSTALL.md`

## 版本历史

- **v1.0.0** (2026-01-31)
  - 初始版本
  - 支持 4 种判断任务
  - 支持 FP16/INT8/INT4 量化
  - 支持批量处理
  - 完整的 API 文档和测试脚本

## 许可证

本项目使用的 Qwen3-0.6B 模型遵循其原始许可证。
