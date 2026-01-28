"""
激活式搜索引擎
基于n-gram匹配激活文档节点，并计算相关性得分
"""
import numpy as np
from typing import List, Dict, Optional
from .config import SCORE_WEIGHTS
from .ngram_processor import NgramProcessor
from .embedding_client import EmbeddingClient


class ActivationSearch:
    """激活式搜索引擎"""

    def __init__(self, indexer):
        self.indexer = indexer
        self.ngram_processor = NgramProcessor()
        self.embedding_client = EmbeddingClient()
        self.weights = SCORE_WEIGHTS

    async def search(self, query: str, options: Dict = None) -> List[Dict]:
        """
        搜索文档

        Args:
            query: 查询文本
            options: 搜索选项 {limit, min_score, use_vector, filter_tags, filter_project}

        Returns:
            排序后的文档列表
        """
        options = options or {}
        limit = options.get('limit', 10)
        min_score = options.get('min_score', 0.1)
        use_vector = options.get('use_vector', True)
        filter_tags = options.get('filter_tags', [])
        filter_project = options.get('filter_project')

        # 1. 处理查询，生成n-gram
        query_ngrams = self.ngram_processor.process_query(query)

        if not query_ngrams:
            return []

        # 2. 搜索匹配的n-gram
        matches = self._search_ngrams(query_ngrams)

        # 3. 聚合到文档并计算激活得分
        doc_scores = self._aggregate_activations(matches, len(query_ngrams))

        # 4. 如果启用，计算向量相似度
        if use_vector and self.indexer.index and self.indexer.index.ntotal > 0:
            await self._add_vector_similarity(doc_scores, query)

        # 5. 应用过滤条件
        results = list(doc_scores.values())

        if filter_tags or filter_project:
            results = self._apply_filters(results, filter_tags, filter_project)

        # 6. 排序并限制结果
        results.sort(key=lambda x: x['total_score'], reverse=True)

        # 7. 过滤低分结果
        results = [r for r in results if r['total_score'] >= min_score]

        # 8. 获取完整文档信息
        return self._enrich_results(results[:limit])

    def _search_ngrams(self, query_ngrams: List[str]) -> List[Dict]:
        """搜索匹配的n-gram"""
        matches = []

        # 使用参数化查询防止SQL注入
        placeholders = ','.join(['?'] * len(query_ngrams))
        query = f'''
            SELECT doc_id, content, gram_type, gram_size, section, position
            FROM ngrams
            WHERE content IN ({placeholders})
            LIMIT 1000
        '''

        cursor = self.indexer.conn.execute(query, query_ngrams)

        for row in cursor.fetchall():
            matches.append({
                'doc_id': row[0],
                'content': row[1],
                'gram_type': row[2],
                'gram_size': row[3],
                'section': row[4],
                'position': row[5]
            })

        return matches

    def _aggregate_activations(self, matches: List[Dict], query_ngram_count: int) -> Dict:
        """聚合激活，计算每个文档的得分"""
        doc_scores = {}

        for match in matches:
            doc_id = match['doc_id']

            if doc_id not in doc_scores:
                doc_scores[doc_id] = {
                    'doc_id': doc_id,
                    'activation_score': 0,
                    'matched_ngrams': 0,
                    'match_details': [],
                    'total_score': 0
                }

            doc_score = doc_scores[doc_id]

            # 计算这个匹配的得分
            gram_weight = self.weights.get(match['gram_type'], 1.0)
            section_weight = self.weights.get(f"section_{match['section']}", 1.0)
            length_bonus = np.log(match['gram_size'] + 1)

            match_score = gram_weight * section_weight * length_bonus

            doc_score['activation_score'] += match_score
            doc_score['matched_ngrams'] += 1
            doc_score['match_details'].append({
                'content': match['content'],
                'type': match['gram_type'],
                'section': match['section'],
                'score': match_score
            })

        # 归一化激活得分
        for doc_id, score in doc_scores.items():
            # 考虑覆盖率：匹配的ngram数量 / 查询ngram数量
            coverage = min(score['matched_ngrams'] / query_ngram_count, 1.0)
            score['total_score'] = score['activation_score'] * (0.7 + 0.3 * coverage)

        return doc_scores

    async def _add_vector_similarity(self, doc_scores: Dict, query: str):
        """添加向量相似度得分"""
        if not doc_scores:
            return

        # 生成查询向量
        query_embedding = await self.embedding_client.embed_text(query)

        # 归一化
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        query_embedding = query_embedding.reshape(1, -1)

        # 批量查询FAISS
        doc_ids = list(doc_scores.keys())
        faiss_indices = [self.indexer.doc_id_to_index.get(doc_id)
                         for doc_id in doc_ids
                         if doc_id in self.indexer.doc_id_to_index]

        if not faiss_indices:
            return

        # 对于每个文档，计算相似度
        for doc_id in doc_ids:
            faiss_idx = self.indexer.doc_id_to_index.get(doc_id)
            if faiss_idx is None:
                continue

            # 从FAISS中获取向量
            doc_vector = self.indexer.index.reconstruct(faiss_idx)
            doc_vector = doc_vector.reshape(1, -1)

            # 计算余弦相似度 (归一化后的内积)
            similarity = float(np.dot(query_embedding, doc_vector.T)[0][0])

            doc_score = doc_scores[doc_id]
            doc_score['vector_similarity'] = similarity
            doc_score['total_score'] += similarity * self.weights['vector_similarity']

    def _apply_filters(self, results: List[Dict],
                      filter_tags: List[str], filter_project: Optional[str]) -> List[Dict]:
        """应用过滤条件"""
        filtered = []

        for result in results:
            match = True

            # 标签过滤
            if filter_tags:
                doc_tags = self._get_document_tags(result['doc_id'])
                match = any(tag in doc_tags for tag in filter_tags)

            # 项目过滤
            if match and filter_project:
                cursor = self.indexer.conn.execute(
                    'SELECT project FROM documents WHERE id = ?',
                    (result['doc_id'],)
                )
                row = cursor.fetchone()
                match = row and row[0] == filter_project

            if match:
                filtered.append(result)

        return filtered

    def _get_document_tags(self, doc_id: int) -> List[str]:
        """获取文档标签"""
        cursor = self.indexer.conn.execute(
            'SELECT tag FROM document_tags WHERE doc_id = ?',
            (doc_id,)
        )
        return [row[0] for row in cursor.fetchall()]

    def _enrich_results(self, results: List[Dict]) -> List[Dict]:
        """丰富结果，添加文档详细信息"""
        enriched = []

        for result in results:
            cursor = self.indexer.conn.execute(
                'SELECT * FROM documents WHERE id = ?',
                (result['doc_id'],)
            )
            row = cursor.fetchone()

            if not row:
                continue

            tags = self._get_document_tags(result['doc_id'])

            enriched.append({
                **result,
                'path': row[1],  # path
                'role': row[2],  # role
                'project': row[3],  # project
                'directory': row[4],  # directory
                'timestamp': row[5],  # timestamp
                'tags': tags,
                'problem': row[7],  # problem
                'solution': row[8],  # solution
                'problem_preview': row[7][:300] if row[7] else '',
                'solution_preview': row[8][:500] if row[8] else ''
            })

        return enriched

    def search_by_tag(self, tag: str, limit: int = 10) -> List[Dict]:
        """按标签搜索"""
        cursor = self.indexer.conn.execute('''
            SELECT d.*, dt.tag
            FROM documents d
            JOIN document_tags dt ON d.id = dt.doc_id
            WHERE dt.tag = ?
            ORDER BY d.timestamp DESC
            LIMIT ?
        ''', (tag, limit))

        results = []
        for row in cursor.fetchall():
            tags = self._get_document_tags(row[0])
            results.append({
                'doc_id': row[0],
                'path': row[1],
                'role': row[2],
                'project': row[3],
                'directory': row[4],
                'timestamp': row[5],
                'tags': tags,
                'problem': row[7],
                'solution': row[8],
                'problem_preview': row[7][:300] if row[7] else '',
                'solution_preview': row[8][:500] if row[8] else ''
            })

        return results

    def get_recent(self, limit: int = 10) -> List[Dict]:
        """获取最近的文档"""
        cursor = self.indexer.conn.execute('''
            SELECT * FROM documents
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        results = []
        for row in cursor.fetchall():
            tags = self._get_document_tags(row[0])
            results.append({
                'doc_id': row[0],
                'path': row[1],
                'role': row[2],
                'project': row[3],
                'directory': row[4],
                'timestamp': row[5],
                'tags': tags,
                'problem': row[7],
                'solution': row[8],
                'problem_preview': row[7][:300] if row[7] else '',
                'solution_preview': row[8][:500] if row[8] else ''
            })

        return results
