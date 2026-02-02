"""
配置文件
"""
from pathlib import Path

# ==================== 项目路径 ====================
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# ==================== 模型配置 ====================
# 使用本地模型
USE_LOCAL_MODEL = True
LOCAL_MODEL_PATH = Path(__file__).parent.parent.parent / "aiserver" / "models" / "qwen3_0__6b"
MODEL_NAME = str(LOCAL_MODEL_PATH)  # 使用本地路径

# 备用：使用 ModelScope 下载（如果本地模型不存在）
USE_MODELSCOPE = True
MODELSCOPE_MODEL_ID = "qwen/Qwen3-0.6B"

# ==================== 服务配置 ====================
HOST = "0.0.0.0"
PORT = 6015
WORKERS = 1  # 单 worker，避免多次加载模型

# ==================== 推理配置 ====================
DEVICE = "cuda"  # "cuda" 或 "cpu"
PRECISION = "fp16"  # "fp16", "int8", "int4"

# 生成参数
MAX_LENGTH = 512
TEMPERATURE = 0.3  # 低温度，更确定的输出
TOP_P = 0.9
DO_SAMPLE = True

# ==================== 判断阈值 ====================
# 无意义短语判断
MEANINGLESS_THRESHOLD = 0.7

# 相似度判断
SIMILARITY_THRESHOLD = 0.85

# 重要性评分
IMPORTANCE_THRESHOLD = 0.6

# ==================== 批量处理 ====================
MAX_BATCH_SIZE = 20  # 最大批量大小
BATCH_TIMEOUT = 30  # 批量处理超时（秒）

# ==================== 停用词列表 ====================
STOP_WORDS = {
    '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
    '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
    '自己', '这', '那', '为', '之', '与', '及', '其', '或', '等', '被', '从', '而',
    '对', '由', '以', '所', '可以', '如果', '但是', '因为', '所以', '这个', '那个'
}
