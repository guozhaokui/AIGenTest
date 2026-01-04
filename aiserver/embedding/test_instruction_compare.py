#!/usr/bin/env python3
"""
对比 instruction 对嵌入的影响
"""
import requests
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import url_embed_8b

BASE_URL = url_embed_8b()

text = "什么是机器学习？"

print("=" * 60)
print(f"测试文本: {text}")
print("=" * 60)

# ========================================
# 情况 1: 不带 instruction
# ========================================
print("\n【情况 1】不带 instruction")
print("  发送内容: 直接发送原文本")

resp1 = requests.post(f"{BASE_URL}/embed/text", json={
    "text": text,
    "is_query": True,
    # 没有 instruction
})
emb1 = np.array(resp1.json()["embedding"])

print(f"  维度: {len(emb1)}")
print(f"  前 10 维: {emb1[:10].round(4)}")
print(f"  范数: {np.linalg.norm(emb1):.6f}")

# ========================================
# 情况 2: 带 instruction
# ========================================
print("\n【情况 2】带 instruction")
instruction = "Given a web search query, retrieve relevant passages that answer the query"
print(f"  Instruction: {instruction}")
print(f"  发送内容: Instruct: {instruction}\\nQuery:{text}")

resp2 = requests.post(f"{BASE_URL}/embed/text", json={
    "text": text,
    "instruction": instruction,
    "is_query": True,
})
emb2 = np.array(resp2.json()["embedding"])

print(f"  维度: {len(emb2)}")
print(f"  前 10 维: {emb2[:10].round(4)}")
print(f"  范数: {np.linalg.norm(emb2):.6f}")

# ========================================
# 对比分析
# ========================================
print("\n" + "=" * 60)
print("【对比分析】")
print("=" * 60)

# 余弦相似度
cosine_sim = np.dot(emb1, emb2)
print(f"\n  余弦相似度: {cosine_sim:.6f}")
print(f"  (1.0 = 完全相同, 0.0 = 正交无关)")

# 欧氏距离
euclidean_dist = np.linalg.norm(emb1 - emb2)
print(f"\n  欧氏距离: {euclidean_dist:.6f}")
print(f"  (0.0 = 完全相同, 越大差异越大)")

# 维度差异
diff = emb1 - emb2
print(f"\n  各维度差异 (前 10 维):")
print(f"    情况1:   {emb1[:10].round(4)}")
print(f"    情况2:   {emb2[:10].round(4)}")
print(f"    差值:    {diff[:10].round(4)}")

# 统计
print(f"\n  差异统计:")
print(f"    最大差值: {np.max(np.abs(diff)):.6f}")
print(f"    平均差值: {np.mean(np.abs(diff)):.6f}")
print(f"    标准差:   {np.std(diff):.6f}")

# 结论
print("\n" + "=" * 60)
print("【结论】")
print("=" * 60)
if cosine_sim > 0.95:
    print("  instruction 对嵌入影响很小 (相似度 > 0.95)")
elif cosine_sim > 0.8:
    print("  instruction 对嵌入有中等影响 (0.8 < 相似度 < 0.95)")
else:
    print("  instruction 对嵌入有显著影响 (相似度 < 0.8)")

print(f"\n  实际相似度: {cosine_sim:.4f}")
print("  这意味着带 instruction 后，嵌入向量发生了明显变化")
print("  模型会根据 instruction 调整语义理解方向")

