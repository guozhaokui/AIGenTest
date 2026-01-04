"""
嵌入服务客户端
调用嵌入服务 API 获取向量

配置源：统一从 aiserver/config.yaml 读取服务地址
本地配置（embedding_services.yaml）仅用于索引定义和 VLM 提示词等
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
            config_path: 本地配置文件路径（用于索引、VLM 等）
        """
        # 加载统一的服务配置（aiserver/config.yaml）
        self.ai_config = self._load_ai_config()
        # 加载本地配置（索引、VLM 等）
        self.local_config = self._load_local_config(config_path)
        # 合并生成 services 配置
        self.config = self._build_services_config()
        
        # 设置默认服务
        defaults = self.ai_config.get("defaults", {})
        self.image_service = self._map_service_name(defaults.get("image_embedding", "siglip2"))
        self.text_service = self._map_service_name(defaults.get("text_embedding", "embed_8b"))
    
    def _load_ai_config(self) -> dict:
        """加载 aiserver/config.yaml（统一服务配置）"""
        # 查找 aiserver/config.yaml
        current_dir = Path(__file__).parent
        possible_paths = [
            current_dir.parent.parent / "aiserver" / "config.yaml",  # imagemgr/src -> 项目根目录
            Path("/home/layabox/laya/guo/AIGenTest/aiserver/config.yaml"),  # 绝对路径
        ]
        
        for path in possible_paths:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    print(f"[EmbeddingClient] 加载服务配置: {path}")
                    return config
        
        print("[EmbeddingClient] 警告: 未找到 aiserver/config.yaml，使用默认配置")
        return {}
    
    def _load_local_config(self, config_path: str = None) -> dict:
        """加载本地配置（索引、VLM 提示词等）"""
        if config_path and Path(config_path).exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}
    
    def _build_services_config(self) -> dict:
        """从 ai_config 构建 services 配置（兼容旧格式）"""
        services = {}
        
        # 从 embed_server_1 构建
        server1 = self.ai_config.get("embed_server_1", {})
        host1 = server1.get("host", "192.168.0.100")
        for svc_name, svc_config in server1.get("services", {}).items():
            internal_name = self._map_service_name(svc_name)
            services[internal_name] = {
                "model_name": svc_config.get("model_name", svc_name),
                "model_version": svc_config.get("model_version", "1.0"),
                "endpoint": f"http://{host1}:{svc_config.get('port')}",
                "dimension": svc_config.get("dimension"),
                "timeout": svc_config.get("timeout", 30),
                "is_enabled": True
            }
        
        # 从 embed_server_2 构建
        server2 = self.ai_config.get("embed_server_2", {})
        host2 = server2.get("host", "192.168.0.132")
        for svc_name, svc_config in server2.get("services", {}).items():
            internal_name = self._map_service_name(svc_name)
            services[internal_name] = {
                "model_name": svc_config.get("model_name", svc_name),
                "model_version": svc_config.get("model_version", "1.0"),
                "endpoint": f"http://{host2}:{svc_config.get('port')}",
                "dimension": svc_config.get("dimension"),
                "timeout": svc_config.get("timeout", 30),
                "is_enabled": True
            }
        
        # 合并本地配置中的额外信息（如 VLM 等）
        local_services = self.local_config.get("services", {})
        for name, config in local_services.items():
            if name not in services:
                services[name] = config
        
        return {
            "services": services,
            "defaults": self.ai_config.get("defaults", {}),
            "indexes": self.local_config.get("indexes", {}),
            "vlm_services": self.local_config.get("vlm_services", {}),
            "vlm": self.local_config.get("vlm", {})
        }
    
    def _map_service_name(self, name: str) -> str:
        """将 aiserver 服务名映射到内部服务名"""
        mapping = {
            "siglip2": "siglip2_local",
            "embed_4b": "qwen3_embed_local",
            "embed_bge": "bge_local",
            "rerank_4b": "qwen3_rerank",
            "embed_8b": "qwen3_8b_embed",
            "rerank_8b": "qwen3_8b_rerank",
        }
        return mapping.get(name, name)
    
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
    
    def get_all_text_services(self, include_siglip: bool = False) -> List[dict]:
        """
        获取所有启用的文本嵌入服务
        
        Args:
            include_siglip: 是否包含 SigLIP2 服务（用于跨模态搜索）
        
        Returns:
            服务配置列表，每个元素包含 service_name 和配置信息
        """
        services = []
        for name, config in self.config.get("services", {}).items():
            # 跳过图片专用服务（除非明确包含 SigLIP2）
            if "siglip" in name.lower():
                if not include_siglip:
                    continue
            # 跳过其他图片服务
            if "image" in name.lower():
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
    
    def get_text_embedding_by_service(self, text: str, service_name: str, 
                                       instruction: str = None, is_query: bool = True) -> Optional[np.ndarray]:
        """
        使用指定服务获取文本嵌入
        
        Args:
            text: 文本内容
            service_name: 服务名称
            instruction: 任务指令（仅对支持 instruction 的模型如 Qwen3-Embedding-8B 有效）
            is_query: True 表示是查询，False 表示是文档
        
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
            # 构建请求体
            payload = {"text": text, "is_query": is_query}
            if instruction:
                payload["instruction"] = instruction
            
            response = requests.post(
                f"{endpoint}/embed/text",
                json=payload,
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            return np.array(data["embedding"], dtype=np.float32)
        except Exception as e:
            print(f"使用 {service_name} 获取文本嵌入失败: {e}")
            return None
    
    def get_all_text_embeddings(self, text: str, is_query: bool = False) -> dict:
        """
        使用所有启用的文本嵌入服务获取嵌入
        
        Args:
            text: 文本内容
            is_query: True 表示是查询，False 表示是文档（默认 False，因为通常用于存储描述）
        
        Returns:
            字典 {service_name: {"embedding": np.ndarray, "model_name": str, "dimension": int}}
        """
        results = {}
        for service in self.get_all_text_services():
            service_name = service["service_name"]
            # 对于文档嵌入，不需要 instruction
            embedding = self.get_text_embedding_by_service(
                text, service_name, instruction=None, is_query=is_query
            )
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
        使用 LLM 重排序（优先使用 8B 模型）
        
        Args:
            query: 用户查询
            documents: 候选文档列表
            top_k: 返回前 k 个结果
        
        Returns:
            重排序后的结果列表 [{"document": str, "score": float, "original_index": int}, ...]
        """
        # 优先使用 8B rerank，然后尝试 4B
        rerank_services = ["qwen3_8b_rerank", "qwen3_rerank"]
        
        for service_name in rerank_services:
            rerank_config = self.config.get("services", {}).get(service_name, {})
            if not rerank_config.get("is_enabled", False):
                continue
            
            endpoint = rerank_config.get("endpoint")
            if not endpoint:
                continue
            
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
                print(f"[Rerank] 使用 {service_name} 成功")
                return data.get("results", [])
            
            except Exception as e:
                print(f"[Rerank] {service_name} 失败: {e}")
                continue
        
        print("所有重排序服务都不可用")
        return None
    
    def check_rerank_service(self) -> bool:
        """检查重排序服务是否可用（优先检查 8B）"""
        for service_name in ["qwen3_8b_rerank", "qwen3_rerank"]:
            rerank_config = self.config.get("services", {}).get(service_name, {})
            if not rerank_config.get("is_enabled", False):
                continue
            
            endpoint = rerank_config.get("endpoint")
            if not endpoint:
                continue
            
            try:
                response = requests.get(f"{endpoint}/health", timeout=(2, 3))
                if response.status_code == 200:
                    return True
            except:
                continue
        return False

