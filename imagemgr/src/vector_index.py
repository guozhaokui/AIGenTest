"""
向量索引管理模块
管理嵌入向量的存储和检索
"""
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import threading


class VectorIndex:
    """向量索引管理器"""
    
    def __init__(self, index_dir: str, index_name: str, dimension: int, 
                 model_name: str, model_version: str, shard_size: int = 100000):
        """
        初始化向量索引
        
        Args:
            index_dir: 索引目录
            index_name: 索引名称
            dimension: 向量维度
            model_name: 模型名称
            model_version: 模型版本
            shard_size: 每个分片的最大条目数
        """
        self.index_path = Path(index_dir) / index_name
        self.index_name = index_name
        self.dimension = dimension
        self.model_name = model_name
        self.model_version = model_version
        self.shard_size = shard_size
        
        self._lock = threading.Lock()
        self._embeddings: List[np.ndarray] = []  # 内存中的嵌入向量
        self._ids: List[Dict[str, Any]] = []  # ID 映射信息
        
        self._init_index()
    
    def _init_index(self):
        """初始化索引目录和加载数据"""
        self.index_path.mkdir(parents=True, exist_ok=True)
        
        # 加载或创建元信息
        meta_path = self.index_path / "meta.json"
        if meta_path.exists():
            with open(meta_path, "r") as f:
                meta = json.load(f)
                # 验证一致性
                if meta.get("dimension") != self.dimension:
                    raise ValueError(f"维度不匹配: 期望 {self.dimension}, 实际 {meta.get('dimension')}")
        else:
            self._save_meta()
        
        # 加载现有数据
        self._load_data()
    
    def _save_meta(self):
        """保存元信息"""
        meta = {
            "index_name": self.index_name,
            "dimension": self.dimension,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "shard_size": self.shard_size,
            "total_count": len(self._ids)
        }
        meta_path = self.index_path / "meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)
    
    def _load_data(self):
        """加载索引数据"""
        # 加载 IDs
        ids_path = self.index_path / "ids.json"
        if ids_path.exists():
            with open(ids_path, "r") as f:
                self._ids = json.load(f)
        
        # 加载嵌入向量分片
        shard_idx = 0
        embeddings_list = []
        while True:
            shard_path = self.index_path / f"embeddings_{shard_idx}.npy"
            if not shard_path.exists():
                break
            embeddings_list.append(np.load(shard_path))
            shard_idx += 1
        
        if embeddings_list:
            self._embeddings = [np.vstack(embeddings_list)]
        else:
            self._embeddings = []
    
    def _save_data(self):
        """保存索引数据"""
        # 保存 IDs
        ids_path = self.index_path / "ids.json"
        with open(ids_path, "w") as f:
            json.dump(self._ids, f)
        
        # 保存嵌入向量（分片）
        if self._embeddings:
            all_embeddings = self._embeddings[0] if len(self._embeddings) == 1 else np.vstack(self._embeddings)
            
            # 分片保存
            num_shards = (len(all_embeddings) + self.shard_size - 1) // self.shard_size
            for i in range(num_shards):
                start = i * self.shard_size
                end = min((i + 1) * self.shard_size, len(all_embeddings))
                shard_path = self.index_path / f"embeddings_{i}.npy"
                np.save(shard_path, all_embeddings[start:end])
        
        # 更新元信息
        self._save_meta()
    
    def add(self, embedding: np.ndarray, sha256: str, method: str = "image") -> int:
        """
        添加向量到索引
        
        Args:
            embedding: 嵌入向量
            sha256: 图片 SHA256
            method: 嵌入来源 (image/vlm1/vlm2/human...)
        
        Returns:
            向量在索引中的位置 ID
        """
        with self._lock:
            # 确保向量是正确维度
            embedding = np.array(embedding, dtype=np.float32).reshape(1, -1)
            if embedding.shape[1] != self.dimension:
                raise ValueError(f"向量维度不匹配: 期望 {self.dimension}, 实际 {embedding.shape[1]}")
            
            # 归一化向量（用于余弦相似度计算）
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm
            
            # 添加到内存
            if not self._embeddings:
                self._embeddings = [embedding]
            else:
                self._embeddings[0] = np.vstack([self._embeddings[0], embedding])
            
            # 记录 ID 映射
            entry_id = len(self._ids)
            self._ids.append({
                "id": entry_id,
                "sha256": sha256,
                "method": method
            })
            
            # 保存数据
            self._save_data()
            
            return entry_id
    
    def search(self, query: np.ndarray, top_k: int = 10) -> List[Tuple[int, float, Dict]]:
        """
        搜索最相似的向量
        
        Args:
            query: 查询向量
            top_k: 返回数量
        
        Returns:
            [(id, score, {sha256, method}), ...]
        """
        with self._lock:
            if not self._embeddings or len(self._ids) == 0:
                return []
            
            # 归一化查询向量
            query = np.array(query, dtype=np.float32).reshape(1, -1)
            query_norm = np.linalg.norm(query)
            if query_norm > 0:
                query = query / query_norm
            
            # 获取所有嵌入向量并归一化（兼容未归一化的旧数据）
            all_embeddings = self._embeddings[0].copy()
            norms = np.linalg.norm(all_embeddings, axis=1, keepdims=True)
            norms = np.where(norms > 0, norms, 1)  # 避免除零
            all_embeddings = all_embeddings / norms
            
            # 计算余弦相似度
            similarities = np.dot(all_embeddings, query.T).flatten()
            
            # 获取 top_k
            top_k = min(top_k, len(similarities))
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                results.append((
                    int(idx),
                    float(similarities[idx]),
                    self._ids[idx]
                ))
            
            return results
    
    def search_deduplicated(self, query: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        搜索并按 sha256 去重（每张图只保留最高分）
        
        Args:
            query: 查询向量
            top_k: 返回数量
        
        Returns:
            [{sha256, score, matched_by, matched_text}, ...]
        """
        # 多取一些结果用于去重
        raw_results = self.search(query, top_k * 3)
        
        # 按 sha256 去重
        seen = {}
        for idx, score, info in raw_results:
            sha256 = info["sha256"]
            if sha256 not in seen or score > seen[sha256]["score"]:
                seen[sha256] = {
                    "sha256": sha256,
                    "score": score,
                    "matched_by": info["method"]
                }
        
        # 排序并返回 top_k
        results = sorted(seen.values(), key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def remove(self, sha256: str) -> int:
        """
        从索引中移除指定 sha256 的所有向量
        注意：这会导致 ID 重新编号，需要重建索引
        
        Args:
            sha256: 要移除的图片 SHA256
        
        Returns:
            移除的数量
        """
        with self._lock:
            # 找到要移除的索引
            remove_indices = [i for i, info in enumerate(self._ids) if info["sha256"] == sha256]
            
            if not remove_indices:
                return 0
            
            # 创建保留的索引
            keep_indices = [i for i in range(len(self._ids)) if i not in remove_indices]
            
            # 更新数据
            if keep_indices and self._embeddings:
                self._embeddings[0] = self._embeddings[0][keep_indices]
                self._ids = [self._ids[i] for i in keep_indices]
                # 重新编号
                for i, entry in enumerate(self._ids):
                    entry["id"] = i
            else:
                self._embeddings = []
                self._ids = []
            
            # 保存数据
            self._save_data()
            
            return len(remove_indices)
    
    def count(self) -> int:
        """返回索引中的向量数量"""
        return len(self._ids)
    
    def get_info(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """根据 ID 获取信息"""
        if 0 <= entry_id < len(self._ids):
            return self._ids[entry_id]
        return None


class VectorIndexManager:
    """向量索引管理器，管理多个索引"""
    
    def __init__(self, index_dir: str):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._indexes: Dict[str, VectorIndex] = {}
    
    def get_or_create_index(self, index_name: str, dimension: int,
                            model_name: str, model_version: str) -> VectorIndex:
        """获取或创建索引"""
        if index_name not in self._indexes:
            self._indexes[index_name] = VectorIndex(
                str(self.index_dir), index_name, dimension, model_name, model_version
            )
        return self._indexes[index_name]
    
    def get_index(self, index_name: str) -> Optional[VectorIndex]:
        """获取索引"""
        if index_name in self._indexes:
            return self._indexes[index_name]
        
        # 尝试从磁盘加载
        index_path = self.index_dir / index_name
        if index_path.exists():
            meta_path = index_path / "meta.json"
            if meta_path.exists():
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                self._indexes[index_name] = VectorIndex(
                    str(self.index_dir),
                    index_name,
                    meta["dimension"],
                    meta["model_name"],
                    meta["model_version"]
                )
                return self._indexes[index_name]
        
        return None
    
    def list_indexes(self) -> List[Dict[str, Any]]:
        """列出所有索引"""
        indexes = []
        for path in self.index_dir.iterdir():
            if path.is_dir():
                meta_path = path / "meta.json"
                if meta_path.exists():
                    with open(meta_path, "r") as f:
                        meta = json.load(f)
                    indexes.append(meta)
        return indexes

