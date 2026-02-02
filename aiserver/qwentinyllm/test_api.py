"""
API 测试脚本
测试所有判断接口
"""
import httpx
import asyncio
import json


BASE_URL = "http://localhost:6015"


async def test_health():
    """测试健康检查"""
    print("\n" + "=" * 60)
    print("测试: 健康检查")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/health")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


async def test_info():
    """测试模型信息"""
    print("\n" + "=" * 60)
    print("测试: 模型信息")
    print("=" * 60)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/info")
        print(f"状态码: {response.status_code}")
        print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")


async def test_meaningless():
    """测试无意义短语判断"""
    print("\n" + "=" * 60)
    print("测试: 无意义短语判断")
    print("=" * 60)

    test_cases = [
        "的 是 在",
        "向量数据库",
        "FAISS 检索",
        "了 的 和",
        "Python 编程语言"
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for text in test_cases:
            print(f"\n输入: {text}")
            try:
                response = await client.post(
                    f"{BASE_URL}/api/judge/meaningless",
                    json={"text": text}
                )
                result = response.json()
                print(f"无意义: {result['is_meaningless']}")
                print(f"置信度: {result['confidence']:.2f}")
                print(f"理由: {result['reason']}")
            except Exception as e:
                print(f"错误: {e}")


async def test_similarity():
    """测试相似度判断"""
    print("\n" + "=" * 60)
    print("测试: 相似度判断")
    print("=" * 60)

    test_cases = [
        ("FAISS 是一个向量数据库", "FAISS 是向量数据库"),
        ("使用 Python 编程", "Python 编程语言"),
        ("机器学习算法", "深度学习模型"),
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for text1, text2 in test_cases:
            print(f"\n句子1: {text1}")
            print(f"句子2: {text2}")
            try:
                response = await client.post(
                    f"{BASE_URL}/api/judge/similarity",
                    json={"text1": text1, "text2": text2}
                )
                result = response.json()
                print(f"相似: {result['is_similar']}")
                print(f"相似度: {result['similarity_score']:.2f}")
                print(f"可合并: {result['can_merge']}")
                print(f"理由: {result['reason']}")
            except Exception as e:
                print(f"错误: {e}")


async def test_importance():
    """测试重要性评分"""
    print("\n" + "=" * 60)
    print("测试: 重要性评分")
    print("=" * 60)

    test_cases = [
        ("向量数据库", "使用 FAISS 向量数据库进行检索"),
        ("的 是", "这是一个例子"),
        ("Python", "Python 是一门编程语言"),
        ("机器学习", "机器学习算法研究"),
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for ngram, context in test_cases:
            print(f"\nN-gram: {ngram}")
            print(f"上下文: {context}")
            try:
                response = await client.post(
                    f"{BASE_URL}/api/judge/importance",
                    json={"ngram": ngram, "context": context}
                )
                result = response.json()
                print(f"重要性: {result['importance_score']:.2f}")
                print(f"应生成向量: {result['should_vectorize']}")
                print(f"类别: {result['category']}")
                print(f"理由: {result['reason']}")
            except Exception as e:
                print(f"错误: {e}")


async def test_quality():
    """测试文本质量评估"""
    print("\n" + "=" * 60)
    print("测试: 文本质量评估")
    print("=" * 60)

    test_cases = [
        "FAISS 是 Facebook AI Research 开发的向量检索库，支持高效的相似度搜索",
        "的 是 在",
        "Python",
        "本文介绍了深度学习的基本原理和常见应用场景"
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        for text in test_cases:
            print(f"\n文本: {text}")
            try:
                response = await client.post(
                    f"{BASE_URL}/api/judge/quality",
                    json={"text": text}
                )
                result = response.json()
                print(f"质量分: {result['quality_score']:.2f}")
                print(f"信息密度: {result['information_density']:.2f}")
                print(f"完整性: {result['completeness']:.2f}")
                print(f"检索价值: {result['retrieval_value']:.2f}")
                print(f"应索引: {result['should_index']}")
                print(f"理由: {result['reason']}")
            except Exception as e:
                print(f"错误: {e}")


async def test_batch():
    """测试批量判断"""
    print("\n" + "=" * 60)
    print("测试: 批量判断")
    print("=" * 60)

    texts = [
        "向量数据库",
        "的 是",
        "FAISS 检索",
        "在 了",
        "机器学习算法"
    ]

    print(f"输入文本列表: {texts}")

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/judge/batch",
                json={
                    "task": "meaningless",
                    "texts": texts
                }
            )
            result = response.json()
            print("\n批量判断结果:")
            for item in result['results']:
                print(f"  - {item['text']:<20} | 无意义: {item['is_meaningless']:<5} | 分数: {item['score']:.2f}")
        except Exception as e:
            print(f"错误: {e}")


async def run_all_tests():
    """运行所有测试"""
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║              Qwen3 Tiny LLM API 测试                         ║")
    print("╚══════════════════════════════════════════════════════════════╝")

    try:
        await test_health()
        await test_info()
        await test_meaningless()
        await test_similarity()
        await test_importance()
        await test_quality()
        await test_batch()

        print("\n" + "=" * 60)
        print("✅ 所有测试完成")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
