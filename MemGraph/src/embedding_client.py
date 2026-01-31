"""
嵌入服务客户端
调用 AI Gateway 的嵌入服务
"""
import httpx
from typing import List
import numpy as np
from .config import EMBED_SERVICE_URL, EMBED_DIMENSION, EMBED_FULL_DIMENSION


class EmbeddingClient:
    """嵌入服务客户端"""

    def __init__(self, service_url: str = EMBED_SERVICE_URL):
        self.service_url = service_url
        self.client = httpx.AsyncClient(timeout=300.0)

    async def embed_text(self, text: str, instruction: str = None) -> np.ndarray:
        """
        生成单个文本的嵌入向量

        Args:
            text: 输入文本
            instruction: 可选的指令前缀

        Returns:
            嵌入向量 (numpy array)
        """
        payload = {"text": text}
        if instruction:
            payload["instruction"] = instruction

        try:
            response = await self.client.post(self.service_url, json=payload)
            response.raise_for_status()

            data = response.json()

            # 从响应中提取嵌入向量
            # 检查多种可能的响应格式
            embedding = None

            if "embedding" in data:
                embedding = data["embedding"]
            elif "embeddings" in data:
                emb_data = data["embeddings"]
                if isinstance(emb_data, list) and len(emb_data) > 0:
                    embedding = emb_data[0] if isinstance(emb_data[0], list) else emb_data
                else:
                    embedding = emb_data
            elif isinstance(data, list):
                # 如果直接是列表
                embedding = data
            else:
                raise ValueError(f"Unknown response format: {list(data.keys())}")

            if embedding is None or len(embedding) == 0:
                raise ValueError("Empty embedding returned")

            embedding_array = np.array(embedding, dtype=np.float32)

            # 验证维度（服务返回的是4096维）
            if len(embedding_array) != EMBED_FULL_DIMENSION:
                raise ValueError(f"Embedding dimension mismatch: expected {EMBED_FULL_DIMENSION}, got {len(embedding_array)}")

            # 验证不是全零向量
            if np.all(embedding_array == 0):
                raise ValueError("Received all-zero embedding vector")

            # 降维到512维以节省存储和计算
            if len(embedding_array) > EMBED_DIMENSION:
                embedding_array = embedding_array[:EMBED_DIMENSION]

            return embedding_array

        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            print(f"❌ Request Error: {e} - Is AI Gateway running at {self.service_url}?")
            raise
        except Exception as e:
            print(f"❌ Embedding service error: {e}")
            raise

    async def embed_texts(self, texts: List[str], instruction: str = None) -> np.ndarray:
        """
        批量生成文本嵌入向量

        Args:
            texts: 文本列表
            instruction: 可选的指令前缀

        Returns:
            嵌入向量矩阵 (n x dimension)
        """
        embeddings = []
        for text in texts:
            embedding = await self.embed_text(text, instruction)
            embeddings.append(embedding)

        return np.array(embeddings, dtype=np.float32)

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
