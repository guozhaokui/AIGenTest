#!/usr/bin/env python3
"""
对比 instruction 对检索效果的影响
核心问题：Query 带/不带 instruction，和 Answer 的相似度哪个更高？
"""
import requests
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import url_embed_8b

BASE_URL = url_embed_8b()

# 测试数据：Query 和对应的 Answer
test_cases = [
    {
        "query": "什么是机器学习？",
        "answer": "机器学习是人工智能的一个分支，它使计算机系统能够从数据中学习和改进，而无需进行明确的编程。",
        "unrelated": "今天天气很好，适合户外运动。"
    },
    {
        "query": "LayaAir 如何创建 3D 场景？",
        "answer": "在 LayaAir 中创建 3D 场景，首先需要初始化 Scene3D，然后添加摄像机、灯光和 3D 模型。",
        "unrelated": "Python 是一种流行的编程语言。"
    },
    {
        "query": "如何优化游戏性能？",
        "answer": "优化游戏性能可以从减少 Draw Call、使用 LOD、合理管理内存、优化资源加载等方面入手。",
        "unrelated": "北京是中国的首都。"
    }
]

instruction = "Given a web search query, retrieve relevant passages that answer the query"

print("=" * 70)
print("Instruction 对检索效果的影响对比")
print("=" * 70)

for i, case in enumerate(test_cases, 1):
    print(f"\n【测试 {i}】")
    print(f"  Query:    {case['query']}")
    print(f"  Answer:   {case['answer'][:50]}...")
    print(f"  无关文本: {case['unrelated']}")
    
    # ========================================
    # 获取 Answer 和无关文本的嵌入（Document，不带 instruction）
    # ========================================
    answer_resp = requests.post(f"{BASE_URL}/embed/text", json={
        "text": case["answer"],
        "is_query": False  # Document 不需要 instruction
    })
    answer_emb = np.array(answer_resp.json()["embedding"])
    
    unrelated_resp = requests.post(f"{BASE_URL}/embed/text", json={
        "text": case["unrelated"],
        "is_query": False
    })
    unrelated_emb = np.array(unrelated_resp.json()["embedding"])
    
    # ========================================
    # 情况 1: Query 不带 instruction
    # ========================================
    query_no_inst_resp = requests.post(f"{BASE_URL}/embed/text", json={
        "text": case["query"],
        "is_query": True,
        # 没有 instruction
    })
    query_no_inst_emb = np.array(query_no_inst_resp.json()["embedding"])
    
    sim_answer_no_inst = np.dot(query_no_inst_emb, answer_emb)
    sim_unrelated_no_inst = np.dot(query_no_inst_emb, unrelated_emb)
    
    # ========================================
    # 情况 2: Query 带 instruction
    # ========================================
    query_with_inst_resp = requests.post(f"{BASE_URL}/embed/text", json={
        "text": case["query"],
        "instruction": instruction,
        "is_query": True,
    })
    query_with_inst_emb = np.array(query_with_inst_resp.json()["embedding"])
    
    sim_answer_with_inst = np.dot(query_with_inst_emb, answer_emb)
    sim_unrelated_with_inst = np.dot(query_with_inst_emb, unrelated_emb)
    
    # ========================================
    # 对比结果
    # ========================================
    print(f"\n  📊 相似度对比:")
    print(f"  {'':30} {'不带 instruction':^18} {'带 instruction':^18} {'差异':^10}")
    print(f"  {'-'*78}")
    
    diff_answer = sim_answer_with_inst - sim_answer_no_inst
    diff_unrelated = sim_unrelated_with_inst - sim_unrelated_no_inst
    
    print(f"  {'Query vs Answer (正确答案)':30} {sim_answer_no_inst:^18.4f} {sim_answer_with_inst:^18.4f} {diff_answer:+.4f}")
    print(f"  {'Query vs Unrelated (无关文本)':30} {sim_unrelated_no_inst:^18.4f} {sim_unrelated_with_inst:^18.4f} {diff_unrelated:+.4f}")
    
    # 区分度
    gap_no_inst = sim_answer_no_inst - sim_unrelated_no_inst
    gap_with_inst = sim_answer_with_inst - sim_unrelated_with_inst
    print(f"\n  🎯 区分度 (Answer - Unrelated):")
    print(f"     不带 instruction: {gap_no_inst:.4f}")
    print(f"     带 instruction:   {gap_with_inst:.4f}")
    
    if gap_with_inst > gap_no_inst:
        print(f"     ✅ 带 instruction 区分度更高 (+{gap_with_inst - gap_no_inst:.4f})")
    else:
        print(f"     ⚠️ 不带 instruction 区分度更高 (+{gap_no_inst - gap_with_inst:.4f})")

# ========================================
# 总结
# ========================================
print("\n" + "=" * 70)
print("【总结】")
print("=" * 70)
print("""
区分度 = Query 与正确 Answer 的相似度 - Query 与无关文本的相似度

区分度越高，检索效果越好：
- 正确答案会排在前面
- 无关文本会排在后面

根据官方文档，使用 instruction 通常能提升 1-5% 的检索性能。
""")

