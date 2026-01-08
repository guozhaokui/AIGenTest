---
name: nvidia-chat
description: Manage NVIDIA NIM chat application. Use when starting the chat server, testing models, listing available models, or checking API status.
allowed-tools: Bash(cd:*, python3:*, ./start.sh:*, ls:*), Read
---

# NVIDIA NIM Chat Manager

管理和操作 NVIDIA NIM 聊天应用的技能。

## 快速命令

### 启动聊天服务器
```bash
cd aiserver/test/nvidia && ./start.sh
```

### 测试首选模型
```bash
cd aiserver/test/nvidia && python3 test_top_models.py
```

### 列出所有可用模型
```bash
cd aiserver/test/nvidia && python3 list_models.py
```

### 测试思考内容格式
```bash
cd aiserver/test/nvidia && python3 test_thinking.py
```

### 测试工具调用
```bash
cd aiserver/test/nvidia && python3 test_tools.py
```

## 主要功能

### 1. 启动服务器

当用户请求"启动 nvidia 聊天"、"运行聊天应用"或类似命令时：

1. 检查环境配置
   ```bash
   cd aiserver/test/nvidia && ls -la
   ```

2. 确认 .env 文件存在（项目根目录）
   ```bash
   ls ../../.env
   ```

3. 启动服务器
   ```bash
   ./start.sh
   ```

4. 告知用户访问地址：`http://localhost:5000`

### 2. 测试模型能力

当用户询问"哪些模型支持 xxx"或"测试模型"时：

1. 运行完整测试套件
   ```bash
   python3 test_top_models.py
   ```

2. 解读测试结果，告知用户：
   - 哪些模型支持思考过程（reasoning）
   - 哪些模型支持工具调用
   - 哪些模型中文表现最好
   - 响应速度对比

### 3. 查看可用模型

当用户询问"有哪些模型"、"模型列表"时：

1. 运行模型列表脚本
   ```bash
   python3 list_models.py
   ```

2. 总结输出，分类展示：
   - 推理模型（支持思考）
   - 通用大模型
   - 代码专用模型
   - 小型快速模型

### 4. 查看 API 格式文档

当用户询问"API 怎么用"、"格式是什么"时：

1. 读取 API 文档
   ```bash
   Read aiserver/test/nvidia/API_FORMAT.md
   ```

2. 根据用户需求提取相关部分：
   - 基本聊天格式
   - 流式输出格式
   - 思考内容格式
   - 工具调用格式

### 5. 检查服务状态

当用户询问"服务是否运行"、"端口是否占用"时：

1. 检查端口占用
   ```bash
   lsof -i :5000 || netstat -tuln | grep 5000
   ```

2. 测试 API 连接
   ```bash
   curl -s http://localhost:5000/api/models | head -20
   ```

## 文件结构

```
aiserver/test/nvidia/
├── app.py                    # Flask 后端服务器
├── index.html                # 前端聊天界面
├── start.sh                  # 启动脚本
├── requirements.txt          # Python 依赖
├── README.md                 # 使用说明
├── API_FORMAT.md             # API 格式文档
├── test_top_models.py        # 测试首选模型
├── test_thinking.py          # 测试思考内容
├── test_tools.py             # 测试工具调用
├── list_models.py            # 列出所有模型
└── modellist.txt             # 模型列表缓存
```

## 配置要求

### 环境变量
项目根目录的 `.env` 文件必须包含：
```
NVIDIA_API_KEY=nvapi-xxx
```

### Python 依赖
```
flask>=3.0.0
flask-cors>=4.0.0
openai>=1.50.0
python-dotenv>=1.0.0
requests
```

### 安装依赖
```bash
cd aiserver/test/nvidia
pip install -r requirements.txt
```

## 常见问题处理

### 问题 1: 端口被占用
```bash
# 查找占用进程
lsof -i :5000

# 杀死进程
kill -9 <PID>
```

### 问题 2: API Key 未配置
检查 `.env` 文件：
```bash
cat /home/guozhaokui/work/AIGenTest/.env | grep NVIDIA_API_KEY
```

### 问题 3: 依赖缺失
重新安装：
```bash
cd aiserver/test/nvidia
pip install --upgrade -r requirements.txt
```

### 问题 4: 流式输出不工作
检查前端是否正确连接到 `/api/chat/stream` 端点。

## 最佳实践

1. **首次使用**：
   - 运行 `test_top_models.py` 了解各模型能力
   - 查看 `API_FORMAT.md` 了解 API 格式

2. **日常使用**：
   - 使用 `./start.sh` 快速启动
   - 在浏览器中打开 `http://localhost:5000`
   - 选择合适的模型开始对话

3. **测试新功能**：
   - 修改代码后重启服务器
   - 使用测试脚本验证功能

4. **故障排查**：
   - 检查终端输出的错误信息
   - 查看浏览器控制台的网络请求
   - 运行相应的测试脚本

## 推荐模型

根据使用场景选择：

| 场景 | 推荐模型 |
|------|----------|
| 需要思考过程 | DeepSeek R1, Kimi K2 Thinking |
| 中文对话 | GLM-4.7, DeepSeek V3.2 |
| 快速响应 | Llama 3.1 8B |
| 代码生成 | Qwen Coder 系列 |
| 通用任务 | DeepSeek V3.2, Llama 3.3 70B |

## 性能优化

1. **首次加载时思考区域默认展开**，可实时看到推理过程
2. **流式输出**减少等待时间，提升用户体验
3. **自动滚动**确保最新内容可见
4. **max_tokens** 设置为 4096，适合长文本生成

## 相关资源

- API 文档：`API_FORMAT.md`
- 使用说明：`README.md`
- 模型列表：https://build.nvidia.com/models
- NVIDIA NIM 文档：https://docs.nvidia.com/nim/
