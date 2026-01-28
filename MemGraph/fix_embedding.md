# 修复嵌入向量问题

## 问题诊断

**发现的问题**:
1. ✅ 向量全是 0 - 因为 AI Gateway 未运行，`embedding_client.py` 返回零向量
2. ✅ 维度配置错误 - Qwen3-Embedding-8B 的维度是 **4096**，而不是 1024
3. ❌ AI Gateway 未运行 - 端口 8899 无响应

## 解决步骤

### 步骤 1: 启动 AI Gateway

AI Gateway 必须先启动才能生成向量。

```bash
cd D:\work\AIGenTest\aiserver\gateway
python ai_gateway.py
```

**验证**:
```bash
curl http://localhost:8899/health
```

应该返回:
```json
{
  "status": "ok",
  "gateway": "python-fastapi",
  "config": "aiserver/config.yaml"
}
```

### 步骤 2: 测试嵌入服务

```bash
cd D:\work\AIGenTest\MemGraph
python test_embed.py
```

**预期输出**:
```
状态码: 200
找到键: 'embedding'
  - 类型: <class 'list'>
  - 长度: 4096
  - 前10维: [0.123, -0.456, ...]
  - 是否全零: False
```

### 步骤 3: 删除旧的 FAISS 索引

因为维度已从 1024 改为 4096，旧索引不兼容。

```bash
cd D:\work\AIGenTest\MemGraph\data
del knowledge.faiss
```

### 步骤 4: 重启 MemGraph 服务

停止当前的 backend（如果在运行），然后重启：

```bash
cd D:\work\AIGenTest
# 按 Ctrl+C 停止
pnpm dev:backend
```

**观察日志**，应该看到：
```
[memgraph] Initializing MemGraph...
[memgraph] Created new FAISS index (dimension: 4096)
[memgraph] Syncing 6 existing documents...
[memgraph] Added vector for doc_id=1, faiss_idx=0, norm=1.0000
[memgraph] Added vector for doc_id=2, faiss_idx=1, norm=1.0000
...
[memgraph] MemGraph initialized: 6 documents indexed
```

### 步骤 5: 验证修复

1. **打开 Web 界面**: http://localhost:8800

2. **搜索测试**: 输入 "claude code mcp"

3. **检查结果**:
   - 激活得分: 应该有数值（如 42.3）
   - **向量相似度**: 应该有数值（如 0.847），**不再是 0**
   - 匹配片段: 应该有数量（如 20）

4. **打开调试面板**: http://localhost:8800/static/debug.html

5. **检查向量索引**:
   - 向量总数: 应该等于文档数（如 6）
   - 向量维度: 应该是 **4096**
   - 向量范数: 应该接近 1.0
   - 向量预览: 应该有非零值

6. **检查文档映射**:
   - 所有文档应该显示 ✅
   - FAISS索引列应该有数字（0, 1, 2...）

## 常见问题

### Q1: AI Gateway 启动失败

**错误**: `ModuleNotFoundError: No module named 'fastapi'`

**解决**:
```bash
cd D:\work\AIGenTest\aiserver\gateway
pip install -r requirements.txt
```

### Q2: 远程嵌入服务连接失败

**错误**: `Connection refused to 192.168.0.132:6014`

**原因**: GPU 服务器上的嵌入服务未启动

**解决**: 需要在 GPU 服务器上启动嵌入服务

### Q3: 向量维度不匹配

**错误**: `RuntimeError: Dimension mismatch`

**原因**: FAISS 索引维度与新向量维度不匹配

**解决**: 删除 `data/knowledge.faiss` 并重建

### Q4: 向量仍然全零

**检查**:
1. AI Gateway 是否真的在运行？
   ```bash
   curl http://localhost:8899/health
   ```

2. 嵌入服务是否可达？
   ```bash
   curl http://localhost:8899/health/all
   ```

3. 查看 MemGraph 日志，是否有错误信息？

4. 手动测试嵌入：
   ```bash
   python test_embed.py
   ```

## 配置说明

### MemGraph 配置 (`src/config.py`)

```python
EMBED_SERVICE_URL = "http://localhost:8899/embed/text/qwen3-8b"
EMBED_DIMENSION = 4096  # Qwen3-Embedding-8B
```

### AI Gateway 配置 (`aiserver/config.yaml`)

```yaml
embed_server_2:
  host: "192.168.0.132"
  services:
    embed_8b:
      port: 6014
      model_name: "Qwen3-Embedding-8B"
      dimension: 4096  # ← 正确的维度
```

## 架构流程

```
MemGraph (8800)
    ↓ HTTP POST
AI Gateway (8899)
    ↓ HTTP转发
GPU Server (192.168.0.132:6014)
    ↓ 返回 4096 维向量
AI Gateway (8899)
    ↓ 返回
MemGraph (8800)
    ↓ 存入 FAISS
```

## 完成检查清单

- [ ] AI Gateway 已启动（8899 端口）
- [ ] test_embed.py 测试通过（返回 4096 维非零向量）
- [ ] 删除旧的 knowledge.faiss 文件
- [ ] 重启 MemGraph 服务
- [ ] 观察日志确认向量生成成功
- [ ] Web 搜索显示非零向量相似度
- [ ] 调试面板显示正确的向量信息

---

**最后更新**: 2026-01-28
