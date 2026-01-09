"""
LTX-2 视频生成服务
提供文生视频 (Text-to-Video) 和图生视频 (Image-to-Video) 接口

⚠️ 重要：此服务只能在 8x3090 服务器上运行
    - 需要使用 conda 环境: ltx
    - 模型路径: /data1/MLLM/ltx-2/models/Lightricks/LTX-2
    - 显存需求: 单卡 RTX 3090 (24GB)
"""
import os
import sys
import uuid
import time
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
import uvicorn

# ============================================================
# 配置
# ============================================================

# 服务配置
SERVICE_NAME = "LTX-2 Video Generation"
SERVICE_VERSION = "1.0.0"
DEFAULT_PORT = 6070

# 模型配置
MODEL_ROOT = "/data1/MLLM/ltx-2/models/Lightricks/LTX-2"
CHECKPOINT = f"{MODEL_ROOT}/ltx-2-19b-distilled-fp8.safetensors"
GEMMA_ROOT = MODEL_ROOT
UPSAMPLER = f"{MODEL_ROOT}/ltx-2-spatial-upscaler-x2-1.0.safetensors"

# 输出配置
OUTPUT_DIR = "/data1/MLLM/ltx-2/outputs/api"
TEMP_DIR = "/data1/MLLM/ltx-2/temp"

# 工作目录
WORK_DIR = "/data1/MLLM/ltx-2"

# 默认参数
DEFAULT_HEIGHT = 512
DEFAULT_WIDTH = 768
DEFAULT_NUM_FRAMES = 25
DEFAULT_FRAME_RATE = 25.0
DEFAULT_SEED = 42
DEFAULT_GPU = 0

# 确保目录存在
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ============================================================
# FastAPI App
# ============================================================

app = FastAPI(
    title=SERVICE_NAME,
    description="LTX-2 视频生成服务 - 支持文生视频和图生视频",
    version=SERVICE_VERSION,
)


# ============================================================
# 请求模型
# ============================================================

class Text2VideoRequest(BaseModel):
    """文生视频请求"""
    prompt: str = Field(..., description="文本提示词，描述视频内容")
    height: int = Field(DEFAULT_HEIGHT, description="视频高度 (推荐 512)")
    width: int = Field(DEFAULT_WIDTH, description="视频宽度 (推荐 768)")
    num_frames: int = Field(DEFAULT_NUM_FRAMES, description="帧数 (公式: 8*K+1, 如 25, 49, 97)")
    frame_rate: float = Field(DEFAULT_FRAME_RATE, description="帧率")
    seed: int = Field(DEFAULT_SEED, description="随机种子 (-1 为随机)")
    gpu_id: int = Field(DEFAULT_GPU, description="GPU 编号 (0-7)")


class Image2VideoRequest(BaseModel):
    """图生视频请求 (JSON 方式)"""
    prompt: str = Field(..., description="文本提示词，描述动作")
    image_path: str = Field(..., description="输入图片路径")
    height: int = Field(DEFAULT_HEIGHT, description="视频高度")
    width: int = Field(DEFAULT_WIDTH, description="视频宽度")
    num_frames: int = Field(DEFAULT_NUM_FRAMES, description="帧数")
    frame_rate: float = Field(DEFAULT_FRAME_RATE, description="帧率")
    seed: int = Field(DEFAULT_SEED, description="随机种子")
    gpu_id: int = Field(DEFAULT_GPU, description="GPU 编号")


class GenerationResponse(BaseModel):
    """生成响应"""
    success: bool
    task_id: str
    video_path: Optional[str] = None
    video_url: Optional[str] = None
    duration: float = 0.0
    message: str = ""


# ============================================================
# 核心生成函数
# ============================================================

def generate_video_cli(
    prompt: str,
    output_path: str,
    image_path: Optional[str] = None,
    height: int = DEFAULT_HEIGHT,
    width: int = DEFAULT_WIDTH,
    num_frames: int = DEFAULT_NUM_FRAMES,
    frame_rate: float = DEFAULT_FRAME_RATE,
    seed: int = DEFAULT_SEED,
    gpu_id: int = DEFAULT_GPU,
) -> tuple[bool, str]:
    """
    调用 CLI 生成视频
    
    Returns:
        (success, message)
    """
    # 处理随机种子
    if seed < 0:
        import random
        seed = random.randint(0, 2**32 - 1)
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "ltx_pipelines.distilled",
        "--checkpoint-path", CHECKPOINT,
        "--gemma-root", GEMMA_ROOT,
        "--spatial-upsampler-path", UPSAMPLER,
        "--prompt", prompt,
        "--output-path", output_path,
        "--height", str(height),
        "--width", str(width),
        "--num-frames", str(num_frames),
        "--frame-rate", str(frame_rate),
        "--seed", str(seed),
        "--enable-fp8",
        "--gemma-4bit",
    ]
    
    # 添加图片条件
    if image_path:
        cmd.extend(["--image", image_path, "0", "1.0"])
    
    # 设置环境变量
    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    env["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    
    # 运行命令
    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
        )
        
        if result.returncode == 0:
            return True, "生成成功"
        else:
            error_msg = result.stderr[-500:] if result.stderr else "未知错误"
            return False, f"生成失败: {error_msg}"
            
    except subprocess.TimeoutExpired:
        return False, "生成超时 (>10分钟)"
    except Exception as e:
        return False, f"执行错误: {str(e)}"


# ============================================================
# API 接口
# ============================================================

@app.get("/health")
async def health_check():
    """健康检查"""
    # 检查模型文件是否存在
    model_exists = os.path.exists(CHECKPOINT)
    
    return {
        "status": "ok" if model_exists else "error",
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "model_path": MODEL_ROOT,
        "model_exists": model_exists,
        "output_dir": OUTPUT_DIR,
        "environment": "8x3090",
        "conda_env": "ltx",
    }


@app.post("/generate/text2video", response_model=GenerationResponse)
async def text_to_video(request: Text2VideoRequest):
    """
    文生视频 (Text-to-Video)
    
    根据文本提示词生成视频
    """
    task_id = f"t2v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    output_path = os.path.join(OUTPUT_DIR, f"{task_id}.mp4")
    
    start_time = time.time()
    
    success, message = generate_video_cli(
        prompt=request.prompt,
        output_path=output_path,
        image_path=None,
        height=request.height,
        width=request.width,
        num_frames=request.num_frames,
        frame_rate=request.frame_rate,
        seed=request.seed,
        gpu_id=request.gpu_id,
    )
    
    duration = time.time() - start_time
    
    if success and os.path.exists(output_path):
        return GenerationResponse(
            success=True,
            task_id=task_id,
            video_path=output_path,
            video_url=f"/download/{task_id}",
            duration=duration,
            message=message,
        )
    else:
        return GenerationResponse(
            success=False,
            task_id=task_id,
            duration=duration,
            message=message,
        )


@app.post("/generate/image2video", response_model=GenerationResponse)
async def image_to_video(request: Image2VideoRequest):
    """
    图生视频 (Image-to-Video) - JSON 方式
    
    根据图片和文本提示词生成视频
    图片路径必须是服务器上的绝对路径
    """
    # 检查图片是否存在
    if not os.path.exists(request.image_path):
        raise HTTPException(status_code=400, detail=f"图片不存在: {request.image_path}")
    
    task_id = f"i2v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    output_path = os.path.join(OUTPUT_DIR, f"{task_id}.mp4")
    
    start_time = time.time()
    
    success, message = generate_video_cli(
        prompt=request.prompt,
        output_path=output_path,
        image_path=request.image_path,
        height=request.height,
        width=request.width,
        num_frames=request.num_frames,
        frame_rate=request.frame_rate,
        seed=request.seed,
        gpu_id=request.gpu_id,
    )
    
    duration = time.time() - start_time
    
    if success and os.path.exists(output_path):
        return GenerationResponse(
            success=True,
            task_id=task_id,
            video_path=output_path,
            video_url=f"/download/{task_id}",
            duration=duration,
            message=message,
        )
    else:
        return GenerationResponse(
            success=False,
            task_id=task_id,
            duration=duration,
            message=message,
        )


@app.post("/generate/image2video/upload", response_model=GenerationResponse)
async def image_to_video_upload(
    prompt: str = Form(..., description="文本提示词"),
    image: UploadFile = File(..., description="输入图片"),
    height: int = Form(DEFAULT_HEIGHT),
    width: int = Form(DEFAULT_WIDTH),
    num_frames: int = Form(DEFAULT_NUM_FRAMES),
    frame_rate: float = Form(DEFAULT_FRAME_RATE),
    seed: int = Form(DEFAULT_SEED),
    gpu_id: int = Form(DEFAULT_GPU),
):
    """
    图生视频 (Image-to-Video) - 上传图片方式
    
    上传图片并根据文本提示词生成视频
    """
    task_id = f"i2v_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    # 保存上传的图片
    image_ext = Path(image.filename).suffix or ".jpg"
    temp_image_path = os.path.join(TEMP_DIR, f"{task_id}{image_ext}")
    output_path = os.path.join(OUTPUT_DIR, f"{task_id}.mp4")
    
    try:
        with open(temp_image_path, "wb") as f:
            content = await image.read()
            f.write(content)
        
        start_time = time.time()
        
        success, message = generate_video_cli(
            prompt=prompt,
            output_path=output_path,
            image_path=temp_image_path,
            height=height,
            width=width,
            num_frames=num_frames,
            frame_rate=frame_rate,
            seed=seed,
            gpu_id=gpu_id,
        )
        
        duration = time.time() - start_time
        
        if success and os.path.exists(output_path):
            return GenerationResponse(
                success=True,
                task_id=task_id,
                video_path=output_path,
                video_url=f"/download/{task_id}",
                duration=duration,
                message=message,
            )
        else:
            return GenerationResponse(
                success=False,
                task_id=task_id,
                duration=duration,
                message=message,
            )
    
    finally:
        # 清理临时文件
        if os.path.exists(temp_image_path):
            os.remove(temp_image_path)


@app.get("/download/{task_id}")
async def download_video(task_id: str):
    """下载生成的视频"""
    video_path = os.path.join(OUTPUT_DIR, f"{task_id}.mp4")
    
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="视频不存在")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{task_id}.mp4",
    )


@app.get("/list")
async def list_videos():
    """列出所有生成的视频"""
    videos = []
    for f in sorted(Path(OUTPUT_DIR).glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = f.stat()
        videos.append({
            "task_id": f.stem,
            "filename": f.name,
            "size_mb": round(stat.st_size / 1024 / 1024, 2),
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "download_url": f"/download/{f.stem}",
        })
    
    return {"count": len(videos), "videos": videos[:50]}  # 最多返回 50 个


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LTX-2 视频生成服务")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="服务端口")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    args = parser.parse_args()
    
    print(f"=" * 60)
    print(f"LTX-2 视频生成服务")
    print(f"=" * 60)
    print(f"端口: {args.port}")
    print(f"模型: {MODEL_ROOT}")
    print(f"输出: {OUTPUT_DIR}")
    print(f"环境: 8x3090 / conda: ltx")
    print(f"=" * 60)
    
    uvicorn.run(app, host=args.host, port=args.port)

