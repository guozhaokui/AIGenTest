# 文档去重和更新机制

## 概述

MemGraph 实现了智能文档去重和更新机制，通过 SHA256 内容哈希自动检测重复文档和文档修改。

## 版本历史

- **v1.0** (2026-02-02): 初始实现，支持基于内容哈希的去重和更新

## 核心功能

### 1. 内容哈希 (Content Hash)

每个文档在索引时会计算其内容的 SHA256 哈希值：

```python
full_content = f"{problem}\n\n{solution}"
content_hash = hashlib.sha256(full_content.encode('utf-8')).hexdigest()
```

- 内容完全相同的文档会产生相同的哈希值
- 哈希值存储在 `documents.content_hash` 字段中
- 数据库中对 `content_hash` 建立了索引以提高查询性能

### 2. 智能索引方法

#### `index_document_smart(document, save_index=True, generate_ngram_vectors=True)`

新的智能索引方法会自动处理三种情况：

**情况 1: 相同哈希 → 跳过（不添加重复）**

```python
# 如果内容哈希完全相同（无论路径是否相同）
{
    'action': 'skipped',
    'doc_id': 123,  # 返回已存在的文档ID
    'message': '跳过重复文档 (相同哈希)',
    'old_hash': 'abc123...',
    'new_hash': 'abc123...'
}
```

**情况 2: 同路径不同哈希 → 更新（删除旧版本）**

```python
# 如果路径相同但内容哈希不同（文档被修改）
{
    'action': 'updated',
    'doc_id': 123,  # 原文档ID
    'message': '更新修改的文档',
    'old_hash': 'abc123...',
    'new_hash': 'def456...'
}
```

**情况 3: 新文档 → 添加**

```python
# 如果既不是重复也不是更新
{
    'action': 'added',
    'doc_id': 456,  # 新文档ID
    'message': '添加新文档',
    'new_hash': 'ghi789...'
}
```

### 3. 更新文档流程

#### `update_document_async(doc_id, document, save_index=True, generate_ngram_vectors=True)`

更新已存在文档时的完整流程：

1. **删除旧的 FAISS 向量**
   - 从 `doc_id_to_index` 和 `index_to_doc_id` 映射中移除

2. **删除旧的数据库记录**
   - 删除 `document_vectors` 表中的所有向量
   - 删除 `ngrams` 表中的所有 n-grams
   - 删除 `document_tags` 表中的标签关联

3. **更新文档元数据**
   - 更新 `documents` 表中的所有字段
   - 计算并更新新的 `content_hash`

4. **重新生成内容**
   - 重新插入标签关联
   - 重新生成 n-grams
   - 重新生成文档全文向量
   - 重新生成多粒度向量（段落、句子）
   - 重新生成 n-gram 向量

5. **保存更改**
   - 提交数据库事务
   - 保存 FAISS 索引到磁盘

## API 集成

### `/record` 端点

记录新经验教训时自动使用智能索引：

```python
@app.post("/record")
async def record_lesson(req: RecordLessonRequest):
    # ... 创建文档 ...

    # 使用智能索引（自动去重和更新检测）
    result = await indexer.index_document_smart(document)

    return {
        "success": True,
        "doc_id": result['doc_id'],
        "action": result['action'],  # 'added', 'updated', 或 'skipped'
        "message": result['message'],
        # ...
    }
```

### `/upload` 端点

上传文件时也使用智能索引：

```python
@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # ... 保存文件 ...

    # 使用智能索引（自动去重和更新检测）
    result = await indexer.index_document_smart(document)

    return {
        "success": True,
        "doc_id": result['doc_id'],
        "action": result['action'],
        "message": result['message'],
        # ...
    }
```

### `/update` 端点

显式更新文档时使用独立的更新方法：

```python
@app.post("/update")
async def update_lesson(req: UpdateLessonRequest):
    # ... 获取原文档信息 ...

    # 重新索引文档（会自动删除旧的向量和N-gram）
    await indexer.reindex_document(req.doc_id, document)

    # ...
}
```

## 使用场景

### 场景 1: 防止用户重复提交相同内容

用户在短时间内提交了两次完全相同的经验教训：

```
第一次提交 → action: 'added', doc_id: 443
第二次提交 → action: 'skipped', doc_id: 443 (复用已有文档ID)
```

### 场景 2: 检测并更新修改的文档

用户修改了某个文档的内容后重新提交（路径相同）：

```
原始提交   → action: 'added', doc_id: 443
修改后提交 → action: 'updated', doc_id: 443 (更新原文档)
```

旧的向量、n-grams 会被完全删除，然后重新生成。

### 场景 3: 导入外部文档库

批量导入大量文档时，自动跳过已存在的文档：

```python
for doc in external_docs:
    result = await indexer.index_document_smart(doc)
    if result['action'] == 'skipped':
        print(f"跳过已存在: {doc['problem']}")
    elif result['action'] == 'added':
        print(f"新增: {doc['problem']}")
    elif result['action'] == 'updated':
        print(f"更新: {doc['problem']}")
```

## 数据库模式

```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    role TEXT,
    project TEXT,
    directory TEXT,
    timestamp TEXT,
    tags TEXT,
    problem TEXT,
    solution TEXT,
    full_content TEXT,
    content_hash TEXT  -- SHA256 哈希值
);

CREATE INDEX idx_content_hash ON documents(content_hash);
CREATE INDEX idx_path ON documents(path);
```

## 性能考虑

1. **哈希计算**: SHA256 计算速度很快，对性能影响可忽略
2. **索引查询**: `content_hash` 和 `path` 都有索引，查询速度快
3. **更新开销**: 更新文档时需要删除并重新生成所有向量，开销较大
4. **跳过开销**: 跳过重复文档几乎没有开销，只需数据库查询

## 测试

运行测试脚本验证去重功能：

```bash
python test_deduplication.py
```

测试覆盖：
- ✅ 添加新文档
- ✅ 跳过完全相同的文档
- ✅ 更新同路径不同内容的文档
- ✅ 验证内容和哈希正确更新

## 维护工具

### 查找重复文档

```bash
python find_duplicates.py
```

输出示例：
```
找到 1 组重复文档:

哈希: be45fd2e3921e909... (共 2 个文档)
  - ID: 443
    路径: 2026/01/31_15-40-22_一些常用地址.md
    时间: 2026-01-31T15:40:22.860662
  - ID: 444
    路径: 2026/01/31_15-40-32_一些常用地址.md
    时间: 2026-01-31T15:40:32.420871
```

### 删除重复文档

手动删除指定的重复文档：

```bash
python remove_duplicate.py
```

## 注意事项

1. **内容哈希不包含元数据**: 只计算 `problem + solution` 的哈希，不包含 `tags`, `project` 等元数据
2. **路径变更**: 如果文档内容相同但路径不同，会被识别为重复并跳过
3. **FAISS 索引限制**: FAISS 不支持直接删除向量，更新时旧向量会保留在索引中但从映射中移除
4. **向量缓存**: 相同内容的向量会被缓存复用，减少重复计算

## 未来改进

- [ ] 实现 FAISS 索引的定期重建以清理"幽灵"向量
- [ ] 添加强制重新索引选项（忽略哈希检查）
- [ ] 支持按相似度合并近似重复的文档
- [ ] 记录文档版本历史
- [ ] 添加批量去重 API 端点

## 相关文件

- `src/knowledge_indexer.py`: 核心实现
  - `check_document_exists()`: 检查文档是否存在
  - `index_document_smart()`: 智能索引方法
  - `update_document_async()`: 更新文档方法
- `src/server.py`: API 集成
  - `/record`: 记录经验教训
  - `/upload`: 上传文件
  - `/update`: 更新文档
- `test_deduplication.py`: 测试脚本
- `find_duplicates.py`: 查找重复工具
- `remove_duplicate.py`: 删除重复工具
