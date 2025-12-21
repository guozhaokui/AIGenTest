import os
os.environ['OPENCV_IO_ENABLE_OPENEXR'] = '1'
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
os.environ["ATTN_BACKEND"] = "sdpa"
os.environ["SPARSE_ATTN_BACKEND"] = "xformers"

import io
import uuid
import time
import tempfile
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

import torch
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
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
    simplify_faces: int = Form(default=16777216),
    decimation_target: int = Form(default=200000),  # 降低默认值，加速 UV 计算
    texture_size: int = Form(default=2048),  # 降低纹理大小
    remesh: bool = Form(default=True)
):
    """
    上传图片，生成3D模型
    
    - **image**: 上传的图片文件（支持 PNG, JPG, WEBP 等格式）
    - **simplify_faces**: 简化后的最大面数（默认 16777216）
    - **decimation_target**: 最终目标面数（默认 200000）
    - **texture_size**: 纹理大小（默认 2048）
    - **remesh**: 是否重新网格化（默认 True）
    
    返回生成的 GLB 文件
    """
    # 生成唯一ID
    task_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # ===== 打印请求参数 =====
    print("\n" + "="*60)
    print(f"[{task_id}] 新请求 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    print(f"📁 文件名: {image.filename}")
    print(f"📁 文件类型: {image.content_type}")
    print(f"📁 文件大小: {image.size if hasattr(image, 'size') else '未知'}")
    print(f"⚙️  参数:")
    print(f"   - simplify_faces: {simplify_faces:,}")
    print(f"   - decimation_target: {decimation_target:,}")
    print(f"   - texture_size: {texture_size}")
    print(f"   - remesh: {remesh}")
    print("-"*60)
    
    if pipeline is None:
        print(f"[{task_id}] ❌ 错误: 模型尚未加载")
        raise HTTPException(status_code=503, detail="模型尚未加载完成")
    
    # 验证文件类型
    allowed_types = ["image/png", "image/jpeg", "image/webp", "image/jpg"]
    if image.content_type not in allowed_types:
        print(f"[{task_id}] ❌ 错误: 不支持的文件类型 {image.content_type}")
        raise HTTPException(
            status_code=400, 
            detail=f"不支持的文件类型: {image.content_type}。支持的类型: {allowed_types}"
        )
    
    try:
        # 读取图片
        t0 = time.time()
        content = await image.read()
        pil_image = Image.open(io.BytesIO(content)).convert("RGBA")
        print(f"[{task_id}] 📷 图片加载完成: {pil_image.size[0]}x{pil_image.size[1]}, 耗时: {time.time()-t0:.2f}s")
        
        output_path = OUTPUT_DIR / f"{task_id}.glb"
        
        # 生成3D模型
        print(f"[{task_id}] 🚀 开始生成3D模型...")
        t1 = time.time()
        with torch.inference_mode():
            mesh = pipeline.run(pil_image)[0]
            t2 = time.time()
            print(f"[{task_id}] ✅ Pipeline完成, 耗时: {t2-t1:.2f}s")
            print(f"[{task_id}]    - 顶点数: {mesh.vertices.shape[0]:,}")
            print(f"[{task_id}]    - 面数: {mesh.faces.shape[0]:,}")
            
            mesh.simplify(simplify_faces)
            t3 = time.time()
            print(f"[{task_id}] ✅ Simplify完成, 耗时: {t3-t2:.2f}s")
            print(f"[{task_id}]    - 简化后面数: {mesh.faces.shape[0]:,}")
        
        # 后处理并导出GLB
        print(f"[{task_id}] 🔧 开始后处理 (to_glb)...")
        t4 = time.time()
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
        t5 = time.time()
        print(f"[{task_id}] ✅ 后处理完成, 耗时: {t5-t4:.2f}s")
        
        glb.export(str(output_path), extension_webp=False)
        file_size = output_path.stat().st_size / (1024 * 1024)  # MB
        
        total_time = time.time() - start_time
        print("-"*60)
        print(f"[{task_id}] 🎉 完成!")
        print(f"   - 输出文件: {output_path}")
        print(f"   - 文件大小: {file_size:.2f} MB")
        print(f"   - 总耗时: {total_time:.2f}s")
        print("="*60 + "\n")
        
        # 返回文件
        return FileResponse(
            path=str(output_path),
            filename=f"{task_id}.glb",
            media_type="model/gltf-binary"
        )
        
    except Exception as e:
        import traceback
        print(f"[{task_id}] ❌ 生成失败!")
        print(f"   - 错误类型: {type(e).__name__}")
        print(f"   - 错误信息: {str(e)}")
        print(f"   - 堆栈跟踪:")
        traceback.print_exc()
        print("="*60 + "\n")
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

