"""
Gemini API 视频理解示例

这个脚本演示如何使用 Google Gemini API 进行视频理解，支持三种方式：
1. 上传本地视频文件（File API）
2. 使用 YouTube 视频链接
3. 内嵌小视频数据（Base64）

安装依赖:
pip install google-generativeai python-dotenv

使用方法:
python gemini_video_understanding.py --mode file --video_path /path/to/video.mp4
python gemini_video_understanding.py --mode youtube --video_url "https://www.youtube.com/watch?v=..."
"""

import os
import sys
import argparse
import time
import base64
import subprocess
import json
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai

# 加载环境变量
load_dotenv()

# 配置 API Key
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("请在 .env 文件中设置 GOOGLE_API_KEY")

genai.configure(api_key=GOOGLE_API_KEY)

# 模型价格表（每百万 tokens，单位：美元）
MODEL_PRICING = {
    "gemini-2.0-flash-exp": {
        "input": 0.0,  # 实验版可能免费
        "output": 0.0,
        "name": "Gemini 2.0 Flash Experimental"
    },
    "gemini-2.0-flash-lite": {
        "input": 0.075,
        "output": 0.30,
        "name": "Gemini 2.0 Flash-Lite"
    },
    "gemini-2.5-flash-lite": {
        "input": 0.10,
        "output": 0.40,
        "name": "Gemini 2.5 Flash-Lite"
    },
    "gemini-2.5-pro": {
        "input": 2.00,
        "output": 12.00,
        "name": "Gemini 2.5 Pro",
        "context_limit": 200000,
        "high_context_input": 4.00,
        "high_context_output": 18.00
    },
    "gemini-3-pro-preview": {
        "input": 2.00,
        "output": 12.00,
        "name": "Gemini 3 Pro Preview",
        "context_limit": 200000,
        "high_context_input": 4.00,
        "high_context_output": 18.00
    }
}

USD_TO_CNY = 7.2  # 美元兑人民币汇率


def get_video_duration(video_path: str) -> float:
    """
    获取视频时长（秒），尝试多种方法

    Args:
        video_path: 视频文件路径

    Returns:
        视频时长（秒），如果获取失败返回 None
    """
    # 方法1: 使用 ffprobe
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            return duration

    except FileNotFoundError:
        pass  # ffprobe 不可用，尝试其他方法
    except Exception as e:
        pass

    # 方法2: 使用 opencv (如果可用)
    try:
        import cv2
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()

        if fps > 0 and frame_count > 0:
            duration = frame_count / fps
            return duration
    except ImportError:
        pass  # opencv 不可用
    except Exception as e:
        pass

    # 方法3: 根据文件大小粗略估算（最后的备选方案）
    try:
        file_size = os.path.getsize(video_path)
        # 假设平均码率为 2 Mbps (250 KB/s)
        # 这只是一个粗略估算
        estimated_duration = file_size / (250 * 1024)
        print(f"警告: 无法精确获取视频时长，根据文件大小估算约 {estimated_duration:.1f} 秒")
        print("建议安装 ffmpeg 或 opencv-python 以获得准确时长")
        return estimated_duration
    except Exception as e:
        print(f"警告: 无法获取视频信息: {e}")
        return None


def estimate_tokens_and_cost(video_duration: float, fps: int = 1, model: str = "gemini-2.0-flash-exp",
                             output_tokens: int = 500):
    """
    估算视频处理的 token 消耗和成本

    Args:
        video_duration: 视频时长（秒）
        fps: 采样率（帧/秒）
        model: 模型名称
        output_tokens: 预计输出 token 数量

    Returns:
        包含估算信息的字典
    """
    # 每秒视频的 token 消耗（基于 1 FPS）
    TOKENS_PER_SECOND_1FPS = 258

    # 根据 FPS 计算输入 tokens
    input_tokens = int(video_duration * TOKENS_PER_SECOND_1FPS * fps)
    total_tokens = input_tokens + output_tokens

    # 获取价格信息
    if model not in MODEL_PRICING:
        print(f"警告: 未知模型 {model}，使用默认价格")
        pricing = MODEL_PRICING["gemini-2.0-flash-exp"]
    else:
        pricing = MODEL_PRICING[model]

    # 计算成本
    # 检查是否超过上下文限制（高价格）
    context_limit = pricing.get("context_limit", float('inf'))
    if total_tokens > context_limit:
        input_price = pricing.get("high_context_input", pricing["input"])
        output_price = pricing.get("high_context_output", pricing["output"])
        high_context = True
    else:
        input_price = pricing["input"]
        output_price = pricing["output"]
        high_context = False

    input_cost_usd = (input_tokens / 1_000_000) * input_price
    output_cost_usd = (output_tokens / 1_000_000) * output_price
    total_cost_usd = input_cost_usd + output_cost_usd

    input_cost_cny = input_cost_usd * USD_TO_CNY
    output_cost_cny = output_cost_usd * USD_TO_CNY
    total_cost_cny = total_cost_usd * USD_TO_CNY

    return {
        "video_duration": video_duration,
        "fps": fps,
        "model": model,
        "model_name": pricing["name"],
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "high_context": high_context,
        "input_cost_usd": input_cost_usd,
        "output_cost_usd": output_cost_usd,
        "total_cost_usd": total_cost_usd,
        "input_cost_cny": input_cost_cny,
        "output_cost_cny": output_cost_cny,
        "total_cost_cny": total_cost_cny,
    }


def print_cost_estimate(estimate: dict):
    """打印成本估算信息"""
    print("\n" + "="*60)
    print("📊 成本估算")
    print("="*60)
    print(f"视频时长: {estimate['video_duration']:.1f} 秒")
    print(f"采样率: {estimate['fps']} FPS")
    print(f"模型: {estimate['model_name']} ({estimate['model']})")

    if estimate['high_context']:
        print("⚠️  注意: Token 数量超过标准上下文限制，使用高价格")

    print(f"\n📈 Token 消耗:")
    print(f"  输入 tokens: {estimate['input_tokens']:,}")
    print(f"  预计输出 tokens: {estimate['output_tokens']:,}")
    print(f"  总计: {estimate['total_tokens']:,} tokens")

    print(f"\n💰 预估成本:")
    print(f"  输入成本: ${estimate['input_cost_usd']:.6f} (¥{estimate['input_cost_cny']:.4f})")
    print(f"  输出成本: ${estimate['output_cost_usd']:.6f} (¥{estimate['output_cost_cny']:.4f})")
    print(f"  总成本: ${estimate['total_cost_usd']:.6f} (¥{estimate['total_cost_cny']:.4f})")
    print("="*60 + "\n")


def upload_video_file(video_path: str):
    """
    上传视频文件到 Gemini File API
    适用于大文件（>20MB）或需要重复使用的视频

    Args:
        video_path: 视频文件路径

    Returns:
        上传后的文件对象
    """
    print(f"正在上传视频文件: {video_path}")

    video_file = genai.upload_file(path=video_path)
    print(f"上传完成! 文件 URI: {video_file.uri}")

    # 等待文件处理完成
    print("等待视频处理...")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)

    if video_file.state.name == "FAILED":
        raise ValueError(f"视频处理失败: {video_file.state}")

    print(f"视频处理完成! 状态: {video_file.state.name}")
    return video_file


def analyze_video_from_file(video_path: str, prompt: str = "请详细描述这个视频的内容",
                           fps: int = 1, model: str = "gemini-2.0-flash-exp",
                           dry_run: bool = False, output_tokens: int = 500):
    """
    从本地文件上传并分析视频

    Args:
        video_path: 视频文件路径
        prompt: 分析提示词
        fps: 视频采样率（帧/秒），默认1，最高10。更高的FPS可以捕捉更多细节，但消耗更多tokens
        model: 使用的模型
        dry_run: 如果为 True，只估算成本不实际调用 API
        output_tokens: 预计输出 token 数量

    Returns:
        分析结果文本，如果是 dry_run 则返回 None
    """
    # 获取视频时长
    duration = get_video_duration(video_path)

    if duration:
        # 估算成本
        estimate = estimate_tokens_and_cost(duration, fps, model, output_tokens)
        print_cost_estimate(estimate)
    else:
        print("无法获取视频时长，跳过成本估算")

    if dry_run:
        print("🔍 Dry-run 模式: 只进行成本估算，不实际调用 API")
        return None

    # 上传视频
    video_file = upload_video_file(video_path)

    # 创建生成模型
    gen_model = genai.GenerativeModel(model_name=model)

    # 构建带有视频配置的内容
    video_part = {
        "file_data": {
            "file_uri": video_file.uri,
            "mime_type": video_file.mime_type
        }
    }

    # 设置生成配置（包含视频处理参数）
    generation_config = {
        "temperature": 0.4,
    }

    # 如果 FPS > 1，在提示词中说明（Gemini API 会自动使用更高采样率）
    if fps > 1:
        print(f"\n使用 {fps} FPS 采样率分析视频（会消耗更多 tokens）")
        enhanced_prompt = f"{prompt}\n\n注意：以 {fps} 帧/秒的采样率分析此视频，捕捉详细的动作变化。"
    else:
        enhanced_prompt = prompt

    # 生成内容
    print(f"\n正在分析视频，提示词: {prompt}")
    response = gen_model.generate_content(
        [video_part, enhanced_prompt],
        generation_config=generation_config
    )

    return response.text


def analyze_video_from_youtube(video_url: str, prompt: str = "请总结这个视频的主要内容"):
    """
    从 YouTube 链接直接分析视频

    Args:
        video_url: YouTube 视频链接
        prompt: 分析提示词

    Returns:
        分析结果文本
    """
    print(f"正在分析 YouTube 视频: {video_url}")

    # 创建生成模型
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp")

    # 直接使用 YouTube 链接
    response = model.generate_content([
        {
            "mime_type": "video/youtube",
            "file_uri": video_url
        },
        prompt
    ])

    return response.text


def analyze_video_embedded(video_path: str, prompt: str = "请描述这个视频"):
    """
    将小视频（<20MB）内嵌到请求中进行分析

    Args:
        video_path: 视频文件路径
        prompt: 分析提示词

    Returns:
        分析结果文本
    """
    # 检查文件大小
    file_size = os.path.getsize(video_path)
    if file_size > 20 * 1024 * 1024:
        raise ValueError(f"文件太大 ({file_size / 1024 / 1024:.2f}MB)，请使用 File API 上传模式")

    print(f"正在读取视频文件: {video_path} ({file_size / 1024 / 1024:.2f}MB)")

    # 读取并编码视频
    with open(video_path, 'rb') as f:
        video_data = base64.b64encode(f.read()).decode('utf-8')

    # 获取 MIME 类型
    mime_type = get_mime_type(video_path)

    # 创建生成模型
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp")

    # 生成内容
    print(f"正在分析视频，提示词: {prompt}")
    response = model.generate_content([
        {
            "mime_type": mime_type,
            "data": video_data
        },
        prompt
    ])

    return response.text


def get_mime_type(file_path: str) -> str:
    """根据文件扩展名获取 MIME 类型"""
    ext = Path(file_path).suffix.lower()
    mime_types = {
        '.mp4': 'video/mp4',
        '.mpeg': 'video/mpeg',
        '.mpg': 'video/mpg',
        '.mov': 'video/mov',
        '.avi': 'video/avi',
        '.flv': 'video/x-flv',
        '.webm': 'video/webm',
        '.wmv': 'video/wmv',
        '.3gp': 'video/3gpp',
    }
    return mime_types.get(ext, 'video/mp4')


def demo_advanced_prompts(video_path: str, fps: int = 1):
    """
    演示高级视频分析功能

    Args:
        video_path: 视频文件路径
        fps: 视频采样率
    """
    print("\n=== 演示高级视频分析功能 ===\n")
    print(f"采样率: {fps} FPS")

    # 上传视频
    video_file = upload_video_file(video_path)
    model = genai.GenerativeModel(model_name="gemini-2.0-flash-exp")

    video_part = {
        "file_data": {
            "file_uri": video_file.uri,
            "mime_type": video_file.mime_type
        }
    }

    # 1. 视频摘要
    print("\n1. 生成视频摘要:")
    response = model.generate_content([video_part, "请生成这个视频的简短摘要（3-5句话）"])
    print(response.text)

    # 2. 时间戳问答
    print("\n2. 询问特定时间点的内容:")
    response = model.generate_content([video_part, "在视频的 00:30 时刻发生了什么？"])
    print(response.text)

    # 3. 提取关键信息
    print("\n3. 提取关键信息:")
    response = model.generate_content([video_part, "请列出视频中提到的所有重要人物、地点或物品"])
    print(response.text)

    # 4. 生成测验题
    print("\n4. 基于视频内容生成测验题:")
    response = model.generate_content([
        video_part,
        "请根据视频内容生成3道选择题，包括正确答案和解释"
    ])
    print(response.text)


def main():
    parser = argparse.ArgumentParser(description='Gemini 视频理解示例')
    parser.add_argument('--mode', type=str, choices=['file', 'youtube', 'embedded', 'demo'],
                        default='demo', help='运行模式')
    parser.add_argument('--video_path', type=str, help='视频文件路径（用于 file/embedded/demo 模式）')
    parser.add_argument('--video_url', type=str, help='YouTube 视频链接（用于 youtube 模式）')
    parser.add_argument('--prompt', type=str, default='请详细描述这个视频的内容',
                        help='分析提示词')
    parser.add_argument('--fps', type=int, default=1, choices=range(1, 11),
                        help='视频采样率（1-10帧/秒），越高越详细但消耗更多tokens。游戏视频建议5-10')
    parser.add_argument('--model', type=str, default='gemini-2.0-flash-exp',
                        choices=list(MODEL_PRICING.keys()),
                        help='使用的模型')
    parser.add_argument('--dry-run', action='store_true',
                        help='只估算成本，不实际调用 API')
    parser.add_argument('--output-tokens', type=int, default=500,
                        help='预计输出 token 数量（用于成本估算）')

    args = parser.parse_args()

    try:
        if args.mode == 'file':
            if not args.video_path:
                print("错误: file 模式需要 --video_path 参数")
                sys.exit(1)
            result = analyze_video_from_file(
                args.video_path,
                args.prompt,
                args.fps,
                args.model,
                args.dry_run,
                args.output_tokens
            )
            if result:
                print("\n=== 分析结果 ===")
                print(result)

        elif args.mode == 'youtube':
            if not args.video_url:
                print("错误: youtube 模式需要 --video_url 参数")
                sys.exit(1)
            result = analyze_video_from_youtube(args.video_url, args.prompt)
            print("\n=== 分析结果 ===")
            print(result)

        elif args.mode == 'embedded':
            if not args.video_path:
                print("错误: embedded 模式需要 --video_path 参数")
                sys.exit(1)
            result = analyze_video_embedded(args.video_path, args.prompt)
            print("\n=== 分析结果 ===")
            print(result)

        elif args.mode == 'demo':
            if not args.video_path:
                print("错误: demo 模式需要 --video_path 参数")
                print("\n示例用法:")
                print("  python gemini_video_understanding.py --mode demo --video_path /path/to/video.mp4")
                sys.exit(1)
            demo_advanced_prompts(args.video_path, args.fps)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # 如果没有命令行参数，显示使用说明
    if len(sys.argv) == 1:
        print("Gemini 视频理解示例\n")
        print("使用方法:")
        print("  1. 从本地文件上传并分析:")
        print("     python gemini_video_understanding.py --mode file --video_path /path/to/video.mp4")
        print("\n  2. 从 YouTube 链接分析:")
        print("     python gemini_video_understanding.py --mode youtube --video_url 'https://www.youtube.com/watch?v=...'")
        print("\n  3. 小视频内嵌分析:")
        print("     python gemini_video_understanding.py --mode embedded --video_path /path/to/small_video.mp4")
        print("\n  4. 运行高级功能演示:")
        print("     python gemini_video_understanding.py --mode demo --video_path /path/to/video.mp4")
        print("\n  5. 自定义提示词:")
        print("     python gemini_video_understanding.py --mode file --video_path video.mp4 --prompt '请分析视频中的人物情绪'")
        print("\n  6. 使用更高 FPS 分析游戏视频（捕捉快速动作）:")
        print("     python gemini_video_understanding.py --mode file --video_path game.mp4 --fps 5 --prompt '分析游戏玩法'")
        print("\n  7. 只估算成本，不实际调用 API（测试模式）:")
        print("     python gemini_video_understanding.py --mode file --video_path video.mp4 --fps 8 --model gemini-3-pro-preview --dry-run")
        print("\n  8. 指定模型进行分析:")
        print("     python gemini_video_understanding.py --mode file --video_path video.mp4 --model gemini-2.5-pro")
        print("\n注意:")
        print("  - 请确保 .env 文件中已设置 GOOGLE_API_KEY")
        print("  - FPS 越高，token 消耗越多。游戏视频建议 5-10 FPS，普通视频 1-3 FPS 即可")
        print("  - 使用 --dry-run 可以在不消耗 API 配额的情况下估算成本")
        print(f"\n支持的模型: {', '.join(MODEL_PRICING.keys())}")
        sys.exit(0)

    main()
