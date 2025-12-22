"""
嵌入服务客户端
调用嵌入服务 API 获取向量
"""
import requests
import numpy as np
from typing import List, Optional
from pathlib import Path
import base64
import yaml


class EmbeddingClient:
    """嵌入服务客户端"""
    
    def __init__(self, config_path: str = None):
        """
        初始化客户端
        
        Args:
            config_path: 配置文件路径，默认使用内置配置
        """
        self.config = self._load_config(config_path)
        self.image_service = self.config.get("defaults", {}).get("image_embedding", "siglip2_local")
        self.text_service = self.config.get("defaults", {}).get("text_embedding", "qwen3_embed_local")
    
    def _load_config(self, config_path: str = None) -> dict:
        """加载配置"""
        if config_path and Path(config_path).exists():
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        
        # 默认配置
        return {
            "services": {
                "siglip2_local": {
                    "model_name": "siglip2-so400m-patch16-512",
                    "model_version": "1.0",
                    "endpoint": "http://192.168.0.100:6010",
                    "dimension": 1152,
                    "timeout": 30
                },
                "qwen3_embed_local": {
                    "model_name": "Qwen3-4B",
                    "model_version": "1.0",
                    "endpoint": "http://192.168.0.100:6011",
                    "dimension": 2560,
                    "timeout": 10
                }
            },
            "defaults": {
                "image_embedding": "siglip2_local",
                "text_embedding": "qwen3_embed_local"
            }
        }
    
    def _get_service_config(self, service_name: str) -> dict:
        """获取服务配置"""
        return self.config.get("services", {}).get(service_name, {})
    
    def get_image_embedding(self, image_path: str = None, 
                           image_bytes: bytes = None) -> Optional[np.ndarray]:
        """
        获取图片嵌入向量
        
        Args:
            image_path: 图片路径
            image_bytes: 图片字节数据（二选一）
        
        Returns:
            嵌入向量
        """
        service = self._get_service_config(self.image_service)
        endpoint = service.get("endpoint")
        if not endpoint:
            raise ValueError(f"服务 {self.image_service} 缺少 endpoint 配置")
        timeout = service.get("timeout", 30)
        
        try:
            if image_path:
                # 上传文件方式
                with open(image_path, "rb") as f:
                    response = requests.post(
                        f"{endpoint}/embed/image",
                        files={"file": f},
                        timeout=timeout
                    )
            elif image_bytes:
                # Base64 方式
                image_base64 = base64.b64encode(image_bytes).decode("utf-8")
                response = requests.post(
                    f"{endpoint}/embed/image/base64",
                    json={"image_base64": image_base64},
                    timeout=timeout
                )
            else:
                raise ValueError("需要提供 image_path 或 image_bytes")
            
            response.raise_for_status()
            data = response.json()
            return np.array(data["embedding"], dtype=np.float32)
        
        except Exception as e:
            print(f"获取图片嵌入失败: {e}")
            return None
    
    def get_text_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        获取文本嵌入向量
        
        Args:
            text: 文本内容
        
        Returns:
            嵌入向量
        """
        service = self._get_service_config(self.text_service)
        endpoint = service.get("endpoint")
        if not endpoint:
            raise ValueError(f"服务 {self.text_service} 缺少 endpoint 配置")
        timeout = service.get("timeout", 10)
        
        try:
            response = requests.post(
                f"{endpoint}/embed/text",
                json={"text": text},
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            return np.array(data["embedding"], dtype=np.float32)
        
        except Exception as e:
            print(f"获取文本嵌入失败: {e}")
            return None
    
    def get_text_embeddings_batch(self, texts: List[str]) -> Optional[np.ndarray]:
        """
        批量获取文本嵌入向量
        
        Args:
            texts: 文本列表
        
        Returns:
            嵌入向量矩阵 (N, dimension)
        """
        service = self._get_service_config(self.text_service)
        endpoint = service.get("endpoint")
        if not endpoint:
            raise ValueError(f"服务 {self.text_service} 缺少 endpoint 配置")
        timeout = service.get("timeout", 10) * len(texts)  # 根据数量增加超时
        
        try:
            response = requests.post(
                f"{endpoint}/embed/texts",
                json={"texts": texts},
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            return np.array(data["embeddings"], dtype=np.float32)
        
        except Exception as e:
            print(f"获取批量文本嵌入失败: {e}")
            return None
    
    def check_image_service(self) -> bool:
        """检查图片嵌入服务是否可用"""
        service = self._get_service_config(self.image_service)
        endpoint = service.get("endpoint")
        if not endpoint:
            return False
        
        try:
            response = requests.get(f"{endpoint}/health", timeout=(2, 3))
            return response.status_code == 200
        except:
            return False
    
    def check_text_service(self) -> bool:
        """检查文本嵌入服务是否可用"""
        service = self._get_service_config(self.text_service)
        endpoint = service.get("endpoint")
        if not endpoint:
            return False
        
        try:
            response = requests.get(f"{endpoint}/health", timeout=(2, 3))
            return response.status_code == 200
        except:
            return False
    
    def get_image_service_info(self) -> dict:
        """获取图片嵌入服务信息"""
        return self._get_service_config(self.image_service)
    
    def get_text_service_info(self) -> dict:
        """获取文本嵌入服务信息"""
        return self._get_service_config(self.text_service)
    
    def get_all_text_services(self) -> List[dict]:
        """
        获取所有启用的文本嵌入服务
        
        Returns:
            服务配置列表，每个元素包含 service_name 和配置信息
        """
        services = []
        for name, config in self.config.get("services", {}).items():
            # 跳过图片嵌入服务（通过 endpoint 端口判断或模型名称）
            if "siglip" in name.lower() or "image" in name.lower():
                continue
            # 跳过未启用的服务
            if not config.get("is_enabled", True):
                continue
            services.append({
                "service_name": name,
                **config
            })
        return services
    
    def get_all_image_services(self) -> List[dict]:
        """
        获取所有启用的图片嵌入服务
        
        Returns:
            服务配置列表
        """
        services = []
        for name, config in self.config.get("services", {}).items():
            # 只选择图片嵌入服务
            if "siglip" in name.lower() or "image" in name.lower():
                if config.get("is_enabled", True):
                    services.append({
                        "service_name": name,
                        **config
                    })
        return services
    
    def get_text_embedding_by_service(self, text: str, service_name: str) -> Optional[np.ndarray]:
        """
        使用指定服务获取文本嵌入
        
        Args:
            text: 文本内容
            service_name: 服务名称
        
        Returns:
            嵌入向量
        """
        service = self._get_service_config(service_name)
        endpoint = service.get("endpoint")
        if not endpoint:
            print(f"服务 {service_name} 缺少 endpoint 配置")
            return None
        timeout = service.get("timeout", 30)
        
        try:
            response = requests.post(
                f"{endpoint}/embed/text",
                json={"text": text},
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            return np.array(data["embedding"], dtype=np.float32)
        except Exception as e:
            print(f"使用 {service_name} 获取文本嵌入失败: {e}")
            return None
    
    def get_all_text_embeddings(self, text: str) -> dict:
        """
        使用所有启用的文本嵌入服务获取嵌入
        
        Args:
            text: 文本内容
        
        Returns:
            字典 {service_name: {"embedding": np.ndarray, "model_name": str, "dimension": int}}
        """
        results = {}
        for service in self.get_all_text_services():
            service_name = service["service_name"]
            embedding = self.get_text_embedding_by_service(text, service_name)
            if embedding is not None:
                results[service_name] = {
                    "embedding": embedding,
                    "model_name": service.get("model_name"),
                    "model_version": service.get("model_version", "1.0"),
                    "dimension": service.get("dimension")
                }
        return results
    
    def get_index_config(self, index_name: str) -> Optional[dict]:
        """获取索引配置"""
        return self.config.get("indexes", {}).get(index_name)
    
    def get_service_for_model(self, model_name: str) -> Optional[str]:
        """根据模型名称查找服务"""
        for name, config in self.config.get("services", {}).items():
            if config.get("model_name") == model_name:
                return name
        return None
    
    def rerank(self, query: str, documents: List[str], top_k: int = None) -> Optional[List[dict]]:
        """
        使用 LLM 重排序
        
        Args:
            query: 用户查询
            documents: 候选文档列表
            top_k: 返回前 k 个结果
        
        Returns:
            重排序后的结果列表 [{"document": str, "score": float, "original_index": int}, ...]
        """
        rerank_config = self.config.get("services", {}).get("qwen3_rerank", {})
        if not rerank_config.get("is_enabled", False):
            print("重排序服务未启用")
            return None
        
        endpoint = rerank_config.get("endpoint")
        if not endpoint:
            print("重排序服务缺少 endpoint 配置")
            return None
        
        timeout = rerank_config.get("timeout", 60)
        
        try:
            payload = {"query": query, "documents": documents}
            if top_k:
                payload["top_k"] = top_k
            
            response = requests.post(
                f"{endpoint}/rerank",
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        
        except Exception as e:
            print(f"重排序失败: {e}")
            return None
    
    def check_rerank_service(self) -> bool:
        """检查重排序服务是否可用"""
        rerank_config = self.config.get("services", {}).get("qwen3_rerank", {})
        if not rerank_config.get("is_enabled", False):
            return False
        
        endpoint = rerank_config.get("endpoint")
        if not endpoint:
            return False
        
        try:
            response = requests.get(f"{endpoint}/health", timeout=(2, 3))
            return response.status_code == 200
        except:
            return False

