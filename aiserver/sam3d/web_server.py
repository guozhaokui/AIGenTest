"""
SAM 3D Body Web 服务
提供可视化界面，支持上传图片进行3D人体重建
"""

import os
import sys
import json
import time
import numpy as np
from pathlib import Path

# 添加 sam-3d-body 到 PYTHONPATH
SAM3D_PATH = Path(__file__).parent.parent / "third_party" / "sam-3d-body"
if str(SAM3D_PATH) not in sys.path:
    sys.path.insert(0, str(SAM3D_PATH))

import gradio as gr
from sam3d_body_demo import SAM3DBodyEstimator


# 全局变量
estimator = None
model_loaded = False


def load_model():
    """加载模型（带预热）"""
    global estimator, model_loaded
    
    if model_loaded:
        return "模型已加载"
    
    import time
    
    print("=" * 60)
    print("🔄 [1/3] 正在初始化 SAM3DBodyEstimator...")
    t0 = time.time()
    
    estimator = SAM3DBodyEstimator(
        use_detector=False,  # 简化，不用检测器
        use_fov_estimator=False
    )
    print(f"✅ [1/3] 初始化完成，耗时: {time.time() - t0:.2f}秒")
    
    # 预热
    print("🔄 [2/3] 预热中（首次推理，编译CUDA kernel）...")
    t0 = time.time()
    dummy = np.zeros((512, 512, 3), dtype=np.uint8)
    _ = estimator.process_image(dummy)
    print(f"✅ [2/3] 预热完成，耗时: {time.time() - t0:.2f}秒")
    
    print("🔄 [3/3] 启动 Gradio 界面...")
    model_loaded = True
    print("=" * 60)
    print("🎉 模型加载完成！服务即将启动...")
    print("=" * 60)
    return "模型加载完成"


def process_image(image):
    """处理上传的图片"""
    global estimator, model_loaded
    
    if not model_loaded:
        load_model()
    
    if image is None:
        return None, None, "请先上传图片"
    
    start_time = time.time()
    print("\n" + "-" * 40)
    print(f"📷 收到新图片，尺寸: {image.shape}")
    
    try:
        # 转换图像格式 (Gradio返回RGB，需要转BGR)
        import cv2
        img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # 推理
        print("🔄 正在推理...")
        t0 = time.time()
        outputs = estimator.process_image(img_bgr)
        inference_time = time.time() - t0
        print(f"✅ 推理完成，耗时: {inference_time:.3f}秒，检测到 {len(outputs)} 个人体")
        
        # 提取数据
        print("🔄 提取结构化数据...")
        result = estimator.process_and_extract(img_bgr)
        print("✅ 数据提取完成")
        
        # 可视化
        print("🔄 生成可视化图像...")
        t0 = time.time()
        vis_img = estimator.visualize(img_bgr, outputs)
        vis_img_rgb = cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB)
        print(f"✅ 可视化完成，耗时: {time.time() - t0:.3f}秒")
        
        total_time = time.time() - start_time
        print(f"🎉 处理完成！总耗时: {total_time:.3f}秒")
        print("-" * 40)
        
        # 生成结果摘要
        num_persons = result.get("num_persons", 0)
        
        summary_lines = [
            f"## 📊 检测结果",
            f"",
            f"**检测到人数**: {num_persons}",
            f"**推理耗时**: {inference_time:.3f} 秒",
            f"**总处理耗时**: {total_time:.3f} 秒",
            f"",
        ]
        
        if num_persons > 0:
            for i, person in enumerate(result.get("persons", [])):
                summary_lines.extend([
                    f"### 👤 人物 {i+1}",
                    f"",
                ])
                
                # 顶点信息
                if "pred_vertices" in person:
                    v = person["pred_vertices"]
                    summary_lines.append(f"- **3D网格顶点**: {v.get('num_vertices', 'N/A')} 个")
                
                # 关键点信息
                if "pred_keypoints_3d" in person:
                    kp = person["pred_keypoints_3d"]
                    summary_lines.append(f"- **3D关键点**: {kp.get('shape', ['N/A'])[0]} 个")
                
                if "pred_keypoints_2d" in person:
                    kp = person["pred_keypoints_2d"]
                    summary_lines.append(f"- **2D关键点**: {kp.get('shape', ['N/A'])[0]} 个")
                
                # 旋转信息
                if "pred_global_rots" in person:
                    rot = person["pred_global_rots"]
                    summary_lines.append(f"- **关节旋转**: {rot.get('num_joints', 'N/A')} 个关节 (3×3矩阵)")
                
                # 参数信息
                if "body_pose_params" in person:
                    bp = person["body_pose_params"]
                    summary_lines.append(f"- **身体姿态参数**: {bp.get('shape', ['N/A'])[0]} 维")
                
                if "shape_params" in person:
                    sp = person["shape_params"]
                    summary_lines.append(f"- **体型参数**: {sp.get('shape', ['N/A'])[0]} 维")
                
                if "focal_length" in person:
                    summary_lines.append(f"- **焦距**: {person['focal_length']:.2f}")
                
                summary_lines.append("")
        
        summary = "\n".join(summary_lines)
        
        # 格式化JSON（精简版）
        json_result = {
            "image_info": result.get("image_info"),
            "num_persons": num_persons,
            "inference_time_sec": round(inference_time, 3),
        }
        
        if num_persons > 0:
            json_result["persons"] = []
            for person in result.get("persons", []):
                p = {
                    "person_id": person.get("person_id"),
                    "num_vertices": person.get("pred_vertices", {}).get("num_vertices"),
                    "num_keypoints_3d": person.get("pred_keypoints_3d", {}).get("shape", [0])[0],
                    "num_joints": person.get("pred_global_rots", {}).get("num_joints"),
                    "focal_length": person.get("focal_length"),
                    "bbox": person.get("bbox"),
                }
                json_result["persons"].append(p)
        
        json_str = json.dumps(json_result, indent=2, ensure_ascii=False)
        
        return vis_img_rgb, summary, json_str
        
    except Exception as e:
        import traceback
        error_msg = f"处理出错: {str(e)}\n{traceback.format_exc()}"
        return None, error_msg, None


def download_full_result(image):
    """下载完整JSON结果"""
    global estimator, model_loaded
    
    if not model_loaded or image is None:
        return None
    
    import cv2
    img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    result = estimator.process_and_extract(img_bgr)
    
    # 保存到临时文件
    output_path = "/tmp/sam3d_result.json"
    
    def convert_to_serializable(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        elif isinstance(obj, dict):
            return {k: convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_serializable(v) for v in obj]
        return obj
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(convert_to_serializable(result), f, indent=2, ensure_ascii=False)
    
    return output_path


# 创建界面
def create_interface():
    """创建 Gradio 界面"""
    
    with gr.Blocks(
        title="SAM 3D Body - 3D人体重建",
        theme=gr.themes.Soft(
            primary_hue="blue",
            secondary_hue="slate",
        ),
        css="""
        .main-title {
            text-align: center;
            margin-bottom: 20px;
        }
        .result-box {
            min-height: 400px;
        }
        """
    ) as demo:
        
        gr.HTML("""
        <div class="main-title">
            <h1>🧍 SAM 3D Body</h1>
            <p>基于 DINOv3 的单图3D人体网格重建</p>
        </div>
        """)
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📤 上传图片")
                input_image = gr.Image(
                    label="输入图片",
                    type="numpy",
                    height=400
                )
                
                with gr.Row():
                    submit_btn = gr.Button("🚀 开始处理", variant="primary", size="lg")
                    clear_btn = gr.Button("🗑️ 清除", size="lg")
                
                gr.Markdown("""
                **提示**：
                - 首次处理需要加载模型（约10秒）
                - 后续处理每张图约0.8秒
                - 建议上传包含完整人体的图片
                """)
                
            with gr.Column(scale=1):
                gr.Markdown("### 🖼️ 可视化结果")
                output_image = gr.Image(
                    label="3D网格叠加",
                    height=400
                )
        
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📋 检测摘要")
                output_summary = gr.Markdown(
                    value="等待处理...",
                    elem_classes=["result-box"]
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📄 JSON结果 (精简)")
                output_json = gr.Code(
                    label="JSON",
                    language="json",
                    lines=15
                )
                download_btn = gr.Button("📥 下载完整JSON")
                download_file = gr.File(label="下载文件", visible=False)
        
        # 事件绑定
        submit_btn.click(
            fn=process_image,
            inputs=[input_image],
            outputs=[output_image, output_summary, output_json]
        )
        
        clear_btn.click(
            fn=lambda: (None, None, "等待处理...", None),
            inputs=[],
            outputs=[input_image, output_image, output_summary, output_json]
        )
        
        download_btn.click(
            fn=download_full_result,
            inputs=[input_image],
            outputs=[download_file]
        )
        
        # 示例图片
        gr.Examples(
            examples=[
                ["/data1/guo/AIGenTest/aiserver/embedding/test/女性裸体雕塑的黑白照片.jpeg"],
            ],
            inputs=[input_image],
            label="📸 示例图片"
        )
    
    return demo


def main():
    """启动服务"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SAM 3D Body Web服务")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务地址")
    parser.add_argument("--port", type=int, default=7860, help="服务端口")
    parser.add_argument("--share", action="store_true", help="创建公共链接")
    parser.add_argument("--preload", action="store_true", help="启动时预加载模型")
    args = parser.parse_args()
    
    print("=" * 60)
    print("SAM 3D Body Web 服务")
    print("=" * 60)
    
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

