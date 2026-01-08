#!/usr/bin/env python3
"""
知识查询Web服务

提供API接口：
1. 文档索引
2. 记忆管理
3. 向量检索
4. 智能问答
"""

import sys
import os
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import openai
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from core.vector_store import VectorStore, Document
from core.embedding import create_embedding_provider

# 加载环境变量
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# 初始化Flask
app = Flask(__name__)
CORS(app)

# 全局变量
vector_store = None
nvidia_client = None
current_docs_path = None

# 配置
DOCS_DEFAULT_PATH = "/mnt/e/TEST/work/日志"  # 默认文档路径


def init_services():
    """初始化服务"""
    global vector_store, nvidia_client

    # 初始化向量存储
    print("初始化向量存储...")
    vector_store = VectorStore(
        path=".memory_db/web_vectors",
        collection_name="knowledge_base"
    )

    # 初始化NVIDIA API
    print("初始化NVIDIA API...")
    api_key = os.getenv('NVIDIA_API_KEY')
    if api_key:
        nvidia_client = openai.OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key
        )
        print("✓ NVIDIA API已初始化")
    else:
        print("⚠️ 未找到NVIDIA_API_KEY")

    print("✓ 服务初始化完成")


@app.route('/api/knowledge/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    return jsonify({
        'success': True,
        'data': {
            'vector_store': {
                'total_documents': vector_store.count() if vector_store else 0,
                'dimension': vector_store.embedding.get_dimension() if vector_store else 0,
            },
            'nvidia_api': nvidia_client is not None,
            'current_docs_path': current_docs_path,
            'embedding_service': {
                'available': vector_store.embedding.health_check() if vector_store else False,
                'type': 'BGE-Remote'
            }
        }
    })


@app.route('/api/knowledge/scan', methods=['POST'])
def scan_documents():
    """扫描文档目录"""
    data = request.json
    docs_path = data.get('path', DOCS_DEFAULT_PATH)

    path = Path(docs_path)
    if not path.exists():
        return jsonify({
            'success': False,
            'error': f'目录不存在: {docs_path}'
        }), 400

    # 扫描markdown文件
    md_files = list(path.glob('*.md'))

    files_info = []
    for md_file in md_files:
        try:
            stat = md_file.stat()
            content = md_file.read_text(encoding='utf-8')

            files_info.append({
                'name': md_file.name,
                'path': str(md_file),
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'length': len(content),
                'indexed': False  # TODO: 检查是否已索引
            })
        except Exception as e:
            print(f"读取文件失败 {md_file}: {e}")

    return jsonify({
        'success': True,
        'data': {
            'path': docs_path,
            'total': len(files_info),
            'files': files_info
        }
    })


@app.route('/api/knowledge/index', methods=['POST'])
def index_documents():
    """索引文档"""
    data = request.json
    files = data.get('files', [])  # 文件路径列表

    if not files:
        return jsonify({
            'success': False,
            'error': '未提供文件列表'
        }), 400

    global current_docs_path

    results = []
    total_chunks = 0

    for file_path in files:
        try:
            path = Path(file_path)
            if not path.exists():
                results.append({
                    'file': path.name,
                    'success': False,
                    'error': '文件不存在'
                })
                continue

            # 读取文件
            content = path.read_text(encoding='utf-8')

            # 添加到向量存储（自动分块）
            doc_ids = vector_store.add_document(
                content=content,
                metadata={
                    'source': path.name,
                    'path': str(path),
                    'type': 'markdown',
                    'indexed_at': datetime.now().isoformat()
                },
                chunk=True
            )

            total_chunks += len(doc_ids)
            current_docs_path = str(path.parent)

            results.append({
                'file': path.name,
                'success': True,
                'chunks': len(doc_ids)
            })

        except Exception as e:
            results.append({
                'file': Path(file_path).name,
                'success': False,
                'error': str(e)
            })

    return jsonify({
        'success': True,
        'data': {
            'results': results,
            'total_files': len(files),
            'success_count': sum(1 for r in results if r['success']),
            'total_chunks': total_chunks,
            'total_documents': vector_store.count()
        }
    })


@app.route('/api/knowledge/query', methods=['POST'])
def query_knowledge():
    """查询知识库"""
    data = request.json
    question = data.get('question', '')
    top_k = data.get('top_k', 3)
    model = data.get('model', 'deepseek-ai/deepseek-v3.2')

    if not question:
        return jsonify({
            'success': False,
            'error': '未提供问题'
        }), 400

    try:
        # 1. 向量检索
        results = vector_store.search(question, top_k=top_k)

        # 构建上下文
        context_docs = []
        for i, result in enumerate(results, 1):
            context_docs.append({
                'index': i,
                'source': result.metadata.get('source', 'unknown'),
                'content': result.content,
                'similarity': result.similarity
            })

        # 2. 生成回答（如果配置了NVIDIA API）
        answer = None
        if nvidia_client:
            context = "\n\n".join([
                f"【文档{doc['index']}】来源: {doc['source']}\n{doc['content']}"
                for doc in context_docs
            ])

            prompt = f"""基于以下文档内容回答问题。

【文档内容】
{context}

【用户问题】
{question}

【回答要求】
1. 只基于文档内容回答，不要添加文档外的信息
2. 如果文档中没有相关信息，明确说明
3. 回答要简洁明了
4. 标注信息来源（哪个文档）

【回答】"""

            completion = nvidia_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
                temperature=0.3
            )

            answer = completion.choices[0].message.content

        return jsonify({
            'success': True,
            'data': {
                'question': question,
                'answer': answer,
                'context': context_docs,
                'model': model
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/knowledge/models', methods=['GET'])
def list_models():
    """获取可用的模型列表"""
    # 从NVIDIA聊天应用的模型列表
    models = [
        {"id": "deepseek-ai/deepseek-v3.2", "name": "DeepSeek V3.2", "recommended": True},
        {"id": "deepseek-ai/deepseek-r1-0528", "name": "DeepSeek R1 (推理)", "recommended": True},
        {"id": "moonshotai/kimi-k2-thinking", "name": "Kimi K2 Thinking", "recommended": True},
        {"id": "z-ai/glm4.7", "name": "GLM-4.7", "recommended": True},
        {"id": "minimaxai/minimax-m2.1", "name": "MiniMax M2.1", "recommended": True},
        {"id": "meta/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "recommended": False},
        {"id": "qwen/qwen3-235b-a22b", "name": "Qwen3 235B", "recommended": False},
        {"id": "meta/llama-3.1-8b-instruct", "name": "Llama 3.1 8B (快速)", "recommended": False},
    ]

    return jsonify({
        'success': True,
        'data': models
    })


@app.route('/api/knowledge/clear', methods=['POST'])
def clear_knowledge():
    """清空知识库"""
    try:
        vector_store.clear()
        global current_docs_path
        current_docs_path = None

        return jsonify({
            'success': True,
            'message': '知识库已清空'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/knowledge/delete', methods=['POST'])
def delete_documents():
    """删除指定文档"""
    data = request.json
    source = data.get('source')  # 文件名

    if not source:
        return jsonify({
            'success': False,
            'error': '未提供文件名'
        }), 400

    try:
        # 按元数据删除
        count = vector_store.delete_by_metadata({'source': source})

        return jsonify({
            'success': True,
            'data': {
                'deleted_count': count,
                'remaining_count': vector_store.count()
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/knowledge/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    stats = vector_store.stats()

    return jsonify({
        'success': True,
        'data': stats
    })


def main():
    """启动服务"""
    print("\n" + "=" * 60)
    print("知识查询Web服务")
    print("=" * 60)

    # 初始化服务
    init_services()

    # 启动Flask
    port = int(os.getenv('KNOWLEDGE_API_PORT', 5001))

    print(f"\n启动API服务...")
    print(f"  地址: http://0.0.0.0:{port}")
    print(f"  文档: http://localhost:{port}/api/knowledge/status")
    print("\n" + "=" * 60 + "\n")

    app.run(host='0.0.0.0', port=port, debug=True)


if __name__ == '__main__':
    main()
