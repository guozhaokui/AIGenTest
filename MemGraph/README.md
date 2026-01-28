# MemGraph - 激活式知识图谱搜索引擎 V3.0

Python + FastAPI + FAISS + Qwen3-8B 嵌入模型实现的高性能知识图谱搜索系统。

## 🚀 核心特性

### V3.0 新特性

- ✅ **真实的语义嵌入** - 使用 Qwen3-8B 嵌入模型，而非TF-IDF词袋
- ✅ **FAISS向量数据库** - 高效的向量检索，支持百万级文档
- ✅ **FastAPI服务** - RESTful API，可独立部署
- ✅ **异步处理** - 全异步设计，高并发性能
- ✅ **自动启动** - 随 `pnpm dev:backend` 一起启动

### 保留特性

- 🎯 **激活式搜索** - 多粒度n-gram激活机制
- 🧠 **智能评分** - 激活得分 + 向量相似度双重排序
- 📊 **多粒度匹配** - 字符/词/句子 7种粒度
- ⚡ **高性能** - FAISS加速向量检索

## 📦 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 服务端 | FastAPI + Uvicorn | HTTP API服务 |
| 向量数据库 | FAISS | 向量相似度检索 |
| 元数据库 | SQLite | N-gram和文档元数据 |
| 嵌入模型 | Qwen3-8B (via Gateway) | 文本向量化 |
| 分词 | jieba | 中文分词 |
| MCP客户端 | Node.js | Claude Code集成 |

## 🏗️ 架构设计

```
┌─────────────┐
│ Claude Code │
│   (MCP)     │
└──────┬──────┘
       │ stdio
       ↓
┌──────────────────┐
│  Node.js Client  │  (mcp-lessons/src/index-v3.js)
│  port: stdio     │
└──────┬───────────┘
       │ HTTP
       ↓
┌──────────────────┐
│  MemGraph Server │  (FastAPI)
│  port: 8800      │
├──────────────────┤
│ • N-gram处理     │
│ • 激活式搜索     │
│ • FAISS向量检索  │
└──────┬───────────┘
       │ HTTP
       ↓
┌──────────────────┐
│  AI Gateway      │  (port: 8899)
│  Qwen3-8B Embed  │
└──────────────────┘
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd D:\work\AIGenTest\MemGraph
pip install -r requirements.txt
```

### 2. 启动服务

#### 方式A：随backend一起启动（推荐）

```bash
cd D:\work\AIGenTest
pnpm dev:backend
```

会自动启动：
- Express Backend (port: 3000)
- ImageMgr (port: 8890)
- Knowledge Query (port: 8891)
- **MemGraph (port: 8800)**

#### 方式B：独立启动

```bash
cd D:\work\AIGenTest\MemGraph
python start.py
```

### 3. 测试服务

#### 方式A：使用 Web 测试面板（推荐）

打开浏览器访问：

```
http://localhost:8800
```

Web 面板提供：
- ✅ 可视化的搜索界面
- ✅ 记录新经验的表单
- ✅ 实时统计信息
- ✅ 详细的得分调试信息（激活得分、向量相似度、匹配片段）
- ✅ 标签管理
- ✅ 索引重建

详细使用说明见：[WEB_TEST_GUIDE.md](./WEB_TEST_GUIDE.md)

#### 方式B：使用 cURL 命令

```bash
# 健康检查
curl http://localhost:8800/health

# 查看统计
curl http://localhost:8800/stats

# 搜索
curl -X POST http://localhost:8800/search \
  -H "Content-Type: application/json" \
  -d '{"query": "claude code mcp", "limit": 5}'
```

## 📚 API文档

启动服务后访问：http://localhost:8800/docs

### 核心接口

#### 1. 记录经验

```http
POST /record
Content-Type: application/json

{
  "role": "AI",
  "project": "项目名",
  "directory": "项目路径",
  "problem": "问题描述",
  "solution": "解决方法",
  "tags": ["标签1", "标签2"]
}
```

#### 2. 搜索经验

```http
POST /search
Content-Type: application/json

{
  "query": "搜索关键词",
  "limit": 10,
  "min_score": 0.1,
  "use_vector": true
}
```

**响应**:
```json
{
  "query": "claude code mcp",
  "count": 3,
  "results": [
    {
      "doc_id": 1,
      "path": "2026/01/22_xxx.md",
      "total_score": 43.58,
      "activation_score": 42.3,
      "vector_similarity": 0.847,
      "matched_ngrams": 20,
      "problem": "...",
      "solution": "...",
      "tags": ["MCP", "Claude Code"]
    }
  ]
}
```

#### 3. 按标签搜索

```http
POST /search/tag
Content-Type: application/json

{
  "tag": "MCP",
  "limit": 10
}
```

#### 4. 最近记录

```http
POST /recent
Content-Type: application/json

{
  "limit": 10
}
```

#### 5. 列出标签

```http
GET /tags
```

#### 6. 统计信息

```http
GET /stats
```

**响应**:
```json
{
  "documents": 6,
  "ngrams": 1247,
  "unique_ngrams": 974,
  "faiss_vectors": 6
}
```

#### 7. 重建索引

```http
POST /rebuild
```

## 📂 文件结构

```
MemGraph/
├── src/
│   ├── config.py              # 配置文件
│   ├── embedding_client.py    # 嵌入服务客户端
│   ├── ngram_processor.py     # N-gram处理器
│   ├── knowledge_indexer.py   # 知识索引器
│   ├── activation_search.py   # 激活式搜索引擎
│   └── server.py              # FastAPI服务
├── data/
│   ├── knowledge.db           # SQLite元数据库
│   └── knowledge.faiss        # FAISS向量索引
├── records/                   # Markdown文档存储
│   └── YYYY/MM/
├── logs/                      # 日志目录
├── requirements.txt           # Python依赖
├── start.py                   # 启动脚本
└── README.md                  # 本文档
```

## 🔍 搜索原理

### 1. 激活式搜索

```
查询: "claude code mcp"
    ↓
分词+N-gram拆分
    ↓
[claude, code, mcp, claude code, code mcp, ...]
    ↓
匹配SQLite中的N-gram
    ↓
激活包含这些N-gram的文档
    ↓
计算激活得分 (基于类型、位置、粒度权重)
```

### 2. 向量相似度

```
查询: "claude code mcp"
    ↓
调用Qwen3-8B生成1024维向量
    ↓
在FAISS中检索最相似的文档向量
    ↓
计算余弦相似度
```

### 3. 综合排序

```
总分 = 激活得分 × 覆盖率 + 向量相似度 × 3.0
```

- **激活得分**: 匹配的n-gram数量和质量
- **覆盖率**: 查询词被匹配的比例
- **向量相似度**: 语义层面的相关性

## ⚙️ 配置说明

### src/config.py

```python
# 嵌入服务
EMBED_SERVICE_URL = "http://localhost:8899/embed/text/qwen3-8b"
EMBED_DIMENSION = 1024

# 服务端口
SERVICE_PORT = 8800

# 评分权重
SCORE_WEIGHTS = {
    "metadata": 5.0,      # 元数据权重
    "sentence": 3.0,      # 句子权重
    "word_4gram": 2.5,    # 4词组权重
    "vector_similarity": 3.0  # 向量相似度权重
}
```

## 📊 性能对比

| 版本 | 检索方式 | 嵌入模型 | 语义理解 | 响应时间 |
|------|---------|---------|---------|---------|
| V1 | 遍历文件 | 无 | ❌ | ~50ms |
| V2 | SQLite+FTS5 | TF-IDF | ⚠️ 弱 | ~5ms |
| **V3** | **FAISS** | **Qwen3-8B** | ✅ **强** | **~10ms** |

## 🎯 使用示例

### Claude Code中使用

```javascript
// 配置 claude_desktop_config.json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["D:/work/AIGenTest/backend/mcp-lessons/src/index-v3.js"]
    }
  }
}
```

然后在Claude Code中：

```
我: 搜索 "claude code mcp 配置"
Claude: 调用 search_lessons 工具...
        找到 3 条相关经验（激活式搜索+向量相似度）：

        1. [2026/01/22_11-07-21_如何在claude-code中添加mcp服务器.md] (得分: 48.23)
           激活: 25 个片段, 激活得分: 45.3, 向量相似度: 0.978
           ...
```

## 🛠️ 故障排查

### 问题1：MemGraph服务启动失败

**原因**: Python依赖未安装

**解决**:
```bash
cd D:\work\AIGenTest\MemGraph
pip install -r requirements.txt
```

### 问题2：嵌入服务连接失败

**原因**: AI Gateway未启动

**检查**:
```bash
curl http://localhost:8899/health
```

**解决**: 确保AI Gateway服务运行中

### 问题3：FAISS索引损坏

**解决**: 重建索引
```bash
curl -X POST http://localhost:8800/rebuild
```

## 📈 未来计划

- [ ] 支持更多嵌入模型（BGE, M3E等）
- [ ] 添加rerank重排序
- [ ] 知识图谱可视化
- [ ] 增量索引更新
- [ ] 分布式部署支持

## 📝 更新日志

### V3.0.0 (2026-01-28)

- ✅ 重写为Python + FastAPI架构
- ✅ 集成Qwen3-8B嵌入模型
- ✅ 使用FAISS替代TF-IDF
- ✅ 自动随backend启动
- ✅ 完整的HTTP API

### V2.0.0 (2026-01-27)

- ✅ 添加激活式搜索
- ✅ 使用SQLite + FTS5
- ✅ TF-IDF向量相似度

### V1.0.0 (2026-01-21)

- ✅ 基础Markdown存储
- ✅ 简单全文搜索

## 📄 许可证

MIT

---

**开发者**: Claude + Human Collaboration
**最后更新**: 2026-01-28
