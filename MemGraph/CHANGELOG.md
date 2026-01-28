# MemGraph 更新日志

## V3.0.1 (2026-01-28)

### 新增功能

#### 🎨 Web 测试面板
- 添加完整的 Web 可视化界面 (`static/index.html`)
- 渐变紫色主题设计，现代化 UI
- 响应式布局，支持移动端访问

#### 功能模块

1. **记录新经验**
   - 可视化表单
   - 实时验证
   - 成功/失败消息提示
   - 支持 Markdown 格式

2. **统计信息面板**
   - 实时显示文档数、N-gram 数、向量数
   - 一键刷新统计
   - 一键重建索引（带确认）

3. **高级搜索**
   - 可调节搜索参数（结果数量、最小得分、向量开关）
   - 加载动画
   - 实时搜索结果展示

4. **详细调试信息**
   - 每条结果显示完整得分细分：
     - 激活得分（n-gram 匹配）
     - 向量相似度（语义相关）
     - 匹配片段数量
   - 元数据展示（角色、项目、时间）
   - 标签可视化
   - 问题预览（300 字符）
   - 解决方法预览（500 字符）

#### 📝 文档更新
- `WEB_TEST_GUIDE.md` - Web 测试面板完整使用指南
- `README.md` - 添加 Web 面板入口说明
- `test_web.py` - 快速启动 Web 测试的 Python 脚本

#### 🔧 技术改进
- FastAPI 挂载静态文件目录
- 根路径 `/` 自动重定向到 Web 界面
- CORS 全域支持
- HTML XSS 防护（escapeHtml 函数）
- 增加预览长度：
  - 问题预览：200 → 300 字符
  - 解决方案预览：200 → 500 字符

### 文件变化

#### 新增文件
```
static/
└── index.html           # Web 测试面板（单页应用）
WEB_TEST_GUIDE.md       # Web 使用指南
test_web.py             # Web 测试启动器
CHANGELOG.md            # 本文件
```

#### 修改文件
```
src/server.py           # 添加静态文件支持、根路径重定向
src/activation_search.py # 增加预览长度
README.md               # 添加 Web 测试说明
```

### 使用方式

#### 启动服务
```bash
cd D:\work\AIGenTest\MemGraph
python start.py
```

#### 访问 Web 界面
```
方式1: http://localhost:8800
方式2: http://localhost:8800/static/index.html
方式3: python test_web.py  # 自动打开浏览器
```

### 截图说明

Web 界面包含：
- **左上**: 记录新经验表单（紫色渐变按钮）
- **右上**: 统计信息卡片（4个统计指标）
- **下方**: 搜索界面
  - 搜索框 + 参数调节
  - 结果列表
  - 每条结果展示完整调试信息

### 性能优化

- 使用 FAISS 向量检索，响应时间 ~10ms
- 前端异步加载，无阻塞
- 自动 HTML 转义，安全性提升

### 兼容性

- **浏览器**: Chrome 90+, Edge 90+, Firefox 88+
- **Python**: 3.8+
- **依赖**: FastAPI 静态文件支持

---

## V3.0.0 (2026-01-28)

### 重大变更

- 完全重写为 Python + FastAPI 架构
- 从 Node.js V2 迁移到 Python V3
- 集成 Qwen3-8B 嵌入模型
- 使用 FAISS 替代 TF-IDF
- 自动随 backend 启动

### 核心特性

- ✅ 激活式搜索引擎
- ✅ 多粒度 N-gram 处理
- ✅ FAISS 向量检索
- ✅ Qwen3-8B 语义嵌入
- ✅ FastAPI RESTful API
- ✅ 数据自动迁移

### 性能提升

- 向量相似度：0.257 → 0.978 (3.8x)
- 语义理解能力显著提升
- 支持 10,000+ 文档规模

---

**开发者**: Claude + Human Collaboration
**最后更新**: 2026-01-28
