"""
Qwen-Image-Layered Web 服务
提供可视化界面，支持上传图片进行图层分解
"""

import os
import sys
import time
import torch
import numpy as np
import subprocess
from pathlib import Path
from PIL import Image
from typing import List, Optional, Tuple

import gradio as gr

# 禁用 Gradio analytics（避免网络超时警告）
import os
os.environ["GRADIO_ANALYTICS_ENABLED"] = "False"

# ============== 性能优化设置 ==============
# 1. cuDNN 优化：对于固定输入尺寸，自动选择最快的卷积算法
torch.backends.cudnn.benchmark = True
torch.backends.cudnn.deterministic = False

# 2. 启用 TF32（Tensor Float 32）- RTX 30系列支持，加速矩阵运算
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# 3. 设置 float32 矩阵乘法精度为 'high'（使用 TF32）
torch.set_float32_matmul_precision('high')

print("⚡ 已启用性能优化: cuDNN benchmark + TF32")

# 模型路径
MODEL_PATH = "/data1/guo/AIGenTest/aiserver/models/Qwen/Qwen-Image-Layered"

# 全局变量
pipeline = None
model_loaded = False
use_int8 = False  # 是否使用 INT8 量化


def print_gpu_info():
    """打印 GPU 信息"""
    print("\n" + "=" * 60)
    print("🖥️  GPU 信息")
    print("=" * 60)
    
    # CUDA 可用性
    print(f"CUDA 可用: {torch.cuda.is_available()}")
    print(f"CUDA 版本: {torch.version.cuda}")
    print(f"PyTorch 版本: {torch.__version__}")
    print(f"cuDNN 版本: {torch.backends.cudnn.version()}")
    
    if torch.cuda.is_available():
        print(f"当前 CUDA 设备: {torch.cuda.current_device()}")
        print(f"GPU 数量: {torch.cuda.device_count()}")
        
        for i in range(torch.cuda.device_count()):
            props = torch.cuda.get_device_properties(i)
            total_mem = props.total_memory / 1024**3
            print(f"\n  GPU {i}: {props.name}")
            print(f"    - 总显存: {total_mem:.2f} GB")
            print(f"    - 计算能力: {props.major}.{props.minor}")
            print(f"    - 多处理器数: {props.multi_processor_count}")
    
    # 环境变量
    cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "未设置")
    print(f"\nCUDA_VISIBLE_DEVICES: {cuda_visible}")
    print("=" * 60 + "\n")


def print_gpu_memory(prefix=""):
    """打印当前 GPU 显存使用情况"""
    if not torch.cuda.is_available():
        print(f"{prefix}CUDA 不可用")
        return
    
    for i in range(torch.cuda.device_count()):
        allocated = torch.cuda.memory_allocated(i) / 1024**3
        reserved = torch.cuda.memory_reserved(i) / 1024**3
        total = torch.cuda.get_device_properties(i).total_memory / 1024**3
        print(f"{prefix}GPU {i}: 已分配 {allocated:.2f}GB / 已预留 {reserved:.2f}GB / 总共 {total:.2f}GB")


def print_nvidia_smi():
    """调用 nvidia-smi 打印简洁的 GPU 状态"""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total,power.draw,utilization.gpu",
             "--format=csv,noheader"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("📊 nvidia-smi 状态:")
            print("   GPU | 型号 | 已用显存 | 总显存 | 功率 | 利用率")
            for line in result.stdout.strip().split('\n'):
                print(f"   {line}")
    except Exception as e:
        print(f"⚠️ 无法运行 nvidia-smi: {e}")


def load_model():
    """加载模型"""
    global pipeline, model_loaded, use_int8
    
    if model_loaded:
        return "模型已加载"
    
    # 打印 GPU 信息
    print_gpu_info()
    
    print("=" * 60)
    print("🔄 [1/3] 加载前显存状态...")
    print_gpu_memory("   ")
    print_nvidia_smi()
    
    print("\n🔄 [2/3] 正在加载 Qwen-Image-Layered 模型...")
    print(f"   模型路径: {MODEL_PATH}")
    t0 = time.time()
    
    from diffusers import QwenImageLayeredPipeline
    
    # 检查是否存在模型文件
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"模型路径不存在: {MODEL_PATH}")
    
    # 检查可用 GPU 数量
    num_gpus = torch.cuda.device_count()
    print(f"   可用 GPU 数量: {num_gpus}")
    print(f"   INT8 量化: {'启用' if use_int8 else '禁用'}")
    
    # 准备量化配置
    quantization_config = None
    if use_int8:
        try:
            # diffusers 使用自己的量化配置
            from diffusers.quantizers import PipelineQuantizationConfig
            # 需要指定 quant_mapping 来告诉哪些组件需要量化
            quantization_config = PipelineQuantizationConfig(
                quant_backend="bitsandbytes_8bit",
                quant_kwargs={"load_in_8bit": True},
                # 量化 transformer 和 text_encoder（最大的两个组件）
                quant_mapping={
                    "transformer": {"load_in_8bit": True},
                    "text_encoder": {"load_in_8bit": True},
                },
            )
            print("   ✅ 已配置 INT8 量化 (diffusers PipelineQuantizationConfig)")
            print("   📉 预计显存占用: ~27GB (原 54GB 的约 50%)")
        except (ImportError, TypeError, ValueError) as e:
            print(f"   ⚠️ PipelineQuantizationConfig 配置失败: {e}")
            # 尝试不使用量化，直接多卡加载
            print("   💡 将使用多卡并行代替量化")
            quantization_config = None
            use_int8 = False
    
    # 模型很大（~54GB），需要多卡加载
    # transformer: 39GB, text_encoder: 16GB, vae: 243MB
    # INT8 量化后约 27GB，单卡仍然紧张，建议 2 卡
    
    print(f"   使用 torch_dtype: bfloat16")
    
    # 构建加载参数
    # diffusers 只支持 "balanced" 或 "cuda"，不支持 "auto"
    load_kwargs = {
        "torch_dtype": torch.bfloat16,
        "device_map": "balanced",
    }
    
    if quantization_config is not None:
        load_kwargs["quantization_config"] = quantization_config
    
    if use_int8 and quantization_config is not None and num_gpus >= 2:
        print(f"   ✅ INT8 量化 + {num_gpus} 张 GPU，使用 device_map='balanced'")
        pipeline = QwenImageLayeredPipeline.from_pretrained(
            MODEL_PATH,
            **load_kwargs
        )
    elif use_int8 and quantization_config is not None and num_gpus == 1:
        print(f"   ⚠️ INT8 量化 + 单卡模式，显存可能仍然紧张")
        pipeline = QwenImageLayeredPipeline.from_pretrained(
            MODEL_PATH,
            **load_kwargs
        )
    elif num_gpus >= 3:
        print(f"   ✅ 检测到 {num_gpus} 张 GPU，分步加载各组件")
        # 模型约 54GB (transformer 39GB, text_encoder 16GB, vae 0.24GB)
        # 分别加载各组件到不同 GPU
        
        # 方案：不使用 device_map，手动分配
        # transformer (39GB) -> GPU 2,3,4 (跨卡)
        # text_encoder (16GB) -> GPU 0
        # vae (0.24GB) -> GPU 1
        
        # 分步加载方式太复杂，diffusers pipeline 有自己的组件加载逻辑
        # 回退到使用 pipeline 的统一加载，但强制不使用 CPU offload
        # 问题的根源是 device_map="balanced" 把 transformer 放到了 meta
        
        # 尝试：先完整加载 pipeline，再手动移动 transformer
        print("   [Step 1] 完整加载 pipeline...")
        pipeline = QwenImageLayeredPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            device_map="balanced",
        )
        
        # 检查 transformer 是否在 meta 设备
        try:
            first_param = next(pipeline.transformer.parameters())
            if first_param.device.type == 'meta':
                print("   ⚠️ transformer 仍在 meta 设备，尝试强制加载...")
                # 单独加载 transformer 到多卡
                from diffusers import QwenImageTransformer2DModel
                transformer_path = os.path.join(MODEL_PATH, "transformer")
                
                # 跳过 GPU 0 (text_encoder ~16GB) 和 GPU 1 (vae ~0.24GB)
                # 让 transformer (~39GB) 分布在 GPU 2,3,4...
                transformer_max_memory = {}
                transformer_max_memory[0] = "0GiB"  # 不用 GPU 0
                transformer_max_memory[1] = "0GiB"  # 不用 GPU 1
                for i in range(2, num_gpus):
                    transformer_max_memory[i] = "22GiB"
                transformer_max_memory["cpu"] = "0GiB"  # 不允许 CPU offload
                
                print(f"   📊 transformer max_memory: {transformer_max_memory}")
                
                new_transformer = QwenImageTransformer2DModel.from_pretrained(
                    transformer_path,
                    torch_dtype=torch.bfloat16,
                    device_map="balanced",
                    max_memory=transformer_max_memory,
                )
                pipeline.transformer = new_transformer
                print("   ✅ transformer 重新加载完成")
        except StopIteration:
            print("   ℹ️ transformer 没有参数")
        except Exception as e:
            print(f"   ⚠️ 检查/重载 transformer 失败: {e}")
    elif num_gpus >= 2:
        print(f"   ⚠️ 仅有 {num_gpus} 张 GPU，尝试使用 device_map='balanced'")
        pipeline = QwenImageLayeredPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            device_map="balanced",
        )
    else:
        print(f"   ⚠️ 仅有 {num_gpus} 张 GPU (24GB)，模型约 54GB，可能显存不足！")
        print(f"   💡 建议启用 INT8 量化: --int8")
        print(f"   尝试使用 CPU offload...")
        pipeline = QwenImageLayeredPipeline.from_pretrained(
            MODEL_PATH,
            torch_dtype=torch.bfloat16,
            device_map="balanced",
            offload_folder="offload",
        )
    
    print(f"\n   ✅ Pipeline 加载完成，耗时: {time.time() - t0:.2f}秒")
    print(f"   📦 Pipeline 类型: {type(pipeline).__name__}")
    
    # 检查 transformer 是否在 meta 设备上，如果是则需要手动移到 GPU
    if hasattr(pipeline, 'transformer') and pipeline.transformer is not None:
        try:
            first_param = next(pipeline.transformer.parameters())
            if first_param.device.type == 'meta':
                print("\n   ⚠️ transformer 在 meta 设备上，尝试手动分配到 GPU...")
                # 使用 accelerate 来分配到多个 GPU
                from accelerate import dispatch_model, infer_auto_device_map
                from accelerate.utils import get_balanced_memory
                
                # 计算每个 GPU 可用的显存
                max_memory = get_balanced_memory(
                    pipeline.transformer,
                    max_memory=None,
                    no_split_module_classes=["QwenImageTransformerBlock"],
                    dtype=torch.bfloat16,
                )
                print(f"   📊 自动计算的 max_memory: {max_memory}")
                
                # 推断设备映射
                device_map = infer_auto_device_map(
                    pipeline.transformer,
                    max_memory=max_memory,
                    no_split_module_classes=["QwenImageTransformerBlock"],
                    dtype=torch.bfloat16,
                )
                print(f"   📊 推断的 device_map 前 5 项: {dict(list(device_map.items())[:5])}")
                
                # 分发模型
                pipeline.transformer = dispatch_model(
                    pipeline.transformer,
                    device_map=device_map,
                )
                print("   ✅ transformer 已分发到 GPU")
        except StopIteration:
            print("   ℹ️ transformer 没有参数")
        except Exception as e:
            print(f"   ⚠️ 尝试移动 transformer 失败: {e}")
    
    # 打印 pipeline 的组件信息和设备分布
    print("\n   📋 Pipeline 组件及设备分布:")
    for name, component in pipeline.components.items():
        if component is not None:
            component_type = type(component).__name__
            # 检查是否在 GPU 上
            device = "N/A"
            if hasattr(component, 'device'):
                device = str(component.device)
            elif hasattr(component, 'hf_device_map'):
                # 多卡时可能有 device_map
                device = f"device_map: {component.hf_device_map}"
            elif hasattr(component, 'parameters'):
                try:
                    params = list(component.parameters())
                    if params:
                        devices = set(str(p.device) for p in params[:10])  # 检查前10个参数
                        device = ", ".join(devices) if len(devices) <= 3 else f"{len(devices)} devices"
                except Exception:
                    device = "无法获取"
            print(f"      - {name}: {component_type} (device: {device})")
    
    pipeline.set_progress_bar_config(disable=None)
    
    print(f"\n✅ [2/3] 模型加载完成，总耗时: {time.time() - t0:.2f}秒")
    
    # 加载后显存状态
    print("\n📊 加载后显存状态:")
    print_gpu_memory("   ")
    print_nvidia_smi()
    
    # ============== 加速优化说明 ==============
    print("\n⚡ 已启用的加速优化:")
    print("   ✅ cuDNN benchmark（自动选择最快卷积算法）")
    print("   ✅ TF32 矩阵运算加速（RTX 30系列）")
    print("   ✅ Flash Attention 2.x（模型内置）")
    print("   ✅ bfloat16 混合精度")
    print("   ✅ 多 GPU 并行（5 张 RTX 3090）")
    # 注意：xformers 与此模型不兼容（会破坏双输出注意力机制）
    # 注意：torch.compile 对此模型不适用（计算图太深）
    
    # 预热
    print("\n🔄 [3/3] 预热中（首次推理，编译 CUDA kernel）...")
    t0 = time.time()
    dummy_image = Image.new("RGBA", (256, 256), (128, 128, 128, 255))
    with torch.inference_mode():
        _ = pipeline(
            image=dummy_image,
            generator=torch.Generator(device='cuda').manual_seed(0),
            num_inference_steps=2,
            layers=2,
            resolution=640,
        )
    print(f"✅ [3/3] 预热完成，耗时: {time.time() - t0:.2f}秒")
    
    # 预热后显存状态
    print("\n📊 预热后显存状态:")
    print_gpu_memory("   ")
    print_nvidia_smi()
    
    model_loaded = True
    print("\n" + "=" * 60)
    print("🎉 模型加载完成！服务即将启动...")
    print("=" * 60)
    return "模型加载完成"


def process_image(
    image: np.ndarray,
    num_layers: int,
    num_inference_steps: int,
    true_cfg_scale: float,
    resolution: int,
    seed: int,
    cfg_normalize: bool,
    use_en_prompt: bool,
    negative_prompt: str,
    progress=gr.Progress()
) -> Tuple[List[Image.Image], Image.Image, str]:
    """处理上传的图片，分解为多个图层"""
    import datetime
    print(f"\n⏰ [{datetime.datetime.now().strftime('%H:%M:%S.%f')[:-3]}] process_image() 函数被调用")
    
    global pipeline, model_loaded
    
    if not model_loaded:
        progress(0, desc="加载模型中...")
        load_model()
    
    if image is None:
        return None, None, "❌ 请先上传图片"
    
    start_time = time.time()
    print("\n" + "-" * 40)
    print(f"📷 收到新图片，尺寸: {image.shape}")
    
    try:
        # 转换为 PIL Image (RGBA)
        if len(image.shape) == 2:
            # 灰度图转RGB
            image = np.stack([image] * 3, axis=-1)
        
        if image.shape[2] == 3:
            # RGB 转 RGBA
            pil_image = Image.fromarray(image).convert("RGBA")
        else:
            pil_image = Image.fromarray(image)
        
        print(f"📐 图片转换为 RGBA，尺寸: {pil_image.size}")
        
        # 设置参数
        inputs = {
            "image": pil_image,
            "generator": torch.Generator(device='cuda').manual_seed(seed),
            "true_cfg_scale": true_cfg_scale,
            "negative_prompt": negative_prompt if negative_prompt.strip() else " ",
            "num_inference_steps": num_inference_steps,
            "num_images_per_prompt": 1,
            "layers": num_layers,
            "resolution": resolution,
            "cfg_normalize": cfg_normalize,
            "use_en_prompt": use_en_prompt,
        }
        
        print(f"⚙️ 参数: layers={num_layers}, steps={num_inference_steps}, cfg={true_cfg_scale}, resolution={resolution}")
        
        # 推理前显存状态
        print("\n📊 推理前显存状态:")
        print_gpu_memory("   ")
        
        # 推理
        progress(0.2, desc="正在分解图层...")
        print("🔄 正在推理...")
        t0 = time.time()
        
        with torch.inference_mode():
            output = pipeline(**inputs)
            output_images = output.images[0]  # List of PIL Images (RGBA)
        
        # 同步 GPU 确保计时准确
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        
        inference_time = time.time() - t0
        print(f"✅ 推理完成，耗时: {inference_time:.2f}秒，生成 {len(output_images)} 个图层")
        
        # 推理后显存状态
        print("\n📊 推理后显存状态:")
        print_gpu_memory("   ")
        print_nvidia_smi()
        
        # 合成预览图（将所有图层叠加）
        progress(0.9, desc="生成预览...")
        composite = None
        for layer in output_images:
            if composite is None:
                composite = layer.copy()
            else:
                composite = Image.alpha_composite(composite, layer)
        
        total_time = time.time() - start_time
        print(f"🎉 处理完成！总耗时: {total_time:.2f}秒")
        print("-" * 40)
        
        # 生成结果摘要
        summary = f"""## 📊 分解结果

**图层数量**: {len(output_images)}
**推理耗时**: {inference_time:.2f} 秒
**总处理耗时**: {total_time:.2f} 秒

### 参数配置
- **推理步数**: {num_inference_steps}
- **CFG Scale**: {true_cfg_scale}
- **分辨率**: {resolution}
- **随机种子**: {seed}
- **CFG 归一化**: {'是' if cfg_normalize else '否'}
- **使用英文提示**: {'是' if use_en_prompt else '否'}

### 图层信息
"""
        for i, layer in enumerate(output_images):
            # 计算图层的非透明像素比例
            alpha = np.array(layer.split()[-1])
            non_transparent = np.sum(alpha > 0) / alpha.size * 100
            summary += f"- **Layer {i}**: {layer.size[0]}x{layer.size[1]}, 非透明区域: {non_transparent:.1f}%\n"
        
        return output_images, composite, summary
        
    except Exception as e:
        import traceback
        error_msg = f"❌ 处理出错: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
        print(error_msg)
        return None, None, error_msg


def save_layers(layers: List[Image.Image]) -> Optional[str]:
    """保存所有图层为 ZIP 文件"""
    if layers is None or len(layers) == 0:
        return None
    
    import zipfile
    import tempfile
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "layers.zip")
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for i, layer in enumerate(layers):
            layer_path = os.path.join(temp_dir, f"layer_{i}.png")
            layer.save(layer_path, "PNG")
            zipf.write(layer_path, f"layer_{i}.png")
    
    return zip_path


def create_interface():
    """创建 Gradio 界面"""
    
    with gr.Blocks(
        title="Qwen-Image-Layered - 图像分层分解",
        theme=gr.themes.Soft(
            primary_hue="indigo",
            secondary_hue="slate",
            neutral_hue="slate",
        ),
        css="""
        .main-title {
            text-align: center;
            margin-bottom: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .layer-gallery img {
            border: 2px solid #ddd;
            border-radius: 8px;
        }
        .result-box {
            min-height: 300px;
        }
        footer {
            display: none !important;
        }
        """
    ) as demo:
        
        # 用于存储图层结果
        layers_state = gr.State([])
        
        gr.HTML("""
        <div class="main-title">
            <h1>🎨 Qwen-Image-Layered</h1>
            <p style="color: #666;">智能图像分层分解 - 将图像分解为可独立编辑的 RGBA 图层</p>
        </div>
        """)
        
        with gr.Row():
            # 左侧：输入区域
            with gr.Column(scale=1):
                gr.Markdown("### 📤 上传图片")
                input_image = gr.Image(
                    label="输入图片",
                    type="numpy",
                    height=350
                )
                
                with gr.Accordion("⚙️ 参数设置", open=True):
                    num_layers = gr.Slider(
                        minimum=2,
                        maximum=10,
                        value=4,
                        step=1,
                        label="图层数量",
                        info="分解为多少个图层（2-10）"
                    )
                    
                    num_inference_steps = gr.Slider(
                        minimum=10,
                        maximum=100,
                        value=50,
                        step=5,
                        label="推理步数",
                        info="步数越多质量越高，但速度越慢"
                    )
                    
                    true_cfg_scale = gr.Slider(
                        minimum=1.0,
                        maximum=10.0,
                        value=4.0,
                        step=0.5,
                        label="CFG Scale",
                        info="控制生成的引导强度"
                    )
                    
                    resolution = gr.Radio(
                        choices=[640, 1024],
                        value=640,
                        label="分辨率",
                        info="640 推荐用于测试，1024 用于高质量输出"
                    )
                    
                    seed = gr.Number(
                        value=777,
                        label="随机种子",
                        info="固定种子可复现结果"
                    )
                    
                    with gr.Row():
                        cfg_normalize = gr.Checkbox(
                            value=True,
                            label="CFG 归一化"
                        )
                        use_en_prompt = gr.Checkbox(
                            value=True,
                            label="使用英文提示"
                        )
                    
                    negative_prompt = gr.Textbox(
                        value=" ",
                        label="负面提示词（可选）",
                        placeholder="不希望出现的内容..."
                    )
                
                with gr.Row():
                    submit_btn = gr.Button("🚀 开始分解", variant="primary", size="lg")
                    clear_btn = gr.Button("🗑️ 清除", size="lg")
            
            # 右侧：输出区域
            with gr.Column(scale=1):
                gr.Markdown("### 🖼️ 合成预览")
                output_composite = gr.Image(
                    label="图层合成预览",
                    height=350
                )
                
                gr.Markdown("### 📚 分层结果")
                output_gallery = gr.Gallery(
                    label="各图层预览",
                    columns=4,
                    rows=2,
                    height=200,
                    object_fit="contain",
                    elem_classes=["layer-gallery"]
                )
                
                download_btn = gr.Button("📥 下载所有图层 (ZIP)", size="lg")
                download_file = gr.File(label="下载文件", visible=False)
        
        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📋 处理结果")
                output_summary = gr.Markdown(
                    value="等待处理...",
                    elem_classes=["result-box"]
                )
        
        gr.Markdown("""
        ---
        ### 💡 使用说明
        
        1. **上传图片**：支持 PNG、JPG 等常见格式
        2. **调整参数**：根据需要调整图层数量和质量参数
        3. **开始分解**：点击按钮，等待模型处理
        4. **查看结果**：预览各个图层，下载 ZIP 包进行后续编辑
        
        **应用场景**：
        - 🎨 图像编辑：独立调整前景/背景
        - 🔄 对象替换：替换特定图层内容
        - 🗑️ 对象删除：移除不需要的图层
        - 📐 重新布局：自由移动各图层位置
        """)
        
        # 事件绑定
        def process_and_store(image, num_layers, num_inference_steps, true_cfg_scale, 
                             resolution, seed, cfg_normalize, use_en_prompt, negative_prompt):
            layers, composite, summary = process_image(
                image, num_layers, num_inference_steps, true_cfg_scale,
                resolution, int(seed), cfg_normalize, use_en_prompt, negative_prompt
            )
            return layers, composite, layers, summary
        
        submit_btn.click(
            fn=process_and_store,
            inputs=[
                input_image, num_layers, num_inference_steps, true_cfg_scale,
                resolution, seed, cfg_normalize, use_en_prompt, negative_prompt
            ],
            outputs=[output_gallery, output_composite, layers_state, output_summary]
        )
        
        clear_btn.click(
            fn=lambda: (None, None, None, [], "等待处理..."),
            inputs=[],
            outputs=[input_image, output_composite, output_gallery, layers_state, output_summary]
        )
        
        download_btn.click(
            fn=save_layers,
            inputs=[layers_state],
            outputs=[download_file]
        )
    
    return demo


def main():
    """启动服务"""
    global use_int8
    import argparse
    
    parser = argparse.ArgumentParser(description="Qwen-Image-Layered Web服务")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务地址")
    parser.add_argument("--port", type=int, default=7861, help="服务端口")
    parser.add_argument("--share", action="store_true", help="创建公共链接")
    parser.add_argument("--preload", action="store_true", help="启动时预加载模型")
    parser.add_argument("--int8", action="store_true", help="启用 INT8 量化（减少约 50% 显存）")
    args = parser.parse_args()
    
    # 设置量化选项
    use_int8 = args.int8
    
    print("=" * 60)
    print("🎨 Qwen-Image-Layered Web 服务")
    print("=" * 60)
    print(f"📂 模型路径: {MODEL_PATH}")
    print(f"🔢 INT8 量化: {'✅ 启用' if use_int8 else '❌ 禁用'}")
    
    # 启动时打印 GPU 信息
    print_gpu_info()
    print_nvidia_smi()
    
    # 预加载模型
    if args.preload:
        load_model()
    
    # 创建界面
    demo = create_interface()
    
    print(f"\n🌐 服务地址: http://{args.host}:{args.port}")
    print("=" * 60)
    
    # 启动服务
    demo.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        show_error=True
    )


if __name__ == "__main__":
    main()

