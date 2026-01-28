"""
快速测试 Web 界面
在浏览器中打开测试面板
"""
import webbrowser
import time
import requests
import sys


def wait_for_service(url, timeout=10):
    """等待服务启动"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(url)
            if response.status_code == 200:
                return True
        except:
            pass
        time.sleep(0.5)
    return False


def main():
    print("=" * 60)
    print("  MemGraph Web 测试面板启动器")
    print("=" * 60)
    print()

    # 检查服务是否运行
    print("1. 检查 MemGraph 服务状态...")
    service_url = "http://localhost:8800/health"

    if not wait_for_service(service_url, timeout=3):
        print("   ❌ MemGraph 服务未启动")
        print()
        print("请先启动服务：")
        print("   cd D:\\work\\AIGenTest\\MemGraph")
        print("   python start.py")
        print()
        print("或者随 backend 一起启动：")
        print("   cd D:\\work\\AIGenTest")
        print("   pnpm dev:backend")
        sys.exit(1)

    print("   ✅ MemGraph 服务正常运行")
    print()

    # 获取统计信息
    print("2. 获取知识库统计...")
    try:
        stats = requests.get("http://localhost:8800/stats").json()
        print(f"   📊 文档数: {stats['documents']}")
        print(f"   📊 N-gram总数: {stats['ngrams']}")
        print(f"   📊 唯一N-gram: {stats['unique_ngrams']}")
        print(f"   📊 FAISS向量: {stats['faiss_vectors']}")
    except Exception as e:
        print(f"   ⚠️ 无法获取统计信息: {e}")

    print()

    # 打开浏览器
    print("3. 打开 Web 测试面板...")
    web_url = "http://localhost:8800"

    try:
        webbrowser.open(web_url)
        print(f"   ✅ 已在浏览器中打开: {web_url}")
    except Exception as e:
        print(f"   ⚠️ 自动打开失败: {e}")
        print(f"   请手动访问: {web_url}")

    print()
    print("=" * 60)
    print("  测试面板功能:")
    print("=" * 60)
    print("  • 📝 记录新经验 - 左上角表单")
    print("  • 📊 统计信息 - 右上角卡片")
    print("  • 🔍 搜索经验 - 下方搜索框")
    print("  • 🎯 调试信息 - 搜索结果中的得分细分")
    print()
    print("  详细使用说明: WEB_TEST_GUIDE.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
