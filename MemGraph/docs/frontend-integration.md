# 前端集成 MemGraph 知识查询服务

## 修改概述

将前端知识查询功能从旧的 memory_system 服务（端口 5001）迁移到 MemGraph 服务（端口 8800）。

## 修改内容

### 1. 前端 API 配置 (`frontend/src/services/api.js`)

#### 修改 API 基础地址
```javascript
// 旧配置 - memory_system 服务
const knowledgeApi = axios.create({
  baseURL: 'http://localhost:5001/api/knowledge',
  timeout: 30000
});

// 新配置 - MemGraph 服务
const knowledgeApi = axios.create({
  baseURL: 'http://localhost:8800',
  timeout: 30000
});
```

#### 修改 `queryKnowledge` 函数
适配 MemGraph 的 `/search` API：

**请求格式转换**:
- 前端: `{ question, model, top_k }`
- MemGraph: `{ query, limit, min_score, use_vector }`

**响应格式转换**:
```javascript
// MemGraph 响应
{
  query: string,
  count: number,
  results: [{
    doc_id, path, problem, solution,
    total_score, vector_similarity, ...
  }]
}

// 转换为前端期望格式
{
  success: true,
  data: {
    question: string,
    answer: null,  // MemGraph 不提供 AI 生成答案
    context: [{
      index, source, content, similarity
    }],
    model: string
  }
}
```

#### 修改 `getStats` 函数
适配 MemGraph 的统计数据格式：

```javascript
// MemGraph 响应
{ documents, ngrams, unique_ngrams, faiss_vectors }

// 转换为前端期望格式
{
  success: true,
  data: {
    total_documents: number,
    dimension: 512,
    faiss_vectors: number
  }
}
```

### 2. 前端 UI 组件 (`frontend/src/views/KnowledgeQuery/QueryInterface.vue`)

#### 修改 AI 回答提示
由于 MemGraph 只提供文档检索，不生成 AI 回答，更新了提示信息：

```html
<el-alert
  v-if="!item.answer"
  title="MemGraph 搜索引擎 - 仅提供文档检索，不生成AI回答"
  type="info"
  :closable="false"
>
  <template #default>
    提示：MemGraph 使用激活式搜索 + FAISS向量检索，快速找到最相关的文档。
    如需 AI 生成答案，请使用"纯聊天"模式。
  </template>
</el-alert>
```

#### 修改文档显示标题
```html
<el-divider content-position="left">
  MemGraph 检索结果 (共 {{ item.context.length }} 条)
</el-divider>
```

## 功能对比

| 功能 | memory_system (旧) | MemGraph (新) |
|------|-------------------|--------------|
| 端口 | 5001 | 8800 |
| API 路径 | `/api/knowledge/query` | `/search` |
| AI 答案生成 | ✅ 支持 (NVIDIA API) | ❌ 不支持 |
| 文档检索 | ✅ 向量检索 | ✅ 激活式搜索 + 向量检索 |
| 搜索速度 | 较慢 | 更快 |
| 搜索准确度 | 中等 | 高 (多粒度 N-gram + 向量) |
| 向量维度 | 未知 | 512 |

## MemGraph 优势

1. **更快的搜索**：激活式搜索 + FAISS 向量索引
2. **更高的准确度**：多粒度 N-gram 匹配
3. **更好的扩展性**：独立的 FastAPI 服务
4. **更详细的匹配信息**：提供激活得分、匹配片段等

## 测试

### 使用前端页面测试
1. 访问 http://localhost:5173/knowledge/query
2. 在"智能问答"模式下输入问题
3. 查看 MemGraph 返回的检索结果

### 使用测试页面
打开 `test_frontend_api.html` 直接测试 API 集成。

### 命令行测试
```bash
# 测试搜索
curl --noproxy "*" -X POST http://localhost:8800/search \
  -H "Content-Type: application/json" \
  -d '{"query":"向量数据库","limit":3,"min_score":0.1,"use_vector":true}'

# 测试统计
curl --noproxy "*" http://localhost:8800/stats
```

## 注意事项

1. **无 AI 生成答案**：MemGraph 只提供文档检索，不调用 LLM 生成答案
2. **聊天功能**：纯聊天模式仍使用旧的 API（需要单独迁移）
3. **前端刷新**：修改后需要重启前端开发服务器
4. **CORS**：MemGraph 已配置允许跨域请求

## 迁移状态

- ✅ 知识问答查询（智能问答模式）
- ✅ 统计信息显示
- ⚠️ 纯聊天模式（仍使用旧 API）
- ⚠️ 文档管理功能（需要单独适配）
- ⚠️ 记忆管理功能（需要单独适配）

## 后续工作

如需完整迁移，还需要适配：
1. 文档管理 (`DocumentManagement.vue`)
2. 记忆管理 (`MemoryManagement.vue`)
3. 纯检索 (`VectorSearch.vue`)
4. 纯聊天模式（可能需要MemGraph增加聊天接口）
