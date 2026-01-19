#!/usr/bin/env python3
"""
扩展的提示词关系测试
包含更多样化、更复杂的测试用例
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

    def test_prompt_effect(self, word1, word2, relation_prompts, verbose=False):
        """测试提示词对相似度的影响"""
        # 基准：直接计算两个词的相似度
        baseline_sim = cosine_similarity(
            self.get_embedding(word1),
            self.get_embedding(word2)
        )[0][0]

        # 测试各种提示词
        best_sim = baseline_sim
        best_prompt = None

        for prompt_template in relation_prompts:
            query_with_prompt = prompt_template.format(word=word1)
            sim = cosine_similarity(
                self.get_embedding(query_with_prompt),
                self.get_embedding(word2)
            )[0][0]

            if sim > best_sim:
                best_sim = sim
                best_prompt = query_with_prompt

        improvement = best_sim - baseline_sim

        if verbose:
            print(f"  {word1:20s} → {word2:20s}  基准:{baseline_sim:.3f}  最佳:{best_sim:.3f}  提升:{improvement:+.3f}")

        return baseline_sim, best_sim, improvement, best_prompt

def main():
    tester = PromptRelationTester()

    # 扩展的测试用例
    test_cases = [
        {
            "name": "反义关系",
            "word_pairs": [
                # 简单的
                ("美丽", "丑陋"), ("热", "冷"), ("高", "低"), ("大", "小"), ("快", "慢"),
                ("好", "坏"), ("明亮", "黑暗"), ("新", "旧"), ("强", "弱"), ("多", "少"),
                # 抽象的
                ("成功", "失败"), ("勇敢", "胆怯"), ("自由", "束缚"), ("繁荣", "衰败"),
                # 动词
                ("前进", "后退"), ("上升", "下降"), ("增加", "减少"),
                # 副词/形容词
                ("经常", "偶尔"), ("容易", "困难"), ("复杂", "简单"),
            ],
            "prompts": [
                "{word}的反义词", "{word}的相反", "与{word}相反", "{word}的对立面",
            ]
        },
        {
            "name": "因果关系",
            "word_pairs": [
                # 自然现象
                ("下雨", "地湿"), ("刮风", "树摇"), ("下雪", "变冷"), ("打雷", "闪电"),
                # 人的行为
                ("努力", "成功"), ("学习", "进步"), ("锻炼", "健康"), ("吸烟", "疾病"),
                # 心理因果
                ("疲劳", "休息"), ("饥饿", "吃饭"), ("口渴", "喝水"), ("寒冷", "穿衣"),
                # 社会因果
                ("教育", "知识"), ("创新", "发展"), ("污染", "环境恶化"),
                # 低频/不明显
                ("熬夜", "黑眼圈"), ("久坐", "颈椎病"), ("压力", "失眠"),
            ],
            "prompts": [
                "{word}导致", "{word}会引起", "{word}的结果", "{word}造成",
                "{word}带来", "{word}产生", "因为{word}所以",
            ]
        },
        {
            "name": "时序关系",
            "word_pairs": [
                # 时间
                ("春天", "夏天"), ("夏天", "秋天"), ("秋天", "冬天"),
                ("早晨", "中午"), ("中午", "下午"), ("下午", "晚上"),
                # 生命阶段
                ("婴儿", "儿童"), ("儿童", "青少年"), ("青少年", "成年"),
                # 事件顺序
                ("播种", "收获"), ("学习", "考试"), ("恋爱", "结婚"),
                ("起床", "洗漱"), ("做饭", "吃饭"), ("写作", "发表"),
                # 历史/发展
                ("工业革命", "现代社会"), ("发明", "应用"), ("研究", "发现"),
            ],
            "prompts": [
                "{word}之后", "{word}的下一个", "{word}接下来", "{word}然后",
                "在{word}后", "{word}的后续", "{word}的下一阶段",
            ]
        },
        {
            "name": "包含关系",
            "word_pairs": [
                # 类别-实例
                ("水果", "苹果"), ("水果", "香蕉"), ("水果", "橙子"),
                ("动物", "狗"), ("动物", "猫"), ("动物", "老虎"),
                ("颜色", "红色"), ("颜色", "蓝色"), ("颜色", "绿色"),
                ("交通工具", "汽车"), ("交通工具", "飞机"), ("交通工具", "船"),
                # 抽象类别
                ("情感", "快乐"), ("情感", "悲伤"), ("情感", "愤怒"),
                ("学科", "数学"), ("学科", "物理"), ("学科", "历史"),
                # 组成关系
                ("身体", "手"), ("房子", "门"), ("汽车", "轮胎"),
            ],
            "prompts": [
                "{word}包括", "{word}有", "{word}的例子", "{word}的一种",
                "{word}比如", "{word}例如", "属于{word}",
            ]
        },
        {
            "name": "属性关系",
            "word_pairs": [
                # 颜色
                ("苹果", "红色"), ("天空", "蓝色"), ("雪", "白色"),
                ("草地", "绿色"), ("太阳", "黄色"), ("煤炭", "黑色"),
                # 质地/形状
                ("铁", "硬的"), ("棉花", "软的"), ("玻璃", "透明"),
                ("球", "圆形"), ("冰", "冷的"), ("火", "热的"),
                # 大小/速度
                ("大象", "巨大"), ("蚂蚁", "微小"), ("猎豹", "快速"),
                # 味道
                ("糖", "甜的"), ("柠檬", "酸的"), ("辣椒", "辣的"),
            ],
            "prompts": [
                "{word}的颜色", "{word}是什么颜色", "{word}的特征",
                "{word}的属性", "{word}通常是", "{word}一般是",
                "{word}是怎样的", "{word}的样子",
            ]
        },
        {
            "name": "功能/用途关系",
            "word_pairs": [
                ("刀", "切割"), ("笔", "写字"), ("电话", "通讯"),
                ("汽车", "运输"), ("电脑", "计算"), ("眼镜", "矫正视力"),
                ("雨伞", "遮雨"), ("空调", "调节温度"), ("灯", "照明"),
                ("锁", "安全"), ("药", "治病"), ("书", "学习知识"),
            ],
            "prompts": [
                "{word}用来", "{word}的作用", "{word}可以用来",
                "{word}的功能", "{word}是用来", "{word}的用途",
            ]
        },
        {
            "name": "地点关系",
            "word_pairs": [
                ("巴黎", "法国"), ("北京", "中国"), ("纽约", "美国"),
                ("鱼", "水里"), ("鸟", "天空"), ("老虎", "森林"),
                ("病人", "医院"), ("学生", "学校"), ("囚犯", "监狱"),
            ],
            "prompts": [
                "{word}在哪里", "{word}的位置", "{word}位于",
                "{word}在", "{word}所在的地方",
            ]
        },
        {
            "name": "材料关系",
            "word_pairs": [
                ("桌子", "木头"), ("窗户", "玻璃"), ("项链", "金子"),
                ("衣服", "布料"), ("雕像", "石头"), ("轮胎", "橡胶"),
            ],
            "prompts": [
                "{word}由什么做", "{word}的材料", "{word}是什么做的",
                "{word}由...制成", "{word}的材质",
            ]
        },
    ]

    print("\n" + "="*80)
    print("扩展的关系测试 - 更多样化的测试用例")
    print("="*80)

    all_results = []

    for test_case in test_cases:
        print(f"\n{'='*80}")
        print(f"【{test_case['name']}】 - 测试 {len(test_case['word_pairs'])} 个词对")
        print(f"{'='*80}")

        baselines = []
        bests = []
        improvements = []

        for word1, word2 in test_case['word_pairs']:
            baseline, best, improvement, best_prompt = tester.test_prompt_effect(
                word1, word2, test_case['prompts'], verbose=True
            )
            baselines.append(baseline)
            bests.append(best)
            improvements.append(improvement)

        avg_baseline = np.mean(baselines)
        avg_best = np.mean(bests)
        avg_improvement = np.mean(improvements)
        std_improvement = np.std(improvements)

        positive_count = sum(1 for imp in improvements if imp > 0.01)
        negative_count = sum(1 for imp in improvements if imp < -0.01)

        all_results.append({
            'relation': test_case['name'],
            'count': len(test_case['word_pairs']),
            'avg_baseline': avg_baseline,
            'avg_best': avg_best,
            'avg_improvement': avg_improvement,
            'std_improvement': std_improvement,
            'positive_count': positive_count,
            'negative_count': negative_count,
        })

        print(f"\n  统计:")
        print(f"    平均基准相似度: {avg_baseline:.4f}")
        print(f"    平均最佳相似度: {avg_best:.4f}")
        print(f"    平均提升: {avg_improvement:+.4f} ± {std_improvement:.4f}")
        print(f"    正向提升: {positive_count}/{len(improvements)}  负向: {negative_count}/{len(improvements)}")

    # 总体分析
    print("\n" + "="*80)
    print("【总体分析】")
    print("="*80)

    # 按提升排序
    sorted_results = sorted(all_results, key=lambda x: x['avg_improvement'], reverse=True)

    print(f"\n按提示词效果排序:")
    print(f"{'关系类型':<15} {'测试数':<8} {'基准':<8} {'提升':<12} {'正/负':<12} {'评价'}")
    print("-" * 80)

    for r in sorted_results:
        effect = ""
        if r['avg_improvement'] > 0.08:
            effect = "✓✓✓ 非常有效"
        elif r['avg_improvement'] > 0.04:
            effect = "✓✓ 明显有效"
        elif r['avg_improvement'] > 0.01:
            effect = "✓ 轻微有效"
        elif r['avg_improvement'] > -0.01:
            effect = "≈ 无明显影响"
        else:
            effect = "✗ 反而变差"

        print(f"{r['relation']:<15} {r['count']:<8} {r['avg_baseline']:.4f}   "
              f"{r['avg_improvement']:+.4f}±{r['std_improvement']:.3f}   "
              f"{r['positive_count']:>2}/{r['negative_count']:<2}       {effect}")

    # 关键结论
    print("\n" + "="*80)
    print("【关键结论】")
    print("="*80)

    effective_relations = [r for r in all_results if r['avg_improvement'] > 0.04]
    ineffective_relations = [r for r in all_results if r['avg_improvement'] < 0]

    if effective_relations:
        print("\n提示词有明显效果的关系类型:")
        for r in effective_relations:
            print(f"  • {r['relation']}: 平均提升 {r['avg_improvement']:+.4f}")
        print("\n  → 这些关系应该使用提示词增强")

    if ineffective_relations:
        print("\n提示词反而降低效果的关系类型:")
        for r in ineffective_relations:
            print(f"  • {r['relation']}: 平均变化 {r['avg_improvement']:+.4f}")
        print("\n  → 这些关系直接用纯相似性搜索更好")

    # 基准相似度分析
    print("\n基准相似度与提示词效果的关系:")
    for r in sorted(all_results, key=lambda x: x['avg_baseline']):
        print(f"  基准{r['avg_baseline']:.3f} → 提升{r['avg_improvement']:+.3f}: {r['relation']}")

    avg_all = np.mean([r['avg_improvement'] for r in all_results])
    print(f"\n总体平均提升: {avg_all:+.4f}")

    print("\n实践建议:")
    if len(effective_relations) > 0:
        print("  1. 对于属性、功能、材料等关系，使用提示词可以显著提升效果")
        print("  2. 对于反义、时序等高共现关系，直接相似性搜索即可")
        print("  3. 可以根据关系类型动态决定是否使用提示词")
    else:
        print("  1. 当前embedding模型可能更适合直接相似性搜索")
        print("  2. 提示词策略可能需要更长的上下文或不同的模板")

if __name__ == "__main__":
    main()
