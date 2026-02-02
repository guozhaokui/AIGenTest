"""
知识索引器
负责构建和维护知识图谱索引 (FAISS + SQLite)
"""
import sqlite3
import json
import faiss
import numpy as np
import hashlib
from pathlib import Path
from typing import List, Dict, Optional
from .config import (
    FAISS_INDEX_PATH, METADATA_DB_PATH, EMBED_DIMENSION, EMBED_FULL_DIMENSION
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

        # 添加 content_hash 列（如果不存在）
        try:
            self.conn.execute('ALTER TABLE documents ADD COLUMN content_hash TEXT')
        except sqlite3.OperationalError:
            # 列已存在，忽略
            pass

        # 为 documents 表添加 content_hash 索引
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash)')

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

        # 添加 vector_data 列（用于存储向量本身）
        try:
            self.conn.execute('ALTER TABLE ngram_vectors ADD COLUMN vector_data BLOB')
        except sqlite3.OperationalError:
            pass

        # 文档多粒度向量表（用于存储文档的段落、句子级向量）
        # 注意：移除了 FOREIGN KEY 约束，使得向量表可以独立存在作为缓存
        # 这样删除 documents 表时不会级联删除向量缓存
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS document_vectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id INTEGER NOT NULL,
                granularity TEXT NOT NULL,
                content TEXT NOT NULL,
                faiss_idx INTEGER UNIQUE,
                position INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 添加 content_hash 列（如果不存在）
        try:
            self.conn.execute('ALTER TABLE document_vectors ADD COLUMN content_hash TEXT')
        except sqlite3.OperationalError:
            pass

        # 添加 vector_data 列（用于存储向量本身）
        try:
            self.conn.execute('ALTER TABLE document_vectors ADD COLUMN vector_data BLOB')
        except sqlite3.OperationalError:
            pass

        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_vectors_doc_id ON document_vectors(doc_id)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_vectors_granularity ON document_vectors(granularity)')
        self.conn.execute('CREATE INDEX IF NOT EXISTS idx_doc_vectors_hash ON document_vectors(content_hash)')

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
        # 使用512维以节省空间（准确率98%+）
        self.index = faiss.IndexFlatIP(EMBED_DIMENSION)
        print(f"Created new FAISS index (dimension: {EMBED_DIMENSION}, reduced from {EMBED_FULL_DIMENSION})")

    @staticmethod
    def reduce_dimension(vector: np.ndarray) -> np.ndarray:
        """降维：保留前512维

        Args:
            vector: 原始向量（4096维）

        Returns:
            降维后的向量（512维）
        """
        if len(vector) > EMBED_DIMENSION:
            return vector[:EMBED_DIMENSION].copy()
        return vector

    def add_vector_to_index(self, vector: np.ndarray) -> int:
        """添加向量到FAISS索引（自动降维到512维）

        Args:
            vector: 原始向量（4096维或已降维）

        Returns:
            faiss_idx: FAISS索引位置
        """
        # 降维到512维
        reduced = self.reduce_dimension(vector)

        # 确保是2D数组
        if reduced.ndim == 1:
            reduced = reduced.reshape(1, -1)

        # 添加到FAISS
        self.index.add(reduced)

        return self.index.ntotal - 1

    @staticmethod
    def compute_content_hash(content: str) -> str:
        """计算内容的 SHA256 哈希

        Args:
            content: 文本内容

        Returns:
            64位十六进制哈希字符串
        """
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def get_cached_vector(self, content_hash: str, vector_type: str = 'chunk') -> Optional[np.ndarray]:
        """从缓存中查找向量数据

        Args:
            content_hash: 内容哈希值
            vector_type: 向量类型 ('document' 或 'chunk')

        Returns:
            numpy array if found, None otherwise
        """
        if vector_type == 'document':
            # 查找文档向量缓存（从 document_vectors 表，granularity='full'）
            # 注意：文档全文向量也存在 document_vectors 中，需要特殊标记
            # 暂时先查 document_vectors 表
            cursor = self.conn.execute('''
                SELECT vector_data FROM document_vectors
                WHERE content_hash = ? AND vector_data IS NOT NULL
                LIMIT 1
            ''', (content_hash,))
            row = cursor.fetchone()
            if row and row[0]:
                # 从 BLOB 解码向量
                return np.frombuffer(row[0], dtype='float32')
        else:
            # 查找段落/句子向量缓存
            cursor = self.conn.execute('''
                SELECT vector_data FROM document_vectors
                WHERE content_hash = ? AND vector_data IS NOT NULL
                LIMIT 1
            ''', (content_hash,))
            row = cursor.fetchone()
            if row and row[0]:
                return np.frombuffer(row[0], dtype='float32')

        return None

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
        为文档生成多粒度向量（带缓存）

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
        cache_hits = 0

        # 生成段落向量（带缓存）
        for i, para_content in enumerate(chunks['paragraphs']):
            content_hash = self.compute_content_hash(para_content)

            # 检查缓存
            cached_vector = self.get_cached_vector(content_hash, 'chunk')
            embedding = None

            if cached_vector is not None:
                # 复用缓存的向量
                try:
                    cached_vector = cached_vector.reshape(1, -1)
                    self.index.add(cached_vector)
                    faiss_idx = self.index.ntotal - 1
                    embedding = cached_vector  # 用于保存到数据库
                    cache_hits += 1
                except Exception as e:
                    print(f"    ⚠️  段落 {i} 复用向量失败，将重新生成: {e}")
                    cached_vector = None

            if cached_vector is None:
                # 生成新向量
                try:
                    embedding = await self.embedding_client.embed_text(para_content)
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = embedding / norm

                    # 添加到FAISS
                    embedding = embedding.reshape(1, -1)
                    self.index.add(embedding)
                    faiss_idx = self.index.ntotal - 1

                except Exception as e:
                    print(f"    ⚠️  段落 {i} 向量生成失败: {e}")
                    continue

            # 保存到数据库（包含 content_hash 和 vector_data）
            self.conn.execute('''
                INSERT INTO document_vectors (doc_id, granularity, content, content_hash, faiss_idx, position, vector_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, 'paragraph', para_content, content_hash, faiss_idx, i, embedding.tobytes()))

            total_vectors += 1

        # 生成句子向量（带缓存）
        for i, sent_content in enumerate(chunks['sentences']):
            content_hash = self.compute_content_hash(sent_content)

            # 检查缓存
            cached_vector = self.get_cached_vector(content_hash, 'chunk')
            embedding = None

            if cached_vector is not None:
                # 复用缓存的向量
                try:
                    cached_vector = cached_vector.reshape(1, -1)
                    self.index.add(cached_vector)
                    faiss_idx = self.index.ntotal - 1
                    embedding = cached_vector  # 用于保存到数据库
                    cache_hits += 1
                except Exception as e:
                    print(f"    ⚠️  句子 {i} 复用向量失败，将重新生成: {e}")
                    cached_vector = None

            if cached_vector is None:
                # 生成新向量
                try:
                    embedding = await self.embedding_client.embed_text(sent_content)
                    norm = np.linalg.norm(embedding)
                    if norm > 0:
                        embedding = embedding / norm

                    # 添加到FAISS
                    embedding = embedding.reshape(1, -1)
                    self.index.add(embedding)
                    faiss_idx = self.index.ntotal - 1

                except Exception as e:
                    print(f"    ⚠️  句子 {i} 向量生成失败: {e}")
                    continue

            # 保存到数据库（包含 content_hash 和 vector_data）
            self.conn.execute('''
                INSERT INTO document_vectors (doc_id, granularity, content, content_hash, faiss_idx, position, vector_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, 'sentence', sent_content, content_hash, faiss_idx, i, embedding.tobytes()))

            total_vectors += 1

        self.conn.commit()
        cache_rate = (cache_hits / total_vectors * 100) if total_vectors > 0 else 0
        print(f"    ✓ 生成 {total_vectors} 个向量 (段落: {len(chunks['paragraphs'])}, 句子: {len(chunks['sentences'])}, 缓存命中: {cache_hits}/{total_vectors} = {cache_rate:.1f}%)")

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
        for idx, content in enumerate(new_ngrams, 1):
            try:
                embedding = await self.embedding_client.embed_text(content)

                # 归一化
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                # 添加到 FAISS
                embedding_2d = embedding.reshape(1, -1)
                self.index.add(embedding_2d)

                faiss_idx = self.index.ntotal - 1

                # 记录到数据库（包含 vector_data）
                self.conn.execute('''
                    INSERT OR IGNORE INTO ngram_vectors (ngram_content, faiss_idx, gram_size, vector_data)
                    VALUES (?, ?, ?, ?)
                ''', (content, faiss_idx, unique_ngrams[content], embedding.tobytes()))

                # 每100个提交一次，避免长事务
                if idx % 100 == 0:
                    self.conn.commit()

            except Exception as e:
                print(f"Warning: Failed to generate embedding for ngram '{content[:30]}...': {e}")

        # 最后提交剩余的
        self.conn.commit()

    def check_document_exists(self, content_hash: str, path: str = None) -> Optional[Dict]:
        """检查文档是否已存在

        Args:
            content_hash: 内容哈希值
            path: 文件路径（可选）

        Returns:
            如果存在返回 {'doc_id': int, 'path': str, 'content_hash': str, 'is_same_content': bool}
            不存在返回 None
        """
        # 1. 先检查是否有相同哈希的文档
        cursor = self.conn.execute('''
            SELECT id, path, content_hash FROM documents
            WHERE content_hash = ?
        ''', (content_hash,))

        row = cursor.fetchone()
        if row:
            return {
                'doc_id': row[0],
                'path': row[1],
                'content_hash': row[2],
                'is_same_content': True  # 内容完全相同
            }

        # 2. 如果提供了path，检查是否有相同路径的文档（可能是修改）
        if path:
            cursor = self.conn.execute('''
                SELECT id, path, content_hash FROM documents
                WHERE path = ?
            ''', (path,))

            row = cursor.fetchone()
            if row:
                return {
                    'doc_id': row[0],
                    'path': row[1],
                    'content_hash': row[2],
                    'is_same_content': False  # 同路径但内容不同
                }

        return None

    async def index_document_smart(self, document: Dict, save_index: bool = True,
                                   generate_ngram_vectors: bool = True,
                                   force_update: bool = False) -> Dict:
        """智能添加或更新文档（带去重和更新检测）

        Args:
            document: 文档字典
            save_index: 是否立即保存FAISS索引
            generate_ngram_vectors: 是否生成N-gram向量
            force_update: 是否强制更新（即使内容相同也更新时间戳等元数据）

        Returns:
            {
                'action': 'added' | 'updated' | 'skipped',
                'doc_id': int,
                'message': str,
                'old_hash': str (仅更新时),
                'new_hash': str
            }
        """
        # 计算内容哈希
        full_content = f"{document.get('problem', '')}\n\n{document.get('solution', '')}"
        content_hash = self.compute_content_hash(full_content)
        path = document.get('path', '')

        # 检查是否已存在
        existing = self.check_document_exists(content_hash, path)

        if existing:
            if existing['is_same_content']:
                # 内容完全相同
                if force_update:
                    # 强制更新元数据
                    await self.update_document_async(existing['doc_id'], document, save_index, generate_ngram_vectors)
                    return {
                        'action': 'updated',
                        'doc_id': existing['doc_id'],
                        'message': f'强制更新文档元数据 (内容未变)',
                        'old_hash': existing['content_hash'],
                        'new_hash': content_hash
                    }
                else:
                    # 跳过重复内容
                    print(f"⏭️  跳过重复文档: {document.get('problem', path)} (哈希: {content_hash[:16]}...)")
                    return {
                        'action': 'skipped',
                        'doc_id': existing['doc_id'],
                        'message': f'跳过重复文档 (相同哈希)',
                        'old_hash': existing['content_hash'],
                        'new_hash': content_hash
                    }
            else:
                # 同路径但内容不同，需要更新
                print(f"📝 检测到文档修改: {path}")
                print(f"   旧哈希: {existing['content_hash'][:16]}...")
                print(f"   新哈希: {content_hash[:16]}...")

                await self.update_document_async(existing['doc_id'], document, save_index, generate_ngram_vectors)
                return {
                    'action': 'updated',
                    'doc_id': existing['doc_id'],
                    'message': f'更新修改的文档',
                    'old_hash': existing['content_hash'],
                    'new_hash': content_hash
                }
        else:
            # 新文档，添加
            print(f"➕ 添加新文档: {document.get('problem', path)} (哈希: {content_hash[:16]}...)")
            doc_id = await self.index_document(document, save_index, generate_ngram_vectors)
            return {
                'action': 'added',
                'doc_id': doc_id,
                'message': f'添加新文档',
                'new_hash': content_hash
            }

    async def update_document_async(self, doc_id: int, document: Dict,
                                     save_index: bool = True,
                                     generate_ngram_vectors: bool = True) -> None:
        """
        更新已存在的文档（删除旧向量，重新索引）

        Args:
            doc_id: 要更新的文档ID
            document: 新的文档数据
            save_index: 是否立即保存FAISS索引
            generate_ngram_vectors: 是否生成N-gram向量
        """
        print(f"🔄 更新文档 {doc_id}: {document.get('problem', document.get('path', 'N/A'))}")

        # 1. 删除旧的FAISS向量
        if doc_id in self.doc_id_to_index:
            old_faiss_idx = self.doc_id_to_index[doc_id]
            # FAISS不支持直接删除，但我们可以从映射中移除
            del self.doc_id_to_index[doc_id]
            del self.index_to_doc_id[old_faiss_idx]
            print(f"   移除旧的FAISS映射 (idx={old_faiss_idx})")

        # 2. 删除旧的数据库记录
        # 删除文档向量
        self.conn.execute('DELETE FROM document_vectors WHERE doc_id = ?', (doc_id,))

        # 删除n-grams
        self.conn.execute('DELETE FROM ngrams WHERE doc_id = ?', (doc_id,))

        # 删除标签关联
        self.conn.execute('DELETE FROM document_tags WHERE doc_id = ?', (doc_id,))

        print(f"   删除旧的向量和n-grams")

        # 3. 更新文档基本信息
        tags_str = ','.join(document.get('tags', []))
        full_content = f"{document.get('problem', '')}\n\n{document.get('solution', '')}"
        content_hash = self.compute_content_hash(full_content)

        self.conn.execute('''
            UPDATE documents
            SET path = ?, role = ?, project = ?, directory = ?,
                timestamp = ?, tags = ?, problem = ?, solution = ?,
                full_content = ?, content_hash = ?
            WHERE id = ?
        ''', (
            document['path'],
            document.get('role', 'AI'),
            document.get('project', ''),
            document.get('directory', ''),
            document.get('timestamp', ''),
            tags_str,
            document.get('problem', ''),
            document.get('solution', ''),
            full_content,
            content_hash,
            doc_id
        ))

        print(f"   更新文档元数据 (新hash={content_hash[:16]}...)")

        # 4. 重新生成标签
        for tag in document.get('tags', []):
            self.conn.execute(
                'INSERT OR IGNORE INTO document_tags (doc_id, tag) VALUES (?, ?)',
                (doc_id, tag)
            )

        # 5. 重新生成n-grams
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

        print(f"   重新生成 {len(ngrams)} 个n-grams")

        # 6. 重新生成文档向量
        try:
            embedding = await self.embedding_client.embed_text(full_content)

            # 归一化向量
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

            # 保存到 document_vectors 表
            self.conn.execute('''
                INSERT INTO document_vectors (doc_id, granularity, content, content_hash, faiss_idx, position, vector_data)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, 'full', full_content[:500], content_hash, faiss_idx, 0, embedding.tobytes()))

            print(f"   生成新的文档向量 (FAISS idx={faiss_idx})")

        except Exception as e:
            print(f"❌ 生成向量失败: {e}")
            raise

        # 7. 生成文档多粒度向量（段落、句子）
        await self._index_document_vectors(doc_id, full_content)
        print(f"   生成多粒度向量")

        # 8. 为 word_3gram, word_4gram, sentence 生成向量
        if generate_ngram_vectors:
            await self._index_ngram_vectors(ngrams)
            print(f"   生成n-gram向量")

        # 9. 提交更改
        self.conn.commit()

        # 10. 保存索引
        if save_index:
            self._save_index()

        print(f"✅ 文档更新完成 (doc_id={doc_id})")

    async def index_document(self, document: Dict, save_index: bool = True, generate_ngram_vectors: bool = True) -> int:
        """
        索引单个文档（内部方法，不做去重检查）

        Args:
            document: 文档字典
            save_index: 是否立即保存FAISS索引（批量操作时设为False以提高性能）
            generate_ngram_vectors: 是否生成N-gram向量（批量操作时设为False，最后统一生成）

        Returns:
            文档ID
        """
        # 1. 准备文档数据并计算哈希
        tags_str = ','.join(document.get('tags', []))
        full_content = f"{document.get('problem', '')}\n\n{document.get('solution', '')}"
        content_hash = self.compute_content_hash(full_content)

        # 插入文档（包含 content_hash）
        cursor = self.conn.execute('''
            INSERT INTO documents (path, role, project, directory, timestamp, tags, problem, solution, full_content, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            document['path'],
            document.get('role', 'AI'),
            document.get('project', ''),
            document.get('directory', ''),
            document.get('timestamp', ''),
            tags_str,
            document.get('problem', ''),
            document.get('solution', ''),
            full_content,
            content_hash
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

        # 5. 生成文档嵌入向量（带缓存）
        cached_vector = self.get_cached_vector(content_hash, 'document')

        if cached_vector is not None:
            # 复用缓存的向量
            print(f"✓ 复用文档向量缓存 (doc_id={doc_id}, hash={content_hash[:8]}...)")
            try:
                # 从数据库加载的向量直接添加到 FAISS
                cached_vector = cached_vector.reshape(1, -1)
                self.index.add(cached_vector)

                # 更新映射
                faiss_idx = self.index.ntotal - 1
                self.doc_id_to_index[doc_id] = faiss_idx
                self.index_to_doc_id[faiss_idx] = doc_id

                # 保存到 document_vectors 表（作为文档全文向量）
                self.conn.execute('''
                    INSERT INTO document_vectors (doc_id, granularity, content, content_hash, faiss_idx, position, vector_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (doc_id, 'full', full_content[:500], content_hash, faiss_idx, 0, cached_vector.tobytes()))

            except Exception as e:
                print(f"⚠️  复用向量失败，将重新生成: {e}")
                cached_vector = None

        if cached_vector is None:
            # 生成新向量
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

                # 保存向量到数据库
                self.conn.execute('''
                    INSERT INTO document_vectors (doc_id, granularity, content, content_hash, faiss_idx, position, vector_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (doc_id, 'full', full_content[:500], content_hash, faiss_idx, 0, embedding.tobytes()))

                print(f"✓ 生成新文档向量 (doc_id={doc_id}, faiss_idx={faiss_idx}, hash={content_hash[:8]}...)")

            except Exception as e:
                print(f"✗ 生成文档向量失败 (doc_id={doc_id}): {e}")
                print("Document indexed without vector embedding")

        # 提交文档基本信息（避免长事务导致数据库锁）
        self.conn.commit()

        # 6. 生成文档多粒度向量（段落、句子）
        await self._index_document_vectors(doc_id, full_content)

        # 7. 为 word_3gram, word_4gram, sentence 生成向量（去重）
        if generate_ngram_vectors:
            print(f"Calling _index_ngram_vectors with {len(ngrams)} ngrams")
            await self._index_ngram_vectors(ngrams)

        # 最终提交
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

        # 4. 更新文档记录（包含 content_hash）
        tags_str = ','.join(document.get('tags', []))
        full_content = f"{document.get('problem', '')}\n\n{document.get('solution', '')}"
        content_hash = self.compute_content_hash(full_content)

        self.conn.execute('''
            UPDATE documents
            SET role = ?, project = ?, directory = ?, timestamp = ?,
                tags = ?, problem = ?, solution = ?, full_content = ?, content_hash = ?
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
            content_hash,
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

        # 7. 更新文档向量（整篇，带缓存）
        cached_faiss_idx = self.get_cached_vector(content_hash, 'document')

        if cached_faiss_idx is not None:
            # 复用缓存的向量
            print(f"✓ 复用文档向量缓存 (doc_id={doc_id}, hash={content_hash[:8]}...)")
            try:
                cached_vector = self.get_vector(cached_faiss_idx)
                cached_vector = cached_vector.reshape(1, -1)
                self.index.add(cached_vector)

                faiss_idx = self.index.ntotal - 1
                self.doc_id_to_index[doc_id] = faiss_idx
                self.index_to_doc_id[faiss_idx] = doc_id
            except Exception as e:
                print(f"⚠️  复用向量失败，将重新生成: {e}")
                cached_faiss_idx = None

        if cached_faiss_idx is None:
            # 生成新向量
            try:
                embedding = await self.embedding_client.embed_text(full_content)

                # 归一化
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm

                # 添加到FAISS索引
                embedding = embedding.reshape(1, -1)
                self.index.add(embedding)

                faiss_idx = self.index.ntotal - 1
                self.doc_id_to_index[doc_id] = faiss_idx
                self.index_to_doc_id[faiss_idx] = doc_id

                print(f"✓ 生成新文档向量 (doc_id={doc_id}, faiss_idx={faiss_idx}, hash={content_hash[:8]}...)")

            except Exception as e:
                print(f"✗ 更新文档向量失败 (doc_id={doc_id}): {e}")

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
        """清空所有索引数据

        保留向量缓存以加速重建：
        - 删除 documents、ngrams、document_tags 表的所有记录
        - 仅删除 document_vectors 和 ngram_vectors 表中 vector_data 为 NULL 的记录（元数据）
        - 保留 vector_data 不为 NULL 的记录作为缓存
        - 清除缓存记录的 faiss_idx 和 doc_id（避免 UNIQUE 冲突）
        """
        self.conn.execute('DELETE FROM documents')
        self.conn.execute('DELETE FROM ngrams')
        self.conn.execute('DELETE FROM document_tags')

        # 只删除没有向量数据的元数据记录，保留缓存
        self.conn.execute('DELETE FROM document_vectors WHERE vector_data IS NULL')
        self.conn.execute('DELETE FROM ngram_vectors WHERE vector_data IS NULL')

        # 清除缓存记录的 faiss_idx 和 doc_id（避免 UNIQUE 冲突和外键引用问题）
        # 设置 doc_id = -1 作为缓存记录的标记（因为有 NOT NULL 约束）
        # 缓存查找通过 content_hash 进行，不依赖 doc_id
        self.conn.execute('UPDATE document_vectors SET faiss_idx = NULL, doc_id = -1 WHERE vector_data IS NOT NULL')
        self.conn.execute('UPDATE ngram_vectors SET faiss_idx = NULL WHERE vector_data IS NOT NULL')
        self.conn.commit()

        # 重建FAISS索引
        self._create_new_index()
        self.doc_id_to_index.clear()
        self.index_to_doc_id.clear()
        self.vector_cache.clear()
        self._save_index()

    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
