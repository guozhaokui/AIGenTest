# 快速启动指南

## 1. 准备工作

模型已下载到：`D:\work\AIGenTest\aiserver\models\qwen3_0__6b`

## 2. 安装依赖

```bash
cd D:\work\AIGenTest\aiserver\qwentinyllm

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

## 3. 启动服务

```bash
# 方式1：使用启动脚本
start_service.bat

# 方式2：直接运行
python service.py
```

## 4. 访问测试页面

启动后，打开浏览器访问：

```
http://localhost:6015
```

你将看到一个美观的测试页面，可以直接测试所有功能：
- 无意义短语判断
- 句子相似度判断
- N-gram 重要性评分
- 文本质量评估

## 5. API 端点

所有 API 都运行在 `http://localhost:6015`：

- `GET /` - 测试页面
- `GET /health` - 健康检查
- `GET /info` - 模型信息
- `POST /api/judge/meaningless` - 无意义判断
- `POST /api/judge/similarity` - 相似度判断
- `POST /api/judge/importance` - 重要性评分
- `POST /api/judge/quality` - 质量评估
- `POST /api/judge/batch` - 批量判断

## 6. 故障排查

### 服务启动失败

检查虚拟环境是否激活，依赖是否安装完整：
```bash
venv\Scripts\activate
pip install -r requirements.txt
```

### 模型加载失败

确认模型路径正确，编辑 `config.py` 检查：
```python
LOCAL_MODEL_PATH = Path(__file__).parent.parent.parent / "aiserver" / "models" / "qwen3_0__6b"
```

### 显存不足

修改 `config.py` 使用量化：
```python
PRECISION = "int8"  # 或 "int4"
```

## 7. 使用示例

### 命令行测试

```bash
# 健康检查
curl http://localhost:6015/health

# 判断无意义短语
curl -X POST http://localhost:6015/api/judge/meaningless \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"的 是 在\"}"
```

### Python 代码

```python
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:6015/api/judge/meaningless",
            json={"text": "的 是 在"}
        )
        print(response.json())

asyncio.run(test())
```

## 8. 性能优化

- 使用批量接口处理多个文本
- 调整 `config.py` 中的参数优化性能
- GTX 1660 Super 推荐使用 FP16

现在可以开始使用了！🚀
