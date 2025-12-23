#!/usr/bin/env python3
"""
Qwen3-VL VLM 服务测试客户端

使用方法:
    python test_client.py --image test.jpg "描述这张图片"
    python test_client.py "你好"
    python test_client.py --interactive
"""

import argparse
import base64
import json
import requests
from pathlib import Path


def encode_image_to_base64(image_path: str) -> str:
    """将本地图片编码为 base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def get_image_mime_type(image_path: str) -> str:
    """根据文件扩展名获取 MIME 类型"""
    ext = Path(image_path).suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return mime_types.get(ext, "image/jpeg")


def chat(prompt: str, image: str = None, api_url: str = "http://localhost:6050/v1/chat/completions", **kwargs) -> str:
    """发送聊天请求"""
    
    content = []
    
    if image:
        if image.startswith("http://") or image.startswith("https://"):
            content.append({
                "type": "image_url",
                "image_url": {"url": image}
            })
        else:
            if not Path(image).exists():
                raise FileNotFoundError(f"图片不存在: {image}")
            
            mime_type = get_image_mime_type(image)
            base64_data = encode_image_to_base64(image)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{base64_data}"}
            })
    
    content.append({"type": "text", "text": prompt})
    
    payload = {
        "model": "qwen3-vl",
        "messages": [{"role": "user", "content": content}],
        "max_tokens": kwargs.get("max_tokens", 1024),
        "temperature": kwargs.get("temperature", 0.7),
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.exceptions.ConnectionError:
        raise ConnectionError(f"无法连接服务器 {api_url}\n请先启动服务: ./start.sh")


def interactive_mode(api_url: str):
    """交互式模式"""
    print("=" * 50)
    print("🤖 Qwen3-VL 交互式聊天")
    print("=" * 50)
    print("命令: /image <路径> | /clear | /quit")
    print("=" * 50)
    
    current_image = None
    
    while True:
        try:
            user_input = input("\n你: ").strip()
            
            if not user_input:
                continue
            
            if user_input == "/quit":
                print("再见! 👋")
                break
            
            if user_input == "/clear":
                current_image = None
                print("✅ 已清除图片")
                continue
            
            if user_input.startswith("/image "):
                path = user_input[7:].strip()
                if Path(path).exists() or path.startswith("http"):
                    current_image = path
                    print(f"✅ 图片: {path}")
                else:
                    print(f"❌ 找不到: {path}")
                continue
            
            print("\n助手: ", end="", flush=True)
            response = chat(user_input, current_image, api_url)
            print(response)
            
        except KeyboardInterrupt:
            print("\n再见! 👋")
            break
        except Exception as e:
            print(f"❌ 错误: {e}")


def main():
    parser = argparse.ArgumentParser(description="Qwen3-VL 测试客户端")
    parser.add_argument("prompt", nargs="?", help="提示文本")
    parser.add_argument("--image", "-i", help="图片路径或URL")
    parser.add_argument("--api-url", default="http://localhost:6050/v1/chat/completions")
    parser.add_argument("--interactive", action="store_true", help="交互模式")
    
    args = parser.parse_args()
    
    if args.interactive:
        interactive_mode(args.api_url)
    elif args.prompt:
        try:
            response = chat(args.prompt, args.image, args.api_url)
            print(f"\n助手: {response}\n")
        except Exception as e:
            print(f"❌ 错误: {e}")
            exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
