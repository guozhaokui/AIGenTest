"""
SQLite 数据库管理模块
管理图片索引信息
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import threading


class Database:
    """SQLite 数据库管理器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    @contextmanager
    def get_cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    
    def _init_db(self):
        """初始化数据库表结构"""
        with self.get_cursor() as cursor:
            # 主表：images
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS images (
                    sha256 TEXT PRIMARY KEY,
                    width INTEGER,
                    height INTEGER,
                    file_size INTEGER,
                    format TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    source TEXT,
                    status TEXT DEFAULT 'pending',
                    is_deleted INTEGER DEFAULT 0,
                    deleted_at DATETIME
                )
            """)
            
            # 描述表：descriptions
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS descriptions (
                    image_sha256 TEXT,
                    method TEXT,
                    content TEXT,
                    has_embedding INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (image_sha256, method),
                    FOREIGN KEY (image_sha256) REFERENCES images(sha256)
                )
            """)
            
            # 向量索引表：vector_entries
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vector_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_sha256 TEXT,
                    method TEXT,
                    model TEXT,
                    model_version TEXT,
                    index_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (image_sha256, method, model)
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_created ON images(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_source ON images(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_status ON images(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_deleted ON images(is_deleted)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_desc_method ON descriptions(method)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_index ON vector_entries(index_name, id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vector_sha256 ON vector_entries(image_sha256)")
    
    # ==================== 图片操作 ====================
    
    def add_image(self, sha256: str, width: int, height: int, 
                  file_size: int, format: str, source: str = None) -> bool:
        """添加图片记录"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT INTO images (sha256, width, height, file_size, format, source, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                """, (sha256, width, height, file_size, format, source))
            return True
        except sqlite3.IntegrityError:
            return False  # 已存在
    
    def get_image(self, sha256: str) -> Optional[Dict[str, Any]]:
        """获取图片信息"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM images WHERE sha256 = ? AND is_deleted = 0
            """, (sha256,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_image_status(self, sha256: str, status: str) -> bool:
        """更新图片状态"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE images SET status = ? WHERE sha256 = ?
            """, (status, sha256))
            return cursor.rowcount > 0
    
    def delete_image(self, sha256: str, hard: bool = False) -> bool:
        """删除图片（软删除或硬删除）"""
        with self.get_cursor() as cursor:
            if hard:
                cursor.execute("DELETE FROM images WHERE sha256 = ?", (sha256,))
                cursor.execute("DELETE FROM descriptions WHERE image_sha256 = ?", (sha256,))
                cursor.execute("DELETE FROM vector_entries WHERE image_sha256 = ?", (sha256,))
            else:
                cursor.execute("""
                    UPDATE images SET is_deleted = 1, deleted_at = ? WHERE sha256 = ?
                """, (datetime.now(), sha256))
            return cursor.rowcount > 0
    
    def image_exists(self, sha256: str) -> bool:
        """检查图片是否存在"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT 1 FROM images WHERE sha256 = ? AND is_deleted = 0
            """, (sha256,))
            return cursor.fetchone() is not None
    
    def list_images(self, offset: int = 0, limit: int = 20, 
                    source: str = None, status: str = None) -> List[Dict[str, Any]]:
        """列出图片"""
        with self.get_cursor() as cursor:
            query = "SELECT * FROM images WHERE is_deleted = 0"
            params = []
            
            if source:
                query += " AND source = ?"
                params.append(source)
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def count_images(self, source: str = None, status: str = None) -> int:
        """统计图片数量"""
        with self.get_cursor() as cursor:
            query = "SELECT COUNT(*) FROM images WHERE is_deleted = 0"
            params = []
            
            if source:
                query += " AND source = ?"
                params.append(source)
            if status:
                query += " AND status = ?"
                params.append(status)
            
            cursor.execute(query, params)
            return cursor.fetchone()[0]
    
    # ==================== 描述操作 ====================
    
    def add_description(self, image_sha256: str, method: str, content: str) -> bool:
        """添加描述"""
        try:
            with self.get_cursor() as cursor:
                cursor.execute("""
                    INSERT OR REPLACE INTO descriptions (image_sha256, method, content, has_embedding)
                    VALUES (?, ?, ?, 0)
                """, (image_sha256, method, content))
            return True
        except Exception:
            return False
    
    def get_descriptions(self, image_sha256: str) -> List[Dict[str, Any]]:
        """获取图片的所有描述"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM descriptions WHERE image_sha256 = ?
            """, (image_sha256,))
            return [dict(row) for row in cursor.fetchall()]
    
    def update_description_embedding(self, image_sha256: str, method: str, has_embedding: bool) -> bool:
        """更新描述的嵌入状态"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE descriptions SET has_embedding = ? 
                WHERE image_sha256 = ? AND method = ?
            """, (1 if has_embedding else 0, image_sha256, method))
            return cursor.rowcount > 0
    
    def get_descriptions_without_embedding(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取未计算嵌入的描述"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT d.*, i.status as image_status
                FROM descriptions d
                JOIN images i ON d.image_sha256 = i.sha256
                WHERE d.has_embedding = 0 AND i.is_deleted = 0
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    # ==================== 向量索引操作 ====================
    
    def add_vector_entry(self, image_sha256: str, method: str, 
                         model: str, model_version: str, index_name: str) -> int:
        """添加向量索引条目，返回 ID"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO vector_entries (image_sha256, method, model, model_version, index_name)
                VALUES (?, ?, ?, ?, ?)
            """, (image_sha256, method, model, model_version, index_name))
            return cursor.lastrowid
    
    def get_vector_entry(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取向量条目"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM vector_entries WHERE id = ?
            """, (entry_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_vector_entries_by_sha256(self, image_sha256: str) -> List[Dict[str, Any]]:
        """获取图片的所有向量条目"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM vector_entries WHERE image_sha256 = ?
            """, (image_sha256,))
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_vector_entries(self, image_sha256: str) -> int:
        """删除图片的所有向量条目"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM vector_entries WHERE image_sha256 = ?
            """, (image_sha256,))
            return cursor.rowcount
    
    def get_vector_entry_count(self, index_name: str) -> int:
        """获取索引中的条目数量"""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM vector_entries WHERE index_name = ?
            """, (index_name,))
            return cursor.fetchone()[0]

