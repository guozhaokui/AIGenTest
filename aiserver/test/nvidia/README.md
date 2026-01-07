# NVIDIA NIM Chat 网页应用

这是一个基于 NVIDIA NIM API 的网页聊天应用，支持多个模型选择和多轮对话。

## 功能特点

- ✨ 支持多个 NVIDIA NIM 模型（Llama 3.1, Mistral, Gemma, Nemotron 等）
- 💬 支持多轮对话，保持上下文
- 🎨 现代化的 UI 设计
- 🚀 实时响应
- 🔄 可随时切换模型
- 🗑️ 一键清空聊天记录

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

确保在项目根目录（`/home/guozhaokui/work/AIGenTest/`）的 `.env` 文件中配置了 `NVIDIA_API_KEY`：

```bash
# 在项目根目录创建或编辑 .env 文件
cd /home/guozhaokui/work/AIGenTest
nano .env

# 添加以下内容：
NVIDIA_API_KEY=nvapi-your-api-key-here
```

应用会自动从项目根目录加载 `.env` 文件。

## 运行

**方式一：使用启动脚本（推荐）**
```bash
./start.sh
```

**方式二：直接运行**
```bash
python app.py
```

服务器将在 `http://localhost:5000` 启动。

## 使用方法

1. 打开浏览器访问 `http://localhost:5000`
2. 从右上角的下拉菜单选择一个模型
3. 在底部输入框输入消息
4. 按回车或点击"发送"按钮发送消息
5. 查看模型的回复
6. 继续对话，系统会保持上下文
7. 点击"清空"按钮可以清空聊天记录

## 可用模型

- **Llama 3.1 8B Instruct** - 快速高效，适合一般任务
- **Llama 3.1 70B Instruct** - 强大的推理能力
- **Llama 3.1 405B Instruct** - 最强大的模型
- **Mistral 7B Instruct** - 高效的指令遵循模型
- **Mixtral 8x7B Instruct** - 混合专家模型
- **Gemma 2 9B IT** - Google 的指令调优模型
- **Nemotron 70B Instruct** - NVIDIA 增强版 Llama 模型

## 技术栈

- **后端**: Flask + OpenAI SDK
- **前端**: HTML + CSS + JavaScript
- **API**: NVIDIA NIM API

## 注意事项

- 需要有效的 NVIDIA API Key
- 确保网络连接正常
- 某些大模型可能响应较慢
