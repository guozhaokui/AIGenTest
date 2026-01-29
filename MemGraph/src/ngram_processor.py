"""
N-gram处理器
负责将文本拆分成各种粒度的片段
"""
import jieba
import re
from typing import List, Dict, Set, Tuple
from .config import STOP_WORDS, NGRAM_CONFIG


class NgramProcessor:
    """N-gram处理器"""

    def __init__(self):
        self.stop_words: Set[str] = STOP_WORDS
        self.min_length = 2

    def _parse_markdown_sections(self, text: str) -> List[Dict]:
        """
        解析 Markdown 文档，按标题层级拆分成章节

        Returns:
            [
                {
                    'title': '标题文本',
                    'level': 2,  # 标题层级 (1=# 2=## 3=###)
                    'content': '标题下的内容',
                    'full_section': '标题 + 内容'
                },
                ...
            ]
        """
        sections = []

        # 按标题分割（匹配 # ## ### 等）
        # 使用正则表达式找到所有标题
        lines = text.split('\n')
        current_section = None

        for line in lines:
            # 检查是否是标题行
            heading_match = re.match(r'^(#{1,6})\s+(.+?)$', line)

            if heading_match:
                # 保存上一个章节
                if current_section:
                    sections.append(current_section)

                # 开始新章节
                level = len(heading_match.group(1))  # # 的数量
                title = heading_match.group(2).strip()

                current_section = {
                    'title': title,
                    'level': level,
                    'content': '',
                    'full_section': line + '\n'
                }
            else:
                # 非标题行，添加到当前章节的内容
                if current_section:
                    current_section['content'] += line + '\n'
                    current_section['full_section'] += line + '\n'
                else:
                    # 文档开头的非标题内容，作为一个特殊章节
                    if not sections or sections[-1].get('title') != '__preamble__':
                        sections.append({
                            'title': '__preamble__',
                            'level': 0,
                            'content': line + '\n',
                            'full_section': line + '\n'
                        })
                    else:
                        sections[-1]['content'] += line + '\n'
                        sections[-1]['full_section'] += line + '\n'

        # 保存最后一个章节
        if current_section:
            sections.append(current_section)

        return sections

    def process_document(self, document: Dict) -> List[Dict]:
        """
        处理文档，生成所有n-gram

        Args:
            document: 文档字典，包含 problem, solution, project, tags 等

        Returns:
            n-gram列表
        """
        ngrams = []

        # 1. 处理元数据
        if document.get("project"):
            ngrams.extend(self._process_text(
                document["project"],
                section="metadata",
                gram_type="metadata"
            ))

        for tag in document.get("tags", []):
            ngrams.extend(self._process_text(
                tag,
                section="metadata",
                gram_type="metadata"
            ))

        # 2. 处理问题部分（按 Markdown 章节拆分）
        if document.get("problem"):
            problem_sections = self._parse_markdown_sections(document["problem"])
            if problem_sections:
                # 如果有章节结构，为每个章节生成 N-gram
                for section in problem_sections:
                    if section['title'] == '__preamble__':
                        # 前言部分
                        ngrams.extend(self._extract_all_ngrams(
                            section['content'],
                            section="problem"
                        ))
                    else:
                        # 标题本身作为重要的 N-gram
                        ngrams.extend(self._process_text(
                            section['title'],
                            section="problem",
                            gram_type="metadata"  # 标题使用 metadata 权重
                        ))
                        # 标题下的内容
                        ngrams.extend(self._extract_all_ngrams(
                            section['content'],
                            section="problem"
                        ))
            else:
                # 没有章节结构，按原来的方式处理
                ngrams.extend(self._extract_all_ngrams(
                    document["problem"],
                    section="problem"
                ))

        # 3. 处理解决方案部分（按 Markdown 章节拆分）
        if document.get("solution"):
            solution_sections = self._parse_markdown_sections(document["solution"])
            if solution_sections:
                # 如果有章节结构，为每个章节生成 N-gram
                for section in solution_sections:
                    if section['title'] == '__preamble__':
                        # 前言部分
                        ngrams.extend(self._extract_all_ngrams(
                            section['content'],
                            section="solution"
                        ))
                    else:
                        # 标题本身作为重要的 N-gram
                        ngrams.extend(self._process_text(
                            section['title'],
                            section="solution",
                            gram_type="metadata"  # 标题使用 metadata 权重
                        ))
                        # 标题下的内容
                        ngrams.extend(self._extract_all_ngrams(
                            section['content'],
                            section="solution"
                        ))
            else:
                # 没有章节结构，按原来的方式处理
                ngrams.extend(self._extract_all_ngrams(
                    document["solution"],
                    section="solution"
                ))

        return ngrams

    def _extract_all_ngrams(self, text: str, section: str) -> List[Dict]:
        """提取所有粒度的n-gram"""
        all_ngrams = []

        # 1. 句子级别
        if NGRAM_CONFIG.get("sentence", True):
            sentences = self._split_sentences(text)
            for idx, sentence in enumerate(sentences):
                if len(sentence.strip()) >= self.min_length:
                    all_ngrams.append({
                        "content": sentence.strip(),
                        "gram_type": "sentence",
                        "gram_size": len(sentence),
                        "section": section,
                        "position": idx
                    })

        # 2. 词级别n-gram
        words = self._segment_words(text)
        filtered_words = [w for w in words
                          if len(w) >= self.min_length and w not in self.stop_words]

        if NGRAM_CONFIG.get("word_2gram", True):
            all_ngrams.extend(self._generate_word_ngrams(
                filtered_words, 2, "word_2gram", section
            ))

        if NGRAM_CONFIG.get("word_3gram", True):
            all_ngrams.extend(self._generate_word_ngrams(
                filtered_words, 3, "word_3gram", section
            ))

        if NGRAM_CONFIG.get("word_4gram", True):
            all_ngrams.extend(self._generate_word_ngrams(
                filtered_words, 4, "word_4gram", section
            ))

        # 3. 字符级别n-gram
        clean_text = re.sub(r'\s+', '', text)

        if NGRAM_CONFIG.get("char_2gram", True):
            all_ngrams.extend(self._generate_char_ngrams(
                clean_text, 2, "char_2gram", section
            ))

        if NGRAM_CONFIG.get("char_3gram", True):
            all_ngrams.extend(self._generate_char_ngrams(
                clean_text, 3, "char_3gram", section
            ))

        return all_ngrams

    def _process_text(self, text: str, section: str, gram_type: str) -> List[Dict]:
        """基本文本处理（用于元数据）"""
        words = self._segment_words(text)
        result = []

        for idx, word in enumerate(words):
            if len(word) >= self.min_length and word not in self.stop_words:
                result.append({
                    "content": word,
                    "gram_type": gram_type,
                    "gram_size": len(word),
                    "section": section,
                    "position": idx
                })

        return result

    def _segment_words(self, text: str) -> List[str]:
        """分词"""
        return list(jieba.cut(text))

    def _split_sentences(self, text: str) -> List[str]:
        """分句"""
        return [s.strip() for s in re.split(r'[。！？!?\n]+', text) if s.strip()]

    def _generate_word_ngrams(self, words: List[str], n: int,
                              gram_type: str, section: str) -> List[Dict]:
        """生成词级别n-gram"""
        ngrams = []
        for i in range(len(words) - n + 1):
            gram = ' '.join(words[i:i + n])
            if len(gram) >= self.min_length:
                ngrams.append({
                    "content": gram,
                    "gram_type": gram_type,
                    "gram_size": n,
                    "section": section,
                    "position": i
                })
        return ngrams

    def _generate_char_ngrams(self, text: str, n: int,
                              gram_type: str, section: str) -> List[Dict]:
        """生成字符级别n-gram"""
        ngrams = []
        for i in range(len(text) - n + 1):
            gram = text[i:i + n]
            # 过滤规则：
            # 1. 必须包含至少一个汉字、字母或数字
            # 2. 必须包含至少一个汉字（避免纯英文/数字的无意义拆分）
            if re.search(r'[\u4e00-\u9fa5]', gram):  # 必须有汉字
                ngrams.append({
                    "content": gram,
                    "gram_type": gram_type,
                    "gram_size": n,
                    "section": section,
                    "position": i
                })
        return ngrams

    def process_query(self, query_text: str) -> List[str]:
        """
        处理查询文本

        Args:
            query_text: 查询文本

        Returns:
            n-gram列表
        """
        ngrams = set()

        # 分词
        words = self._segment_words(query_text)
        filtered_words = [w for w in words
                          if len(w) >= self.min_length and w not in self.stop_words]

        # 单词
        ngrams.update(filtered_words)

        # 词n-gram
        for n in [2, 3]:
            if len(filtered_words) >= n:
                for i in range(len(filtered_words) - n + 1):
                    ngrams.add(' '.join(filtered_words[i:i + n]))

        # 字符n-gram (仅中文，避免纯英文数字的无意义拆分)
        clean_text = re.sub(r'\s+', '', query_text)
        for n in [2, 3]:
            for i in range(len(clean_text) - n + 1):
                gram = clean_text[i:i + n]
                # 必须包含至少一个汉字
                if re.search(r'[\u4e00-\u9fa5]', gram):
                    ngrams.add(gram)

        return [g for g in ngrams if len(g) >= self.min_length]
