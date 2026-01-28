---
role: 用户
project: Claude Code
directory: D:\work\laya_ai_platform
timestamp: 2026-01-22T03:07:21.819Z
tags: [claude-code, mcp, 配置, 命令行]
---

# 如何在Claude Code中添加MCP服务器

## 问题

如何在Claude Code中添加MCP服务器

## 解决方法

## 添加MCP服务器到Claude Code

### 命令格式
```bash
claude mcp add --transport stdio <服务器名称> -- <命令> "<脚本路径>"
```

### 实际示例
```bash
D:\work\laya_ai_platform>claude mcp add --transport stdio lessons-recorder -- node "D:/work/AIGenTest/backend/mcp-lessons/src/index.js"
```

### 输出结果
```
Added stdio MCP server lessons-recorder with command: node D:/work/AIGenTest/backend/mcp-lessons/src/index.js to local config
File modified: C:\Users\DELL\.claude.json [project: D:\work\laya_ai_platform]
```

### 说明
- `--transport stdio`: 指定传输方式为标准输入输出
- 服务器名称（如 `lessons-recorder`）用于后续引用该MCP服务
- 配置会保存到用户目录下的 `.claude.json` 文件中，并关联到当前项目
