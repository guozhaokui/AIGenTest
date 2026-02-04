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
            # 提取标题：优先使用第一个一级标题，否则使用文件名
            first_h1 = re.search(r'^#\s+(.+?)$', body, re.MULTILINE)
            if first_h1:
                metadata['title'] = first_h1.group(1).strip()
            else:
                # 从文件名提取（去掉日期时间前缀）
                filename = md_file.stem
                title_from_filename = re.sub(r'^\d{4}[/-]\d{2}[/-]\d{2}[_-]\d{2}[-:]\d{2}[-:]\d{2}[_-]?', '', filename)
                metadata['title'] = title_from_filename if title_from_filename else filename

            # content 包含整个文档内容（保持原始Markdown格式）
            metadata['content'] = body.strip()

            # 构建文档对象
            relative_path = md_file.relative_to(RECORDS_DIR)
            document = {
                'role': metadata.get('role', 'AI'),
                'project': metadata.get('project', ''),
                'directory': metadata.get('directory', ''),
                'timestamp': metadata.get('timestamp', datetime.now().strftime("%Y-%m-%d")),
                'tags': metadata.get('tags', []),
                'title': metadata.get('title', ''),
                'content': metadata.get('content', ''),
                'path': str(relative_path).replace('\\', '/')
            }

            # 索引文档（使用智能方法，自动去重）
            await indexer.index_document_smart(document, save_index=False, generate_ngram_vectors=True, force_update=False)

        except Exception as e:
            print(f"   ⚠️  处理失败: {e}")
            continue

    # 保存索引
    print("\n4. 保存索引...")
    indexer._save_index()
    print("   ✓ 索引已保存")

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
