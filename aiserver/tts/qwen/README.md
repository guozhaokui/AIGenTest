# Qwen3-TTS 语音合成服务

基于Qwen3-TTS-12Hz-1.7B-VoiceDesign模型的高质量语音合成服务。

## 特性

- 🎙️ 多种音色支持（青年/中年男女声、老年、儿童）
- 😊 情绪控制（中性、快乐、悲伤、愤怒、兴奋）
- ⚡ 语速调节（0.5x-2.0x）
- 🎵 音调控制（0.5x-2.0x）
- 🔊 音量调节（0.1x-2.0x）
- 📦 多格式输出（WAV、MP3、OPUS）
- 🚀 GPU加速（NVIDIA 4090）
- 📡 RESTful API
- 📊 批量合成
- 📝 完整的API文档

## 环境要求

- Python 3.12+
- CUDA 11.8+
- NVIDIA GPU（推荐4090）
- 16GB+ RAM
- 10GB+ 磁盘空间（模型文件）

## 安装

### 1. 安装依赖

```bash
conda activate /mnt/hdd/anaconda3/envs/tts
pip install -r requirements.txt
```

### 2. 安装FFmpeg（用于格式转换）

```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# 或从conda安装
conda install -c conda-forge ffmpeg
```

### 3. （可选）安装pyrubberband以获得更好的音调控制

```bash
# 先安装系统依赖
sudo apt-get install librubberband-dev

# 再安装Python包
pip install pyrubberband
```

## 快速开始

### 启动服务

```bash
# 方式1：使用启动脚本
bash start_service.sh

# 方式2：直接运行
python main.py

# 方式3：使用uvicorn（生产环境）
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
```

服务将在 `http://localhost:8000` 启动。

### 测试服务

```bash
# 运行完整测试套件
python test_api.py

# 或使用curl快速测试
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，世界！"}' \
  --output test.wav
```

## API文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

完整API设计文档：[api_design.md](api_design.md)

## 使用示例

### Python客户端

```python
import requests

# 基础合成
response = requests.post(
    "http://localhost:8000/api/v1/synthesize",
    json={
        "text": "你好，我是Qwen语音助手！",
        "speaker": "young_female",
        "emotion": "happy",
        "speed": 1.2
    }
)

with open("output.wav", "wb") as f:
    f.write(response.content)
```

### JavaScript客户端

```javascript
const response = await fetch('http://localhost:8000/api/v1/synthesize', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    text: '你好，世界！',
    speaker: 'young_male',
    emotion: 'neutral'
  })
});

const audioBlob = await response.blob();
const audio = new Audio(URL.createObjectURL(audioBlob));
audio.play();
```

### cURL

```bash
# 基础合成
curl -X POST http://localhost:8000/api/v1/synthesize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "测试语音合成",
    "speaker": "young_female",
    "emotion": "happy",
    "speed": 1.0
  }' \
  --output speech.wav

# 获取音色列表
curl http://localhost:8000/api/v1/voices

# 批量合成
curl -X POST http://localhost:8000/api/v1/batch \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"text": "第一句", "speaker": "young_female"},
      {"text": "第二句", "speaker": "young_male"}
    ]
  }'
```

## 可用音色

| ID | 名称 | 描述 | 适用场景 |
|----|------|------|----------|
| young_female | 青年女性 | 清新自然 | 客服、教育、导航 |
| young_male | 青年男性 | 沉稳大气 | 新闻、广播、导航 |
| middle_aged_female | 中年女性 | 温柔知性 | 有声读物、教学 |
| middle_aged_male | 中年男性 | 成熟稳重 | 企业宣传、纪录片 |
| elderly | 老年人 | 慈祥和蔼 | 故事讲述 |
| child | 儿童 | 天真可爱 | 儿童内容、游戏 |

## 支持的情绪

- `neutral` - 中性（默认）
- `happy` - 快乐
- `sad` - 悲伤
- `angry` - 愤怒
- `excited` - 兴奋
- `calm` - 平静

## 项目结构

```
qwen/
├── main.py              # FastAPI主应用
├── config.py            # 配置文件
├── models.py            # Pydantic数据模型
├── tts_engine.py        # TTS核心引擎
├── audio_utils.py       # 音频处理工具
├── start_service.sh     # 启动脚本
├── test_api.py          # API测试脚本
├── requirements.txt     # 依赖包
├── api_design.md        # API设计文档
├── README.md            # 本文件
├── models/              # 模型缓存目录
└── outputs/             # 音频输出目录
```

## 性能指标

基于NVIDIA 4090测试：

- **首次加载**: ~5-10秒
- **短文本合成** (<50字): ~1-2秒
- **中等文本** (50-200字): ~2-5秒
- **长文本** (200-1000字): ~5-15秒
- **并发处理**: 建议最多10个并发请求
- **吞吐量**: 约5-10个请求/秒

## 故障排查

### 模型加载失败

```bash
# 检查conda环境
conda activate /mnt/hdd/anaconda3/envs/tts
python -c "import torch; print(torch.cuda.is_available())"

# 手动下载模型
python -c "from modelscope import snapshot_download; snapshot_download('Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign')"
```

### GPU内存不足

```python
# 在config.py中调整batch size或使用CPU
# 设置环境变量
export CUDA_VISIBLE_DEVICES=0
```

### 音频格式转换失败

```bash
# 确保ffmpeg已安装
ffmpeg -version

# 如果ffmpeg不可用，只使用wav格式
```

## 开发计划

- [ ] 音色克隆功能
- [ ] 流式输出
- [ ] SSML支持
- [ ] 多语言支持
- [ ] WebSocket接口
- [ ] 音频后处理增强
- [ ] 缓存机制
- [ ] 性能监控
- [ ] Docker部署

## 许可证

本项目基于Qwen3-TTS模型，遵循其许可证条款。

## 联系方式

问题反馈：请在项目中创建Issue

## 更新日志

### v1.0.0 (2026-01-30)
- 初始版本
- 基础TTS功能
- 多音色支持
- 情绪和语速控制
- 多格式输出
- RESTful API
- 批量合成
