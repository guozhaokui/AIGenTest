#!/usr/bin/env python3
"""
Qwen3-Embedding-8B 服务测试脚本
测试各项功能：健康检查、嵌入计算、MRL 维度、Query/Document 区分
"""
import requests
import numpy as np
import json
import sys
from pathlib import Path

# 添加 aiserver 到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import url_embed_8b

# 服务地址
BASE_URL = url_embed_8b()
print(f"测试服务地址: {BASE_URL}")
print("=" * 60)


def test_health():
    """测试健康检查"""
    print("\n[1] 健康检查")
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f"  ✅ 服务正常")
            print(f"     模型: {data['model']}")
            print(f"     维度: {data['dimension']}")
            print(f"     量化: {data['quantization']}")
            print(f"     显存: {data['memory_gb']} GB")
            print(f"     设备: {data['device']}")
            return True
        else:
            print(f"  ❌ 健康检查失败: {resp.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        return False


def test_single_query():
    """测试单个 Query 嵌入（带 instruction）"""
    print("\n[2] 单个 Query 嵌入（带 instruction）")
    
    payload = {
        "text": "什么是人工智能？",
        "instruction": "Given a web search query, retrieve relevant passages that answer the query",
        "is_query": True
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/embed/text", json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            embedding = np.array(data["embedding"])
            print(f"  ✅ 成功")
            print(f"     维度: {data['dimension']}")
            print(f"     向量范数: {np.linalg.norm(embedding):.6f} (应接近 1.0)")
            print(f"     前5维: {embedding[:5]}")
            return embedding
        else:
            print(f"  ❌ 失败: {resp.status_code}")
            print(f"     {resp.text}")
            return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def test_single_document():
    """测试单个 Document 嵌入（不带 instruction）"""
    print("\n[3] 单个 Document 嵌入（不带 instruction）")
    
    payload = {
        "text": "人工智能（AI）是计算机科学的一个分支，旨在创建能够执行通常需要人类智能的任务的系统。",
        "is_query": False  # Document 不需要 instruction
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/embed/text", json=payload, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            embedding = np.array(data["embedding"])
            print(f"  ✅ 成功")
            print(f"     维度: {data['dimension']}")
            print(f"     向量范数: {np.linalg.norm(embedding):.6f} (应接近 1.0)")
            print(f"     前5维: {embedding[:5]}")
            return embedding
        else:
            print(f"  ❌ 失败: {resp.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def test_mrl_dimensions():
    """测试 MRL 可变维度"""
    print("\n[4] MRL 可变维度测试")
    
    text = "LayaAir 是一款高性能的游戏引擎"
    dimensions = [32, 128, 512, 1024, 4096]
    embeddings = {}
    
    for dim in dimensions:
        payload = {
            "text": text,
            "is_query": False,
            "output_dimension": dim
        }
        
        try:
            resp = requests.post(f"{BASE_URL}/embed/text", json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                embedding = np.array(data["embedding"])
                norm = np.linalg.norm(embedding)
                embeddings[dim] = embedding
                print(f"  ✅ {dim:4d} 维: 长度={len(embedding)}, 范数={norm:.6f}")
            else:
                print(f"  ❌ {dim:4d} 维失败")
        except Exception as e:
            print(f"  ❌ {dim:4d} 维请求失败: {e}")
    
    # 验证 MRL 嵌套关系：低维是高维的前缀
    if 128 in embeddings and 4096 in embeddings:
        prefix_match = np.allclose(embeddings[128], embeddings[4096][:128] / np.linalg.norm(embeddings[4096][:128]), rtol=1e-3)
        print(f"\n  🔍 MRL 嵌套验证: {'✅ 低维是高维前缀（归一化后）' if prefix_match else '⚠️ 需要重新归一化'}")
    
    return embeddings


def test_batch_embedding():
    """测试批量嵌入"""
    print("\n[5] 批量嵌入测试")
    
    # 批量 Document
    documents = [
        "LayaAir 是一款高性能 3D 游戏引擎",
        "Unity 是最流行的游戏开发平台之一",
        "Unreal Engine 以其高质量图形著称",
        "Godot 是一款开源的游戏引擎"
    ]
    
    payload = {
        "texts": documents,
        "is_query": False
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/embed/texts", json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            embeddings = np.array(data["embeddings"])
            print(f"  ✅ 成功")
            print(f"     数量: {data['count']}")
            print(f"     维度: {data['dimension']}")
            print(f"     形状: {embeddings.shape}")
            
            # 计算文档间相似度
            print("\n  📊 文档间余弦相似度:")
            for i in range(len(documents)):
                for j in range(i+1, len(documents)):
                    sim = np.dot(embeddings[i], embeddings[j])
                    print(f"     [{i}] vs [{j}]: {sim:.4f}")
            
            return embeddings
        else:
            print(f"  ❌ 失败: {resp.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return None


def test_query_document_similarity():
    """测试 Query-Document 相似度匹配"""
    print("\n[6] Query-Document 相似度匹配")
    
    # Query
    query = "如何使用 LayaAir 创建 3D 游戏？"
    query_payload = {
        "text": query,
        "instruction": "Given a web search query, retrieve relevant passages that answer the query",
        "is_query": True
    }
    
    # Documents
    documents = [
        "LayaAir 引擎支持 3D 游戏开发，提供完整的 3D 渲染管线和物理引擎。",  # 相关
        "使用 LayaAir 创建 3D 场景需要先导入 3D 模型，然后设置材质和光照。",  # 高度相关
        "Python 是一种通用编程语言，广泛用于数据科学和机器学习。",  # 不相关
        "今天天气很好，适合户外活动。"  # 完全不相关
    ]
    
    doc_payload = {
        "texts": documents,
        "is_query": False
    }
    
    try:
        # 获取 Query 嵌入
        query_resp = requests.post(f"{BASE_URL}/embed/text", json=query_payload, timeout=30)
        doc_resp = requests.post(f"{BASE_URL}/embed/texts", json=doc_payload, timeout=60)
        
        if query_resp.status_code == 200 and doc_resp.status_code == 200:
            query_emb = np.array(query_resp.json()["embedding"])
            doc_embs = np.array(doc_resp.json()["embeddings"])
            
            print(f"  Query: {query}")
            print(f"\n  📊 相似度排名:")
            
            similarities = []
            for i, doc in enumerate(documents):
                sim = np.dot(query_emb, doc_embs[i])
                similarities.append((sim, i, doc))
            
            # 按相似度排序
            similarities.sort(reverse=True)
            for rank, (sim, idx, doc) in enumerate(similarities, 1):
                doc_preview = doc[:50] + "..." if len(doc) > 50 else doc
                print(f"     {rank}. [{sim:.4f}] {doc_preview}")
            
            print("\n  ✅ 测试完成")
            return True
        else:
            print(f"  ❌ 请求失败")
            return False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return False


def test_instruction_effect():
    """测试 instruction 对嵌入的影响"""
    print("\n[7] Instruction 效果对比")
    
    text = "什么是机器学习？"
    
    # 不带 instruction
    payload_no_inst = {
        "text": text,
        "is_query": True  # 但没有 instruction
    }
    
    # 带 instruction
    payload_with_inst = {
        "text": text,
        "instruction": "Given a web search query, retrieve relevant passages that answer the query",
        "is_query": True
    }
    
    try:
        resp1 = requests.post(f"{BASE_URL}/embed/text", json=payload_no_inst, timeout=30)
        resp2 = requests.post(f"{BASE_URL}/embed/text", json=payload_with_inst, timeout=30)
        
        if resp1.status_code == 200 and resp2.status_code == 200:
            emb1 = np.array(resp1.json()["embedding"])
            emb2 = np.array(resp2.json()["embedding"])
            
            # 计算两个嵌入的相似度
            similarity = np.dot(emb1, emb2)
            diff = np.linalg.norm(emb1 - emb2)
            
            print(f"  文本: {text}")
            print(f"  不带 instruction vs 带 instruction:")
            print(f"     余弦相似度: {similarity:.6f}")
            print(f"     欧氏距离: {diff:.6f}")
            print(f"\n  💡 说明: 相似度越低，说明 instruction 对嵌入影响越大")
            return True
        else:
            print(f"  ❌ 请求失败")
            return False
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return False


def main():
    print("=" * 60)
    print("Qwen3-Embedding-8B 服务测试")
    print("=" * 60)
    
    # 1. 健康检查
    if not test_health():
        print("\n⚠️  服务不可用，请先启动服务：")
        print("   cd /home/layabox/laya/guo/AIGenTest/aiserver/embedding")
        print("   ./start_8b.sh")
        return
    
    # 2. 单个 Query 嵌入
    test_single_query()
    
    # 3. 单个 Document 嵌入
    test_single_document()
    
    # 4. MRL 可变维度
    test_mrl_dimensions()
    
    # 5. 批量嵌入
    test_batch_embedding()
    
    # 6. Query-Document 相似度
    test_query_document_similarity()
    
    # 7. Instruction 效果
    test_instruction_effect()
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()

