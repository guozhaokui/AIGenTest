---
role: AI
project: MemGraph 知识库系统
directory: D:\work\AIGenTest\MemGraph
timestamp: 2026-01-28T14:02:19.924012
tags: [Internal Server Error, 延迟初始化, API端点, 调试接口, MemGraph]
---

## 问题

MemGraph API 端点返回 Internal Server Error 的问题

## 解决方法

## 问题原因

使用了延迟初始化（Lazy Initialization）机制后，所有需要访问 `indexer` 或 `search_engine` 的 API 端点都必须先调用 `await ensure_initialized()` 来确保服务已初始化。

但是很多端点（尤其是调试接口）直接使用了这些全局变量，导致返回 500 Internal Server Error。

## 需要添加 ensure_initialized() 的端点

### 核心端点
- `/stats` ✅
- `/search` ✅  
- `/record` ✅

### 标签和搜索
- `/search/tag` - 按标签搜索
- `/recent` - 获取最近记录
- `/tags` - 列出所有标签

### 维护端点
- `/rebuild` - 重建索引（**测试页面会用到**）

### 调试端点
- `/debug/vectors` - 查看所有向量
- `/debug/documents` - 查看所有文档
- `/debug/ngrams` - N-gram 统计
- `/debug/test-embedding` - 测试嵌入服务
- `/debug/search-full` - 完整搜索调试
- `/debug/vector-similarity` - 向量相似度调试

## 修复方法

在每个端点函数开头添加：

```python
@app.post("/some-endpoint")
async def some_function():
    await ensure_initialized()  # 确保初始化
    # ... 业务逻辑
```

## 为什么会忘记

1. 延迟初始化是后来添加的优化
2. 调试接口通常是早期开发时编写的
3. 没有统一的检查机制

## 预防措施

可以考虑：
1. 使用 FastAPI 的依赖注入（Depends）统一处理
2. 或者在中间件层面统一初始化
3. 添加自动化测试覆盖所有端点
