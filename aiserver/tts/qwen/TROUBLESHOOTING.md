# 故障排查指南

本文档记录部署和测试过程中遇到的问题及解决方案。

## 🔧 依赖包问题

### 问题1: ModuleNotFoundError: No module named 'addict'

**错误信息：**
```
ModuleNotFoundError: No module named 'addict'
```

**原因：**
modelscope需要addict包，但未在requirements.txt中列出。

**解决方案：**
```bash
pip install addict
```

**状态：** ✅ 已解决

---

### 问题2: ModuleNotFoundError: No module named 'datasets'

**错误信息：**
```
ModuleNotFoundError: No module named 'datasets'
```

**原因：**
modelscope的某些功能依赖datasets包。

**解决方案：**
```bash
pip install datasets
```

**注意：** 安装后发现版本兼容性问题，见问题3。

**状态：** ⚠️ 引发新问题

---

### 问题3: datasets版本不兼容

**错误信息：**
```
ImportError: cannot import name 'ALL_ALLOWED_EXTENSIONS' from 'datasets.load'
```

**原因：**
- 安装了最新版本的datasets (4.5.0)
- modelscope 1.32.0依赖的是旧版本的datasets API
- 新版本移除了`ALL_ALLOWED_EXTENSIONS`

**解决方案：**
```bash
# 降级到2.x版本
pip install 'datasets<3.0.0'

# 或指定具体版本
pip install datasets==2.18.0
```

**状态：** 🔄 正在验证

---

### 问题4: FFmpeg不可用

**错误信息：**
```
RuntimeError: ffmpeg not available
```

**原因：**
MP3和OPUS格式转换需要FFmpeg。

**解决方案：**

**方法1：使用conda安装（推荐）**
```bash
conda install -c conda-forge ffmpeg
```

**方法2：使用apt安装**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

**验证安装：**
```bash
ffmpeg -version
```

**降级方案：**
如果无法安装FFmpeg，服务仍可运行，但只能输出WAV格式。

**状态：** ⏳ 待测试

---

## 🚀 模型加载问题

### 问题5: 模型下载缓慢

**现象：**
首次加载模型时下载很慢。

**原因：**
- 模型文件约1.7GB
- 可能受网络限制

**解决方案：**

**方法1：使用ModelScope镜像（国内）**
```bash
export MODELSCOPE_CACHE=./models
export MODELSCOPE_MIRROR=https://modelscope.cn
```

**方法2：手动下载模型**
```python
from modelscope import snapshot_download
model_dir = snapshot_download('Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign',
                               cache_dir='./models')
```

**方法3：离线部署**
在其他机器下载好模型，然后复制到服务器。

**状态：** ⏳ 首次运行时需要

---

### 问题6: CUDA out of memory

**错误信息：**
```
RuntimeError: CUDA out of memory
```

**原因：**
- GPU内存不足
- 并发请求过多

**解决方案：**

**临时方案：**
```bash
# 清理GPU缓存
python -c "import torch; torch.cuda.empty_cache()"

# 限制并发请求数
# 在config.py中设置
MAX_CONCURRENT_REQUESTS = 5
```

**长期方案：**
```bash
# 使用CPU模式（config.py会自动检测）
export CUDA_VISIBLE_DEVICES=""

# 或限制使用的GPU
export CUDA_VISIBLE_DEVICES=0
```

**状态：** ⏳ 待监控

---

## ⚙️ 服务运行问题

### 问题7: 端口被占用

**错误信息：**
```
OSError: [Errno 98] Address already in use
```

**原因：**
8000端口已被其他进程占用。

**解决方案：**

**查找占用进程：**
```bash
lsof -i:8000
# 或
netstat -tunlp | grep 8000
```

**杀死占用进程：**
```bash
kill -9 <PID>
```

**使用其他端口：**
在config.py中修改：
```python
PORT = 8001  # 改为其他端口
```

**状态：** ⏳ 待测试

---

### 问题8: 权限错误

**错误信息：**
```
PermissionError: [Errno 13] Permission denied
```

**原因：**
- 输出目录没有写权限
- 模型缓存目录没有写权限

**解决方案：**
```bash
# 创建目录并设置权限
mkdir -p outputs models
chmod 755 outputs models

# 或更改所有者
chown -R $USER:$USER outputs models
```

**状态：** ⏳ 待测试

---

## 🧪 测试问题

### 问题9: API测试超时

**现象：**
test_api.py运行时某些测试超时。

**原因：**
- 首次合成需要模型加载时间
- 长文本合成时间较长
- 网络延迟

**解决方案：**

**增加超时时间：**
在test_api.py中：
```python
response = requests.post(
    url,
    json=data,
    timeout=60  # 增加到60秒
)
```

**分批测试：**
```bash
# 只运行基础测试
python quick_test.py

# 再运行完整测试
python test_api.py
```

**状态：** ⏳ 待测试

---

### 问题10: 音频文件无法播放

**现象：**
生成的音频文件无法播放。

**可能原因：**
1. 文件格式错误
2. 采样率不支持
3. 数据类型错误

**诊断方法：**
```bash
# 使用ffprobe检查音频信息
ffprobe output.wav

# 使用Python检查
python -c "
import wave
with wave.open('output.wav', 'rb') as f:
    print('Channels:', f.getnchannels())
    print('Sample width:', f.getsampwidth())
    print('Frame rate:', f.getframerate())
    print('Frames:', f.getnframes())
"
```

**解决方案：**
- 确保采样率正确（12000 Hz）
- 确保是16位PCM格式
- 检查音频数据范围（-32768到32767）

**状态：** ⏳ 待测试

---

## 🔍 诊断工具

### 检查环境

```bash
# 检查Python版本
python --version

# 检查CUDA
nvidia-smi
python -c "import torch; print(torch.cuda.is_available())"

# 检查已安装的包
pip list | grep -E 'torch|transformers|modelscope|fastapi'

# 检查磁盘空间
df -h

# 检查内存
free -h
```

### 检查模型

```bash
# 查看模型缓存
ls -lh ./models/

# 测试模型加载
python quick_test.py
```

### 检查服务

```bash
# 测试服务是否运行
curl http://localhost:8000/health

# 查看进程
ps aux | grep python | grep main.py

# 查看日志（如果使用nohup）
tail -f service.log
```

---

## 📝 最佳实践

### 1. 首次部署清单

- [ ] 检查Python版本 (≥3.10)
- [ ] 检查CUDA版本 (≥11.8)
- [ ] 检查GPU显存 (≥8GB)
- [ ] 安装所有依赖包
- [ ] 运行quick_test.py
- [ ] 检查模型下载完成
- [ ] 启动服务
- [ ] 运行test_api.py

### 2. 依赖包版本建议

```txt
# 核心包
torch>=2.0.0
transformers>=4.50.0
modelscope>=1.30.0
fastapi>=0.100.0
uvicorn>=0.20.0

# 音频处理
soundfile>=0.12.0
librosa>=0.10.0
numpy>=1.24.0,<2.0.0

# 数据处理
datasets>=2.0.0,<3.0.0  # 注意版本限制
pydantic>=2.0.0

# 可选
pyrubberband>=0.3.0  # 需要系统先安装librubberband-dev
```

### 3. 环境变量设置

```bash
# 模型缓存
export MODELSCOPE_CACHE=./models

# GPU设置
export CUDA_VISIBLE_DEVICES=0

# 线程数（可选）
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
```

### 4. 日志配置

在main.py中添加：
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('tts_service.log'),
        logging.StreamHandler()
    ]
)
```

---

## 🆘 获取帮助

### 问题报告清单

提交问题时请包含：

1. **环境信息**
   - Python版本
   - CUDA版本
   - GPU型号
   - 操作系统

2. **错误信息**
   - 完整的错误堆栈
   - 相关日志

3. **复现步骤**
   - 执行的命令
   - 使用的配置
   - 输入数据

4. **已尝试的解决方案**

### 调试模式

启用详细日志：
```python
# 在main.py开头添加
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 常用命令

```bash
# 查看服务状态
systemctl status tts-service  # 如果使用systemd

# 查看实时日志
tail -f tts_service.log

# 查看GPU使用
watch -n 1 nvidia-smi

# 测试API
curl -v http://localhost:8000/health
```

---

## 📚 参考资源

- [FastAPI文档](https://fastapi.tiangolo.com/)
- [ModelScope文档](https://modelscope.cn/docs)
- [PyTorch文档](https://pytorch.org/docs/)
- [Qwen3-TTS模型页面](https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign)

---

## 🔄 更新日志

- 2026-01-30: 初始版本
  - 记录了依赖包兼容性问题
  - 添加了datasets版本降级方案
  - 提供了常见问题解决方案
