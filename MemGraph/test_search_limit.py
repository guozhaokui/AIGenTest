"""
测试搜索的 limit 参数是否生效
"""
import asyncio
import httpx
import json


async def test_search_limit():
    url = "http://localhost:8800/search"

    print("=" * 60)
    print("测试搜索 limit 参数")
    print("=" * 60)

    # 测试不同的 limit 值
    test_cases = [
        {"limit": 2, "query": "claude"},
        {"limit": 5, "query": "claude"},
        {"limit": 10, "query": "claude"},
        {"limit": 20, "query": "claude"},
    ]

    for test in test_cases:
        payload = {
            "query": test["query"],
            "limit": test["limit"],
            "min_score": 0.0,  # 设为 0 确保不过滤
            "use_vector": True
        }

        print(f"\n{'='*60}")
        print(f"测试: limit={test['limit']}, query='{test['query']}'")
        print(f"请求: {json.dumps(payload, ensure_ascii=False)}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    data = response.json()

                    print(f"状态: ✅ 成功")
                    print(f"返回数量: {data['count']}")
                    print(f"期望数量: {test['limit']}")

                    if data['count'] <= test['limit']:
                        print(f"✅ PASS - 返回数量 ({data['count']}) <= 限制 ({test['limit']})")
                    else:
                        print(f"❌ FAIL - 返回数量 ({data['count']}) > 限制 ({test['limit']})")

                    # 显示结果列表
                    if data['results']:
                        print(f"\n结果列表:")
                        for idx, result in enumerate(data['results'], 1):
                            print(f"  {idx}. 得分={result['total_score']:.2f} - {result['path']}")
                else:
                    print(f"❌ HTTP 错误: {response.status_code}")
                    print(f"响应: {response.text}")

        except Exception as e:
            print(f"❌ 请求失败: {e}")

    print(f"\n{'='*60}")
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_search_limit())
