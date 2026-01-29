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
                    'matched_unique_ngrams': set(),  # 去重：唯一的N-gram内容
                    'unique_ngram_scores': {},  # 每个唯一N-gram的最高得分
                    'match_details': [],
                    'total_score': 0
                }

            doc_score = doc_scores[doc_id]

            # 计算这个匹配的得分
            gram_weight = self.weights.get(match['gram_type'], 1.0)
            section_weight = self.weights.get(f"section_{match['section']}", 1.0)
            length_bonus = np.log(match['gram_size'] + 1)

            match_score = gram_weight * section_weight * length_bonus

            # 去重统计：相同内容只算一次，取最高得分
            ngram_content = match['content']
            if ngram_content not in doc_score['unique_ngram_scores']:
                doc_score['unique_ngram_scores'][ngram_content] = match_score
                doc_score['matched_unique_ngrams'].add(ngram_content)
            else:
                # 如果已经存在，取更高的得分
                doc_score['unique_ngram_scores'][ngram_content] = max(
                    doc_score['unique_ngram_scores'][ngram_content],
                    match_score
                )

            doc_score['match_details'].append({
                'content': match['content'],
                'type': match['gram_type'],
                'section': match['section'],
                'score': match_score
            })

        # 归一化激活得分
        for doc_id, score in doc_scores.items():
            # 使用去重后的数量
            score['matched_ngrams'] = len(score['matched_unique_ngrams'])

            # 计算激活得分：所有唯一 N-gram 的得分之和
            score['activation_score'] = sum(score['unique_ngram_scores'].values())

            # 降低 N-gram 权重，向量为主
            # activation_score 只作为基础分，不再考虑覆盖率
            score['total_score'] = score['activation_score'] * 0.3

        return doc_scores

    async def _match_query_ngram_vectors(self, doc_scores: Dict, query: str, query_full_embedding: np.ndarray):
        """
        查询N-gram向量匹配：为查询的N-gram生成向量，并与N-gram向量库比较
        这允许查询的片段（如"linux21"）与库中的N-gram向量进行语义匹配

        例如: 查询"linux21是什么"
        - 提取N-gram: ["linux21", "是什么", ...]
        - 为符合条件的N-gram生成向量（metadata, word_3gram+, sentence）
        - 与N-gram向量库比较，找到语义相似的片段
        - 根据匹配的N-gram所属文档，增加文档得分
        """
        # 1. 提取查询中的关键词（单词）
        # 使用简单的分词，避免复杂的N-gram处理
        words = self.ngram_processor._segment_words(query)
        filtered_words = [w for w in words
                          if len(w) >= 2 and w not in self.ngram_processor.stop_words]

        # 2. 只为重要的查询片段生成向量（限制数量，避免过多向量操作）
        eligible_query_ngrams = {}  # {content: info}

        # 单词（作为 metadata 类型）- 只取前3个最长的词
        sorted_words = sorted(filtered_words, key=len, reverse=True)[:3]
        for word in sorted_words:
            if word not in eligible_query_ngrams:
                eligible_query_ngrams[word] = {
                    'gram_type': 'metadata',
                    'gram_size': len(word)
                }

        # 只生成 3-4 词组合（跳过 2-gram，减少查询向量数量）
        for n in [3, 4]:
            if len(filtered_words) >= n:
                # 只取第一个组合，避免生成过多查询向量
                phrase = ' '.join(filtered_words[:n])
                if phrase not in eligible_query_ngrams and len(eligible_query_ngrams) < 3:
                    eligible_query_ngrams[phrase] = {
                        'gram_type': f'word_{n}gram',
                        'gram_size': len(phrase)
                    }

        if not eligible_query_ngrams:
            return

        print(f"🔍 查询N-gram向量匹配: 找到 {len(eligible_query_ngrams)} 个符合条件的查询片段")

        # 3. 为这些查询N-gram生成向量
        query_ngram_embeddings = {}  # {content: embedding}
        for content in eligible_query_ngrams.keys():
            try:
                embedding = await self.embedding_client.embed_text(content)
                # 归一化
                norm = np.linalg.norm(embedding)
                if norm > 0:
                    embedding = embedding / norm
                query_ngram_embeddings[content] = embedding
                print(f"  ✓ 生成向量: '{content}'")
            except Exception as e:
                print(f"  ✗ 生成向量失败: '{content}' - {e}")

        if not query_ngram_embeddings:
            return

        # 4. 只查询已激活文档中的N-gram向量（大幅减少向量检索次数）
        activated_doc_ids = list(doc_scores.keys())
        placeholders = ','.join(['?'] * len(activated_doc_ids))

        cursor = self.indexer.conn.execute(f'''
            SELECT nv.ngram_content, nv.faiss_idx, nv.gram_size, ng.doc_id, ng.gram_type
            FROM ngram_vectors nv
            JOIN ngrams ng ON nv.ngram_content = ng.content
            WHERE ng.doc_id IN ({placeholders})
            GROUP BY nv.ngram_content, ng.doc_id
        ''', activated_doc_ids)

        stored_ngrams = cursor.fetchall()

        if not stored_ngrams:
            print(f"  ℹ️  已激活文档中没有N-gram向量")
            return

        print(f"📊 已激活文档的N-gram向量: {len(stored_ngrams)} 个")

        # 5. 预加载所有需要的向量到缓存（批量操作，避免多次 reconstruct）
        unique_faiss_indices = list(set([row[1] for row in stored_ngrams]))
        print(f"  ⚡ 预加载 {len(unique_faiss_indices)} 个唯一向量到缓存...")
        for faiss_idx in unique_faiss_indices:
            try:
                _ = self.indexer.get_vector(faiss_idx)  # 触发缓存加载
            except Exception as e:
                print(f"    ⚠️  预加载向量失败 (idx {faiss_idx}): {e}")

        # 6. 计算查询N-gram向量 vs 存储N-gram向量的相似度
        # 为每个文档收集最佳匹配
        query_ngram_matches = {}  # {doc_id: [match_info]}

        for query_content, query_vec in query_ngram_embeddings.items():
            query_vec = query_vec.reshape(1, -1)
            best_matches = []  # 收集该查询N-gram的最佳匹配

            for row in stored_ngrams:
                stored_content, faiss_idx, gram_size, doc_id, gram_type = row

                try:
                    # 获取存储的N-gram向量（现在应该都在缓存中）
                    stored_vec = self.indexer.get_vector(faiss_idx)
                    stored_vec = stored_vec.reshape(1, -1)

                    # 计算余弦相似度
                    similarity = float(np.dot(query_vec, stored_vec.T)[0][0])

                    # 只保留相似度较高的匹配（阈值 0.3）
                    if similarity > 0.3:
                        best_matches.append({
                            'query_ngram': query_content,
                            'stored_ngram': stored_content,
                            'similarity': similarity,
                            'doc_id': doc_id,
                            'gram_type': gram_type,
                            'gram_size': gram_size
                        })
                except Exception as e:
                    print(f"  ⚠️  向量比较失败 (FAISS idx {faiss_idx}): {e}")

            # 按相似度排序，只保留前10个最佳匹配
            best_matches.sort(key=lambda x: x['similarity'], reverse=True)
            for match in best_matches[:10]:
                doc_id = match['doc_id']
                if doc_id not in query_ngram_matches:
                    query_ngram_matches[doc_id] = []
                query_ngram_matches[doc_id].append(match)

        # 6. 将查询N-gram匹配结果加到文档得分
        for doc_id, matches in query_ngram_matches.items():
            if doc_id not in doc_scores:
                continue

            doc_score = doc_scores[doc_id]

            # 按相似度排序
            matches.sort(key=lambda x: x['similarity'], reverse=True)

            # 取最高的相似度作为得分
            max_similarity = matches[0]['similarity']

            # 记录匹配信息（用于调试）
            doc_score['query_ngram_matches'] = matches[:5]  # 只保留前5个
            doc_score['query_ngram_max_similarity'] = max_similarity

            # 增加得分（权重 3.0，比激活N-gram的5.0略低）
            doc_score['total_score'] += max_similarity * 3.0

            print(f"  📄 文档 {doc_id}: 查询N-gram匹配 {len(matches)} 条, 最高相似度 {max_similarity:.4f}")

    async def _add_vector_similarity(self, doc_scores: Dict, query: str):
        """添加向量相似度得分（文档级 + N-gram级 + 查询N-gram级）"""
        if not doc_scores:
            return

        # 生成查询整句向量
        query_embedding = await self.embedding_client.embed_text(query)

        # 归一化
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        query_embedding = query_embedding.reshape(1, -1)

        # 1. 计算文档级向量相似度（多粒度：整篇 + 段落 + 句子）
        doc_ids = list(doc_scores.keys())

        for doc_id in doc_ids:
            # 1.1 获取整篇文档向量
            faiss_idx = self.indexer.doc_id_to_index.get(doc_id)
            doc_full_similarity = 0.0

            if faiss_idx is not None:
                doc_vector = self.indexer.get_vector(faiss_idx)
                doc_vector = doc_vector.reshape(1, -1)
                doc_full_similarity = float(np.dot(query_embedding, doc_vector.T)[0][0])

            # 1.2 获取文档的多粒度向量（段落、句子）
            cursor = self.indexer.conn.execute('''
                SELECT granularity, content, faiss_idx
                FROM document_vectors
                WHERE doc_id = ?
            ''', (doc_id,))

            chunk_similarities = []
            chunk_matches = []

            for row in cursor.fetchall():
                granularity, content, chunk_faiss_idx = row
                try:
                    chunk_vector = self.indexer.get_vector(chunk_faiss_idx)
                    chunk_vector = chunk_vector.reshape(1, -1)
                    similarity = float(np.dot(query_embedding, chunk_vector.T)[0][0])
                    chunk_similarities.append(similarity)
                    chunk_matches.append({
                        'granularity': granularity,
                        'content': content[:100] + '...' if len(content) > 100 else content,
                        'similarity': similarity
                    })
                except Exception as e:
                    print(f"  ⚠️  获取chunk向量失败: {e}")

            # 1.3 取最高的块相似度
            max_chunk_similarity = max(chunk_similarities) if chunk_similarities else 0.0

            # 1.4 综合得分：整篇文档 + 最佳块匹配
            doc_score = doc_scores[doc_id]
            doc_score['vector_similarity'] = doc_full_similarity
            doc_score['chunk_max_similarity'] = max_chunk_similarity
            doc_score['chunk_matches'] = sorted(chunk_matches, key=lambda x: x['similarity'], reverse=True)[:3]

            # 整篇文档权重8.0，最佳块权重6.0（块更精确）
            doc_score['total_score'] += doc_full_similarity * 8.0
            doc_score['total_score'] += max_chunk_similarity * 6.0

        # 2. 计算已激活N-gram的向量相似度（整句查询 vs 已激活N-gram）
        # 获取这些文档中匹配到的唯一N-gram内容
        all_matched_ngrams = set()
        for doc_score in doc_scores.values():
            all_matched_ngrams.update(doc_score.get('matched_unique_ngrams', set()))

        if not all_matched_ngrams:
            return

        # 查询这些N-gram的向量索引和类型信息
        ngram_info = {}  # {content: {'faiss_idx': idx, 'gram_type': type, 'gram_size': size}}
        placeholders = ','.join(['?'] * len(all_matched_ngrams))
        query_sql = f'''
            SELECT nv.ngram_content, nv.faiss_idx, nv.gram_size, ng.gram_type
            FROM ngram_vectors nv
            JOIN ngrams ng ON nv.ngram_content = ng.content
            WHERE nv.ngram_content IN ({placeholders})
            GROUP BY nv.ngram_content
        '''

        cursor = self.indexer.conn.execute(query_sql, list(all_matched_ngrams))
        for row in cursor.fetchall():
            ngram_info[row[0]] = {
                'faiss_idx': row[1],
                'gram_size': row[2],
                'gram_type': row[3]
            }

        if not ngram_info:
            return

        # 计算N-gram向量相似度（使用缓存避免崩溃）
        ngram_similarities = {}
        for ngram_content, info in ngram_info.items():
            try:
                # 使用安全的 get_vector 方法（带缓存）
                ngram_vector = self.indexer.get_vector(info['faiss_idx'])
                ngram_vector = ngram_vector.reshape(1, -1)

                ngram_similarity = float(np.dot(query_embedding, ngram_vector.T)[0][0])
                ngram_similarities[ngram_content] = {
                    'similarity': ngram_similarity,
                    'gram_type': info['gram_type'],
                    'gram_size': info['gram_size']
                }
            except Exception as e:
                print(f"Warning: Failed to get vector for ngram '{ngram_content[:30]}...': {e}")

        # 将N-gram相似度加到对应的文档得分
        for doc_id, doc_score in doc_scores.items():
            matched_ngrams = doc_score.get('matched_unique_ngrams', set())

            # 收集该文档的所有N-gram向量匹配信息
            ngram_vector_matches = []
            max_ngram_similarity = 0.0

            for ngram in matched_ngrams:
                if ngram in ngram_similarities:
                    sim_info = ngram_similarities[ngram]
                    similarity = sim_info['similarity']

                    ngram_vector_matches.append({
                        'content': ngram,
                        'similarity': similarity,
                        'gram_type': sim_info['gram_type'],
                        'gram_size': sim_info['gram_size']
                    })

                    max_ngram_similarity = max(max_ngram_similarity, similarity)

            # 按相似度降序排序
            ngram_vector_matches.sort(key=lambda x: x['similarity'], reverse=True)

            if max_ngram_similarity > 0:
                doc_score['ngram_vector_similarity'] = max_ngram_similarity
                doc_score['ngram_vector_matches'] = ngram_vector_matches  # 记录所有匹配
                # N-gram向量相似度也给较高权重（5.0）
                doc_score['total_score'] += max_ngram_similarity * 5.0

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
