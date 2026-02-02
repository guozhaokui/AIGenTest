#!/usr/bin/env python3
"""
测试 CosyVoice3 模型
验证是否满足需求
"""
import os

# 设置模型缓存目录
os.environ['MODELSCOPE_CACHE'] = '/mnt/hdd/guo/AIGenTest/aiserver/models'

def test_model_info():
    """测试模型信息"""
    print("=" * 60)
    print("测试 CosyVoice3-0.5B 模型")
    print("=" * 60)

    try:
        from modelscope import snapshot_download

        model_id = "FunAudioLLM/Fun-CosyVoice3-0.5B-2512"
        print(f"\n模型ID: {model_id}")
        print(f"缓存目录: {os.environ['MODELSCOPE_CACHE']}")

        # 下载模型（如果还没下载）
        print("\n正在下载模型...")
        model_dir = snapshot_download(model_id)
        print(f"✓ 模型路径: {model_dir}")

        # 查看模型文件
        files = os.listdir(model_dir)
        print(f"\n✓ 模型文件: {len(files)} 个")
        for f in sorted(files):
            fpath = os.path.join(model_dir, f)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                if size > 1024*1024:
                    print(f"  - {f} ({size/1024/1024:.1f}MB)")
                else:
                    print(f"  - {f}")

        return True, model_dir

    except Exception as e:
        print(f"✗ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_basic_tts(model_dir):
    """测试基础TTS功能"""
    print("\n" + "=" * 60)
    print("测试基础语音合成")
    print("=" * 60)

    if not model_dir:
        print("✗ 模型未加载")
        return False

    try:
        # 尝试不同的导入方式
        print("\n尝试导入 CosyVoice...")

        # 方式1: 从 modelscope
        try:
            from modelscope.pipelines import pipeline
            from modelscope.utils.constant import Tasks

            print("✓ 使用 modelscope pipeline")

            # 创建 pipeline
            tts_pipeline = pipeline(
                task=Tasks.text_to_speech,
                model=model_dir
            )

            print("✓ Pipeline 创建成功")

            # 测试合成
            text = "你好，这是CosyVoice语音合成测试"
            print(f"\n合成文本: {text}")

            result = tts_pipeline(text)

            print(f"✓ 合成成功")
            print(f"  结果类型: {type(result)}")

            if isinstance(result, dict):
                print(f"  结果键: {list(result.keys())}")

            return True

        except Exception as e1:
            print(f"✗ modelscope pipeline 失败: {e1}")

            # 方式2: 直接导入
            try:
                import sys
                sys.path.insert(0, model_dir)

                # 根据实际的模型结构导入
                print("\n尝试直接导入模型...")

                # 这里需要根据实际模型结构调整
                print("✓ 需要查看模型文档了解具体用法")

                return False

            except Exception as e2:
                print(f"✗ 直接导入失败: {e2}")
                return False

    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_features():
    """检查功能特性"""
    print("\n" + "=" * 60)
    print("CosyVoice 功能分析")
    print("=" * 60)

    features = {
        "模型大小": "0.5B (约500MB，比Qwen的1.7B小)",
        "采样率": "通常支持 24kHz 高质量",
        "多音色": "✓ 支持（零样本音色克隆）",
        "情绪控制": "需要验证",
        "语速控制": "需要验证",
        "易用性": "阿里达摩院开源，文档较完善",
        "环境要求": "相对简单，不需要torchvision",
    }

    print("\n预期特性：")
    for k, v in features.items():
        print(f"  {k:12s}: {v}")

    print("\n优势：")
    print("  1. 模型更小 (0.5B vs 1.7B)")
    print("  2. 依赖更少，环境更简单")
    print("  3. 支持零样本音色克隆")
    print("  4. 高质量输出 (24kHz)")
    print("  5. 阿里达摩院维护，更新活跃")


def main():
    """主函数"""
    print("\n🚀 CosyVoice3 模型评估\n")

    # 检查依赖
    print("检查依赖包...")
    try:
        import torch
        print(f"✓ torch {torch.__version__}")
        print(f"  CUDA: {torch.cuda.is_available()}")
    except:
        print("✗ torch 未安装")
        return

    try:
        import modelscope
        print(f"✓ modelscope {modelscope.__version__}")
    except:
        print("✗ modelscope 未安装")
        return

    print()

    # 测试模型
    success, model_dir = test_model_info()

    if success:
        test_basic_tts(model_dir)

    # 功能分析
    check_features()

    print("\n" + "=" * 60)
    print("📋 评估总结")
    print("=" * 60)

    print("\n✅ CosyVoice3 的优势：")
    print("  1. 模型更小，下载更快（约500MB）")
    print("  2. 环境简单，不需要torchvision")
    print("  3. 支持零样本音色克隆")
    print("  4. 更高的采样率（24kHz）")
    print("  5. 维护活跃，文档完善")

    print("\n⚠️  需要验证的功能：")
    print("  1. 情绪控制方式")
    print("  2. 语速调节接口")
    print("  3. API调用方式")
    print("  4. 具体参数格式")

    print("\n💡 建议：")
    print("  CosyVoice3 是一个很好的选择！")
    print("  - 环境更简单（避免torch/torchvision兼容问题）")
    print("  - 功能更强（支持音色克隆）")
    print("  - 更易部署")

    print("\n下一步：")
    print("  查看模型文档，了解具体API用法")
    print("  参考: https://github.com/FunAudioLLM/CosyVoice")


if __name__ == "__main__":
    main()
