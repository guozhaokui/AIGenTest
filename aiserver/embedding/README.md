# 嵌入服务（GPU 服务器）

此目录包含运行在 GPU 服务器上的嵌入计算服务。

## 服务列表

| 服务 | 端口 | 模型 | 维度 |
|------|------|------|------|
| 图片嵌入 | 6010 | SigLIP-2 (so400m-patch16-512) | 1152 |
| 文本嵌入 | 6011 | Qwen3-4B | 2560 |

## 快速启动

```bash
# 启动服务
./start_embed_server.sh

# 停止服务
./stop_all.sh
```

## 模型路径

需要预先下载模型到以下位置：

```
/mnt/hdd/models/
├── siglip2-so400m-patch16-512/    # SigLIP-2 图片编码器
└── Z-Image-Turbo/                  # 包含 Qwen3 text_encoder
    ├── text_encoder/
    └── tokenizer/
```

## 依赖

```bash
# Conda 环境
conda activate hidream

# 依赖包
pip install torch transformers fastapi uvicorn pillow numpy
```

## API 接口

### 图片嵌入 (6010)

```bash
# 健康检查
curl http://localhost:6010/health

# 上传图片获取嵌入
curl -X POST http://localhost:6010/embed/image \
  -F "file=@image.jpg"

# Base64 方式
curl -X POST http://localhost:6010/embed/image/base64 \
  -H "Content-Type: application/json" \
  -d '{"image": "base64编码..."}'
```

### 文本嵌入 (6011)

```bash
# 健康检查
curl http://localhost:6011/health

# 单个文本
curl -X POST http://localhost:6011/embed/text \
  -H "Content-Type: application/json" \
  -d '{"text": "一只猫在晒太阳"}'

# 批量文本
curl -X POST http://localhost:6011/embed/texts \
  -H "Content-Type: application/json" \
  -d '{"texts": ["文本1", "文本2"]}'
```

## 返回格式

```json
{
  "embedding": [0.1, 0.2, ...],
  "dimension": 1152,
  "model": "siglip2-so400m-patch16-512",
  "version": "1.0"
}
```

## 显存需求

| 模型 | 显存 |
|------|------|
| SigLIP-2 1.14B | ~3GB |
| Qwen3-4B | ~8GB |
| **合计** | **~11GB** |

推荐 16GB+ 显存的 GPU。

