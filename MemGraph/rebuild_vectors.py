"""
重建向量索引
"""
import asyncio
import sys
sys.path.insert(0, '.')

from src.knowledge_indexer import KnowledgeIndexer
from src.config import RECORDS_DIR

async def main():
    print("=" * 80)
    print("重建向量索引")
    print("=" * 80)

    # 初始化索引器
    print("\n1. 初始化索引器...")
    indexer = KnowledgeIndexer()

    # 清除现有数据
    print("\n2. 清除现有数据...")
    indexer.clear_all()

    # 扫描文档
    print("\n3. 扫描文档...")
    import re
    from datetime import datetime

    all_files = list(RECORDS_DIR.rglob("*.md"))
    total_files = len(all_files)
    print(f"   找到 {total_files} 个 markdown 文件")

    # 处理每个文档
    for idx, md_file in enumerate(all_files, 1):
        try:
            print(f"\n   处理 {idx}/{total_files}: {md_file.name}")

            content = md_file.read_text(encoding='utf-8')

            # 解析frontmatter
            metadata = {}
            body = content

            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    frontmatter = parts[1]
                    body = parts[2]

                    # 解析元数据
                    for line in frontmatter.strip().split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            key = key.strip()
                            value = value.strip()

                            if key == 'tags':
                                value = [t.strip() for t in value.strip('[]').split(',')]
                            metadata[key] = value

            # 解析文档内容
            problem_match = re.search(r'## 问题\s*\n+(.*?)(?=\n##|\Z)', body, re.DOTALL)
            solution_match = re.search(r'## 解决[方法办]*\s*\n+(.*)', body, re.DOTALL)

            if problem_match or solution_match:
                metadata['problem'] = problem_match.group(1).strip() if problem_match else ''
                metadata['solution'] = solution_match.group(1).strip() if solution_match else ''
            else:
                # 没有标准格式，整体作为solution
                metadata['solution'] = body.strip()

            # 构建文档对象
            document = {
                'role': metadata.get('role', 'AI'),
                'project': metadata.get('project', ''),
                'directory': metadata.get('directory', ''),
                'timestamp': metadata.get('timestamp', datetime.now().strftime("%Y-%m-%d")),
                'tags': metadata.get('tags', []),
                'problem': metadata.get('problem', ''),
                'solution': metadata.get('solution', ''),
                'path': str(md_file.relative_to(RECORDS_DIR))
            }

            # 索引文档
            await indexer.index_document(document)

        except Exception as e:
            print(f"   ⚠️  处理失败: {e}")
            continue

    # 获取统计
    print("\n" + "=" * 80)
    print("重建完成！")
    stats = indexer.get_stats()
    print(f"   文档数: {stats['documents']}")
    print(f"   N-grams: {stats['ngrams']}")
    print(f"   FAISS向量: {stats['faiss_vectors']}")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
