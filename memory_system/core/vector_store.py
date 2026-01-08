"""
向量存储层

使用ChromaDB + 远程BGE embedding服务
支持文档的添加、检索、更新、删除
"""

import chromadb
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from pathlib import Path
import hashlib
import time

from .embedding import EmbeddingProvider, create_embedding_provider


@dataclass
class SearchResult:
    """检索结果"""
    id: str
    content: str
    metadata: Dict
    distance: float  # 距离（越小越相似）
    similarity: float  # 相似度（0-1，越大越相似）


@dataclass
class Document:
    """文档对象"""
    content: str
    metadata: Dict
    id: Optional[str] = None

    def __post_init__(self):
        """自动生成ID（如果未提供）"""
        if self.id is None:
            # 基于内容生成唯一ID
            content_hash = hashlib.md5(self.content.encode()).hexdigest()[:16]
            timestamp = int(time.time() * 1000)
            self.id = f"doc_{timestamp}_{content_hash}"


class DocumentChunker:
    """文档分块器"""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        separators: List[str] = None
    ):
        """
        Args:
            chunk_size: 块大小（字符数）
            chunk_overlap: 重叠大小（保持上下文连贯）
            separators: 分隔符优先级列表
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", " ", ""]

    def chunk(self, text: str, metadata: Optional[Dict] = None) -> List[Document]:
        """
        将文本分块

        Args:
            text: 原始文本
            metadata: 文档元数据

        Returns:
            Document列表
        """
        if not text or len(text) == 0:
            return []

        metadata = metadata or {}

        # 如果文本很短，不分块
        if len(text) <= self.chunk_size:
            return [Document(content=text, metadata=metadata)]

        chunks = self._split_text(text)
        documents = []

        for i, chunk in enumerate(chunks):
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["total_chunks"] = len(chunks)

            documents.append(Document(
                content=chunk,
                metadata=chunk_metadata
            ))

        return documents

    def _split_text(self, text: str) -> List[str]:
        """递归分割文本"""
        chunks = []
        current_chunk = ""

        for separator in self.separators:
            if separator == "":
                # 最后的兜底：按字符分割
                return self._split_by_char(text)

            splits = text.split(separator)

            for i, split in enumerate(splits):
                # 添加分隔符（除了最后一个）
                if i < len(splits) - 1:
                    split = split + separator

                if len(current_chunk) + len(split) <= self.chunk_size:
                    current_chunk += split
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = split

                    # 如果单个split太大，递归分割
                    if len(split) > self.chunk_size:
                        # 尝试下一个分隔符
                        break

            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""

            # 如果成功分块，返回
            if chunks:
                return self._merge_small_chunks(chunks)

        return chunks

    def _split_by_char(self, text: str) -> List[str]:
        """按字符强制分割"""
        chunks = []
        for i in range(0, len(text), self.chunk_size - self.chunk_overlap):
            chunk = text[i:i + self.chunk_size]
            chunks.append(chunk)
        return chunks

    def _merge_small_chunks(self, chunks: List[str]) -> List[str]:
        """合并过小的块"""
        merged = []
        buffer = ""

        for chunk in chunks:
            if len(buffer) + len(chunk) <= self.chunk_size:
                buffer += chunk
            else:
                if buffer:
                    merged.append(buffer)
                buffer = chunk

        if buffer:
            merged.append(buffer)

        return merged


class VectorStore:
    """向量存储"""

    def __init__(
        self,
        path: str = ".memory_db/vectors",
        collection_name: str = "documents",
        embedding_provider: Optional[EmbeddingProvider] = None,
        embedding_config: Optional[Dict] = None
    ):
        """
        Args:
            path: ChromaDB存储路径
            collection_name: 集合名称
            embedding_provider: 自定义embedding provider
            embedding_config: embedding配置（如果未提供provider）
        """
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

        # 初始化embedding
        if embedding_provider:
            self.embedding = embedding_provider
        elif embedding_config:
            from .embedding import EmbeddingFactory
            self.embedding = EmbeddingFactory.create(embedding_config)
        else:
            # 默认使用远程BGE服务
            self.embedding = create_embedding_provider(
                "remote",
                base_url="http://192.168.0.100:6012"
            )

        # 初始化ChromaDB
        self.client = chromadb.PersistentClient(path=str(self.path))

        # 获取或创建集合
        dimension = self.embedding.get_dimension()
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={
                "dimension": dimension,
                "embedding_model": getattr(self.embedding, 'model_name', 'remote-bge')
            }
        )

        # 文档分块器
        self.chunker = DocumentChunker()

        print(f"✓ VectorStore初始化完成")
        print(f"  路径: {self.path}")
        print(f"  集合: {collection_name}")
        print(f"  维度: {dimension}")
        print(f"  文档数: {self.collection.count()}")

    def add_document(
        self,
        content: str,
        metadata: Optional[Dict] = None,
        doc_id: Optional[str] = None,
        chunk: bool = True
    ) -> List[str]:
        """
        添加单个文档

        Args:
            content: 文档内容
            metadata: 元数据
            doc_id: 文档ID（可选）
            chunk: 是否分块

        Returns:
            添加的文档ID列表
        """
        metadata = metadata or {}

        # 分块
        if chunk:
            documents = self.chunker.chunk(content, metadata)
        else:
            documents = [Document(content=content, metadata=metadata, id=doc_id)]

        return self.add_documents(documents)

    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        批量添加文档

        Args:
            documents: Document列表

        Returns:
            添加的文档ID列表
        """
        if not documents:
            return []

        # 提取内容
        contents = [doc.content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        ids = [doc.id for doc in documents]

        # 生成embeddings
        print(f"  生成{len(documents)}个文档的embeddings...")
        result = self.embedding.embed(contents)

        # 添加到ChromaDB
        self.collection.add(
            embeddings=result.to_list(),
            documents=contents,
            metadatas=metadatas,
            ids=ids
        )

        print(f"  ✓ 添加{len(documents)}个文档")
        return ids

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_metadata: Optional[Dict] = None
    ) -> List[SearchResult]:
        """
        向量检索

        Args:
            query: 查询文本
            top_k: 返回结果数量
            filter_metadata: 元数据过滤条件
                例如: {"type": "server"} 或
                     {"type": "server", "status": "active"}

        Returns:
            SearchResult列表
        """
        # 生成查询向量
        query_result = self.embedding.embed(query)

        # 构建where条件（ChromaDB格式）
        where = None
        if filter_metadata:
            if len(filter_metadata) == 1:
                # 单个条件：直接使用
                where = filter_metadata
            else:
                # 多个条件：使用$and
                where = {"$and": [
                    {k: v} for k, v in filter_metadata.items()
                ]}

        # 检索
        results = self.collection.query(
            query_embeddings=query_result.to_list(),
            n_results=top_k,
            where=where
        )

        # 转换为SearchResult
        search_results = []

        if results['ids'] and len(results['ids']) > 0:
            for i in range(len(results['ids'][0])):
                distance = results['distances'][0][i]
                # 将距离转换为相似度（假设使用欧氏距离）
                # 对于归一化向量，欧氏距离和余弦距离有关系
                similarity = 1 - (distance / 2)  # 近似转换

                search_results.append(SearchResult(
                    id=results['ids'][0][i],
                    content=results['documents'][0][i],
                    metadata=results['metadatas'][0][i] or {},
                    distance=distance,
                    similarity=max(0, min(1, similarity))  # 限制在[0,1]
                ))

        return search_results

    def get_by_id(self, doc_id: str) -> Optional[Document]:
        """根据ID获取文档"""
        try:
            result = self.collection.get(ids=[doc_id])
            if result['ids']:
                return Document(
                    content=result['documents'][0],
                    metadata=result['metadatas'][0] or {},
                    id=result['ids'][0]
                )
        except Exception:
            pass
        return None

    def delete(self, doc_ids: Union[str, List[str]]) -> int:
        """
        删除文档

        Args:
            doc_ids: 文档ID或ID列表

        Returns:
            删除的数量
        """
        if isinstance(doc_ids, str):
            doc_ids = [doc_ids]

        if not doc_ids:
            return 0

        self.collection.delete(ids=doc_ids)
        print(f"  ✓ 删除{len(doc_ids)}个文档")
        return len(doc_ids)

    def delete_by_metadata(self, filter_metadata: Dict) -> int:
        """根据元数据删除文档"""
        # 先查询符合条件的文档
        results = self.collection.get(where=filter_metadata)

        if results['ids']:
            count = len(results['ids'])
            self.collection.delete(ids=results['ids'])
            print(f"  ✓ 删除{count}个文档（按元数据）")
            return count

        return 0

    def update_metadata(self, doc_id: str, metadata: Dict) -> bool:
        """更新文档元数据"""
        try:
            self.collection.update(
                ids=[doc_id],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            print(f"  ✗ 更新元数据失败: {e}")
            return False

    def count(self) -> int:
        """获取文档总数"""
        return self.collection.count()

    def clear(self):
        """清空所有文档"""
        self.client.delete_collection(self.collection.name)
        dimension = self.embedding.get_dimension()
        self.collection = self.client.get_or_create_collection(
            name=self.collection.name,
            metadata={"dimension": dimension}
        )
        print("  ✓ 清空所有文档")

    def stats(self) -> Dict:
        """获取统计信息"""
        return {
            "total_documents": self.count(),
            "collection_name": self.collection.name,
            "dimension": self.embedding.get_dimension(),
            "path": str(self.path)
        }


if __name__ == "__main__":
    # 测试代码
    print("\n" + "=" * 60)
    print("测试VectorStore")
    print("=" * 60)

    # 创建向量存储
    print("\n1. 初始化VectorStore...")
    store = VectorStore(path=".memory_db/test_vectors")

    # 添加文档
    print("\n2. 添加测试文档...")
    doc_ids = store.add_documents([
        Document(
            content="linux81是公司内网服务器，配置为8核CPU+64GB RAM，主要用于运行大模型推理服务。",
            metadata={"source": "日志/2601.md", "type": "server", "entity": "linux81"}
        ),
        Document(
            content="QAMath是一个基于Qwen-8B的数学问答系统，部署在linux81服务器上。",
            metadata={"source": "日志/2601.md", "type": "project", "entity": "QAMath"}
        ),
        Document(
            content="MetaGPT是AI代码生成框架，使用Python开发，支持自动生成项目代码。",
            metadata={"source": "日志/2601.md", "type": "project", "entity": "MetaGPT"}
        ),
        Document(
            content="usa服务器用于部署Claude Code服务器，提供低延迟的API访问。",
            metadata={"source": "日志/2601.md", "type": "server", "entity": "usa服务器"}
        )
    ])

    print(f"\n  添加了{len(doc_ids)}个文档")
    print(f"  总文档数: {store.count()}")

    # 搜索测试
    print("\n3. 测试向量检索...")

    queries = [
        "QAMath是什么？",
        "有哪些服务器？",
        "如何生成代码？"
    ]

    for query in queries:
        print(f"\n  查询: {query}")
        results = store.search(query, top_k=2)

        for i, result in enumerate(results, 1):
            print(f"    {i}. [相似度: {result.similarity:.3f}]")
            print(f"       {result.content[:60]}...")
            print(f"       来源: {result.metadata.get('source', 'unknown')}")

    # 元数据过滤
    print("\n4. 测试元数据过滤...")
    print("  查询: 关于服务器的文档")
    results = store.search(
        "服务器配置",
        top_k=5,
        filter_metadata={"type": "server"}
    )

    for i, result in enumerate(results, 1):
        print(f"    {i}. {result.metadata.get('entity')}: {result.content[:40]}...")

    # 统计信息
    print("\n5. 统计信息...")
    stats = store.stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
