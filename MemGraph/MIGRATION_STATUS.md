# Metadata N-gram 向量迁移状态

## 迁移尝试记录

### 第一次迁移 (beec971)
- **时间**: 刚才
- **状态**: ❌ 大部分失败
- **成功**: 11/211 (5.2%)
- **失败**: 200 (94.8%) - database is locked
- **原因**: MemGraph服务器正在运行，数据库被锁定

### 第二次迁移 (b3e0054)
- **时间**: 刚才
- **状态**: ⚠️ 部分成功
- **成功**: 146/211 (69.2%)
- **失败**: 65 (30.8%) - database is locked
- **原因**: MemGraph服务器仍在运行

## 关键问题

**linux21 和 linux81 仍然没有向量！**

```
linux21    ❌ No vector found
linux81    ❌ No vector found
```

这两个关键词在两次迁移中都失败了，因为它们出现在失败列表中：
- 第一次迁移 line 35-36: 'linux21' 和 'linux81' - database is locked
- 第二次迁移: 同样失败

## 当前统计

| 类型 | 总数 | 有向量 | 覆盖率 |
|------|------|--------|--------|
| metadata | 245 | 34 | 13.9% |
| sentence | 434 | 429 | 98.8% |
| word_3gram | 2103 | 1904 | 90.5% |
| word_4gram | 2123 | 1928 | 90.8% |

**问题**: metadata覆盖率只有13.9%，还有211个metadata N-gram没有向量

## 需要采取的行动

### ⚠️ 必须先停止MemGraph服务器！

**步骤**:

1. **停止MemGraph服务器**
   ```bash
   # 查找Python进程
   tasklist | findstr python
   
   # 如果服务器在端口8800运行，停止它
   # 或者直接Ctrl+C停止服务器
   ```

2. **等待数据库完全释放**
   ```bash
   # 等待几秒钟，确保数据库连接关闭
   ```

3. **重新运行迁移**
   ```bash
   cd D:\work\AIGenTest\MemGraph
   python migrate_add_metadata_vectors.py
   ```
   
   **预期结果**:
   - 应该成功处理剩余的 ~200 个metadata N-gram
   - 包括 linux21 和 linux81
   - 不会再有 "database is locked" 错误

4. **验证结果**
   ```python
   import sqlite3
   conn = sqlite3.connect('data/knowledge.db')
   
   # 验证linux21和linux81有向量
   for term in ['linux21', 'linux81']:
       cursor = conn.execute(
           'SELECT faiss_idx FROM ngram_vectors WHERE ngram_content = ?',
           (term,)
       )
       result = cursor.fetchone()
       print(f'{term}: {"✅ 有向量" if result else "❌ 无向量"}')
   ```

5. **重启MemGraph服务器**
   ```bash
   python src/server.py
   ```

6. **测试查询**
   - 打开 http://localhost:8800/static/debug.html
   - 搜索 "linux21是什么，linux81呢"
   - 检查 "向量匹配" 部分
   - 应该看到 linux21 和 linux81 及其相似度分数

## 为什么会失败？

SQLite 在多进程访问时使用文件锁机制：
- MemGraph服务器打开了数据库连接（reader）
- 迁移脚本需要写入数据库（writer）
- SQLite不允许在有reader时进行write操作
- 结果: `database is locked`

**解决方案**: 停止所有使用数据库的进程，然后运行迁移。

## 下次迁移注意事项

1. ✅ 代码已修复 (`src/knowledge_indexer.py` 已添加metadata支持)
2. ✅ 迁移脚本已创建 (`migrate_add_metadata_vectors.py`)
3. ⚠️ **必须停止服务器才能运行迁移**
4. ✅ 迁移完成后，新添加的文档会自动为metadata N-gram生成向量

## 技术细节

### 为什么有些迁移成功了？

观察到的现象:
- 第一次: 11/211 成功
- 第二次: 146/211 成功

可能原因:
1. 数据库锁是暂时的，在某些时刻释放
2. SQLite的WAL模式允许部分并发操作
3. 迁移脚本在某些N-gram上成功获得了写锁

但这不可靠！正确做法是停止服务器。

### FAISS索引状态

```
初始: 420 vectors
第一次迁移后: 420 + 11 = 431 vectors
第二次迁移后: 631 vectors (增加了200个)
```

这表明第二次迁移确实添加了很多向量，但不包括linux21和linux81。

---

**创建时间**: 2026-01-28
**状态**: ⚠️ 等待停止服务器后重新运行迁移
**关键目标**: 为 linux21 和 linux81 生成向量
