# 让Claude Code全局识别MCP Lessons服务

## 核心原理

Claude Code启动时会按以下顺序查找MCP配置：

1. **项目级配置**：`.claude/mcp.json` （只在当前项目生效）
2. **用户级配置**：`~/.claude/mcp.json` （所有项目生效）
3. **全局配置**：Claude Code安装目录的配置

## 方法1：用户级全局配置（推荐）✅

### 步骤1：创建全局MCP配置文件

**Windows路径**：`C:\Users\你的用户名\.claude\mcp.json`

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["D:\\work\\AIGenTest\\backend\\mcp-lessons\\src\\index.js"],
      "name": "AI Lessons Recorder",
      "description": "记录AI解决问题的经验教训",
      "alwaysEnabled": true
    }
  }
}
```

### 步骤2：重启Claude Code

关闭并重新打开Claude Code，MCP服务会自动加载。

### 步骤3：验证配置

在任何项目中，输入：
- "列出最近的经验记录"
- "搜索React相关经验"

如果Claude能够执行这些命令，说明配置成功。

## 方法2：修改settings.json

在 `~/.claude/settings.json` 中添加MCP配置：

```json
{
  "env": {
    // ... 现有配置
  },
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["D:\\work\\AIGenTest\\backend\\mcp-lessons\\src\\index.js"],
      "alwaysEnabled": true
    }
  }
}
```

## 方法3：环境变量配置

创建系统环境变量：

```bash
CLAUDE_MCP_LESSONS_PATH=D:\work\AIGenTest\backend\mcp-lessons\src\index.js
CLAUDE_MCP_ENABLED=true
```

然后在 `~/.claude/mcp.json` 中引用：

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["${CLAUDE_MCP_LESSONS_PATH}"]
    }
  }
}
```

## 方法4：使用启动脚本

创建 `~/.claude/startup.json`：

```json
{
  "autoStart": [
    {
      "type": "mcp",
      "id": "lessons-recorder",
      "command": "node D:\\work\\AIGenTest\\backend\\mcp-lessons\\src\\index.js"
    }
  ]
}
```

## 测试MCP服务是否生效

### 方法A：直接询问Claude

在任何项目中问Claude：
- "你能访问lessons-recorder MCP服务吗？"
- "列出可用的MCP工具"

### 方法B：查看日志

检查MCP服务日志：
```bash
cat D:\work\AIGenTest\backend\mcp-lessons\logs\combined.log
```

### 方法C：使用测试命令

让Claude执行：
```
使用record_lesson工具记录一个测试经验
```

## 故障排查

### 问题1：MCP服务未加载

**症状**：Claude说找不到相关工具

**解决方案**：
1. 检查路径是否正确（使用双反斜杠 `\\`）
2. 确保Node.js已安装
3. 重启Claude Code

### 问题2：权限错误

**症状**：服务启动失败

**解决方案**：
1. 确保有文件读写权限
2. 以管理员身份运行Claude Code（不推荐）
3. 将服务安装到用户目录

### 问题3：路径问题

**症状**：找不到文件

**解决方案**：
使用绝对路径，注意Windows路径格式：
- 正确：`D:\\work\\AIGenTest\\...`
- 错误：`D:\work\AIGenTest\...`

## 最佳实践

### 1. 将MCP服务安装到固定位置

```bash
# 复制到用户目录
xcopy /E /I backend\mcp-lessons %USERPROFILE%\.mcp-lessons
```

### 2. 使用固定的全局路径

在 `~/.claude/mcp.json` 中：

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["%USERPROFILE%\\.mcp-lessons\\src\\index.js"]
    }
  }
}
```

### 3. 创建多个MCP服务

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["...\\mcp-lessons\\src\\index.js"]
    },
    "another-service": {
      "command": "python",
      "args": ["...\\another-service\\main.py"]
    }
  }
}
```

## 验证全局配置成功

当配置成功后，你应该能够：

1. ✅ 在任何项目中使用MCP工具
2. ✅ 不需要每个项目都配置
3. ✅ Claude自动识别可用的工具
4. ✅ 经验记录保存在统一位置

## 快速测试命令

配置完成后，在Claude Code中测试：

```
请使用list_recent工具显示最近的经验记录
```

如果Claude能够执行并返回结果，说明全局配置成功！