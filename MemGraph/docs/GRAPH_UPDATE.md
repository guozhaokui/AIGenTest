# 知识图谱可视化 - 优化更新

## 更新内容

### 1. 布局优化

#### 更宽松的节点间距
- ✅ 排斥力增强：`20000`（原 `8000`）
- ✅ 最小距离增加：`200px`（原 `100px`）
- ✅ 理想连接距离：`300px`
- ✅ 初始布局半径：`250px + 层数 × 350px`

#### 减少抖动
- ✅ 增强阻尼：`0.85`（原 `0.8`）
- ✅ 速度阈值：小于 `0.01` 时停止
- ✅ 减弱中心吸引力：`0.0005`

### 2. 节点拖动功能 ⭐

#### 用户可以手动拖动节点
- **操作方式**：`Shift + 鼠标拖动`节点
- **固定机制**：拖动后的节点会被标记为"固定"（`fixed = true`）
- **物理引擎**：固定的节点不受力的影响，保持用户设置的位置
- **视觉反馈**：
  - 悬停在节点上 + 按住 Shift → 光标变为 `move`
  - 拖动时 → 光标保持 `move`
  - 正常点击 → 光标为 `pointer`（查看详情）

#### 展开节点时保留布局
- ✅ 展开时不会重置固定节点的位置
- ✅ 新节点在源节点周围均匀分布（圆形，半径 `350px`）
- ✅ 新节点不固定（`fixed = false`），允许物理引擎自动调整
- ✅ 用户拖动的布局会被保留

### 3. 交互优化

#### 鼠标操作清晰分离
```
正常点击节点        → 查看详情（左侧面板）
Shift + 拖动节点    → 移动节点位置（固定）
拖动空白区域        → 移动整个画布
鼠标滚轮           → 缩放视图
```

#### 光标提示
- `pointer`：可点击的节点
- `move`：可拖动的节点（Shift 按下时）
- `grabbing`：正在拖动画布
- `default`：默认状态

### 4. 布局算法改进

#### 力的计算
```javascript
// 1. 排斥力（所有节点之间）
force = REPULSION / (distance^2)
→ 距离越近，排斥力越强

// 2. 吸引力（仅连接的节点）
force = ATTRACTION × (distance - idealDistance)
→ 距离偏离理想值时产生恢复力

// 3. 中心吸引力（温和）
force = CENTER_FORCE × distance
→ 防止节点飘离画布中心
```

#### 固定节点的处理
```javascript
if (!node.fixed) {
    // 应用力
    node.applyForce(fx, fy);
}

if (node.fixed) {
    // 重置速度
    node.vx = 0;
    node.vy = 0;
    // 不更新位置
    return;
}
```

## 使用指南

### 基本操作

1. **搜索节点**
   ```
   输入关键词 → 点击"搜索节点"
   ```

2. **查看详情**
   ```
   直接点击节点 → 左侧面板显示信息
   ```

3. **调整布局**
   ```
   按住 Shift → 拖动节点到合适位置
   → 松开后节点固定在该位置
   ```

4. **展开关联**
   ```
   选中节点 → 点击"展开关联节点"
   → 新节点出现在周围
   → 之前拖动的节点保持原位置
   ```

5. **重置布局**
   ```
   点击右上角 🔄 按钮
   → 所有节点取消固定
   → 重新应用物理布局
   ```

### 高级技巧

#### 技巧1：手动整理复杂图谱
```
1. 搜索生成初始图谱
2. 按住 Shift 拖动主要节点到合适位置
3. 展开某个节点查看关联
4. 继续调整新节点位置
5. 最终得到清晰的自定义布局
```

#### 技巧2：逐步探索
```
1. 初始搜索设置：扩展层数 = 0
2. 只显示主节点
3. 手动选择感兴趣的节点
4. 逐个展开关联
5. 拖动整理，构建个性化知识图谱
```

#### 技巧3：保持关注焦点
```
1. 找到核心节点
2. Shift + 拖动到画布中心
3. 展开其关联节点
4. 核心节点保持在中心
5. 关联节点自动围绕分布
```

## 参数说明

### 物理参数（可调）

```javascript
// graph-viewer.js 中可以调整

const REPULSION = 20000;      // 排斥力强度
const ATTRACTION = 0.005;     // 吸引力强度
const DAMPING = 0.85;         // 阻尼系数（越大越稳定）
const MIN_DISTANCE = 200;     // 最小节点间距
const CENTER_FORCE = 0.0005;  // 中心吸引力
```

### 布局参数

```javascript
// 初始布局
const radius = 250 + layerIndex * 350;  // 层级半径

// 展开节点
const radius = 350;  // 新节点距离源节点的半径
```

## 性能优化

### 固定节点减少计算
- 固定的节点跳过物理计算
- 减少 CPU 使用
- 提升大图性能

### 速度阈值
- 速度 < 0.01 时置零
- 避免微小抖动
- 节点更快稳定

### 边界约束
- padding = 100px
- 防止节点飞出画布
- 保持可视范围

## 常见问题

### Q: 节点还是有点挤？
**A**: 调整参数：
```javascript
const REPULSION = 25000;  // 增大排斥力
const MIN_DISTANCE = 250; // 增大最小距离
```

### Q: 如何取消节点固定？
**A**: 点击右上角 🔄 重置视图，所有节点恢复自由状态。

### Q: 拖动节点很难拖到准确位置？
**A**: 先放大视图（滚轮），再 Shift + 拖动，更精确。

### Q: 展开节点后布局混乱？
**A**: 等待 2-3 秒让物理引擎稳定，或手动拖动整理。

### Q: 节点飘出画布了？
**A**: 点击 🔄 重置视图，节点会回到可视范围。

## 对比旧版

| 特性 | 旧版 | 新版 |
|------|------|------|
| 节点间距 | 紧凑 | 宽松 |
| 抖动 | 明显 | 轻微 |
| 用户拖动 | ❌ | ✅ |
| 布局保留 | ❌ | ✅ |
| 展开重置 | 重新布局 | 保留拖动 |
| 操作提示 | 无 | 有 |

## 最新更新 (v3.5)

### 展开相似度阈值控制 ✅

#### 新增功能
- **可调节的相似度阈值**：展开关联节点时可以设置最小相似度
- **默认70%**：只展开高质量关联，避免噪音
- **实时调节**：滑块范围0-100%，步长5%
- **视觉反馈**：显示当前阈值设置和展开的节点数量

#### 使用场景
- **高精度探索**（70-90%）：只看最相关的知识
- **中等范围**（50-70%）：平衡质量和覆盖面
- **广泛发现**（30-50%）：探索弱关联和潜在关系

---

## v3.4 更新

### 节点关联发现 - 动态分析 ✅

#### 核心概念
**从单个节点出发，动态发现所有关联节点**：

1. 选择/搜索一个节点
2. 遍历该节点的所有子向量（ngram、句子、段落、全文等）
3. 对每个子向量搜索相似向量
4. 反向查找相似向量属于哪些文档
5. 自动建立关联并显示详细匹配信息

这种方式**不需要预先知道两个节点**，完全动态发现关联，更灵活且易于扩展。

#### 功能特性

1. **单节点关联分析**
   - 点击节点 → 点击"🔍 查看所有关联详情"
   - 系统自动：
     - 遍历该节点的所有子向量
     - 搜索每个子向量的相似向量
     - 反向查找这些向量属于哪些文档
     - 汇总所有关联节点及其匹配详情

2. **详细匹配展示**
   - 按匹配数量排序显示关联节点
   - 每个关联节点显示：
     - 节点标题和ID
     - 匹配向量对数量
     - 所有匹配详情（源向量 ↓ ↑ 目标向量）
   - 每对匹配显示：
     - 向量粒度（ngram/句子/段落/全文）
     - 向量内容预览（200字符）
     - 相似度百分比

3. **统计信息**
   - 关联节点总数
   - 总匹配数
   - 平均每个节点的匹配数

4. **兼容旧功能**
   - 仍可点击边查看两个节点之间的匹配
   - 旧接口 `/graph/edge-details` 保留（内部调用新方法）

### 技术实现

#### 后端核心方法 (`graph_expander.py`)

**新方法：`get_node_relations()`** - 从单个节点发现所有关联

```python
def get_node_relations(self, doc_id: int, top_k_per_vector: int = 3,
                       min_similarity: float = 0.3):
    """从一个节点出发，发现所有关联节点"""

    # 1. 获取源节点的所有子向量
    source_vectors = self.get_document_vectors(doc_id)

    relations = defaultdict(list)  # {target_doc_id: [matches]}

    # 2. 遍历每个子向量
    for source_vec in source_vectors:
        # 获取向量embeddings
        vector = self.indexer.get_vector(source_vec['faiss_idx'])

        # 3. FAISS 搜索相似向量
        distances, indices = self.indexer.index.search(vector, top_k_per_vector * 3)

        # 4. 对每个相似向量，反向查找它属于哪个文档
        for idx, dist in zip(indices[0], distances[0]):
            if dist < min_similarity:  # 相似度过滤
                continue

            # 反向查询：这个向量属于哪个文档？
            cursor = self.indexer.conn.execute('''
                SELECT doc_id, content, granularity
                FROM document_vectors
                WHERE faiss_idx = ?
            ''', (int(idx),))

            row = cursor.fetchone()
            if row:
                target_doc_id = row[0]
                if target_doc_id != doc_id:  # 排除自己
                    # 记录匹配
                    relations[target_doc_id].append({
                        'source_vec_content': source_vec['content'],
                        'source_vec_granularity': source_vec['granularity'],
                        'target_vec_content': row[1],
                        'target_vec_granularity': row[2],
                        'similarity': dist
                    })

    # 5. 按相似度排序
    for target_doc_id in relations:
        relations[target_doc_id].sort(key=lambda x: x['similarity'], reverse=True)

    return dict(relations)
```

**优势**：
- ✅ 不需要预先知道目标节点
- ✅ 自动发现所有关联
- ✅ 一次遍历获取完整关系图
- ✅ 易于扩展（可调整相似度阈值、每向量返回数等）

#### API 端点 (`server.py`)

**新接口：`POST /graph/node-relations`**

```json
// 请求
{
  "doc_id": 123,
  "top_k_per_vector": 3,      // 每个子向量最多返回3个相似向量
  "min_similarity": 0.3        // 最小相似度阈值
}

// 响应
{
  "success": true,
  "doc_id": 123,
  "relations": {
    "456": [  // 关联的文档ID
      {
        "source_vec_content": "MemGraph使用多粒度向量...",
        "source_vec_granularity": "paragraph",
        "target_vec_content": "向量检索系统需要...",
        "target_vec_granularity": "sentence",
        "similarity": 0.92
      },
      ...
    ],
    "789": [...],
    ...
  },
  "related_nodes": {
    "456": {
      "doc_id": 456,
      "problem": "向量搜索技术",
      "match_count": 5
    },
    ...
  },
  "related_count": 15  // 总共发现15个关联节点
}
```

#### 前端交互 (`graph-viewer.js`)

```javascript
// 1. 点击节点 → 点击"查看所有关联详情"按钮
async function showNodeRelations(docId) {
    const response = await fetch('/graph/node-relations', {
        method: 'POST',
        body: JSON.stringify({
            doc_id: docId,
            top_k_per_vector: 3,
            min_similarity: 0.3
        })
    });

    const data = await response.json();
    displayNodeRelations(docId, data.relations, data.related_nodes);
}

// 2. 显示关联节点列表（按匹配数量排序）
function displayNodeRelations(sourceDocId, relations, relatedNodes) {
    // 统计信息
    const relatedCount = Object.keys(relations).length;
    const totalMatches = sum(relations.values().map(m => m.length));

    // 按匹配数量排序
    const sortedRelations = Object.entries(relations)
        .sort((a, b) => b[1].length - a[1].length);

    // 渲染每个关联节点及其匹配详情
    sortedRelations.forEach(([targetDocId, matches]) => {
        // 显示节点标题
        // 显示所有匹配对（源向量 ↓ ↑ 目标向量）
    });
}
```

### 使用说明

#### 方法1：查看单个节点的所有关联（推荐）✨

1. **搜索/选择节点**：搜索关键词或点击图中的节点
2. **查看关联**：点击左侧面板的"🔍 查看所有关联详情"按钮
3. **分析结果**：
   - 查看统计信息（关联节点数、总匹配数）
   - 按匹配数量排序的关联节点列表
   - 每个关联节点的所有向量匹配详情
4. **深入了解**：每对匹配显示：
   - 源节点的向量（粒度 + 内容）
   - 目标节点的向量（粒度 + 内容）
   - 相似度百分比

**优势**：
- 不需要预先知道目标节点
- 一次性看到所有关联
- 自动发现潜在关联

#### 方法2：查看两个节点之间的匹配（兼容）

1. **悬停**：鼠标移到连接线上，线条变蓝色
2. **点击**：点击连接线，左侧面板显示匹配详情
3. **返回**：点击"← 返回"按钮

### 实际应用场景

**场景1：探索节点的知识网络**
```
目标：了解"MemGraph"这个概念与哪些知识相关
操作：
  1. 搜索"MemGraph"
  2. 点击搜索结果节点
  3. 点击"查看所有关联详情"
结果：
  发现关联了15个节点：
  - 5个关于向量检索技术（段落级匹配）
  - 3个关于知识图谱（句子级匹配）
  - 2个关于FAISS（ngram级匹配）
  - ...
```

**场景2：诊断为什么两个节点关联**
```
问题：为什么"Python异步编程"和"数据库连接池"建立了关联？
操作：
  1. 点击"Python异步编程"节点
  2. 查看所有关联详情
  3. 找到"数据库连接池"
结果：
  看到3个匹配：
  - asyncio事件循环（段落级，89%）
  - 并发连接管理（句子级，76%）
  - async/await关键字（ngram级，65%）
```

**场景3：优化向量粒度策略**
```
问题：当前的多粒度向量是否合理？
操作：随机选择几个节点，查看关联详情
发现：
  - 90%的高质量关联（>80%）来自段落级和句子级
  - ngram级匹配虽然多，但相似度普遍较低（40-60%）
  - n句子级匹配较少但很准确
结论：可以考虑降低ngram级的权重，提高句子级和段落级的权重
```

**场景4：发现意外的知识关联**
```
场景：浏览知识图谱寻找灵感
操作：
  1. 搜索"机器学习"
  2. 查看所有关联详情
  3. 发现关联了"游戏平衡设计"
  4. 查看匹配详情
结果：
  两者通过"强化学习"和"奖励函数"建立了关联
  启发：可以将机器学习技术应用到游戏设计中
```

## 未来改进

- [ ] 双击节点自动居中
- [ ] 右键菜单（固定/解除固定）
- [ ] 节点标签可编辑
- [ ] 保存/加载布局
- [ ] 批量固定/解除固定
- [ ] 磁性吸附网格
- [ ] 边关系类型标注（除相似度外，添加关系类型）
- [ ] 边过滤（按相似度阈值过滤显示）

## 开发者备注

### 关键代码位置

**节点固定检查**：`graph-viewer.js:111-117`
```javascript
if (this.fixed) {
    this.vx = 0;
    this.vy = 0;
    return;
}
```

**拖动节点逻辑**：`graph-viewer.js:294-304`
```javascript
if (isDraggingNode && draggedNode) {
    draggedNode.x += dx;
    draggedNode.y += dy;
    draggedNode.fixed = true;
}
```

**力的应用判断**：`graph-viewer.js:166-167`
```javascript
if (!n1.fixed) n1.applyForce(-fx, -fy);
if (!n2.fixed) n2.applyForce(fx, fy);
```

## 测试建议

1. **压力测试**：搜索生成 20+ 节点，测试性能
2. **拖动测试**：拖动多个节点，展开后检查位置是否保留
3. **重置测试**：点击重置后，检查所有节点是否取消固定
4. **边界测试**：拖动节点到边缘，检查约束是否生效

---

**版本**: v3.5
**更新日期**: 2026-02-02
**作者**: MemGraph Team

## 更新历史

### v3.5 (2026-02-02) - 质量控制
- ✅ **展开相似度阈值控制**
  - 添加滑块设置最小相似度（默认70%）
  - 只展开高质量关联，过滤低相关度节点
  - 实时反馈展开的节点数量
- ✅ 优化 `expand_from_node` 使用 `get_node_relations`
- ✅ 返回每个关联节点的最高相似度和匹配数量

### v3.4 (2026-02-02) - 🎯 重大更新
- ✅ **单节点关联发现** - 核心功能
  - 从单个节点动态发现所有关联节点
  - 遍历节点的所有子向量（ngram/句子/段落/全文）
  - 对每个子向量搜索相似向量
  - 反向查找相似向量属于哪些文档
  - 不需要预先知道目标节点
- ✅ 新增后端方法 `get_node_relations()`
- ✅ 新增API `/graph/node-relations`
- ✅ 详细匹配展示（按匹配数量排序）
- ✅ 统计信息（关联节点数、总匹配数、平均匹配数）
- ✅ 兼容旧版 `/graph/edge-details` 接口

### v3.3 (2026-02-02)
- ✅ 边关系详情显示（点击边查看匹配）
- ✅ 边选中状态（绿色加粗）
- ✅ 节点文字可读性优化

### v3.2 (2026-02-02)
- ✅ 边悬停检测算法
- ✅ 边悬停高亮显示

### v3.1 (2026-01-31)
- ✅ 布局优化（更宽松的节点间距，减少抖动）
- ✅ 节点拖动功能（Shift + 拖动）
- ✅ 固定节点机制（保留用户布局）
- ✅ 展开节点时保留已固定节点的位置

### v3.0 (2026-01-30)
- ✅ 初始版本：动态知识图谱可视化
- ✅ 力导向布局算法
- ✅ 多层节点扩展
- ✅ 节点详情显示
