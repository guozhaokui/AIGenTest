"""
测试 Transformer 不同层的向量变化率
验证假设：底层变化率对应词级边界，高层变化率对应主题级边界
"""
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
import sys

# 模型路径
MODEL_PATH = "/mnt/hdd/models/Z-Image-Turbo"

# 全局模型（避免重复加载）
_model = None
_tokenizer = None

def load_model():
    """加载模型"""
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

def compute_change_rate(hidden_states, method="cosine"):
    """计算相邻token的向量变化率"""
    seq_len = hidden_states.shape[0]
    change_rates = []

    for i in range(1, seq_len):
        v1 = hidden_states[i-1]
        v2 = hidden_states[i]

        if method == "cosine":
            cos_sim = torch.nn.functional.cosine_similarity(v1.unsqueeze(0), v2.unsqueeze(0))
            dist = 1 - cos_sim.item()
        else:
            dist = torch.norm(v2 - v1).item()

        change_rates.append(dist)

    return np.array(change_rates)

def analyze_text(model, tokenizer, text, selected_layers=None):
    """分析文本在不同层的变化率"""
    # Tokenize
    inputs = tokenizer(text, return_tensors="pt")
    input_ids = inputs.input_ids.to("cuda")

    # 获取tokens - 正确解码中文
    tokens = []
    for token_id in input_ids[0]:
        token_text = tokenizer.decode([token_id.item()])
        tokens.append(token_text)

    # 前向传播
    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            output_hidden_states=True,
        )
        all_hidden_states = outputs.hidden_states

    num_layers = len(all_hidden_states)
    print(f"Total layers: {num_layers}, Sequence length: {len(tokens)}")

    if selected_layers is None:
        selected_layers = list(range(num_layers))

    # 计算每一层的变化率
    results = {}
    for layer_idx in selected_layers:
        if layer_idx < 0:
            layer_idx = num_layers + layer_idx
        if layer_idx >= num_layers:
            continue

        hidden = all_hidden_states[layer_idx][0]
        change_rates = compute_change_rate(hidden)
        results[layer_idx] = change_rates

    return results, tokens, num_layers

def visualize_results(results, tokens, output_file="change_rate_plot.png", title="Layer Change Rate Analysis"):
    """可视化结果"""
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')

    # 设置中文字体 - 使用FontProperties直接指定字体文件
    from matplotlib import font_manager
    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
    chinese_font = font_manager.FontProperties(fname=font_path)
    plt.rcParams['axes.unicode_minus'] = False

    layers = sorted(results.keys())
    seq_len = len(tokens) - 1

    # 创建图表
    fig, axes = plt.subplots(len(layers), 1, figsize=(20, 2.5*len(layers)), sharex=True)
    if len(layers) == 1:
        axes = [axes]

    # 找出所有层的最大值用于标注阈值
    for ax, layer in zip(axes, layers):
        rates = results[layer]
        ax.bar(range(seq_len), rates, alpha=0.7, width=0.8)
        ax.set_ylabel(f'Layer {layer}', fontsize=10)

        # 计算阈值并标注峰值
        mean_rate = np.mean(rates)
        std_rate = np.std(rates)
        threshold = mean_rate + std_rate

        # 在峰值位置标注token文字
        for i, rate in enumerate(rates):
            if rate > threshold:
                token_text = tokens[i+1].replace('\n', '\\n')
                if len(token_text) > 6:
                    token_text = token_text[:6]
                ax.annotate(token_text, (i, rate), fontsize=8, rotation=45, ha='left', fontproperties=chinese_font)

        # 画阈值线
        ax.axhline(y=threshold, color='orange', linestyle=':', alpha=0.5)

    # X轴：显示所有token
    x_labels = []
    for i in range(seq_len):
        token = tokens[i+1].replace('\n', '↵')
        if len(token) > 4:
            token = token[:4]
        x_labels.append(f"{i+1}:{token}")

    axes[-1].set_xticks(range(seq_len))
    axes[-1].set_xticklabels(x_labels, rotation=90, fontsize=7, fontproperties=chinese_font)

    plt.suptitle(title, fontsize=12)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"图表已保存到: {output_file}")
    plt.close()

def print_summary(results, tokens):
    """打印摘要"""
    print("\n" + "="*80)
    print("Token序列:")
    for i, t in enumerate(tokens):
        t_display = t.replace('\n', '\\n')
        print(f"  {i:3d}: {t_display}")

    print("\n" + "="*80)
    print("每层的峰值位置（变化率最大的前5个）:")

    layers = sorted(results.keys())
    for layer in layers:
        rates = results[layer]
        top_indices = np.argsort(rates)[-5:][::-1]
        print(f"  Layer {layer:2d}: ", end="")
        for idx in top_indices:
            token = tokens[idx+1].replace('\n', '\\n')[:6]
            print(f"pos{idx+1}({token})={rates[idx]:.3f}  ", end="")
        print()

def run_test(text, output_file="change_rate_plot.png", title=None):
    """运行测试的主函数"""
    model, tokenizer = load_model()

    # 选择代表性的层
    selected_layers = [0, 4, 8, 12, 16, 20, 24, 28, -2]

    print("\n测试文本:")
    print(text)
    print()

    results, tokens, num_layers = analyze_text(model, tokenizer, text, selected_layers)

    if title is None:
        title = f"Layer Change Rate (Total {num_layers} layers)"

    print_summary(results, tokens)
    visualize_results(results, tokens, output_file, title)

    return results, tokens

# 默认测试文本
DEFAULT_TEXT = """甜甜的苹果熊熊的火焰美丽的北京very good一把生锈的手枪"""

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 从命令行参数读取文本文件
        text_file = sys.argv[1]
        with open(text_file, 'r', encoding='utf-8') as f:
            text = f.read()
        output_file = sys.argv[2] if len(sys.argv) > 2 else "change_rate_plot.png"
    else:
        text = DEFAULT_TEXT
        output_file = "change_rate_plot.png"

    run_test(text, output_file)
