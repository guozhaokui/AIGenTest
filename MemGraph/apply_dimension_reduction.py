"""
自动应用降维修改到 knowledge_indexer.py
"""
import re

# 读取文件
with open('src/knowledge_indexer.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 替换模式1: self.index.add(xxx); faiss_idx = self.index.ntotal - 1
# 替换为: faiss_idx = self.add_vector_to_index(xxx)

# 先处理简单的情况
replacements = [
    # 模式: embedding.reshape(1, -1)\n    self.index.add(embedding)\n    faiss_idx = self.index.ntotal - 1
    (
        r'(\s+)(embedding(?:_2d)?) = (\w+)\.reshape\(1, -1\)\s+self\.index\.add\(\2\)\s+faiss_idx = self\.index\.ntotal - 1',
        r'\1faiss_idx = self.add_vector_to_index(\3)'
    ),
    # 模式: cached_vector.reshape(1, -1)\n    self.index.add(cached_vector)\n    faiss_idx = self.index.ntotal - 1
    (
        r'(\s+)cached_vector = cached_vector\.reshape\(1, -1\)\s+self\.index\.add\(cached_vector\)\s+faiss_idx = self\.index\.ntotal - 1',
        r'\1faiss_idx = self.add_vector_to_index(cached_vector)'
    ),
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# 特殊处理batch_generate_all_ngram_vectors中的批量添加
# 这里需要对每个向量降维后再vstack

# 写回文件
with open('src/knowledge_indexer.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ 自动替换完成")
print("\n⚠️  请手工检查以下情况：")
print("1. batch_generate_all_ngram_vectors 中的批量添加")
print("2. rebuild_index 中的向量重建")
print("3. 所有存储到数据库的 vector_data")
