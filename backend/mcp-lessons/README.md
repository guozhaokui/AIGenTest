# MCP Lessons Recorder

一个用于记录AI解决问题时经验教训的MCP（Model Context Protocol）服务。使用Markdown格式存储，便于查看、编辑和版本控制。

## 特点

- 📝 **Markdown格式** - 每个经验记录都是一个独立的Markdown文件，可读性强
- 📁 **按日期组织** - 文件按年/月目录结构存储，便于管理
- 🔍 **全文搜索** - 支持关键词搜索所有经验记录
- 🏷️ **标签系统** - 为经验添加标签，便于分类和检索
- 💡 **简单易用** - 不依赖数据库，直接操作文件系统

## 安装

1. 进入服务目录：
```bash
cd backend/mcp-lessons
```

2. 安装依赖：
```bash
npm install
```

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

1. **record_lesson** - 记录新的经验教训
   ```javascript
   {
     role: "AI",           // 角色：AI 或 用户
     project: "AIGenTest", // 项目名称
     directory: "D:/work/AIGenTest", // 项目目录
     problem: "React组件渲染性能问题", // 问题描述
     solution: "使用React.memo优化...", // 解决方法（支持Markdown）
     tags: ["React", "性能优化"] // 可选标签
   }
   ```

2. **search_lessons** - 搜索经验教训
   ```javascript
   {
     query: "React性能"
   }
   ```

3. **list_recent** - 列出最近的经验记录
   ```javascript
   {
     limit: 10  // 返回记录数量
   }
   ```

4. **read_lesson** - 读取特定的经验记录
   ```javascript
   {
     path: "2024/01/21_10-30-00_react-performance.md"
   }
   ```

5. **list_tags** - 列出所有标签
   ```javascript
   {}
   ```

6. **search_by_tag** - 按标签搜索经验
   ```javascript
   {
     tag: "性能优化"
   }
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
│   ├── index.js         # MCP服务主程序
│   └── storage.js       # Markdown文件存储管理
├── records/             # 经验记录存储目录
│   └── YYYY/MM/         # 按年月组织的目录
├── logs/                # 日志目录
│   ├── error.log        # 错误日志
│   └── combined.log     # 所有日志
├── tools/               # 工具脚本
│   └── export-to-json.js # 导出工具
├── docs/
│   └── 需求.md          # 需求文档
├── package.json         # 项目配置
└── README.md           # 本文档
```

## 优势

1. **人类可读** - 直接打开Markdown文件即可查看，无需专门工具
2. **版本控制友好** - Git可以清晰地追踪每个文件的变化
3. **易于编辑** - 任何文本编辑器都可以编辑Markdown文件
4. **便于迁移** - 只需复制文件夹即可迁移所有数据
5. **支持富文本** - Markdown支持代码块、列表、链接等格式
6. **工具支持** - VSCode、Obsidian、Typora等都能直接预览

## 日志

日志文件位于 `logs/` 目录：
- `error.log` - 仅包含错误信息
- `combined.log` - 包含所有日志信息

## 许可证

MIT