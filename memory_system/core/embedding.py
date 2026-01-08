"""
Embedding抽象层 - 支持多种embedding服务

支持的后端：
1. RemoteHTTP - 远程HTTP服务（如你的BGE服务）
2. Local - 本地sentence-transformers模型
3. ChromaDB - ChromaDB内置embedding
"""

from abc import ABC, abstractmethod
from typing import List, Union
import numpy as np
import httpx
from dataclasses import dataclass


@dataclass
class EmbeddingResult:
    """Embedding结果"""
    embeddings: np.ndarray  # shape: (n, dimension)
    dimension: int
    model: str

    def to_list(self) -> List[List[float]]:
        """转换为列表格式"""
        return self.embeddings.tolist()


class EmbeddingProvider(ABC):
    """Embedding提供者抽象基类"""

    @abstractmethod
    def embed(self, texts: Union[str, List[str]]) -> EmbeddingResult:
        """
        嵌入文本

        Args:
            texts: 单个文本或文本列表

        Returns:
            EmbeddingResult对象
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """获取embedding维度"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """健康检查"""
        pass

    def _ensure_list(self, texts: Union[str, List[str]]) -> List[str]:
        """确保输入是列表"""
        if isinstance(texts, str):
            return [texts]
        return texts


class RemoteHTTPEmbedding(EmbeddingProvider):
    """
    远程HTTP Embedding服务

    支持你的BGE服务：http://192.168.0.100:6012
    """

    def __init__(
        self,
        base_url: str = "http://192.168.0.100:6012",
        timeout: float = 30.0,
        batch_size: int = 32
    ):
        """
        Args:
            base_url: 服务地址
            timeout: 超时时间（秒）
            batch_size: 批量处理大小
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.batch_size = batch_size
        self.client = httpx.Client(timeout=timeout)

        # 检查服务可用性
        if not self.health_check():
            print(f"警告: Embedding服务 {base_url} 不可用")

    def embed(self, texts: Union[str, List[str]]) -> EmbeddingResult:
        """调用远程服务进行embedding"""
        texts = self._ensure_list(texts)

        # 分批处理
        if len(texts) <= self.batch_size:
            return self._embed_batch(texts)

        # 大批量：分批请求并合并
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            result = self._embed_batch(batch)
            all_embeddings.append(result.embeddings)

        embeddings = np.vstack(all_embeddings)
        return EmbeddingResult(
            embeddings=embeddings,
            dimension=result.dimension,
            model=result.model
        )

    def _embed_batch(self, texts: List[str]) -> EmbeddingResult:
        """单批次embedding"""
        if len(texts) == 1:
            # 单个文本
            response = self.client.post(
                f"{self.base_url}/embed/text",
                json={"text": texts[0]}
            )
            response.raise_for_status()
            data = response.json()

            embeddings = np.array([data["embedding"]])
            dimension = data["dimension"]
            model = data["model"]
        else:
            # 批量文本
            response = self.client.post(
                f"{self.base_url}/embed/texts",
                json={"texts": texts}
            )
            response.raise_for_status()
            data = response.json()

            embeddings = np.array(data["embeddings"])
            dimension = data["dimension"]
            model = data["model"]

        return EmbeddingResult(
            embeddings=embeddings,
            dimension=dimension,
            model=model
        )

    def get_dimension(self) -> int:
        """从服务获取维度"""
        try:
            response = self.client.get(f"{self.base_url}/health")
            response.raise_for_status()
            return response.json()["dimension"]
        except Exception as e:
            print(f"获取维度失败: {e}")
            return 1024  # BGE-Large默认维度

    def health_check(self) -> bool:
        """检查服务是否可用"""
        try:
            response = self.client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            return response.status_code == 200
        except Exception:
            return False

    def __del__(self):
        """关闭HTTP客户端"""
        self.client.close()


class LocalEmbedding(EmbeddingProvider):
    """
    本地Embedding模型

    使用sentence-transformers
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        """
        Args:
            model_name: 模型名称
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "需要安装 sentence-transformers: "
                "pip install sentence-transformers"
            )

        print(f"加载本地Embedding模型: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self._dimension = self.model.get_sentence_embedding_dimension()

    def embed(self, texts: Union[str, List[str]]) -> EmbeddingResult:
        """本地embedding"""
        texts = self._ensure_list(texts)

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,  # 归一化
            show_progress_bar=False
        )

        # 确保是numpy数组
        if not isinstance(embeddings, np.ndarray):
            embeddings = np.array(embeddings)

        # 确保是2D数组
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)

        return EmbeddingResult(
            embeddings=embeddings,
            dimension=self._dimension,
            model=self.model_name
        )

    def get_dimension(self) -> int:
        """获取维度"""
        return self._dimension

    def health_check(self) -> bool:
        """本地模型总是可用"""
        return True


class ChromaDBEmbedding(EmbeddingProvider):
    """
    ChromaDB内置Embedding

    最简单的选项，无需额外配置
    """

    def __init__(self):
        """使用ChromaDB默认embedding函数"""
        try:
            from chromadb.utils import embedding_functions
        except ImportError:
            raise ImportError(
                "需要安装 chromadb: pip install chromadb"
            )

        # 使用默认的sentence-transformers函数
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self._dimension = 384  # all-MiniLM-L6-v2 的维度

    def embed(self, texts: Union[str, List[str]]) -> EmbeddingResult:
        """使用ChromaDB的embedding"""
        texts = self._ensure_list(texts)

        embeddings = self.embedding_fn(texts)
        embeddings = np.array(embeddings)

        return EmbeddingResult(
            embeddings=embeddings,
            dimension=self._dimension,
            model="chromadb-default"
        )

    def get_dimension(self) -> int:
        """获取维度"""
        return self._dimension

    def health_check(self) -> bool:
        """ChromaDB内置总是可用"""
        return True


class EmbeddingFactory:
    """Embedding工厂：根据配置创建相应的provider"""

    @staticmethod
    def create(config: dict) -> EmbeddingProvider:
        """
        根据配置创建embedding provider

        Args:
            config: 配置字典
                {
                    "provider": "remote" | "local" | "chromadb",
                    "remote": {
                        "base_url": "http://192.168.0.100:6012",
                        "timeout": 30.0
                    },
                    "local": {
                        "model_name": "BAAI/bge-small-zh-v1.5"
                    }
                }

        Returns:
            EmbeddingProvider实例
        """
        provider_type = config.get("provider", "remote")

        if provider_type == "remote":
            remote_config = config.get("remote", {})
            return RemoteHTTPEmbedding(
                base_url=remote_config.get("base_url", "http://192.168.0.100:6012"),
                timeout=remote_config.get("timeout", 30.0),
                batch_size=remote_config.get("batch_size", 32)
            )

        elif provider_type == "local":
            local_config = config.get("local", {})
            return LocalEmbedding(
                model_name=local_config.get("model_name", "BAAI/bge-small-zh-v1.5")
            )

        elif provider_type == "chromadb":
            return ChromaDBEmbedding()

        else:
            raise ValueError(f"不支持的provider类型: {provider_type}")


# 便捷函数
def create_embedding_provider(
    provider: str = "remote",
    **kwargs
) -> EmbeddingProvider:
    """
    快速创建embedding provider

    Examples:
        # 使用远程服务（推荐）
        emb = create_embedding_provider("remote", base_url="http://192.168.0.100:6012")

        # 使用本地模型
        emb = create_embedding_provider("local", model_name="BAAI/bge-small-zh-v1.5")

        # 使用ChromaDB内置
        emb = create_embedding_provider("chromadb")
    """
    config = {"provider": provider}

    if provider == "remote":
        config["remote"] = kwargs
    elif provider == "local":
        config["local"] = kwargs

    return EmbeddingFactory.create(config)


if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试Embedding提供者")
    print("=" * 60)

    texts = ["这是第一句话", "这是第二句话", "这是第三句话"]

    # 测试1: 远程HTTP服务
    print("\n1. 测试远程HTTP服务 (BGE)")
    try:
        remote_emb = create_embedding_provider(
            "remote",
            base_url="http://192.168.0.100:6012"
        )

        if remote_emb.health_check():
            print(f"   ✓ 服务可用")
            print(f"   维度: {remote_emb.get_dimension()}")

            result = remote_emb.embed(texts)
            print(f"   ✓ Embedding成功")
            print(f"   形状: {result.embeddings.shape}")
            print(f"   模型: {result.model}")
        else:
            print(f"   ✗ 服务不可用")
    except Exception as e:
        print(f"   ✗ 错误: {e}")

    # 测试2: 本地模型
    print("\n2. 测试本地模型")
    try:
        local_emb = create_embedding_provider(
            "local",
            model_name="BAAI/bge-small-zh-v1.5"
        )

        print(f"   ✓ 模型加载成功")
        print(f"   维度: {local_emb.get_dimension()}")

        result = local_emb.embed(texts)
        print(f"   ✓ Embedding成功")
        print(f"   形状: {result.embeddings.shape}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")

    # 测试3: ChromaDB内置
    print("\n3. 测试ChromaDB内置")
    try:
        chroma_emb = create_embedding_provider("chromadb")

        print(f"   ✓ ChromaDB准备就绪")
        print(f"   维度: {chroma_emb.get_dimension()}")

        result = chroma_emb.embed(texts)
        print(f"   ✓ Embedding成功")
        print(f"   形状: {result.embeddings.shape}")
    except Exception as e:
        print(f"   ✗ 错误: {e}")

    print("\n" + "=" * 60)
