---
role: AI
project: MemGraph 知识库系统
directory: D:\work\AIGenTest\MemGraph
timestamp: 2026-01-28T13:13:23.484576
tags: [503错误, 代理问题, Windows, localhost, NO_PROXY, 故障排查]
---

## 问题

Windows 上 MemGraph 服务总是返回 503 的根本原因

## 解决方法

## 问题现象

每次启动 MemGraph 服务后，所有请求都返回 503 错误（包括 `/health` 端点），响应头包含 `proxy-connection: close`。

## 根本原因

**Windows 系统配置了 HTTP 代理，所有 HTTP 请求（包括 localhost/127.0.0.1）都被代理服务器拦截，代理返回 503 Service Unavailable。**

## 解决方案

在 Python 脚本开头设置 `NO_PROXY` 环境变量，让 localhost 请求不走代理：

```python
import os

# 禁用代理，避免 localhost 请求被拦截
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
os.environ['no_proxy'] = 'localhost,127.0.0.1'
```

### 需要修改的文件

1. **MemGraph/start.py** - 服务启动脚本
2. **所有测试脚本** - test_*.py 文件
3. **MCP Client** - 如果使用 Python 实现

## 验证方法

```python
import httpx

async with httpx.AsyncClient() as client:
    r = await client.get('http://localhost:8800/health')
    print(r.status_code)  # 应该返回 200
    print(r.headers.get('proxy-connection'))  # 不应该有这个头
```

## 为什么每次都遇到

1. 修改代码后重启服务
2. 新启动的 Python 进程继承系统代理设置
3. 所有 localhost 请求被代理拦截
4. 返回 503 错误

## 其他解决方案

1. **全局禁用代理**（不推荐）
   - 修改系统环境变量 `NO_PROXY`

2. **配置代理排除规则**
   - 在代理软件中添加 localhost 到排除列表

3. **使用专用测试工具**
   - curl 的 `--noproxy` 参数
   - requests 的 `proxies={'http': None}`
