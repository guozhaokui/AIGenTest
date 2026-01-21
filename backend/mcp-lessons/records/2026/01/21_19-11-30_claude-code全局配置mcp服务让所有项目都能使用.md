---
role: AI
project: AIGenTest MCP配置
directory: D:/work/AIGenTest
timestamp: 2026-01-21T11:11:30.979Z
tags: [MCP, 配置, Claude Code, 全局设置]
---

# Claude Code全局配置MCP服务，让所有项目都能使用

## 问题

Claude Code全局配置MCP服务，让所有项目都能使用

## 解决方法

## 配置方法

### 1. 创建全局MCP配置文件

在用户目录创建配置文件：
- `C:\Users\用户名\.claude\mcp.json`
- 或 `C:\Users\用户名\.claude\.mcp.json`

### 2. 配置内容

```json
{
  "lessons-recorder": {
    "type": "stdio",
    "command": "node",
    "args": ["D:\\work\\AIGenTest\\backend\\mcp-lessons\\src\\index.js"],
    "name": "AI Lessons Recorder",
    "description": "记录AI解决问题的经验教训"
  }
}
```

注意：Windows路径需要双反斜杠。

### 3. 重启Claude Code

配置后需要重启Claude Code才能生效。

### 4. 备选方案

如果MCP配置不生效，可以：
- 使用便捷脚本：`node use-lessons.js`
- 创建批处理文件放在PATH中
- 让AI助手帮助操作
