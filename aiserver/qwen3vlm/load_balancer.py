#!/usr/bin/env python3
"""
VLM 服务负载均衡器
将请求分发到多个后端实例

使用方法:
    python load_balancer.py --port 6050 --backends 6051,6052,6053,6054
"""

import argparse
import asyncio
import time
from collections import deque
from typing import List, Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


class Backend:
    """后端实例"""
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.url = f"http://{host}:{port}"
        self.active_requests = 0
        self.total_requests = 0
        self.total_latency = 0.0
        self.healthy = True
        self.last_check = 0
    
    @property
    def avg_latency(self) -> float:
        if self.total_requests == 0:
            return 0
        return self.total_latency / self.total_requests
    
    def __repr__(self):
        return f"Backend({self.url}, active={self.active_requests}, healthy={self.healthy})"


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, backends: List[Backend]):
        self.backends = backends
        self.current_index = 0
        self.client = httpx.AsyncClient(timeout=300.0)
    
    def get_backend(self) -> Optional[Backend]:
        """
        选择一个后端（最少连接算法）
        """
        healthy_backends = [b for b in self.backends if b.healthy]
        
        if not healthy_backends:
            return None
        
        # 选择活跃请求最少的后端
        return min(healthy_backends, key=lambda b: b.active_requests)
    
    async def health_check(self):
        """健康检查"""
        for backend in self.backends:
            try:
                response = await self.client.get(f"{backend.url}/", timeout=5.0)
                backend.healthy = response.status_code == 200
            except Exception:
                backend.healthy = False
            backend.last_check = time.time()
    
    async def forward_request(self, request: Request, path: str) -> Response:
        """转发请求到后端"""
        backend = self.get_backend()
        
        if not backend:
            raise HTTPException(status_code=503, detail="所有后端都不可用")
        
        backend.active_requests += 1
        start_time = time.time()
        
        try:
            # 读取请求体
            body = await request.body()
            
            # 构建请求
            url = f"{backend.url}{path}"
            headers = dict(request.headers)
            headers.pop("host", None)
            
            # 转发请求
            response = await self.client.request(
                method=request.method,
                url=url,
                headers=headers,
                content=body,
                params=request.query_params,
            )
            
            # 记录统计
            latency = time.time() - start_time
            backend.total_requests += 1
            backend.total_latency += latency
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
            
        except httpx.TimeoutException:
            backend.healthy = False
            raise HTTPException(status_code=504, detail="后端超时")
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e))
        finally:
            backend.active_requests -= 1


# 全局负载均衡器
lb: Optional[LoadBalancer] = None

app = FastAPI(title="VLM Load Balancer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """状态信息"""
    return {
        "message": "VLM Load Balancer",
        "backends": [
            {
                "url": b.url,
                "healthy": b.healthy,
                "active_requests": b.active_requests,
                "total_requests": b.total_requests,
                "avg_latency_ms": round(b.avg_latency * 1000, 2)
            }
            for b in lb.backends
        ],
        "endpoints": {
            "caption": "/caption",
            "chat": "/v1/chat/completions",
            "status": "/lb/status"
        }
    }


@app.get("/lb/status")
async def lb_status():
    """负载均衡器状态"""
    await lb.health_check()
    
    return {
        "healthy_backends": sum(1 for b in lb.backends if b.healthy),
        "total_backends": len(lb.backends),
        "backends": [
            {
                "url": b.url,
                "healthy": b.healthy,
                "active_requests": b.active_requests,
                "total_requests": b.total_requests,
                "avg_latency_ms": round(b.avg_latency * 1000, 2)
            }
            for b in lb.backends
        ]
    }


@app.api_route("/caption", methods=["POST"])
async def proxy_caption(request: Request):
    """转发 caption 请求"""
    return await lb.forward_request(request, "/caption")


@app.api_route("/v1/chat/completions", methods=["POST"])
async def proxy_chat(request: Request):
    """转发 chat 请求"""
    return await lb.forward_request(request, "/v1/chat/completions")


@app.api_route("/v1/models", methods=["GET"])
async def proxy_models(request: Request):
    """转发 models 请求"""
    return await lb.forward_request(request, "/v1/models")


async def periodic_health_check():
    """定期健康检查"""
    while True:
        await asyncio.sleep(30)
        await lb.health_check()


@app.on_event("startup")
async def startup():
    """启动时进行健康检查"""
    await lb.health_check()
    asyncio.create_task(periodic_health_check())


def main():
    global lb
    
    parser = argparse.ArgumentParser(description="VLM 负载均衡器")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=6050)
    parser.add_argument("--backends", type=str, required=True,
                        help="后端端口列表，逗号分隔，如 6051,6052,6053")
    
    args = parser.parse_args()
    
    # 解析后端
    backends = []
    for port_str in args.backends.split(","):
        port = int(port_str.strip())
        backends.append(Backend("127.0.0.1", port))
    
    lb = LoadBalancer(backends)
    
    print("=" * 60)
    print("🔀 VLM 负载均衡器")
    print("=" * 60)
    print(f"🌐 监听: http://{args.host}:{args.port}")
    print(f"📡 后端: {[b.url for b in backends]}")
    print("=" * 60)
    
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

