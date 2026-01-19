#!/usr/bin/env python3
"""
测试提示词用于判断文档片段是否包含特定信息
这是记忆检索的核心场景：不是找相似的，而是找"包含我需要信息"的片段
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

class ContainmentTester:
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

    def test_containment_methods(self, query, positive_docs, negative_docs):
        """测试不同的包含性判断方法"""
        print(f"\n{'='*80}")
        print(f"查询: {query}")
        print(f"{'='*80}")

        query_emb = self.get_embedding(query)

        # 方法1: 直接相似度
        print(f"\n【方法1: 直接相似度】query_emb ↔ doc_emb")
        print(f"  正样本（应该包含'{query}'的文档）:")
        pos_scores_direct = []
        for doc in positive_docs:
            doc_emb = self.get_embedding(doc)
            sim = cosine_similarity(query_emb, doc_emb)[0][0]
            pos_scores_direct.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        print(f"  负样本（不包含'{query}'的文档）:")
        neg_scores_direct = []
        for doc in negative_docs:
            doc_emb = self.get_embedding(doc)
            sim = cosine_similarity(query_emb, doc_emb)[0][0]
            neg_scores_direct.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        # 方法2: 查询侧提示词
        print(f"\n【方法2: 查询侧提示词】'关于{query}的内容' ↔ doc_emb")
        query_with_prompt = f"关于{query}的内容"
        query_prompted_emb = self.get_embedding(query_with_prompt)

        print(f"  正样本:")
        pos_scores_query_prompt = []
        for doc in positive_docs:
            doc_emb = self.get_embedding(doc)
            sim = cosine_similarity(query_prompted_emb, doc_emb)[0][0]
            pos_scores_query_prompt.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        print(f"  负样本:")
        neg_scores_query_prompt = []
        for doc in negative_docs:
            doc_emb = self.get_embedding(doc)
            sim = cosine_similarity(query_prompted_emb, doc_emb)[0][0]
            neg_scores_query_prompt.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        # 方法3: 文档侧提示词
        print(f"\n【方法3: 文档侧提示词】query_emb ↔ '这段话的主题是...'")
        print(f"  正样本:")
        pos_scores_doc_prompt = []
        for doc in positive_docs:
            doc_with_prompt = f"这段话的主题: {doc}"
            doc_prompted_emb = self.get_embedding(doc_with_prompt)
            sim = cosine_similarity(query_emb, doc_prompted_emb)[0][0]
            pos_scores_doc_prompt.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        print(f"  负样本:")
        neg_scores_doc_prompt = []
        for doc in negative_docs:
            doc_with_prompt = f"这段话的主题: {doc}"
            doc_prompted_emb = self.get_embedding(doc_with_prompt)
            sim = cosine_similarity(query_emb, doc_prompted_emb)[0][0]
            neg_scores_doc_prompt.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        # 方法4: 双侧提示词
        print(f"\n【方法4: 双侧提示词】'关于{query}' ↔ '这段话的主题是...'")
        print(f"  正样本:")
        pos_scores_both_prompt = []
        for doc in positive_docs:
            doc_with_prompt = f"这段话的主题: {doc}"
            doc_prompted_emb = self.get_embedding(doc_with_prompt)
            sim = cosine_similarity(query_prompted_emb, doc_prompted_emb)[0][0]
            pos_scores_both_prompt.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        print(f"  负样本:")
        neg_scores_both_prompt = []
        for doc in negative_docs:
            doc_with_prompt = f"这段话的主题: {doc}"
            doc_prompted_emb = self.get_embedding(doc_with_prompt)
            sim = cosine_similarity(query_prompted_emb, doc_prompted_emb)[0][0]
            neg_scores_both_prompt.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        # 方法5: 明确的包含判断提示词
        print(f"\n【方法5: 明确包含判断】'这段话是否提到{query}' ↔ doc_emb")
        containment_query = f"这段话是否提到{query}"
        containment_query_emb = self.get_embedding(containment_query)

        print(f"  正样本:")
        pos_scores_containment = []
        for doc in positive_docs:
            doc_emb = self.get_embedding(doc)
            sim = cosine_similarity(containment_query_emb, doc_emb)[0][0]
            pos_scores_containment.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        print(f"  负样本:")
        neg_scores_containment = []
        for doc in negative_docs:
            doc_emb = self.get_embedding(doc)
            sim = cosine_similarity(containment_query_emb, doc_emb)[0][0]
            neg_scores_containment.append(sim)
            print(f"    {sim:.4f} | {doc[:60]}...")

        # 分析区分度
        print(f"\n{'='*80}")
        print(f"【区分度分析】")
        print(f"{'='*80}")

        methods = [
            ("直接相似度", pos_scores_direct, neg_scores_direct),
            ("查询侧提示词", pos_scores_query_prompt, neg_scores_query_prompt),
            ("文档侧提示词", pos_scores_doc_prompt, neg_scores_doc_prompt),
            ("双侧提示词", pos_scores_both_prompt, neg_scores_both_prompt),
            ("明确包含判断", pos_scores_containment, neg_scores_containment),
        ]

        best_method = None
        best_separation = -1

        for method_name, pos_scores, neg_scores in methods:
            avg_pos = np.mean(pos_scores)
            avg_neg = np.mean(neg_scores)
            separation = avg_pos - avg_neg  # 正负样本分离度

            # 计算分类准确度（简单阈值法）
            threshold = (avg_pos + avg_neg) / 2
            tp = sum(1 for s in pos_scores if s > threshold)
            tn = sum(1 for s in neg_scores if s <= threshold)
            accuracy = (tp + tn) / (len(pos_scores) + len(neg_scores))

            print(f"\n{method_name}:")
            print(f"  正样本平均: {avg_pos:.4f}")
            print(f"  负样本平均: {avg_neg:.4f}")
            print(f"  分离度: {separation:.4f}")
            print(f"  准确度: {accuracy:.2%} (阈值={threshold:.4f})")

            if separation > best_separation:
                best_separation = separation
                best_method = method_name

        print(f"\n{'='*80}")
        print(f"【最佳方法】: {best_method} (分离度={best_separation:.4f})")
        print(f"{'='*80}")

        return best_method, best_separation

def main():
    tester = ContainmentTester()

    # 测试用例：不同主题的文档片段
    test_cases = [
        {
            "query": "天气",
            "positive_docs": [
                "今天天气很好，阳光明媚，温度适中，非常适合外出活动。",
                "最近天气变化很大，早晚温差较大，大家要注意添加衣物。",
                "气象台预报明天会下雨，出门记得带伞，天气转凉了。",
            ],
            "negative_docs": [
                "我今天去了超市买了很多蔬菜和水果，准备做一顿大餐。",
                "公司最近业务发展很快，我们部门又招了几个新员工。",
                "这本书的内容非常有趣，讲述了一个关于友情的故事。",
            ]
        },
        {
            "query": "价格",
            "positive_docs": [
                "这款手机的价格是2999元，现在有优惠活动，可以便宜200元。",
                "房价又涨了，现在市中心的房子每平米要5万多。",
                "超市里的苹果打折了，原价10元一斤，现在只要6元。",
            ],
            "negative_docs": [
                "这款手机的性能很强，配备了最新的处理器和高清屏幕。",
                "房子的装修风格很现代，采用了大量的智能家居设备。",
                "苹果的营养价值很高，富含维生素和膳食纤维。",
            ]
        },
        {
            "query": "健康",
            "positive_docs": [
                "经常锻炼对健康很有益，可以增强免疫力，预防疾病。",
                "饮食要均衡，多吃蔬菜水果，少吃油腻食物，这样才能保持健康。",
                "睡眠不足会严重影响身体健康，容易导致记忆力下降和免疫力低下。",
            ],
            "negative_docs": [
                "这家健身房的设施很齐全，有跑步机、动感单车和力量训练器材。",
                "蔬菜水果在超市的生鲜区可以找到，品种很多，很新鲜。",
                "他最近工作很忙，经常加班到很晚，周末也很少休息。",
            ]
        },
        {
            "query": "原因",
            "positive_docs": [
                "项目延期的原因是技术难题没有及时解决，导致进度滞后。",
                "他迟到的原因是路上堵车了，本来只需要半小时的路程走了两个小时。",
                "销售下滑的主要原因是市场竞争加剧，竞品推出了更有吸引力的产品。",
            ],
            "negative_docs": [
                "项目已经成功完成了，客户对结果非常满意。",
                "他每天都很准时到达公司，从来不迟到早退。",
                "公司的销售业绩一直保持稳定增长，市场份额不断扩大。",
            ]
        },
    ]

    all_results = []

    for test_case in test_cases:
        best_method, separation = tester.test_containment_methods(
            test_case["query"],
            test_case["positive_docs"],
            test_case["negative_docs"]
        )
        all_results.append({
            'query': test_case['query'],
            'best_method': best_method,
            'separation': separation
        })

    # 总结
    print("\n" + "="*80)
    print("【总结】")
    print("="*80)

    print("\n各查询的最佳方法:")
    for r in all_results:
        print(f"  '{r['query']}': {r['best_method']} (分离度={r['separation']:.4f})")

    # 统计最佳方法
    from collections import Counter
    method_counts = Counter(r['best_method'] for r in all_results)

    print(f"\n最佳方法统计:")
    for method, count in method_counts.most_common():
        print(f"  {method}: {count}/{len(all_results)}")

    avg_separation = np.mean([r['separation'] for r in all_results])
    print(f"\n平均分离度: {avg_separation:.4f}")

    print("\n" + "="*80)
    print("【实践建议】")
    print("="*80)
    print("""
基于测试结果，对于记忆检索系统：

1. 如果某种方法的分离度明显更高：
   → 使用该方法作为默认策略

2. 如果"明确包含判断"效果最好：
   → query可以构造为"这段话是否提到X"
   → 更符合"判断是否包含信息"的语义

3. 如果提示词没有明显改善：
   → 直接相似度搜索已经足够好
   → 提示词可能引入噪音

4. 多阶段检索策略：
   - Stage 1: 用直接相似度快速召回top-K
   - Stage 2: 用提示词重排序，提高精确度
    """)

if __name__ == "__main__":
    main()
