"""
Qwen3-4B 重排序服务
使用 LLM 判断查询和文档的相关性，比向量相似度更准确
"""
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import numpy as np
from pydantic import BaseModel
from typing import List, Optional

# Initialize FastAPI app
app = FastAPI(title="Qwen3-4B Rerank API")

# Model configuration
MODEL_PATH = "/mnt/hdd/models/Z-Image-Turbo"
MODEL_NAME = "Qwen3-4B-Rerank"
MODEL_VERSION = "1.0"

# Global model and tokenizer
model = None
tokenizer = None


def load_model():
    """加载 Qwen3 模型（用于生成）"""
    global model, tokenizer
    print(f"Loading Qwen3 for reranking from {MODEL_PATH}...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(f"{MODEL_PATH}/tokenizer")
        
        # 使用 CausalLM 以获取生成能力
        model = AutoModelForCausalLM.from_pretrained(
            f"{MODEL_PATH}/text_encoder",
            torch_dtype=torch.bfloat16,
        )
        model.to("cuda")
        model.eval()
        print("Qwen3 rerank model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")
        raise e


class RerankRequest(BaseModel):
    """重排序请求"""
    query: str
    documents: List[str]
    top_k: Optional[int] = None  # 返回前 k 个，默认返回全部


class RerankResult(BaseModel):
    """重排序结果"""
    document: str
    score: float
    original_index: int


@app.on_event("startup")
async def startup_event():
    load_model()


@app.get("/health")
def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "version": MODEL_VERSION,
        "device": str(next(model.parameters()).device) if model else "not loaded"
    }


def compute_relevance_score(query: str, document: str) -> float:
    """
    计算查询和文档的相关性分数
    
    使用 LLM 的 logits 来判断相关性，而不是生成文本（更快）
    思路：给模型一个 prompt，看它对 "是" 的置信度
    """
    # 构造 prompt
    prompt = f"""判断以下图片描述是否与用户查询相关。

图片描述：{document}
用户查询：{query}

请只回答"是"或"否"："""

    # Tokenize
    inputs = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512)
    input_ids = inputs.input_ids.to("cuda")
    
    # 获取 "是" 和 "否" 的 token id
    yes_token_id = tokenizer.encode("是", add_special_tokens=False)[0]
    no_token_id = tokenizer.encode("否", add_special_tokens=False)[0]
    
    with torch.no_grad():
        outputs = model(input_ids=input_ids)
        # 取最后一个位置的 logits
        last_logits = outputs.logits[0, -1, :]
        
        # 计算 "是" 和 "否" 的概率
        yes_logit = last_logits[yes_token_id].float()
        no_logit = last_logits[no_token_id].float()
        
        # Softmax 得到概率
        probs = torch.softmax(torch.tensor([yes_logit, no_logit]), dim=0)
        yes_prob = probs[0].item()
    
    return yes_prob


def compute_relevance_score_batch(query: str, documents: List[str]) -> List[float]:
    """
    批量计算相关性分数（优化版本）
    """
    scores = []
    for doc in documents:
        score = compute_relevance_score(query, doc)
        scores.append(score)
    return scores


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
        if not req.documents:
            return {"query": req.query, "results": []}
        
        # 计算每个文档的相关性分数
        scores = compute_relevance_score_batch(req.query, req.documents)
        
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
        
        return {
            "query": req.query,
            "results": results
        }
    
    except Exception as e:
        print(f"Error in rerank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rerank/score")
async def rerank_score(query: str, document: str):
    """
    计算单个查询-文档对的相关性分数
    """
    try:
        score = compute_relevance_score(query, document)
        return {
            "query": query,
            "document": document,
            "score": score
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6013)

