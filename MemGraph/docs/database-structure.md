# MemGraph 数据库结构文档

## 概述

MemGraph V3 使用混合检索架构，结合了：
- **SQLite** - 存储元数据和 N-gram 文本
- **FAISS** - 存储向量索引（4096维，Qwen3-Embedding-8B）

实现了**精确匹配（N-gram）+ 语义匹配（向量）**的混合检索。

---

## 1. SQLite 数据库结构

数据库文件：`data/knowledge.db`

### 1.1 documents 表（21 条记录）

存储文档元数据和内容。

**字段结构：**
```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    role TEXT,
    project TEXT,
    directory TEXT,
    timestamp TEXT,
    tags TEXT,
    problem TEXT,
    solution TEXT,
    full_content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**说明：**
- `id`: 文档唯一标识
- `path`: 文件相对路径
- `role`: 记录者角色
- `project`: 所属项目
- `problem`: 问题描述
- `solution`: 解决方案
- `full_content`: 完整内容（problem + solution）

### 1.2 ngrams 表（19,546 条记录）

存储所有 N-gram 文本片段（不包含向量）。

**字段结构：**
```sql
CREATE TABLE ngrams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    gram_type TEXT NOT NULL,
    gram_size INTEGER NOT NULL,
    section TEXT,
    position INTEGER,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_ngrams_content ON ngrams(content);
CREATE INDEX idx_ngrams_doc_id ON ngrams(doc_id);
CREATE INDEX idx_ngrams_type ON ngrams(gram_type);
```

**N-gram 类型分布：**
```
char_3gram:    4,068 个  (3字符片段，如 "是一台")
char_2gram:    3,656 个  (2字符片段，如 "是一")
word_1gram:    2,875 个  (单个词，如 "metagpt")
word_2gram:    2,764 个  (2词组合，如 "一台 局域网")
word_3gram:    2,655 个  (3词组合)
word_4gram:    2,546 个  (4词组合)
sentence:        564 个  (完整句子)
metadata:        418 个  (标签、项目名等元数据)
```

**重要特性：**
- 所有 N-gram 内容在存储时统一转为**小写**
- 支持大小写不敏感搜索
- 按类型索引，加速查询

### 1.3 document_vectors 表（723 条记录）

存储文档级别的向量引用。

**字段结构：**
```sql
CREATE TABLE document_vectors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id INTEGER NOT NULL,
    granularity TEXT NOT NULL,
    content TEXT NOT NULL,
    faiss_idx INTEGER UNIQUE,
    position INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_doc_vectors_doc_id ON document_vectors(doc_id);
CREATE INDEX idx_doc_vectors_granularity ON document_vectors(granularity);
```

**粒度分布：**
```
paragraph: 179 个  (段落级向量)
sentence:  544 个  (句子级向量)
```

**说明：**
- `granularity`: 粒度类型（paragraph/sentence）
- `content`: 原始文本内容
- `faiss_idx`: 对应的 FAISS 索引位置
- `position`: 在文档中的位置序号

### 1.4 ngram_vectors 表（5,427 条记录）

存储具有向量表示的 N-gram。

**字段结构：**
```sql
CREATE TABLE ngram_vectors (
    ngram_content TEXT PRIMARY KEY,
    faiss_idx INTEGER UNIQUE,
    gram_size INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**生成规则：**

只为以下类型的 N-gram 生成向量：
- `metadata`: 标签、项目名等元数据
- `word_3gram`: 3词短语
- `word_4gram`: 4词短语
- `sentence`: 完整句子

**说明：**
- `ngram_content`: N-gram 文本内容（去重）
- `faiss_idx`: 对应的 FAISS 索引位置
- 一个 N-gram 在多个文档中出现时，只生成一个向量

### 1.5 document_tags 表（87 条记录）

文档和标签的多对多关联表。

**字段结构：**
```sql
CREATE TABLE document_tags (
    doc_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (doc_id, tag),
    FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE INDEX idx_tags_tag ON document_tags(tag);
```

**热门标签示例：**
```
MCP: 5 个文档
配置: 5 个文档
MemGraph: 4 个文档
FAISS: 3 个文档
Claude Code: 2 个文档
```

---

## 2. FAISS 索引结构

索引文件：`data/knowledge.faiss`

**索引类型：** IndexFlat (IndexFlatIP)

**参数：**
```
索引类型: IndexFlat (内积索引)
向量维度: 4096 (Qwen3-Embedding-8B)
向量总数: 6,171
是否训练: True
```

**索引分配结构：**
```
faiss_idx 0-20     (21 个):    文档全文向量
faiss_idx 21-743   (723 个):   文档片段向量（段落+句子）
faiss_idx 744-6170 (5,427 个): N-gram 向量
```

**向量特性：**
- 所有向量已归一化（L2范数 = 1.0）
- 使用内积计算相似度（等价于余弦相似度）
- 值域范围：[-0.0955, 0.0735]

---

## 3. 数据流示例

以文档 `raw\2601.md` (ID=193) 为例：

### 3.1 文档索引流程

```
文档输入: raw\2601.md
  |
  v
1. 解析文档
  - 提取 metadata: role, project, tags
  - 提取 problem, solution
  - 生成 full_content
  |
  v
2. 生成 N-grams (1,400 个)
  - char_2gram: 133 个 (如 "是一")
  - char_3gram: 161 个 (如 "是一台")
  - word_1gram: 266 个 (如 "metagpt")
  - word_2gram: 265 个 (如 "一台 局域网")
  - word_3gram: 264 个
  - word_4gram: 263 个
  - sentence: 44 个
  - metadata: 4 个
  |
  v
3. 存储到 ngrams 表
  - 所有内容转小写
  - 记录 doc_id, gram_type, section, position
  |
  v
4. 生成向量 (52 个)
  - 1 个文档全文向量 (faiss_idx=5593)
  - 12 个段落向量
  - 40 个句子向量 (faiss_idx=5606-5645)
  |
  v
5. 生成 N-gram 向量
  - 从 N-grams 中选择符合条件的
  - 生成向量并去重（共享）
  - 存储到 ngram_vectors 表
  |
  v
6. 保存到 FAISS 索引
  - 归一化向量
  - 添加到 FAISS index
  - 记录 faiss_idx
```

### 3.2 生成的数据统计

**文档 ID=193 的数据分布：**
```
N-grams:         1,400 个
  - 存储在 ngrams 表
  - 关联 doc_id=193

文档向量:        52 个
  - 12 个段落向量
  - 40 个句子向量
  - 存储在 document_vectors 表

N-gram 向量:     约 525 个
  - 存储在 ngram_vectors 表
  - 与其他文档共享，不重复生成
```

---

## 4. 搜索流程

### 4.1 搜索查询示例

**查询：** `"metagpt"`

**步骤 1: N-gram 激活匹配**
```
1. 查询预处理
   - 原查询: "metagpt"
   - 转小写: "metagpt"
   - 分词: ["metagpt"]
   - 生成 N-grams: ["metagpt", "meta", "tag", "gp", ...]

2. 精确匹配
   - 在 ngrams 表中查找 content="metagpt"
   - 找到 12 个匹配 (doc_id=193)
   - 计算激活得分: 1.04

3. 聚合到文档
   - 按 doc_id 分组
   - 计算每个文档的 N-gram 激活得分
```

**步骤 2: 向量相似度计算**
```
1. 查询向量化
   - 调用 Qwen3-Embedding-8B
   - 生成 4096 维向量
   - 归一化处理

2. FAISS 检索
   - 在 FAISS index 中搜索 Top-K
   - 返回最相似的向量及其 faiss_idx

3. 匹配到文档
   - 通过 faiss_idx 查找对应的文档
   - 区分文档级向量和片段级向量
   - 计算相似度得分

4. 示例结果
   - 句子: "~/work/MetaGPT$ python -m metagpt"
   - 相似度: 0.935
   - faiss_idx: 5606
```

**步骤 3: 综合评分**
```
总分计算公式:
  total_score =
    + activation_score * 0.3       (N-gram 激活)
    + doc_vector_score * 10.0      (文档级向量)
    + chunk_max_similarity * 5.0   (片段最高相似度)
    + ngram_vector_score * 5.0     (N-gram 向量)

文档 ID=193 得分:
  - activation_score: 1.04
  - chunk_max_similarity: 0.94
  - 总分: 8.99
```

**最终结果：**
```json
{
  "doc_id": 193,
  "path": "raw\\2601.md",
  "total_score": 8.99,
  "activation_score": 1.04,
  "chunk_max_similarity": 0.94
}
```

---

## 5. 关键特性

### 5.1 大小写不敏感搜索

**实现方式：**
- N-gram 生成时转小写（`_segment_words`, `_generate_char_ngrams`）
- 查询处理时转小写（`process_query`）

**效果：**
- 搜索 "metagpt" 可以找到 "MetaGPT"
- 搜索 "LINUX" 可以找到 "linux"

### 5.2 多粒度向量索引

**四个层次：**
1. 文档级：完整文档的语义表示
2. 段落级：按段落分割的语义块
3. 句子级：精确到句子的细粒度表示
4. N-gram 级：关键短语的语义表示

**优势：**
- 长文档不会稀释语义
- 可以精确定位到具体句子
- 支持短语级别的语义匹配

### 5.3 混合检索策略

**N-gram 激活（精确匹配）：**
- 优势：精确、快速
- 适用：关键词、专有名词、代码片段

**向量检索（语义匹配）：**
- 优势：理解语义、支持同义词
- 适用：自然语言问题、模糊查询

**结合使用：**
- 互补优势
- 提高召回率和准确率

---

## 6. 数据统计

### 6.1 总体统计

```
文档总数:           21 个
N-gram 总数:        19,546 个
  - 唯一 N-grams:   13,357 个
向量总数:           6,171 个
  - 文档向量:       21 个
  - 片段向量:       723 个
  - N-gram 向量:    5,427 个
```

### 6.2 存储占用

```
SQLite 数据库:      约 3-5 MB
FAISS 索引:         约 95 MB (6171 × 4096 × 4 bytes)
总存储:             约 100 MB
```

### 6.3 性能指标

```
索引速度:           约 1-2 文档/秒 (包含向量生成)
查询速度:
  - N-gram 匹配:    < 10ms
  - FAISS 检索:     < 50ms
  - 总查询时间:     < 100ms
```

---

## 7. 配置参数

### 7.1 N-gram 配置

文件：`src/config.py`

```python
NGRAM_CONFIG = {
    "char_2gram": True,
    "char_3gram": True,
    "word_2gram": True,
    "word_3gram": True,
    "word_4gram": True,
    "sentence": True,
}
```

### 7.2 评分权重

```python
SCORE_WEIGHTS = {
    # N-gram 类型权重
    "metadata": 5.0,
    "sentence": 3.0,
    "word_4gram": 2.5,
    "word_3gram": 2.0,
    "word_2gram": 1.5,
    "char_3gram": 1.0,
    "char_2gram": 0.8,

    # Section 权重
    "section_metadata": 3.0,
    "section_problem": 2.0,
    "section_solution": 1.5,
}
```

### 7.3 向量配置

```python
EMBED_SERVICE_URL = "http://192.168.0.132:6014/embed/text"
EMBED_DIMENSION = 4096  # Qwen3-Embedding-8B
```

---

## 8. 维护操作

### 8.1 重建索引

```bash
cd /path/to/MemGraph
python rebuild_vectors.py
```

功能：
- 清空所有向量数据
- 重新扫描所有文档
- 重新生成 N-grams 和向量
- 重建 FAISS 索引

### 8.2 查看统计信息

```bash
curl --noproxy "*" http://localhost:8800/stats
```

返回：
```json
{
    "documents": 21,
    "ngrams": 19546,
    "unique_ngrams": 13357,
    "faiss_vectors": 6171
}
```

### 8.3 数据库备份

```bash
# 备份 SQLite
cp data/knowledge.db data/knowledge.db.backup

# 备份 FAISS
cp data/knowledge.faiss data/knowledge.faiss.backup
```

---

## 9. 技术栈

- **数据库**: SQLite 3
- **向量索引**: FAISS (Facebook AI Similarity Search)
- **向量模型**: Qwen3-Embedding-8B (4096 维)
- **分词**: jieba
- **Web 框架**: FastAPI
- **HTTP 客户端**: httpx (异步)

---

## 10. 相关文件

```
MemGraph/
├── data/
│   ├── knowledge.db          # SQLite 数据库
│   └── knowledge.faiss        # FAISS 向量索引
├── src/
│   ├── server.py              # FastAPI 服务器
│   ├── knowledge_indexer.py   # 索引器
│   ├── activation_search.py   # 搜索引擎
│   ├── ngram_processor.py     # N-gram 处理器
│   ├── embedding_client.py    # 向量服务客户端
│   └── config.py              # 配置文件
├── rebuild_vectors.py         # 重建索引脚本
└── docs/
    └── database-structure.md  # 本文档
```
