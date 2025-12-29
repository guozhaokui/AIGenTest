"""
DINOv3 可视化服务
提供网页界面展示 DINO 的核心能力：
1. 自注意力语义分割
2. Patch 相似性可视化
3. Patch-to-Patch 局部匹配
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
from io import BytesIO
import base64
from typing import Optional
import colorsys

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 模型路径
MODEL_PATH = "/mnt/hdd/guo/AIGenTest/aiserver/models/facebook/dinov3-vit7b16-pretrain-lvd1689m"

# 全局变量
model = None
processor = None

app = FastAPI(title="DINOv3 Visualization Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_model():
    """加载 DINOv3 模型（INT8 量化）"""
    global model, processor
    
    from transformers import AutoImageProcessor, AutoModel, BitsAndBytesConfig
    
    print(f"正在加载 DINOv3-7B 模型（INT8 量化）...")
    
    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
    )
    
    processor = AutoImageProcessor.from_pretrained(MODEL_PATH)
    model = AutoModel.from_pretrained(
        MODEL_PATH,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    
    if torch.cuda.is_available():
        memory = torch.cuda.memory_allocated() / 1024**3
        print(f"✓ 模型加载完成，显存占用: {memory:.2f} GB")


def image_to_base64(image: Image.Image, format: str = "PNG") -> str:
    """将 PIL Image 转换为 base64"""
    buffer = BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode()


def base64_to_image(b64: str) -> Image.Image:
    """将 base64 转换为 PIL Image"""
    if ',' in b64:
        b64 = b64.split(',')[1]
    image_data = base64.b64decode(b64)
    return Image.open(BytesIO(image_data)).convert('RGB')


def get_patch_features(image: Image.Image) -> tuple:
    """提取 patch 特征"""
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        all_features = outputs.last_hidden_state[0]
        patch_features = all_features[1:]
    
    num_patches = patch_features.shape[0]
    grid_h = grid_w = int(np.sqrt(num_patches))
    if grid_h * grid_w != num_patches:
        for h in range(int(np.sqrt(num_patches)) + 5, 0, -1):
            if num_patches % h == 0:
                grid_h = h
                grid_w = num_patches // h
                break
    
    features = patch_features.float().cpu().numpy()
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    features = features / (norms + 1e-8)
    
    return features, (grid_h, grid_w)


def get_attention_map(image: Image.Image) -> tuple:
    """
    获取自注意力图
    
    注意：某些 attention 实现（如 flash attention）不支持 output_attentions
    这种情况下，我们使用 CLS token 与各 patch 的相似度作为替代
    """
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        try:
            # 尝试获取真正的注意力权重
            outputs = model(**inputs, output_attentions=True)
            if outputs.attentions is not None and len(outputs.attentions) > 0:
                attentions = outputs.attentions[-1]
                # CLS token (位置0) 对所有 patches 的注意力
                cls_attention = attentions[0, :, 0, 1:].mean(dim=0)
            else:
                raise ValueError("No attentions available")
        except Exception as e:
            print(f"无法获取注意力权重: {e}")
            print("使用 CLS-Patch 相似度作为替代...")
            
            # 替代方案：使用 CLS token 与各 patch 的余弦相似度
            outputs = model(**inputs)
            all_features = outputs.last_hidden_state[0]
            cls_feature = all_features[0]  # CLS token
            patch_features = all_features[1:]  # Patch tokens
            
            # 归一化
            cls_feature = cls_feature / cls_feature.norm()
            patch_features = patch_features / patch_features.norm(dim=1, keepdim=True)
            
            # 计算相似度
            cls_attention = (patch_features @ cls_feature).squeeze()
    
    num_patches = cls_attention.shape[0]
    grid_h = grid_w = int(np.sqrt(num_patches))
    if grid_h * grid_w != num_patches:
        for h in range(int(np.sqrt(num_patches)) + 5, 0, -1):
            if num_patches % h == 0:
                grid_h = h
                grid_w = num_patches // h
                break
    
    attention_map = cls_attention.float().cpu().numpy().reshape(grid_h, grid_w)
    return attention_map, (grid_h, grid_w)


def heatmap_to_rgb(heatmap: np.ndarray, colormap: str = "hot") -> np.ndarray:
    """将热力图转换为 RGB 图像"""
    # 归一化
    heatmap = (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min() + 1e-8)
    
    # 使用 matplotlib colormap
    import matplotlib.cm as cm
    if colormap == "hot":
        cmap = cm.hot
    elif colormap == "viridis":
        cmap = cm.viridis
    elif colormap == "jet":
        cmap = cm.jet
    else:
        cmap = cm.hot
    
    rgb = cmap(heatmap)[:, :, :3]
    return (rgb * 255).astype(np.uint8)


def overlay_heatmap(image: Image.Image, heatmap: np.ndarray, alpha: float = 0.5, colormap: str = "hot") -> Image.Image:
    """将热力图叠加到图像上"""
    # 将热力图 resize 到图像大小
    heatmap_rgb = heatmap_to_rgb(heatmap, colormap)
    heatmap_img = Image.fromarray(heatmap_rgb).resize(image.size, Image.BILINEAR)
    
    # 混合
    result = Image.blend(image, heatmap_img, alpha)
    return result


# ==================== API 端点 ====================

class ImageRequest(BaseModel):
    image_base64: str


class PatchSimilarityRequest(BaseModel):
    image_base64: str
    patch_x: int
    patch_y: int


class PatchMatchRequest(BaseModel):
    query_base64: str
    gallery_base64: str


@app.on_event("startup")
async def startup():
    load_model()


@app.get("/health")
def health():
    memory = 0
    if torch.cuda.is_available():
        memory = torch.cuda.memory_allocated() / 1024**3
    return {
        "status": "ok",
        "model": "DINOv3-7B (INT8)",
        "memory_gb": round(memory, 2)
    }


@app.post("/api/attention")
async def get_attention(req: ImageRequest):
    """
    获取自注意力分割图
    """
    try:
        image = base64_to_image(req.image_base64)
        
        # 获取注意力图
        attention_map, grid_size = get_attention_map(image)
        
        # 生成叠加图
        overlay = overlay_heatmap(image, attention_map, alpha=0.5, colormap="viridis")
        
        # 生成纯热力图
        heatmap_rgb = heatmap_to_rgb(attention_map, "viridis")
        heatmap_img = Image.fromarray(heatmap_rgb).resize(image.size, Image.BILINEAR)
        
        return {
            "original": image_to_base64(image),
            "heatmap": image_to_base64(heatmap_img),
            "overlay": image_to_base64(overlay),
            "grid_size": grid_size,
            "stats": {
                "min": float(attention_map.min()),
                "max": float(attention_map.max()),
                "mean": float(attention_map.mean())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/patch_similarity")
async def get_patch_similarity(req: PatchSimilarityRequest):
    """
    获取 Patch 相似性图
    选择一个 patch，显示所有与它相似的位置
    """
    try:
        image = base64_to_image(req.image_base64)
        
        # 提取 patch 特征
        patches, grid_size = get_patch_features(image)
        
        # 验证位置
        if req.patch_x >= grid_size[1] or req.patch_y >= grid_size[0]:
            raise HTTPException(status_code=400, detail=f"位置超出范围，网格大小: {grid_size}")
        
        # 获取查询 patch
        query_idx = req.patch_y * grid_size[1] + req.patch_x
        query_patch = patches[query_idx]
        
        # 计算相似度
        similarities = patches @ query_patch
        similarity_map = similarities.reshape(grid_size)
        
        # 生成叠加图
        overlay = overlay_heatmap(image, similarity_map, alpha=0.5, colormap="hot")
        
        # 生成纯热力图
        heatmap_rgb = heatmap_to_rgb(similarity_map, "hot")
        heatmap_img = Image.fromarray(heatmap_rgb).resize(image.size, Image.BILINEAR)
        
        return {
            "original": image_to_base64(image),
            "heatmap": image_to_base64(heatmap_img),
            "overlay": image_to_base64(overlay),
            "grid_size": grid_size,
            "query_position": [req.patch_x, req.patch_y],
            "stats": {
                "min": float(similarity_map.min()),
                "max": float(similarity_map.max()),
                "query_value": float(similarity_map[req.patch_y, req.patch_x])
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/patch_match")
async def patch_to_patch_match(req: PatchMatchRequest):
    """
    Patch-to-Patch 局部匹配
    在目标图中找到与查询图最匹配的位置
    """
    try:
        query = base64_to_image(req.query_base64)
        gallery = base64_to_image(req.gallery_base64)
        
        # 提取两张图的 patch 特征
        query_patches, query_grid = get_patch_features(query)
        gallery_patches, gallery_grid = get_patch_features(gallery)
        
        # 计算相似度矩阵
        similarity_matrix = query_patches @ gallery_patches.T
        
        # 对于目标图的每个 patch，找到查询图中最匹配的分数
        max_similarity = similarity_matrix.max(axis=0)
        heatmap = max_similarity.reshape(gallery_grid)
        
        # 找最佳位置
        best_idx = np.argmax(heatmap)
        best_y, best_x = divmod(best_idx, gallery_grid[1])
        
        # 生成叠加图
        overlay = overlay_heatmap(gallery, heatmap, alpha=0.5, colormap="hot")
        
        # 生成纯热力图
        heatmap_rgb = heatmap_to_rgb(heatmap, "hot")
        heatmap_img = Image.fromarray(heatmap_rgb).resize(gallery.size, Image.BILINEAR)
        
        return {
            "query": image_to_base64(query),
            "gallery": image_to_base64(gallery),
            "heatmap": image_to_base64(heatmap_img),
            "overlay": image_to_base64(overlay),
            "query_grid": query_grid,
            "gallery_grid": gallery_grid,
            "best_match": {
                "x": int(best_x),
                "y": int(best_y),
                "score": float(heatmap[best_y, best_x])
            },
            "stats": {
                "min": float(heatmap.min()),
                "max": float(heatmap.max()),
                "mean": float(heatmap.mean())
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/get_grid_size")
async def get_grid_size(req: ImageRequest):
    """获取图片的 patch 网格大小"""
    try:
        image = base64_to_image(req.image_base64)
        patches, grid_size = get_patch_features(image)
        return {
            "grid_size": grid_size,
            "num_patches": patches.shape[0],
            "feature_dim": patches.shape[1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 前端页面 ====================

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DINOv3 可视化</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #e8e8e8;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.3);
            padding: 20px;
            text-align: center;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .header h1 {
            font-size: 28px;
            font-weight: 300;
            color: #00d4ff;
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        }
        
        .header p {
            color: #888;
            margin-top: 8px;
        }
        
        .tabs {
            display: flex;
            justify-content: center;
            gap: 10px;
            padding: 20px;
            background: rgba(0, 0, 0, 0.2);
        }
        
        .tab {
            padding: 12px 24px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            color: #ccc;
        }
        
        .tab:hover {
            background: rgba(255, 255, 255, 0.15);
        }
        
        .tab.active {
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: white;
            border-color: transparent;
            box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px;
        }
        
        .panel {
            display: none;
        }
        
        .panel.active {
            display: block;
        }
        
        .upload-area {
            border: 2px dashed rgba(255, 255, 255, 0.3);
            border-radius: 12px;
            padding: 40px;
            text-align: center;
            margin-bottom: 20px;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .upload-area:hover {
            border-color: #00d4ff;
            background: rgba(0, 212, 255, 0.1);
        }
        
        .upload-area.dragover {
            border-color: #00d4ff;
            background: rgba(0, 212, 255, 0.2);
        }
        
        .upload-area input[type="file"] {
            display: none;
        }
        
        .upload-area .icon {
            font-size: 48px;
            margin-bottom: 15px;
        }
        
        .results {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .result-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .result-card h3 {
            padding: 15px;
            background: rgba(0, 0, 0, 0.3);
            font-size: 14px;
            font-weight: 500;
            color: #00d4ff;
        }
        
        .result-card img {
            width: 100%;
            display: block;
            cursor: pointer;
        }
        
        .result-card .stats {
            padding: 12px 15px;
            font-size: 12px;
            color: #888;
            background: rgba(0, 0, 0, 0.2);
        }
        
        .btn {
            padding: 12px 24px;
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            border: none;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 15px rgba(0, 212, 255, 0.4);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        
        .loading.show {
            display: block;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 3px solid rgba(255, 255, 255, 0.1);
            border-top-color: #00d4ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .grid-info {
            background: rgba(0, 0, 0, 0.3);
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
        }
        
        .grid-info.show {
            display: block;
        }
        
        .clickable-image {
            position: relative;
            cursor: crosshair;
        }
        
        .click-marker {
            position: absolute;
            width: 20px;
            height: 20px;
            border: 3px solid #ff0000;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            pointer-events: none;
            box-shadow: 0 0 10px rgba(255, 0, 0, 0.5);
        }
        
        .dual-upload {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        
        @media (max-width: 768px) {
            .dual-upload {
                grid-template-columns: 1fr;
            }
        }
        
        .preview-container {
            position: relative;
            margin-top: 15px;
        }
        
        .preview-container img {
            max-width: 100%;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔬 DINOv3 可视化</h1>
        <p>探索 DINOv3 的自注意力分割、Patch 相似性、局部匹配能力</p>
    </div>
    
    <div class="tabs">
        <div class="tab active" data-tab="attention">自注意力分割</div>
        <div class="tab" data-tab="similarity">Patch 相似性</div>
        <div class="tab" data-tab="match">局部匹配</div>
    </div>
    
    <div class="container">
        <!-- 自注意力分割 -->
        <div class="panel active" id="attention-panel">
            <div class="upload-area" id="attention-upload">
                <div class="icon">📷</div>
                <p>点击或拖拽上传图片</p>
                <p style="color: #666; margin-top: 8px;">DINO 的自注意力会自动形成语义分割</p>
                <input type="file" accept="image/*" id="attention-file">
            </div>
            
            <div class="loading" id="attention-loading">
                <div class="spinner"></div>
                <p>正在分析...</p>
            </div>
            
            <div class="results" id="attention-results"></div>
        </div>
        
        <!-- Patch 相似性 -->
        <div class="panel" id="similarity-panel">
            <div class="upload-area" id="similarity-upload">
                <div class="icon">🎯</div>
                <p>点击或拖拽上传图片</p>
                <p style="color: #666; margin-top: 8px;">上传后点击图片选择一个位置，查看相似区域</p>
                <input type="file" accept="image/*" id="similarity-file">
            </div>
            
            <div class="grid-info" id="similarity-grid-info">
                <strong>网格大小:</strong> <span id="grid-size-text">-</span> |
                <strong>点击位置:</strong> <span id="click-pos-text">-</span>
            </div>
            
            <div class="preview-container" id="similarity-preview" style="display: none;">
                <div class="clickable-image" id="clickable-container">
                    <img id="similarity-image" src="">
                    <div class="click-marker" id="click-marker" style="display: none;"></div>
                </div>
            </div>
            
            <div class="loading" id="similarity-loading">
                <div class="spinner"></div>
                <p>正在分析...</p>
            </div>
            
            <div class="results" id="similarity-results"></div>
        </div>
        
        <!-- 局部匹配 -->
        <div class="panel" id="match-panel">
            <div class="dual-upload">
                <div class="upload-area" id="query-upload">
                    <div class="icon">🔍</div>
                    <p>上传查询图（局部）</p>
                    <input type="file" accept="image/*" id="query-file">
                    <div class="preview-container" id="query-preview"></div>
                </div>
                <div class="upload-area" id="gallery-upload">
                    <div class="icon">🖼️</div>
                    <p>上传目标图（完整）</p>
                    <input type="file" accept="image/*" id="gallery-file">
                    <div class="preview-container" id="gallery-preview"></div>
                </div>
            </div>
            
            <div style="text-align: center; margin-top: 20px;">
                <button class="btn" id="match-btn" disabled>开始匹配</button>
            </div>
            
            <div class="loading" id="match-loading">
                <div class="spinner"></div>
                <p>正在匹配...</p>
            </div>
            
            <div class="results" id="match-results"></div>
        </div>
    </div>

    <script>
        // Tab 切换
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + '-panel').classList.add('active');
            });
        });

        // 通用文件上传处理
        function setupUpload(uploadAreaId, fileInputId, callback) {
            const area = document.getElementById(uploadAreaId);
            const input = document.getElementById(fileInputId);
            
            area.addEventListener('click', (e) => {
                if (e.target.tagName !== 'INPUT') {
                    input.click();
                }
            });
            
            area.addEventListener('dragover', (e) => {
                e.preventDefault();
                area.classList.add('dragover');
            });
            
            area.addEventListener('dragleave', () => {
                area.classList.remove('dragover');
            });
            
            area.addEventListener('drop', (e) => {
                e.preventDefault();
                area.classList.remove('dragover');
                const file = e.dataTransfer.files[0];
                if (file && file.type.startsWith('image/')) {
                    callback(file);
                }
            });
            
            input.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (file) callback(file);
            });
        }

        function fileToBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsDataURL(file);
            });
        }

        // ==================== 自注意力分割 ====================
        setupUpload('attention-upload', 'attention-file', async (file) => {
            const base64 = await fileToBase64(file);
            
            document.getElementById('attention-loading').classList.add('show');
            document.getElementById('attention-results').innerHTML = '';
            
            try {
                const response = await fetch('/api/attention', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_base64: base64 })
                });
                
                const data = await response.json();
                
                document.getElementById('attention-results').innerHTML = `
                    <div class="result-card">
                        <h3>原始图片</h3>
                        <img src="data:image/png;base64,${data.original}">
                    </div>
                    <div class="result-card">
                        <h3>自注意力热力图</h3>
                        <img src="data:image/png;base64,${data.heatmap}">
                        <div class="stats">网格: ${data.grid_size[0]}×${data.grid_size[1]}</div>
                    </div>
                    <div class="result-card">
                        <h3>叠加效果</h3>
                        <img src="data:image/png;base64,${data.overlay}">
                        <div class="stats">Min: ${data.stats.min.toFixed(4)} | Max: ${data.stats.max.toFixed(4)}</div>
                    </div>
                `;
            } catch (e) {
                alert('分析失败: ' + e.message);
            }
            
            document.getElementById('attention-loading').classList.remove('show');
        });

        // ==================== Patch 相似性 ====================
        let similarityImageBase64 = null;
        let gridSize = null;

        setupUpload('similarity-upload', 'similarity-file', async (file) => {
            similarityImageBase64 = await fileToBase64(file);
            
            // 显示预览
            const img = document.getElementById('similarity-image');
            img.src = similarityImageBase64;
            document.getElementById('similarity-preview').style.display = 'block';
            document.getElementById('click-marker').style.display = 'none';
            document.getElementById('similarity-results').innerHTML = '';
            
            // 获取网格大小
            try {
                const response = await fetch('/api/get_grid_size', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image_base64: similarityImageBase64 })
                });
                const data = await response.json();
                gridSize = data.grid_size;
                document.getElementById('grid-size-text').textContent = `${gridSize[0]}×${gridSize[1]}`;
                document.getElementById('similarity-grid-info').classList.add('show');
            } catch (e) {
                console.error(e);
            }
        });

        // 点击图片选择 patch
        document.getElementById('clickable-container').addEventListener('click', async (e) => {
            if (!similarityImageBase64 || !gridSize) return;
            
            const img = document.getElementById('similarity-image');
            const rect = img.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // 计算 patch 位置
            const patchX = Math.floor(x / rect.width * gridSize[1]);
            const patchY = Math.floor(y / rect.height * gridSize[0]);
            
            // 显示标记
            const marker = document.getElementById('click-marker');
            marker.style.left = x + 'px';
            marker.style.top = y + 'px';
            marker.style.display = 'block';
            
            document.getElementById('click-pos-text').textContent = `(${patchX}, ${patchY})`;
            
            // 请求相似性分析
            document.getElementById('similarity-loading').classList.add('show');
            
            try {
                const response = await fetch('/api/patch_similarity', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        image_base64: similarityImageBase64,
                        patch_x: patchX,
                        patch_y: patchY
                    })
                });
                
                const data = await response.json();
                
                document.getElementById('similarity-results').innerHTML = `
                    <div class="result-card">
                        <h3>相似性热力图</h3>
                        <img src="data:image/png;base64,${data.heatmap}">
                        <div class="stats">查询位置相似度: ${data.stats.query_value.toFixed(4)}</div>
                    </div>
                    <div class="result-card">
                        <h3>叠加效果</h3>
                        <img src="data:image/png;base64,${data.overlay}">
                        <div class="stats">Min: ${data.stats.min.toFixed(4)} | Max: ${data.stats.max.toFixed(4)}</div>
                    </div>
                `;
            } catch (e) {
                alert('分析失败: ' + e.message);
            }
            
            document.getElementById('similarity-loading').classList.remove('show');
        });

        // ==================== 局部匹配 ====================
        let queryBase64 = null;
        let galleryBase64 = null;

        setupUpload('query-upload', 'query-file', async (file) => {
            queryBase64 = await fileToBase64(file);
            document.getElementById('query-preview').innerHTML = 
                `<img src="${queryBase64}" style="max-height: 150px; border-radius: 8px;">`;
            updateMatchButton();
        });

        setupUpload('gallery-upload', 'gallery-file', async (file) => {
            galleryBase64 = await fileToBase64(file);
            document.getElementById('gallery-preview').innerHTML = 
                `<img src="${galleryBase64}" style="max-height: 150px; border-radius: 8px;">`;
            updateMatchButton();
        });

        function updateMatchButton() {
            document.getElementById('match-btn').disabled = !(queryBase64 && galleryBase64);
        }

        document.getElementById('match-btn').addEventListener('click', async () => {
            if (!queryBase64 || !galleryBase64) return;
            
            document.getElementById('match-loading').classList.add('show');
            document.getElementById('match-results').innerHTML = '';
            
            try {
                const response = await fetch('/api/patch_match', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query_base64: queryBase64,
                        gallery_base64: galleryBase64
                    })
                });
                
                const data = await response.json();
                
                document.getElementById('match-results').innerHTML = `
                    <div class="result-card">
                        <h3>查询图 (${data.query_grid[0]}×${data.query_grid[1]})</h3>
                        <img src="data:image/png;base64,${data.query}">
                    </div>
                    <div class="result-card">
                        <h3>目标图 (${data.gallery_grid[0]}×${data.gallery_grid[1]})</h3>
                        <img src="data:image/png;base64,${data.gallery}">
                    </div>
                    <div class="result-card">
                        <h3>匹配热力图</h3>
                        <img src="data:image/png;base64,${data.heatmap}">
                        <div class="stats">最佳匹配: (${data.best_match.x}, ${data.best_match.y}) 分数: ${data.best_match.score.toFixed(4)}</div>
                    </div>
                    <div class="result-card">
                        <h3>叠加效果</h3>
                        <img src="data:image/png;base64,${data.overlay}">
                        <div class="stats">Min: ${data.stats.min.toFixed(4)} | Max: ${data.stats.max.toFixed(4)}</div>
                    </div>
                `;
            } catch (e) {
                alert('匹配失败: ' + e.message);
            }
            
            document.getElementById('match-loading').classList.remove('show');
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_CONTENT


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 6020
    print(f"启动 DINOv3 可视化服务，端口: {port}")
    print(f"访问 http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port)

