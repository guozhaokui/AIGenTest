"""
测试 MemGraph 服务状态
"""
import httpx
import asyncio


async def test_service():
    # 禁用代理
    client = httpx.AsyncClient(timeout=5.0, transport=httpx.HTTPTransport(proxy=None))

    print("=" * 60)
    print("测试 MemGraph 服务")
    print("=" * 60)

    # 测试 health
    print("\n1. 测试 /health...")
    try:
        response = await client.get("http://localhost:8800/health")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ 响应: {response.json()}")
        else:
            print(f"   ❌ 错误: {response.text}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")

    # 测试 stats
    print("\n2. 测试 /stats...")
    try:
        response = await client.get("http://localhost:8800/stats")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 文档数: {data['documents']}")
            print(f"   ✅ FAISS向量: {data['faiss_vectors']}")
            print(f"   ✅ N-gram: {data['ngrams']}")
        else:
            print(f"   ❌ 错误: {response.text}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")

    # 测试调试接口
    print("\n3. 测试 /debug/vectors...")
    try:
        response = await client.get("http://localhost:8800/debug/vectors")
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ 向量总数: {data['total_vectors']}")
            print(f"   ✅ 向量维度: {data['dimension']}")
            print(f"   ✅ 索引类型: {data['index_type']}")
        else:
            print(f"   ❌ 错误: {response.text}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(test_service())
