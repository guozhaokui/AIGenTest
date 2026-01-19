"""
滑动窗口 + 白化 的概念分割实验
每个窗口独立编码，解决长序列稀释问题
对向量做白化，解决各向异性问题
"""
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
import sys

MODEL_PATH = "/mnt/hdd/models/Z-Image-Turbo"

_model = None
_tokenizer = None

def load_model():
    global _model, _tokenizer
    if _model is not None:
        return _model, _tokenizer

    print(f"Loading model from {MODEL_PATH}...")
    _tokenizer = AutoTokenizer.from_pretrained(f"{MODEL_PATH}/tokenizer")
    _model = AutoModel.from_pretrained(
        f"{MODEL_PATH}/text_encoder",
        torch_dtype=torch.bfloat16,
    )
    _model.to("cuda")
    _model.eval()
    print("Model loaded.")
    return _model, _tokenizer


def encode_window(model, tokenizer, text, selected_layers):
    """编码一个窗口，返回各层最后一个token的向量"""
    inputs = tokenizer(text, return_tensors="pt")
    input_ids = inputs.input_ids.to("cuda")

    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            output_hidden_states=True,
        )
        all_hidden_states = outputs.hidden_states

    num_layers = len(all_hidden_states)

    # 取每层最后一个token的向量
    layer_vecs = {}
    for layer_idx in selected_layers:
        if layer_idx < 0:
            layer_idx = num_layers + layer_idx
        # 最后一个token的向量
        vec = all_hidden_states[layer_idx][0, -1, :].float().cpu().numpy()
        layer_vecs[layer_idx] = vec

    return layer_vecs, num_layers


def sliding_window_encode(model, tokenizer, text, window_size=10, step=5, selected_layers=None):
    """
    滑动窗口编码

    Args:
        text: 输入文本
        window_size: 窗口大小（字符数）
        step: 步长（字符数）
        selected_layers: 要分析的层

    Returns:
        windows: [(start, end, window_text), ...]
        layer_vectors: {layer_idx: [vec1, vec2, ...]}
    """
    if selected_layers is None:
        selected_layers = [0, 4, 8, 12, 16, 20, 24, 28, -2]

    windows = []
    # 先做一次编码来获取实际的层数
    _, num_layers = encode_window(model, tokenizer, text[:min(10, len(text))], selected_layers)

    # 将负数索引转换为正数
    actual_layers = []
    for l in selected_layers:
        actual_l = l if l >= 0 else num_layers + l
        actual_layers.append(actual_l)

    layer_vectors = {l: [] for l in actual_layers}

    # 滑动窗口
    i = 0
    while i < len(text):
        end = min(i + window_size, len(text))
        window_text = text[i:end]

        if len(window_text.strip()) > 0:  # 跳过空窗口
            windows.append((i, end, window_text))

            # 编码这个窗口
            vecs, _ = encode_window(model, tokenizer, window_text, selected_layers)

            for layer_idx in actual_layers:
                layer_vectors[layer_idx].append(vecs[layer_idx])

        i += step
        if end >= len(text):
            break

    # 转换为numpy数组
    for layer_idx in list(layer_vectors.keys()):
        layer_vectors[layer_idx] = np.array(layer_vectors[layer_idx])

    return windows, layer_vectors


def whiten_vectors(vectors):
    """
    对向量做白化（标准化版本）

    Args:
        vectors: (N, dim) 的向量矩阵

    Returns:
        whitened: 白化后的向量
        mean: 均值
        std: 标准差
    """
    mean = vectors.mean(axis=0)
    std = vectors.std(axis=0)
    std[std < 1e-8] = 1e-8  # 避免除零

    whitened = (vectors - mean) / std
    return whitened, mean, std


def compute_distances(vectors, method="cosine"):
    """计算相邻向量的距离"""
    distances = []
    for i in range(1, len(vectors)):
        v1 = vectors[i-1]
        v2 = vectors[i]

        if method == "cosine":
            cos_sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-8)
            dist = 1 - cos_sim
        else:
            dist = np.linalg.norm(v2 - v1)

        distances.append(dist)

    return np.array(distances)


def visualize_results(windows, layer_distances_raw, layer_distances_white, output_file="sliding_window_plot.png"):
    """可视化结果"""
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')

    from matplotlib import font_manager
    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
    chinese_font = font_manager.FontProperties(fname=font_path)

    layers = sorted(layer_distances_raw.keys())
    num_layers = len(layers)

    fig, axes = plt.subplots(num_layers, 2, figsize=(20, 2.5*num_layers))

    for row, layer in enumerate(layers):
        # 左边：原始向量的距离
        ax_raw = axes[row, 0]
        dist_raw = layer_distances_raw[layer]
        ax_raw.bar(range(len(dist_raw)), dist_raw, alpha=0.7, color='blue')
        ax_raw.set_ylabel(f'L{layer}\nRaw', fontsize=9)
        if row == 0:
            ax_raw.set_title('原始向量距离', fontproperties=chinese_font, fontsize=12)

        # 画阈值线
        if len(dist_raw) > 0:
            threshold = np.mean(dist_raw) + np.std(dist_raw)
            ax_raw.axhline(y=threshold, color='orange', linestyle=':', alpha=0.5)

        # 右边：白化后的距离
        ax_white = axes[row, 1]
        dist_white = layer_distances_white[layer]
        ax_white.bar(range(len(dist_white)), dist_white, alpha=0.7, color='green')
        ax_white.set_ylabel(f'L{layer}\nWhite', fontsize=9)
        if row == 0:
            ax_white.set_title('白化后向量距离', fontproperties=chinese_font, fontsize=12)

        if len(dist_white) > 0:
            threshold = np.mean(dist_white) + np.std(dist_white)
            ax_white.axhline(y=threshold, color='orange', linestyle=':', alpha=0.5)

    # X轴标签：显示窗口内容
    x_labels = []
    for i in range(1, len(windows)):
        w = windows[i][2].replace('\n', '↵')
        if len(w) > 8:
            w = w[:8]
        x_labels.append(f"{i}:{w}")

    for ax in [axes[-1, 0], axes[-1, 1]]:
        ax.set_xticks(range(len(x_labels)))
        ax.set_xticklabels(x_labels, rotation=90, fontsize=7, fontproperties=chinese_font)

    plt.suptitle('滑动窗口 + 白化 分析', fontproperties=chinese_font, fontsize=14)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"图表已保存到: {output_file}")
    plt.close()


def print_summary(windows, layer_distances_raw, layer_distances_white):
    """打印摘要"""
    print("\n" + "="*80)
    print("窗口列表:")
    for i, (start, end, text) in enumerate(windows):
        text_display = text.replace('\n', '\\n')
        if len(text_display) > 30:
            text_display = text_display[:30] + "..."
        print(f"  {i:3d}: [{start:3d}-{end:3d}] {text_display}")

    print("\n" + "="*80)
    print("原始向量 - 每层峰值位置:")
    layers = sorted(layer_distances_raw.keys())
    for layer in layers:
        dist = layer_distances_raw[layer]
        if len(dist) > 0:
            top_k = min(5, len(dist))
            top_indices = np.argsort(dist)[-top_k:][::-1]
            print(f"  Layer {layer:2d}: ", end="")
            for idx in top_indices:
                w = windows[idx+1][2].replace('\n', '\\n')[:8]
                print(f"win{idx+1}({w})={dist[idx]:.3f}  ", end="")
            print()

    print("\n" + "="*80)
    print("白化后 - 每层峰值位置:")
    for layer in layers:
        dist = layer_distances_white[layer]
        if len(dist) > 0:
            top_k = min(5, len(dist))
            top_indices = np.argsort(dist)[-top_k:][::-1]
            print(f"  Layer {layer:2d}: ", end="")
            for idx in top_indices:
                w = windows[idx+1][2].replace('\n', '\\n')[:8]
                print(f"win{idx+1}({w})={dist[idx]:.3f}  ", end="")
            print()


def run_test(text, window_size=10, step=5, output_file="sliding_window_plot.png"):
    """运行测试"""
    model, tokenizer = load_model()

    selected_layers = [0, 4, 8, 12, 16, 20, 24, 28, -2]

    print(f"\n测试文本: {text}")
    print(f"窗口大小: {window_size}, 步长: {step}")
    print()

    # 滑动窗口编码
    windows, layer_vectors = sliding_window_encode(
        model, tokenizer, text,
        window_size=window_size,
        step=step,
        selected_layers=selected_layers
    )

    print(f"窗口数量: {len(windows)}")

    # 计算原始距离和白化后距离
    layer_distances_raw = {}
    layer_distances_white = {}

    for layer_idx, vectors in layer_vectors.items():
        if len(vectors) > 1:
            # 原始距离
            dist_raw = compute_distances(vectors)
            layer_distances_raw[layer_idx] = dist_raw

            # 白化后距离
            vectors_white, _, _ = whiten_vectors(vectors)
            dist_white = compute_distances(vectors_white)
            layer_distances_white[layer_idx] = dist_white
        else:
            layer_distances_raw[layer_idx] = np.array([])
            layer_distances_white[layer_idx] = np.array([])

    # 打印和可视化
    print_summary(windows, layer_distances_raw, layer_distances_white)
    visualize_results(windows, layer_distances_raw, layer_distances_white, output_file)

    return windows, layer_distances_raw, layer_distances_white


# 默认测试文本
DEFAULT_TEXT = """甜甜的苹果熊熊的火焰美丽的北京very good一把生锈的手枪"""

if __name__ == "__main__":
    text = DEFAULT_TEXT
    window_size = 8
    step = 4
    output_file = "sliding_window_plot.png"

    if len(sys.argv) > 1 and sys.argv[1] and sys.argv[1] not in ["''", "-", ""]:
        text_file = sys.argv[1]
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()

    if len(sys.argv) > 2:
        window_size = int(sys.argv[2])
    if len(sys.argv) > 3:
        step = int(sys.argv[3])
    if len(sys.argv) > 4:
        output_file = sys.argv[4]

    run_test(text, window_size, step, output_file)
