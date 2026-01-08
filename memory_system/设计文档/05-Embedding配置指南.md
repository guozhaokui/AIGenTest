# Embedding配置指南

## 概述

系统支持多种embedding服务，可以灵活切换：

| 方式 | 优势 | 适用场景 |
|------|------|----------|
| **远程HTTP** | 复用现有服务，无需本地GPU | 推荐！已有embedding服务器 |
| **本地模型** | 完全离线，无网络依赖 | 无法访问远程服务器 |
| **ChromaDB内置** | 配置最简单，自动处理 | 快速原型验证 |

---

## 方案1：远程HTTP服务（推荐）

### 现有BGE服务

你的服务器(`192.168.0.100`)上已部署：

- **BGE文本嵌入**：`http://192.168.0.100:6012`
- **SigLIP-2图片嵌入**：`http://192.168.0.100:6010`
- **Qwen3重排序**：`http://192.168.0.100:6013`

### 配置

**config.yaml:**
```yaml
embedding:
  provider: remote

  remote:
    base_url: http://192.168.0.100:6012
    timeout: 30.0
    batch_size: 32
```

### 代码使用

```python
from core.embedding import create_embedding_provider

# 创建远程embedding provider
emb = create_embedding_provider(
    "remote",
    base_url="http://192.168.0.100:6012"
)

# 单个文本
result = emb.embed("这是一个测试")
print(result.embeddings.shape)  # (1, 1024)

# 批量文本
texts = ["文本1", "文本2", "文本3"]
result = emb.embed(texts)
print(result.embeddings.shape)  # (3, 1024)
```

### 优势

✅ **复用现有服务**：无需重复部署
✅ **GPU加速**：使用服务器GPU，速度快
✅ **统一模型**：与其他项目使用相同的embedding
✅ **节省资源**：本地无需加载大模型

### 注意事项

- 确保BGE服务已启动：`./start_embed_server.sh`
- 检查网络连通性：`curl http://192.168.0.100:6012/health`
- 批量请求限制：最多32条文本/请求（服务端限制）

---

## 方案2：本地模型

### 安装依赖

```bash
pip install sentence-transformers
```

### 配置

**config.yaml:**
```yaml
embedding:
  provider: local

  local:
    model_name: BAAI/bge-small-zh-v1.5
```

### 可选模型

| 模型 | 维度 | 大小 | 速度 | 适用 |
|------|------|------|------|------|
| `BAAI/bge-small-zh-v1.5` | 512 | 200MB | 快 | 中文优化 |
| `BAAI/bge-base-zh-v1.5` | 768 | 400MB | 中 | 平衡 |
| `BAAI/bge-large-zh-v1.5` | 1024 | 1.3GB | 慢 | 最高精度 |
| `paraphrase-multilingual-MiniLM-L12-v2` | 384 | 470MB | 快 | 多语言 |

### 代码使用

```python
from core.embedding import create_embedding_provider

# 创建本地embedding provider
emb = create_embedding_provider(
    "local",
    model_name="BAAI/bge-small-zh-v1.5"
)

# 使用方式与远程相同
result = emb.embed("测试文本")
```

### 优势

✅ **完全离线**：无需网络
✅ **隐私保护**：数据不离开本地
✅ **稳定可靠**：不依赖外部服务

### 注意事项

- 首次使用会下载模型（几百MB）
- 需要一定的CPU/内存资源
- 速度比GPU服务器慢

---

## 方案3：ChromaDB内置

### 配置

**config.yaml:**
```yaml
embedding:
  provider: chromadb
```

### 代码使用

```python
from core.embedding import create_embedding_provider

# 使用ChromaDB内置
emb = create_embedding_provider("chromadb")

result = emb.embed("测试文本")
```

### 优势

✅ **零配置**：无需额外设置
✅ **自动下载**：首次使用自动下载小模型
✅ **快速上手**：适合原型验证

### 注意事项

- 维度较小（384维）：精度略低
- 模型固定：无法自定义
- 主要用于快速测试

---

## 切换策略

### 开发阶段

```yaml
# 使用远程BGE服务（推荐）
embedding:
  provider: remote
  remote:
    base_url: http://192.168.0.100:6012
```

### 部署到其他机器

```yaml
# 如果新机器无法访问BGE服务器，切换到本地
embedding:
  provider: local
  local:
    model_name: BAAI/bge-small-zh-v1.5
```

### 快速原型验证

```yaml
# 最快上手
embedding:
  provider: chromadb
```

---

## 测试方法

### 1. 快速测试脚本

```bash
cd memory_system
python tests/test_embedding.py
```

输出示例：
```
===========================================================
测试远程BGE服务 (http://192.168.0.100:6012)
===========================================================

1. 健康检查...
   ✓ 服务可用

2. 获取模型信息...
   维度: 1024
   模型: BGE-Large-ZH

3. 测试单个文本...
   ✓ Embedding成功
   形状: (1, 1024)
   维度: 1024

4. 测试批量文本...
   ✓ Embedding成功
   形状: (3, 1024)

✅ 远程BGE服务测试通过！
```

### 2. 手动测试

```python
from core.embedding import create_embedding_provider

# 测试远程服务
emb = create_embedding_provider("remote", base_url="http://192.168.0.100:6012")

# 健康检查
print("服务可用:", emb.health_check())

# 测试embedding
result = emb.embed("测试")
print("成功! 形状:", result.embeddings.shape)
```

---

## 性能对比

基于1000条文档，平均每条300字：

| 方式 | 处理时间 | 维度 | 精度 |
|------|----------|------|------|
| 远程BGE (GPU) | ~5秒 | 1024 | ⭐⭐⭐⭐⭐ |
| 本地bge-small (CPU) | ~30秒 | 512 | ⭐⭐⭐⭐ |
| 本地bge-large (CPU) | ~60秒 | 1024 | ⭐⭐⭐⭐⭐ |
| ChromaDB内置 (CPU) | ~25秒 | 384 | ⭐⭐⭐ |

**结论：** 远程BGE服务最快且精度最高！

---

## 常见问题

### Q1: 如何确认BGE服务是否启动？

```bash
curl http://192.168.0.100:6012/health
```

应该返回：
```json
{
  "status": "ok",
  "model": "bge-large-zh",
  "version": "1.0",
  "dimension": 1024,
  "device": "cuda:0"
}
```

### Q2: 无法连接到远程服务？

**检查清单：**
1. BGE服务是否启动？
   ```bash
   ssh ubuntu@192.168.0.100
   cd /mnt/hdd/guo/AIGenTest/aiserver/embedding
   ./start_embed_server.sh
   ```

2. 网络是否连通？
   ```bash
   ping 192.168.0.100
   ```

3. 防火墙是否阻止？
   ```bash
   telnet 192.168.0.100 6012
   ```

4. 服务器日志检查：
   ```bash
   tail -f aiserver/embedding/logs/bge_embed.log
   ```

### Q3: 本地模型下载慢？

使用国内镜像：
```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### Q4: 如何批量处理大量文本？

```python
# 自动分批处理
emb = create_embedding_provider("remote", base_url="http://192.168.0.100:6012")

# 即使有1000条文本，也会自动分批（每批32条）
texts = ["文本" + str(i) for i in range(1000)]
result = emb.embed(texts)  # 自动分批，无需手动处理
```

### Q5: 维度不一致怎么办？

**问题：** BGE-Large是1024维，ChromaDB内置是384维

**解决：** 统一使用一种服务，不要混用

```yaml
# 正确：统一使用BGE
embedding:
  provider: remote

# 错误：不要切换（会导致向量维度不匹配）
```

---

## 推荐配置

### 生产环境

```yaml
embedding:
  provider: remote
  remote:
    base_url: http://192.168.0.100:6012
    timeout: 60.0  # 增加超时时间
    batch_size: 32
```

### 开发调试

```yaml
embedding:
  provider: chromadb  # 快速测试
```

### 离线部署

```yaml
embedding:
  provider: local
  local:
    model_name: BAAI/bge-small-zh-v1.5  # 平衡性能和精度
```

---

## 下一步

- [测试embedding服务](../tests/test_embedding.py)
- [向量存储设计](./02-知识库设计.md#向量存储vector-store)
- [开始实现MVP](./00-README.md#下一步计划)
