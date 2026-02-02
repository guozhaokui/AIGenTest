"""
图扩展器
实现基于向量相似度的动态节点扩展
"""
import numpy as np
from typing import List, Dict, Set, Optional, Tuple
from collections import defaultdict


class GraphExpander:
    """动态图扩展器"""

    def __init__(self, indexer, search_engine):
        """
        Args:
            indexer: KnowledgeIndexer 实例
            search_engine: ActivationSearch 实例
        """
        self.indexer = indexer
        self.search_engine = search_engine

    def get_document_vectors(self, doc_id: int) -> List[Dict]:
        """获取文档的所有向量

        Args:
            doc_id: 文档ID

        Returns:
            向量列表，每个元素包含 {faiss_idx, content, granularity}
        """
        cursor = self.indexer.conn.execute('''
            SELECT faiss_idx, content, granularity
            FROM document_vectors
            WHERE doc_id = ? AND faiss_idx IS NOT NULL
        ''', (doc_id,))

        vectors = []
        for row in cursor.fetchall():
            vectors.append({
                'faiss_idx': row[0],
                'content': row[1],
                'granularity': row[2]
            })

        return vectors

    def get_document_by_vector(self, faiss_idx: int) -> Optional[Dict]:
        """通过向量索引找到所属文档

        Args:
            faiss_idx: FAISS 索引位置

        Returns:
            文档信息字典，包含 doc_id 和基本信息
        """
        cursor = self.indexer.conn.execute('''
            SELECT dv.doc_id, d.path, d.problem, d.solution, d.tags
            FROM document_vectors dv
            JOIN documents d ON dv.doc_id = d.id
            WHERE dv.faiss_idx = ?
            LIMIT 1
        ''', (faiss_idx,))

        row = cursor.fetchone()
        if row:
            return {
                'doc_id': row[0],
                'path': row[1],
                'problem': row[2],
                'solution': row[3],
                'tags': row[4]
            }
        return None

    def get_document_info(self, doc_id: int) -> Optional[Dict]:
        """获取文档详细信息

        Args:
            doc_id: 文档ID

        Returns:
            文档详细信息
        """
        cursor = self.indexer.conn.execute('''
            SELECT id, path, problem, solution, tags, role, project, timestamp
            FROM documents
            WHERE id = ?
        ''', (doc_id,))

        row = cursor.fetchone()
        if row:
            return {
                'doc_id': row[0],
                'path': row[1],
                'problem': row[2],
                'solution': row[3][:500] if row[3] else '',  # 截取前500字符
                'tags': row[4],
                'role': row[5],
                'project': row[6],
                'timestamp': row[7]
            }
        return None

    def search_similar_vectors(self, vector: np.ndarray, k: int = 5,
                              exclude_docs: Set[int] = None) -> List[Tuple[int, float]]:
        """搜索相似向量

        Args:
            vector: 查询向量
            k: 返回top-k结果
            exclude_docs: 要排除的文档ID集合

        Returns:
            [(faiss_idx, similarity), ...]
        """
        if exclude_docs is None:
            exclude_docs = set()

        # 确保向量是2D
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)

        # FAISS 搜索，多取一些以便过滤
        distances, indices = self.indexer.index.search(vector, k * 3)

        results = []
        for idx, dist in zip(indices[0], distances[0]):
            if idx == -1:
                continue

            # 找到这个向量所属的文档
            doc = self.get_document_by_vector(int(idx))
            if doc and doc['doc_id'] not in exclude_docs:
                results.append((int(idx), float(dist)))

                if len(results) >= k:
                    break

        return results

    def expand_one_layer(self, doc_ids: List[int], top_k: int = 3,
                        max_vectors_per_doc: int = 10) -> Dict[int, Dict]:
        """扩展一层节点

        Args:
            doc_ids: 要扩展的文档ID列表
            top_k: 每个文档扩展出的最多关联文档数
            max_vectors_per_doc: 每个文档最多使用多少个向量进行扩展

        Returns:
            {doc_id: doc_info} 关联文档字典
        """
        exclude_docs = set(doc_ids)
        related_docs = {}
        doc_scores = defaultdict(float)  # 累积得分

        for doc_id in doc_ids:
            # 获取文档的向量
            vectors = self.get_document_vectors(doc_id)

            # 限制向量数量（选择最重要的）
            if len(vectors) > max_vectors_per_doc:
                # 优先选择段落级（paragraph）和句子级（sentence）
                priority_vectors = [v for v in vectors if v['granularity'] in ['paragraph', 'sentence']]
                if len(priority_vectors) > max_vectors_per_doc:
                    vectors = priority_vectors[:max_vectors_per_doc]
                else:
                    vectors = priority_vectors + vectors[:max_vectors_per_doc - len(priority_vectors)]

            # 对每个向量进行相似度搜索
            for vec_info in vectors:
                faiss_idx = vec_info['faiss_idx']

                try:
                    # 获取向量
                    vector = self.indexer.get_vector(faiss_idx)

                    # 搜索相似向量
                    similar = self.search_similar_vectors(
                        vector,
                        k=top_k,
                        exclude_docs=exclude_docs
                    )

                    # 累积得分
                    for _, similarity in similar:
                        doc = self.get_document_by_vector(_)
                        if doc:
                            doc_scores[doc['doc_id']] += similarity

                except Exception as e:
                    print(f"Warning: Failed to expand vector {faiss_idx}: {e}")
                    continue

        # 选择得分最高的文档
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)

        for related_doc_id, score in sorted_docs[:top_k * len(doc_ids)]:
            if related_doc_id not in exclude_docs:
                doc_info = self.get_document_info(related_doc_id)
                if doc_info:
                    doc_info['similarity_score'] = float(score)
                    related_docs[related_doc_id] = doc_info

        return related_docs

    async def search_and_expand(self, query: str, initial_k: int = 5,
                         expand_layers: int = 0, nodes_per_layer: int = 3) -> Dict:
        """搜索并扩展节点

        Args:
            query: 搜索查询
            initial_k: 初始搜索返回的文档数
            expand_layers: 扩展层数（0表示不扩展）
            nodes_per_layer: 每层扩展的节点数

        Returns:
            {
                'layer0': [主节点列表],
                'layer1': [第一层关联节点列表],
                ...
            }
        """
        # 初始搜索
        search_results = await self.search_engine.search(query, {
            'limit': initial_k,
            'min_score': 0.1,
            'use_vector': True
        })

        # 构建第0层（主节点）
        layer0_docs = []
        doc_ids_set = set()

        for result in search_results:
            doc_id = result['doc_id']
            doc_ids_set.add(doc_id)

            doc_info = self.get_document_info(doc_id)
            if doc_info:
                doc_info['layer'] = 0
                doc_info['total_score'] = result.get('total_score', 0)
                doc_info['vector_score'] = result.get('vector_similarity', 0)
                layer0_docs.append(doc_info)

        result = {'layer0': layer0_docs}

        # 扩展
        current_layer_ids = list(doc_ids_set)

        for layer_num in range(1, expand_layers + 1):
            if not current_layer_ids:
                break

            # 扩展一层
            expanded = self.expand_one_layer(
                current_layer_ids,
                top_k=nodes_per_layer,
                max_vectors_per_doc=10
            )

            # 转换为列表
            layer_docs = []
            for doc_id, doc_info in expanded.items():
                if doc_id not in doc_ids_set:
                    doc_info['layer'] = layer_num
                    layer_docs.append(doc_info)
                    doc_ids_set.add(doc_id)

            result[f'layer{layer_num}'] = layer_docs

            # 更新下一层的起始节点
            current_layer_ids = [doc['doc_id'] for doc in layer_docs]

        return result

    def expand_from_node(self, doc_id: int, top_k: int = 5, min_similarity: float = 0.7) -> List[Dict]:
        """从指定节点扩展一层

        Args:
            doc_id: 文档ID
            top_k: 返回的关联节点数
            min_similarity: 最小相似度阈值（0-1之间，默认0.7即70%）

        Returns:
            关联节点列表
        """
        # 使用 get_node_relations 获取详细的关联信息
        relations = self.get_node_relations(
            doc_id,
            top_k_per_vector=5,
            min_similarity=min_similarity
        )

        # 转换为列表格式，包含最高相似度
        result = []
        for related_doc_id, matches in relations.items():
            # 获取文档基本信息
            doc_info = self.get_document_info(related_doc_id)
            if doc_info:
                # 取该文档所有匹配中的最高相似度作为代表
                max_similarity = max(m['similarity'] for m in matches) if matches else 0
                doc_info['similarity_score'] = max_similarity
                doc_info['match_count'] = len(matches)  # 记录匹配数量
                result.append(doc_info)

        # 按最高相似度排序
        result.sort(key=lambda x: x.get('similarity_score', 0), reverse=True)

        # 返回top_k个结果
        return result[:top_k]

    def get_node_relations(self, doc_id: int, top_k_per_vector: int = 3,
                           min_similarity: float = 0.3) -> Dict[int, List[Dict]]:
        """从一个节点出发，发现所有关联节点及其详细匹配信息

        Args:
            doc_id: 源文档ID
            top_k_per_vector: 每个子向量最多返回多少个相似向量
            min_similarity: 最小相似度阈值

        Returns:
            {
                target_doc_id: [
                    {
                        'source_vec_content': 源向量内容,
                        'source_vec_granularity': 源向量粒度,
                        'target_vec_content': 目标向量内容,
                        'target_vec_granularity': 目标向量粒度,
                        'similarity': 相似度得分
                    },
                    ...
                ]
            }
        """
        # 1. 获取源节点的所有子向量
        source_vectors = self.get_document_vectors(doc_id)

        if not source_vectors:
            return {}

        # 存储结果: {target_doc_id: [matches]}
        relations = defaultdict(list)

        # 2. 遍历每个子向量
        for source_vec in source_vectors:
            try:
                # 获取向量embeddings
                vector = self.indexer.get_vector(source_vec['faiss_idx'])

                if vector.ndim == 1:
                    vector = vector.reshape(1, -1)

                # 3. 搜索相似向量（多取一些以便过滤）
                distances, indices = self.indexer.index.search(vector, top_k_per_vector * 3)

                # 4. 对每个相似向量，反向查找它属于哪个文档
                found_count = 0
                for idx, dist in zip(indices[0], distances[0]):
                    if idx == -1:
                        continue

                    # 跳过自己
                    if int(idx) == source_vec['faiss_idx']:
                        continue

                    # 相似度过滤（IndexFlatIP: 内积越大越相似）
                    similarity = float(dist)
                    if similarity < min_similarity:  # 内积小于阈值则跳过
                        continue

                    # 反向查找：这个向量属于哪个文档？
                    cursor = self.indexer.conn.execute('''
                        SELECT dv.doc_id, dv.content, dv.granularity
                        FROM document_vectors dv
                        WHERE dv.faiss_idx = ?
                    ''', (int(idx),))

                    row = cursor.fetchone()
                    if row:
                        target_doc_id = row[0]

                        # 排除源文档自己
                        if target_doc_id == doc_id:
                            continue

                        # 记录匹配
                        relations[target_doc_id].append({
                            'source_vec_content': source_vec['content'][:200] if source_vec['content'] else '',
                            'source_vec_granularity': source_vec['granularity'],
                            'source_vec_faiss_idx': source_vec['faiss_idx'],
                            'target_vec_content': row[1][:200] if row[1] else '',
                            'target_vec_granularity': row[2],
                            'target_vec_faiss_idx': int(idx),
                            'similarity': similarity
                        })

                        found_count += 1
                        if found_count >= top_k_per_vector:
                            break

            except Exception as e:
                print(f"Warning: Failed to search vector {source_vec['faiss_idx']}: {e}")
                continue

        # 5. 对每个目标文档的匹配按相似度排序
        for target_doc_id in relations:
            relations[target_doc_id].sort(key=lambda x: x['similarity'], reverse=True)

        return dict(relations)

    def get_edge_details(self, doc_id1: int, doc_id2: int, top_k: int = 20) -> List[Dict]:
        """获取两个节点之间的详细向量匹配信息（兼容旧接口）

        Args:
            doc_id1: 第一个文档ID
            doc_id2: 第二个文档ID
            top_k: 返回最多多少对匹配向量

        Returns:
            匹配向量对列表
        """
        # 使用新方法获取关联
        # 为了找到两个节点之间的所有匹配，我们：
        # 1. 让每个向量多返回一些结果（top_k_per_vector=5）
        # 2. 降低相似度阈值（min_similarity=0.1）以包含更多弱关联
        # 3. 然后从结果中筛选出目标节点的匹配
        all_relations = self.get_node_relations(
            doc_id1,
            top_k_per_vector=5,
            min_similarity=0.1  # 降低阈值以找到更多匹配
        )

        # 提取特定目标节点的匹配
        if doc_id2 in all_relations:
            matches = all_relations[doc_id2][:top_k]
            # 转换字段名以兼容旧接口
            return [{
                'vec1_content': m['source_vec_content'],
                'vec1_granularity': m['source_vec_granularity'],
                'vec1_faiss_idx': m['source_vec_faiss_idx'],
                'vec2_content': m['target_vec_content'],
                'vec2_granularity': m['target_vec_granularity'],
                'vec2_faiss_idx': m['target_vec_faiss_idx'],
                'similarity': m['similarity']
            } for m in matches]

        return []
