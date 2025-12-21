# 图片管理服务

图片文件管理系统，支持去重、多源描述、向量搜索。

## 功能

- 📷 **图片上传**：自动去重、生成缩略图、计算嵌入向量
- 🔍 **文本搜索**：根据文字描述搜索图片
- 🖼️ **以图搜图**：上传图片找相似图
- 📝 **描述管理**：为图片添加多种描述（VLM 生成、人工标注）

## 快速开始

### 1. 启动嵌入服务

```bash
cd ../aiserver/embedding
./start_all.sh
```

### 2. 启动图片管理服务

```bash
./start.sh
```

### 3. 停止服务

```bash
./stop.sh
```

## API 文档

服务启动后访问: http://localhost:6060/docs

### 主要接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/images` | POST | 上传图片 |
| `/api/images` | GET | 列出图片 |
| `/api/images/{sha256}` | GET | 获取图片信息 |
| `/api/images/{sha256}` | DELETE | 删除图片 |
| `/api/images/{sha256}/thumbnail` | GET | 获取缩略图 |
| `/api/images/{sha256}/file` | GET | 获取原图 |
| `/api/images/{sha256}/descriptions` | POST | 添加描述 |
| `/api/search/text` | POST | 文本搜索 |
| `/api/search/image` | POST | 以图搜图 |
| `/health` | GET | 健康检查 |
| `/api/stats` | GET | 统计信息 |

## 使用示例

### 上传图片

```bash
curl -X POST http://localhost:6060/api/images \
  -F "file=@image.jpg" \
  -F "source=test"
```

返回：
```json
{
  "message": "上传成功",
  "sha256": "a1b2c3d4...",
  "width": 1024,
  "height": 768,
  "file_size": 102400,
  "format": "JPEG",
  "status": "ready"
}
```

### 文本搜索

```bash
curl -X POST http://localhost:6060/api/search/text \
  -H "Content-Type: application/json" \
  -d '{"query": "一只猫在晒太阳", "top_k": 10}'
```

返回：
```json
{
  "query": "一只猫在晒太阳",
  "results": [
    {
      "sha256": "a1b2c3d4...",
      "score": 0.92,
      "matched_by": "vlm1",
      "matched_text": "一只橙色的猫坐在窗台上晒太阳",
      "width": 1024,
      "height": 768
    }
  ]
}
```

### 以图搜图

```bash
curl -X POST http://localhost:6060/api/search/image \
  -F "file=@query.jpg" \
  -F "top_k=10"
```

### 添加描述

```bash
curl -X POST http://localhost:6060/api/images/a1b2c3d4.../descriptions \
  -H "Content-Type: application/json" \
  -d '{"method": "human", "content": "我家的橘猫"}'
```

### Python 调用示例

```python
import requests

# 上传图片
with open("image.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:6060/api/images",
        files={"file": f},
        data={"source": "my_album"}
    )
    result = response.json()
    sha256 = result["sha256"]

# 文本搜索
response = requests.post(
    "http://localhost:6060/api/search/text",
    json={"query": "风景照片", "top_k": 10}
)
results = response.json()["results"]

# 获取缩略图
response = requests.get(f"http://localhost:6060/api/images/{sha256}/thumbnail")
with open("thumb.jpg", "wb") as f:
    f.write(response.content)
```

## 目录结构

```
imagemgr/
├── src/                    # 源代码
│   ├── api_server.py       # API 服务
│   ├── database.py         # 数据库管理
│   ├── storage.py          # 文件存储
│   ├── vector_index.py     # 向量索引
│   └── embedding_client.py # 嵌入服务客户端
├── config/                 # 配置文件
│   └── embedding_services.yaml
├── data/                   # 数据库文件
│   └── imagemgr.db
├── storage/                # 图片存储
│   └── xx/yy/zzz.../
├── vector_index/           # 向量索引
│   ├── siglip2_image_v1/
│   └── qwen3_text_v1/
├── logs/                   # 日志目录
├── doc/                    # 文档
├── start.sh                # 启动脚本
├── stop.sh                 # 停止脚本
└── README.md
```

## 端口配置

| 服务 | 端口 | 说明 |
|------|------|------|
| 图片管理服务 | 6060 | 主服务 |
| 图片嵌入服务 | 6010 | SigLIP2 |
| 文本嵌入服务 | 6011 | Qwen3-4B |

## 依赖服务

图片管理服务依赖嵌入服务，请确保先启动：

cd imagemgr/src
pip install fastapi uvicorn pillow numpy pyyaml aiohttp aiofiles python-multipart

```bash
cd ../aiserver/embedding
./start_all.sh
```

