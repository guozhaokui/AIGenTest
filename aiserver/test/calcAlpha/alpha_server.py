"""
图片Alpha计算服务
==================
根据不同策略计算图片的alpha通道，输出带透明通道的PNG图片

功能：
1. 单图 + 背景色 -> 计算alpha
2. 双图（相同前景，不同背景）+ 背景色 -> 计算alpha  
3. 原图 + 黑白遮罩图 -> 直接应用alpha
"""

import io
import os
import sys
import argparse
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Tuple
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 当前脚本目录
SCRIPT_DIR = Path(__file__).parent.resolve()


app = FastAPI(
    title="Alpha计算服务",
    description="计算图片的alpha通道，输出带透明的PNG图片",
    version="1.0.0"
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """将十六进制颜色转换为RGB元组
    
    支持格式: #RRGGBB, RRGGBB, 0xRRGGBB
    """
    hex_color = hex_color.strip()
    if hex_color.startswith('#'):
        hex_color = hex_color[1:]
    elif hex_color.startswith('0x') or hex_color.startswith('0X'):
        hex_color = hex_color[2:]
    
    if len(hex_color) != 6:
        raise ValueError(f"无效的颜色格式: {hex_color}")
    
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b)


def resize_to_match(img: Image.Image, target_size: Tuple[int, int]) -> Image.Image:
    """将图片缩放到目标尺寸（不裁剪）"""
    if img.size == target_size:
        return img
    return img.resize(target_size, Image.Resampling.LANCZOS)


def calc_alpha_from_single_image(
    img: Image.Image,
    bg_color: Tuple[int, int, int],
    tolerance: float = 0.3,
    edge_softness: float = 0.1
) -> Image.Image:
    """
    从单张图片计算alpha通道
    
    原理：
    - 计算每个像素与背景色的相似度
    - 背景色相似度高 -> alpha低（透明）
    - 背景色相似度低 -> alpha高（不透明）
    
    参数:
        img: 输入图片
        bg_color: 背景色RGB
        tolerance: 背景色容差范围 (0-1)，越大则更多颜色被视为背景
        edge_softness: 边缘柔化程度 (0-1)
    """
    # 转换为RGBA
    img = img.convert('RGB')
    img_array = np.array(img, dtype=np.float32) / 255.0
    
    bg = np.array(bg_color, dtype=np.float32) / 255.0
    
    # 计算每个像素与背景色的距离
    # 使用加权欧氏距离，考虑人眼对绿色更敏感
    weights = np.array([0.299, 0.587, 0.114])  # 亮度权重
    diff = img_array - bg
    weighted_diff = diff * weights
    distance = np.sqrt(np.sum(weighted_diff ** 2, axis=2))
    
    # 归一化距离
    max_distance = np.sqrt(np.sum(weights ** 2))
    normalized_distance = distance / max_distance
    
    # 使用sigmoid函数平滑过渡
    # 根据tolerance调整中心点
    center = tolerance
    steepness = 10.0 / (edge_softness + 0.01)  # 控制边缘锐度
    
    alpha = 1.0 / (1.0 + np.exp(-steepness * (normalized_distance - center)))
    
    # 限制范围
    alpha = np.clip(alpha, 0, 1)
    
    # 创建带alpha的图片
    rgba_array = np.zeros((img_array.shape[0], img_array.shape[1], 4), dtype=np.uint8)
    rgba_array[:, :, :3] = (img_array * 255).astype(np.uint8)
    rgba_array[:, :, 3] = (alpha * 255).astype(np.uint8)
    
    return Image.fromarray(rgba_array, 'RGBA')


def calc_alpha_from_two_images(
    img1: Image.Image,
    img2: Image.Image,
    bg_color1: Tuple[int, int, int],
    bg_color2: Tuple[int, int, int]
) -> Image.Image:
    """
    从两张图片计算alpha通道（差异比较法）
    
    原理：
    合成公式: C = α*F + (1-α)*B
    
    对于两张图（相同前景F，不同背景B1,B2）：
    C1 = α*F + (1-α)*B1
    C2 = α*F + (1-α)*B2
    
    两式相减：
    C1 - C2 = (1-α)*(B1 - B2)
    
    所以：
    α = 1 - |C1 - C2| / |B1 - B2|
    
    半透明边缘自然就有渐变的alpha值，无需人工柔化。
    
    参数:
        img1: 第一张图片（如绿背景）
        img2: 第二张图片（如蓝背景）
        bg_color1: 第一张图的背景色
        bg_color2: 第二张图的背景色
    """
    # 确保尺寸一致
    target_size = img1.size
    img2 = resize_to_match(img2, target_size)
    
    # 转换为浮点数组
    img1 = img1.convert('RGB')
    img2 = img2.convert('RGB')
    
    c1 = np.array(img1, dtype=np.float32) / 255.0
    c2 = np.array(img2, dtype=np.float32) / 255.0
    
    b1 = np.array(bg_color1, dtype=np.float32) / 255.0
    b2 = np.array(bg_color2, dtype=np.float32) / 255.0
    
    # =========================================
    # 核心算法：alpha = 1 - |C1-C2| / |B1-B2|
    # =========================================
    
    # 背景色差异向量
    bg_diff = b1 - b2  # shape: (3,)
    
    # 像素差异
    pixel_diff = c1 - c2  # shape: (H, W, 3)
    
    # 对每个通道分别计算 alpha
    # alpha_channel = 1 - (C1-C2) / (B1-B2)
    epsilon = 1e-6
    alpha_per_channel = []
    valid_channels = []
    
    for i in range(3):
        if abs(bg_diff[i]) > 0.05:  # 只使用背景差异足够大的通道
            # alpha = 1 - (c1-c2)/(b1-b2)
            alpha_ch = 1.0 - pixel_diff[:, :, i] / (bg_diff[i] + epsilon)
            alpha_per_channel.append(alpha_ch)
            valid_channels.append(i)
    
    if len(alpha_per_channel) == 0:
        # 背景色差异太小，无法计算
        print("警告: 两张图的背景色差异太小，请使用差异更大的背景色")
        # 回退：使用简单的差异计算
        diff_magnitude = np.sqrt(np.sum(pixel_diff ** 2, axis=2))
        bg_magnitude = np.sqrt(np.sum(bg_diff ** 2))
        alpha = 1.0 - diff_magnitude / (bg_magnitude + epsilon)
        alpha = np.clip(alpha, 0, 1)
    else:
        # 取各通道的中值作为最终alpha（更稳健）
        alpha_stack = np.stack(alpha_per_channel, axis=2)
        alpha = np.median(alpha_stack, axis=2)
        alpha = np.clip(alpha, 0, 1)
    
    # =========================================
    # 计算前景色
    # F = (C - (1-α)*B) / α
    # =========================================
    
    alpha_3d = alpha[:, :, np.newaxis]
    
    # 从两张图分别估算前景色
    f1 = (c1 - (1 - alpha_3d) * b1) / (alpha_3d + epsilon)
    f2 = (c2 - (1 - alpha_3d) * b2) / (alpha_3d + epsilon)
    
    # 取平均
    foreground = (f1 + f2) / 2.0
    foreground = np.clip(foreground, 0, 1)
    
    # 对于完全透明的区域（alpha < 0.01），颜色不重要，用原图避免噪点
    mask = alpha_3d < 0.01
    foreground = np.where(mask, c1, foreground)
    
    # 创建带alpha的图片
    rgba_array = np.zeros((c1.shape[0], c1.shape[1], 4), dtype=np.uint8)
    rgba_array[:, :, :3] = (foreground * 255).astype(np.uint8)
    rgba_array[:, :, 3] = (alpha * 255).astype(np.uint8)
    
    return Image.fromarray(rgba_array, 'RGBA')


def apply_mask_as_alpha(
    img: Image.Image,
    mask: Image.Image,
    invert_mask: bool = False
) -> Image.Image:
    """
    将黑白遮罩图作为alpha通道应用到图片
    
    参数:
        img: 原始图片
        mask: 黑白遮罩图（白色=不透明，黑色=透明）
        invert_mask: 是否反转遮罩
    """
    # 确保尺寸一致
    target_size = img.size
    mask = resize_to_match(mask, target_size)
    
    # 转换格式
    img = img.convert('RGB')
    mask = mask.convert('L')  # 转为灰度图
    
    img_array = np.array(img)
    mask_array = np.array(mask)
    
    if invert_mask:
        mask_array = 255 - mask_array
    
    # 创建RGBA图片
    rgba_array = np.zeros((img_array.shape[0], img_array.shape[1], 4), dtype=np.uint8)
    rgba_array[:, :, :3] = img_array
    rgba_array[:, :, 3] = mask_array
    
    return Image.fromarray(rgba_array, 'RGBA')


def image_to_bytes(img: Image.Image) -> bytes:
    """将PIL Image转换为PNG字节流"""
    buffer = io.BytesIO()
    img.save(buffer, format='PNG', optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


# =============================================================================
# API端点
# =============================================================================

@app.get("/")
async def root():
    """服务状态检查"""
    return {
        "service": "Alpha计算服务",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "/api/alpha/single": "单图+背景色计算alpha",
            "/api/alpha/dual": "双图+背景色计算alpha",
            "/api/alpha/mask": "原图+遮罩图应用alpha"
        }
    }


@app.post("/api/alpha/single")
async def calc_alpha_single(
    image: UploadFile = File(..., description="输入图片"),
    bg_color: str = Form(..., description="背景色，支持 #RRGGBB 或 RRGGBB 格式"),
    tolerance: float = Form(0.3, description="背景容差 0-1"),
    edge_softness: float = Form(0.1, description="边缘柔化 0-1")
):
    """
    功能1: 单图 + 背景色 -> 计算alpha
    
    上传一张图片和背景色，计算alpha通道后返回带透明的PNG
    """
    try:
        # 解析背景色
        bg_rgb = hex_to_rgb(bg_color)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"背景色格式错误: {e}")
    
    # 读取图片
    try:
        img_bytes = await image.read()
        img = Image.open(io.BytesIO(img_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片读取失败: {e}")
    
    # 计算alpha
    result = calc_alpha_from_single_image(
        img, bg_rgb, 
        tolerance=tolerance, 
        edge_softness=edge_softness
    )
    
    # 返回PNG
    png_bytes = image_to_bytes(result)
    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=result.png"}
    )


@app.post("/api/alpha/dual")
async def calc_alpha_dual(
    image1: UploadFile = File(..., description="第一张图片"),
    image2: UploadFile = File(..., description="第二张图片（相同前景，不同背景）"),
    bg_color1: str = Form(..., description="第一张图的背景色"),
    bg_color2: str = Form(..., description="第二张图的背景色")
):
    """
    功能2: 双图（相同前景，不同背景）+ 背景色 -> 计算alpha
    
    原理：
    C1 - C2 = (1-α) * (B1 - B2)
    α = 1 - |C1-C2| / |B1-B2|
    
    半透明边缘自然就有渐变的alpha值，无需人工柔化。
    图片大小以第一张图为准。
    """
    try:
        bg_rgb1 = hex_to_rgb(bg_color1)
        bg_rgb2 = hex_to_rgb(bg_color2)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"背景色格式错误: {e}")
    
    # 读取图片
    try:
        img1_bytes = await image1.read()
        img2_bytes = await image2.read()
        img1 = Image.open(io.BytesIO(img1_bytes))
        img2 = Image.open(io.BytesIO(img2_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片读取失败: {e}")
    
    # 计算alpha
    result = calc_alpha_from_two_images(img1, img2, bg_rgb1, bg_rgb2)
    
    # 返回PNG
    png_bytes = image_to_bytes(result)
    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=result.png"}
    )


@app.post("/api/alpha/mask")
async def apply_alpha_mask(
    image: UploadFile = File(..., description="原始图片"),
    mask: UploadFile = File(..., description="黑白遮罩图（白色=不透明，黑色=透明）"),
    invert: bool = Form(False, description="是否反转遮罩")
):
    """
    功能3: 原图 + 黑白遮罩图 -> 应用alpha
    
    将黑白遮罩图作为alpha通道应用到原图
    图片大小以原图为准
    """
    # 读取图片
    try:
        img_bytes = await image.read()
        mask_bytes = await mask.read()
        img = Image.open(io.BytesIO(img_bytes))
        mask_img = Image.open(io.BytesIO(mask_bytes))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片读取失败: {e}")
    
    # 应用遮罩
    result = apply_mask_as_alpha(img, mask_img, invert_mask=invert)
    
    # 返回PNG
    png_bytes = image_to_bytes(result)
    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=result.png"}
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/ui")
async def serve_ui():
    """提供Web测试界面"""
    html_path = SCRIPT_DIR / "index.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="UI页面未找到")


# =============================================================================
# 主程序入口
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="图片Alpha计算服务")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务地址")
    parser.add_argument("--port", type=int, default=5000, help="服务端口")
    args = parser.parse_args()
    
    host_display = "localhost" if args.host == "0.0.0.0" else args.host
    
    print("=" * 60)
    print("📷 图片Alpha计算服务")
    print("=" * 60)
    print(f"🌐 服务地址: http://{host_display}:{args.port}")
    print(f"🎨 测试界面: http://{host_display}:{args.port}/ui")
    print(f"📖 API文档:  http://{host_display}:{args.port}/docs")
    print("=" * 60)
    print("\n可用接口:")
    print("  GET  /ui               - Web测试界面")
    print("  POST /api/alpha/single - 单图+背景色计算alpha")
    print("  POST /api/alpha/dual   - 双图+背景色计算alpha")
    print("  POST /api/alpha/mask   - 原图+遮罩图应用alpha")
    print("=" * 60)
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

