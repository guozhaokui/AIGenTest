"""
Prompt 模板
专门为知识库文本判断任务设计的提示词
"""

# ==================== 无意义短语判断 ====================
MEANINGLESS_PROMPT = """你是一个专业的中文文本分析专家。请判断以下文本是否是无意义的短语。

【判断标准】
1. 只包含停用词（如：的、是、在、了）
2. 没有实际语义内容
3. 无法独立表达完整意思
4. 不是专业术语或领域词汇

【输入文本】
"{text}"

【输出格式】
请用 JSON 格式回答：
{{
    "is_meaningless": true/false,
    "confidence": 0.0-1.0,
    "reason": "判断理由"
}}

【回答】
"""

# ==================== 相似句子判断 ====================
SIMILARITY_PROMPT = """你是一个专业的中文语义分析专家。请判断以下两个句子是否语义相似。

【判断标准】
1. 核心语义是否相同
2. 只是表述略有差异（如：空格、标点、措辞）
3. 可以用同一个向量表示而不影响检索效果

【句子1】
"{text1}"

【句子2】
"{text2}"

【输出格式】
请用 JSON 格式回答：
{{
    "is_similar": true/false,
    "similarity_score": 0.0-1.0,
    "can_merge": true/false,
    "reason": "判断理由"
}}

【回答】
"""

# ==================== N-gram 重要性评分 ====================
IMPORTANCE_PROMPT = """你是一个专业的知识库优化专家。请评估以下 N-gram 的重要性，判断是否值得为它生成向量索引。

【评估标准】
1. 是否包含关键信息（技术术语、专有名词、核心概念）
2. 是否有独立检索价值
3. 是否有助于知识库检索准确度
4. 是否不是通用停用词组合

【N-gram】
"{ngram}"

【上下文】
"{context}"

【输出格式】
请用 JSON 格式回答：
{{
    "importance_score": 0.0-1.0,
    "should_vectorize": true/false,
    "category": "technical_term/common_phrase/stop_words/entity/concept",
    "reason": "判断理由"
}}

【回答】
"""

# ==================== 文本质量评估 ====================
QUALITY_PROMPT = """你是一个专业的文本质量评估专家。请评估以下文本的信息量和重要性。

【评估维度】
1. 信息密度（是否包含有价值的信息）
2. 语义完整性（是否表达完整）
3. 检索价值（是否有助于检索）
4. 内容质量（是否有意义）

【文本】
"{text}"

【输出格式】
请用 JSON 格式回答：
{{
    "quality_score": 0.0-1.0,
    "information_density": 0.0-1.0,
    "completeness": 0.0-1.0,
    "retrieval_value": 0.0-1.0,
    "should_index": true/false,
    "reason": "评估理由"
}}

【回答】
"""

# ==================== 批量判断提示词 ====================
BATCH_MEANINGLESS_PROMPT = """你是一个专业的中文文本分析专家。请批量判断以下文本是否是无意义的短语。

【判断标准】
1. 只包含停用词（如：的、是、在、了）
2. 没有实际语义内容
3. 无法独立表达完整意思
4. 不是专业术语或领域词汇

【输入文本列表】
{text_list}

【输出格式】
请用 JSON 数组格式回答，每个元素格式为：
{{
    "text": "原文本",
    "is_meaningless": true/false,
    "score": 0.0-1.0
}}

【回答】
"""


def build_meaningless_prompt(text: str) -> str:
    """构建无意义短语判断的 prompt"""
    return MEANINGLESS_PROMPT.format(text=text)


def build_similarity_prompt(text1: str, text2: str) -> str:
    """构建相似度判断的 prompt"""
    return SIMILARITY_PROMPT.format(text1=text1, text2=text2)


def build_importance_prompt(ngram: str, context: str = "") -> str:
    """构建重要性评分的 prompt"""
    return IMPORTANCE_PROMPT.format(ngram=ngram, context=context or "无上下文")


def build_quality_prompt(text: str) -> str:
    """构建文本质量评估的 prompt"""
    return QUALITY_PROMPT.format(text=text)


def build_batch_meaningless_prompt(texts: list[str]) -> str:
    """构建批量无意义短语判断的 prompt"""
    text_list = "\n".join([f"{i+1}. {text}" for i, text in enumerate(texts)])
    return BATCH_MEANINGLESS_PROMPT.format(text_list=text_list)
