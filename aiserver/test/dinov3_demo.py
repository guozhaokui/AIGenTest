"""
DINOv3 INT8 量化 Demo
展示 DINOv3 的核心特性：
1. INT8 量化加载（节省显存）
2. 全局特征提取（CLS token）
3. Patch 特征提取（局部特征）
4. 局部图片匹配（在大图中找小图）
5. 相似度热力图可视化
"""

import torch
import numpy as np
from PIL import Image
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 非交互式后端

# 模型路径
MODEL_PATH = "/mnt/hdd/guo/AIGenTest/aiserver/models/facebook/dinov3-vit7b16-pretrain-lvd1689m"

# 全局变量
model = None
processor = None


def load_model_int8():
    """
    使用 INT8 量化加载 DINOv3-7B 模型
    
    显存占用：~8GB（相比 FP16 的 ~14GB）
    """
    global model, processor
    
    from transformers import AutoImageProcessor, AutoModel, BitsAndBytesConfig
    
    print(f"正在加载 DINOv3-7B 模型（INT8 量化）...")
    print(f"模型路径: {MODEL_PATH}")
    
    # INT8 量化配置
    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
    )
    
    # 加载 processor
    processor = AutoImageProcessor.from_pretrained(MODEL_PATH)
    
    # 加载量化模型
    model = AutoModel.from_pretrained(
        MODEL_PATH,
        quantization_config=quantization_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    
    # 打印显存使用
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated() / 1024**3
        memory_reserved = torch.cuda.memory_reserved() / 1024**3
        print(f"✓ 模型加载完成")
        print(f"  显存占用: {memory_allocated:.2f} GB (已分配)")
        print(f"  显存预留: {memory_reserved:.2f} GB (已预留)")
    
    return model, processor


def get_global_feature(image: Image.Image) -> np.ndarray:
    """
    提取图像的全局特征（CLS token）
    
    用途：以图搜图、图像分类
    
    Args:
        image: PIL Image
    
    Returns:
        归一化的特征向量 (hidden_dim,)
    """
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        # CLS token 是第一个位置
        cls_feature = outputs.last_hidden_state[0, 0]
    
    # 归一化
    feature = cls_feature.float().cpu().numpy()
    feature = feature / np.linalg.norm(feature)
    
    return feature


def get_patch_features(image: Image.Image) -> tuple:
    """
    提取图像的所有 patch 特征
    
    用途：局部匹配、语义分割
    
    Args:
        image: PIL Image
    
    Returns:
        patch_features: (num_patches, hidden_dim) 特征矩阵
        grid_size: (h, w) patch 网格大小
    """
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
        # last_hidden_state: (batch, num_patches+1, hidden_dim)
        # 第一个是 CLS token，后面是各个 patch
        all_features = outputs.last_hidden_state[0]
        patch_features = all_features[1:]  # 去掉 CLS
    
    # 计算 patch 网格大小
    # DINOv3-7B 可能不是正方形网格，需要从 processor 获取
    num_patches = patch_features.shape[0]
    
    # 尝试从 processor 获取图片尺寸信息
    img_size = processor.size.get('height', processor.size.get('shortest_edge', 518))
    patch_size = getattr(model.config, 'patch_size', 16)
    
    # 计算网格大小
    grid_h = grid_w = int(np.sqrt(num_patches))
    
    # 如果不是完美正方形，尝试找到合适的因数
    if grid_h * grid_w != num_patches:
        # 尝试常见的长宽比
        for h in range(int(np.sqrt(num_patches)) + 5, 0, -1):
            if num_patches % h == 0:
                grid_h = h
                grid_w = num_patches // h
                break
    
    print(f"  [Debug] num_patches={num_patches}, grid=({grid_h}, {grid_w})")
    
    # 归一化
    features = patch_features.float().cpu().numpy()
    norms = np.linalg.norm(features, axis=1, keepdims=True)
    features = features / norms
    
    return features, (grid_h, grid_w)


def compute_similarity_heatmap(query_image: Image.Image, gallery_image: Image.Image) -> tuple:
    """
    计算查询图在目标图上的相似度热力图
    
    用途：在大图中定位小图/局部
    
    Args:
        query_image: 查询图片（通常是局部/小图）
        gallery_image: 目标图片（通常是完整/大图）
    
    Returns:
        heatmap: (grid_h, grid_w) 相似度矩阵
        grid_size: (h, w) 网格大小
    """
    # 获取查询图的全局特征
    query_feature = get_global_feature(query_image)
    
    # 获取目标图的所有 patch 特征
    gallery_patches, grid_size = get_patch_features(gallery_image)
    
    # 计算相似度
    similarities = gallery_patches @ query_feature  # (num_patches,)
    
    # 重塑为热力图
    heatmap = similarities.reshape(grid_size)
    
    return heatmap, grid_size


def local_match(query_image: Image.Image, gallery_image: Image.Image) -> dict:
    """
    局部匹配：在目标图中找到与查询图最匹配的位置
    
    Args:
        query_image: 查询图片（局部）
        gallery_image: 目标图片（完整）
    
    Returns:
        {
            'best_score': 最佳匹配分数,
            'best_position': (x, y) 在 patch 网格中的位置,
            'best_position_pixel': (x, y) 在像素坐标中的位置,
            'heatmap': 相似度热力图
        }
    """
    heatmap, grid_size = compute_similarity_heatmap(query_image, gallery_image)
    
    # 找最佳位置
    best_idx = np.argmax(heatmap)
    best_y, best_x = divmod(best_idx, heatmap.shape[1])
    best_score = heatmap[best_y, best_x]
    
    # 转换为像素坐标（假设图片被 resize 到 processor 的目标尺寸）
    img_size = processor.size.get('height', processor.size.get('shortest_edge', 518))
    patch_size_h = img_size // heatmap.shape[0]
    patch_size_w = img_size // heatmap.shape[1]
    
    pixel_x = best_x * patch_size_w + patch_size_w // 2
    pixel_y = best_y * patch_size_h + patch_size_h // 2
    
    return {
        'best_score': float(best_score),
        'best_position': (int(best_x), int(best_y)),
        'best_position_pixel': (int(pixel_x), int(pixel_y)),
        'heatmap': heatmap,
        'grid_size': heatmap.shape
    }


def visualize_heatmap(gallery_image: Image.Image, heatmap: np.ndarray, 
                      save_path: str = None, title: str = "Similarity Heatmap"):
    """
    可视化相似度热力图
    
    Args:
        gallery_image: 目标图片
        heatmap: 相似度热力图
        save_path: 保存路径（可选）
        title: 图片标题
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # 原图
    axes[0].imshow(gallery_image)
    axes[0].set_title("Original Image")
    axes[0].axis('off')
    
    # 热力图
    im = axes[1].imshow(heatmap, cmap='hot', interpolation='nearest')
    axes[1].set_title("Similarity Heatmap")
    axes[1].axis('off')
    plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    
    # 叠加图
    # 将热力图 resize 到图片大小
    heatmap_resized = np.array(Image.fromarray(
        ((heatmap - heatmap.min()) / (heatmap.max() - heatmap.min()) * 255).astype(np.uint8)
    ).resize(gallery_image.size, Image.BILINEAR))
    
    axes[2].imshow(gallery_image)
    axes[2].imshow(heatmap_resized, cmap='hot', alpha=0.5)
    axes[2].set_title("Overlay")
    axes[2].axis('off')
    
    plt.suptitle(title)
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"✓ 可视化已保存到: {save_path}")
    
    plt.close()


def demo_image_similarity():
    """
    Demo 1: 图像相似度计算
    """
    print("\n" + "="*60)
    print("Demo 1: 图像全局特征 & 相似度计算")
    print("="*60)
    
    # 创建测试图片
    img1 = Image.new('RGB', (256, 256), color='red')
    img2 = Image.new('RGB', (256, 256), color='red')
    img3 = Image.new('RGB', (256, 256), color='blue')
    
    # 提取特征
    feat1 = get_global_feature(img1)
    feat2 = get_global_feature(img2)
    feat3 = get_global_feature(img3)
    
    # 计算相似度
    sim_12 = float(feat1 @ feat2)
    sim_13 = float(feat1 @ feat3)
    
    print(f"特征维度: {feat1.shape}")
    print(f"红色图 vs 红色图 相似度: {sim_12:.4f}")
    print(f"红色图 vs 蓝色图 相似度: {sim_13:.4f}")


def demo_patch_features():
    """
    Demo 2: Patch 特征提取
    """
    print("\n" + "="*60)
    print("Demo 2: Patch 特征提取")
    print("="*60)
    
    # 创建一个有不同区域的测试图片
    img = Image.new('RGB', (512, 512))
    pixels = img.load()
    for x in range(512):
        for y in range(512):
            if x < 256 and y < 256:
                pixels[x, y] = (255, 0, 0)  # 左上：红
            elif x >= 256 and y < 256:
                pixels[x, y] = (0, 255, 0)  # 右上：绿
            elif x < 256 and y >= 256:
                pixels[x, y] = (0, 0, 255)  # 左下：蓝
            else:
                pixels[x, y] = (255, 255, 0)  # 右下：黄
    
    # 提取 patch 特征
    patches, grid_size = get_patch_features(img)
    
    print(f"Patch 网格大小: {grid_size}")
    print(f"总 Patch 数量: {patches.shape[0]}")
    print(f"每个 Patch 特征维度: {patches.shape[1]}")
    
    # 计算四个角落 patch 的相似度
    corner_patches = [
        patches[0],  # 左上角
        patches[grid_size[1] - 1],  # 右上角
        patches[(grid_size[0] - 1) * grid_size[1]],  # 左下角
        patches[-1]  # 右下角
    ]
    
    print("\n四个角落 Patch 之间的相似度:")
    labels = ["左上(红)", "右上(绿)", "左下(蓝)", "右下(黄)"]
    for i in range(4):
        for j in range(i+1, 4):
            sim = float(corner_patches[i] @ corner_patches[j])
            print(f"  {labels[i]} vs {labels[j]}: {sim:.4f}")


def demo_local_match():
    """
    Demo 3: 局部匹配
    """
    print("\n" + "="*60)
    print("Demo 3: 局部图片匹配")
    print("="*60)
    
    # 创建目标图（大图，有多个区域）
    gallery = Image.new('RGB', (512, 512), color='gray')
    pixels = gallery.load()
    
    # 在中间偏右上方放一个红色方块
    for x in range(300, 400):
        for y in range(100, 200):
            pixels[x, y] = (255, 0, 0)
    
    # 在左下角放一个蓝色方块
    for x in range(50, 150):
        for y in range(350, 450):
            pixels[x, y] = (0, 0, 255)
    
    # 创建查询图（小图，红色方块）
    query = Image.new('RGB', (128, 128), color=(255, 0, 0))
    
    # 执行局部匹配
    result = local_match(query, gallery)
    
    print(f"查询图: 红色方块 (128x128)")
    print(f"目标图: 灰色背景 + 红色方块(300-400, 100-200) + 蓝色方块(50-150, 350-450)")
    print(f"\n匹配结果:")
    print(f"  最佳分数: {result['best_score']:.4f}")
    print(f"  Patch 位置: {result['best_position']}")
    print(f"  像素位置: {result['best_position_pixel']}")
    print(f"  网格大小: {result['grid_size']}")
    
    # 保存可视化
    output_dir = Path(__file__).parent
    visualize_heatmap(
        gallery, 
        result['heatmap'],
        save_path=str(output_dir / "demo_local_match.png"),
        title="Local Match: Find Red Block"
    )


def demo_with_real_images(image_path1: str = None, image_path2: str = None):
    """
    Demo 4: 使用真实图片
    
    Args:
        image_path1: 查询图片路径
        image_path2: 目标图片路径
    """
    print("\n" + "="*60)
    print("Demo 4: 真实图片局部匹配")
    print("="*60)
    
    if not image_path1 or not image_path2:
        print("请提供两张图片路径")
        print("用法: demo_with_real_images('query.jpg', 'gallery.jpg')")
        return
    
    query = Image.open(image_path1).convert('RGB')
    gallery = Image.open(image_path2).convert('RGB')
    
    print(f"查询图: {image_path1} ({query.size})")
    print(f"目标图: {image_path2} ({gallery.size})")
    
    result = local_match(query, gallery)
    
    print(f"\n匹配结果:")
    print(f"  最佳分数: {result['best_score']:.4f}")
    print(f"  Patch 位置: {result['best_position']}")
    print(f"  像素位置: {result['best_position_pixel']}")
    
    # 保存可视化
    output_dir = Path(__file__).parent
    visualize_heatmap(
        gallery,
        result['heatmap'],
        save_path=str(output_dir / "demo_real_images.png"),
        title=f"Match Score: {result['best_score']:.4f}"
    )


def show_model_info():
    """
    显示模型信息
    """
    print("\n" + "="*60)
    print("DINOv3-7B 模型信息")
    print("="*60)
    
    # 统计参数量
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"模型路径: {MODEL_PATH}")
    print(f"总参数量: {total_params / 1e9:.2f}B")
    print(f"可训练参数: {trainable_params / 1e9:.2f}B")
    print(f"量化方式: INT8")
    
    if torch.cuda.is_available():
        memory = torch.cuda.memory_allocated() / 1024**3
        print(f"显存占用: {memory:.2f} GB")
    
    # 输入输出信息
    print(f"\n输入:")
    print(f"  图片大小: {processor.size}")
    
    # 测试一下输出维度
    test_img = Image.new('RGB', (256, 256))
    feat = get_global_feature(test_img)
    patches, grid = get_patch_features(test_img)
    
    print(f"\n输出:")
    print(f"  全局特征 (CLS): {feat.shape}")
    print(f"  Patch 网格: {grid}")
    print(f"  Patch 特征: {patches.shape}")


def get_attention_map(image: Image.Image) -> np.ndarray:
    """
    获取 CLS token 对所有 patches 的注意力权重
    
    DINO 的核心能力：自注意力图自动形成语义分割！
    
    Returns:
        attention_map: (grid_h, grid_w) 注意力权重图
    """
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    
    with torch.no_grad():
        # 获取注意力权重
        outputs = model(**inputs, output_attentions=True)
        
        # 最后一层的注意力 shape: (batch, num_heads, seq_len, seq_len)
        attentions = outputs.attentions[-1]
        
        # 取所有 head 的平均
        # CLS token (位置0) 对所有 patches 的注意力
        cls_attention = attentions[0, :, 0, 1:].mean(dim=0)  # (num_patches,)
    
    # 计算网格大小
    num_patches = cls_attention.shape[0]
    grid_h = grid_w = int(np.sqrt(num_patches))
    if grid_h * grid_w != num_patches:
        for h in range(int(np.sqrt(num_patches)) + 5, 0, -1):
            if num_patches % h == 0:
                grid_h = h
                grid_w = num_patches // h
                break
    
    attention_map = cls_attention.float().cpu().numpy().reshape(grid_h, grid_w)
    
    return attention_map


def demo_attention_segmentation(image_path: str = None):
    """
    Demo: DINO 的自注意力自动形成语义分割
    
    这是 DINO 最强大的能力之一！
    """
    print("\n" + "="*60)
    print("Demo: 自注意力语义分割 (DINO 核心能力)")
    print("="*60)
    
    # 如果没有提供图片，生成一个有物体的测试图
    if image_path and Path(image_path).exists():
        image = Image.open(image_path).convert('RGB')
        print(f"使用图片: {image_path}")
    else:
        # 创建一个有"物体"的测试图
        print("生成测试图片...")
        image = Image.new('RGB', (512, 512), color=(200, 200, 200))
        pixels = image.load()
        
        # 画一个圆形"物体"
        import math
        cx, cy, r = 256, 256, 120
        for x in range(512):
            for y in range(512):
                dist = math.sqrt((x - cx)**2 + (y - cy)**2)
                if dist < r:
                    # 渐变色圆形
                    intensity = int(255 * (1 - dist/r))
                    pixels[x, y] = (intensity, 100, 50)
        
        # 再画一个小方块
        for x in range(50, 130):
            for y in range(50, 130):
                pixels[x, y] = (50, 150, 200)
    
    # 获取注意力图
    print("计算自注意力图...")
    try:
        attention_map = get_attention_map(image)
        
        # 可视化
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        axes[0].imshow(image)
        axes[0].set_title("Original Image")
        axes[0].axis('off')
        
        im = axes[1].imshow(attention_map, cmap='viridis')
        axes[1].set_title("CLS Attention Map\n(自动语义分割)")
        axes[1].axis('off')
        plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
        
        # 叠加
        att_resized = np.array(Image.fromarray(
            ((attention_map - attention_map.min()) / (attention_map.max() - attention_map.min() + 1e-8) * 255).astype(np.uint8)
        ).resize(image.size, Image.BILINEAR))
        
        axes[2].imshow(image)
        axes[2].imshow(att_resized, cmap='viridis', alpha=0.6)
        axes[2].set_title("Overlay")
        axes[2].axis('off')
        
        plt.suptitle("DINO Self-Attention → Automatic Segmentation")
        plt.tight_layout()
        
        output_path = Path(__file__).parent / "demo_attention_segmentation.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        print(f"✓ 保存到: {output_path}")
        plt.close()
        
    except Exception as e:
        print(f"注意力图提取失败: {e}")
        print("(某些量化模型可能不支持 output_attentions)")


def demo_patch_similarity_map(image_path: str = None, query_position: tuple = None):
    """
    Demo: Patch 相似性可视化
    
    选择图中一个位置，显示其他位置与它的相似度
    相似的部位会高亮（如：选择一只眼睛，另一只眼睛也会高亮）
    """
    print("\n" + "="*60)
    print("Demo: Patch 相似性可视化")
    print("="*60)
    
    if image_path and Path(image_path).exists():
        image = Image.open(image_path).convert('RGB')
        print(f"使用图片: {image_path}")
    else:
        # 创建有对称结构的测试图
        print("生成测试图片（带对称结构）...")
        image = Image.new('RGB', (512, 512), color=(220, 220, 220))
        pixels = image.load()
        
        # 两个相似的圆（模拟两只眼睛）
        for cx, cy in [(150, 200), (350, 200)]:
            for x in range(512):
                for y in range(512):
                    dist = ((x - cx)**2 + (y - cy)**2) ** 0.5
                    if dist < 50:
                        pixels[x, y] = (50, 50, 150)
                    elif dist < 60:
                        pixels[x, y] = (100, 100, 100)
        
        # 底部一个矩形（模拟嘴巴）
        for x in range(180, 330):
            for y in range(350, 400):
                pixels[x, y] = (200, 100, 100)
    
    # 提取 patch 特征
    print("提取 patch 特征...")
    patches, grid_size = get_patch_features(image)
    
    # 选择查询位置
    if query_position is None:
        # 默认选择左上区域（如果有对称物体，应该能找到右边对应的）
        query_y = grid_size[0] // 3
        query_x = grid_size[1] // 3
    else:
        query_x, query_y = query_position
    
    query_idx = query_y * grid_size[1] + query_x
    query_patch = patches[query_idx]
    
    print(f"查询位置: ({query_x}, {query_y}), 网格大小: {grid_size}")
    
    # 计算所有 patch 与查询 patch 的相似度
    similarities = patches @ query_patch
    similarity_map = similarities.reshape(grid_size)
    
    # 可视化
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    axes[0].imshow(image)
    # 标记查询位置
    patch_h = image.size[1] / grid_size[0]
    patch_w = image.size[0] / grid_size[1]
    rect_x = query_x * patch_w
    rect_y = query_y * patch_h
    from matplotlib.patches import Rectangle
    rect = Rectangle((rect_x, rect_y), patch_w, patch_h, 
                      linewidth=3, edgecolor='red', facecolor='none')
    axes[0].add_patch(rect)
    axes[0].set_title(f"Query Patch: ({query_x}, {query_y})")
    axes[0].axis('off')
    
    im = axes[1].imshow(similarity_map, cmap='hot')
    axes[1].set_title("Patch Similarity Map")
    axes[1].axis('off')
    plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    
    # 叠加
    sim_resized = np.array(Image.fromarray(
        ((similarity_map - similarity_map.min()) / (similarity_map.max() - similarity_map.min() + 1e-8) * 255).astype(np.uint8)
    ).resize(image.size, Image.BILINEAR))
    
    axes[2].imshow(image)
    axes[2].imshow(sim_resized, cmap='hot', alpha=0.6)
    axes[2].set_title("Overlay (相似区域高亮)")
    axes[2].axis('off')
    
    plt.suptitle("Patch-to-Patch Similarity\n(选择一个位置，找到所有相似位置)")
    plt.tight_layout()
    
    output_path = Path(__file__).parent / "demo_patch_similarity.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 保存到: {output_path}")
    plt.close()


def demo_patch_to_patch_match(query_path: str, gallery_path: str):
    """
    Demo: Patch-to-Patch 局部匹配（正确方法）
    
    用查询图的所有 patches 与目标图的所有 patches 匹配
    """
    print("\n" + "="*60)
    print("Demo: Patch-to-Patch 局部匹配")
    print("="*60)
    
    if not Path(query_path).exists() or not Path(gallery_path).exists():
        print("请提供有效的图片路径")
        return
    
    query = Image.open(query_path).convert('RGB')
    gallery = Image.open(gallery_path).convert('RGB')
    
    print(f"查询图: {query_path} ({query.size})")
    print(f"目标图: {gallery_path} ({gallery.size})")
    
    # 提取两张图的 patch 特征
    print("提取 patch 特征...")
    query_patches, query_grid = get_patch_features(query)
    gallery_patches, gallery_grid = get_patch_features(gallery)
    
    print(f"查询图 patches: {query_patches.shape}, 网格: {query_grid}")
    print(f"目标图 patches: {gallery_patches.shape}, 网格: {gallery_grid}")
    
    # 计算相似度矩阵 (query_patches, gallery_patches)
    similarity_matrix = query_patches @ gallery_patches.T
    
    # 方法1: 对于目标图的每个 patch，找到查询图中最匹配的 patch 的分数
    max_similarity = similarity_matrix.max(axis=0)  # (num_gallery_patches,)
    heatmap = max_similarity.reshape(gallery_grid)
    
    print(f"相似度范围: [{heatmap.min():.4f}, {heatmap.max():.4f}]")
    
    # 可视化
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    
    axes[0].imshow(query)
    axes[0].set_title(f"Query Image\n{query_grid[0]}×{query_grid[1]} patches")
    axes[0].axis('off')
    
    axes[1].imshow(gallery)
    axes[1].set_title(f"Gallery Image\n{gallery_grid[0]}×{gallery_grid[1]} patches")
    axes[1].axis('off')
    
    im = axes[2].imshow(heatmap, cmap='hot')
    axes[2].set_title("Match Heatmap\n(Patch-to-Patch)")
    axes[2].axis('off')
    plt.colorbar(im, ax=axes[2], fraction=0.046, pad=0.04)
    
    # 叠加
    heatmap_resized = np.array(Image.fromarray(
        ((heatmap - heatmap.min()) / (heatmap.max() - heatmap.min() + 1e-8) * 255).astype(np.uint8)
    ).resize(gallery.size, Image.BILINEAR))
    
    axes[3].imshow(gallery)
    axes[3].imshow(heatmap_resized, cmap='hot', alpha=0.6)
    axes[3].set_title("Overlay")
    axes[3].axis('off')
    
    # 找到最佳匹配位置
    best_idx = np.argmax(heatmap)
    best_y, best_x = divmod(best_idx, gallery_grid[1])
    print(f"最佳匹配位置: ({best_x}, {best_y}), 分数: {heatmap[best_y, best_x]:.4f}")
    
    plt.suptitle("Patch-to-Patch Matching (正确的局部匹配方法)")
    plt.tight_layout()
    
    output_path = Path(__file__).parent / "demo_patch_to_patch.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"✓ 保存到: {output_path}")
    plt.close()


def main():
    """
    运行所有 Demo
    """
    print("="*60)
    print("DINOv3-7B INT8 量化 Demo")
    print("="*60)
    
    # 加载模型
    load_model_int8()
    
    # 显示模型信息
    show_model_info()
    
    # 基础 Demo
    demo_image_similarity()
    demo_patch_features()
    
    # DINO 核心能力演示
    demo_attention_segmentation()  # 自注意力语义分割
    demo_patch_similarity_map()     # Patch 相似性
    
    # 原来的局部匹配 demo
    demo_local_match()
    
    print("\n" + "="*60)
    print("所有 Demo 完成！")
    print("="*60)
    print("\n生成的可视化文件:")
    print("  - demo_local_match.png         (CLS 局部匹配)")
    print("  - demo_attention_segmentation.png (自注意力分割)")
    print("  - demo_patch_similarity.png    (Patch 相似性)")
    print("\n进阶用法:")
    print("  # 用真实图片测试自注意力分割")
    print("  demo_attention_segmentation('your_image.jpg')")
    print()
    print("  # 用真实图片测试 Patch-to-Patch 匹配")
    print("  demo_patch_to_patch_match('query.jpg', 'gallery.jpg')")


if __name__ == "__main__":
    main()

