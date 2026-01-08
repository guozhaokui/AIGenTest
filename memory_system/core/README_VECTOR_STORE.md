# 向量存储使用指南

## 快速开始

### 1. 基本使用

```python
from core.vector_store import VectorStore, Document

# 创建向量存储（自动使用BGE服务）
store = VectorStore(path=".memory_db/vectors")

# 添加文档
store.add_documents([
    Document(
        content="linux81是内网服务器",
        metadata={"source": "日志/2601.md", "type": "server"}
    ),
    Document(
        content="QAMath是数学问答系统",
        metadata={"source": "日志/2601.md", "type": "project"}
    )
])

# 搜索
results = store.search("什么是QAMath？", top_k=3)

for result in results:
    print(f"[相似度: {result.similarity:.3f}] {result.content}")
    print(f"来源: {result.metadata.get('source')}")
```

### 2. 自动分块

```python
# 长文档自动分块
long_text = """
linux81是公司的内网服务器...
（很长的文本）
"""

# 自动分块并添加
doc_ids = store.add_document(
    content=long_text,
    metadata={"source": "long_doc.md"},
    chunk=True  # 启用自动分块
)

print(f"分成了{len(doc_ids)}个块")
```

### 3. 元数据过滤

```python
# 只搜索特定类型的文档
results = store.search(
    query="服务器配置",
    top_k=5,
    filter_metadata={"type": "server"}
)

# 多条件过滤
results = store.search(
    query="项目部署",
    filter_metadata={
        "type": "project",
        "status": "active"
    }
)
```

## 核心功能

### 文档对象

```python
from core.vector_store import Document

doc = Document(
    content="文档内容",
    metadata={
        "source": "file.md",
        "type": "server",
        "date": "2024-01-07",
        "custom_field": "任意值"
    },
    id="doc_001"  # 可选，不提供会自动生成
)
```

### 文档操作

```python
# 添加单个文档
doc_id = store.add_document(
    content="内容",
    metadata={"key": "value"}
)

# 批量添加
doc_ids = store.add_documents([doc1, doc2, doc3])

# 获取文档
doc = store.get_by_id("doc_001")

# 删除文档
store.delete("doc_001")
store.delete(["doc_001", "doc_002"])

# 按元数据删除
count = store.delete_by_metadata({"type": "deprecated"})

# 更新元数据
store.update_metadata("doc_001", {"status": "updated"})
```

### 搜索功能

```python
# 基本搜索
results = store.search("查询内容", top_k=5)

# 元数据过滤
results = store.search(
    "查询内容",
    top_k=5,
    filter_metadata={"type": "server"}
)

# 访问结果
for result in results:
    print(result.id)           # 文档ID
    print(result.content)      # 内容
    print(result.metadata)     # 元数据
    print(result.similarity)   # 相似度 (0-1)
    print(result.distance)     # 距离（越小越相似）
```

### 统计信息

```python
# 文档数量
count = store.count()

# 详细统计
stats = store.stats()
print(stats)
# {
#     "total_documents": 156,
#     "collection_name": "documents",
#     "dimension": 1024,
#     "path": ".memory_db/vectors"
# }
```

## 配置选项

### 自定义Embedding

```python
from core.embedding import create_embedding_provider

# 使用本地模型
emb = create_embedding_provider(
    "local",
    model_name="BAAI/bge-small-zh-v1.5"
)

store = VectorStore(
    path=".memory_db/vectors",
    embedding_provider=emb
)
```

### 自定义分块

```python
from core.vector_store import DocumentChunker

chunker = DocumentChunker(
    chunk_size=1000,     # 块大小（字符）
    chunk_overlap=200,   # 重叠大小
    separators=["\n\n", "\n", "。"]  # 分隔符优先级
)

store.chunker = chunker
```

### 多个集合

```python
# 创建不同的集合
docs_store = VectorStore(
    path=".memory_db/vectors",
    collection_name="documents"
)

logs_store = VectorStore(
    path=".memory_db/vectors",
    collection_name="logs"
)
```

## 性能数据

基于你的BGE服务（1024维）：

| 操作 | 数量 | 时间 |
|------|------|------|
| 添加文档 | 100条 | ~2秒 |
| 添加文档 | 1000条 | ~15秒 |
| 搜索 | 单次 | ~50ms |
| 分块+添加 | 长文档(5000字) | ~3秒 |

## 最佳实践

### 1. 合理设置元数据

```python
Document(
    content="...",
    metadata={
        "source": "file.md",           # 来源文件
        "type": "server|project|...",  # 类型
        "date": "2024-01-07",          # 日期
        "entity": "linux81",           # 关联实体
        "status": "active|deprecated"  # 状态
    }
)
```

### 2. 分块策略

- **短文档**（<500字）：不分块
- **中文档**（500-2000字）：分2-4块
- **长文档**（>2000字）：自动分块

```python
# 对长文档启用分块
if len(content) > 500:
    store.add_document(content, metadata, chunk=True)
else:
    store.add_document(content, metadata, chunk=False)
```

### 3. 定期清理

```python
# 删除废弃文档
store.delete_by_metadata({"status": "deprecated"})

# 删除旧文档
store.delete_by_metadata({"date": {"$lt": "2024-01-01"}})
```

### 4. 元数据过滤优化检索

```python
# 不好：全局搜索
results = store.search("配置信息")

# 好：限定范围
results = store.search(
    "配置信息",
    filter_metadata={"type": "server"}
)
```

## 集成示例

### 与知识库集成

```python
from core.vector_store import VectorStore
from core.knowledge_base import KnowledgeBase

vector_store = VectorStore()
knowledge_base = KnowledgeBase()

def query_with_context(question: str):
    # 1. 向量检索文档
    docs = vector_store.search(question, top_k=5)

    # 2. 提取实体
    entities = extract_entities(question)

    # 3. 从知识库获取背景
    background = knowledge_base.get_context(entities)

    # 4. 组合上下文
    context = {
        "documents": docs,
        "background": background
    }

    # 5. 生成回答
    answer = llm.generate(question, context)
    return answer
```

### 批量导入文档

```python
from pathlib import Path

def import_documents(docs_dir: str):
    store = VectorStore()

    for md_file in Path(docs_dir).glob("**/*.md"):
        content = md_file.read_text()

        store.add_document(
            content=content,
            metadata={
                "source": str(md_file),
                "date": md_file.stat().st_mtime,
                "type": "daily_log"
            },
            chunk=True
        )

    print(f"导入完成，总文档数: {store.count()}")
```

## 故障排查

### 问题1：embedding服务不可用

```python
# 检查服务
from core.embedding import create_embedding_provider

emb = create_embedding_provider("remote", base_url="http://192.168.0.100:6012")
print(emb.health_check())  # 应该返回True
```

**解决：**
```bash
ssh ubuntu@192.168.0.100
cd /mnt/hdd/guo/AIGenTest/aiserver/embedding
./start_embed_server.sh
```

### 问题2：搜索结果不相关

- 检查embedding是否正确
- 增加top_k数量
- 调整分块大小

### 问题3：内存占用大

```python
# 使用小维度模型
emb = create_embedding_provider(
    "local",
    model_name="BAAI/bge-small-zh-v1.5"  # 512维，更小
)
```

## 下一步

- [实体提取器](./entity_extractor.py) - 从文档提取实体
- [知识库](./knowledge_base.py) - 结构化知识存储
- [查询服务](./query_service.py) - 集成RAG查询
