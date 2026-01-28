"""
查询日志记录器
用于收集搜索查询以便性能测试
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from .config import QUERY_LOG_PATH


class QueryLogger:
    """查询日志记录器"""

    def __init__(self, log_path: Path = QUERY_LOG_PATH):
        self.log_path = log_path

    def log_query(
        self,
        query: str,
        result_count: int,
        search_time_ms: float,
        options: Dict[str, Any] = None,
        top_score: float = None
    ):
        """
        记录一次查询

        Args:
            query: 查询文本
            result_count: 返回结果数量
            search_time_ms: 搜索耗时（毫秒）
            options: 搜索选项（limit, min_score 等）
            top_score: 最高得分
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "result_count": result_count,
            "search_time_ms": round(search_time_ms, 2),
            "options": options or {},
            "top_score": round(top_score, 2) if top_score else None
        }

        # 追加写入 JSONL 格式
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

    def get_recent_queries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取最近的查询记录

        Args:
            limit: 返回数量

        Returns:
            查询记录列表
        """
        if not self.log_path.exists():
            return []

        queries = []
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    queries.append(json.loads(line))

        # 返回最后 N 条
        return queries[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """
        获取查询统计信息

        Returns:
            统计信息字典
        """
        if not self.log_path.exists():
            return {
                "total_queries": 0,
                "avg_search_time_ms": 0,
                "avg_result_count": 0,
                "unique_queries": 0
            }

        queries = []
        unique_queries = set()

        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    queries.append(entry)
                    unique_queries.add(entry['query'])

        if not queries:
            return {
                "total_queries": 0,
                "avg_search_time_ms": 0,
                "avg_result_count": 0,
                "unique_queries": 0
            }

        total_time = sum(q['search_time_ms'] for q in queries)
        total_results = sum(q['result_count'] for q in queries)

        return {
            "total_queries": len(queries),
            "unique_queries": len(unique_queries),
            "avg_search_time_ms": round(total_time / len(queries), 2),
            "avg_result_count": round(total_results / len(queries), 2),
            "min_search_time_ms": min(q['search_time_ms'] for q in queries),
            "max_search_time_ms": max(q['search_time_ms'] for q in queries),
        }

    def export_queries(self, output_path: str = None) -> List[str]:
        """
        导出所有唯一查询（用于性能测试）

        Args:
            output_path: 可选的输出文件路径

        Returns:
            唯一查询列表
        """
        if not self.log_path.exists():
            return []

        unique_queries = set()

        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    unique_queries.add(entry['query'])

        query_list = sorted(list(unique_queries))

        # 如果指定了输出路径，写入文件
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                for query in query_list:
                    f.write(query + '\n')

        return query_list

    def clear_log(self):
        """清空查询日志"""
        if self.log_path.exists():
            self.log_path.unlink()
