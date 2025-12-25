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
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
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


def load_model():
    """加载 Qwen3-Reranker-8B 模型"""
    global model, tokenizer, token_true_id, token_false_id
    print(f"Loading Qwen3-Reranker-8B from {MODEL_PATH}...")
    print(f"Using quantization: {USE_QUANTIZATION}")
    
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        
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
        
        print(f"Qwen3-Reranker-8B loaded successfully.")
        print(f"Token IDs - yes: {token_true_id}, no: {token_false_id}")
        
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


def format_rerank_prompt(query: str, document: str) -> str:
    """
    构造 Qwen3-Reranker 的输入格式
    
    Qwen3-Reranker 使用 chat 格式，询问文档是否与查询相关
    """
    # 标准的 reranker prompt 格式
    prompt = f"""Given a query and a document, determine if the document is relevant to the query. Answer only "yes" or "no".

Query: {query}

Document: {document}

Is the document relevant to the query?"""
    
    # 使用 chat 模板
    messages = [{"role": "user", "content": prompt}]
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False  # 禁用思考模式，直接输出答案
    )
    return text


def compute_relevance_score(query: str, document: str) -> float:
    """
    计算查询和文档的相关性分数
    
    使用模型对 "yes" 的置信度作为相关性分数
    """
    # 构造 prompt
    text = format_rerank_prompt(query, document)
    
    # Tokenize
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=4096)
    device = next(model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        # 取最后一个位置的 logits
        logits = outputs.logits[0, -1, :]
        
        # 获取 "yes" 和 "no" 的 logits
        yes_logit = logits[token_true_id].float()
        no_logit = logits[token_false_id].float()
        
        # Softmax 得到概率
        probs = torch.softmax(torch.tensor([yes_logit, no_logit]), dim=0)
        score = probs[0].item()
    
    return score


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
        
        # 计算每个文档的相关性分数
        print(f"\n[Rerank-8B] 计算相关性分数...")
        scores = []
        for doc in req.documents:
            score = compute_relevance_score(req.query, doc)
            scores.append(score)
        
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

