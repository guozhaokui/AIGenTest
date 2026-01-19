"""
分析 Attention 权重来检测概念边界
- Attention Entropy：集中度，entropy低表示关注集中
- Attention Span：跨度，关注的平均距离
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
        attn_implementation="eager",  # 使用eager attention以支持输出attention权重
    )
    _model.to("cuda")
    _model.eval()
    print("Model loaded.")
    return _model, _tokenizer


def get_attention_weights(model, tokenizer, text):
    """获取所有层的attention权重"""
    inputs = tokenizer(text, return_tensors="pt")
    input_ids = inputs.input_ids.to("cuda")

    # 获取tokens
    tokens = []
    for token_id in input_ids[0]:
        token_text = tokenizer.decode([token_id.item()])
        tokens.append(token_text)

    with torch.no_grad():
        outputs = model(
            input_ids=input_ids,
            output_attentions=True,
        )
        # attentions: tuple of (batch, num_heads, seq_len, seq_len)
        attentions = outputs.attentions

    num_layers = len(attentions)
    num_heads = attentions[0].shape[1]
    seq_len = len(tokens)

    print(f"Layers: {num_layers}, Heads: {num_heads}, Seq_len: {seq_len}")

    return attentions, tokens, num_layers, num_heads


def compute_attention_entropy(attn_weights, normalize=True):
    """
    计算attention的entropy（集中度）

    Args:
        attn_weights: (seq_len, seq_len)
        normalize: 是否归一化（除以最大可能entropy）

    Returns:
        entropy值，归一化后范围[0,1]，越低表示attention越集中
    """
    seq_len = attn_weights.shape[0]
    # 避免log(0)
    attn = attn_weights + 1e-10
    entropy = -torch.sum(attn * torch.log(attn), dim=-1)

    if normalize:
        # 最大entropy = log(可关注的位置数)
        # 位置i可以关注0~i，共i+1个位置
        max_entropy = torch.log(torch.arange(1, seq_len + 1, device=attn_weights.device, dtype=torch.float32))
        max_entropy = torch.clamp(max_entropy, min=1e-10)  # 避免除零
        entropy = entropy.float() / max_entropy

    return entropy


def compute_attention_span(attn_weights, normalize=True):
    """
    计算attention的跨度（平均关注距离）

    Args:
        attn_weights: (seq_len, seq_len)，第i行是位置i对所有位置的attention
        normalize: 是否归一化（除以期望值）

    Returns:
        每个位置的平均关注距离，归一化后>1表示关注比期望更远
    """
    seq_len = attn_weights.shape[0]
    positions = torch.arange(seq_len, device=attn_weights.device, dtype=attn_weights.dtype)

    spans = []
    for i in range(seq_len):
        # 位置i对位置0~i的attention（因果mask）
        attn_i = attn_weights[i, :i+1]
        pos_i = positions[:i+1]

        # 平均关注距离 = sum(attention * distance)
        distances = i - pos_i  # 当前位置到各位置的距离
        avg_span = torch.sum(attn_i * distances)

        if normalize and i > 0:
            # 如果均匀分布，期望span = i/2
            expected_span = i / 2.0
            avg_span = avg_span / expected_span
        elif i == 0:
            avg_span = torch.tensor(1.0)

        spans.append(avg_span.item())

    return np.array(spans)


def compute_attention_concentration(attn_weights):
    """
    计算attention的集中度（另一种指标）
    = 最大attention值 / 平均attention值

    高值表示attention非常集中在某几个位置
    """
    seq_len = attn_weights.shape[0]
    concentrations = []

    for i in range(seq_len):
        attn_i = attn_weights[i, :i+1]
        if i == 0:
            concentrations.append(1.0)
        else:
            max_attn = torch.max(attn_i)
            mean_attn = torch.mean(attn_i)
            conc = (max_attn / mean_attn).item()
            concentrations.append(conc)

    return np.array(concentrations)


def compute_attention_locality(attn_weights, window=3):
    """
    计算attention的局部性
    = 最近window个位置的attention权重之和

    高值表示主要关注最近的内容（局部）
    低值表示关注较远的内容（全局/引用）
    """
    seq_len = attn_weights.shape[0]
    localities = []

    for i in range(seq_len):
        attn_i = attn_weights[i, :i+1]
        # 最近window个位置
        start = max(0, i - window + 1)
        local_attn = attn_i[start:i+1].sum()
        localities.append(local_attn.item())

    return np.array(localities)


def analyze_attention(attentions, selected_layers=None):
    """
    分析各层的attention

    Returns:
        layer_entropy: {layer_idx: (seq_len,) 归一化entropy}
        layer_span: {layer_idx: (seq_len,) 归一化span}
        layer_locality: {layer_idx: (seq_len,) 局部性}
        layer_concentration: {layer_idx: (seq_len,) 集中度}
    """
    num_layers = len(attentions)

    if selected_layers is None:
        selected_layers = [0, 4, 8, 12, 16, 20, 24, 28, num_layers-2]

    layer_entropy = {}
    layer_span = {}
    layer_locality = {}
    layer_concentration = {}

    for layer_idx in selected_layers:
        if layer_idx < 0:
            layer_idx = num_layers + layer_idx
        if layer_idx >= num_layers:
            continue

        # (batch, num_heads, seq_len, seq_len)
        attn = attentions[layer_idx][0]  # (num_heads, seq_len, seq_len)

        # 对所有head取平均
        attn_avg = attn.mean(dim=0).float()  # (seq_len, seq_len)

        # 计算各种指标（归一化）
        entropy = compute_attention_entropy(attn_avg, normalize=True)
        layer_entropy[layer_idx] = entropy.cpu().numpy()

        span = compute_attention_span(attn_avg, normalize=True)
        layer_span[layer_idx] = span

        locality = compute_attention_locality(attn_avg, window=3)
        layer_locality[layer_idx] = locality

        concentration = compute_attention_concentration(attn_avg)
        layer_concentration[layer_idx] = concentration

    return layer_entropy, layer_span, layer_locality, layer_concentration


def visualize_attention_analysis(tokens, layer_entropy, layer_span, layer_locality, output_file="attention_analysis.png"):
    """可视化attention分析结果"""
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')

    from matplotlib import font_manager
    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
    chinese_font = font_manager.FontProperties(fname=font_path)

    layers = sorted(layer_entropy.keys())
    num_layers = len(layers)
    seq_len = len(tokens)

    fig, axes = plt.subplots(num_layers, 3, figsize=(24, 2.5*num_layers))

    for row, layer in enumerate(layers):
        # 左边：归一化Entropy
        ax_ent = axes[row, 0]
        entropy = layer_entropy[layer]
        ax_ent.bar(range(seq_len), entropy, alpha=0.7, color='blue')
        ax_ent.set_ylabel(f'L{layer}', fontsize=9)
        ax_ent.axhline(y=1.0, color='orange', linestyle='--', alpha=0.5, label='均匀分布')
        if row == 0:
            ax_ent.set_title('归一化Entropy (>1=比均匀更分散)', fontproperties=chinese_font, fontsize=11)

        # 标注异常点
        if len(entropy) > 1:
            mean_e, std_e = np.mean(entropy[1:]), np.std(entropy[1:])
            for i, e in enumerate(entropy):
                if i > 0 and (e > mean_e + std_e or e < mean_e - std_e):
                    token = tokens[i].replace('\n', '↵')[:4]
                    ax_ent.annotate(token, (i, e), fontsize=7, rotation=45, fontproperties=chinese_font)

        # 中间：归一化Span
        ax_span = axes[row, 1]
        span = layer_span[layer]
        ax_span.bar(range(seq_len), span, alpha=0.7, color='green')
        ax_span.axhline(y=1.0, color='orange', linestyle='--', alpha=0.5, label='均匀分布')
        if row == 0:
            ax_span.set_title('归一化Span (>1=比均匀关注更远)', fontproperties=chinese_font, fontsize=11)

        if len(span) > 1:
            mean_s, std_s = np.mean(span[1:]), np.std(span[1:])
            for i, s in enumerate(span):
                if i > 0 and (s > mean_s + std_s or s < mean_s - std_s):
                    token = tokens[i].replace('\n', '↵')[:4]
                    ax_span.annotate(token, (i, s), fontsize=7, rotation=45, fontproperties=chinese_font)

        # 右边：Locality（局部性）
        ax_loc = axes[row, 2]
        locality = layer_locality[layer]
        ax_loc.bar(range(seq_len), locality, alpha=0.7, color='purple')
        if row == 0:
            ax_loc.set_title('Locality (高=关注最近3个token)', fontproperties=chinese_font, fontsize=11)

        if len(locality) > 1:
            mean_l, std_l = np.mean(locality[1:]), np.std(locality[1:])
            for i, l in enumerate(locality):
                if i > 0 and l < mean_l - std_l:  # 低于均值表示关注远处
                    token = tokens[i].replace('\n', '↵')[:4]
                    ax_loc.annotate(token, (i, l), fontsize=7, rotation=45, fontproperties=chinese_font)

    # X轴标签
    x_labels = []
    for i, token in enumerate(tokens):
        t = token.replace('\n', '↵')
        if len(t) > 4:
            t = t[:4]
        x_labels.append(f"{i}:{t}")

    for ax in [axes[-1, 0], axes[-1, 1], axes[-1, 2]]:
        ax.set_xticks(range(seq_len))
        ax.set_xticklabels(x_labels, rotation=90, fontsize=7, fontproperties=chinese_font)

    plt.suptitle('Attention分析（归一化后）', fontproperties=chinese_font, fontsize=14)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"图表已保存到: {output_file}")
    plt.close()


def visualize_attention_heatmap(attentions, tokens, selected_layers, output_file="attention_heatmap.png"):
    """可视化attention热力图"""
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')

    from matplotlib import font_manager
    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
    chinese_font = font_manager.FontProperties(fname=font_path)

    num_layers = len(attentions)
    actual_layers = []
    for l in selected_layers:
        actual_l = l if l >= 0 else num_layers + l
        if actual_l < num_layers:
            actual_layers.append(actual_l)

    n_layers = len(actual_layers)
    fig, axes = plt.subplots(1, n_layers, figsize=(4*n_layers, 4))
    if n_layers == 1:
        axes = [axes]

    # Token标签
    labels = []
    for i, t in enumerate(tokens):
        t = t.replace('\n', '↵')
        if len(t) > 3:
            t = t[:3]
        labels.append(f"{i}:{t}")

    for ax, layer_idx in zip(axes, actual_layers):
        attn = attentions[layer_idx][0].mean(dim=0).cpu().numpy()  # 平均所有head

        im = ax.imshow(attn, cmap='Blues')
        ax.set_title(f'Layer {layer_idx}', fontsize=10)
        ax.set_xticks(range(len(tokens)))
        ax.set_yticks(range(len(tokens)))
        ax.set_xticklabels(labels, rotation=90, fontsize=6, fontproperties=chinese_font)
        ax.set_yticklabels(labels, fontsize=6, fontproperties=chinese_font)

    plt.suptitle('Attention Heatmap (行=query, 列=key)', fontproperties=chinese_font, fontsize=12)
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"热力图已保存到: {output_file}")
    plt.close()


def print_summary(tokens, layer_entropy, layer_span, layer_locality):
    """打印摘要"""
    print("\n" + "="*80)
    print("Token序列:")
    for i, t in enumerate(tokens):
        t_display = t.replace('\n', '\\n')
        print(f"  {i:3d}: {t_display}")

    print("\n" + "="*80)
    print("归一化Entropy异常点（>1表示比均匀分布更分散）:")
    layers = sorted(layer_entropy.keys())
    for layer in layers:
        entropy = layer_entropy[layer]
        if len(entropy) > 1:
            mean_e = np.mean(entropy[1:])
            std_e = np.std(entropy[1:])
            anomalies = [(i, entropy[i]) for i in range(1, len(entropy))
                        if entropy[i] > mean_e + std_e or entropy[i] < mean_e - std_e]
            if anomalies:
                print(f"  Layer {layer:2d}: ", end="")
                for idx, val in anomalies[:5]:
                    token = tokens[idx].replace('\n', '\\n')[:6]
                    print(f"pos{idx}({token})={val:.2f}  ", end="")
                print()

    print("\n" + "="*80)
    print("归一化Span异常点（>1表示关注比均匀分布更远）:")
    for layer in layers:
        span = layer_span[layer]
        if len(span) > 1:
            mean_s = np.mean(span[1:])
            std_s = np.std(span[1:])
            anomalies = [(i, span[i]) for i in range(1, len(span))
                        if span[i] > mean_s + std_s or span[i] < mean_s - std_s]
            if anomalies:
                print(f"  Layer {layer:2d}: ", end="")
                for idx, val in anomalies[:5]:
                    token = tokens[idx].replace('\n', '\\n')[:6]
                    print(f"pos{idx}({token})={val:.2f}  ", end="")
                print()

    print("\n" + "="*80)
    print("Locality低谷（低=关注远处而非最近的token）:")
    for layer in layers:
        locality = layer_locality[layer]
        if len(locality) > 1:
            mean_l = np.mean(locality[1:])
            std_l = np.std(locality[1:])
            # 低于均值的点
            anomalies = [(i, locality[i]) for i in range(1, len(locality))
                        if locality[i] < mean_l - std_l]
            if anomalies:
                print(f"  Layer {layer:2d}: ", end="")
                for idx, val in anomalies[:5]:
                    token = tokens[idx].replace('\n', '\\n')[:6]
                    print(f"pos{idx}({token})={val:.2f}  ", end="")
                print()


def run_test(text, output_file="attention_analysis.png"):
    """运行测试"""
    model, tokenizer = load_model()

    print(f"\n测试文本: {text}\n")

    # 获取attention
    attentions, tokens, num_layers, num_heads = get_attention_weights(model, tokenizer, text)

    # 选择代表性的层
    selected_layers = [0, 4, 8, 12, 16, 20, 24, 28, -2]

    # 分析
    layer_entropy, layer_span, layer_locality, layer_concentration = analyze_attention(attentions, selected_layers)

    # 打印和可视化
    print_summary(tokens, layer_entropy, layer_span, layer_locality)
    visualize_attention_analysis(tokens, layer_entropy, layer_span, layer_locality, output_file)

    # 热力图暂时跳过
    # heatmap_layers = [0, 12, num_layers-2]
    # heatmap_file = output_file.replace('.png', '_heatmap.png')
    # visualize_attention_heatmap(attentions, tokens, heatmap_layers, heatmap_file)

    return tokens, layer_entropy, layer_span, layer_locality


# 默认测试文本
DEFAULT_TEXT = """甜甜的苹果熊熊的火焰美丽的北京very good一把生锈的手枪"""

if __name__ == "__main__":
    text = DEFAULT_TEXT
    output_file = "attention_analysis.png"

    if len(sys.argv) > 1 and sys.argv[1] not in ["-", "''"]:
        with open(sys.argv[1], 'r', encoding='utf-8') as f:
            text = f.read()

    if len(sys.argv) > 2:
        output_file = sys.argv[2]

    run_test(text, output_file)
