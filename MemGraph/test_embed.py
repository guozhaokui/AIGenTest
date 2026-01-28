"""
测试嵌入服务的响应格式
"""
import asyncio
import httpx
import json


async def test_embedding():
    # 直接访问 GPU 服务器的嵌入服务
    url = "http://192.168.0.132:6014/embed/text"

    payload = {
        "text": "这是一个测试文本"
    }

    print("=" * 60)
    print("测试 Qwen3-8B 嵌入服务（直接访问 GPU 服务器）")
    print("=" * 60)
    print(f"\n请求 URL: {url}")
    print(f"请求体: {json.dumps(payload, ensure_ascii=False)}\n")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)

            print(f"状态码: {response.status_code}")
            print(f"响应头: {dict(response.headers)}\n")

            if response.status_code == 200:
                data = response.json()

                print("响应体结构:")
                print(f"  - 类型: {type(data)}")
                print(f"  - 键: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")

                # 检查嵌入向量
                if isinstance(data, dict):
                    for key in ['embedding', 'embeddings', 'vector', 'data']:
                        if key in data:
                            emb = data[key]
                            print(f"\n找到键: '{key}'")
                            print(f"  - 类型: {type(emb)}")
                            print(f"  - 长度: {len(emb) if isinstance(emb, (list, tuple)) else 'N/A'}")
                            if isinstance(emb, (list, tuple)) and len(emb) > 0:
                                print(f"  - 前10维: {emb[:10]}")
                                print(f"  - 是否全零: {all(x == 0 for x in emb[:100])}")
                elif isinstance(data, list):
                    print(f"\n响应是列表")
                    print(f"  - 长度: {len(data)}")
                    print(f"  - 前10维: {data[:10]}")

                print(f"\n完整响应 (前500字符):")
                print(str(data)[:500])
            else:
                print(f"❌ 错误响应: {response.text}")

    except httpx.ConnectError:
        print("❌ 连接失败: GPU 服务器可能未启动或不可达")
        print("\n检查:")
        print("  1. GPU 服务器 192.168.0.132 是否在线？")
        print("  2. 端口 6014 的嵌入服务是否启动？")
        print("  3. 网络连接是否正常？")
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_embedding())
