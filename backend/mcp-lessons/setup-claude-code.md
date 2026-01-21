# 在Claude Code中使用MCP Lessons服务

## 配置步骤

### 1. 确保服务可以运行

首先测试MCP服务是否正常工作：

```bash
cd backend/mcp-lessons
node src/index.js
```

如果看到输出 "MCP Lessons Recorder server started"，说明服务正常。按Ctrl+C退出。

### 2. 配置Claude Code

Claude Code支持两种配置方式：

#### 方式A：项目级配置（推荐）

在项目根目录创建 `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["backend/mcp-lessons/src/index.js"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

#### 方式B：全局配置

找到Claude Code的配置目录（通常在用户目录下），创建或编辑 `mcp_config.json`:

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

注意：使用绝对路径。

### 3. 重启Claude Code

配置完成后，需要重启Claude Code以加载MCP服务。

### 4. 验证服务是否加载

在Claude Code中，你可以通过以下方式验证：

1. 查看是否有新的工具可用
2. 尝试使用 `list_recent` 工具查看最近的记录
3. 或使用 `record_lesson` 记录一条测试经验

## 使用示例

### 记录新经验

```javascript
// 使用record_lesson工具
{
  "role": "AI",
  "project": "AIGenTest",
  "directory": "D:/work/AIGenTest",
  "problem": "配置MCP服务遇到问题",
  "solution": "需要在.claude目录下创建mcp.json配置文件...",
  "tags": ["MCP", "配置", "Claude Code"]
}
```

### 搜索经验

```javascript
// 使用search_lessons工具
{
  "query": "MCP"
}
```

### 查看最近记录

```javascript
// 使用list_recent工具
{
  "limit": 5
}
```

## 故障排查

如果MCP服务没有正常加载：

1. **检查日志**：查看 `backend/mcp-lessons/logs/` 目录下的日志文件
2. **验证路径**：确保配置文件中的路径正确
3. **权限问题**：确保Node.js有执行权限
4. **依赖问题**：确保已运行 `npm install`

## 命令行测试

你也可以通过命令行直接测试MCP服务：

```bash
# 启动服务并发送测试命令
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | node backend/mcp-lessons/src/index.js
```

如果返回工具列表，说明服务正常工作。