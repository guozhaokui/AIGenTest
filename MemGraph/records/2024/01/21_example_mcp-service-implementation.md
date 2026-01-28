---
role: AI
project: AIGenTest MCP Lessons Service
directory: D:/work/AIGenTest/backend/mcp-lessons
timestamp: 2024-01-21T15:30:00.000Z
tags: [MCP, 架构设计, 重构]
---

# MCP经验记录服务的存储方案选择

## 问题

最初设计了基于SQLite数据库的复杂方案，包含全文搜索、索引优化等功能。但根据实际需求，这种方案过度工程化了，增加了不必要的复杂性。

用户的实际需求很简单：
- 记录AI解决问题时的经验教训
- 便于查看和编辑
- 支持版本控制

## 解决方法

### 1. 改用Markdown文件存储

每个经验记录保存为一个独立的Markdown文件，优势：
- **人类可读** - 双击即可打开查看
- **易于编辑** - 任何文本编辑器都能编辑
- **版本控制友好** - Git可以清晰追踪变化
- **支持富文本** - 代码块、列表、链接等

### 2. 文件组织结构

采用年/月目录结构：
```
records/
├── 2024/
│   ├── 01/
│   │   ├── 21_10-30-00_bug-fix.md
│   │   └── 21_14-20-15_feature.md
│   └── 02/
```

文件命名规则：`DD_HH-MM-SS_slug.md`

### 3. 实现要点

```javascript
// 生成文件路径
const year = now.getFullYear();
const month = String(now.getMonth() + 1).padStart(2, '0');
const filename = `${day}_${hour}-${minute}-${second}_${slug}.md`;
```

### 4. 保持功能简单

- 使用frontmatter存储元数据
- 简单的全文搜索（读取文件内容）
- 按修改时间排序获取最近记录

## 经验总结

1. **避免过度工程化** - 先满足核心需求，再考虑扩展
2. **选择合适的技术** - 不是所有场景都需要数据库
3. **考虑用户体验** - Markdown文件更容易查看和分享
4. **保持灵活性** - 文件格式便于未来迁移到其他系统