# 快速安装指南

## 1. 创建虚拟环境

```bash
cd D:\work\AIGenTest\aiserver\qwentinyllm

# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

## 2. 安装依赖

```bash
pip install -r requirements.txt
```

如果遇到网络问题，使用国内镜像：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 3. 配置（可选）

编辑 `config.py` 修改配置：

```python
# 如果只有 CPU
DEVICE = "cpu"

# 如果显存不足，使用量化
PRECISION = "int8"  # 或 "int4"
```

## 4. 启动服务

### Windows

```bash
start_service.bat
```

或者：

```bash
python service.py
```

### Linux/Mac

```bash
chmod +x start_service.sh
./start_service.sh
```

或者：

```bash
python service.py
```

## 5. 测试服务

等待模型加载完成（首次运行需要下载模型，约 1.2GB），然后在新终端运行：

```bash
# 激活虚拟环境
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 运行测试
python test_api.py
```

或者直接访问：

```bash
curl http://localhost:6015/health
```

## 6. 常见问题

### Q: 模型下载失败

A: 设置使用 ModelScope（国内镜像）：

```python
# config.py
USE_MODELSCOPE = True
```

### Q: 显存不足

A: 使用量化版本：

```python
# config.py
PRECISION = "int8"  # ~1.5GB 显存
# 或
PRECISION = "int4"  # ~1GB 显存
```

### Q: 推理速度慢

A: 降低 `MAX_LENGTH` 或使用批量接口：

```python
# config.py
MAX_LENGTH = 256  # 默认 512
```

### Q: CUDA 版本不匹配

A: 安装对应 CUDA 版本的 PyTorch：

```bash
# CUDA 11.8
pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch==2.1.0 --index-url https://download.pytorch.org/whl/cu121
```

## 7. 服务信息

- **地址**: http://localhost:6015
- **文档**: http://localhost:6015/docs (自动生成的 API 文档)
- **健康检查**: http://localhost:6015/health
- **模型信息**: http://localhost:6015/info

## 8. 下一步

查看 `README.md` 了解详细的 API 使用方法和集成示例。
