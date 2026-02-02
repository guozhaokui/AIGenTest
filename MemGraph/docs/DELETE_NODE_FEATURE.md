# 图谱节点删除功能

## 概述

MemGraph 图谱查看器现在支持直接从可视化界面删除节点（文档），删除操作会：
- 删除物理文件
- 删除数据库记录
- 删除所有向量数据
- 从图谱中移除节点和相关连线

## 版本历史

- **v1.0** (2026-02-02): 初始实现，支持从图谱界面删除节点

## 功能特性

### 1. 用户界面

在图谱查看器中点击任意节点后，节点详情面板会显示：

```
📊 节点信息
  文档ID: xxx
  层级: Layer x
  ...

🔗 展开关联节点
🔍 查看所有关联详情
🗑️ 删除此节点  ← 新增的删除按钮
```

### 2. 删除确认

点击"删除此节点"按钮后，会弹出确认对话框：

```
⚠️ 确定要删除节点吗？

节点: [节点名称]
ID: [文档ID]

此操作将：
• 删除物理文件
• 删除数据库记录
• 删除所有向量数据
• 从图谱中移除节点

此操作不可撤销！

[取消] [确定]
```

### 3. 删除流程

用户确认后，系统执行以下操作：

#### 后端操作 (server.py)

1. **验证文档存在**
   - 检查文档ID是否存在
   - 获取文档路径和基本信息

2. **删除物理文件**
   - 删除 `records/` 目录下的实际文件
   - 如果文件不存在，记录警告但继续

3. **删除 FAISS 向量映射**
   - 从 `doc_id_to_index` 映射中移除
   - 从 `index_to_doc_id` 映射中移除
   - 注意：FAISS 索引本身不支持删除，向量仍保留但不可访问

4. **删除数据库记录**
   - 删除 `document_vectors` 表中的所有向量
   - 删除 `ngrams` 表中的所有 n-grams
   - 删除 `document_tags` 表中的标签关联
   - 删除 `documents` 表中的文档记录

5. **保存更新**
   - 提交数据库事务
   - 保存 FAISS 索引到磁盘

#### 前端操作 (graph-viewer.js)

1. **移除节点**
   - 从 nodes 数据集中删除节点

2. **移除连线**
   - 查找所有与该节点相关的边
   - 从 edges 数据集中删除这些边

3. **更新UI**
   - 清空节点详情面板
   - 显示成功消息
   - 图谱自动重新渲染

## API 端点

### DELETE /document/{doc_id}

删除指定ID的文档。

**请求参数：**
- `doc_id` (path): 文档ID

**响应示例：**

```json
{
    "success": true,
    "doc_id": 456,
    "problem": "测试删除功能...",
    "file_deleted": true,
    "stats": {
        "vectors": 2,
        "ngrams": 65,
        "tags": 2
    }
}
```

**错误响应：**

```json
{
    "detail": "Document 999 not found"
}
```

## 使用场景

### 场景 1: 删除错误或过时的文档

用户在图谱中发现某个文档内容已过时或有错误：

1. 在图谱中搜索并找到该文档节点
2. 点击节点查看详情
3. 确认是要删除的文档
4. 点击"删除此节点"按钮
5. 确认删除操作
6. 节点从图谱中消失

### 场景 2: 清理测试数据

开发或测试过程中创建了一些测试文档：

1. 搜索测试相关的节点
2. 逐个删除测试节点
3. 验证图谱中不再有测试数据

### 场景 3: 删除重复文档

虽然系统现在有去重机制，但对于历史重复数据：

1. 通过 `find_duplicates.py` 找到重复文档
2. 在图谱中查看这些文档
3. 决定保留哪个，删除哪个
4. 通过图谱界面删除不需要的版本

## 代码实现

### 后端实现 (src/server.py)

```python
@app.delete("/document/{doc_id}")
async def delete_document(doc_id: int):
    """删除文档（包括文件、数据库记录和向量）"""
    await ensure_initialized()

    # 1. 获取文档信息
    cursor = indexer.conn.execute(
        'SELECT path, problem FROM documents WHERE id = ?',
        (doc_id,)
    )
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    doc_path, problem = row

    # 2. 删除物理文件
    full_file_path = RECORDS_DIR / doc_path
    file_deleted = False
    if full_file_path.exists():
        try:
            full_file_path.unlink()
            file_deleted = True
        except Exception as e:
            print(f"⚠️  删除文件失败: {e}")

    # 3. 从 FAISS 映射中删除
    if doc_id in indexer.doc_id_to_index:
        old_faiss_idx = indexer.doc_id_to_index[doc_id]
        del indexer.doc_id_to_index[doc_id]
        del indexer.index_to_doc_id[old_faiss_idx]

    # 4. 删除数据库记录
    cursor1 = indexer.conn.execute('DELETE FROM document_vectors WHERE doc_id = ?', (doc_id,))
    deleted_vectors = cursor1.rowcount

    cursor2 = indexer.conn.execute('DELETE FROM ngrams WHERE doc_id = ?', (doc_id,))
    deleted_ngrams = cursor2.rowcount

    cursor3 = indexer.conn.execute('DELETE FROM document_tags WHERE doc_id = ?', (doc_id,))
    deleted_tags = cursor3.rowcount

    indexer.conn.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
    indexer.conn.commit()

    # 5. 保存索引
    indexer._save_index()

    return {
        "success": True,
        "doc_id": doc_id,
        "problem": problem[:50] + "..." if len(problem) > 50 else problem,
        "file_deleted": file_deleted,
        "stats": {
            "vectors": deleted_vectors,
            "ngrams": deleted_ngrams,
            "tags": deleted_tags
        }
    }
```

### 前端实现 (static/graph-viewer.js)

```javascript
// 删除节点
async function deleteNode(docId) {
    const node = nodes.get(docId);
    if (!node) {
        showStatus('❌ 节点不存在', 'error');
        return;
    }

    // 显示确认对话框
    const nodeName = node.label || `文档 ${docId}`;
    const confirmed = confirm(`⚠️ 确定要删除节点吗？\n\n节点: ${nodeName}\nID: ${docId}\n\n此操作将：\n• 删除物理文件\n• 删除数据库记录\n• 删除所有向量数据\n• 从图谱中移除节点\n\n此操作不可撤销！`);

    if (!confirmed) {
        return;
    }

    try {
        showStatus(`🗑️ 正在删除节点 ${docId}...`, 'loading');

        const response = await fetch(`${API_BASE}/document/${docId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || '删除失败');
        }

        if (data.success) {
            // 从图谱中移除节点
            nodes.remove(docId);

            // 移除所有与该节点相关的边
            const connectedEdges = edges.get({
                filter: edge => edge.from === docId || edge.to === docId
            });
            const edgeIds = connectedEdges.map(e => e.id);
            edges.remove(edgeIds);

            // 清空节点信息面板
            const infoEl = document.getElementById('nodeInfo');
            infoEl.innerHTML = '<div class="info-empty">节点已删除</div>';

            // 显示成功消息
            const stats = data.stats;
            showStatus(`✅ 成功删除节点 (向量:${stats.vectors}, n-grams:${stats.ngrams})`, 'success');
        }
    } catch (error) {
        console.error('删除节点失败:', error);
        showStatus(`❌ 删除失败: ${error.message}`, 'error');
    }
}
```

## 测试

运行测试脚本验证删除功能：

```bash
python test_delete_function.py
```

测试覆盖：
- ✅ 创建测试文档
- ✅ 验证文档存在及其关联数据
- ✅ 执行删除操作
- ✅ 验证文档、向量、n-grams、标签全部删除
- ✅ 验证 FAISS 映射删除
- ✅ 验证文档总数正确

## 注意事项

### 1. 不可撤销

删除操作是永久性的，无法撤销。被删除的文档、向量和文件都无法恢复（除非有备份）。

### 2. FAISS 索引限制

FAISS 不支持直接删除向量，已删除文档的向量仍保留在索引文件中，但：
- 从映射中移除，无法通过 doc_id 访问
- 不会影响搜索结果（因为无法映射回文档）
- 占用少量磁盘空间

如需完全清理，可以定期重建 FAISS 索引。

### 3. 文件删除失败

如果物理文件删除失败（如文件被占用、权限不足等），数据库记录仍会被删除。这种情况下：
- `file_deleted` 字段会返回 `false`
- 后端日志会显示警告
- 需要手动删除残留文件

### 4. 图谱刷新

删除节点后，图谱会立即更新，但：
- 如果有多个浏览器标签页打开同一图谱，其他页面不会自动更新
- 需要刷新页面或重新搜索以同步状态

### 5. 关联影响

删除节点后：
- 与该节点相关的所有边都会被移除
- 但其他节点不受影响
- 如果需要查看被删除节点的关联，需要在删除前记录

## 安全考虑

### 1. 权限控制

当前实现没有权限验证。在生产环境中应该：
- 添加用户认证
- 只允许管理员或文档所有者删除
- 记录删除操作的审计日志

### 2. 批量删除

当前只支持单个删除。如需批量删除：
- 可以扩展 API 接受文档ID列表
- 前端添加批量选择功能
- 需要考虑性能和事务一致性

### 3. 软删除

当前是硬删除。考虑实现软删除：
- 添加 `deleted` 标志字段
- 删除时只标记而不真正删除
- 提供恢复功能
- 定期清理过期的软删除记录

## 未来改进

- [ ] 添加回收站功能（软删除）
- [ ] 支持批量删除节点
- [ ] 添加删除操作的审计日志
- [ ] 实现删除前的依赖检查
- [ ] 定期重建 FAISS 索引以清理"幽灵"向量
- [ ] 添加用户权限控制
- [ ] 实现更友好的确认对话框（替代 alert）
- [ ] 支持撤销最近的删除操作

## 相关文件

- `src/server.py`: 后端 API 实现
  - `DELETE /document/{doc_id}`: 删除端点
- `static/graph-viewer.js`: 前端实现
  - `deleteNode(docId)`: 删除函数
- `static/graph-viewer.html`: UI 界面
- `test_delete_function.py`: 测试脚本
- `test_delete_api.py`: API 测试脚本（需要服务器运行）
