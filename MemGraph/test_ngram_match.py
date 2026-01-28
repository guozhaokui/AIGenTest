"""
测试 N-gram 匹配详情
"""
import httpx
import asyncio
import json


async def test_ngram_match():
    url = "http://localhost:8800/debug/search-full"

    payload = {
        "query": "如何配置mcp",
        "limit": 2,
        "min_score": 0.0
    }

    print("=" * 80)
    print("测试 N-gram 匹配详情")
    print("=" * 80)
    print(f"\n查询: {payload['query']}\n")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)

            if response.status_code == 200:
                data = response.json()

                print(f"✅ 找到 {data['count']} 条结果\n")

                for idx, result in enumerate(data['results'], 1):
                    print(f"{'=' * 80}")
                    print(f"结果 {idx}: {result['path']}")
                    print(f"{'=' * 80}")
                    print(f"总得分: {result['total_score']:.2f}")
                    print(f"激活得分: {result.get('activation_score', 0):.2f}")
                    print(f"向量相似度: {result.get('vector_similarity', 0):.4f}")
                    print(f"匹配片段数: {result.get('matched_ngrams', 0)}")

                    if 'match_details' in result and result['match_details']:
                        print(f"\nN-gram 匹配详情 (前 10 条):")
                        print(f"{'-' * 80}")
                        print(f"{'序号':<6} {'内容':<20} {'类型':<15} {'章节':<12} {'得分':<8}")
                        print(f"{'-' * 80}")

                        for i, detail in enumerate(result['match_details'][:10], 1):
                            content = detail['content'][:18] + '..' if len(detail['content']) > 20 else detail['content']
                            print(f"{i:<6} {content:<20} {detail['type']:<15} {detail['section']:<12} {detail['score']:<8.2f}")

                        if len(result['match_details']) > 10:
                            print(f"... 还有 {len(result['match_details']) - 10} 条匹配\n")
                    else:
                        print("\n❌ 没有 match_details 字段\n")

            else:
                print(f"❌ HTTP 错误: {response.status_code}")
                print(response.text)

    except Exception as e:
        print(f"❌ 请求失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ngram_match())
