"""
局部图片匹配可视化服务
用于展示局部图片与完整图片各个 patch 的匹配度
"""
import torch
import numpy as np
from PIL import Image
from io import BytesIO
import base64
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

# 尝试导入 SigLIP2
try:
    from transformers import AutoModel, AutoProcessor
    SIGLIP_AVAILABLE = True
except ImportError:
    SIGLIP_AVAILABLE = False
    print("Warning: transformers not available, using mock features")

app = FastAPI(title="Patch Match Visualization")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局模型
model = None
processor = None
MODEL_PATH = "/mnt/hdd/models/siglip2-so400m-patch16-512"


def load_model():
    """加载 SigLIP2 模型"""
    global model, processor
    if not SIGLIP_AVAILABLE:
        return
    
    print(f"Loading SigLIP2 from {MODEL_PATH}...")
    processor = AutoProcessor.from_pretrained(MODEL_PATH)
    model = AutoModel.from_pretrained(MODEL_PATH, torch_dtype=torch.bfloat16)
    model.to("cuda")
    model.eval()
    print("Model loaded.")


def get_image_embedding(image: Image.Image) -> np.ndarray:
    """获取图片的全局嵌入"""
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model.get_image_features(**inputs)
    
    embedding = outputs[0].float().cpu().numpy()
    embedding = embedding / np.linalg.norm(embedding)
    return embedding


def get_patch_embeddings(image: Image.Image, patch_size: int) -> tuple:
    """
    将图片分成 patches 并计算每个 patch 的嵌入
    
    Returns:
        embeddings: [num_patches, dim] 每个 patch 的嵌入
        grid_shape: (rows, cols) patch 网格形状
    """
    w, h = image.size
    
    # 计算 patch 网格
    cols = w // patch_size
    rows = h // patch_size
    
    if cols == 0 or rows == 0:
        raise ValueError(f"Patch size {patch_size} too large for image {w}x{h}")
    
    patches = []
    for row in range(rows):
        for col in range(cols):
            x1 = col * patch_size
            y1 = row * patch_size
            x2 = x1 + patch_size
            y2 = y1 + patch_size
            patch = image.crop((x1, y1, x2, y2))
            patches.append(patch)
    
    # 批量计算嵌入
    embeddings = []
    batch_size = 16
    
    for i in range(0, len(patches), batch_size):
        batch = patches[i:i+batch_size]
        inputs = processor(images=batch, return_tensors="pt")
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = model.get_image_features(**inputs)
        
        batch_emb = outputs.float().cpu().numpy()
        # 归一化
        norms = np.linalg.norm(batch_emb, axis=1, keepdims=True)
        batch_emb = batch_emb / norms
        embeddings.append(batch_emb)
    
    embeddings = np.concatenate(embeddings, axis=0)
    return embeddings, (rows, cols)


class MatchRequest(BaseModel):
    """匹配请求"""
    partial_image: str  # base64 编码的局部图片
    full_image: str     # base64 编码的完整图片
    patch_size: int = 64  # patch 大小（像素）


@app.on_event("startup")
async def startup():
    load_model()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": model is not None
    }


@app.post("/api/match")
async def compute_match(req: MatchRequest):
    """
    计算局部图片与完整图片各个 patch 的匹配度
    
    Returns:
        similarity_map: 2D 相似度矩阵 (rows x cols)
        grid_shape: [rows, cols]
        stats: 统计信息
    """
    try:
        # 解码图片
        partial_data = base64.b64decode(req.partial_image)
        full_data = base64.b64decode(req.full_image)
        
        partial_img = Image.open(BytesIO(partial_data)).convert("RGB")
        full_img = Image.open(BytesIO(full_data)).convert("RGB")
        
        # 获取局部图片的嵌入
        partial_emb = get_image_embedding(partial_img)
        
        # 获取完整图片各个 patch 的嵌入
        patch_embs, grid_shape = get_patch_embeddings(full_img, req.patch_size)
        
        # 计算相似度
        similarities = patch_embs @ partial_emb  # [num_patches]
        
        # 重塑为 2D
        similarity_map = similarities.reshape(grid_shape)
        
        # 归一化到 0-1 范围（用于可视化）
        min_sim = similarity_map.min()
        max_sim = similarity_map.max()
        if max_sim > min_sim:
            normalized_map = (similarity_map - min_sim) / (max_sim - min_sim)
        else:
            normalized_map = np.zeros_like(similarity_map)
        
        return JSONResponse(content={
            "similarity_map": normalized_map.tolist(),
            "raw_similarity_map": similarity_map.tolist(),
            "grid_shape": list(grid_shape),
            "patch_size": req.patch_size,
            "full_image_size": [full_img.width, full_img.height],
            "stats": {
                "min": float(min_sim),
                "max": float(max_sim),
                "mean": float(similarity_map.mean()),
                "std": float(similarity_map.std())
            }
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def index():
    """返回前端页面"""
    return HTML_PAGE


# 前端 HTML 页面
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Patch Match Visualization</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        h1 {
            text-align: center;
            color: #00d4ff;
            margin-bottom: 30px;
            font-size: 2rem;
            text-shadow: 0 0 20px rgba(0, 212, 255, 0.3);
        }
        
        .panels {
            display: grid;
            grid-template-columns: 300px 1fr;
            gap: 20px;
        }
        
        .control-panel {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .control-group {
            margin-bottom: 20px;
        }
        
        .control-group label {
            display: block;
            margin-bottom: 8px;
            color: #aaa;
            font-size: 0.9rem;
        }
        
        .upload-area {
            border: 2px dashed rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: rgba(0, 0, 0, 0.2);
        }
        
        .upload-area:hover {
            border-color: #00d4ff;
            background: rgba(0, 212, 255, 0.05);
        }
        
        .upload-area.has-image {
            padding: 10px;
        }
        
        .upload-area img {
            max-width: 100%;
            max-height: 150px;
            border-radius: 8px;
        }
        
        input[type="file"] {
            display: none;
        }
        
        input[type="range"] {
            width: 100%;
            margin: 10px 0;
        }
        
        .value-display {
            text-align: center;
            font-size: 1.2rem;
            color: #00d4ff;
            font-weight: bold;
        }
        
        button {
            width: 100%;
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            cursor: pointer;
            transition: all 0.3s;
            margin-bottom: 10px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 212, 255, 0.4);
        }
        
        .btn-primary:disabled {
            background: #555;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        .btn-toggle {
            background: rgba(255, 100, 100, 0.3);
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
        }
        
        .btn-toggle.active {
            background: rgba(255, 100, 100, 0.6);
        }
        
        .result-panel {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .image-container {
            position: relative;
            display: inline-block;
            max-width: 100%;
        }
        
        .image-container img {
            max-width: 100%;
            display: block;
            border-radius: 8px;
        }
        
        .heatmap-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            transition: opacity 0.3s;
        }
        
        .heatmap-overlay.hidden {
            opacity: 0;
        }
        
        .stats-panel {
            margin-top: 20px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            text-align: center;
        }
        
        .stat-item {
            padding: 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 8px;
        }
        
        .stat-value {
            font-size: 1.2rem;
            color: #00d4ff;
            font-weight: bold;
        }
        
        .stat-label {
            font-size: 0.8rem;
            color: #888;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }
        
        .loading.active {
            display: block;
        }
        
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid rgba(0, 212, 255, 0.3);
            border-top-color: #00d4ff;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        
        .empty-state svg {
            width: 80px;
            height: 80px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Patch Match Visualization</h1>
        
        <div class="panels">
            <div class="control-panel">
                <div class="control-group">
                    <label>局部图片（查询图）</label>
                    <div class="upload-area" id="partialUpload" onclick="document.getElementById('partialInput').click()">
                        <div class="placeholder">点击选择图片</div>
                    </div>
                    <input type="file" id="partialInput" accept="image/*" onchange="handleImageUpload(this, 'partial')">
                </div>
                
                <div class="control-group">
                    <label>完整图片（搜索目标）</label>
                    <div class="upload-area" id="fullUpload" onclick="document.getElementById('fullInput').click()">
                        <div class="placeholder">点击选择图片</div>
                    </div>
                    <input type="file" id="fullInput" accept="image/*" onchange="handleImageUpload(this, 'full')">
                </div>
                
                <div class="control-group">
                    <label>Patch 大小（像素）</label>
                    <input type="range" id="patchSize" min="16" max="256" value="64" step="16" 
                           oninput="updatePatchSizeDisplay()">
                    <div class="value-display" id="patchSizeValue">64 px</div>
                </div>
                
                <button class="btn-primary" id="matchBtn" onclick="computeMatch()" disabled>
                    计算匹配
                </button>
                
                <button class="btn-toggle" id="toggleBtn" onclick="toggleHeatmap()" style="display: none;">
                    显示/隐藏热力图
                </button>
            </div>
            
            <div class="result-panel">
                <div class="empty-state" id="emptyState">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1">
                        <path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                    </svg>
                    <p>上传局部图片和完整图片开始匹配</p>
                </div>
                
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    <p>正在计算匹配度...</p>
                </div>
                
                <div id="resultContainer" style="display: none;">
                    <div class="image-container" id="imageContainer">
                        <img id="fullImageDisplay" src="" alt="Full Image">
                        <canvas id="heatmapCanvas" class="heatmap-overlay"></canvas>
                    </div>
                    
                    <div class="stats-panel">
                        <div class="stats-grid">
                            <div class="stat-item">
                                <div class="stat-value" id="statMin">-</div>
                                <div class="stat-label">最小相似度</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value" id="statMax">-</div>
                                <div class="stat-label">最大相似度</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value" id="statMean">-</div>
                                <div class="stat-label">平均相似度</div>
                            </div>
                            <div class="stat-item">
                                <div class="stat-value" id="statPatches">-</div>
                                <div class="stat-label">Patch 数量</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let partialImageData = null;
        let fullImageData = null;
        let heatmapVisible = true;
        
        function handleImageUpload(input, type) {
            const file = input.files[0];
            if (!file) return;
            
            const reader = new FileReader();
            reader.onload = function(e) {
                const base64 = e.target.result.split(',')[1];
                const uploadArea = document.getElementById(type + 'Upload');
                
                if (type === 'partial') {
                    partialImageData = base64;
                } else {
                    fullImageData = base64;
                }
                
                // 显示预览
                uploadArea.innerHTML = `<img src="${e.target.result}" alt="${type}">`;
                uploadArea.classList.add('has-image');
                
                // 检查是否可以开始匹配
                checkMatchReady();
            };
            reader.readAsDataURL(file);
        }
        
        function checkMatchReady() {
            const btn = document.getElementById('matchBtn');
            btn.disabled = !(partialImageData && fullImageData);
        }
        
        function updatePatchSizeDisplay() {
            const value = document.getElementById('patchSize').value;
            document.getElementById('patchSizeValue').textContent = value + ' px';
        }
        
        async function computeMatch() {
            if (!partialImageData || !fullImageData) return;
            
            // 显示加载状态
            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('loading').classList.add('active');
            document.getElementById('resultContainer').style.display = 'none';
            
            try {
                const response = await fetch('/api/match', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        partial_image: partialImageData,
                        full_image: fullImageData,
                        patch_size: parseInt(document.getElementById('patchSize').value)
                    })
                });
                
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                
                const result = await response.json();
                displayResult(result);
                
            } catch (error) {
                alert('匹配失败: ' + error.message);
            } finally {
                document.getElementById('loading').classList.remove('active');
            }
        }
        
        function displayResult(result) {
            // 显示完整图片
            const fullImg = document.getElementById('fullImageDisplay');
            fullImg.src = 'data:image/jpeg;base64,' + fullImageData;
            
            // 等待图片加载完成后绘制热力图
            fullImg.onload = function() {
                drawHeatmap(result.similarity_map, result.grid_shape, result.patch_size, 
                           fullImg.naturalWidth, fullImg.naturalHeight,
                           fullImg.width, fullImg.height);
            };
            
            // 更新统计
            document.getElementById('statMin').textContent = result.stats.min.toFixed(3);
            document.getElementById('statMax').textContent = result.stats.max.toFixed(3);
            document.getElementById('statMean').textContent = result.stats.mean.toFixed(3);
            document.getElementById('statPatches').textContent = 
                result.grid_shape[0] + ' × ' + result.grid_shape[1];
            
            // 显示结果容器和切换按钮
            document.getElementById('resultContainer').style.display = 'block';
            document.getElementById('toggleBtn').style.display = 'block';
            heatmapVisible = true;
        }
        
        function drawHeatmap(similarityMap, gridShape, patchSize, 
                            naturalWidth, naturalHeight, displayWidth, displayHeight) {
            const canvas = document.getElementById('heatmapCanvas');
            const ctx = canvas.getContext('2d');
            
            // 设置 canvas 尺寸
            canvas.width = displayWidth;
            canvas.height = displayHeight;
            
            const [rows, cols] = gridShape;
            const scaleX = displayWidth / naturalWidth;
            const scaleY = displayHeight / naturalHeight;
            
            const displayPatchWidth = patchSize * scaleX;
            const displayPatchHeight = patchSize * scaleY;
            
            // 绘制热力图
            for (let row = 0; row < rows; row++) {
                for (let col = 0; col < cols; col++) {
                    const similarity = similarityMap[row][col];
                    
                    // 使用红色通道表示相似度，透明度也随相似度变化
                    const alpha = 0.3 + similarity * 0.5;  // 0.3 - 0.8
                    const red = Math.floor(255 * similarity);
                    
                    ctx.fillStyle = `rgba(${red}, 0, 0, ${alpha})`;
                    ctx.fillRect(
                        col * displayPatchWidth,
                        row * displayPatchHeight,
                        displayPatchWidth,
                        displayPatchHeight
                    );
                    
                    // 绘制 patch 边框
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
                    ctx.strokeRect(
                        col * displayPatchWidth,
                        row * displayPatchHeight,
                        displayPatchWidth,
                        displayPatchHeight
                    );
                }
            }
        }
        
        function toggleHeatmap() {
            const canvas = document.getElementById('heatmapCanvas');
            const btn = document.getElementById('toggleBtn');
            
            heatmapVisible = !heatmapVisible;
            
            if (heatmapVisible) {
                canvas.classList.remove('hidden');
                btn.classList.add('active');
            } else {
                canvas.classList.add('hidden');
                btn.classList.remove('active');
            }
        }
    </script>
</body>
</html>
"""


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=6080)

