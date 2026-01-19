#!/usr/bin/env python3
"""
使用 Qwen3-Embedding-8B 专用嵌入模型测试关系
验证专用embedding模型是否比通用模型更好地捕捉关系
"""

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

# matplotlib 可选
try:
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    HAS_MATPLOTLIB = True
    # 设置中文字体
    font_path = '/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc'
    font_prop = font_manager.FontProperties(fname=font_path)
    plt.rcParams['font.family'] = font_prop.get_name()
    plt.rcParams['axes.unicode_minus'] = False
except ImportError:
    HAS_MATPLOTLIB = False
    print("Warning: matplotlib not found, will skip visualization")

def cosine_similarity(v1, v2):
    """计算余弦相似度"""
    v1 = np.array(v1)
    v2 = np.array(v2)
    if v1.ndim == 1:
        v1 = v1.reshape(1, -1)
    if v2.ndim == 1:
        v2 = v2.reshape(1, -1)
    dot_product = np.dot(v1, v2.T)
    norm_v1 = np.linalg.norm(v1, axis=1, keepdims=True)
    norm_v2 = np.linalg.norm(v2, axis=1, keepdims=True)
    return dot_product / (norm_v1 * norm_v2.T)

class RelationTester:
    def __init__(self, model_path="/home/layabox/laya/guo/AIGenTest/aiserver/models/Qwen/Qwen3-Embedding-8B"):
        print(f"加载模型: {model_path}")
        # Qwen3-Embedding 要求 padding_side='left'
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True,
            padding_side='left'
        )
        self.model = AutoModel.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            trust_remote_code=True,
        )
        self.model.to("cuda")
        self.model.eval()
        print("模型加载完成")

    def last_token_pool(self, last_hidden_states, attention_mask):
        """
        使用 Last Token Pooling 获取句子嵌入
        Qwen3-Embedding 官方推荐方法
        """
        left_padding = (attention_mask[:, -1].sum() == attention_mask.shape[0])
        if left_padding:
            return last_hidden_states[:, -1]
        else:
            sequence_lengths = attention_mask.sum(dim=1) - 1
            batch_size = last_hidden_states.shape[0]
            return last_hidden_states[torch.arange(batch_size, device=last_hidden_states.device), sequence_lengths]

    def get_embedding(self, text):
        """获取文本的embedding"""
        with torch.no_grad():
            inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
            outputs = self.model(**inputs)
            # 使用 last token pooling（官方推荐）
            embedding = self.last_token_pool(outputs.last_hidden_state, inputs['attention_mask'])
            return embedding.squeeze().float().cpu().numpy()

    def compute_similarity(self, text1, text2):
        """计算两个文本的余弦相似度"""
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        return cosine_similarity(emb1, emb2)[0][0]

    def compute_vector_offset(self, text1, text2):
        """计算向量差"""
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        return emb2 - emb1

    def test_relation_type(self, relation_name, word_pairs):
        """测试一种关系类型"""
        print(f"\n{'='*60}")
        print(f"测试关系类型: {relation_name}")
        print(f"{'='*60}")

        similarities = []
        offsets = []

        for word1, word2 in word_pairs:
            sim = self.compute_similarity(word1, word2)
            offset = self.compute_vector_offset(word1, word2)
            similarities.append(sim)
            offsets.append(offset)
            print(f"{word1:8s} → {word2:8s}  相似度: {sim:.4f}")

        # 分析向量差的一致性
        if len(offsets) > 1:
            offsets_matrix = np.array(offsets)
            # 计算所有offset之间的余弦相似度
            n = len(offsets_matrix)
            offset_sims = []
            for i in range(n):
                for j in range(i+1, n):
                    sim = cosine_similarity(offsets_matrix[i], offsets_matrix[j])[0, 0]
                    offset_sims.append(sim)
            avg_offset_sim = np.mean(offset_sims)
            print(f"\n向量差的平均相似度: {avg_offset_sim:.4f}")
            print("(如果>0.5说明这种关系有一致的向量模式)")

        return similarities, offsets

def main():
    tester = RelationTester()

    # 定义测试用例
    test_cases = {
        "相似关系": [
            ("苹果", "水果"),
            ("汽车", "车辆"),
            ("快乐", "高兴"),
            ("房子", "建筑"),
            ("医生", "职业")
        ],

        "反义关系": [
            ("热", "冷"),
            ("高", "低"),
            ("大", "小"),
            ("快", "慢"),
            ("好", "坏")
        ],

        "包含关系": [
            ("动物", "狗"),
            ("水果", "苹果"),
            ("颜色", "红色"),
            ("交通工具", "汽车"),
            ("食物", "米饭")
        ],

        "时序关系": [
            ("春天", "夏天"),
            ("播种", "收获"),
            ("婴儿", "儿童"),
            ("早晨", "中午"),
            ("学习", "考试")
        ],

        "因果关系": [
            ("下雨", "地湿"),
            ("努力", "成功"),
            ("饥饿", "吃饭"),
            ("寒冷", "穿衣"),
            ("疲劳", "休息")
        ]
    }

    results = {}

    # 测试每种关系
    for relation_name, word_pairs in test_cases.items():
        similarities, offsets = tester.test_relation_type(relation_name, word_pairs)
        results[relation_name] = {
            'similarities': similarities,
            'offsets': offsets
        }

    # 可视化结果
    if HAS_MATPLOTLIB:
        print("\n" + "="*60)
        print("生成可视化...")
        print("="*60)

        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        axes = axes.flatten()

        for idx, (relation_name, data) in enumerate(results.items()):
            if idx >= len(axes):
                break

            ax = axes[idx]
            similarities = data['similarities']

            # 绘制相似度柱状图
            x = range(len(similarities))
            bars = ax.bar(x, similarities, color='steelblue', alpha=0.7)

            # 标记平均值
            avg = np.mean(similarities)
            ax.axhline(y=avg, color='red', linestyle='--',
                      label=f'平均: {avg:.3f}', linewidth=2)

            ax.set_xlabel('词对索引', fontproperties=font_prop)
            ax.set_ylabel('余弦相似度', fontproperties=font_prop)
            ax.set_title(f'{relation_name} - 相似度分布', fontproperties=font_prop)
            ax.legend(prop=font_prop)
            ax.grid(True, alpha=0.3)
            ax.set_ylim([-0.2, 1.0])

            # 添加具体数值
            for i, v in enumerate(similarities):
                ax.text(i, v + 0.02, f'{v:.2f}', ha='center', va='bottom', fontsize=9)

        # 隐藏多余的子图
        for idx in range(len(results), len(axes)):
            axes[idx].set_visible(False)

        plt.tight_layout()
        plt.savefig('relation_qwen3embed_test.png', dpi=150, bbox_inches='tight')
        print(f"图表已保存: relation_qwen3embed_test.png")
    else:
        print("\n(跳过可视化 - matplotlib未安装)")

    # 分析总结
    print("\n" + "="*60)
    print("分析总结")
    print("="*60)

    for relation_name, data in results.items():
        similarities = data['similarities']
        avg_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        print(f"\n{relation_name}:")
        print(f"  平均相似度: {avg_sim:.4f} ± {std_sim:.4f}")

        # 判断
        if relation_name == "相似关系":
            if avg_sim > 0.7:
                print("  ✓ embedding很好地捕捉了相似关系")
            else:
                print("  ✗ embedding对相似关系的捕捉不理想")
        elif relation_name in ["反义关系", "因果关系", "时序关系"]:
            if avg_sim < 0.3:
                print("  ? 低相似度，关系可能需要通过向量差或其他方式表达")
            elif avg_sim > 0.5:
                print("  ? 高相似度，说明这些词经常共现（符合共现假设）")
            else:
                print("  ? 中等相似度")
        elif relation_name == "包含关系":
            if avg_sim > 0.5:
                print("  ✓ 包含关系有较高相似度（子类和父类语义接近）")
            else:
                print("  ✗ 包含关系的相似度较低")

    print("\n" + "="*60)
    print("对比通用模型的差异")
    print("="*60)
    print("""
使用专用embedding模型 (Qwen3-Embedding-8B) 的优势：
1. 专门针对文本表示优化，使用 last token pooling
2. 支持更长的上下文 (32K tokens)
3. 4096维的高维度表示，捕捉更丰富的语义信息

对比通用语言模型，观察是否：
- 相似度的区分度更好（不是所有都接近1.0）
- 不同关系类型有更明显的差异
- 向量差是否更有一致性
    """)

if __name__ == "__main__":
    main()
