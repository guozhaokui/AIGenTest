"""
SAM 3D Body - 3D人体网格恢复模块

模型: facebook/sam-3d-body-dinov3
功能: 从单张图片恢复3D人体网格、姿态、关键点等信息

输出包含:
- pred_vertices: 3D网格顶点坐标 [N, 3]
- pred_keypoints_3d: 3D姿态关键点
- pred_keypoints_2d: 2D姿态关键点(投影到图像)
- pred_cam_t: 相机平移参数
- focal_length: 估计的焦距
- bbox: 人体边界框

使用方法:
    from aiserver.sam3d import SAM3DBodyEstimator
    
    estimator = SAM3DBodyEstimator()
    outputs = estimator.process_image("image.jpg")
    result = estimator.process_and_extract("image.jpg")
"""

from .sam3d_body_demo import SAM3DBodyEstimator, print_result

__all__ = ["SAM3DBodyEstimator", "print_result"]

