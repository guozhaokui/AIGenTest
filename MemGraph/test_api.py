"""
快速测试MemGraph API
"""
import requests
import json

BASE_URL = "http://localhost:8800"


def test_health():
    """测试健康检查"""
    print("=" * 60)
    print("1. 健康检查")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()


def test_stats():
    """测试统计信息"""
    print("=" * 60)
    print("2. 统计信息")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/stats")
    print(f"Status: {response.status_code}")
    stats = response.json()
    print(f"文档数: {stats['documents']}")
    print(f"N-gram总数: {stats['ngrams']}")
    print(f"唯一N-gram: {stats['unique_ngrams']}")
    print(f"FAISS向量数: {stats['faiss_vectors']}")
    print()


def test_search():
    """测试搜索"""
    print("=" * 60)
    print("3. 搜索测试")
    print("=" * 60)

    queries = [
        "claude code mcp",
        "登录流程",
        "性能优化"
    ]

    for query in queries:
        print(f"\n查询: '{query}'")
        print("-" * 40)

        response = requests.post(
            f"{BASE_URL}/search",
            json={
                "query": query,
                "limit": 3,
                "use_vector": True
            }
        )

        if response.status_code != 200:
            print(f"错误: {response.status_code} - {response.text}")
            continue

        data = response.json()
        print(f"找到 {data['count']} 条结果\n")

        for idx, result in enumerate(data['results'][:3], 1):
            print(f"{idx}. {result['path']}")
            print(f"   得分: {result['total_score']:.2f}")
            print(f"   激活: {result.get('activation_score', 0):.2f} ({result.get('matched_ngrams', 0)}个片段)")

            if 'vector_similarity' in result:
                print(f"   向量: {result['vector_similarity']:.3f}")

            print(f"   问题: {result.get('problem_preview', '')[:60]}...")
            print()


def test_tags():
    """测试标签"""
    print("=" * 60)
    print("4. 标签测试")
    print("=" * 60)

    response = requests.get(f"{BASE_URL}/tags")
    data = response.json()

    print(f"共 {data['count']} 个标签:")
    print(", ".join(data['tags']))
    print()

    if data['tags']:
        tag = data['tags'][0]
        print(f"\n搜索标签: '{tag}'")
        print("-" * 40)

        response = requests.post(
            f"{BASE_URL}/search/tag",
            json={"tag": tag, "limit": 2}
        )

        data = response.json()
        print(f"找到 {data['count']} 条结果\n")

        for idx, result in enumerate(data['results'][:2], 1):
            print(f"{idx}. {result['path']}")
            print(f"   问题: {result.get('problem_preview', '')[:60]}...")
            print()


def test_recent():
    """测试最近记录"""
    print("=" * 60)
    print("5. 最近记录测试")
    print("=" * 60)

    response = requests.post(
        f"{BASE_URL}/recent",
        json={"limit": 3}
    )

    data = response.json()
    print(f"最近 {data['count']} 条记录:\n")

    for idx, result in enumerate(data['results'], 1):
        print(f"{idx}. {result['path']}")
        print(f"   时间: {result['timestamp']}")
        print(f"   问题: {result.get('problem_preview', '')[:60]}...")
        print()


def main():
    """运行所有测试"""
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║           MemGraph API 测试                                ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

    try:
        test_health()
        test_stats()
        test_search()
        test_tags()
        test_recent()

        print("\n╔════════════════════════════════════════════════════════════╗")
        print("║           测试完成！                                        ║")
        print("╚════════════════════════════════════════════════════════════╝\n")

    except requests.exceptions.ConnectionError:
        print("\n❌ 错误: 无法连接到MemGraph服务")
        print("请确保服务已启动: python start.py")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
