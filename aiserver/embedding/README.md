# 嵌入服务

本地嵌入服务，用于图片管理系统的向量索引。

## 服务列表

| 服务 | 端口 | 模型 | 用途 | 维度 |
|------|------|------|------|------|
| siglip2_embed.py | 6010 | SigLIP2-so400m-patch16-512 (1.14B) | 图片嵌入 | 1152 |
| qwen3_embed.py | 6011 | Qwen3-4B (ZImage-Turbo) | 文本嵌入 | 2560 |

## 模型来源

- **文本嵌入**：复用 ZImage-Turbo 的 text_encoder（Qwen3-4B），使用**倒数第二层**作为嵌入向量
- **图片嵌入**：SigLIP2-so400m-patch16-512 (1.14B 最强版本)

## 快速开始

### 一键启动所有服务

```bash
./start_all.sh
```

### 单独启动

```bash
# 激活 conda 环境
conda activate hidream

# 图片嵌入服务
python siglip2_embed.py

# 文本嵌入服务
python qwen3_embed.py
```

### 停止所有服务

```bash
./stop_all.sh
```

## API 接口

### 图片嵌入服务 (端口 6010)

| 接口 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /embed/image | POST | 上传图片计算嵌入 |
| /embed/image/base64 | POST | Base64 图片计算嵌入 |

### 文本嵌入服务 (端口 6011)

| 接口 | 方法 | 说明 |
|------|------|------|
| /health | GET | 健康检查 |
| /embed/text | POST | 单个文本嵌入 |
| /embed/texts | POST | 批量文本嵌入 |

## 使用示例

### 健康检查

```bash
# 图片嵌入服务
curl http://localhost:6010/health

# 文本嵌入服务
curl http://localhost:6011/health
```

返回示例：
```json
{
  "status": "ok",
  "model": "siglip2-so400m-patch16-512",
  "version": "1.0",
  "dimension": 1152,
  "device": "cuda:0"
}
```

### 图片嵌入

**上传文件方式：**
```bash
curl -X POST http://localhost:6010/embed/image \
  -F "file=@/path/to/image.jpg"
```

**Base64 方式：**
```bash
curl -X POST http://localhost:6010/embed/image/base64 \
  -H "Content-Type: application/json" \
  -d '{"image_base64": "base64编码的图片数据..."}'
```

返回示例：
```json
{
  "embedding": [-0.0138, -0.0193, 0.0094, ...],
  "dimension": 1152,
  "model": "siglip2-so400m-patch16-512",
  "version": "1.0"
}
```

### 文本嵌入

**单个文本：**
```bash
curl -X POST http://localhost:6011/embed/text \
  -H "Content-Type: application/json" \
  -d '{"text": "一只橙色的猫在阳光下晒太阳"}'
```

返回示例：
```json
{
  "embedding": [0.2095, 0.0005, -0.0102, ...],
  "dimension": 2560,
  "model": "Qwen3-4B",
  "version": "1.0"
}
```

**批量文本：**
```bash
curl -X POST http://localhost:6011/embed/texts \
  -H "Content-Type: application/json" \
  -d '{"texts": ["一只猫", "一只狗", "美丽的风景"]}'
```

返回示例：
```json
{
  "embeddings": [
    [0.1, 0.2, ...],
    [0.3, 0.4, ...],
    [0.5, 0.6, ...]
  ],
  "dimension": 2560,
  "model": "Qwen3-4B",
  "version": "1.0"
}
```

### Python 调用示例

```python
import requests
import numpy as np

# 文本嵌入
def get_text_embedding(text: str) -> np.ndarray:
    response = requests.post(
        "http://localhost:6011/embed/text",
        json={"text": text}
    )
    data = response.json()
    return np.array(data["embedding"])

# 图片嵌入
def get_image_embedding(image_path: str) -> np.ndarray:
    with open(image_path, "rb") as f:
        response = requests.post(
            "http://localhost:6010/embed/image",
            files={"file": f}
        )
    data = response.json()
    return np.array(data["embedding"])

# 计算余弦相似度
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# 使用示例
text_emb = get_text_embedding("一只猫在晒太阳")
image_emb = get_image_embedding("cat.jpg")

print(f"文本嵌入维度: {len(text_emb)}")
print(f"图片嵌入维度: {len(image_emb)}")
```

## 模型路径

| 模型 | 路径 |
|------|------|
| Qwen3-4B | `/mnt/hdd/models/Z-Image-Turbo` (复用 text_encoder) |
| SigLIP2 | `/mnt/hdd/models/siglip2-so400m-patch16-512` |

### 下载 SigLIP2 模型

```bash
# 从 ModelScope 下载
modelscope download google/siglip2-so400m-patch16-512 \
    --local_dir /mnt/hdd/models/siglip2-so400m-patch16-512

# 或从 HuggingFace 下载
huggingface-cli download google/siglip2-so400m-patch16-512 \
    --local-dir /mnt/hdd/models/siglip2-so400m-patch16-512
```

## 显存需求

| 服务 | 模型 | 显存占用 |
|------|------|---------|
| 文本嵌入 | Qwen3-4B | ~8GB |
| 图片嵌入 | SigLIP2 1.14B | ~3GB |
| **总计** | | **~11GB** |

> 24GB 显存可以同时运行两个服务，还有约 13GB 余量

## 日志查看

服务启动后，日志输出到终端。可以使用 `nohup` 或 `screen` 后台运行：

```bash
# 使用 nohup 后台运行
nohup python siglip2_embed.py > logs/siglip2.log 2>&1 &
nohup python qwen3_embed.py > logs/qwen3.log 2>&1 &

# 查看日志
tail -f logs/siglip2.log
tail -f logs/qwen3.log
```
