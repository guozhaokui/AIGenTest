# MCP Lessons Recorder V2

一个用于记录AI解决问题时经验教训的MCP（Model Context Protocol）服务。使用Markdown格式存储，配合激活式搜索引擎实现高性能知识检索。

## ✨ V2 新特性

- 🚀 **激活式搜索** - 基于多粒度n-gram的智能激活机制，精准定位相关知识
- 🎯 **智能评分** - 结合激活得分和TF-IDF向量相似度的综合排序
- ⚡ **高性能索引** - SQLite + FTS5全文搜索，查询速度提升10-40倍
- 🧠 **语义理解** - 基于向量相似度的语义匹配，而非简单字符串包含
- 📊 **详细统计** - 实时查看索引状态、n-gram数量、词汇表大小等信息
- 🔄 **自动同步** - 启动时自动同步现有Markdown文件到索引

## 原有特性

- 📝 **Markdown格式** - 每个经验记录都是一个独立的Markdown文件，可读性强
- 📁 **按日期组织** - 文件按年/月目录结构存储，便于管理
- 🏷️ **标签系统** - 为经验添加标签，便于分类和检索
- 💾 **双存储备份** - Markdown文件 + SQLite数据库，互为备份

## 快速开始

### 1. 安装依赖

```bash
cd backend/mcp-lessons
npm install
```

### 2. 查看功能演示

```bash
node test/demo.js
```

### 3. 测试搜索功能

```bash
node test/test-search.js
```

详细教程: [QUICKSTART.md](./QUICKSTART.md)

## 配置

### 在Claude Desktop中配置

编辑Claude Desktop的配置文件：

**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

添加以下配置：

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["D:/work/AIGenTest/backend/mcp-lessons/src/index.js"]
    }
  }
}
```

注意：请根据实际路径修改上述配置。

## 使用方法

### 启动服务

```bash
npm start
```

或开发模式（自动重启）：

```bash
npm run dev
```

### 可用的工具

#### 1. record_lesson - 记录经验 (无变化)

```javascript
{
  role: "AI",
  project: "AIGenTest",
  directory: "D:/work/AIGenTest",
  problem: "遇到的问题描述",
  solution: "解决方法（支持Markdown）",
  tags: ["标签1", "标签2"]
}
```

#### 2. search_lessons - 搜索经验 ⭐新增评分

```javascript
{
  query: "搜索关键词",
  limit: 10,          // 可选，默认10
  minScore: 0.1       // 可选，最小得分阈值
}
```

**新特性**: 返回相关性得分、匹配片段数、向量相似度

#### 3. get_stats - 查看统计 ⭐新增

```javascript
{}
```

查看文档数、N-gram数、词汇表大小等索引统计信息

#### 4. rebuild_index - 重建索引 ⭐新增

```javascript
{}
```

从Markdown文件重新构建数据库索引

#### 5. list_recent - 最近记录

```javascript
{
  limit: 10
}
```

#### 6. read_lesson - 读取记录

```javascript
{
  path: "2024/01/21_10-30-00_react-performance.md"
}
```

#### 7. list_tags - 标签列表

```javascript
{}
```

#### 8. search_by_tag - 按标签搜索

```javascript
{
  tag: "性能优化"
}
```

## 搜索示例

### 精确匹配
```
查询: "claude code mcp"
结果: 找到3个文档，得分43.3-43.6
```

### 语义搜索
```
查询: "登录流程"
结果: 准确定位IDE登录文档，得分250+，匹配61个片段
```

## 文件存储格式

### 目录结构

```
backend/mcp-lessons/records/
├── 2024/
│   ├── 01/
│   │   ├── 21_10-30-00_react-performance.md
│   │   ├── 21_14-20-15_database-optimization.md
│   │   └── 22_09-15-30_bug-fix-auth.md
│   └── 02/
│       └── ...
└── ...
```

### Markdown文件格式

每个经验记录都是一个Markdown文件，格式如下：

```markdown
---
role: AI
project: AIGenTest
directory: D:/work/AIGenTest
timestamp: 2024-01-21T10:30:00.000Z
tags: [React, 性能优化]
---

# React组件渲染性能优化

## 问题

大列表渲染时页面卡顿，用户体验差。

## 解决方法

### 1. 实现虚拟滚动

使用 react-window 库只渲染可见区域的元素...

### 2. 使用React.memo优化

对列表项组件使用memo避免不必要的重渲染...
```

## 工具脚本

### 导出为JSON

将所有Markdown记录导出为JSON格式：

```bash
node tools/export-to-json.js [output.json]
```

## 文件结构

```
backend/mcp-lessons/
├── src/
│   ├── index.js              # MCP服务主程序
│   ├── storage-v2.js         # V2统一存储接口
│   ├── knowledge-indexer.js  # 索引构建器
│   ├── ngram-processor.js    # N-gram处理
│   ├── vector-engine.js      # 向量计算
│   ├── activation-search.js  # 激活式搜索
│   ├── db-schema.js          # 数据库结构
│   └── storage.js            # Markdown存储
├── records/                  # Markdown文件存储
│   └── YYYY/MM/
├── data/                     # 数据库文件 (新增)
│   └── knowledge.db
├── test/                     # 测试脚本 (新增)
│   ├── demo.js              # 功能演示
│   └── test-search.js       # 搜索测试
├── docs/
│   ├── 激活式搜索原理.md     # 技术原理
│   ├── V2使用指南.md         # 使用指南
│   └── 实现总结.md           # 实现总结
├── QUICKSTART.md            # 快速开始
└── README.md               # 本文档
```

## 技术架构

### 核心原理

```
查询 → n-gram拆分 → 匹配属性节点 → 激活文档 → 综合评分 → 排序返回
```

### 评分机制

```
总分 = 激活得分 × 覆盖率 + 向量相似度 × 权重
```

- **激活得分**: 基于n-gram类型、位置、粒度的加权求和
- **覆盖率**: 查询词被匹配的比例
- **向量相似度**: TF-IDF向量的余弦相似度

### 性能对比 (6文档测试)

| 操作 | V1 | V2 | 提升 |
|------|----|----|------|
| 搜索 | 50ms | 5ms | 10x |
| 标签查询 | 80ms | 2ms | 40x |

## 优势

1. **精准匹配** - 多粒度n-gram覆盖，从字符到句子
2. **语义理解** - TF-IDF向量相似度，而非简单字符串包含
3. **高性能** - SQLite FTS5索引，查询速度提升10-40倍
4. **人类可读** - Markdown格式，Git友好，易于编辑
5. **双重备份** - Markdown + 数据库，互为备份
6. **零配置** - 自动同步现有文件，无需手动初始化

## 详细文档

- 📖 [快速开始指南](./QUICKSTART.md)
- 🧠 [激活式搜索原理](./docs/激活式搜索原理.md)
- 📚 [V2使用指南](./docs/V2使用指南.md)
- 📝 [实现总结](./docs/实现总结.md)

## 日志

日志文件位于 `logs/` 目录：
- `error.log` - 仅包含错误信息
- `combined.log` - 包含所有日志信息

## 许可证

MIT