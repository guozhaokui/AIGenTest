#!/usr/bin/env python3
"""测试流式响应"""

import requests
import time

url = "http://localhost:5001/api/knowledge/chat/stream"

data = {
    "message": "你好，请介绍一下你自己",
    "model": "deepseek-ai/deepseek-v3.2",
    "history": []
}

print("开始测试流式响应...")
print("=" * 60)

start_time = time.time()
first_token_time = None
token_count = 0

response = requests.post(url, json=data, stream=True)

for line in response.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            if not first_token_time:
                first_token_time = time.time()
                print(f"首字延迟: {(first_token_time - start_time) * 1000:.0f}ms")
                print("=" * 60)

            token_count += 1
            print(f"[{token_count}] {time.time() - start_time:.2f}s: {line_str[:100]}")

end_time = time.time()
print("=" * 60)
print(f"总耗时: {(end_time - start_time):.2f}s")
print(f"Token数: {token_count}")
if token_count > 0:
    print(f"平均速度: {token_count / (end_time - start_time):.1f} tokens/s")
