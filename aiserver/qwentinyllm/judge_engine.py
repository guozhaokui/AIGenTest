"""
判断引擎
使用 Qwen3-0.6B 进行各类文本判断任务
"""
import json
import re
from typing import Dict, List, Optional
from model_loader import get_model_loader
import prompts
import config


class JudgeEngine:
    """文本判断引擎"""

    def __init__(self):
        self.model_loader = get_model_loader()

    def _parse_json_response(self, text: str) -> Optional[dict]:
        """从模型输出中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 尝试找到 JSON 代码块
        json_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试找到花括号包裹的内容
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def judge_meaningless(self, text: str) -> Dict:
        """
        判断文本是否无意义

        Args:
            text: 待判断的文本

        Returns:
            {
                "is_meaningless": bool,
                "confidence": float,
                "reason": str
            }
        """
        # 快速预过滤：如果全是停用词，直接判定为无意义
        words = set(text.split())
        if words and words.issubset(config.STOP_WORDS):
            return {
                "is_meaningless": True,
                "confidence": 1.0,
                "reason": "纯停用词组合"
            }

        prompt = prompts.build_meaningless_prompt(text)
        response = self.model_loader.generate(prompt, max_length=256)

        result = self._parse_json_response(response)
        if result:
            return {
                "is_meaningless": result.get("is_meaningless", False),
                "confidence": result.get("confidence", 0.5),
                "reason": result.get("reason", "")
            }

        # 解析失败，使用启发式规则
        is_meaningless = len(words.intersection(config.STOP_WORDS)) / max(len(words), 1) > 0.8
        return {
            "is_meaningless": is_meaningless,
            "confidence": 0.6,
            "reason": "模型响应解析失败，使用规则判断"
        }

    def judge_similarity(self, text1: str, text2: str) -> Dict:
        """
        判断两个句子是否相似

        Args:
            text1: 句子1
            text2: 句子2

        Returns:
            {
                "is_similar": bool,
                "similarity_score": float,
                "can_merge": bool,
                "reason": str
            }
        """
        # 快速预过滤：完全相同
        if text1 == text2:
            return {
                "is_similar": True,
                "similarity_score": 1.0,
                "can_merge": True,
                "reason": "完全相同"
            }

        # 快速预过滤：去掉标点空格后相同
        clean1 = re.sub(r'[^\w]', '', text1)
        clean2 = re.sub(r'[^\w]', '', text2)
        if clean1 == clean2:
            return {
                "is_similar": True,
                "similarity_score": 0.95,
                "can_merge": True,
                "reason": "仅标点空格差异"
            }

        prompt = prompts.build_similarity_prompt(text1, text2)
        response = self.model_loader.generate(prompt, max_length=256)

        result = self._parse_json_response(response)
        if result:
            return {
                "is_similar": result.get("is_similar", False),
                "similarity_score": result.get("similarity_score", 0.0),
                "can_merge": result.get("can_merge", False),
                "reason": result.get("reason", "")
            }

        # 解析失败，使用简单字符匹配
        common_chars = set(clean1) & set(clean2)
        similarity = len(common_chars) / max(len(set(clean1)), len(set(clean2)), 1)
        is_similar = similarity > 0.7

        return {
            "is_similar": is_similar,
            "similarity_score": similarity,
            "can_merge": is_similar,
            "reason": "模型响应解析失败，使用字符匹配"
        }

    def judge_importance(self, ngram: str, context: str = "") -> Dict:
        """
        判断 N-gram 的重要性

        Args:
            ngram: N-gram 文本
            context: 上下文（可选）

        Returns:
            {
                "importance_score": float,
                "should_vectorize": bool,
                "category": str,
                "reason": str
            }
        """
        # 快速预过滤：纯停用词
        words = set(ngram.split())
        if words and words.issubset(config.STOP_WORDS):
            return {
                "importance_score": 0.0,
                "should_vectorize": False,
                "category": "stop_words",
                "reason": "纯停用词"
            }

        # 快速预过滤：过短或过长
        if len(ngram) < 2:
            return {
                "importance_score": 0.0,
                "should_vectorize": False,
                "category": "too_short",
                "reason": "文本过短"
            }

        if len(ngram) > 100:
            return {
                "importance_score": 0.8,
                "should_vectorize": True,
                "category": "long_text",
                "reason": "长文本，保留"
            }

        prompt = prompts.build_importance_prompt(ngram, context)
        response = self.model_loader.generate(prompt, max_length=256)

        result = self._parse_json_response(response)
        if result:
            return {
                "importance_score": result.get("importance_score", 0.5),
                "should_vectorize": result.get("should_vectorize", True),
                "category": result.get("category", "unknown"),
                "reason": result.get("reason", "")
            }

        # 解析失败，使用保守策略（保留）
        return {
            "importance_score": 0.6,
            "should_vectorize": True,
            "category": "unknown",
            "reason": "模型响应解析失败，保守保留"
        }

    def judge_quality(self, text: str) -> Dict:
        """
        评估文本质量

        Args:
            text: 待评估的文本

        Returns:
            {
                "quality_score": float,
                "information_density": float,
                "completeness": float,
                "retrieval_value": float,
                "should_index": bool,
                "reason": str
            }
        """
        # 快速预过滤：过短
        if len(text) < 5:
            return {
                "quality_score": 0.2,
                "information_density": 0.1,
                "completeness": 0.3,
                "retrieval_value": 0.2,
                "should_index": False,
                "reason": "文本过短"
            }

        # 快速预过滤：纯停用词
        words = set(text.split())
        if words and words.issubset(config.STOP_WORDS):
            return {
                "quality_score": 0.0,
                "information_density": 0.0,
                "completeness": 0.0,
                "retrieval_value": 0.0,
                "should_index": False,
                "reason": "纯停用词"
            }

        prompt = prompts.build_quality_prompt(text)
        response = self.model_loader.generate(prompt, max_length=256)

        result = self._parse_json_response(response)
        if result:
            return {
                "quality_score": result.get("quality_score", 0.5),
                "information_density": result.get("information_density", 0.5),
                "completeness": result.get("completeness", 0.5),
                "retrieval_value": result.get("retrieval_value", 0.5),
                "should_index": result.get("should_index", True),
                "reason": result.get("reason", "")
            }

        # 解析失败，使用启发式评分
        stop_ratio = len(words.intersection(config.STOP_WORDS)) / max(len(words), 1)
        quality = 1.0 - stop_ratio * 0.5

        return {
            "quality_score": quality,
            "information_density": quality,
            "completeness": quality,
            "retrieval_value": quality,
            "should_index": quality > 0.5,
            "reason": "模型响应解析失败，使用启发式评分"
        }

    def batch_judge_meaningless(self, texts: List[str]) -> List[Dict]:
        """
        批量判断文本是否无意义

        Args:
            texts: 文本列表

        Returns:
            [{
                "text": str,
                "is_meaningless": bool,
                "score": float
            }, ...]
        """
        # 如果数量较少，直接单独判断
        if len(texts) <= 3:
            results = []
            for text in texts:
                result = self.judge_meaningless(text)
                results.append({
                    "text": text,
                    "is_meaningless": result["is_meaningless"],
                    "score": result["confidence"]
                })
            return results

        # 批量判断
        prompt = prompts.build_batch_meaningless_prompt(texts)
        response = self.model_loader.generate(prompt, max_length=512)

        # 尝试解析批量响应
        try:
            # 尝试直接解析数组
            if response.strip().startswith('['):
                result = json.loads(response.strip())
                if isinstance(result, list):
                    return result
        except json.JSONDecodeError:
            pass

        # 解析失败，回退到单独判断
        results = []
        for text in texts:
            result = self.judge_meaningless(text)
            results.append({
                "text": text,
                "is_meaningless": result["is_meaningless"],
                "score": result["confidence"]
            })
        return results


# 全局引擎实例
_judge_engine: Optional[JudgeEngine] = None


def get_judge_engine() -> JudgeEngine:
    """获取全局判断引擎实例"""
    global _judge_engine
    if _judge_engine is None:
        _judge_engine = JudgeEngine()
    return _judge_engine
