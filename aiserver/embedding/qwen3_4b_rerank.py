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
    # 构造严格的 prompt，强调必须精确匹配关键词
    # 截取描述前200字符避免太长
    doc_snippet = document[:200].replace('\n', ' ')
    
    prompt = f"""任务：判断图片描述是否匹配用户搜索。

用户搜索：{query}
图片描述：{doc_snippet}

判断标准：描述中必须包含与"{query}"直接相关的关键词或概念。
如果描述完全没有提及相关内容，回答"否"。
如果描述明确涉及相关内容，回答"是"。

回答（是/否）："""

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
        print(f"\n{'='*60}")
        print(f"[Rerank] 收到请求")
        print(f"  查询: {req.query}")
        print(f"  文档数: {len(req.documents)}")
        print(f"  top_k: {req.top_k}")
        
        if not req.documents:
            print(f"  结果: 无文档，返回空")
            return {"query": req.query, "results": []}
        
        # 打印每个文档
        print(f"\n[Rerank] 输入文档:")
        for i, doc in enumerate(req.documents):
            doc_preview = doc[:50] + "..." if len(doc) > 50 else doc
            print(f"  [{i}] {doc_preview}")
        
        # 计算每个文档的相关性分数
        print(f"\n[Rerank] 计算相关性分数...")
        scores = compute_relevance_score_batch(req.query, req.documents)
        
        # 打印每个分数
        print(f"\n[Rerank] 相关性分数:")
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
        print(f"\n[Rerank] 排序后结果 (top {len(results)}):")
        for i, r in enumerate(results):
            doc_preview = r["document"][:30] + "..." if len(r["document"]) > 30 else r["document"]
            print(f"  {i+1}. [{r['original_index']}] {r['score']*100:5.1f}% {doc_preview}")
        print(f"{'='*60}\n")
        
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
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import port_rerank_4b
    
    port = port_rerank_4b()
    print(f"启动 Qwen3-4B 重排序服务，端口: {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

