# AI 服务网关

轻量级 Python 网关，统一管理和路由所有 AI 服务请求。

## 架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           客户端电脑                                 │
│                                                                     │
│  Frontend ──┐                                                       │
│  Backend  ──┼──▶ AI Gateway (localhost:8080)                        │
│  imagemgr ──┘         │                                             │
│                       ├──▶ 服务器1 (EMBED_SERVER_1) 基础嵌入服务    │
│                       ├──▶ 服务器2 (EMBED_SERVER_2) 8B 嵌入服务     │
│                       ├──▶ VLM_HOST (VLM, SSH 转发)                 │
│                       └──▶ TRELLIS_HOST (Trellis 3D)                │
└─────────────────────────────────────────────────────────────────────┘
```

## 配置

**所有配置都在项目根目录的 `.env` 文件中**，网关和 GPU 服务器都应使用相同的端口配置。

### 必需的环境变量

```env
# =============================================================================
# AI 服务网关配置
# =============================================================================

# GPU 服务器 1：基础嵌入服务
EMBED_SERVER_1=192.168.0.100
PORT_SIGLIP2=6010      # SigLIP2 图片嵌入
PORT_EMBED_4B=6011     # Qwen3-4B 嵌入
PORT_EMBED_BGE=6012    # BGE 嵌入
PORT_RERANK_4B=6013    # Qwen3-4B 重排序
PORT_ZIMAGE=6006       # Z-Image 图片生成

# GPU 服务器 2：8B 专用嵌入模型
EMBED_SERVER_2=192.168.0.132
PORT_EMBED_8B=6014     # Qwen3-Embedding-8B
PORT_RERANK_8B=6015    # Qwen3-Reranker-8B

# VLM 服务（SSH 端口转发）
VLM_HOST=localhost
PORT_VLM=6050

# Trellis 3D 生成服务
TRELLIS_HOST=localhost
PORT_TRELLIS=8000

# 默认模型
DEFAULT_EMBED=embed_text_bge
DEFAULT_RERANK=rerank_4b

# 网关端口
GATEWAY_PORT=8080
```

## 快速开始

### 安装依赖

```bash
pip install fastapi uvicorn httpx python-dotenv
```

### 启动网关

```bash
cd aiserver/gateway
python ai_gateway.py
```

### 测试

```bash
# 检查所有服务状态
curl http://localhost:8080/health/all

# 文本嵌入
curl -X POST http://localhost:8080/embed/text \
  -H "Content-Type: application/json" \
  -d '{"text": "一只猫"}'
```

## API 路由

### 嵌入服务

| 路由 | 服务器 | 端口变量 | 说明 |
|------|--------|----------|------|
| `/embed/image` | EMBED_SERVER_1 | PORT_SIGLIP2 | SigLIP2 图片嵌入 |
| `/embed/text` | - | - | 文本嵌入（使用默认模型） |
| `/embed/text/bge` | EMBED_SERVER_1 | PORT_EMBED_BGE | BGE 嵌入 |
| `/embed/text/qwen3-4b` | EMBED_SERVER_1 | PORT_EMBED_4B | Qwen3-4B 嵌入 |
| `/embed/text/qwen3-8b` | EMBED_SERVER_2 | PORT_EMBED_8B | Qwen3-Embedding-8B |

### 重排序服务

| 路由 | 服务器 | 端口变量 | 说明 |
|------|--------|----------|------|
| `/rerank` | - | - | 重排序（使用默认模型） |
| `/rerank/qwen3-4b` | EMBED_SERVER_1 | PORT_RERANK_4B | Qwen3-4B 重排序 |
| `/rerank/qwen3-8b` | EMBED_SERVER_2 | PORT_RERANK_8B | Qwen3-Reranker-8B |

### 其他服务

| 路由 | 服务器 | 端口变量 | 说明 |
|------|--------|----------|------|
| `/vlm/caption` | VLM_HOST | PORT_VLM | VLM 图片描述 |
| `/vlm/chat` | VLM_HOST | PORT_VLM | VLM 聊天 |
| `/generate/image` | EMBED_SERVER_1 | PORT_ZIMAGE | Z-Image 图片生成 |
| `/generate/3d` | TRELLIS_HOST | PORT_TRELLIS | Trellis 3D 生成 |
| `/health/all` | - | - | 所有服务状态 |

## GPU 服务器端口配置

GPU 服务器上的服务也应使用 `.env` 中配置的端口：

```bash
# 在 GPU 服务器上启动服务时使用对应端口
# 例如 siglip2_embed.py 默认端口应与 PORT_SIGLIP2 一致
python siglip2_embed.py  # 使用端口 6010
```

如果需要修改端口，同时修改：
1. `.env` 文件中的端口配置
2. GPU 服务器上对应服务的启动端口

## VLM 端口转发

VLM 服务在远程 GPU 服务器上，通过 SSH 端口转发访问：

```bash
# 启动端口转发
aiserver/qwen3vlm/port_forward.sh start

# 检查状态
aiserver/qwen3vlm/port_forward.sh status
```
