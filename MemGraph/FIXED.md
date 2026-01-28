# 向量问题已修复

## ✅ 问题诊断

### 原因
1. **向量全是 0** - `embedding_client.py` 在服务出错时返回零向量
2. **维度错误** - 配置为 1024，实际 Qwen3-8B 是 4096 维
3. **服务地址错误** - 配置为 Gateway (8899)，但 Gateway 已弃用

## ✅ 已修复

### 1. 更新嵌入服务地址
**文件**: `src/config.py`

```python
# 旧配置
EMBED_SERVICE_URL = "http://localhost:8899/embed/text/qwen3-8b"
EMBED_DIMENSION = 1024

# 新配置（直接访问 GPU 服务器）
EMBED_SERVICE_URL = "http://192.168.0.132:6014/embed/text"
EMBED_DIMENSION = 4096  # Qwen3-Embedding-8B
```

### 2. 修复 embedding_client.py
- ❌ **旧**: 出错时返回零向量
- ✅ **新**: 抛出异常，显示详细错误
- 增加验证：响应格式、维度、全零检查

### 3. 删除旧的 FAISS 索引
因为维度从 1024 改为 4096，旧索引不兼容。

```bash
cd D:\work\AIGenTest\MemGraph\data
rm -f knowledge.faiss
```

### 4. 测试通过
```bash
cd D:\work\AIGenTest\MemGraph
python test_embed.py
```

**结果**:
```
✅ 状态码: 200
✅ 找到键: 'embedding'
✅ 长度: 4096
✅ 前10维: [0.027, -0.012, 0.012, ...]
✅ 是否全零: False
```

## 🚀 下一步

### 重启 MemGraph 服务

```bash
cd D:\work\AIGenTest
# Ctrl+C 停止当前 backend（如果在运行）
pnpm dev:backend
```

### 观察日志

应该看到：
```
[memgraph] Initializing MemGraph...
[memgraph] Created new FAISS index (dimension: 4096)
[memgraph] Syncing 6 existing documents...
[memgraph] Added vector for doc_id=1, faiss_idx=0, norm=1.0000
[memgraph] Added vector for doc_id=2, faiss_idx=1, norm=1.0000
[memgraph] Added vector for doc_id=3, faiss_idx=2, norm=1.0000
...
[memgraph] MemGraph initialized: 6 documents indexed
```

**关键指标**:
- ✅ 维度: 4096
- ✅ 向量范数: ~1.0
- ✅ 每个文档都成功生成向量

### 验证修复

#### 1. 访问主界面
http://localhost:8800

搜索测试：输入 "claude code mcp"

**检查搜索结果**:
- 激活得分: 有数值（如 42.3）
- **向量相似度**: 有数值（如 0.847）✅ 不再是 0
- 匹配片段: 有数量（如 20）

#### 2. 访问调试面板
http://localhost:8800/static/debug.html

**检查向量索引详情**:
- 向量总数: 6（等于文档数）✅
- 向量维度: 4096 ✅
- 向量范数: ~1.0 ✅
- 向量预览: 非零值 ✅

**检查文档映射**:
- 所有文档显示 ✅
- FAISS索引列显示 0, 1, 2, 3, 4, 5 ✅

## 架构说明

### 旧架构（已弃用）
```
MemGraph → AI Gateway (8899) → GPU Server (192.168.0.132:6014)
```

### 新架构（当前）
```
MemGraph → GPU Server (192.168.0.132:6014)
```

**原因**: Backend 直接访问各 GPU 服务，不需要 Gateway 中转层。

## GPU 服务器信息

**嵌入服务**:
- 地址: `http://192.168.0.132:6014`
- 端点: `/embed/text`
- 模型: Qwen3-Embedding-8B
- 维度: 4096
- 超时: 30秒

**请求格式**:
```json
POST http://192.168.0.132:6014/embed/text
Content-Type: application/json

{
  "text": "要嵌入的文本",
  "instruction": "可选的指令前缀"
}
```

**响应格式**:
```json
{
  "embedding": [0.027, -0.012, ...],  // 4096维
  "dimension": 4096,
  "model": "Qwen3-Embedding-8B",
  "version": "1.0"
}
```

## 常见问题

### Q1: 连接 GPU 服务器失败

**错误**: `Connection refused`

**检查**:
1. GPU 服务器是否在线？
   ```bash
   ping 192.168.0.132
   ```

2. 嵌入服务是否启动？
   ```bash
   curl http://192.168.0.132:6014/health
   ```

3. 防火墙/网络配置？

### Q2: 向量仍然为 0

**检查**:
1. 确认删除了旧的 `knowledge.faiss`
2. 重启了 MemGraph 服务
3. 查看日志确认向量生成成功
4. 检查 GPU 服务器连通性

### Q3: 维度不匹配错误

**错误**: `Embedding dimension mismatch`

**原因**: FAISS 索引维度与新向量不一致

**解决**:
```bash
rm -f D:\work\AIGenTest\MemGraph\data\knowledge.faiss
# 然后重启服务
```

## 测试清单

- [x] 嵌入服务连通性测试通过
- [x] 维度配置更新为 4096
- [x] 服务地址更新为 GPU 服务器
- [x] 删除旧的 FAISS 索引
- [ ] 重启 MemGraph 服务
- [ ] 观察日志确认向量生成
- [ ] Web 搜索显示非零向量相似度
- [ ] 调试面板显示正确向量信息

---

**修复时间**: 2026-01-28
**状态**: ✅ 已修复，等待重启验证
