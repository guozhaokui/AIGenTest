"""
文件存储管理模块
管理图片文件的存储、缩略图生成等
"""
import hashlib
import shutil
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import numpy as np


class StorageManager:
    """文件存储管理器"""
    
    def __init__(self, storage_root: str, thumbnail_size: Tuple[int, int] = (256, 256)):
        self.storage_root = Path(storage_root)
        self.thumbnail_size = thumbnail_size
        self.storage_root.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """计算文件的 SHA256 哈希值（取前32位）"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()[:32]
    
    @staticmethod
    def compute_sha256_from_bytes(data: bytes) -> str:
        """从字节数据计算 SHA256"""
        return hashlib.sha256(data).hexdigest()[:32]
    
    def get_image_dir(self, sha256: str) -> Path:
        """根据 SHA256 获取图片存储目录"""
        # xx/yy/zzzzzzzzzzzzzzzzzzzzzzzzzzzz/
        return self.storage_root / sha256[:2] / sha256[2:4] / sha256[4:]
    
    def get_image_path(self, sha256: str) -> Path:
        """获取原始图片路径"""
        image_dir = self.get_image_dir(sha256)
        # 查找图片文件
        for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
            path = image_dir / f"image{ext}"
            if path.exists():
                return path
        return image_dir / "image.png"  # 默认路径
    
    def get_thumbnail_path(self, sha256: str) -> Path:
        """获取缩略图路径"""
        return self.get_image_dir(sha256) / "thumbnail.jpg"
    
    def get_description_path(self, sha256: str, method: str) -> Path:
        """获取描述文件路径"""
        return self.get_image_dir(sha256) / "description" / f"{method}.txt"
    
    def get_embedding_path(self, sha256: str, method: str) -> Path:
        """获取嵌入向量路径"""
        return self.get_image_dir(sha256) / "embedding" / f"{method}.npy"
    
    def save_image(self, source_path: str, sha256: str) -> Tuple[Path, dict]:
        """
        保存图片到存储目录
        
        Returns:
            (图片路径, 图片元信息)
        """
        image_dir = self.get_image_dir(sha256)
        image_dir.mkdir(parents=True, exist_ok=True)
        (image_dir / "description").mkdir(exist_ok=True)
        (image_dir / "embedding").mkdir(exist_ok=True)
        
        # 读取图片获取元信息
        with Image.open(source_path) as img:
            width, height = img.size
            format_name = img.format or "PNG"
            
            # 确定保存格式
            ext = f".{format_name.lower()}"
            if ext == ".jpeg":
                ext = ".jpg"
            
            # 保存原图
            dest_path = image_dir / f"image{ext}"
            if source_path != str(dest_path):
                shutil.copy2(source_path, dest_path)
            
            # 生成缩略图
            self._generate_thumbnail(img, sha256)
        
        # 获取文件大小
        file_size = dest_path.stat().st_size
        
        meta = {
            "width": width,
            "height": height,
            "format": format_name,
            "file_size": file_size
        }
        
        return dest_path, meta
    
    def save_image_from_bytes(self, data: bytes, sha256: str) -> Tuple[Path, dict]:
        """从字节数据保存图片"""
        from io import BytesIO
        
        image_dir = self.get_image_dir(sha256)
        image_dir.mkdir(parents=True, exist_ok=True)
        (image_dir / "description").mkdir(exist_ok=True)
        (image_dir / "embedding").mkdir(exist_ok=True)
        
        # 读取图片
        with Image.open(BytesIO(data)) as img:
            width, height = img.size
            format_name = img.format or "PNG"
            
            ext = f".{format_name.lower()}"
            if ext == ".jpeg":
                ext = ".jpg"
            
            # 保存原图
            dest_path = image_dir / f"image{ext}"
            with open(dest_path, "wb") as f:
                f.write(data)
            
            # 生成缩略图
            self._generate_thumbnail(img, sha256)
        
        file_size = len(data)
        
        meta = {
            "width": width,
            "height": height,
            "format": format_name,
            "file_size": file_size
        }
        
        return dest_path, meta
    
    def _generate_thumbnail(self, img: Image.Image, sha256: str):
        """生成缩略图"""
        thumbnail_path = self.get_thumbnail_path(sha256)
        
        # 创建缩略图
        thumb = img.copy()
        thumb.thumbnail(self.thumbnail_size, Image.Resampling.LANCZOS)
        
        # 转换为 RGB（处理 RGBA 或其他模式）
        if thumb.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', thumb.size, (255, 255, 255))
            if thumb.mode == 'P':
                thumb = thumb.convert('RGBA')
            background.paste(thumb, mask=thumb.split()[-1] if thumb.mode == 'RGBA' else None)
            thumb = background
        elif thumb.mode != 'RGB':
            thumb = thumb.convert('RGB')
        
        thumb.save(thumbnail_path, "JPEG", quality=85)
    
    def save_description(self, sha256: str, method: str, content: str):
        """保存描述文本"""
        desc_path = self.get_description_path(sha256, method)
        desc_path.parent.mkdir(parents=True, exist_ok=True)
        desc_path.write_text(content, encoding="utf-8")
    
    def get_description(self, sha256: str, method: str) -> Optional[str]:
        """读取描述文本"""
        desc_path = self.get_description_path(sha256, method)
        if desc_path.exists():
            return desc_path.read_text(encoding="utf-8")
        return None
    
    def save_embedding(self, sha256: str, method: str, embedding: np.ndarray):
        """保存嵌入向量"""
        emb_path = self.get_embedding_path(sha256, method)
        emb_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(emb_path, embedding)
    
    def get_embedding(self, sha256: str, method: str) -> Optional[np.ndarray]:
        """读取嵌入向量"""
        emb_path = self.get_embedding_path(sha256, method)
        if emb_path.exists():
            return np.load(emb_path)
        return None
    
    def delete_image_dir(self, sha256: str) -> bool:
        """删除图片目录"""
        image_dir = self.get_image_dir(sha256)
        if image_dir.exists():
            shutil.rmtree(image_dir)
            return True
        return False
    
    def image_exists(self, sha256: str) -> bool:
        """检查图片文件是否存在"""
        return self.get_image_path(sha256).exists()
    
    def get_thumbnail_bytes(self, sha256: str) -> Optional[bytes]:
        """获取缩略图字节数据"""
        thumb_path = self.get_thumbnail_path(sha256)
        if thumb_path.exists():
            return thumb_path.read_bytes()
        return None
    
    def get_image_bytes(self, sha256: str) -> Optional[bytes]:
        """获取原图字节数据"""
        image_path = self.get_image_path(sha256)
        if image_path.exists():
            return image_path.read_bytes()
        return None

