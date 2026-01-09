"""
LTX-2 API 测试脚本
"""
import requests
import time

BASE_URL = "http://localhost:6020"


def test_health():
    """测试健康检查"""
    print("=" * 50)
    print("测试健康检查")
    print("=" * 50)
    
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")
    return response.json()["status"] == "ok"


def test_text2video():
    """测试文生视频"""
    print("\n" + "=" * 50)
    print("测试文生视频")
    print("=" * 50)
    
    payload = {
        "prompt": "A cat walking slowly across the room",
        "num_frames": 25,
        "height": 512,
        "width": 768,
        "seed": 42,
    }
    
    print(f"请求: {payload}")
    start = time.time()
    
    response = requests.post(
        f"{BASE_URL}/generate/text2video",
        json=payload,
        timeout=600,
    )
    
    duration = time.time() - start
    result = response.json()
    
    print(f"状态码: {response.status_code}")
    print(f"耗时: {duration:.1f}s")
    print(f"响应: {result}")
    
    return result.get("success", False)


def test_image2video():
    """测试图生视频"""
    print("\n" + "=" * 50)
    print("测试图生视频")
    print("=" * 50)
    
    image_path = "/data1/MLLM/ltx-2/test_image.jpg"
    
    payload = {
        "prompt": "A person slowly turns their head and smiles",
        "image_path": image_path,
        "num_frames": 25,
        "height": 512,
        "width": 768,
        "seed": 42,
    }
    
    print(f"请求: {payload}")
    start = time.time()
    
    response = requests.post(
        f"{BASE_URL}/generate/image2video",
        json=payload,
        timeout=600,
    )
    
    duration = time.time() - start
    result = response.json()
    
    print(f"状态码: {response.status_code}")
    print(f"耗时: {duration:.1f}s")
    print(f"响应: {result}")
    
    return result.get("success", False)


def test_list():
    """测试列表"""
    print("\n" + "=" * 50)
    print("测试视频列表")
    print("=" * 50)
    
    response = requests.get(f"{BASE_URL}/list")
    result = response.json()
    
    print(f"视频数量: {result['count']}")
    for v in result["videos"][:5]:
        print(f"  - {v['task_id']}: {v['size_mb']}MB")
    
    return True


if __name__ == "__main__":
    print("LTX-2 API 测试")
    print("服务地址:", BASE_URL)
    
    # 健康检查
    if not test_health():
        print("\n❌ 服务未启动或不健康")
        exit(1)
    
    # 测试文生视频
    # test_text2video()
    
    # 测试图生视频
    # test_image2video()
    
    # 测试列表
    test_list()
    
    print("\n✅ 测试完成")

