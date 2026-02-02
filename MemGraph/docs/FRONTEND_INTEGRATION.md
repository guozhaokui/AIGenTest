# 前端集成指南

## 概述

已将 MemGraph 图谱查看器功能集成到 Vue 前端应用中，用户可以在 `http://localhost:5173/knowledge/memory` 访问完整的知识图谱可视化功能。

## 版本历史

- **v1.0** (2026-02-02): 初始集成，将独立的 graph-viewer.html 转换为 Vue 组件

## 集成内容

### 1. 新增文件

#### frontend/src/components/GraphViewer.vue

完整的图谱查看器 Vue 组件，包含以下功能：

**功能特性：**
- ✅ 智能搜索节点
- ✅ 可视化网络图谱
- ✅ 节点详情查看
- ✅ 动态展开关联节点
- ✅ 相似度阈值控制
- ✅ 关联详情对话框
- ✅ 节点删除功能
- ✅ 图谱缩放和导航控制

**技术栈：**
- Vue 3 Composition API
- Element Plus UI 组件
- vis-network 图谱可视化库
- Axios HTTP 客户端

### 2. 修改文件

#### frontend/package.json

添加 `vis-network` 依赖：

```json
{
  "dependencies": {
    "vis-network": "^9.1.9"
  }
}
```

#### frontend/src/views/KnowledgeQuery/MemoryManagement.vue

集成图谱组件，使用标签页切换：

- **知识图谱** 标签页：显示 GraphViewer 组件
- **统计与管理** 标签页：原有的记忆管理功能

#### frontend/src/services/api.js

更新 MemGraph 服务端口：

```javascript
// 从 8800 更新到 8848
const knowledgeApi = axios.create({
  baseURL: 'http://localhost:8848',
  timeout: 30000
});
```

## 使用指南

### 启动服务

1. **启动 MemGraph 后端服务：**

```bash
cd D:\work\AIGenTest\MemGraph
python src/server.py
```

服务运行在 `http://localhost:8848`

2. **安装前端依赖（首次）：**

```bash
cd D:\work\AIGenTest\frontend
npm install
```

3. **启动前端开发服务器：**

```bash
cd D:\work\AIGenTest\frontend
npm run dev
```

前端运行在 `http://localhost:5173`

### 访问图谱查看器

打开浏览器访问：
```
http://localhost:5173/knowledge/memory
```

点击"知识图谱"标签页即可看到图谱查看器。

## 功能说明

### 1. 搜索节点

在搜索框输入关键词（如"什么是 MemGraph"），点击"搜索节点"按钮：

- **初始节点数**：控制初次搜索返回多少个相关节点（1-10）
- **扩展层数**：自动扩展多少层关联节点（0-2）
- **每层节点数**：每层扩展时返回多少个节点（1-5）

### 2. 图谱交互

**鼠标操作：**
- **点击节点**：查看节点详情
- **双击节点**：展开该节点的关联节点
- **拖拽节点**：调整节点位置
- **拖拽空白**：移动整个画布
- **滚轮**：缩放视图

**控制按钮：**
- 🔄 重置视图：恢复默认缩放和位置
- ➕ 放大：放大图谱
- ➖ 缩小：缩小图谱

### 3. 节点详情面板

点击节点后，右侧面板显示：

**基本信息：**
- 标题
- 文档ID
- 层级
- 相似度（关联节点）

**内容：**
- 完整的文档内容

**标签：**
- 文档的所有标签

**展开设置：**
- 最小相似度滑块（0-100%）：控制展开节点时的相似度阈值

**操作按钮：**
- 🔗 **展开关联节点**：基于设置的相似度阈值展开关联节点
- 👁️ **查看所有关联详情**：弹出对话框显示详细的向量匹配信息
- 🗑️ **删除此节点**：永久删除该文档

### 4. 关联详情对话框

点击"查看所有关联详情"后，显示：

**统计信息：**
- 源节点
- 关联节点数
- 总匹配数
- 平均匹配数

**详细匹配：**
- 每个关联节点的折叠面板
- 显示所有向量匹配对
- 包含匹配内容、粒度类型、相似度

### 5. 删除节点

点击"删除此节点"按钮：

1. 弹出确认对话框，详细说明删除影响
2. 确认后：
   - 删除物理文件
   - 删除数据库记录
   - 删除所有向量数据
   - 从图谱中移除节点和相关边
3. 显示删除统计（向量数、n-grams数）

## 图例说明

- 🔵 **紫色节点**：主节点（Layer 0），搜索结果
- 🟢 **绿色节点**：一级关联（Layer 1），从主节点扩展
- 🟠 **橙色节点**：二级关联（Layer 2），从一级关联扩展

## API 端点

图谱组件使用以下 MemGraph API：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/graph/search` | POST | 搜索节点并构建初始图谱 |
| `/graph/expand` | POST | 从指定节点扩展关联节点 |
| `/graph/relations/{doc_id}` | GET | 获取节点的所有关联详情 |
| `/document/{doc_id}` | DELETE | 删除指定文档 |

## 组件架构

```
frontend/src/views/KnowledgeQuery/
└── MemoryManagement.vue (容器页面)
    └── GraphViewer.vue (图谱组件)
        ├── 搜索控制区
        │   ├── 搜索输入框
        │   └── 参数设置
        ├── 图谱画布区
        │   ├── vis-network 图谱
        │   ├── 控制按钮
        │   └── 图例
        ├── 节点详情面板
        │   ├── 基本信息
        │   ├── 内容显示
        │   ├── 标签列表
        │   ├── 展开设置
        │   └── 操作按钮
        └── 关联详情对话框
            ├── 统计信息
            └── 匹配详情列表
```

## 技术细节

### vis-network 配置

```javascript
const networkOptions = {
  nodes: {
    shape: 'dot',
    size: 20,
    font: { size: 14, color: '#333' },
    borderWidth: 2,
    shadow: true
  },
  edges: {
    width: 2,
    color: { inherit: 'both' },
    smooth: { type: 'continuous', roundness: 0.5 }
  },
  physics: {
    enabled: true,
    stabilization: { iterations: 200 },
    barnesHut: {
      gravitationalConstant: -8000,
      springConstant: 0.04,
      springLength: 150
    }
  }
};
```

### 响应式数据

```javascript
// 使用 vis-network 的 DataSet 实现响应式更新
import { DataSet } from 'vis-network/standalone';

const nodesDataSet = new DataSet([]);
const edgesDataSet = new DataSet([]);

// 添加节点
nodesDataSet.add([...]);

// 删除节点
nodesDataSet.remove(nodeId);

// 更新节点
nodesDataSet.update({...});
```

### 事件处理

```javascript
// 点击事件
network.on('click', (params) => {
  if (params.nodes.length > 0) {
    handleNodeClick(params.nodes[0]);
  }
});

// 双击事件
network.on('doubleClick', (params) => {
  if (params.nodes.length > 0) {
    expandNodeFromClick(params.nodes[0]);
  }
});
```

## 性能优化

1. **按需加载 vis-network**：使用动态导入减少初始包大小

```javascript
import('vis-network/standalone').then((vis) => {
  const { DataSet } = vis;
  // 初始化网络
});
```

2. **物理引擎优化**：设置合理的物理参数平衡性能和视觉效果

3. **数据过滤**：展开节点时过滤已存在的节点，避免重复

4. **懒加载关联详情**：只在用户请求时加载详细的向量匹配信息

## 样式定制

### 主题颜色

```css
/* 节点颜色 */
Layer 0: #667eea (紫色)
Layer 1: #48bb78 (绿色)
Layer 2: #ed8936 (橙色)
选中: #ffd700 (金色)

/* 边框 */
正常: 2px
选中: 4px, #ff6b6b

/* 阴影 */
启用 box-shadow 增强立体感
```

### 响应式布局

- 左侧图谱：16/24 宽度
- 右侧详情：8/24 宽度
- 高度固定：600px（可滚动）

## 故障排除

### 问题 1: 图谱不显示

**原因：** vis-network 未正确加载

**解决：**
```bash
cd frontend
npm install vis-network
```

### 问题 2: API 请求失败

**原因：** MemGraph 服务未启动或端口错误

**解决：**
1. 检查后端服务是否运行：`http://localhost:8848/stats`
2. 确认 api.js 中的端口配置正确

### 问题 3: 组件导入错误

**原因：** 路径错误或组件未导出

**解决：**
```javascript
// 确保正确导入
import GraphViewer from '@/components/GraphViewer.vue';
```

### 问题 4: CORS 错误

**原因：** 跨域请求被阻止

**解决：**
后端已配置 CORS（server.py:52-57），确保包含前端域名：
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # 前端地址
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
```

## 未来改进

- [ ] 添加图谱布局算法切换（力导向、层次、圆形等）
- [ ] 实现节点搜索和过滤功能
- [ ] 支持保存和加载图谱视图
- [ ] 添加节点批量操作
- [ ] 实现图谱导出（PNG、SVG）
- [ ] 优化大规模图谱渲染性能
- [ ] 添加图谱统计和分析功能
- [ ] 支持自定义节点样式和颜色
- [ ] 实现图谱的历史回溯
- [ ] 添加快捷键支持

## 相关文件

- `frontend/src/components/GraphViewer.vue`: 图谱组件
- `frontend/src/views/KnowledgeQuery/MemoryManagement.vue`: 容器页面
- `frontend/src/services/api.js`: API 服务
- `frontend/package.json`: 依赖配置
- `static/graph-viewer.html`: 原独立页面（保留）
- `static/graph-viewer.js`: 原独立脚本（保留）

## 对比：独立页面 vs Vue 集成

| 特性 | 独立页面 | Vue 集成 |
|------|---------|----------|
| 访问方式 | `/static/graph-viewer.html` | `/knowledge/memory` |
| UI 框架 | 原生 HTML/CSS | Element Plus |
| 状态管理 | 全局变量 | Vue Composition API |
| 样式 | 内联 CSS | Scoped CSS |
| 交互反馈 | 原生 alert/confirm | Element Plus 对话框 |
| 维护性 | 较低 | 较高 |
| 集成性 | 独立 | 与前端系统集成 |

## 总结

通过这次集成，MemGraph 的图谱查看器从独立页面升级为完整的 Vue 应用组件，提供了：

1. ✅ 统一的用户界面和体验
2. ✅ 更好的代码组织和维护性
3. ✅ 与前端系统的深度集成
4. ✅ 响应式设计和现代化 UI
5. ✅ 完整的功能保留和增强

用户现在可以在统一的前端应用中访问所有 MemGraph 功能，包括智能问答、文档管理和知识图谱可视化。
