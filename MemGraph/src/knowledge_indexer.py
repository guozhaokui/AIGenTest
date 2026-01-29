"""
知识索引器
负责构建和维护知识图谱索引 (FAISS + SQLite)
"""
import sqlite3
import json
import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from .config import (
    FAISS_INDEX_PATH, METADATA_DB_PATH, EMBED_DIMENSION
)
from .ngram_processor import NgramProcessor
from .embedding_client import EmbeddingClient


class KnowledgeIndexer:
    """知识索引器"""

    def __init__(self):
        self.ngram_processor = NgramProcessor()
        self.embedding_client = EmbeddingClient()

        # FAISS索引
        self.index: Optional[faiss.Index] = None
        self.doc_id_to_index = {}  # doc_id -> FAISS index
        self.index_to_doc_id = {}  # FAISS index -> doc_id

        # 向量缓存（避免频繁 reconstruct 导致 Segmentation Fault）
        self.vector_cache = {}  # {faiss_idx: numpy.ndarray}

        # SQLite连接
        self.db_path = str(METADATA_DB_PATH)
        self.conn: Optional[sqlite3.Connection] = None

        self._init_db()
        self._load_index()

    def _init_db(self):
        """初始化数据库"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row

        # 文档表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                role TEXT,
                project TEXT,
                directory TEXT,
                timestamp TEXT,
                tags TEXT,
                problem TEXT,
                solution TEXT,
                full_content TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # N-gram表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS ngrams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                gram_type TEXT NOT NULL,
                gram_size INTEGER NOT NULL,
                section TEXT,
                position INTEGER,
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')

        # 创建索引
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_ngrams_content ON ngrams(content)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_ngrams_doc_id ON ngrams(doc_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_ngrams_type ON ngrams(gram_type)')

        # 标签表
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS document_tags (
                doc_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (doc_id, tag),
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')

        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_tags_tag ON document_tags(tag)')

        # N-gram 向量表（用于 5-gram 以上的语义向量）
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS ngram_vectors (
                ngram_content TEXT PRIMARY KEY,
                faiss_idx INTEGER UNIQUE,
                gram_size INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 文档多粒度向量表（用于存储文档的段落、句子级向量）
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS document_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                granularity TEXT NOT NULL,
                content TEXT NOT NULL,
                faiss_idx INTEGER UNIQUE,
                position INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        ''')

        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_vectors_doc_id ON document_vectors(doc_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_vectors_granularity ON document_vectors(granularity)')

        self.conn.commit()

    def _load_index(self):
        """加载FAISS索引"""
        if FAISS_INDEX_PATH.exists():
            try:
                self.index = faiss.read_index(str(FAISS_INDEX_PATH))
                print(f"Loaded FAISS index with {self.index.ntotal} vectors")

                # 重建映射
                cursor = self.conn.execute('SELECT id FROM documents ORDER BY id')
                for idx, row in enumerate(cursor.fetchall()):
                    doc_id = row[0]
                    self.doc_id_to_index[doc_id] = idx
                    self.index_to_doc_id[idx] = doc_id

            except Exception as e:
                print(f"Failed to load FAISS index: {e}")
                self._create_new_index()
        else:
            self._create_new_index()

    def _create_new_index(self):
        """创建新的FAISS索引"""
        # 使用 IndexFlatIP (内积，适合归一化后的向量)
        self.index = faiss.IndexFlatIP(EMBED_DIMENSION)
        print(f"Created new FAISS index (dimension: {EMBED_DIMENSION})")

    def _save_index(self):
        """保存FAISS索引"""
        if self.index:
            faiss.write_index(self.index, str(FAISS_INDEX_PATH))

    def get_vector(self, faiss_idx: int) -> np.ndarray:
        """
        安全地获取向量（使用缓存避免 reconstruct 崩溃）

        Args:
            faiss_idx: FAISS 索引位置

        Returns:
            向量 (numpy array)
        """
        # 检查缓存
        if faiss_idx in self.vector_cache:
            return self.vector_cache[faiss_idx]

        # 如果不在缓存，reconstruct 并缓存
        try:
            vector = self.index.reconstruct(int(faiss_idx))
            # 缓存向量（限制缓存大小，避免内存溢出）
            if len(self.vector_cache) < 10000:  # 最多缓存 10000 个向量
                self.vector_cache[faiss_idx] = vector
            return vector
        except Exception as e:
            print(f"Warning: Failed to reconstruct vector at index {faiss_idx}: {e}")
            # 返回零向量作为fallback
            return np.zeros(EMBED_DIMENSION, dtype=np.float32)

    async def batch_generate_all_ngram_vectors(self):
        """
        批量生成所有未生成向量的 N-gram

        从数据库中查找所有需要向量但还没有向量的 N-gram，
        然后批量生成它们的向量（去重）
        """
        print("🔍 查找需要生成向量的 N-gram...")

        # 查询所有需要向量但还没有向量的 N-gram
        cursor = self.conn.execute('''
            SELECT DISTINCT content, gram_size
            FROM ngrams
            WHERE gram_type IN ('metadata', 'word_3gram', 'word_4gram', 'sentence')
            AND content NOT IN (SELECT ngram_content FROM ngram_vectors)
            ORDER BY gram_size DESC, content
        ''')

        pending_ngrams = cursor.fetchall()

        if not pending_ngrams:
            print("✅ 所有 N-gram 都已有向量")
            return

        total = len(pending_ngrams)
        print(f"📊 找到 {total} 个需要生成向量的 N-gram")

        # 批量生成向量（先收集，再一次性添加到 FAISS）
        batch_size = 10  # 每10个打印一次进度
        embeddings_to_add = []  # 收集所有向量
        metadata_to_insert = []  # 收集数据库记录

        current_faiss_size = self.index.ntotal  # 记录当前 FAISS 大小

        for idx, (content, gram_size) in enumerate(pending_ngrams, 1):
            try:
                # 生成嵌入向量
                embedding = await self.embedding_client.embed_text(content)

                # 归一化
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                # 收集向量（不立即添加到 FAISS）
                embeddings_to_add.append(embedding)

                # 计算这个向量在 FAISS 中的索引（基于收集顺序）
                faiss_idx = current_faiss_size + len(embeddings_to_add) - 1

                # 收集数据库记录
                metadata_to_insert.append((content, faiss_idx, gram_size))

                if idx % batch_size == 0 or idx == total:
                    print(f"  ⚡ 已生成 {idx}/{total} 个向量 ({idx*100//total}%)")

            except Exception as e:
                print(f"⚠️  生成向量失败: '{content[:30]}...' - {e}")

        # 一次性批量添加所有向量到 FAISS（避免多次内存重分配）
        if embeddings_to_add:
            print(f"💾 批量添加 {len(embeddings_to_add)} 个向量到 FAISS 索引...")
            embeddings_matrix = np.vstack(embeddings_to_add).astype('float32')
            self.index.add(embeddings_matrix)
            print(f"✅ FAISS 索引添加完成")

        # 批量插入数据库记录
        if metadata_to_insert:
            print(f"💾 批量保存元数据到数据库...")
            self.conn.executemany('''
                INSERT OR IGNORE INTO ngram_vectors (ngram_content, faiss_idx, gram_size)
                VALUES (?, ?, ?)
            ''', metadata_to_insert)

        self.conn.commit()
        print(f"✅ 批量生成完成！共生成 {total} 个 N-gram 向量")

    def _split_document_into_chunks(self, full_content: str) -> Dict[str, List[str]]:
        """
        将文档分割成多粒度的文本块

        Returns:
            {
                'paragraphs': [段落1, 段落2, ...],
                'sentences': [句子1, 句子2, ...]
            }
        """
        import re

        chunks = {
            'paragraphs': [],
            'sentences': []
        }

        # 1. 分割段落（按双换行符或Markdown标题）
        # 匹配 Markdown 标题 (##, ###) 或双换行
        paragraph_pattern = r'(?:^|\n)(?:#{1,6}\s+.+?\n|.+?\n\n)'
        paragraphs = re.split(r'\n\s*\n+', full_content)

        for para in paragraphs:
            para = para.strip()
            if len(para) >= 20:  # 只保留足够长的段落
                chunks['paragraphs'].append(para)

        # 2. 分割句子（按中文句号、英文句号、换行）
        sentence_pattern = r'[。！？\.\!\?\n]+'
        sentences = re.split(sentence_pattern, full_content)

        for sent in sentences:
            sent = sent.strip()
            # 只保留10-500字符的句子
            if 10 <= len(sent) <= 500:
                chunks['sentences'].append(sent)

        return chunks

    async def _index_document_vectors(self, doc_id: int, full_content: str):
        """
        为文档生成多粒度向量

        Args:
            doc_id: 文档ID
            full_content: 文档完整内容

        粒度:
            1. full: 整篇文档向量（已在 index_document 中生成）
            2. paragraph: 段落级向量
            3. sentence: 重要句子向量
        """
        print(f"  🔍 生成文档 {doc_id} 的多粒度向量...")

        # 分割文档
        chunks = self._split_document_into_chunks(full_content)

        total_vectors = 0

        # 生成段落向量
        for i, para_content in enumerate(chunks['paragraphs']):
            try:
                embedding = await self.embedding_client.embed_text(para_content)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                # 添加到FAISS
                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)
                faiss_idx = self.index.ntotal - 1

                # 保存到数据库
                self.conn.execute('''
                    INSERT INTO document_vectors (doc_id, granularity, content, faiss_idx, position)
                    VALUES (?, ?, ?, ?, ?)
                ''', (doc_id, 'paragraph', para_content, faiss_idx, i))

                total_vectors += 1

            except Exception as e:
                print(f"    ⚠️  段落 {i} 向量生成失败: {e}")

        # 生成句子向量（取所有句子）
        for i, sent_content in enumerate(chunks['sentences']):
            try:
                embedding = await self.embedding_client.embed_text(sent_content)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                # 添加到FAISS
                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)
                faiss_idx = self.index.ntotal - 1

                # 保存到数据库
                self.conn.execute('''
                    INSERT INTO document_vectors (doc_id, granularity, content, faiss_idx, position)
                    VALUES (?, ?, ?, ?, ?)
                ''', (doc_id, 'sentence', sent_content, faiss_idx, i))

                total_vectors += 1

            except Exception as e:
                print(f"    ⚠️  句子 {i} 向量生成失败: {e}")

        self.conn.commit()
        print(f"    ✓ 共生成 {total_vectors} 个多粒度向量 (段落: {len(chunks['paragraphs'])}, 句子: {len(chunks['sentences'])})")

    async def _index_ngram_vectors(self, ngrams: List[Dict]):
        """
        为长 N-gram 片段生成向量（去重）

        生成向量的条件:
        - metadata (项目名、标签、标题等元数据)
        - word_3gram, word_4gram (3-4个词的短语)
        - sentence (句子级别)

        Args:
            ngrams: N-gram 列表
        """
        # 收集符合条件的唯一片段
        unique_ngrams = {}
        for ngram in ngrams:
            gram_type = ngram['gram_type']
            # 为 metadata, word_3gram, word_4gram, sentence 生成向量
            if gram_type in ('metadata', 'word_3gram', 'word_4gram', 'sentence'):
                content = ngram['content']
                if content not in unique_ngrams:
                    unique_ngrams[content] = ngram['gram_size']

        if not unique_ngrams:
            print("No eligible n-grams found for vectorization")
            return

        print(f"Found {len(unique_ngrams)} unique eligible n-grams")

        # 检查哪些片段还没有向量
        new_ngrams = []
        for content in unique_ngrams.keys():
            cursor = self.conn.execute(
                'SELECT faiss_idx FROM ngram_vectors WHERE ngram_content = ?',
                (content,)
            )
            if cursor.fetchone() is None:
                new_ngrams.append(content)

        if not new_ngrams:
            return

        print(f"Generating vectors for {len(new_ngrams)} new ngrams (size >= 5)...")

        # 批量生成向量
        for content in new_ngrams:
            try:
                embedding = await self.embedding_client.embed_text(content)

                # 归一化
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                # 添加到 FAISS
                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)

                faiss_idx = self.index.ntotal - 1

                # 记录到数据库
                self.conn.execute('''
                    INSERT OR IGNORE INTO ngram_vectors (ngram_content, faiss_idx, gram_size)
                    VALUES (?, ?, ?)
                ''', (content, faiss_idx, unique_ngrams[content]))

            except Exception as e:
                print(f"Warning: Failed to generate embedding for ngram '{content[:30]}...': {e}")

    async def index_document(self, document: Dict, save_index: bool = True, generate_ngram_vectors: bool = True) -> int:
        """
        索引单个文档

        Args:
            document: 文档字典
            save_index: 是否立即保存FAISS索引（批量操作时设为False以提高性能）
            generate_ngram_vectors: 是否生成N-gram向量（批量操作时设为False，最后统一生成）

        Returns:
            文档ID
        """
        # 1. 插入文档
        tags_str = ','.join(document.get('tags', []))
        full_content = f"{document.get('problem', '')}\n\n{document.get('solution', '')}"

        cursor = self.conn.execute('''
            INSERT INTO documents (path, role, project, directory, timestamp, tags, problem, solution, full_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            document['path'],
            document.get('role', 'AI'),
            document.get('project', ''),
            document.get('directory', ''),
            document.get('timestamp', ''),
            tags_str,
            document.get('problem', ''),
            document.get('solution', ''),
            full_content
        ))

        doc_id = cursor.lastrowid

        # 2. 插入标签
        for tag in document.get('tags', []):
            self.conn.execute(
                'INSERT OR IGNORE INTO document_tags (doc_id, tag) VALUES (?, ?)',
                (doc_id, tag)
            )

        # 3. 生成n-gram
        ngrams = self.ngram_processor.process_document(document)

        # 4. 插入n-gram
        for ngram in ngrams:
            self.conn.execute('''
                INSERT INTO ngrams (doc_id, content, gram_type, gram_size, section, position)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                doc_id,
                ngram['content'],
                ngram['gram_type'],
                ngram['gram_size'],
                ngram['section'],
                ngram['position']
            ))

        # 5. 生成文档嵌入向量
        try:
            embedding = await self.embedding_client.embed_text(full_content)

            # 归一化向量 (用于余弦相似度)
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            # 添加到FAISS索引
            embedding = embedding.reshape(1, -1)
            self.index.add(embedding)

            # 更新映射
            faiss_idx = self.index.ntotal - 1
            self.doc_id_to_index[doc_id] = faiss_idx
            self.index_to_doc_id[faiss_idx] = doc_id

            print(f"Added vector for doc_id={doc_id}, faiss_idx={faiss_idx}, norm={norm:.4f}")

        except Exception as e:
            print(f"Warning: Failed to generate embedding for doc_id={doc_id}: {e}")
            print("Document indexed without vector embedding")

        # 6. 生成文档多粒度向量（段落、句子）
        await self._index_document_vectors(doc_id, full_content)

        # 7. 为 word_3gram, word_4gram, sentence 生成向量（去重）
        if generate_ngram_vectors:
            print(f"Calling _index_ngram_vectors with {len(ngrams)} ngrams")
            await self._index_ngram_vectors(ngrams)

        self.conn.commit()

        # 保存FAISS索引到磁盘（可选）
        if save_index:
            self._save_index()

        return doc_id

    async def index_documents(self, documents: List[Dict]) -> List[int]:
        """
        批量索引文档

        Args:
            documents: 文档列表

        Returns:
            文档ID列表
        """
        doc_ids = []

        for doc in documents:
            try:
                doc_id = await self.index_document(doc)
                doc_ids.append(doc_id)
                print(f"Indexed document: {doc['path']}")
            except Exception as e:
                print(f"Failed to index {doc.get('path')}: {e}")

        # 保存FAISS索引
        self._save_index()

        return doc_ids

    async def reindex_document(self, doc_id: int, document: Dict):
        """
        重新索引已有文档（删除旧索引，创建新索引）

        Args:
            doc_id: 文档ID
            document: 新的文档数据
        """
        print(f"Reindexing document {doc_id}...")

        # 1. 删除旧的 N-gram 记录
        self.conn.execute('DELETE FROM ngrams WHERE doc_id = ?', (doc_id,))

        # 2. 删除旧的文档向量（段落、句子）
        self.conn.execute('DELETE FROM document_vectors WHERE doc_id = ?', (doc_id,))

        # 3. 删除旧的标签关联
        self.conn.execute('DELETE FROM document_tags WHERE doc_id = ?', (doc_id,))

        # 4. 更新文档记录
        tags_str = ','.join(document.get('tags', []))
        full_content = f"{document.get('problem', '')}\n\n{document.get('solution', '')}"

        self.conn.execute('''
            UPDATE documents
            SET role = ?, project = ?, directory = ?, timestamp = ?,
                tags = ?, problem = ?, solution = ?, full_content = ?
            WHERE id = ?
        ''', (
            document.get('role', 'AI'),
            document.get('project', ''),
            document.get('directory', ''),
            document.get('timestamp', ''),
            tags_str,
            document.get('problem', ''),
            document.get('solution', ''),
            full_content,
            doc_id
        ))

        # 5. 插入新的标签
        for tag in document.get('tags', []):
            self.conn.execute(
                'INSERT OR IGNORE INTO document_tags (doc_id, tag) VALUES (?, ?)',
                (doc_id, tag)
            )

        # 6. 生成新的 N-gram
        ngrams = self.ngram_processor.process_document(document)

        for ngram in ngrams:
            self.conn.execute('''
                INSERT INTO ngrams (doc_id, content, gram_type, gram_size, section, position)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                doc_id,
                ngram['content'],
                ngram['gram_type'],
                ngram['gram_size'],
                ngram['section'],
                ngram['position']
            ))

        # 7. 更新文档向量（整篇）
        try:
            embedding = await self.embedding_client.embed_text(full_content)

            # 归一化
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

            # 获取旧的 FAISS 索引位置
            if doc_id in self.doc_id_to_index:
                faiss_idx = self.doc_id_to_index[doc_id]

                # 直接覆盖 FAISS 向量（使用 reconstruct_n 和 add）
                # 注意：FAISS IndexFlatIP 不支持原地修改，只能通过重建实现
                # 这里我们保持原 faiss_idx 不变，重建索引时会覆盖
                embedding_2d = embedding.reshape(1, -1)

                # 临时方案：标记需要重建索引
                # 实际更新会在 _save_index 时通过完整重建完成
                print(f"Updated vector for doc_id={doc_id}, faiss_idx={faiss_idx}")

        except Exception as e:
            print(f"Warning: Failed to update embedding for doc_id={doc_id}: {e}")

        # 8. 重新生成文档多粒度向量
        await self._index_document_vectors(doc_id, full_content)

        # 9. 重新生成 N-gram 向量
        await self._index_ngram_vectors(ngrams)

        self.conn.commit()

        # 10. 重建 FAISS 索引（因为无法原地修改）
        print("Rebuilding FAISS index after document update...")
        await self._rebuild_faiss_index()

        self._save_index()
        print(f"Document {doc_id} reindexed successfully")

    async def _rebuild_faiss_index(self):
        """重建完整的FAISS索引"""
        print("Rebuilding FAISS index...")

        # 创建新索引
        self.index = faiss.IndexFlatIP(EMBED_DIMENSION)
        self.doc_id_to_index.clear()
        self.index_to_doc_id.clear()

        # 清除所有旧的 faiss_idx (避免 UNIQUE 冲突)
        self.conn.execute('UPDATE document_vectors SET faiss_idx = NULL')
        self.conn.execute('UPDATE ngram_vectors SET faiss_idx = NULL')
        self.conn.commit()

        # 1. 重建文档向量
        cursor = self.conn.execute('SELECT id, full_content FROM documents ORDER BY id')
        for doc_id, full_content in cursor.fetchall():
            try:
                embedding = await self.embedding_client.embed_text(full_content)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)

                faiss_idx = self.index.ntotal - 1
                self.doc_id_to_index[doc_id] = faiss_idx
                self.index_to_doc_id[faiss_idx] = doc_id

            except Exception as e:
                print(f"Warning: Failed to rebuild vector for doc_id={doc_id}: {e}")

        # 2. 重建文档块向量
        cursor = self.conn.execute('''
            SELECT id, doc_id, content
            FROM document_vectors
            ORDER BY id
        ''')

        for vec_id, doc_id, content in cursor.fetchall():
            try:
                embedding = await self.embedding_client.embed_text(content)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)

                faiss_idx = self.index.ntotal - 1

                # 更新 document_vectors 表中的 faiss_idx
                self.conn.execute(
                    'UPDATE document_vectors SET faiss_idx = ? WHERE id = ?',
                    (faiss_idx, vec_id)
                )

            except Exception as e:
                print(f"Warning: Failed to rebuild chunk vector for vec_id={vec_id}: {e}")

        # 3. 重建 N-gram 向量
        cursor = self.conn.execute('''
            SELECT ngram_content, faiss_idx
            FROM ngram_vectors
            WHERE faiss_idx IS NOT NULL
            ORDER BY ngram_content
        ''')

        old_ngram_vectors = cursor.fetchall()

        for ngram_content, old_faiss_idx in old_ngram_vectors:
            try:
                embedding = await self.embedding_client.embed_text(ngram_content)
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)

                new_faiss_idx = self.index.ntotal - 1

                # 更新映射
                self.conn.execute(
                    'UPDATE ngram_vectors SET faiss_idx = ? WHERE ngram_content = ?',
                    (new_faiss_idx, ngram_content)
                )

            except Exception as e:
                print(f"Warning: Failed to rebuild ngram vector for ngram={ngram_content}: {e}")

        self.conn.commit()
        print(f"FAISS index rebuilt: {self.index.ntotal} vectors")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        cursor = self.conn.execute('SELECT COUNT(*) FROM documents')
        doc_count = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(*) FROM ngrams')
        ngram_count = cursor.fetchone()[0]

        cursor = self.conn.execute('SELECT COUNT(DISTINCT content) FROM ngrams')
        unique_ngrams = cursor.fetchone()[0]

        return {
            "documents": doc_count,
            "ngrams": ngram_count,
            "unique_ngrams": unique_ngrams,
            "faiss_vectors": self.index.ntotal if self.index else 0
        }

    def clear_all(self):
        """清空所有索引"""
        self.conn.execute('DELETE FROM documents')
        self.conn.execute('DELETE FROM ngrams')
        self.conn.execute('DELETE FROM document_tags')
        self.conn.commit()

        # 重建FAISS索引
        self._create_new_index()
        self.doc_id_to_index.clear()
        self.index_to_doc_id.clear()
        self._save_index()

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
