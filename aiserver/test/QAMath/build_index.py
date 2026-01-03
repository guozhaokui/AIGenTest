"""
QA 数据索引构建脚本
读取 data 目录下所有 JSON 文件，调用嵌入服务，存储到 FAISS 向量数据库
"""
import json
import os
import sys
from pathlib import Path
import requests
import numpy as np
import pickle
from tqdm import tqdm

# 添加 aiserver 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import url_embed_8b

# 配置
DATA_DIR = Path(__file__).parent / "data"
INDEX_DIR = Path(__file__).parent / "index"
EMBED_URL = url_embed_8b()
BATCH_SIZE = 32  # 批量嵌入大小

# 确保索引目录存在
INDEX_DIR.mkdir(exist_ok=True)


def load_all_qa_data():
    """加载 data 目录下所有 JSON 文件的 QA 数据"""
    all_data = []
    
    for json_file in DATA_DIR.glob("*.json"):
        print(f"加载文件: {json_file.name}")
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            for item in data:
                all_data.append({
                    "id": item.get("id", len(all_data)),
                    "instruction": item.get("instruction", ""),
                    "input": item.get("input", ""),
                    "output": item.get("output", ""),
                    "source_file": json_file.name
                })
    
    print(f"共加载 {len(all_data)} 条 QA 数据")
    return all_data


def embed_texts(texts: list, instruction: str = None) -> np.ndarray:
    """调用嵌入服务批量计算文本嵌入"""
    response = requests.post(
        f"{EMBED_URL}/embed/texts",
        json={"texts": texts, "instruction": instruction},
        timeout=120
    )
    response.raise_for_status()
    result = response.json()
    return np.array(result["embeddings"], dtype=np.float32)


def build_index(qa_data: list):
    """构建 FAISS 索引"""
    try:
        import faiss
    except ImportError:
        print("错误: 请先安装 faiss-cpu 或 faiss-gpu")
        print("  pip install faiss-cpu")
        sys.exit(1)
    
    # 准备问题和答案文本
    questions = [item["instruction"] for item in qa_data]
    answers = [item["output"] for item in qa_data]
    
    print(f"\n开始嵌入问题 (共 {len(questions)} 条)...")
    question_embeddings = []
    for i in tqdm(range(0, len(questions), BATCH_SIZE), desc="嵌入问题"):
        batch = questions[i:i + BATCH_SIZE]
        embeddings = embed_texts(batch, instruction="Retrieve relevant QA pairs for the query")
        question_embeddings.append(embeddings)
    question_embeddings = np.vstack(question_embeddings)
    
    print(f"\n开始嵌入答案 (共 {len(answers)} 条)...")
    answer_embeddings = []
    for i in tqdm(range(0, len(answers), BATCH_SIZE), desc="嵌入答案"):
        batch = answers[i:i + BATCH_SIZE]
        embeddings = embed_texts(batch)  # 答案不需要 instruction
        answer_embeddings.append(embeddings)
    answer_embeddings = np.vstack(answer_embeddings)
    
    # 获取嵌入维度
    dimension = question_embeddings.shape[1]
    print(f"\n嵌入维度: {dimension}")
    
    # 创建 FAISS 索引 (使用内积，因为向量已归一化)
    # 对于归一化向量，内积等价于余弦相似度
    question_index = faiss.IndexFlatIP(dimension)
    answer_index = faiss.IndexFlatIP(dimension)
    
    # 添加向量到索引
    question_index.add(question_embeddings)
    answer_index.add(answer_embeddings)
    
    print(f"问题索引大小: {question_index.ntotal}")
    print(f"答案索引大小: {answer_index.ntotal}")
    
    # 保存索引
    faiss.write_index(question_index, str(INDEX_DIR / "question.index"))
    faiss.write_index(answer_index, str(INDEX_DIR / "answer.index"))
    
    # 保存元数据
    with open(INDEX_DIR / "metadata.pkl", "wb") as f:
        pickle.dump(qa_data, f)
    
    # 保存配置
    config = {
        "dimension": dimension,
        "total_count": len(qa_data),
        "embed_model": "Qwen3-Embedding-8B"
    }
    with open(INDEX_DIR / "config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    
    print(f"\n索引已保存到: {INDEX_DIR}")


def main():
    # 检查嵌入服务是否可用
    print(f"嵌入服务地址: {EMBED_URL}")
    try:
        response = requests.get(f"{EMBED_URL}/health", timeout=10)
        response.raise_for_status()
        health = response.json()
        print(f"嵌入服务状态: {health['status']}")
        print(f"模型: {health['model']}, 维度: {health['dimension']}")
    except Exception as e:
        print(f"错误: 无法连接嵌入服务 - {e}")
        print("请确保 qwen3_8b_embed.py 服务已启动")
        sys.exit(1)
    
    # 加载数据
    qa_data = load_all_qa_data()
    
    if not qa_data:
        print("错误: 没有找到任何 QA 数据")
        sys.exit(1)
    
    # 构建索引
    build_index(qa_data)
    
    print("\n✅ 索引构建完成!")


if __name__ == "__main__":
    main()

