#!/usr/bin/env python3
"""
测试提示词增强的关系查询
验证假设：通过添加关系描述，可以让embedding更精确地找到目标概念
"""

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

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

class PromptRelationTester:
    def __init__(self, model_path="/home/layabox/laya/guo/AIGenTest/aiserver/models/Qwen/Qwen3-Embedding-8B"):
        print(f"加载模型: {model_path}")
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
        """Last Token Pooling"""
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
            embedding = self.last_token_pool(outputs.last_hidden_state, inputs['attention_mask'])
            return embedding.squeeze().float().cpu().numpy()

    def test_prompt_effect(self, word1, word2, relation_prompts):
        """测试提示词对相似度的影响"""
        print(f"\n{'='*70}")
        print(f"测试词对: {word1} ↔ {word2}")
        print(f"{'='*70}")

        # 基准：直接计算两个词的相似度
        baseline_sim = cosine_similarity(
            self.get_embedding(word1),
            self.get_embedding(word2)
        )[0][0]
        print(f"\n【基准】直接相似度:")
        print(f"  '{word1}' ↔ '{word2}': {baseline_sim:.4f}")

        # 测试各种提示词
        print(f"\n【提示词增强】:")
        results = []
        for prompt_template in relation_prompts:
            # 构造带提示词的查询
            query_with_prompt = prompt_template.format(word=word1)
            sim = cosine_similarity(
                self.get_embedding(query_with_prompt),
                self.get_embedding(word2)
            )[0][0]

            improvement = sim - baseline_sim
            results.append({
                'prompt': query_with_prompt,
                'similarity': sim,
                'improvement': improvement
            })

            indicator = "✓✓✓" if improvement > 0.1 else "✓✓" if improvement > 0.05 else "✓" if improvement > 0 else "✗"
            print(f"  {indicator} '{query_with_prompt}' ↔ '{word2}'")
            print(f"      相似度: {sim:.4f}  (变化: {improvement:+.4f})")

        # 找出最佳提示词
        best = max(results, key=lambda x: x['similarity'])
        print(f"\n【最佳提示词】:")
        print(f"  '{best['prompt']}' ↔ '{word2}'")
        print(f"  相似度: {best['similarity']:.4f}  (提升: {best['improvement']:+.4f})")

        return baseline_sim, results

def main():
    tester = PromptRelationTester()

    # 定义测试用例
    test_cases = [
        {
            "name": "反义关系",
            "word_pairs": [
                ("美丽", "丑陋"),
                ("热", "冷"),
                ("高", "低"),
            ],
            "prompts": [
                "{word}的反义词",
                "{word}的相反概念",
                "与{word}相反的是",
                "{word}的对立面",
            ]
        },
        {
            "name": "因果关系",
            "word_pairs": [
                ("下雨", "地湿"),
                ("努力", "成功"),
                ("疲劳", "休息"),
            ],
            "prompts": [
                "{word}导致",
                "{word}会引起",
                "{word}的结果",
                "{word}造成",
            ]
        },
        {
            "name": "时序关系",
            "word_pairs": [
                ("春天", "夏天"),
                ("早晨", "中午"),
                ("婴儿", "儿童"),
            ],
            "prompts": [
                "{word}之后",
                "{word}的下一个阶段",
                "{word}过后是",
                "在{word}后面的是",
            ]
        },
        {
            "name": "包含关系",
            "word_pairs": [
                ("水果", "苹果"),
                ("动物", "狗"),
                ("颜色", "红色"),
            ],
            "prompts": [
                "{word}包括",
                "{word}的例子",
                "{word}的一种",
                "属于{word}的",
            ]
        },
        {
            "name": "属性关系",
            "word_pairs": [
                ("苹果", "红色"),
                ("天空", "蓝色"),
                ("雪", "白色"),
            ],
            "prompts": [
                "{word}的颜色",
                "{word}是什么颜色",
                "{word}通常是",
                "{word}的特征",
            ]
        }
    ]

    all_improvements = []

    for test_case in test_cases:
        print("\n" + "="*70)
        print(f"【关系类型: {test_case['name']}】")
        print("="*70)

        for word1, word2 in test_case['word_pairs']:
            baseline, results = tester.test_prompt_effect(word1, word2, test_case['prompts'])

            # 记录最佳改进
            best_improvement = max(r['improvement'] for r in results)
            all_improvements.append({
                'relation': test_case['name'],
                'pair': f"{word1}-{word2}",
                'baseline': baseline,
                'best_improvement': best_improvement
            })

    # 总结
    print("\n" + "="*70)
    print("【总体分析】")
    print("="*70)

    for relation_name in set(imp['relation'] for imp in all_improvements):
        relation_improvements = [imp for imp in all_improvements if imp['relation'] == relation_name]
        avg_improvement = np.mean([imp['best_improvement'] for imp in relation_improvements])
        avg_baseline = np.mean([imp['baseline'] for imp in relation_improvements])

        print(f"\n{relation_name}:")
        print(f"  平均基准相似度: {avg_baseline:.4f}")
        print(f"  平均最佳提升: {avg_improvement:+.4f}")

        if avg_improvement > 0.1:
            print(f"  ✓✓✓ 提示词非常有效！")
        elif avg_improvement > 0.05:
            print(f"  ✓✓ 提示词有明显效果")
        elif avg_improvement > 0:
            print(f"  ✓ 提示词有轻微帮助")
        else:
            print(f"  ✗ 提示词无明显帮助")

    print("\n" + "="*70)
    print("【关键结论】")
    print("="*70)
    avg_all = np.mean([imp['best_improvement'] for imp in all_improvements])
    print(f"\n所有测试的平均提升: {avg_all:+.4f}")

    if avg_all > 0.1:
        print("""
✓✓✓ 提示词策略非常有效！

建议实现方案：
1. 用户查询时可以指定关系类型：
   - "什么是热的反义词？" → 自动添加"反义词"提示
   - "下雨会导致什么？" → 自动添加"导致"提示

2. 记忆检索时可以分两步：
   - 第一步：用原始查询找相似概念
   - 第二步：用提示词增强找特定关系的概念

3. 可以实现"关系感知"的记忆激活：
   - 根据上下文判断需要什么关系
   - 动态添加相应的提示词
   - 更精确地激活相关记忆
        """)
    elif avg_all > 0.05:
        print("""
✓✓ 提示词策略有明显效果！

可以作为可选的增强功能：
- 当需要特定关系时使用提示词
- 一般查询仍用纯相似性搜索
        """)
    else:
        print("""
提示词策略效果不明显。

可能的原因：
1. Embedding模型在单词级别的语义表示不够丰富
2. 需要更长的上下文才能理解关系
3. 或许需要专门针对关系查询微调
        """)

if __name__ == "__main__":
    main()
