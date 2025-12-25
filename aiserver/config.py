"""
AI 服务统一配置模块
从 config.yaml 加载配置，供网关和各服务使用
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

# 配置文件路径
CONFIG_PATH = Path(__file__).parent / "config.yaml"

_config: Optional[Dict[str, Any]] = None


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    global _config
    if _config is None:
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"配置文件不存在: {CONFIG_PATH}")
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def get_config() -> Dict[str, Any]:
    """获取配置（已缓存）"""
    return load_config()


def get_service_url(server: str, service: str) -> str:
    """
    获取服务完整 URL
    
    Args:
        server: 服务器名称 (embed_server_1, embed_server_2, vlm, trellis)
        service: 服务名称 (siglip2, embed_4b, embed_bge, etc.)
    
    Returns:
        完整 URL，如 http://192.168.0.100:6010
    """
    config = get_config()
    
    if server in ("vlm", "trellis"):
        # vlm 和 trellis 是顶级服务
        srv = config[server]
        return f"http://{srv['host']}:{srv['port']}"
    else:
        # embed_server_1, embed_server_2 下有多个服务
        srv = config[server]
        host = srv["host"]
        port = srv["services"][service]["port"]
        return f"http://{host}:{port}"


def get_service_port(server: str, service: str = None) -> int:
    """
    获取服务端口
    
    Args:
        server: 服务器名称
        service: 服务名称（对于 vlm, trellis 可以不传）
    """
    config = get_config()
    
    if server in ("vlm", "trellis", "gateway"):
        return config[server]["port"]
    else:
        return config[server]["services"][service]["port"]


def get_host(server: str) -> str:
    """获取服务器地址"""
    config = get_config()
    return config[server]["host"]


def get_default(key: str) -> str:
    """获取默认配置"""
    config = get_config()
    return config["defaults"][key]


def get_gateway_port() -> int:
    """获取网关端口"""
    config = get_config()
    return config["gateway"]["port"]


# =============================================================================
# 便捷函数：获取各服务 URL
# =============================================================================

def url_siglip2() -> str:
    return get_service_url("embed_server_1", "siglip2")

def url_embed_4b() -> str:
    return get_service_url("embed_server_1", "embed_4b")

def url_embed_bge() -> str:
    return get_service_url("embed_server_1", "embed_bge")

def url_rerank_4b() -> str:
    return get_service_url("embed_server_1", "rerank_4b")

def url_zimage() -> str:
    return get_service_url("embed_server_1", "zimage")

def url_embed_8b() -> str:
    return get_service_url("embed_server_2", "embed_8b")

def url_rerank_8b() -> str:
    return get_service_url("embed_server_2", "rerank_8b")

def url_vlm() -> str:
    return get_service_url("vlm", None)

def url_trellis() -> str:
    return get_service_url("trellis", None)


# =============================================================================
# 便捷函数：获取各服务端口
# =============================================================================

def port_siglip2() -> int:
    return get_service_port("embed_server_1", "siglip2")

def port_embed_4b() -> int:
    return get_service_port("embed_server_1", "embed_4b")

def port_embed_bge() -> int:
    return get_service_port("embed_server_1", "embed_bge")

def port_rerank_4b() -> int:
    return get_service_port("embed_server_1", "rerank_4b")

def port_zimage() -> int:
    return get_service_port("embed_server_1", "zimage")

def port_embed_8b() -> int:
    return get_service_port("embed_server_2", "embed_8b")

def port_rerank_8b() -> int:
    return get_service_port("embed_server_2", "rerank_8b")

def port_vlm() -> int:
    return get_service_port("vlm")

def port_trellis() -> int:
    return get_service_port("trellis")


# =============================================================================
# 便捷函数：获取模型路径
# =============================================================================

def model_path_embed_8b() -> str:
    config = get_config()
    return config["embed_server_2"]["services"]["embed_8b"]["model_path"]

def model_path_rerank_8b() -> str:
    config = get_config()
    return config["embed_server_2"]["services"]["rerank_8b"]["model_path"]


if __name__ == "__main__":
    # 测试配置加载
    print("配置文件:", CONFIG_PATH)
    print()
    print("服务 URL:")
    print(f"  SigLIP2:    {url_siglip2()}")
    print(f"  Embed-4B:   {url_embed_4b()}")
    print(f"  Embed-BGE:  {url_embed_bge()}")
    print(f"  Rerank-4B:  {url_rerank_4b()}")
    print(f"  Embed-8B:   {url_embed_8b()}")
    print(f"  Rerank-8B:  {url_rerank_8b()}")
    print(f"  VLM:        {url_vlm()}")
    print(f"  Z-Image:    {url_zimage()}")
    print(f"  Trellis:    {url_trellis()}")
    print()
    print("默认配置:")
    print(f"  文本嵌入:   {get_default('text_embedding')}")
    print(f"  重排序:     {get_default('rerank')}")
    print()
    print(f"网关端口:     {get_gateway_port()}")

