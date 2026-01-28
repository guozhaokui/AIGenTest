"""
配置文件
"""
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).parent.parent
BASE_DIR = ROOT_DIR  # 别名，用于兼容
DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# 数据文件
FAISS_INDEX_PATH = DATA_DIR / "knowledge.faiss"
METADATA_DB_PATH = DATA_DIR / "knowledge.db"
RECORDS_DIR = ROOT_DIR / "records"

# 嵌入服务配置
# 直接访问 GPU 服务器的嵌入服务（不通过 Gateway）
EMBED_SERVICE_URL = "http://192.168.0.132:6014/embed/text"
EMBED_DIMENSION = 4096  # Qwen3-Embedding-8B dimension (根据 aiserver/config.yaml)

# 服务配置
SERVICE_PORT = 8800
SERVICE_HOST = "0.0.0.0"

# N-gram配置
NGRAM_CONFIG = {
    "char_2gram": True,
    "char_3gram": True,
    "word_2gram": True,
    "word_3gram": True,
    "word_4gram": True,
    "sentence": True,
}

# 评分权重
SCORE_WEIGHTS = {
    # N-gram类型权重
    "metadata": 5.0,
    "sentence": 3.0,
    "word_4gram": 2.5,
    "word_3gram": 2.0,
    "word_2gram": 1.5,
    "char_3gram": 1.0,
    "char_2gram": 0.8,

    # Section权重
    "section_metadata": 3.0,
    "section_problem": 2.0,
    "section_solution": 1.5,

    # 向量相似度权重
    "vector_similarity": 3.0,
}

# 停用词
STOP_WORDS = {
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '为', '之', '与', '及', '其', '或', '等', '被', '从', '而',
    '对', '由', '以', '所', '可以', '如果', '但是', '因为', '所以', '这个', '那个'
}
