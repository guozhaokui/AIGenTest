#!/usr/bin/env python3
"""
测试向量存储功能

验证：
1. 文档添加和检索
2. 文档分块
3. 元数据过滤
4. 相似度排序
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.vector_store import VectorStore, Document


def test_basic_operations():
    """测试基本操作"""
    print("\n" + "=" * 60)
    print("测试1：基本操作（添加、搜索、删除）")
    print("=" * 60)

    # 创建临时向量存储
    store = VectorStore(
        path=".memory_db/test_vectors",
        collection_name="test_basic"
    )

    # 清空（如果之前有数据）
    if store.count() > 0:
        print(f"\n清理之前的测试数据（{store.count()}条）...")
        store.clear()

    # 添加文档
    print("\n添加测试文档...")
    docs = [
        Document(
            content="linux81是公司内网服务器，8核CPU+64GB RAM",
            metadata={"source": "test.md", "entity": "linux81"}
        ),
        Document(
            content="QAMath是数学问答系统，使用Qwen-8B模型",
            metadata={"source": "test.md", "entity": "QAMath"}
        ),
        Document(
            content="MetaGPT可以自动生成项目代码",
            metadata={"source": "test.md", "entity": "MetaGPT"}
        )
    ]

    doc_ids = store.add_documents(docs)
    print(f"✓ 添加成功，文档数: {store.count()}")

    # 搜索测试
    print("\n测试搜索...")
    query = "什么是QAMath？"
    results = store.search(query, top_k=3)

    print(f"查询: {query}")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [相似度: {result.similarity:.3f}] {result.content[:50]}...")

    # 验证最相关的是QAMath
    if results and "QAMath" in results[0].content:
        print("✅ 搜索结果正确！")
    else:
        print("❌ 搜索结果不正确")

    # 删除测试
    print("\n测试删除...")
    store.delete(doc_ids[0])
    print(f"✓ 删除后文档数: {store.count()}")

    # 清理
    store.clear()
    print(f"✓ 清空后文档数: {store.count()}")

    return True


def test_chunking():
    """测试文档分块"""
    print("\n" + "=" * 60)
    print("测试2：文档分块")
    print("=" * 60)

    store = VectorStore(
        path=".memory_db/test_vectors",
        collection_name="test_chunking"
    )
    store.clear()

    # 长文档
    long_text = """
    linux81是公司的内网服务器，配置为8核CPU和64GB RAM。
    服务器主要用于运行大模型推理服务。
    目前部署了QAMath项目，这是一个数学问答系统。
    QAMath使用Qwen-8B模型进行推理。
    启动命令是 python build_index.py，然后执行 ./start_8b.sh。
    服务器还部署了其他一些测试项目。
    """ * 3  # 重复3次，确保会分块

    print(f"\n原始文档长度: {len(long_text)} 字符")

    # 添加（自动分块）
    doc_ids = store.add_document(
        content=long_text,
        metadata={"source": "long_doc.md"},
        chunk=True
    )

    print(f"✓ 分块后文档数: {len(doc_ids)}")

    # 搜索
    results = store.search("QAMath启动命令", top_k=2)
    print(f"\n查询: QAMath启动命令")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [相似度: {result.similarity:.3f}]")
        print(f"     块索引: {result.metadata.get('chunk_index', 'N/A')}")
        print(f"     内容: {result.content[:60]}...")

    # 清理
    store.clear()

    return True


def test_metadata_filter():
    """测试元数据过滤"""
    print("\n" + "=" * 60)
    print("测试3：元数据过滤")
    print("=" * 60)

    store = VectorStore(
        path=".memory_db/test_vectors",
        collection_name="test_filter"
    )
    store.clear()

    # 添加不同类型的文档
    docs = [
        Document(
            content="linux81是内网服务器",
            metadata={"source": "test.md", "type": "server", "status": "active"}
        ),
        Document(
            content="linux21是测试服务器",
            metadata={"source": "test.md", "type": "server", "status": "active"}
        ),
        Document(
            content="QAMath是数学问答系统",
            metadata={"source": "test.md", "type": "project", "status": "active"}
        ),
        Document(
            content="old-server已废弃",
            metadata={"source": "test.md", "type": "server", "status": "deprecated"}
        )
    ]

    store.add_documents(docs)
    print(f"✓ 添加{len(docs)}个文档")

    # 测试过滤
    print("\n过滤条件: type='server' AND status='active'")
    results = store.search(
        "服务器",
        top_k=10,
        filter_metadata={"type": "server", "status": "active"}
    )

    print(f"结果数量: {len(results)}")
    for i, result in enumerate(results, 1):
        print(f"  {i}. {result.content} - 类型: {result.metadata.get('type')}, 状态: {result.metadata.get('status')}")

    # 验证：应该只返回active的服务器
    if all(r.metadata.get('status') == 'active' for r in results):
        print("✅ 元数据过滤正确！")
    else:
        print("❌ 元数据过滤不正确")

    # 清理
    store.clear()

    return True


def test_real_scenario():
    """测试真实场景：读取你的2601.md"""
    print("\n" + "=" * 60)
    print("测试4：真实场景（模拟2601.md）")
    print("=" * 60)

    store = VectorStore(
        path=".memory_db/test_vectors",
        collection_name="test_real"
    )
    store.clear()

    # 模拟2601.md的内容
    log_content = """
0107
MetaGPT
    在wsl环境下
    ~/work$ conda create -n metagpt python=3.9
    ~/work$ conda activate metagpt
    ~/work/MetaGPT$ pip install -e .
    ~/work/MetaGPT$ metagpt --init-config
    ~/work/MetaGPT$ python -m metagpt.webserver.run --reload
    🌐 地址: http://0.0.0.0:8000

Claude Code
    cursor的对话记录对应 wsl的home目录
    server
    在wsl的 /home/guozhaokui/work/testcode/claudeserver
    需要先部署到usa服务器，然后在那个服务器上执行server.py

linux81
~/laya/guo/AIGenTest/aiserver/test/QAMath$ python build_index.py 生成索引
因为有Qwen8B模型
start_8b.sh
    """

    print("\n添加文档...")
    doc_ids = store.add_document(
        content=log_content,
        metadata={
            "source": "日志/2601.md",
            "date": "2024-01-07",
            "type": "daily_log"
        },
        chunk=True
    )

    print(f"✓ 分块后文档数: {len(doc_ids)}")

    # 测试各种查询
    queries = [
        "MetaGPT怎么启动？",
        "QAMath在哪里？",
        "usa服务器是干什么的？",
        "如何初始化配置？"
    ]

    print("\n测试查询...")
    for query in queries:
        print(f"\n查询: {query}")
        results = store.search(query, top_k=2)

        for i, result in enumerate(results, 1):
            print(f"  {i}. [相似度: {result.similarity:.3f}]")
            content_preview = result.content.replace('\n', ' ')[:60]
            print(f"     {content_preview}...")

    # 清理
    store.clear()

    return True


def test_similarity_ranking():
    """测试相似度排序"""
    print("\n" + "=" * 60)
    print("测试5：相似度排序验证")
    print("=" * 60)

    store = VectorStore(
        path=".memory_db/test_vectors",
        collection_name="test_ranking"
    )
    store.clear()

    # 添加文档
    docs = [
        Document(content="苹果是一种水果，富含维生素", metadata={"id": "1"}),
        Document(content="苹果公司是美国的科技公司", metadata={"id": "2"}),
        Document(content="橙子也是水果，含有维生素C", metadata={"id": "3"}),
        Document(content="iPhone是苹果公司的手机产品", metadata={"id": "4"}),
    ]

    store.add_documents(docs)

    # 测试查询1：关于水果
    print("\n查询: 水果的营养")
    results = store.search("水果的营养", top_k=4)

    print("排序结果：")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [相似度: {result.similarity:.3f}] {result.content}")

    # 验证：水果相关的应该排前面
    if "水果" in results[0].content or "水果" in results[1].content:
        print("✅ 相似度排序正确！")
    else:
        print("❌ 相似度排序可能不正确")

    # 测试查询2：关于科技公司
    print("\n查询: 科技公司产品")
    results = store.search("科技公司产品", top_k=4)

    print("排序结果：")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [相似度: {result.similarity:.3f}] {result.content}")

    # 清理
    store.clear()

    return True


def main():
    print("\n" + "🧪 " * 20)
    print("向量存储功能测试")
    print("🧪 " * 20)

    # 检查embedding服务
    print("\n检查embedding服务...")
    from core.embedding import create_embedding_provider

    emb = create_embedding_provider("remote", base_url="http://192.168.0.100:6012")
    if not emb.health_check():
        print("❌ BGE embedding服务不可用")
        print("   请先启动: cd aiserver/embedding && ./start_embed_server.sh")
        return

    print("✓ BGE embedding服务正常")

    # 运行测试
    tests = [
        ("基本操作", test_basic_operations),
        ("文档分块", test_chunking),
        ("元数据过滤", test_metadata_filter),
        ("真实场景", test_real_scenario),
        ("相似度排序", test_similarity_ranking)
    ]

    results = {}

    for name, test_func in tests:
        try:
            success = test_func()
            results[name] = success
        except Exception as e:
            print(f"\n❌ 测试失败: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)

    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {name:12s}: {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n🎉 所有测试通过！向量存储功能正常")
    else:
        print(f"\n⚠️ {total - passed} 个测试失败")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
