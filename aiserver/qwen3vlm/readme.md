# Qwen3-VL VLM 服务

机器：8x3090  
环境：qwen  
模型：Qwen3-VL-8B-Instruct  
端口：6050

## 启动服务

### 方式一：标准版（transformers）

```bash
./start.sh
```

### 方式二：高性能版（vLLM，推荐）

vLLM 支持连续批处理，吞吐量更高：

```bash
# 安装 vLLM
pip install vllm

# 启动
python vlm_service_vllm.py --gpu 1
```

## 性能优化

| 优化方式 | 速度提升 | 说明 |
|----------|----------|------|
| torch.compile | ~20-30% | 已默认启用 |
| vLLM | ~2-5x | 连续批处理，推荐生产环境 |
| 多 GPU | 线性 | `--tensor-parallel 2` |
| 量化 (Q4/Q8) | ~2x | 使用 GGUF 版本 |

## 端口转发

### 使用脚本

```bash
./port_forward.sh start   # 启动
./port_forward.sh stop    # 停止
./port_forward.sh status  # 查看状态
```

### 手动命令

```bash
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
python test_client.py --image test.jpg "描述这张图片"

# 交互模式
python test_client.py --interactive
```

## 并发说明

### 单实例模式
- **transformers 版本**: 单请求模式，适合开发测试
- **vLLM 版本**: 支持并发请求，自动批处理

### 多实例模式（8x3090 推荐）

在多个 GPU 上运行多个实例 + 负载均衡：

```bash
# 启动 4 个实例（GPU 1-4）
GPUS=1,2,3,4 ./start_multi.sh

# 启动 6 个实例（GPU 1-6）
GPUS=1,2,3,4,5,6 ./start_multi.sh

# 停止所有实例
./stop_multi.sh
```

架构：
```
         ┌─────────────────┐
         │  负载均衡器     │ :6050
         │  (最少连接)     │
         └────────┬────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌───────┐   ┌───────┐     ┌───────┐
│ GPU 1 │   │ GPU 2 │ ... │ GPU N │
│ :6051 │   │ :6052 │     │ :605N │
└───────┘   └───────┘     └───────┘
```

查看状态：
```bash
curl http://localhost:6050/lb/status
```

### 性能估算

| 配置 | 并发能力 | 说明 |
|------|----------|------|
| 单实例 | 1 req/time | 约 3-5s/请求 |
| 4 实例 | 4 req/time | 4x 吞吐量 |
| 6 实例 | 6 req/time | 6x 吞吐量 |
