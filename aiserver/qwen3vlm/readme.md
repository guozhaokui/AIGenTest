# Qwen3-VL VLM 服务

机器：8x3090  
环境：qwen  
模型：Qwen3-VL-8B-Instruct  
端口：6050

## 启动服务

```bash
./start.sh
```

## 端口转发

### 方式一：使用脚本（推荐）

```bash
./port_forward.sh start   # 启动
./port_forward.sh stop    # 停止
./port_forward.sh status  # 查看状态
```

### 方式二：手动命令

```bash
# 前台运行
ssh -L 6050:localhost:6050 -N zhangqu-8x3090

# 后台运行
ssh -L 6050:localhost:6050 -N -f zhangqu-8x3090
```

## API 端点

| 端点 | 说明 |
|------|------|
| `POST /caption` | 图片描述（imagemgr 兼容） |
| `POST /v1/chat/completions` | OpenAI 兼容 API |
| `GET /v1/models` | 模型列表 |

## 测试

```bash
# 纯文本
python test_client.py "你好"

# 图片描述
python test_client.py --image /path/to/image.jpg "描述这张图片"

# 交互模式
python test_client.py --interactive
```
