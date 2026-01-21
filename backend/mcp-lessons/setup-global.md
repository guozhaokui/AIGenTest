# 全局使用MCP Lessons服务

## 方法1：快速全局安装（Windows）

### 步骤1：运行安装脚本

```bash
cd backend/mcp-lessons
install-global.bat
```

这会将服务安装到 `%USERPROFILE%\.mcp-lessons` 目录。

### 步骤2：添加到系统PATH

1. 打开"系统属性" → "高级" → "环境变量"
2. 在用户变量或系统变量的PATH中添加：
   ```
   %USERPROFILE%\.mcp-lessons
   ```
3. 重启命令行窗口

### 步骤3：在任何地方使用

```bash
# 在任何项目目录下都可以使用
mcp-lessons record "遇到的问题" "解决方案"
mcp-lessons search "React"
mcp-lessons recent
```

## 方法2：配置Claude Code全局设置

### 找到Claude Code配置文件

Claude Code的全局配置通常在以下位置之一：

**Windows:**
- `%USERPROFILE%\.claude\settings.json`
- `%LOCALAPPDATA%\Claude\settings.json`
- `%APPDATA%\Claude\settings.json`

### 添加MCP配置

将以下内容添加到配置文件中：

```json
{
  "mcpServers": {
    "lessons-recorder": {
      "command": "node",
      "args": ["C:\\Users\\你的用户名\\.mcp-lessons\\src\\index.js"]
    }
  }
}
```

注意：替换"你的用户名"为实际用户名。

## 方法3：创建全局npm包（最优雅）

### 步骤1：创建全局链接

```bash
cd backend/mcp-lessons
npm link
```

### 步骤2：创建全局命令

创建 `bin/mcp-lessons` 文件：

```javascript
#!/usr/bin/env node
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import { spawn } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
const scriptPath = join(__dirname, '..', 'use-lessons.js');

const child = spawn('node', [scriptPath, ...process.argv.slice(2)], {
  stdio: 'inherit'
});

child.on('exit', (code) => {
  process.exit(code);
});
```

### 步骤3：更新package.json

```json
{
  "name": "@local/mcp-lessons",
  "bin": {
    "mcp-lessons": "./bin/mcp-lessons"
  }
}
```

### 步骤4：全局安装

```bash
npm install -g .
```

现在可以在任何地方使用：
```bash
mcp-lessons help
mcp-lessons record "问题" "解决方案"
```

## 方法4：使用环境变量（最简单）

### 创建批处理文件

在 `C:\Windows\` 或任何PATH目录中创建 `mcp-lessons.bat`：

```batch
@echo off
node "D:\work\AIGenTest\backend\mcp-lessons\use-lessons.js" %*
```

然后在任何地方都可以使用：
```bash
mcp-lessons search "关键词"
```

## 选择建议

- **最简单**: 方法4 - 创建批处理文件
- **最完整**: 方法1 - 使用install-global.bat
- **最优雅**: 方法3 - npm全局包
- **Claude集成**: 方法2 - 配置Claude Code

## 数据存储位置

无论使用哪种方法，经验记录都会保存在：
- **项目级**: `项目目录/backend/mcp-lessons/records/`
- **全局级**: `%USERPROFILE%\.mcp-lessons\records\`

这样所有项目都能共享同一个经验库。