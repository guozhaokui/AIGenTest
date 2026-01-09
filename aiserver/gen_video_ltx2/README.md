# LTX-2 视频生成服务

基于 Lightricks LTX-2 模型的视频生成服务，提供文生视频和图生视频接口。

## ⚠️ 环境要求

| 项目 | 要求 |
|------|------|
| **服务器** | 8x3090 (只能在此服务器运行) |
| **Conda 环境** | `ltx` |
| **显存需求** | 单卡 RTX 3090 (24GB) |
| **Python** | 3.12 |

## 服务信息

| 项目 | 值 |
|------|-----|
| 端口 | 6020 |
| 模型 | LTX-2 19B Distilled (FP8 + Gemma 4-bit) |
| 模型路径 | `/data1/MLLM/ltx-2/models/Lightricks/LTX-2` |
| 输出目录 | `/data1/MLLM/ltx-2/outputs/api` |

## 模型文件

使用的模型文件：

| 文件 | 大小 | 说明 |
|------|------|------|
| `ltx-2-19b-distilled-fp8.safetensors` | 26GB | 蒸馏模型 (FP8) |
| `ltx-2-spatial-upscaler-x2-1.0.safetensors` | 0.9GB | 空间上采样器 |
| `text_encoder/` | ~54GB | Gemma 3 27B 文本编码器 |

## 修改的文件

为了支持单卡 RTX 3090 运行，对 LTX-2 源码进行了以下修改：

| 文件 | 修改内容 |
|------|---------|
| `packages/ltx-core/src/ltx_core/text_encoders/gemma/encoders/base_encoder.py` | 添加 Gemma 4-bit/8-bit 量化支持 |
| `packages/ltx-pipelines/src/ltx_pipelines/utils/model_ledger.py` | 添加 `gemma_4bit`, `gemma_8bit` 参数 |
| `packages/ltx-pipelines/src/ltx_pipelines/utils/args.py` | 添加 `--gemma-4bit`, `--gemma-8bit` 命令行参数 |
| `packages/ltx-pipelines/src/ltx_pipelines/distilled.py` | 支持量化参数传递 |
| `packages/ltx-pipelines/src/ltx_pipelines/keyframe_interpolation.py` | 支持量化参数传递 |

## 快速开始

### 启动服务

```bash
cd /data1/guo/AIGenTest/aiserver/gen_video_ltx2
./start.sh
```

或手动启动：

```bash
conda activate ltx
python ltx2_server.py --port 6020
```

### 停止服务

```bash
./stop.sh
```

## API 接口

### 1. 健康检查

```bash
curl http://localhost:6020/health
```

### 2. 文生视频 (Text-to-Video)

```bash
curl -X POST http://localhost:6020/generate/text2video \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A beautiful sunset over the ocean with gentle waves",
    "num_frames": 25,
    "height": 512,
    "width": 768
  }'
```

**参数说明：**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `prompt` | string | 必填 | 文本提示词 |
| `height` | int | 512 | 视频高度 |
| `width` | int | 768 | 视频宽度 |
| `num_frames` | int | 25 | 帧数 (公式: 8*K+1) |
| `frame_rate` | float | 25.0 | 帧率 |
| `seed` | int | 42 | 随机种子 (-1 为随机) |
| `gpu_id` | int | 0 | GPU 编号 (0-7) |

### 3. 图生视频 (Image-to-Video) - JSON 方式

```bash
curl -X POST http://localhost:6020/generate/image2video \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A person slowly turns their head and smiles",
    "image_path": "/data1/MLLM/ltx-2/test_image.jpg",
    "num_frames": 25
  }'
```

### 4. 图生视频 (Image-to-Video) - 上传图片方式

```bash
curl -X POST http://localhost:6020/generate/image2video/upload \
  -F "prompt=A person slowly smiles" \
  -F "image=@/path/to/image.jpg" \
  -F "num_frames=25"
```

### 5. 下载视频

```bash
curl -O http://localhost:6020/download/{task_id}
```

### 6. 列出视频

```bash
curl http://localhost:6020/list
```

## 响应格式

```json
{
  "success": true,
  "task_id": "t2v_20260109_152500_abc12345",
  "video_path": "/data1/MLLM/ltx-2/outputs/api/t2v_20260109_152500_abc12345.mp4",
  "video_url": "/download/t2v_20260109_152500_abc12345",
  "duration": 45.2,
  "message": "生成成功"
}
```

## Python 调用示例

```python
import requests

# 文生视频
response = requests.post(
    "http://localhost:6020/generate/text2video",
    json={
        "prompt": "A cat walking slowly across the room",
        "num_frames": 25,
    }
)
result = response.json()
print(f"视频路径: {result['video_path']}")

# 图生视频（上传图片）
with open("input.jpg", "rb") as f:
    response = requests.post(
        "http://localhost:6020/generate/image2video/upload",
        data={"prompt": "The person slowly smiles", "num_frames": 49},
        files={"image": f}
    )
result = response.json()
print(f"视频路径: {result['video_path']}")

# 下载视频
if result["success"]:
    video = requests.get(f"http://localhost:6020{result['video_url']}")
    with open("output.mp4", "wb") as f:
        f.write(video.content)
```

## 帧数与时长对应

| num_frames | 时长 (25fps) |
|------------|-------------|
| 25 | 1 秒 |
| 33 | 1.3 秒 |
| 41 | 1.6 秒 |
| 49 | 2 秒 |
| 97 | ~4 秒 |

**帧数公式**: `num_frames = 8 * K + 1`（K 为正整数）

## 显存使用

| 组件 | 显存 |
|------|------|
| Transformer (FP8) | ~7GB |
| Gemma 3 27B (4-bit) | ~15GB |
| VAE + Upsampler | ~2GB |
| **总计** | **~24GB** |

## 故障排除

### 1. CUDA out of memory

确保：
- 使用单卡运行 (`gpu_id` 参数)
- 没有其他进程占用 GPU
- 使用默认分辨率 (512x768)

### 2. 模型加载失败

检查：
- 模型文件是否存在: `/data1/MLLM/ltx-2/models/Lightricks/LTX-2/`
- Conda 环境是否正确: `conda activate ltx`
- bitsandbytes 是否安装: `pip install bitsandbytes`

### 3. 生成超时

- 默认超时 10 分钟
- 减少 `num_frames` 可加快生成

## 相关文件

| 文件 | 说明 |
|------|------|
| `/data1/MLLM/ltx-2/run_ltx2.py` | 命令行测试脚本 |
| `/data1/MLLM/ltx-2/USAGE_GUIDE.md` | 详细使用指南 |
| `/data1/MLLM/ltx-2/models/` | 模型文件目录 |

## 更新日志

- **2026-01-09**: 初始版本，支持文生视频和图生视频

