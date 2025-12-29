"""
SAM 3D Body 人体3D网格恢复示例
根据输入图片输出完整的人体3D信息

模型: facebook/sam-3d-body-dinov3
功能: 从单张图片恢复3D人体网格、姿态、关键点等信息

使用方法:
    # 设置环境
    export PYTHONPATH=/data1/guo/AIGenTest/aiserver/third_party/sam-3d-body:$PYTHONPATH
    
    # 运行示例
    python sam3d_body_demo.py --image /path/to/image.jpg
    python sam3d_body_demo.py --image /path/to/image.jpg --output result.json --output_image result.png
"""

import os
import sys
import json
import numpy as np
from pathlib import Path
from typing import Union, Dict, List, Any, Optional

# 添加 sam-3d-body 到 PYTHONPATH
SAM3D_PATH = Path(__file__).parent.parent / "third_party" / "sam-3d-body"
if str(SAM3D_PATH) not in sys.path:
    sys.path.insert(0, str(SAM3D_PATH))


class SAM3DBodyEstimator:
    """SAM 3D Body 人体3D估计器封装类"""
    
    def __init__(
        self, 
        checkpoint_path: str = None,
        mhr_path: str = None,
        device: str = None,
        use_detector: bool = True,
        use_fov_estimator: bool = False,  # 默认关闭，避免网络下载
    ):
        """
        初始化 SAM 3D Body 估计器
        
        Args:
            checkpoint_path: 模型检查点路径，默认使用本地下载的模型
            mhr_path: MHR 模型路径
            device: 设备类型，默认自动选择 cuda/cpu
            use_detector: 是否使用人体检测器（推荐开启）
            use_fov_estimator: 是否使用视野估计器
        """
        import torch
        
        # 设置默认路径
        model_dir = Path(__file__).parent.parent / "models" / "sam-3d-body-dinov3"
        
        if checkpoint_path is None:
            checkpoint_path = str(model_dir / "model.ckpt")
        if mhr_path is None:
            mhr_path = str(model_dir / "assets" / "mhr_model.pt")
            
        self.checkpoint_path = checkpoint_path
        self.mhr_path = mhr_path
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.use_detector = use_detector
        self.use_fov_estimator = use_fov_estimator
        
        print(f"模型检查点: {checkpoint_path}")
        print(f"MHR 模型: {mhr_path}")
        print(f"使用设备: {self.device}")
        
        # 检查文件是否存在
        if not os.path.exists(checkpoint_path):
            raise FileNotFoundError(f"找不到模型检查点: {checkpoint_path}")
        if not os.path.exists(mhr_path):
            raise FileNotFoundError(f"找不到 MHR 模型: {mhr_path}")
        
        self._estimator = None
        self._faces = None
        
    def _load_model(self):
        """延迟加载模型"""
        if self._estimator is not None:
            return
            
        print("正在加载 SAM 3D Body 模型...")
        
        # 导入官方库
        from sam_3d_body import load_sam_3d_body, SAM3DBodyEstimator as _SAM3DBodyEstimator
        
        # 加载核心模型
        model, model_cfg = load_sam_3d_body(
            checkpoint_path=self.checkpoint_path,
            mhr_path=self.mhr_path,
            device=self.device
        )
        
        # 初始化可选组件
        human_detector = None
        fov_estimator = None
        
        if self.use_detector:
            try:
                print("加载人体检测器 (vitdet)...")
                from tools.build_detector import HumanDetector
                human_detector = HumanDetector(name="vitdet", device=self.device)
            except Exception as e:
                print(f"警告: 无法加载人体检测器: {e}")
        
        if self.use_fov_estimator:
            try:
                print("加载视野估计器 (moge2)...")
                from tools.build_fov_estimator import FOVEstimator
                fov_estimator = FOVEstimator(name="moge2", device=self.device)
            except Exception as e:
                print(f"警告: 无法加载视野估计器: {e}")
        
        # 创建估计器
        self._estimator = _SAM3DBodyEstimator(
            sam_3d_body_model=model,
            model_cfg=model_cfg,
            human_detector=human_detector,
            human_segmentor=None,
            fov_estimator=fov_estimator,
        )
        
        self._faces = self._estimator.faces
        print("模型加载完成!")
    
    @property
    def faces(self) -> np.ndarray:
        """获取网格面索引"""
        self._load_model()
        return self._faces
    
    def process_image(
        self, 
        image_input: Union[str, np.ndarray],
        bboxes: Optional[np.ndarray] = None,
        inference_type: str = "full"
    ) -> List[Dict[str, Any]]:
        """
        处理图像并返回所有检测到的人体3D信息
        
        Args:
            image_input: 图像路径(str) 或 numpy数组(BGR格式)
            bboxes: 可选的预计算边界框 [N, 4]，格式为 [x1, y1, x2, y2]
            inference_type: 推理类型
                - "full": 完整推理（身体+手部）
                - "body": 仅身体推理
                - "hand": 仅手部推理
                
        Returns:
            检测到的人体列表，每个人体包含:
            - pred_vertices: 3D网格顶点 [N, 3]
            - pred_keypoints_3d: 3D关键点
            - pred_keypoints_2d: 2D关键点
            - pred_cam_t: 相机平移
            - focal_length: 焦距
            - bbox: 边界框
        """
        import cv2
        
        self._load_model()
        
        # 加载图像
        if isinstance(image_input, str):
            img_bgr = cv2.imread(image_input)
            if img_bgr is None:
                raise ValueError(f"无法读取图像: {image_input}")
        elif isinstance(image_input, np.ndarray):
            img_bgr = image_input
        else:
            raise ValueError(f"不支持的图像类型: {type(image_input)}")
        
        # 调用官方 API
        outputs = self._estimator.process_one_image(
            img_bgr,
            bboxes=bboxes,
            inference_type=inference_type
        )
        
        return outputs
    
    def process_and_extract(
        self, 
        image_input: Union[str, np.ndarray],
        **kwargs
    ) -> Dict[str, Any]:
        """
        处理图像并提取结构化信息
        
        Returns:
            包含图像信息和所有人体数据的字典
        """
        import cv2
        
        # 获取图像信息
        if isinstance(image_input, str):
            img_bgr = cv2.imread(image_input)
        else:
            img_bgr = image_input
            
        outputs = self.process_image(image_input, **kwargs)
        
        result = {
            "image_info": {
                "height": img_bgr.shape[0],
                "width": img_bgr.shape[1],
                "channels": img_bgr.shape[2],
            },
            "num_persons": len(outputs),
            "persons": []
        }
        
        for i, output in enumerate(outputs):
            person = self._extract_person_data(output, i)
            result["persons"].append(person)
        
        return result
    
    def _extract_person_data(self, output: dict, person_idx: int) -> dict:
        """从模型输出提取单个人的数据"""
        person = {"person_id": person_idx}
        
        def to_numpy(x):
            if x is None:
                return None
            if hasattr(x, 'cpu'):
                return x.cpu().numpy()
            return np.array(x) if not isinstance(x, np.ndarray) else x
        
        # 3D网格顶点
        if "pred_vertices" in output:
            vertices = to_numpy(output["pred_vertices"])
            person["pred_vertices"] = {
                "shape": list(vertices.shape),
                "num_vertices": vertices.shape[0],
                "bounds": {
                    "min": vertices.min(axis=0).tolist(),
                    "max": vertices.max(axis=0).tolist(),
                },
            }
        
        # 3D/2D 关键点（位置）
        for key in ["pred_keypoints_3d", "pred_keypoints_2d"]:
            if key in output:
                kp = to_numpy(output[key])
                person[key] = {
                    "shape": list(kp.shape),
                    "data": kp.tolist() if kp.size < 1000 else "数据过大",
                }
        
        # 关节坐标
        if "pred_joint_coords" in output:
            jc = to_numpy(output["pred_joint_coords"])
            person["pred_joint_coords"] = {
                "shape": list(jc.shape),
                "data": jc.tolist() if jc.size < 1000 else "数据过大",
            }
        
        # 全局旋转（根节点）
        if "global_rot" in output:
            gr = to_numpy(output["global_rot"])
            person["global_rot"] = {
                "shape": list(gr.shape),
                "data": gr.tolist(),
            }
        
        # 所有关节的全局旋转矩阵
        if "pred_global_rots" in output:
            pgr = to_numpy(output["pred_global_rots"])
            person["pred_global_rots"] = {
                "shape": list(pgr.shape),  # [num_joints, 3, 3] 旋转矩阵
                "num_joints": pgr.shape[0] if pgr.ndim >= 1 else 0,
                "data": pgr.tolist() if pgr.size < 2000 else "数据过大，请通过 process_image() 获取原始输出",
            }
        
        # 身体姿态参数（关节旋转）
        if "body_pose_params" in output:
            bp = to_numpy(output["body_pose_params"])
            person["body_pose_params"] = {
                "shape": list(bp.shape),
                "data": bp.tolist() if bp.size < 500 else "数据过大",
            }
        
        # 手部姿态参数
        if "hand_pose_params" in output:
            hp = to_numpy(output["hand_pose_params"])
            person["hand_pose_params"] = {
                "shape": list(hp.shape),
                "data": hp.tolist() if hp.size < 500 else "数据过大",
            }
        
        # 体型参数
        if "shape_params" in output:
            sp = to_numpy(output["shape_params"])
            person["shape_params"] = {
                "shape": list(sp.shape),
                "data": sp.tolist(),
            }
        
        # 缩放参数
        if "scale_params" in output:
            sc = to_numpy(output["scale_params"])
            person["scale_params"] = {
                "shape": list(sc.shape),
                "data": sc.tolist(),
            }
        
        # 表情参数
        if "expr_params" in output:
            ep = to_numpy(output["expr_params"])
            if ep is not None:
                person["expr_params"] = {
                    "shape": list(ep.shape),
                    "data": ep.tolist() if ep.size < 200 else "数据过大",
                }
        
        # 相机参数
        if "pred_cam_t" in output:
            person["pred_cam_t"] = to_numpy(output["pred_cam_t"]).tolist()
        if "focal_length" in output:
            focal = output["focal_length"]
            person["focal_length"] = float(focal) if np.isscalar(focal) else float(to_numpy(focal).flat[0])
        
        # 边界框
        if "bbox" in output:
            person["bbox"] = to_numpy(output["bbox"]).tolist()
        
        return person
    
    def visualize(
        self,
        image_input: Union[str, np.ndarray],
        outputs: List[Dict[str, Any]],
        show_skeleton: bool = True,
        show_mesh: bool = True,
    ) -> np.ndarray:
        """
        可视化结果
        
        Args:
            image_input: 原始图像
            outputs: process_image 的返回结果
            show_skeleton: 是否显示骨架
            show_mesh: 是否显示3D网格
            
        Returns:
            可视化后的图像 (BGR格式)
        """
        import cv2
        
        if isinstance(image_input, str):
            img_bgr = cv2.imread(image_input)
        else:
            img_bgr = image_input.copy()
        
        if not outputs:
            return img_bgr
        
        try:
            from sam_3d_body.visualization.renderer import Renderer
            from sam_3d_body.visualization.skeleton_visualizer import SkeletonVisualizer
            from sam_3d_body.metadata.mhr70 import pose_info as mhr70_pose_info
            
            LIGHT_BLUE = (0.65098039, 0.74117647, 0.85882353)
            
            result_images = [img_bgr.copy()]
            
            for person_output in outputs:
                focal_length = person_output["focal_length"]
                
                if show_mesh:
                    renderer = Renderer(focal_length=focal_length, faces=self.faces)
                    
                    # 网格叠加
                    img_mesh = (renderer(
                        person_output["pred_vertices"],
                        person_output["pred_cam_t"],
                        img_bgr.copy(),
                        mesh_base_color=LIGHT_BLUE,
                        scene_bg_color=(1, 1, 1),
                    ) * 255).astype(np.uint8)
                    result_images.append(img_mesh)
                
                if show_skeleton:
                    visualizer = SkeletonVisualizer(line_width=2, radius=5)
                    visualizer.set_pose_meta(mhr70_pose_info)
                    
                    keypoints_2d = person_output["pred_keypoints_2d"]
                    keypoints_2d_vis = np.concatenate(
                        [keypoints_2d, np.ones((keypoints_2d.shape[0], 1))], axis=-1
                    )
                    img_skeleton = visualizer.draw_skeleton(img_bgr.copy(), keypoints_2d_vis)
                    
                    # 画边界框
                    bbox = person_output["bbox"]
                    cv2.rectangle(
                        img_skeleton,
                        (int(bbox[0]), int(bbox[1])),
                        (int(bbox[2]), int(bbox[3])),
                        (0, 255, 0), 2
                    )
                    result_images.append(img_skeleton)
            
            # 拼接所有图像
            return np.concatenate(result_images, axis=1)
            
        except ImportError as e:
            print(f"可视化需要完整的 sam-3d-body 库: {e}")
            return img_bgr
    
    def save_mesh(
        self,
        outputs: List[Dict[str, Any]],
        output_dir: str,
        prefix: str = "mesh"
    ) -> List[str]:
        """
        保存3D网格为PLY文件
        
        Args:
            outputs: process_image 的返回结果
            output_dir: 输出目录
            prefix: 文件名前缀
            
        Returns:
            保存的PLY文件路径列表
        """
        os.makedirs(output_dir, exist_ok=True)
        ply_files = []
        
        try:
            from sam_3d_body.visualization.renderer import Renderer
            LIGHT_BLUE = (0.65098039, 0.74117647, 0.85882353)
            
            for i, person_output in enumerate(outputs):
                renderer = Renderer(
                    focal_length=person_output["focal_length"],
                    faces=self.faces
                )
                
                tmesh = renderer.vertices_to_trimesh(
                    person_output["pred_vertices"],
                    person_output["pred_cam_t"],
                    LIGHT_BLUE
                )
                
                mesh_path = os.path.join(output_dir, f"{prefix}_{i:03d}.ply")
                tmesh.export(mesh_path)
                ply_files.append(mesh_path)
                print(f"已保存网格: {mesh_path}")
                
        except ImportError as e:
            print(f"保存网格需要完整的 sam-3d-body 库: {e}")
        
        return ply_files


def print_result(result: dict, indent: int = 0):
    """递归打印结果"""
    prefix = "  " * indent
    for key, value in result.items():
        if isinstance(value, dict):
            print(f"{prefix}{key}:")
            print_result(value, indent + 1)
        elif isinstance(value, list):
            if len(value) > 0 and isinstance(value[0], dict):
                print(f"{prefix}{key}: [{len(value)} 项]")
                for i, item in enumerate(value):
                    print(f"{prefix}  [{i}]:")
                    print_result(item, indent + 2)
            elif len(value) > 20:
                print(f"{prefix}{key}: [列表共 {len(value)} 项]")
            else:
                print(f"{prefix}{key}: {value}")
        else:
            print(f"{prefix}{key}: {value}")


def main():
    """主函数示例"""
    import argparse
    import cv2
    import time
    
    parser = argparse.ArgumentParser(description="SAM 3D Body 人体3D网格恢复示例")
    parser.add_argument("--image", type=str, required=True, help="输入图像路径")
    parser.add_argument("--checkpoint", type=str, default=None, help="模型检查点路径")
    parser.add_argument("--mhr_path", type=str, default=None, help="MHR模型路径")
    parser.add_argument("--output", type=str, default=None, help="输出JSON文件路径")
    parser.add_argument("--output_image", type=str, default=None, help="可视化输出图像路径")
    parser.add_argument("--output_mesh_dir", type=str, default=None, help="输出网格目录")
    parser.add_argument("--no_detector", action="store_true", help="不使用人体检测器")
    args = parser.parse_args()
    
    print("=" * 60)
    print("SAM 3D Body - 3D 人体网格恢复")
    print("=" * 60)
    
    # 时间统计
    time_stats = {}
    total_start = time.time()
    
    # 初始化估计器（包含模型加载）
    t0 = time.time()
    estimator = SAM3DBodyEstimator(
        checkpoint_path=args.checkpoint,
        mhr_path=args.mhr_path,
        use_detector=not args.no_detector
    )
    time_stats["模型初始化"] = time.time() - t0
    
    print("\n正在处理图像...")
    print("-" * 60)
    
    # 处理图像（推理）
    t0 = time.time()
    outputs = estimator.process_image(args.image)
    time_stats["图像推理"] = time.time() - t0
    
    # 提取结构化数据
    t0 = time.time()
    result = estimator.process_and_extract(args.image)
    time_stats["数据提取"] = time.time() - t0
    
    # 打印结果
    print(f"\n检测到 {len(outputs)} 个人体")
    print("\n【检测结果】")
    print("-" * 60)
    print_result(result)
    
    # 保存JSON
    if args.output:
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
        
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(convert_to_serializable(result), f, indent=2, ensure_ascii=False)
        print(f"\n结果已保存到: {args.output}")
    
    # 可视化
    if args.output_image:
        t0 = time.time()
        vis_img = estimator.visualize(args.image, outputs)
        cv2.imwrite(args.output_image, vis_img)
        time_stats["可视化渲染"] = time.time() - t0
        print(f"可视化图像已保存到: {args.output_image}")
    
    # 保存网格
    if args.output_mesh_dir:
        t0 = time.time()
        mesh_files = estimator.save_mesh(outputs, args.output_mesh_dir)
        time_stats["网格保存"] = time.time() - t0
        print(f"共保存 {len(mesh_files)} 个网格文件")
    
    # 总时间
    time_stats["总耗时"] = time.time() - total_start
    
    # 打印时间统计
    print("\n" + "=" * 60)
    print("⏱️  时间统计")
    print("=" * 60)
    for step, duration in time_stats.items():
        if step == "总耗时":
            print("-" * 40)
        print(f"  {step}: {duration:.3f} 秒")
    
    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)
    
    return result, outputs


if __name__ == "__main__":
    main()
