"""删除重复文档 ID 444"""
import sys
sys.path.insert(0, 'D:/work/AIGenTest/MemGraph')

from src.knowledge_indexer import KnowledgeIndexer

print("初始化索引器...")
indexer = KnowledgeIndexer()
indexer._load_index()

doc_id = 444

# 1. 检查文档是否存在
cursor = indexer.conn.execute('SELECT id, problem, content_hash FROM documents WHERE id = ?', (doc_id,))
row = cursor.fetchone()

if not row:
    print(f"文档 {doc_id} 不存在")
    sys.exit(1)

print(f"\n找到文档:")
print(f"  ID: {row[0]}")
print(f"  问题: {row[1][:50]}...")
print(f"  哈希: {row[2][:16]}...")

# 2. 删除相关数据
print(f"\n开始删除文档 {doc_id}...")

# 删除文档向量
result = indexer.conn.execute('DELETE FROM document_vectors WHERE doc_id = ?', (doc_id,))
print(f"  删除了 {result.rowcount} 个文档向量")

# 删除 n-grams
result = indexer.conn.execute('DELETE FROM ngrams WHERE doc_id = ?', (doc_id,))
print(f"  删除了 {result.rowcount} 个n-grams")

# 删除标签关联
result = indexer.conn.execute('DELETE FROM document_tags WHERE doc_id = ?', (doc_id,))
print(f"  删除了 {result.rowcount} 个标签关联")

# 删除文档记录
result = indexer.conn.execute('DELETE FROM documents WHERE id = ?', (doc_id,))
print(f"  删除了 {result.rowcount} 个文档记录")

# 从映射中删除
if doc_id in indexer.doc_id_to_index:
    old_faiss_idx = indexer.doc_id_to_index[doc_id]
    del indexer.doc_id_to_index[doc_id]
    del indexer.index_to_doc_id[old_faiss_idx]
    print(f"  删除了FAISS映射 (idx={old_faiss_idx})")

# 提交更改
indexer.conn.commit()
print(f"\n✅ 成功删除文档 {doc_id}")

# 3. 验证删除
cursor = indexer.conn.execute('SELECT COUNT(*) FROM documents WHERE content_hash = ?', (row[2],))
count = cursor.fetchone()[0]
print(f"\n验证: 现在有 {count} 个文档具有相同的哈希")
