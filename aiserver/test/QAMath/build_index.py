"""
QA 数据索引构建脚本
读取 data 目录下所有 JSON 文件，调用嵌入服务，存储到 FAISS 向量数据库

支持断点续传：中断后重新运行会从上次进度继续
"""
import json
import os
import sys
import time
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
CACHE_DIR = Path(__file__).parent / "cache"  # 缓存目录，用于断点续传
EMBED_URL = url_embed_8b()
BATCH_SIZE = 4  # 减小批量大小，避免 OOM
MAX_RETRIES = 3  # 最大重试次数
RETRY_DELAY = 5  # 重试间隔（秒）

# 确保目录存在
INDEX_DIR.mkdir(exist_ok=True)
CACHE_DIR.mkdir(exist_ok=True)


def load_all_qa_data():
    """加载 data 目录下所有 JSON 文件的 QA 数据"""
    all_data = []
    
    for json_file in sorted(DATA_DIR.glob("*.json")):
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


def embed_texts_with_retry(texts: list, instruction: str = None, is_query: bool = True) -> np.ndarray:
    """调用嵌入服务批量计算文本嵌入，带重试机制"""
    last_error = None
    
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                f"{EMBED_URL}/embed/texts",
                json={
                    "texts": texts,
                    "instruction": instruction,
                    "is_query": is_query  # 明确指定是 query 还是 document
                },
                timeout=180  # 增加超时时间
            )
            response.raise_for_status()
            result = response.json()
            return np.array(result["embeddings"], dtype=np.float32)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                print(f"\n⚠️  请求失败 (尝试 {attempt + 1}/{MAX_RETRIES}): {e}")
                print(f"   等待 {RETRY_DELAY} 秒后重试...")
                time.sleep(RETRY_DELAY)
    
    raise last_error


def embed_single_text(text: str, instruction: str = None, is_query: bool = True) -> np.ndarray:
    """嵌入单个文本（当批量失败时使用）"""
    try:
        response = requests.post(
            f"{EMBED_URL}/embed/text",
            json={
                "text": text,
                "instruction": instruction,
                "is_query": is_query
            },
            timeout=60
        )
        response.raise_for_status()
        result = response.json()
        return np.array(result["embedding"], dtype=np.float32)
    except Exception as e:
        print(f"\n⚠️  单文本嵌入失败: {e}")
        print(f"   文本: {text[:100]}...")
        # 返回零向量作为占位符
        return None


def process_batch_with_fallback(texts: list, instruction: str = None, is_query: bool = True, pbar=None) -> list:
    """处理批量文本，失败时逐个处理"""
    try:
        embeddings = embed_texts_with_retry(texts, instruction, is_query)
        return list(embeddings)
    except Exception as e:
        print(f"\n⚠️  批量处理失败，切换到逐个处理模式...")
        results = []
        for text in texts:
            emb = embed_single_text(text, instruction, is_query)
            if emb is not None:
                results.append(emb)
            else:
                # 使用零向量占位
                results.append(np.zeros(4096, dtype=np.float32))
            if pbar:
                pbar.update(0)  # 更新进度描述
        return results


def save_cache(embeddings: list, cache_file: Path):
    """保存嵌入缓存"""
    with open(cache_file, "wb") as f:
        pickle.dump(embeddings, f)


def load_cache(cache_file: Path) -> list:
    """加载嵌入缓存"""
    if cache_file.exists():
        with open(cache_file, "rb") as f:
            return pickle.load(f)
    return []


def build_embeddings(texts: list, cache_file: Path, instruction: str = None, is_query: bool = True, desc: str = "嵌入") -> np.ndarray:
    """构建嵌入向量，支持断点续传"""
    # 尝试加载缓存
    cached_embeddings = load_cache(cache_file)
    start_idx = len(cached_embeddings)
    
    if start_idx > 0:
        print(f"  从缓存恢复进度: {start_idx}/{len(texts)} ({start_idx * 100 // len(texts)}%)")
    
    if start_idx >= len(texts):
        print(f"  已完成，使用缓存")
        return np.vstack(cached_embeddings)
    
    all_embeddings = cached_embeddings.copy()
    
    # 计算剩余批次
    remaining_texts = texts[start_idx:]
    total_batches = (len(remaining_texts) + BATCH_SIZE - 1) // BATCH_SIZE
    
    pbar = tqdm(total=len(remaining_texts), desc=desc, initial=0)
    
    try:
        for i in range(0, len(remaining_texts), BATCH_SIZE):
            batch = remaining_texts[i:i + BATCH_SIZE]
            batch_embeddings = process_batch_with_fallback(batch, instruction, is_query, pbar)
            all_embeddings.extend(batch_embeddings)
            pbar.update(len(batch))
            
            # 每处理 10 个批次保存一次缓存
            if (i // BATCH_SIZE + 1) % 10 == 0:
                save_cache(all_embeddings, cache_file)
        
        # 最终保存
        save_cache(all_embeddings, cache_file)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断，保存当前进度...")
        save_cache(all_embeddings, cache_file)
        print(f"   进度已保存到: {cache_file}")
        print(f"   下次运行将从 {len(all_embeddings)}/{len(texts)} 继续")
        sys.exit(0)
    finally:
        pbar.close()
    
    return np.vstack(all_embeddings)


def build_index(qa_data: list):
    """构建 FAISS 索引"""
    try:
        import faiss
    except ImportError:
        print("错误: 请先安装 faiss-cpu 或 faiss-gpu")
        print("  pip install faiss-cpu -i https://mirrors.aliyun.com/pypi/simple/")
        sys.exit(1)
    
    # 准备问题和答案文本
    questions = [item["instruction"] for item in qa_data]
    answers = [item["output"] for item in qa_data]
    
    print(f"\n开始嵌入问题 (共 {len(questions)} 条)...")
    question_embeddings = build_embeddings(
        questions,
        CACHE_DIR / "question_embeddings.pkl",
        instruction="Retrieve relevant QA pairs for the query",
        is_query=True,  # 问题是 Query
        desc="嵌入问题"
    )
    
    print(f"\n开始嵌入答案 (共 {len(answers)} 条)...")
    answer_embeddings = build_embeddings(
        answers,
        CACHE_DIR / "answer_embeddings.pkl",
        instruction=None,
        is_query=False,  # 答案是 Document
        desc="嵌入答案"
    )
    
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
    
    # 清理缓存
    print("清理缓存文件...")
    for cache_file in CACHE_DIR.glob("*.pkl"):
        cache_file.unlink()


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
