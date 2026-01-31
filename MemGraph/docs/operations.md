# MemGraph 操作指南

## 1. 服务管理

### 1.1 启动服务

**标准启动：**
```bash
cd /path/to/MemGraph
python -m src.server
```

**后台启动：**
```bash
# Linux/macOS
nohup python -m src.server > logs/server.log 2>&1 &

# Windows
start /B python -m src.server
```

**服务信息：**
- 默认端口：8800
- 监听地址：0.0.0.0（所有网络接口）
- 配置文件：`src/config.py`

**启动输出：**
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8800 (Press CTRL+C to quit)
```

### 1.2 停止服务

**交互式停止：**
```bash
# 按 Ctrl+C
```

**强制停止（通过进程 ID）：**
```bash
# Linux/macOS
ps aux | grep "src.server"
kill <PID>

# Windows
netstat -ano | findstr "8800"
taskkill //F //PID <PID>
```

**强制停止（通过端口）：**
```bash
# Linux/macOS
lsof -ti:8800 | xargs kill -9

# Windows
FOR /F "tokens=5" %P IN ('netstat -ano ^| findstr :8800') DO taskkill /F /PID %P
```

### 1.3 检查服务状态

**检查端口：**
```bash
# Linux/macOS
lsof -i:8800

# Windows
netstat -ano | findstr "8800"
```

**检查服务健康：**
```bash
curl --noproxy "*" http://localhost:8800/stats
```

预期返回：
```json
{
    "documents": 21,
    "ngrams": 19546,
    "unique_ngrams": 13357,
    "faiss_vectors": 6171
}
```

### 1.4 重启服务

```bash
# 停止服务（Ctrl+C 或 kill）
# 等待 2-3 秒
# 重新启动
python -m src.server
```

---

## 2. 测试

### 2.1 基础功能测试

**测试脚本位置：**
```
MemGraph/
├── test_search_metagpt.py      # 搜索功能测试
├── test_manual_init.py         # 初始化测试
├── test_embed.py               # 嵌入服务测试
├── test_record.py              # 记录功能测试
├── test_api.py                 # API 测试
└── test_ngram_match.py         # N-gram 匹配测试
```

**运行测试：**
```bash
cd /path/to/MemGraph

# 测试初始化
python test_manual_init.py

# 测试搜索
python test_search_metagpt.py

# 测试嵌入服务
python test_embed.py
```

### 2.2 API 测试

**测试统计接口：**
```bash
curl --noproxy "*" http://localhost:8800/stats
```

**测试搜索接口：**
```bash
curl --noproxy "*" -X POST "http://localhost:8800/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "metagpt", "limit": 3}'
```

**测试最近记录：**
```bash
curl --noproxy "*" -X POST "http://localhost:8800/recent" \
  -H "Content-Type: application/json" \
  -d '{"limit": 5}'
```

**测试标签搜索：**
```bash
curl --noproxy "*" -X POST "http://localhost:8800/search/tag" \
  -H "Content-Type: application/json" \
  -d '{"tag": "MCP", "limit": 5}'
```

**测试记录新文档：**
```bash
curl --noproxy "*" -X POST "http://localhost:8800/record" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "AI",
    "problem": "测试问题",
    "solution": "测试解决方案",
    "tags": ["测试"]
  }'
```

### 2.3 性能测试

**测试向量生成速度：**
```python
import asyncio
import time
from src.embedding_client import EmbeddingClient

async def test_embed_speed():
    client = EmbeddingClient()

    texts = ["这是一个测试句子"] * 10

    start = time.time()
    for text in texts:
        embedding = await client.embed_text(text)
    elapsed = time.time() - start

    print(f"生成 {len(texts)} 个向量耗时: {elapsed:.2f}秒")
    print(f"平均速度: {len(texts)/elapsed:.2f} 个/秒")

asyncio.run(test_embed_speed())
```

**测试搜索速度：**
```python
import asyncio
import time
from src.knowledge_indexer import KnowledgeIndexer
from src.activation_search import ActivationSearch

async def test_search_speed():
    indexer = KnowledgeIndexer()
    search = ActivationSearch(indexer)

    queries = ["metagpt", "linux", "配置", "向量", "搜索"]

    start = time.time()
    for query in queries:
        results = await search.search(query, {'limit': 5})
    elapsed = time.time() - start

    print(f"执行 {len(queries)} 次搜索耗时: {elapsed:.2f}秒")
    print(f"平均速度: {len(queries)/elapsed:.2f} 次/秒")

asyncio.run(test_search_speed())
```

### 2.4 数据一致性测试

**检查向量数量一致性：**
```python
import sqlite3
import faiss

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# SQLite 中的向量引用
cursor.execute('SELECT COUNT(*) FROM documents')
doc_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM document_vectors')
doc_vec_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM ngram_vectors')
ngram_vec_count = cursor.fetchone()[0]

# FAISS 中的向量
index = faiss.read_index('data/knowledge.faiss')
faiss_total = index.ntotal

sqlite_total = doc_count + doc_vec_count + ngram_vec_count

print(f"SQLite 总计: {sqlite_total}")
print(f"  - 文档向量: {doc_count}")
print(f"  - 片段向量: {doc_vec_count}")
print(f"  - N-gram向量: {ngram_vec_count}")
print(f"FAISS 总计: {faiss_total}")
print(f"一致性: {'通过' if sqlite_total == faiss_total else '失败'}")

conn.close()
```

---

## 3. 注意事项

### 3.1 HTTP 代理问题

**问题表现：**
- curl 请求返回 503
- 请求长时间无响应
- 服务器日志无任何请求记录

**原因：**
本地可能配置了 HTTP 代理（如梯子），代理会拦截 localhost 请求。

**检查代理：**
```bash
# Linux/macOS
echo $http_proxy
echo $https_proxy

# Windows
echo %http_proxy%
echo %https_proxy%
```

**解决方案 1：绕过代理**
```bash
# 单次请求
curl --noproxy "*" http://localhost:8800/stats

# 临时禁用代理
unset http_proxy https_proxy  # Linux/macOS
set http_proxy=               # Windows
```

**解决方案 2：配置代理例外**
```bash
# 添加到 ~/.bashrc 或 ~/.zshrc (Linux/macOS)
export no_proxy="localhost,127.0.0.1"

# Windows 系统设置 > 网络 > 代理 > 例外
```

### 3.2 延迟初始化机制

**特性说明：**
- 服务器启动后不立即加载数据
- 第一次请求时才初始化 KnowledgeIndexer
- 初始化需要 5-10 秒（加载 FAISS 索引）

**表现：**
- 首次请求响应慢
- 后续请求正常响应

**日志输出：**
```
Lazy initializing MemGraph...
Loaded FAISS index with 6171 vectors
MemGraph initialized: 21 documents indexed
```

**建议：**
- 启动后等待 10 秒再测试
- 或先调用 `/stats` 触发初始化

### 3.3 嵌入服务依赖

**服务地址：**
```python
# src/config.py
EMBED_SERVICE_URL = "http://192.168.0.132:6014/embed/text"
```

**注意事项：**
- 必须确保嵌入服务可访问
- 网络延迟会影响索引速度
- 建议使用局域网地址

**测试连接：**
```bash
curl -X POST "http://192.168.0.132:6014/embed/text" \
  -H "Content-Type: application/json" \
  -d '{"text": "测试"}'
```

预期返回：
```json
{
  "embedding": [0.028, -0.021, ...]
}
```

**常见问题：**
- 网络不通：检查防火墙、路由
- 服务未启动：启动嵌入服务
- 超时：增加 timeout（`embedding_client.py` 中设置）

### 3.4 FAISS 索引问题

**问题 1：索引文件不存在**
```
错误：FileNotFoundError: data/knowledge.faiss
```

**解决：**
```bash
python rebuild_vectors.py
```

**问题 2：维度不匹配**
```
错误：Embedding dimension mismatch: expected 4096, got xxx
```

**解决：**
- 检查 `EMBED_DIMENSION` 配置
- 确认嵌入服务返回的维度
- 重建索引

**问题 3：索引损坏**
```
错误：RuntimeError: faiss index error
```

**解决：**
```bash
# 删除旧索引
rm data/knowledge.faiss

# 重建
python rebuild_vectors.py
```

### 3.5 数据库锁定问题

**问题表现：**
```
sqlite3.OperationalError: database is locked
```

**原因：**
- 多个进程同时访问 SQLite
- 前一个连接未正常关闭

**解决：**
```bash
# 1. 停止所有 MemGraph 服务进程
pkill -f "src.server"

# 2. 等待几秒让 SQLite 释放锁

# 3. 重新启动
python -m src.server
```

**预防：**
- 确保同时只有一个服务进程
- 正确处理异常，确保 conn.close()

### 3.6 大小写敏感问题

**已解决：**
从 V3 开始，所有 N-gram 已转为小写存储。

**测试验证：**
```python
import sqlite3

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# 查看 N-gram 是否包含大写字母
cursor.execute("SELECT content FROM ngrams WHERE content != LOWER(content) LIMIT 5")
results = cursor.fetchall()

if results:
    print("发现大写 N-gram，需要重建索引")
else:
    print("所有 N-gram 已是小写，搜索正常")

conn.close()
```

### 3.7 句子向量生成

**配置：**
```python
# src/knowledge_indexer.py
# 分割句子时的最小长度
if 10 <= len(sent) <= 500:  # 最小 10 字符
    chunks['sentences'].append(sent)
```

**注意：**
- 最小长度：10 字符（之前是 20）
- 最大长度：500 字符
- 索引所有句子（之前只索引前 5 个）

**影响：**
- 句子向量数量大幅增加
- 搜索精度提高
- 索引时间增加

### 3.8 内存使用

**典型内存占用：**
```
FAISS 索引:     约 95 MB (6171 × 4096 × 4 bytes)
SQLite 缓存:    约 10-20 MB
Python 进程:    约 200-300 MB
总计:           约 300-400 MB
```

**大规模数据：**
- 1000 文档：约 2-3 GB 内存
- 10000 文档：约 20-30 GB 内存

**优化建议：**
- 使用 FAISS IVF 索引（近似搜索）
- 分片存储大规模数据
- 增加服务器内存

---

## 4. 维护操作

### 4.1 完整重建索引

**何时需要：**
- 修改了 N-gram 生成逻辑
- 修改了向量生成逻辑
- 数据损坏或不一致
- 嵌入模型更换

**操作步骤：**
```bash
cd /path/to/MemGraph

# 1. 停止服务
pkill -f "src.server"

# 2. 备份数据（可选）
cp data/knowledge.db data/knowledge.db.backup
cp data/knowledge.faiss data/knowledge.faiss.backup

# 3. 运行重建脚本
python rebuild_vectors.py

# 4. 等待完成（约 5-10 分钟，取决于文档数量）

# 5. 重新启动服务
python -m src.server
```

**重建输出示例：**
```
================================================================================
重建向量索引
================================================================================

1. 初始化索引器...
Loaded FAISS index with 0 vectors

2. 清除现有数据...
Created new FAISS index (dimension: 4096)

3. 扫描文档...
   找到 21 个 markdown 文件

   处理 1/21: 概念.md
Added vector for doc_id=173, faiss_idx=0, norm=1.0000
  生成文档 173 的多粒度向量...
    共生成 13 个多粒度向量 (段落: 3, 句子: 10)
...

================================================================================
重建完成！
   文档数: 21
   N-grams: 19546
   FAISS向量: 6171
================================================================================
```

### 4.2 增量更新文档

**API 方式：**
```bash
# 记录新文档
curl --noproxy "*" -X POST "http://localhost:8800/record" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "AI",
    "problem": "新问题",
    "solution": "新解决方案",
    "project": "项目名",
    "tags": ["标签1", "标签2"]
  }'

# 更新已有文档
curl --noproxy "*" -X POST "http://localhost:8800/update" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": 193,
    "solution": "更新后的解决方案",
    "tags": ["新标签"]
  }'
```

**注意：**
- 更新文档需要重建 FAISS 索引（耗时约 60 秒）
- 更新期间服务不可用
- 建议批量更新而非频繁单个更新

### 4.3 数据库备份

**自动备份脚本：**
```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# 创建备份目录
mkdir -p "$BACKUP_DIR/$DATE"

# 备份 SQLite
cp data/knowledge.db "$BACKUP_DIR/$DATE/"

# 备份 FAISS
cp data/knowledge.faiss "$BACKUP_DIR/$DATE/"

# 备份文档
cp -r records "$BACKUP_DIR/$DATE/"

# 压缩
cd "$BACKUP_DIR"
tar -czf "$DATE.tar.gz" "$DATE"
rm -rf "$DATE"

echo "备份完成: $BACKUP_DIR/$DATE.tar.gz"
```

**定时备份（crontab）：**
```bash
# 每天凌晨 3 点备份
0 3 * * * /path/to/MemGraph/backup.sh
```

### 4.4 清理查询日志

**查询日志位置：**
```
data/query_log.jsonl
```

**清理日志：**
```bash
# 方式 1: 直接删除
rm data/query_log.jsonl

# 方式 2: 通过 API
curl --noproxy "*" -X POST "http://localhost:8800/clear_log"
```

**日志格式：**
```json
{"query": "metagpt", "timestamp": "2026-01-30T10:00:00", "results": 1, "top_score": 8.99}
```

---

## 5. 故障排查

### 5.1 服务启动失败

**检查清单：**
```bash
# 1. 检查端口占用
netstat -ano | findstr "8800"

# 2. 检查 Python 环境
python --version  # 需要 Python 3.8+
pip list | grep -E "fastapi|faiss|jieba"

# 3. 检查文件权限
ls -l data/

# 4. 检查配置文件
cat src/config.py

# 5. 查看错误日志
python -m src.server 2>&1 | tee error.log
```

### 5.2 搜索结果异常

**问题 1：搜索无结果**

**排查：**
```python
import sqlite3

conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()

# 检查文档数量
cursor.execute('SELECT COUNT(*) FROM documents')
print(f"文档数: {cursor.fetchone()[0]}")

# 检查 N-gram 数量
cursor.execute('SELECT COUNT(*) FROM ngrams')
print(f"N-gram数: {cursor.fetchone()[0]}")

# 检查向量数量
cursor.execute('SELECT COUNT(*) FROM document_vectors')
print(f"文档向量数: {cursor.fetchone()[0]}")

conn.close()
```

**解决：**
- 如果数量为 0，运行 `python rebuild_vectors.py`
- 如果有数据但搜索无结果，检查查询关键词是否正确

**问题 2：搜索得分异常**

**排查：**
```bash
# 使用 debug 接口
curl --noproxy "*" -X POST "http://localhost:8800/debug/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "metagpt", "limit": 3}'
```

返回详细的 N-gram 匹配信息和向量得分。

### 5.3 性能问题

**问题：查询速度慢**

**排查：**
```python
import time
import asyncio
from src.knowledge_indexer import KnowledgeIndexer
from src.activation_search import ActivationSearch

async def profile_search():
    indexer = KnowledgeIndexer()
    search = ActivationSearch(indexer)

    query = "metagpt"

    # 分步计时
    start = time.time()
    results = await search.search(query, {'limit': 5})
    total_time = time.time() - start

    print(f"总耗时: {total_time*1000:.2f}ms")

asyncio.run(profile_search())
```

**优化：**
- FAISS 检索：使用 IVF 索引（数据量大时）
- N-gram 匹配：添加更多索引
- 向量生成：使用更快的嵌入模型

---

## 6. 开发调试

### 6.1 调试模式启动

```bash
# 开启详细日志
export LOG_LEVEL=DEBUG
python -m src.server

# 或修改 src/server.py
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 6.2 常用调试接口

```bash
# 查看所有向量信息
curl --noproxy "*" "http://localhost:8800/debug/vectors"

# 查看所有文档
curl --noproxy "*" "http://localhost:8800/debug/documents"

# 查看 N-gram 统计
curl --noproxy "*" "http://localhost:8800/debug/ngrams"

# 测试嵌入服务
curl --noproxy "*" -X POST "http://localhost:8800/debug/test-embedding"

# 查看向量相似度排名
curl --noproxy "*" -X POST "http://localhost:8800/debug/rank_all" \
  -H "Content-Type: application/json" \
  -d '{"query": "metagpt", "limit": 10}'
```

### 6.3 Python 交互式调试

```python
import asyncio
from src.knowledge_indexer import KnowledgeIndexer
from src.activation_search import ActivationSearch

# 初始化
indexer = KnowledgeIndexer()
search = ActivationSearch(indexer)

# 查看统计
stats = indexer.get_stats()
print(stats)

# 测试搜索
async def test():
    results = await search.search("metagpt", {'limit': 5})
    for r in results:
        print(f"{r['path']}: {r['total_score']:.2f}")

asyncio.run(test())

# 查看文档内容
import sqlite3
conn = sqlite3.connect('data/knowledge.db')
cursor = conn.cursor()
cursor.execute('SELECT id, path, solution FROM documents LIMIT 1')
doc = cursor.fetchone()
print(f"ID: {doc[0]}")
print(f"Path: {doc[1]}")
print(f"Content: {doc[2][:200]}")
conn.close()
```

---

## 7. 常见命令速查

```bash
# 启动服务
python -m src.server

# 停止服务
Ctrl+C

# 重建索引
python rebuild_vectors.py

# 测试初始化
python test_manual_init.py

# 测试搜索
python test_search_metagpt.py

# 查看统计
curl --noproxy "*" http://localhost:8800/stats

# 搜索测试
curl --noproxy "*" -X POST "http://localhost:8800/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "metagpt", "limit": 3}'

# 检查端口
netstat -ano | findstr "8800"

# 强制停止
taskkill //F //PID <PID>

# 备份数据
cp data/knowledge.db data/knowledge.db.backup
cp data/knowledge.faiss data/knowledge.faiss.backup
```
