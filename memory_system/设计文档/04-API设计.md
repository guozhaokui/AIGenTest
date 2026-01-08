# API设计文档

## API概览

系统提供三种接口：

1. **REST API**：HTTP接口，供其他应用调用
2. **Python SDK**：Python库，直接集成
3. **CLI工具**：命令行工具，手动操作

## REST API

### 基础信息

- **Base URL**: `http://localhost:8080/api/v1`
- **认证**: 可选（未来支持API Key）
- **数据格式**: JSON
- **错误格式**: 统一错误响应

### 通用响应格式

```json
{
  "success": true,
  "data": {...},
  "error": null,
  "metadata": {
    "timestamp": "2024-01-10T10:00:00Z",
    "request_id": "req_123456"
  }
}
```

### 错误响应

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "ENTITY_NOT_FOUND",
    "message": "实体 'linux81' 不存在",
    "details": {}
  }
}
```

---

## 核心API端点

### 1. 查询接口

#### POST /query

增强的RAG查询。

**请求：**
```json
{
  "question": "linux81上的QAMath怎么启动？",
  "options": {
    "include_background": true,
    "include_evidence": true,
    "max_docs": 5
  }
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "answer": {
      "content": "QAMath启动步骤：\n1. cd ~/laya/guo/AIGenTest/aiserver/test/QAMath\n2. python build_index.py\n3. ./start_8b.sh",
      "confidence": 0.92
    },
    "background": {
      "entities": [
        {
          "name": "linux81",
          "type": "server",
          "properties": {
            "config": "8核CPU + 64GB RAM",
            "purpose": "运行大模型推理服务"
          }
        },
        {
          "name": "QAMath",
          "type": "project",
          "properties": {
            "function": "数学问答系统",
            "model": "Qwen-8B"
          }
        }
      ]
    },
    "evidence": [
      {
        "source": "日志/2601.md",
        "line": 32,
        "content": "~/laya/guo/AIGenTest/aiserver/test/QAMath$ python build_index.py",
        "relevance": 0.95
      }
    ],
    "uncertainties": []
  }
}
```

---

### 2. 实体管理

#### GET /entities

获取所有实体列表。

**请求参数：**
```
?type=server          # 筛选类型
&status=confirmed     # 筛选状态
&min_confidence=0.7   # 最低置信度
&limit=50             # 返回数量
&offset=0             # 分页偏移
```

**响应：**
```json
{
  "success": true,
  "data": {
    "entities": [
      {
        "id": "ent_123",
        "name": "linux81",
        "type": "server",
        "confidence": 0.92,
        "status": "confirmed",
        "created_at": "2024-01-07T10:00:00Z",
        "metadata": {
          "frequency": 32,
          "last_seen": "2024-01-10"
        }
      }
    ],
    "total": 156,
    "page": {
      "limit": 50,
      "offset": 0,
      "has_more": true
    }
  }
}
```

#### GET /entities/:name

获取单个实体的详细信息。

**响应：**
```json
{
  "success": true,
  "data": {
    "entity": {
      "id": "ent_123",
      "name": "linux81",
      "type": "server",
      "aliases": ["81", "81机器"],
      "confidence": 0.92,
      "status": "confirmed",
      "properties": [
        {
          "key": "config",
          "value": "8核CPU + 64GB RAM",
          "confidence": 0.9,
          "source": "对话/conv_456"
        },
        {
          "key": "purpose",
          "value": "运行大模型推理服务",
          "confidence": 0.85,
          "source": "日志/2601.md"
        }
      ],
      "relations": [
        {
          "type": "hosts",
          "target": "QAMath",
          "confidence": 0.88
        }
      ],
      "learned_from": [
        {
          "source": "日志/2601.md",
          "timestamp": "2024-01-07"
        }
      ]
    }
  }
}
```

#### POST /entities

手动添加实体。

**请求：**
```json
{
  "name": "新服务器",
  "type": "server",
  "properties": {
    "ip": "192.168.1.100",
    "config": "16核 + 128G"
  },
  "confidence": 1.0,
  "status": "confirmed"
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "entity_id": "ent_789",
    "message": "实体创建成功"
  }
}
```

#### PUT /entities/:name

更新实体信息。

**请求：**
```json
{
  "properties": {
    "ip": "192.168.1.101"
  },
  "add_alias": "新别名"
}
```

#### DELETE /entities/:name

删除实体。

**响应：**
```json
{
  "success": true,
  "data": {
    "message": "实体 'linux81' 已删除"
  }
}
```

---

### 3. 学习管理

#### POST /learn/document

学习单个文档。

**请求：**
```json
{
  "path": "/path/to/document.md",
  "force_reindex": false
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "entities_found": 12,
    "new_entities": 3,
    "updated_entities": 9,
    "conflicts": [
      {
        "entity": "QAMath",
        "property": "deployed_on",
        "old_value": "linux81",
        "new_value": "linux21"
      }
    ]
  }
}
```

#### POST /learn/bootstrap

批量学习所有文档。

**请求：**
```json
{
  "docs_path": "/path/to/documents",
  "recursive": true,
  "exclude_patterns": ["**/private/**"]
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "status": "completed",
    "statistics": {
      "total_documents": 156,
      "total_entities": 423,
      "high_confidence": 312,
      "need_confirmation": 45
    },
    "duration_seconds": 12.5
  }
}
```

#### GET /learn/status

查看学习进度（如果正在进行）。

**响应：**
```json
{
  "success": true,
  "data": {
    "is_running": true,
    "progress": {
      "current": 89,
      "total": 156,
      "percentage": 57.1
    },
    "elapsed_seconds": 8.2,
    "estimated_remaining_seconds": 6.1
  }
}
```

---

### 4. 冲突管理

#### GET /conflicts

获取所有未解决的冲突。

**响应：**
```json
{
  "success": true,
  "data": {
    "conflicts": [
      {
        "id": "conflict_123",
        "type": "property_conflict",
        "entity": "QAMath",
        "property": "deployed_on",
        "values": [
          {
            "value": "linux81",
            "source": "日志/2601.md",
            "timestamp": "2024-01-07",
            "confidence": 0.8
          },
          {
            "value": "linux21",
            "source": "日志/2603.md",
            "timestamp": "2024-03-15",
            "confidence": 0.8
          }
        ],
        "detected_at": "2024-03-15T10:00:00Z"
      }
    ],
    "total": 3
  }
}
```

#### POST /conflicts/:id/resolve

解决冲突。

**请求：**
```json
{
  "resolution": "use_latest",  // use_latest | use_most_confident | use_value:xxx | both_valid
  "note": "项目在2024年3月迁移到linux21"
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "message": "冲突已解决",
    "final_value": "linux21"
  }
}
```

---

### 5. 确认管理

#### GET /confirmations

获取需要用户确认的项目。

**响应：**
```json
{
  "success": true,
  "data": {
    "confirmations": [
      {
        "id": "confirm_456",
        "type": "uncertain_entity",
        "entity": "hidream",
        "question": "conda环境'hidream'是用来做什么的？",
        "current_understanding": {
          "type": "environment",
          "confidence": 0.5
        }
      },
      {
        "id": "confirm_789",
        "type": "conflict",
        "question": "QAMath是从linux81迁移到linux21了吗？",
        "options": ["是，迁移了", "否，两台都在运行", "其他"]
      }
    ]
  }
}
```

#### POST /confirmations/:id/answer

回答确认问题。

**请求：**
```json
{
  "answer": "hidream环境用于运行视觉模型，包括DINOv3"
}
```

**响应：**
```json
{
  "success": true,
  "data": {
    "message": "感谢确认，知识库已更新"
  }
}
```

---

### 6. 统计信息

#### GET /stats

获取知识库统计。

**响应：**
```json
{
  "success": true,
  "data": {
    "overview": {
      "total_entities": 156,
      "total_properties": 423,
      "total_relations": 89,
      "total_documents": 234
    },
    "by_type": {
      "server": 12,
      "project": 45,
      "tool": 23,
      "environment": 18,
      "other": 58
    },
    "by_status": {
      "confirmed": 98,
      "inferred": 45,
      "draft": 13
    },
    "confidence": {
      "avg": 0.76,
      "high_confidence_count": 112,
      "low_confidence_count": 23
    },
    "conflicts": {
      "total": 3,
      "resolved": 15,
      "pending": 3
    }
  }
}
```

---

## Python SDK

### 安装

```bash
pip install memory-system
```

### 使用示例

```python
from memory_system import MemoryClient

# 初始化客户端
client = MemoryClient(
    api_url="http://localhost:8080",
    # 或者直接使用本地模式
    local=True,
    db_path=".memory_db"
)

# 查询
result = client.query("linux81上的QAMath怎么启动？")
print(result.answer.content)
print(f"置信度: {result.answer.confidence}")

# 获取实体
entity = client.get_entity("linux81")
print(f"类型: {entity.type}")
print(f"配置: {entity.get_property('config')}")

# 获取所有关系
relations = client.get_relations("linux81")
for rel in relations:
    print(f"{rel.from_entity} --{rel.type}--> {rel.to_entity}")

# 学习文档
client.learn_document("/path/to/new_doc.md")

# 批量学习
client.bootstrap("/path/to/docs")

# 获取统计
stats = client.get_stats()
print(f"总实体数: {stats.total_entities}")
```

### 高级用法

```python
# 自定义提取器
from memory_system import BaseExtractor

class MyCustomExtractor(BaseExtractor):
    def extract(self, text: str):
        # 自定义逻辑
        ...

client.register_extractor(MyCustomExtractor())

# 监听文档变更
from memory_system import DocumentWatcher

watcher = DocumentWatcher(client)
watcher.watch("/path/to/docs", recursive=True)

# 导出知识库
client.export("knowledge.json")

# 导入知识库
client.import_data("team_knowledge.json", merge=True)
```

---

## CLI工具

### 安装

```bash
pip install memory-system
# 或在开发目录
cd memory_system && pip install -e .
```

### 基本命令

#### 初始化

```bash
# 初始化配置
memory-cli init

# 指定文档目录
memory-cli init --docs-path /path/to/docs
```

#### 学习

```bash
# 批量学习所有文档
memory-cli bootstrap --docs-path /path/to/docs

# 学习单个文档
memory-cli learn /path/to/doc.md

# 监听文档变更（后台运行）
memory-cli watch --daemon
```

#### 查询

```bash
# 查询问题
memory-cli query "linux81上的QAMath怎么启动？"

# 输出JSON格式
memory-cli query "..." --json

# 只返回答案（不含背景）
memory-cli query "..." --simple
```

#### 实体管理

```bash
# 列出所有实体
memory-cli entities list

# 筛选
memory-cli entities list --type server --status confirmed

# 查看单个实体
memory-cli entities show linux81

# 添加实体
memory-cli entities add "新服务器" --type server --property "ip=192.168.1.100"

# 更新实体
memory-cli entities update linux81 --property "config=16核128G"

# 删除实体
memory-cli entities delete "旧服务器"
```

#### 冲突管理

```bash
# 列出冲突
memory-cli conflicts list

# 解决冲突
memory-cli conflicts resolve conflict_123 --resolution use_latest
```

#### 统计信息

```bash
# 查看统计
memory-cli stats

# 详细统计
memory-cli stats --detailed

# 导出报告
memory-cli stats --export report.json
```

#### 数据管理

```bash
# 导出知识库
memory-cli export knowledge.json

# 导入知识库
memory-cli import team_knowledge.json --merge

# 备份
memory-cli backup backups/$(date +%Y%m%d).json

# 清空知识库（危险！）
memory-cli reset --confirm
```

---

## WebHook（未来功能）

### 配置

```yaml
# config.yaml
webhooks:
  - event: entity_learned
    url: http://your-server.com/webhook
    method: POST

  - event: conflict_detected
    url: http://your-server.com/webhook
    method: POST
```

### 事件类型

```python
# entity_learned
{
  "event": "entity_learned",
  "timestamp": "2024-01-10T10:00:00Z",
  "data": {
    "entity": {
      "name": "新实体",
      "type": "server",
      "confidence": 0.7
    }
  }
}

# conflict_detected
{
  "event": "conflict_detected",
  "timestamp": "2024-01-10T10:00:00Z",
  "data": {
    "conflict": {
      "entity": "QAMath",
      "property": "deployed_on",
      "values": [...]
    }
  }
}
```

---

## 集成示例

### 集成到NVIDIA聊天应用

```python
# aiserver/test/nvidia/app.py

from memory_system import MemoryClient

memory = MemoryClient(local=True, db_path="../../../memory_system/.memory_db")

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    question = data['message']

    # 从记忆系统获取背景
    memory_result = memory.query(question, include_background=True)

    # 增强prompt
    enhanced_messages = [
        {"role": "system", "content": f"背景知识：\n{format_background(memory_result.background)}"},
        *data['messages']
    ]

    # 调用NVIDIA API
    completion = client.chat.completions.create(
        model=data['model'],
        messages=enhanced_messages,
        ...
    )

    return jsonify(completion)

def format_background(background):
    """格式化背景知识"""
    lines = []
    for entity in background.entities:
        lines.append(f"- {entity.name} ({entity.type}):")
        for key, value in entity.properties.items():
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)
```

### 集成到VS Code插件

```typescript
// vscode-extension/src/extension.ts
import axios from 'axios';

const MEMORY_API = 'http://localhost:8080/api/v1';

async function queryMemory(question: string) {
  const response = await axios.post(`${MEMORY_API}/query`, {
    question,
    options: {
      include_background: true
    }
  });

  return response.data.data;
}

// 使用
const result = await queryMemory("如何部署项目？");
vscode.window.showInformationMessage(result.answer.content);
```

---

## 错误码

| 错误码 | 说明 |
|-------|------|
| `ENTITY_NOT_FOUND` | 实体不存在 |
| `INVALID_ENTITY_TYPE` | 无效的实体类型 |
| `CONFLICT_NOT_FOUND` | 冲突不存在 |
| `LEARNING_IN_PROGRESS` | 正在学习中，请稍后 |
| `INVALID_DOCUMENT_PATH` | 无效的文档路径 |
| `DATABASE_ERROR` | 数据库错误 |
| `VALIDATION_ERROR` | 参数验证错误 |

---

## 下一步

继续阅读：
- [05-部署指南.md](./05-部署指南.md) - 安装和配置
- [00-README.md](./00-README.md) - 项目总览
