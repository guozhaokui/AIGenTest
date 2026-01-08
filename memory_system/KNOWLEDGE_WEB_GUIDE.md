# 知识查询Web服务使用指南

## 系统架构

```
前端 (Vue.js)              后端服务
Port 5173/5174    ←→    Port 5001 (知识查询API)
   ↓                        ↓
/knowledge/query          向量存储 (ChromaDB)
/knowledge/docs           ↓
/knowledge/memory         BGE Embedding服务
                          (192.168.0.100:6012)
                          ↓
                          NVIDIA NIM API
                          (LLM生成回答)
```

## 快速启动

### 1. 启动后端知识查询服务

```bash
cd memory_system
python web_service.py
```

服务将在 `http://localhost:5001` 启动。

**输出示例：**
```
============================================================
知识查询Web服务
============================================================
初始化向量存储...
初始化NVIDIA API...
✓ NVIDIA API已初始化
✓ 服务初始化完成

启动API服务...
  地址: http://0.0.0.0:5001
  文档: http://localhost:5001/api/knowledge/status
============================================================
```

### 2. 启动前端开发服务器

```bash
cd frontend
npm run dev
```

前端将在 `http://localhost:5173` 或 `http://localhost:5174` 启动。

### 3. 访问知识查询页面

在浏览器中打开：
```
http://localhost:5173/knowledge
```

## 功能说明

### 1. 智能问答 (/knowledge/query)

**功能：**
- 输入问题，AI基于知识库回答
- 支持多种LLM模型选择
- 显示检索到的相关文档
- 查看历史问答记录

**使用流程：**
1. 选择AI模型（默认：DeepSeek V3.2）
2. 输入问题
3. 点击"查询"或按 Ctrl+Enter
4. 查看AI回答和相关文档

**示例问题：**
- "MetaGPT怎么启动？"
- "QAMath在哪个服务器上？"
- "BGE嵌入服务的端口是多少？"

### 2. 文档管理 (/knowledge/docs)

**功能：**
- 扫描目录中的Markdown文件
- 选择文件进行索引
- 查看索引状态
- 删除或重新索引文档

**使用流程：**
1. 点击"扫描目录"（默认路径：/mnt/e/TEST/work/日志）
2. 在文件列表中选择要索引的文件
3. 点击"索引选中"
4. 等待索引完成（会显示进度）

**索引过程：**
- 自动分块（500字/块，重叠100字）
- 生成向量（BGE-1024维）
- 存储到ChromaDB
- 关联元数据（来源、时间等）

### 3. 记忆管理 (/knowledge/memory)

**功能：**
- 查看知识库统计信息
- 文档来源分布
- 记忆质量检查
- 更新历史记录

**统计信息：**
- 文档块总数
- 向量维度
- 数据集名称
- 嵌入服务状态

## API端点

### 系统状态
```bash
GET http://localhost:5001/api/knowledge/status
```

### 扫描文档
```bash
POST http://localhost:5001/api/knowledge/scan
Content-Type: application/json

{
  "path": "/mnt/e/TEST/work/日志"
}
```

### 索引文档
```bash
POST http://localhost:5001/api/knowledge/index
Content-Type: application/json

{
  "files": [
    "/mnt/e/TEST/work/日志/2601.md",
    "/mnt/e/TEST/work/日志/2512.md"
  ]
}
```

### 查询问答
```bash
POST http://localhost:5001/api/knowledge/query
Content-Type: application/json

{
  "question": "MetaGPT怎么启动？",
  "model": "deepseek-ai/deepseek-v3.2",
  "top_k": 3
}
```

### 获取模型列表
```bash
GET http://localhost:5001/api/knowledge/models
```

### 清空知识库
```bash
POST http://localhost:5001/api/knowledge/clear
```

### 删除文档
```bash
POST http://localhost:5001/api/knowledge/delete
Content-Type: application/json

{
  "source": "2601.md"
}
```

### 获取统计信息
```bash
GET http://localhost:5001/api/knowledge/stats
```

## 可用的LLM模型

系统支持以下NVIDIA NIM模型：

| 模型ID | 名称 | 推荐 | 特点 |
|--------|------|------|------|
| deepseek-ai/deepseek-v3.2 | DeepSeek V3.2 | ✅ | 通用对话，中文友好 |
| deepseek-ai/deepseek-r1-0528 | DeepSeek R1 | ✅ | 推理能力强 |
| moonshotai/kimi-k2-thinking | Kimi K2 Thinking | ✅ | 思维链推理 |
| z-ai/glm4.7 | GLM-4.7 | ✅ | 国产大模型 |
| minimaxai/minimax-m2.1 | MiniMax M2.1 | ✅ | 对话生成 |
| meta/llama-3.3-70b-instruct | Llama 3.3 70B | - | 英文强 |
| qwen/qwen3-235b-a22b | Qwen3 235B | - | 超大规模 |
| meta/llama-3.1-8b-instruct | Llama 3.1 8B | - | 快速响应 |

## 系统要求

### 必需服务

1. **BGE Embedding服务**
   - 地址：http://192.168.0.100:6012
   - 提供1024维向量嵌入
   - 启动命令：
     ```bash
     ssh ubuntu@192.168.0.100
     cd /mnt/hdd/guo/AIGenTest/aiserver/embedding
     ./start_embed_server.sh
     ```

2. **NVIDIA API Key**
   - 在 `.env` 文件中配置
   - 用于LLM回答生成
   ```bash
   NVIDIA_API_KEY=nvapi-xxx
   ```

### 可选配置

在 `.env` 文件中可配置：
```bash
# 知识查询API端口
KNOWLEDGE_API_PORT=5001

# BGE嵌入服务地址
BGE_EMBEDDING_URL=http://192.168.0.100:6012

# NVIDIA API密钥
NVIDIA_API_KEY=nvapi-xxx
```

## 数据存储

### 向量数据库位置
```
memory_system/.memory_db/web_vectors/
  ├── chroma.sqlite3         # 元数据
  └── collection_data/       # 向量数据
```

### 清空数据库
```bash
# 方法1：通过Web界面
访问 /knowledge/docs → 点击"清空知识库"

# 方法2：通过API
curl -X POST http://localhost:5001/api/knowledge/clear

# 方法3：直接删除文件
rm -rf memory_system/.memory_db/web_vectors/
```

## 故障排查

### 问题1：前端无法连接后端
**现象：** 查询时提示"Network Error"

**解决：**
1. 确认后端服务已启动（http://localhost:5001）
2. 检查CORS配置
3. 查看浏览器控制台错误

### 问题2：BGE服务连接失败
**现象：** 索引文档时报错

**解决：**
```bash
# 检查BGE服务
curl http://192.168.0.100:6012/health

# 如果服务未启动，启动它
ssh ubuntu@192.168.0.100
cd /mnt/hdd/guo/AIGenTest/aiserver/embedding
./start_embed_server.sh
```

### 问题3：NVIDIA API调用失败
**现象：** 查询后没有AI回答

**解决：**
1. 检查 `.env` 中的 `NVIDIA_API_KEY`
2. 验证API key有效性
3. 查看后端日志

### 问题4：文档路径找不到
**现象：** 扫描目录时报错"目录不存在"

**解决：**
- WSL环境下，Windows路径 `E:\TEST\work\日志` 对应 `/mnt/e/TEST/work/日志`
- 确认路径存在且有读取权限

## 性能优化

### 索引性能
- 单文件索引：< 1秒
- 10个文件：~15秒
- 批量索引：自动分批处理

### 查询性能
- 向量检索：~50ms
- LLM生成：2-3秒
- 端到端：< 5秒

### 建议
- 首次使用先索引少量文档测试
- 根据需要调整 `top_k` 参数（默认3）
- 定期清理不需要的旧文档

## 开发调试

### 后端日志
```bash
cd memory_system
python web_service.py

# 查看详细日志
```

### 前端调试
```bash
# 浏览器控制台
F12 → Console

# 网络请求
F12 → Network → XHR
```

### API测试
```bash
# 使用curl测试
curl http://localhost:5001/api/knowledge/status

# 使用HTTPie
http GET http://localhost:5001/api/knowledge/status
```

## 下一步计划

- [ ] AI主动学习功能
- [ ] 实体提取和关系图
- [ ] 冲突检测
- [ ] 知识图谱可视化
- [ ] 多模态支持（图片、代码）
- [ ] 记忆更新建议
- [ ] 导出知识库

## 相关文档

- [RAG系统Demo指南](./DEMO_README.md)
- [向量存储文档](./core/README_VECTOR_STORE.md)
- [嵌入层文档](./core/embedding.py)
