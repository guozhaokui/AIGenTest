#!/usr/bin/env python3
"""
测试Embedding服务

快速验证embedding配置是否正确
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.embedding import create_embedding_provider


def test_remote_bge():
    """测试远程BGE服务"""
    print("\n" + "=" * 60)
    print("测试远程BGE服务 (http://192.168.0.100:6012)")
    print("=" * 60)

    try:
        # 创建远程embedding provider
        emb = create_embedding_provider(
            "remote",
            base_url="http://192.168.0.100:6012"
        )

        # 健康检查
        print("\n1. 健康检查...")
        if emb.health_check():
            print("   ✓ 服务可用")
        else:
            print("   ✗ 服务不可用")
            print("   提示: 请确保BGE服务已启动")
            print("   启动命令: cd aiserver/embedding && ./start_embed_server.sh")
            return False

        # 获取维度
        print("\n2. 获取模型信息...")
        dimension = emb.get_dimension()
        print(f"   维度: {dimension}")
        print(f"   模型: BGE-Large-ZH")

        # 单个文本embedding
        print("\n3. 测试单个文本...")
        text = "这是一个测试句子"
        result = emb.embed(text)
        print(f"   ✓ Embedding成功")
        print(f"   形状: {result.embeddings.shape}")
        print(f"   维度: {result.dimension}")
        print(f"   向量范数: {(result.embeddings ** 2).sum() ** 0.5:.4f}")

        # 批量文本embedding
        print("\n4. 测试批量文本...")
        texts = [
            "linux81是内网服务器",
            "QAMath是数学问答系统",
            "使用Qwen-8B模型进行推理"
        ]
        result = emb.embed(texts)
        print(f"   ✓ Embedding成功")
        print(f"   形状: {result.embeddings.shape}")
        print(f"   文本数量: {len(texts)}")

        # 相似度测试
        print("\n5. 测试相似度计算...")
        query = "什么是QAMath？"
        query_result = emb.embed(query)

        # 计算余弦相似度
        import numpy as np
        query_vec = query_result.embeddings[0]
        similarities = np.dot(result.embeddings, query_vec)

        for i, (text, sim) in enumerate(zip(texts, similarities)):
            print(f"   {i+1}. [{sim:.4f}] {text}")

        print("\n✅ 远程BGE服务测试通过！")
        return True

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_local():
    """测试本地模型（可选）"""
    print("\n" + "=" * 60)
    print("测试本地Embedding模型")
    print("=" * 60)

    try:
        print("\n加载本地模型 (BAAI/bge-small-zh-v1.5)...")
        emb = create_embedding_provider(
            "local",
            model_name="BAAI/bge-small-zh-v1.5"
        )

        print(f"✓ 模型加载成功")
        print(f"维度: {emb.get_dimension()}")

        texts = ["测试文本1", "测试文本2"]
        result = emb.embed(texts)
        print(f"✓ Embedding成功: {result.embeddings.shape}")

        print("\n✅ 本地模型测试通过！")
        return True

    except ImportError:
        print("\n⚠️ 未安装 sentence-transformers")
        print("   安装: pip install sentence-transformers")
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def test_chromadb():
    """测试ChromaDB内置（可选）"""
    print("\n" + "=" * 60)
    print("测试ChromaDB内置Embedding")
    print("=" * 60)

    try:
        print("\n初始化ChromaDB embedding...")
        emb = create_embedding_provider("chromadb")

        print(f"✓ 初始化成功")
        print(f"维度: {emb.get_dimension()}")

        texts = ["测试文本1", "测试文本2"]
        result = emb.embed(texts)
        print(f"✓ Embedding成功: {result.embeddings.shape}")

        print("\n✅ ChromaDB内置测试通过！")
        return True

    except ImportError:
        print("\n⚠️ 未安装 chromadb")
        print("   安装: pip install chromadb")
        return False
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        return False


def main():
    print("\n" + "🔍 " * 20)
    print("Embedding服务测试")
    print("🔍 " * 20)

    results = {}

    # 测试远程BGE（主要）
    results["remote"] = test_remote_bge()

    # 询问是否测试其他选项
    print("\n" + "-" * 60)
    answer = input("\n是否测试本地模型和ChromaDB？(y/n, 默认n): ").strip().lower()

    if answer == 'y':
        results["local"] = test_local()
        results["chromadb"] = test_chromadb()

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name:12s}: {status}")

    if results.get("remote"):
        print("\n✅ 推荐使用远程BGE服务")
        print("   配置文件中设置: embedding.provider = 'remote'")
    else:
        print("\n⚠️ 远程BGE服务不可用")
        print("   请启动服务: cd aiserver/embedding && ./start_embed_server.sh")
        if results.get("local"):
            print("   或使用本地模型: embedding.provider = 'local'")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
