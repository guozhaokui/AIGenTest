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

    async def index_document(self, document: Dict) -> int:
        """
        索引单个文档

        Args:
            document: 文档字典

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

        self.conn.commit()

        # 保存FAISS索引到磁盘
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
