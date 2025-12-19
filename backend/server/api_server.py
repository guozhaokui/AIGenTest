import os
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["ATTN_BACKEND"] = "sdpa"
os.environ["SPARSE_ATTN_BACKEND"] = "xformers"

import io
import uuid
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager

import torch
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import o_voxel
from trellis2.pipelines import Trellis2ImageTo3DPipeline

# 全局变量
pipeline = None
OUTPUT_DIR = Path("/data1/3D/TRELLIS.2/outputs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global pipeline
    
    # 启动时加载模型
    print("正在加载 TRELLIS.2 模型...")
    pipeline = Trellis2ImageTo3DPipeline.from_pretrained("/data1/models/microsoft/TRELLIS.2-4B")
    pipeline.cuda()
    print("模型加载完成！")
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    yield
    
    # 关闭时清理
    print("正在关闭服务...")


app = FastAPI(
    title="TRELLIS.2 3D Generation API",
    description="上传图片，生成3D模型（GLB格式）",
    version="1.0.0",
    lifespan=lifespan
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "message": "TRELLIS.2 3D Generation API is running"}


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "healthy",
        "model_loaded": pipeline is not None,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    }


@app.post("/generate")
async def generate_3d(
    image: UploadFile = File(..., description="要转换为3D模型的图片"),
    simplify_faces: int = 16777216,
    decimation_target: int = 1000000,
    texture_size: int = 4096,
    remesh: bool = True
):
    """
    上传图片，生成3D模型
    
    - **image**: 上传的图片文件（支持 PNG, JPG, WEBP 等格式）
    - **simplify_faces**: 简化后的最大面数（默认 16777216）
    - **decimation_target**: 最终目标面数（默认 1000000）
    - **texture_size**: 纹理大小（默认 4096）
    - **remesh**: 是否重新网格化（默认 True）
    
    返回生成的 GLB 文件
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="模型尚未加载完成")
    
    # 验证文件类型
    allowed_types = ["image/png", "image/jpeg", "image/webp", "image/jpg"]
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型: {image.content_type}。支持的类型: {allowed_types}"
        )
    
    try:
        # 读取图片
        content = await image.read()
        pil_image = Image.open(io.BytesIO(content)).convert("RGBA")
        
        # 生成唯一ID
        task_id = str(uuid.uuid4())[:8]
        output_path = OUTPUT_DIR / f"{task_id}.glb"
        
        print(f"[{task_id}] 开始生成3D模型...")
        
        # 生成3D模型
        with torch.inference_mode():
            mesh = pipeline.run(pil_image)[0]
            mesh.simplify(simplify_faces)
        
        print(f"[{task_id}] 3D模型生成完成，开始后处理...")
        
        # 后处理并导出GLB
        glb = o_voxel.postprocess.to_glb(
            vertices=mesh.vertices,
            faces=mesh.faces,
            attr_volume=mesh.attrs,
            coords=mesh.coords,
            attr_layout=mesh.layout,
            voxel_size=mesh.voxel_size,
            aabb=[[-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]],
            decimation_target=decimation_target,
            texture_size=texture_size,
            remesh=remesh,
            remesh_band=1,
            remesh_project=0,
            verbose=True
        )
        
        glb.export(str(output_path), extension_webp=False)
        
        print(f"[{task_id}] GLB 文件已保存: {output_path}")
        
        # 返回文件
        return FileResponse(
            path=str(output_path),
            filename=f"{task_id}.glb",
            media_type="model/gltf-binary"
        )
        
    except Exception as e:
        print(f"生成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"生成3D模型失败: {str(e)}")


@app.post("/generate_async")
async def generate_3d_async(
    image: UploadFile = File(..., description="要转换为3D模型的图片")
):
    """
    异步生成3D模型（返回任务ID，稍后查询结果）
    
    目前为简化版，直接返回下载链接
    """
    # 这里可以扩展为真正的异步任务队列
    result = await generate_3d(image)
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

