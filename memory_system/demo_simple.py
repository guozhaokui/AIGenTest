#!/usr/bin/env python3
"""
简化版Demo：测试2601.md的问答

快速验证RAG流程
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.vector_store import VectorStore, Document
from dotenv import load_dotenv
import openai


def main():
    print("\n" + "=" * 60)
    print("简化版RAG Demo - 测试2601.md")
    print("=" * 60)

    # 1. 准备测试文档（模拟2601.md）
    test_content = """
0107
MetaGPT
    在wsl环境下
    ~/work$ conda create -n metagpt python=3.9
    ~/work$ conda activate metagpt
    ~/work/MetaGPT$ pip install -e .
    ~/work/MetaGPT$ metagpt --init-config
    Configuration file initialized at /home/guozhaokui/.metagpt/config2.yaml
    ~/work/MetaGPT$ python -m metagpt.webserver.run --reload
    🌐 地址: http://0.0.0.0:8000

Claude Code
    cursor的对话记录对应 wsl的home目录
    server在wsl的 /home/guozhaokui/work/testcode/claudeserver
    需要先部署到usa服务器，然后在那个服务器上执行server.py
    claude code的配置在 ~/.claude/settings.json

linux81
~/laya/guo/AIGenTest/aiserver/test/QAMath$ python build_index.py 生成索引
(qwen) layabox@layabox-System-Product-Name:~/laya/guo/AIGenTest/aiserver/test/QAMath$ python server.py
因为有Qwen8B模型
start_8b.sh

sam3D测试
    8卡3090
    conda activate sam3d
    /data1/guo/AIGenTest/aiserver/sam3d/start_web.sh

linux21
    (hidream) ubuntu@ubuntu21:/mnt/hdd/guo/AIGenTest/aiserver/test$ python ./dinov3_server.py
    启动 DINOv3 可视化服务，端口: 6020
    访问 http://localhost:6020

(base) ubuntu@ubuntu21:/mnt/hdd/guo/AIGenTest/aiserver/embedding$ ./start_embed_server.sh
    BGE嵌入服务，端口: 6012
    SigLIP-2图片嵌入，端口: 6010
    """

    # 2. 初始化向量存储
    print("\n[步骤1] 初始化向量存储...")
    store = VectorStore(path=".memory_db/demo_simple", collection_name="simple_demo")
    store.clear()

    # 3. 索引文档
    print("\n[步骤2] 索引文档...")
    doc_ids = store.add_document(
        content=test_content,
        metadata={"source": "2601.md", "date": "2024-01-07"},
        chunk=True
    )
    print(f"  ✓ 文档分成 {len(doc_ids)} 个块")
    print(f"  ✓ 总文档数: {store.count()}")

    # 4. 测试查询
    print("\n[步骤3] 测试查询...")
    print("=" * 60)

    test_queries = [
        "MetaGPT怎么启动？",
        "QAMath在哪个服务器上？",
        "BGE嵌入服务的端口是多少？",
        "linux21上运行什么服务？"
    ]

    for query in test_queries:
        print(f"\n💬 问题: {query}")
        print("-" * 60)

        # 检索
        results = store.search(query, top_k=2)

        print(f"检索结果（Top-{len(results)}）:\n")
        for i, result in enumerate(results, 1):
            print(f"{i}. [相似度: {result.similarity:.3f}]")
            # 显示片段
            lines = result.content.strip().split('\n')[:3]
            for line in lines:
                if line.strip():
                    print(f"   {line}")
            print()

    # 5. 测试LLM回答（如果配置了API）
    print("\n[步骤4] 测试LLM生成回答...")
    print("=" * 60)

    # 加载环境变量
    env_path = Path(__file__).parent.parent / '.env'
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv('NVIDIA_API_KEY')
    if not api_key:
        print("⚠️ 未找到NVIDIA_API_KEY，跳过LLM测试")
        print("\n✅ Demo完成（向量检索部分）")
        return

    # 初始化LLM
    client = openai.OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key
    )

    # 测试一个问题
    query = "QAMath在哪个服务器上？怎么启动？"
    print(f"\n💬 问题: {query}")
    print("-" * 60)

    # 检索上下文
    results = store.search(query, top_k=3)
    context = "\n\n".join([r.content for r in results])

    print("检索到的上下文:")
    print(context[:200] + "...\n")

    # 构建prompt
    prompt = f"""基于以下文档内容回答问题。如果文档中没有相关信息，明确说明。

【文档内容】
{context}

【问题】
{query}

【回答】（简洁明了，标注来源）"""

    # 生成回答
    print("🤖 LLM回答:")
    print("-" * 60)

    try:
        completion = client.chat.completions.create(
            model="deepseek-ai/deepseek-v3.2",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.3
        )

        answer = completion.choices[0].message.content
        print(answer)
        print()

    except Exception as e:
        print(f"❌ LLM调用失败: {e}")

    # 6. 统计信息
    print("\n" + "=" * 60)
    print("统计信息")
    print("=" * 60)

    stats = store.stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n✅ Demo完成！")
    print("\n提示: 运行 python demo_e2e.py 体验完整版")
    print("=" * 60)


if __name__ == "__main__":
    main()
