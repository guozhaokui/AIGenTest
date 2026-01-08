#!/usr/bin/env python3
"""
端到端Demo：从文档读取到智能问答

演示流程：
1. 读取真实文档（2601.md）
2. 向量化并存储
3. 用户提问
4. 检索相关文档
5. 调用LLM生成回答
"""

import sys
import os
from pathlib import Path
from typing import List

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.vector_store import VectorStore, Document
from core.embedding import create_embedding_provider


class SimpleRAGDemo:
    """简单的RAG演示系统"""

    def __init__(self, docs_path: str = "/mnt/e/TEST/work/日志"):
        """
        Args:
            docs_path: 文档目录路径
        """
        self.docs_path = Path(docs_path)

        # 初始化向量存储
        print("=" * 60)
        print("初始化RAG系统")
        print("=" * 60)

        self.vector_store = VectorStore(
            path=".memory_db/demo_vectors",
            collection_name="demo"
        )

        # 清空之前的数据（demo）
        if self.vector_store.count() > 0:
            print(f"\n清理之前的demo数据（{self.vector_store.count()}条）...")
            self.vector_store.clear()

        # 初始化NVIDIA API（用于生成回答）
        self.setup_llm()

    def setup_llm(self):
        """初始化LLM API"""
        from dotenv import load_dotenv
        import openai

        # 加载环境变量
        env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(dotenv_path=env_path)

        api_key = os.getenv('NVIDIA_API_KEY')
        if not api_key:
            print("⚠️ 未找到NVIDIA_API_KEY，将无法生成回答")
            self.llm_client = None
            return

        self.llm_client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )

        print("✓ NVIDIA API已初始化")

    def load_documents(self):
        """加载文档目录下的所有markdown文件"""
        print("\n" + "=" * 60)
        print("加载文档")
        print("=" * 60)

        if not self.docs_path.exists():
            print(f"⚠️ 文档目录不存在: {self.docs_path}")
            print("  使用示例文档...")
            return self.load_example_documents()

        md_files = list(self.docs_path.glob("*.md"))
        print(f"\n找到 {len(md_files)} 个Markdown文件")

        documents = []
        for md_file in md_files[:5]:  # 限制只加载前5个文件（demo）
            try:
                content = md_file.read_text(encoding='utf-8')
                print(f"  ✓ {md_file.name} ({len(content)} 字符)")

                documents.append(Document(
                    content=content,
                    metadata={
                        "source": md_file.name,
                        "path": str(md_file),
                        "type": "daily_log"
                    }
                ))
            except Exception as e:
                print(f"  ✗ {md_file.name}: {e}")

        return documents

    def load_example_documents(self):
        """加载示例文档（如果找不到真实文档）"""
        print("\n使用示例文档...")

        example_content = """
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
    server
    在wsl的 /home/guozhaokui/work/testcode/claudeserver
    需要先部署到usa服务器，然后在那个服务器上执行server.py
    claude code的配置在 ~/.claude$ nano settings.json
    ~/work/testcode/claudeserver$ python test_thinking_cache.py
    这个thinking的测试没有通过

linux81
~/laya/guo/AIGenTest/aiserver/test/QAMath$ python build_index.py 生成索引
(qwen) layabox@layabox-System-Product-Name:~/laya/guo/AIGenTest/aiserver/test/QAMath$ python server.py
因为有Qwen8B模型
start_8b.sh
stop_8b.sh

sam3D测试
    8卡3090
    conda activate sam3d
    /data1/guo/AIGenTest/aiserver/sam3d/start_web.sh

linux21
    有一个iquest环境，下载了 mlx-community/IQuest-Coder-V1-40B-Loop-Instruct-4bit 模型
    这个模型是给mac用的，所以失败了
    (hidream) ubuntu@ubuntu21:/mnt/hdd/guo/AIGenTest/aiserver/test$ python ./dinov3_server.py
启动 DINOv3 可视化服务，端口: 6020
访问 http://localhost:6020

(base) ubuntu@ubuntu21:/mnt/hdd/guo/AIGenTest/aiserver/embedding$ ./start_embed_server.sh
    BGE
    siglip2

windows claude code
set HTTPS_PROXY=http://127.0.0.1:10809
export https_proxy=http://127.0.0.1:10809

在gitbash下安装
$ export CLAUDE_CODE_GIT_BASH_PATH="D:\\Program Files\\Git\\git-bash.exe"
        """

        return [Document(
            content=example_content,
            metadata={
                "source": "示例-2601.md",
                "type": "daily_log"
            }
        )]

    def index_documents(self, documents: List[Document]):
        """索引文档到向量数据库"""
        print("\n" + "=" * 60)
        print("索引文档")
        print("=" * 60)

        print(f"\n正在索引 {len(documents)} 个文档...")

        for doc in documents:
            # 自动分块并添加
            doc_ids = self.vector_store.add_document(
                content=doc.content,
                metadata=doc.metadata,
                chunk=True  # 启用分块
            )

            source = doc.metadata.get('source', 'unknown')
            print(f"  ✓ {source}: 分成 {len(doc_ids)} 个块")

        total = self.vector_store.count()
        print(f"\n✓ 索引完成，总文档数: {total}")

    def search(self, query: str, top_k: int = 3):
        """检索相关文档"""
        print(f"\n🔍 检索: {query}")
        print("-" * 60)

        results = self.vector_store.search(query, top_k=top_k)

        print(f"找到 {len(results)} 个相关文档:\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. [相似度: {result.similarity:.3f}] {result.metadata.get('source', 'unknown')}")
            # 显示内容片段
            content_preview = result.content.replace('\n', ' ')[:80]
            print(f"   {content_preview}...")
            print()

        return results

    def generate_answer(self, query: str, context_docs):
        """使用LLM生成回答"""
        if not self.llm_client:
            print("⚠️ LLM未初始化，无法生成回答")
            return None

        print("🤖 生成回答...")
        print("-" * 60)

        # 构建上下文
        context = "\n\n".join([
            f"【文档{i+1}】来源: {doc.metadata.get('source')}\n{doc.content}"
            for i, doc in enumerate(context_docs)
        ])

        # 构建prompt
        prompt = f"""基于以下文档内容回答问题。

【文档内容】
{context}

【用户问题】
{query}

【回答要求】
1. 只基于文档内容回答，不要添加文档外的信息
2. 如果文档中没有相关信息，明确说明
3. 回答要简洁明了
4. 标注信息来源（哪个文档）

【回答】"""

        try:
            # 调用NVIDIA API
            completion = self.llm_client.chat.completions.create(
                model="deepseek-ai/deepseek-v3.2",
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1024,
                temperature=0.3
            )

            answer = completion.choices[0].message.content
            print(answer)
            print()

            return answer

        except Exception as e:
            print(f"❌ 生成回答失败: {e}")
            return None

    def query(self, question: str):
        """完整的查询流程"""
        print("\n" + "=" * 60)
        print(f"问题: {question}")
        print("=" * 60)

        # 1. 检索相关文档
        docs = self.search(question, top_k=3)

        if not docs:
            print("❌ 未找到相关文档")
            return

        # 2. 生成回答
        answer = self.generate_answer(question, docs)

        return {
            "question": question,
            "documents": docs,
            "answer": answer
        }

    def interactive_mode(self):
        """交互模式"""
        print("\n" + "=" * 60)
        print("交互式问答（输入 'quit' 退出）")
        print("=" * 60)

        while True:
            try:
                question = input("\n💬 你的问题: ").strip()

                if not question:
                    continue

                if question.lower() in ['quit', 'exit', 'q']:
                    print("\n再见！")
                    break

                self.query(question)

            except KeyboardInterrupt:
                print("\n\n再见！")
                break
            except Exception as e:
                print(f"\n❌ 错误: {e}")


def main():
    """主函数"""
    print("\n" + "🚀 " * 20)
    print("端到端RAG Demo")
    print("🚀 " * 20)

    # 创建demo系统
    demo = SimpleRAGDemo(docs_path="/mnt/e/TEST/work/日志")

    # 1. 加载文档
    documents = demo.load_documents()

    if not documents:
        print("❌ 没有找到文档")
        return

    # 2. 索引文档
    demo.index_documents(documents)

    # 3. 测试查询
    print("\n" + "=" * 60)
    print("测试查询")
    print("=" * 60)

    test_queries = [
        "MetaGPT怎么启动？",
        "QAMath在哪个服务器上？",
        "有哪些服务器？",
        "Claude Code的配置在哪里？"
    ]

    for query in test_queries:
        demo.query(query)
        print("\n" + "-" * 60)
        input("按回车继续下一个问题...")

    # 4. 进入交互模式
    print("\n\n")
    choice = input("是否进入交互模式？(y/n): ").strip().lower()

    if choice == 'y':
        demo.interactive_mode()

    print("\n" + "=" * 60)
    print("Demo结束")
    print("=" * 60)


if __name__ == "__main__":
    main()
