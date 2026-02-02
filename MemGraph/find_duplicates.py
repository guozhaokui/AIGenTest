"""查找重复文档"""
import sys
import sqlite3
sys.path.insert(0, 'D:/work/AIGenTest/MemGraph')

conn = sqlite3.connect('data/knowledge.db')

# 查找所有有相同 content_hash 的文档
cursor = conn.execute('''
    SELECT content_hash, COUNT(*) as count
    FROM documents
    WHERE content_hash IS NOT NULL AND content_hash != ''
    GROUP BY content_hash
    HAVING count > 1
''')

duplicates = cursor.fetchall()

if duplicates:
    print(f"找到 {len(duplicates)} 组重复文档:\n")

    for content_hash, count in duplicates:
        print(f"哈希: {content_hash[:16]}... (共 {count} 个文档)")

        # 获取这组重复文档的详细信息
        cursor2 = conn.execute('''
            SELECT id, path, problem, timestamp
            FROM documents
            WHERE content_hash = ?
            ORDER BY id
        ''', (content_hash,))

        docs = cursor2.fetchall()
        for doc_id, path, problem, timestamp in docs:
            print(f"  - ID: {doc_id}")
            print(f"    路径: {path}")
            print(f"    问题: {problem[:50]}...")
            print(f"    时间: {timestamp}")
        print()
else:
    print("没有找到重复文档")

conn.close()
