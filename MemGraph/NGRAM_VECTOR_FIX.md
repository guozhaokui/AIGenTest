# N-gram 向量匹配问题调试报告

## 问题描述

查询 "linux21是什么，linux81呢" 时，debug页面显示"无 N-gram 向量匹配"，即使数据库中确实有包含这些关键词的N-gram。

## 根本原因

经过调查，发现问题的根本原因是：

1. **metadata类型的N-gram没有生成向量**
   - 数据库中有412个metadata类型的N-gram（包括 "linux21"、"linux81"等标题和标签）
   - 但只有34个metadata N-gram有向量（8.3%）
   - 其他378个metadata N-gram没有向量

2. **知识索引器的配置遗漏**
   - 在 `src/knowledge_indexer.py` 的 `_index_ngram_vectors()` 方法中
   - 原来只为 `word_3gram`, `word_4gram`, `sentence` 生成向量
   - **遗漏了 `metadata` 类型**

3. **激活搜索的工作流程**
   - 激活搜索通过精确匹配找到N-gram（如 "linux21"）
   - 然后尝试查找这些N-gram的向量来计算语义相似度
   - 但因为metadata N-gram没有向量，所以JOIN查询返回空结果

## 数据统计

### N-gram类型分布

| 类型 | 总数 | 有向量 | 覆盖率 |
|------|------|--------|--------|
| char_3gram | 12,034 | 1 | 0.008% |
| char_2gram | 11,619 | 1 | 0.009% |
| word_2gram | 2,491 | 3 | 0.1% |
| word_3gram | 2,384 | 1,904 | 79.9% |
| word_4gram | 2,277 | 1,928 | 84.7% |
| **metadata** | **412** | **34** | **8.3%** |
| sentence | 520 | 429 | 82.5% |

### 查询示例验证

```sql
-- 查找包含linux21的N-gram
SELECT content, gram_type FROM ngrams
WHERE content LIKE '%linux21%';

结果:
- linux21 (metadata) - ❌ 无向量
- 是一台局域网电脑，linux系统，因为...所以叫linux21，4090显卡 (sentence) - ❌ 无向量
- 21 linux21 (word_2gram) - ❌ 无向量
- 地址 21 linux21 (word_3gram) - ✅ 有向量
- ip 地址 21 linux21 (word_4gram) - ✅ 有向量
```

## 解决方案

### 1. 代码修复

已修改 `src/knowledge_indexer.py` 第149行：

```python
# 修改前
if gram_type in ('word_3gram', 'word_4gram', 'sentence'):

# 修改后
if gram_type in ('metadata', 'word_3gram', 'word_4gram', 'sentence'):
```

### 2. 数据迁移

创建了迁移脚本 `migrate_add_metadata_vectors.py`，用于为现有的metadata N-gram生成向量。

**运行迁移的前提条件**:
- ⚠️ **必须先停止MemGraph服务器**，否则会遇到 "database is locked" 错误
- 需要可以访问embedding服务（默认 http://127.0.0.1:11434）

**运行命令**:
```bash
# 1. 停止MemGraph服务器
# 2. 运行迁移
cd D:\work\AIGenTest\MemGraph
python migrate_add_metadata_vectors.py

# 3. 重启MemGraph服务器
python src/server.py
```

**迁移预计处理**:
- 378个metadata N-gram需要生成向量
- 预计时间: 约2-3分钟（取决于embedding服务性能）

### 3. 验证步骤

迁移完成后，可以通过以下SQL验证：

```sql
-- 检查metadata向量覆盖率
SELECT
    COUNT(DISTINCT ng.content) as total,
    COUNT(DISTINCT nv.ngram_content) as with_vectors
FROM ngrams ng
LEFT JOIN ngram_vectors nv ON ng.content = nv.ngram_content
WHERE ng.gram_type = 'metadata';

-- 验证linux21是否有向量
SELECT nv.faiss_idx, nv.gram_size
FROM ngram_vectors nv
WHERE nv.ngram_content = 'linux21';
```

## 预期效果

迁移完成后，再次搜索 "linux21是什么，linux81呢"，debug页面应该显示：

### 向量匹配（包含句子）
```
#  内容        类型       向量相似度
1  linux21     metadata   0.xxxx
2  linux81     metadata   0.xxxx
3  地址 21 linux21  word_3gram  0.xxxx
4  ip 地址 21 linux21  word_4gram  0.xxxx
...
```

## 技术说明

### 为什么要为metadata生成向量？

1. **标题和标签的语义搜索**
   - 用户搜索 "linux21" 时，metadata类型的N-gram会被精确匹配
   - 有了向量后，可以计算语义相似度，提高排序准确性
   - 例如："linux21" 和 "linux服务器21" 可能有较高的语义相似度

2. **混合搜索策略**
   - 激活搜索：精确匹配（适合短词）
   - 向量搜索：语义匹配（适合长句）
   - 两者结合：metadata既可以精确匹配，又可以参与语义评分

3. **一致性**
   - 所有被激活的N-gram都应该能参与向量相似度计算
   - 避免出现"找到了匹配但没有向量"的情况

## 后续优化建议

1. **向量生成策略**
   - 考虑是否需要为 `word_2gram` 生成向量（目前只有3个）
   - `char_2gram` 和 `char_3gram` 可能不需要向量（太短，语义信息少）

2. **增量索引**
   - 添加新文档时，自动为所有metadata N-gram生成向量
   - 确保新旧文档的索引一致性

3. **性能优化**
   - 批量生成embedding，减少网络往返
   - 考虑使用embedding cache

## 修改文件列表

- `src/knowledge_indexer.py` - 添加metadata类型到向量生成
- `migrate_add_metadata_vectors.py` - 新增迁移脚本
- `NGRAM_VECTOR_FIX.md` - 本文档

---

**调试时间**: 2026-01-28
**问题发现者**: 用户
**调试人员**: Claude Code
**状态**: ✅ 代码已修复，等待运行迁移
