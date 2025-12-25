# 嵌入与重排序服务

本地嵌入和重排序服务，用于图片管理系统的向量索引和检索优化。

## 服务列表

| 服务 | 端口 | 模型 | 用途 | 维度/说明 |
|------|------|------|------|------|
| siglip2_embed.py | 6010 | SigLIP2-so400m-patch16-512 (1.14B) | 图片嵌入 | 1152 |
| qwen3_4b_embed.py | 6011 | Qwen3-4B (ZImage-Turbo) | 文本嵌入（复用语言模型） | 2560 |
| bge_embed.py | 6012 | BGE-Large-zh-v1.5 | 文本嵌入（轻量） | 1024 |
| qwen3_4b_rerank.py | 6013 | Qwen3-4B (ZImage-Turbo) | 重排序（LLM logits） | - |
| **qwen3_8b_embed.py** | **6014** | **Qwen3-Embedding-8B** | **文本嵌入（专用模型）** | **4096** |
| **qwen3_8b_rerank.py** | **6015** | **Qwen3-Reranker-8B** | **重排序（专用模型）** | **-** |

## 模型对比

### 嵌入模型

| 模型 | 参数量 | 维度 | 特点 | 推荐场景 |
|------|--------|------|------|----------|
| BGE-Large-zh | 326M | 1024 | 轻量、中文优化 | 资源受限、中文检索 |
| Qwen3-4B | 4B | 2560 | 复用语言模型 | 已有 4B 模型时 |
| **Qwen3-Embedding-8B** | 8B | 4096 | **专用嵌入模型** | **高精度检索** |

### 重排序模型

| 模型 | 参数量 | 特点 | 推荐场景 |
|------|--------|------|----------|
| Qwen3-4B | 4B | 用 LLM logits 判断 | 已有 4B 模型时 |
| **Qwen3-Reranker-8B** | 8B | **专用重排模型** | **高精度排序** |

## 快速开始

### 下载 8B 模型

```python
from modelscope import snapshot_download

# 下载嵌入模型
snapshot_download(
    'Qwen/Qwen3-Embedding-8B',
    cache_dir='/home/layabox/laya/guo/AIGenTest/aiserver/models/'
)

# 下载重排序模型
snapshot_download(
    'Qwen/Qwen3-Reranker-8B',
    cache_dir='/home/layabox/laya/guo/AIGenTest/aiserver/models/'
)
```

### 启动服务

```bash
# 激活 conda 环境
conda activate hidream

# 8B 嵌入服务
python qwen3_8b_embed.py  # 端口 6014

# 8B 重排序服务
python qwen3_8b_rerank.py  # 端口 6015
```

### 一键启动所有服务

```bash
./start_embed_server.sh
```

## API 接口

### 8B 嵌入服务 (端口 6014)

| 接口 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /embed/text | POST | 单个文本嵌入 |
| /embed/texts | POST | 批量文本嵌入 |

**请求示例：**
```bash
# 单个文本
curl -X POST http://localhost:6014/embed/text \
  -H "Content-Type: application/json" \
  -d '{"text": "一只橙色的猫在阳光下晒太阳"}'

# 带任务指令（提升检索效果）
curl -X POST http://localhost:6014/embed/text \
  -H "Content-Type: application/json" \
  -d '{"text": "橙色猫", "instruction": "Retrieve relevant images"}'
```

### 8B 重排序服务 (端口 6015)

| 接口 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /rerank | POST | 文档重排序 |
| /rerank/score | POST | 单对评分 |

**请求示例：**
```bash
curl -X POST http://localhost:6015/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "橙色的猫",
    "documents": [
      "一只橙色的猫在阳光下晒太阳",
      "黑色的狗在草地上奔跑",
      "可爱的猫咪在睡觉"
    ],
    "top_k": 2
  }'
```

## 显存需求

| 服务 | 模型 | FP16 显存 | INT8 显存 |
|------|------|----------|----------|
| 图片嵌入 | SigLIP2 1.14B | ~3GB | - |
| 文本嵌入 | Qwen3-4B | ~8GB | ~4GB |
| 文本嵌入 | BGE-Large-zh | ~2GB | - |
| 重排序 | Qwen3-4B | ~8GB | ~4GB |
| **文本嵌入** | **Qwen3-Embedding-8B** | **~16GB** | **~8GB** |
| **重排序** | **Qwen3-Reranker-8B** | **~16GB** | **~8GB** |

### 24GB 显存推荐配置

| 配置 | 组合 | 总显存 |
|------|------|--------|
| 高精度 | 8B-Embed(INT8) + 8B-Rerank(INT8) | ~16GB |
| 平衡 | 8B-Embed(INT8) + 4B-Rerank | ~12GB |
| 轻量 | 4B-Embed + 4B-Rerank | ~16GB (共享) |

## 模型路径

| 模型 | 路径 |
|------|------|
| SigLIP2 | `/mnt/hdd/models/siglip2-so400m-patch16-512` |
| Qwen3-4B | `/mnt/hdd/models/Z-Image-Turbo` (复用 text_encoder) |
| BGE-Large-zh | `/mnt/hdd/models/bge-large-zh` |
| **Qwen3-Embedding-8B** | `/home/layabox/laya/guo/AIGenTest/aiserver/models/Qwen3-Embedding-8B` |
| **Qwen3-Reranker-8B** | `/home/layabox/laya/guo/AIGenTest/aiserver/models/Qwen3-Reranker-8B` |

## Python 调用示例

```python
import requests
import numpy as np

# 8B 嵌入服务
def get_embedding_8b(text: str, instruction: str = None) -> np.ndarray:
    payload = {"text": text}
    if instruction:
        payload["instruction"] = instruction
    
    response = requests.post(
        "http://localhost:6014/embed/text",
        json=payload
    )
    return np.array(response.json()["embedding"])

# 8B 重排序服务
def rerank_8b(query: str, documents: list, top_k: int = None) -> list:
    payload = {"query": query, "documents": documents}
    if top_k:
        payload["top_k"] = top_k
    
    response = requests.post(
        "http://localhost:6015/rerank",
        json=payload
    )
    return response.json()["results"]

# 使用示例
embedding = get_embedding_8b("一只可爱的猫")
print(f"嵌入维度: {len(embedding)}")

results = rerank_8b(
    query="橙色猫",
    documents=["橙猫晒太阳", "黑狗跑步", "白猫睡觉"],
    top_k=2
)
for r in results:
    print(f"[{r['original_index']}] {r['score']:.2%} - {r['document']}")
```

## 配置选项

### 量化设置

8B 模型默认启用 INT8 量化以节省显存。如需 FP16 精度：

```python
# 在 qwen3_8b_embed.py 或 qwen3_8b_rerank.py 中修改
USE_QUANTIZATION = False  # 改为 False
```

注意：FP16 需要约 16GB 显存/模型，两个 8B 模型需要 32GB。
