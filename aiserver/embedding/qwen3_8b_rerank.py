"""
Qwen3-Reranker-8B 重排序服务
使用阿里通义千问专用重排序模型，效果优于通用语言模型

支持 INT8 量化以节省显存（约 8GB）
"""
import sys
from pathlib import Path

# 添加 aiserver 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from fastapi import FastAPI, HTTPException
import uvicorn
from pydantic import BaseModel
from typing import List, Optional

from config import model_path_rerank_8b

# Initialize FastAPI app
app = FastAPI(title="Qwen3-Reranker-8B Rerank API")

# Model configuration - 从 config.yaml 读取
MODEL_PATH = model_path_rerank_8b()
MODEL_NAME = "Qwen3-Reranker-8B"
MODEL_VERSION = "1.0"

# 是否使用 INT8 量化（节省显存）
USE_QUANTIZATION = True

# Global model and tokenizer
model = None
tokenizer = None

# Token IDs for "yes" and "no"
token_true_id = None
token_false_id = None

# 官方 prompt 模板
PREFIX = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
SUFFIX = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
prefix_tokens = None
suffix_tokens = None
MAX_LENGTH = 8192


def load_model():
    """加载 Qwen3-Reranker-8B 模型"""
    global model, tokenizer, token_true_id, token_false_id, prefix_tokens, suffix_tokens
    print(f"Loading Qwen3-Reranker-8B from {MODEL_PATH}...")
    print(f"Using quantization: {USE_QUANTIZATION}")
    
    try:
        # 注意：官方要求 padding_side='left'
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True, padding_side='left')
        
        if USE_QUANTIZATION:
            # 使用 INT8 量化
            quantization_config = BitsAndBytesConfig(load_in_8bit=True)
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                quantization_config=quantization_config,
                device_map="auto",
                trust_remote_code=True,
            )
        else:
            # 不使用量化（需要约 16GB 显存）
            model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
            )
            model.to("cuda")
        
        model.eval()
        
        # 获取 "yes" 和 "no" 的 token ID（用于计算相关性分数）
        token_true_id = tokenizer.convert_tokens_to_ids("yes")
        token_false_id = tokenizer.convert_tokens_to_ids("no")
        
        # 预处理 prefix 和 suffix tokens（官方用法）
        prefix_tokens = tokenizer.encode(PREFIX, add_special_tokens=False)
        suffix_tokens = tokenizer.encode(SUFFIX, add_special_tokens=False)
        
        print(f"Qwen3-Reranker-8B loaded successfully.")
        print(f"Token IDs - yes: {token_true_id}, no: {token_false_id}")
        print(f"Prefix tokens: {len(prefix_tokens)}, Suffix tokens: {len(suffix_tokens)}")
        
        # 打印显存使用
        if torch.cuda.is_available():
            memory_allocated = torch.cuda.memory_allocated() / 1024**3
            print(f"GPU memory allocated: {memory_allocated:.2f} GB")
            
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e


class RerankRequest(BaseModel):
    """重排序请求"""
    query: str
    documents: List[str]
    top_k: Optional[int] = None  # 返回前 k 个，默认返回全部


class PairScoreRequest(BaseModel):
    """单个查询-文档对的评分请求"""
    query: str
    document: str


@app.on_event("startup")
async def startup_event():
    load_model()


@app.get("/health")
def health_check():
    """健康检查"""
    memory_allocated = 0
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
    
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "version": MODEL_VERSION,
        "quantization": USE_QUANTIZATION,
        "memory_gb": round(memory_allocated, 2),
        "device": str(next(model.parameters()).device) if model else "not loaded"
    }


def format_instruction(query: str, document: str, instruction: str = None) -> str:
    """
    构造 Qwen3-Reranker 的输入格式（官方用法）
    
    使用 <Instruct>, <Query>, <Document> 标签格式
    """
    if instruction is None:
        instruction = "Given a web search query, retrieve relevant passages that answer the query"
    
    return f"<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {document}"


def process_inputs(pairs: List[str]):
    """
    处理输入文本，按照官方方式添加 prefix 和 suffix tokens
    """
    inputs = tokenizer(
        pairs, 
        padding=False, 
        truncation='longest_first',
        return_attention_mask=False, 
        max_length=MAX_LENGTH - len(prefix_tokens) - len(suffix_tokens)
    )
    
    # 添加 prefix 和 suffix tokens
    for i, ele in enumerate(inputs['input_ids']):
        inputs['input_ids'][i] = prefix_tokens + ele + suffix_tokens
    
    # Padding
    inputs = tokenizer.pad(inputs, padding=True, return_tensors="pt", max_length=MAX_LENGTH)
    
    # Move to device
    device = next(model.parameters()).device
    for key in inputs:
        inputs[key] = inputs[key].to(device)
    
    return inputs


def compute_relevance_scores(queries: List[str], documents: List[str]) -> List[float]:
    """
    批量计算查询和文档的相关性分数（官方用法）
    
    使用 log_softmax + exp 计算概率
    """
    # 构造输入对
    pairs = [format_instruction(q, d) for q, d in zip(queries, documents)]
    
    # 处理输入
    inputs = process_inputs(pairs)
    
    with torch.no_grad():
        # 获取最后一个 token 的 logits
        batch_scores = model(**inputs).logits[:, -1, :]
        
        # 获取 yes 和 no 的 logits
        true_vector = batch_scores[:, token_true_id]
        false_vector = batch_scores[:, token_false_id]
        
        # 使用 log_softmax 然后 exp（官方用法）
        batch_scores = torch.stack([false_vector, true_vector], dim=1)
        batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)
        scores = batch_scores[:, 1].exp().tolist()
    
    return scores


def compute_relevance_score(query: str, document: str) -> float:
    """
    计算单个查询-文档对的相关性分数
    """
    scores = compute_relevance_scores([query], [document])
    return scores[0]


@app.post("/rerank")
async def rerank(req: RerankRequest):
    """
    重排序接口
    
    Args:
        query: 用户查询
        documents: 候选文档列表
        top_k: 返回前 k 个结果
    
    Returns:
        results: 按相关性排序的结果
    """
    try:
        print(f"\n{'='*60}")
        print(f"[Rerank-8B] 收到请求")
        print(f"  查询: {req.query}")
        print(f"  文档数: {len(req.documents)}")
        print(f"  top_k: {req.top_k}")
        
        if not req.documents:
            print(f"  结果: 无文档，返回空")
            return {"query": req.query, "results": []}
        
        # 打印每个文档
        print(f"\n[Rerank-8B] 输入文档:")
        for i, doc in enumerate(req.documents):
            doc_preview = doc[:50] + "..." if len(doc) > 50 else doc
            print(f"  [{i}] {doc_preview}")
        
        # 批量计算所有文档的相关性分数（更高效）
        print(f"\n[Rerank-8B] 计算相关性分数...")
        queries = [req.query] * len(req.documents)
        scores = compute_relevance_scores(queries, req.documents)
        
        # 打印每个分数
        print(f"\n[Rerank-8B] 相关性分数:")
        for i, (doc, score) in enumerate(zip(req.documents, scores)):
            doc_preview = doc[:30] + "..." if len(doc) > 30 else doc
            bar = "█" * int(score * 20)
            print(f"  [{i}] {score*100:5.1f}% {bar:<20} {doc_preview}")
        
        # 构建结果
        results = []
        for i, (doc, score) in enumerate(zip(req.documents, scores)):
            results.append({
                "document": doc,
                "score": score,
                "original_index": i
            })
        
        # 按分数排序
        results.sort(key=lambda x: x["score"], reverse=True)
        
        # 返回 top_k
        if req.top_k:
            results = results[:req.top_k]
        
        # 打印排序后结果
        print(f"\n[Rerank-8B] 排序后结果 (top {len(results)}):")
        for i, r in enumerate(results):
            doc_preview = r["document"][:30] + "..." if len(r["document"]) > 30 else r["document"]
            print(f"  {i+1}. [{r['original_index']}] {r['score']*100:5.1f}% {doc_preview}")
        print(f"{'='*60}\n")
        
        return {
            "query": req.query,
            "results": results,
            "model": MODEL_NAME
        }
    
    except Exception as e:
        print(f"Error in rerank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rerank/score")
async def rerank_score(req: PairScoreRequest):
    """
    计算单个查询-文档对的相关性分数
    """
    try:
        score = compute_relevance_score(req.query, req.document)
        return {
            "query": req.query,
            "document": req.document,
            "score": score,
            "model": MODEL_NAME
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_rerank_8b
    
    port = port_rerank_8b()
    print(f"启动 Qwen3-Reranker-8B 服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

