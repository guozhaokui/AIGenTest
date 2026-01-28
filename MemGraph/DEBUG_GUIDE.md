# MemGraph 调试指南

## 问题诊断

### 问题1: 向量相似度为 0 或显示 "-"

**可能原因**:
1. FAISS 向量索引为空或未构建
2. AI Gateway (嵌入服务) 未运行
3. 嵌入生成失败但被忽略
4. 文档-向量映射 (`doc_id_to_index`) 未建立

**诊断步骤**:

#### 1. 打开调试面板

访问：http://localhost:8800/static/debug.html

#### 2. 检查系统状态

查看顶部的 4 个统计指标：

```
文档数: 6
FAISS向量数: 0  ❌ 问题在这里！
N-gram总数: 1247
唯一N-gram: 974
```

**正常状态**: 文档数 = FAISS向量数

**异常状态**: 文档数 > 0 但 FAISS向量数 = 0

#### 3. 测试嵌入服务

点击 **"测试嵌入服务"** 按钮

**成功响应**:
```
✅ 嵌入服务正常！维度: 1024, 耗时: 150ms
```

**失败响应**:
```
❌ 嵌入服务失败: Connection refused
```

#### 4. 检查 AI Gateway

如果嵌入服务测试失败，需要检查 AI Gateway：

```bash
# 检查服务状态
curl http://localhost:8899/health

# 手动测试嵌入接口
curl -X POST http://localhost:8899/embed/text/qwen3-8b \
  -H "Content-Type: application/json" \
  -d '{"text": "测试文本"}'
```

**预期响应**:
```json
{
  "embedding": [0.123, -0.456, ...],  // 1024维向量
  "dimension": 1024
}
```

#### 5. 查看文档-向量映射

在调试面板中，查看 **"文档列表与向量映射"** 表格：

| 文档ID | FAISS索引 | 路径 | 问题预览 |
|--------|-----------|------|----------|
| 1 | ❌ - | 2026/01/... | ... |
| 2 | ❌ - | 2026/01/... | ... |

**❌ 表示该文档没有 FAISS 向量**

**✅ 表示有向量，后面会显示 FAISS 索引号**

#### 6. 查看向量索引详情

在 **"向量索引详情"** 部分：

**如果为空**:
```
向量总数: 0
向量维度: 0
索引类型: empty
```

**如果正常**:
```
向量总数: 6
向量维度: 1024
索引类型: IndexFlatIP
```

并且会显示每个向量的详细信息：
- FAISS索引号
- 对应的文档ID
- 文档路径
- 向量范数 (应该接近 1.0，因为已归一化)
- 向量预览 (前10维)

## 解决方案

### 方案1: 重建索引

如果 AI Gateway 现在已经正常运行，但之前构建索引时未运行：

1. 在调试面板点击 **"重建索引"** 按钮
2. 确认操作
3. 等待重建完成（会显示进度日志）
4. 检查系统状态是否恢复正常

**重建过程**:
- 清空所有数据库表
- 重新扫描 `records/` 目录下的所有 `.md` 文件
- 提取 n-gram
- 调用 AI Gateway 生成向量
- 构建 FAISS 索引
- 保存到磁盘

### 方案2: 启动 AI Gateway

如果 AI Gateway 未运行：

```bash
# 方法1: 单独启动
cd D:\work\AIGenTest\aiserver\gateway
python ai_gateway.py

# 方法2: 使用 backend 统一启动 (需要修改 server.js)
cd D:\work\AIGenTest
# 取消注释 server.js 中的 startGateway()
pnpm dev:backend
```

**验证 AI Gateway**:
```bash
curl http://localhost:8899/health
```

### 方案3: 检查配置

检查 `MemGraph/src/config.py`:

```python
# 嵌入服务配置
EMBED_SERVICE_URL = "http://localhost:8899/embed/text/qwen3-8b"
EMBED_DIMENSION = 1024
```

确保：
- 端口号正确 (8899)
- 路径正确 (`/embed/text/qwen3-8b`)
- 维度匹配 (Qwen3-8B = 1024)

## 调试面板功能详解

### 1. 系统状态卡片

显示核心指标和健康检查。

**警告提示**:
- 文档数和向量数不一致
- 向量索引为空

### 2. 向量索引详情

**信息**:
- 向量总数
- 向量维度 (Qwen3-8B = 1024)
- 索引类型 (IndexFlatIP = 内积索引，用于余弦相似度)

**向量列表**:
- 每个向量的 FAISS 索引号
- 对应的文档ID
- 文档路径
- 向量范数 (应该 ≈ 1.0)
- 向量预览和完整向量

**操作**:
- 点击 "显示完整向量" 可以查看所有 1024 维的值

### 3. 文档列表与向量映射

**检查项**:
- 每个文档是否有对应的 FAISS 向量
- doc_id → faiss_index 映射关系
- 文档元数据 (角色、项目、标签)

**用途**:
- 发现哪些文档缺少向量
- 验证映射关系是否正确

### 4. N-gram 分布统计

**按类型统计**:
```
char_2gram: 523
char_3gram: 412
word_2gram: 189
word_3gram: 87
word_4gram: 36
sentence: 0
```

**Top 50 N-gram**:
- 显示出现在最多文档中的 n-gram
- 显示总出现次数
- 帮助理解激活式搜索的覆盖情况

**用途**:
- 检查分词是否正常
- 发现高频关键词
- 理解激活机制

## 常见问题

### Q1: 重建索引很慢

**原因**: 每个文档都需要调用 AI Gateway 生成 1024 维向量

**耗时估算**:
- 单个文档: ~150ms (嵌入生成)
- 6个文档: ~1秒
- 100个文档: ~15秒

**建议**: 耐心等待，查看 backend 日志确认进度

### Q2: 向量范数不是 1.0

**原因**: 向量已归一化，理论上范数应该是 1.0

**可接受范围**: 0.99 - 1.01 (浮点精度误差)

**异常**: < 0.9 或 > 1.1

### Q3: 向量维度不是 1024

**检查**:
1. AI Gateway 返回的维度
2. `config.py` 中的 `EMBED_DIMENSION` 配置
3. FAISS 索引初始化时的维度

**Qwen3-8B 标准**: 1024 维

### Q4: 部分文档没有向量

**可能原因**:
1. 索引该文档时 AI Gateway 未运行
2. 文档内容为空或过短
3. 嵌入生成超时或失败

**解决**: 重建索引

### Q5: 搜索时向量相似度仍然为 0

即使 FAISS 有向量，搜索结果的 `vector_similarity` 仍然是 0：

**检查 `activation_search.py`**:

```python
async def _add_vector_similarity(self, doc_scores: Dict, query: str):
    # 1. 生成查询向量
    query_embedding = await self.embedding_client.embed_text(query)

    # 2. 检查 doc_id_to_index 映射
    for doc_id in doc_ids:
        faiss_idx = self.indexer.doc_id_to_index.get(doc_id)
        if faiss_idx is None:
            print(f"Warning: doc_id={doc_id} has no FAISS mapping")
            continue
```

**调试步骤**:
1. 检查查询向量是否成功生成
2. 检查 `doc_id_to_index` 映射是否存在
3. 检查 FAISS 索引中是否能 reconstruct 向量

## 日志查看

### Backend 日志

```bash
# 查看 MemGraph 启动日志
cd D:\work\AIGenTest
pnpm dev:backend

# 观察输出
[memgraph] Initializing MemGraph...
[memgraph] Loaded FAISS index with 6 vectors
[memgraph] Syncing 6 existing documents...
[memgraph] Added vector for doc_id=1, faiss_idx=0, norm=1.0000
[memgraph] Added vector for doc_id=2, faiss_idx=1, norm=1.0000
...
[memgraph] MemGraph initialized: 6 documents indexed
```

### 查看持久化数据

```bash
# 检查 SQLite 数据库
cd D:\work\AIGenTest\MemGraph\data
sqlite3 knowledge.db

sqlite> SELECT COUNT(*) FROM documents;
sqlite> SELECT COUNT(*) FROM ngrams;
sqlite> SELECT * FROM documents LIMIT 1;

# 检查 FAISS 索引文件
ls -lh knowledge.faiss
```

## 性能监控

### 向量生成性能

在调试面板点击 **"测试嵌入服务"**，查看耗时：

- **< 100ms**: 优秀
- **100-300ms**: 正常
- **> 500ms**: 需要优化 AI Gateway

### 搜索性能

正常搜索耗时：
- N-gram 激活: ~5ms
- 向量检索: ~5ms
- 总计: ~10-20ms

## 最佳实践

1. **确保 AI Gateway 先启动**，再启动 MemGraph
2. **定期备份** `data/knowledge.db` 和 `data/knowledge.faiss`
3. **首次使用** 先在调试面板测试嵌入服务
4. **索引失败** 查看 backend 日志确认错误原因
5. **搜索异常** 使用调试面板检查向量状态

---

**开发者**: Claude + Human Collaboration
**版本**: V3.0.1
**最后更新**: 2026-01-28
