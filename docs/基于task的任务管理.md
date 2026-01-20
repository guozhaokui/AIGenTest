# 基于Task的任务管理系统

## 背景问题

这是一个AIGC项目。
`D:\work\AIGenTest\backend\data\live-gen.json` 这个文件是在ai生成之后保存历史记录的，
由于AI生成速度普遍较慢，现在我想做一个任务系统，允许发起生成请求之后立即转入后台，这个怎么实现比较好，是把请求立即加入 live-gen.json 再加一个完成状态？还是
新建一个当前执行任务的持久列表，有个服务一直检查各个任务的状态？一旦完成之后再加入live-gen.json?

已知：
`D:\work\AIGenTest\backend\src\services\modelDrivers` 这个目录下的各个生成驱动,有的驱动的服务本身是基于task的，能得到taskid，然后根据taskid查询生成状态，有的是没有taskid的，需要一直等待服务返回才知道结果

## 解决方案设计

### 架构概述

采用**混合模式**设计，结合独立任务队列和历史记录的优点：

1. **任务队列** (`tasks.json`) - 管理活跃任务的生命周期
2. **历史记录** (`live-gen.json`) - 只存储成功完成的结果
3. **统一接口** - 无论驱动是同步还是异步，都提供一致的任务管理体验

### 核心组件

```
backend/
├── data/
│   ├── tasks.json          # 活跃任务队列
│   └── live-gen.json       # 完成历史（保持不变）
├── src/
│   ├── routes/
│   │   └── tasks.js        # 任务管理API
│   ├── services/
│   │   ├── taskManager.js  # 任务管理核心
│   │   ├── taskExecutor.js # 任务执行器
│   │   └── modelDrivers/   # 各种AI驱动
```

### 数据结构

#### 任务对象 (Task)

```json
{
  "id": "uuid-v4",
  "type": "image|3d|video|audio",
  "status": "pending|running|completed|failed|cancelled",
  "modelId": "model_identifier",
  "driverId": "driver_name",
  "driverTaskId": "external_task_id",  // 驱动返回的任务ID（如果有）
  "prompt": "generation prompt",
  "params": {},
  "progress": 0-100,
  "result": null,  // 完成后的结果
  "error": null,   // 错误信息
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "startedAt": "ISO-8601",
  "completedAt": "ISO-8601",
  "metadata": {}
}
```

### 任务状态流转

```
pending → running → completed
   ↓         ↓          ↓
   ↓      failed    cancelled
   ↓         ↓          ↓
   └─────────┴──────────┴──→ (可删除)
```

## API 端点详细说明

### 1. 创建任务
**POST** `/api/tasks`

创建新的生成任务，可选择是否立即执行。

**请求体：**
```json
{
  "type": "image",              // 必需：任务类型
  "driverId": "google",         // 必需：驱动ID
  "modelId": "gemini-pro",      // 可选：模型ID
  "prompt": "生成提示词",        // 必需：生成提示
  "params": {},                 // 可选：驱动特定参数
  "metadata": {},               // 可选：额外元数据
  "execute": true               // 可选：是否立即执行（默认true）
}
```

**响应：**
```json
{
  "id": "task-uuid",
  "status": "pending",
  "type": "image",
  "createdAt": "2024-01-20T10:00:00Z",
  ...
}
```

### 2. 查询任务列表
**GET** `/api/tasks`

获取任务列表，支持过滤。

**查询参数：**
- `status` - 按状态过滤 (pending|running|completed|failed|cancelled)
- `type` - 按类型过滤 (image|3d|video|audio)
- `modelId` - 按模型ID过滤

**响应：**
```json
[
  {
    "id": "task-1",
    "status": "completed",
    ...
  },
  {
    "id": "task-2",
    "status": "running",
    "progress": 45,
    ...
  }
]
```

### 3. 获取单个任务
**GET** `/api/tasks/:id`

获取特定任务的详细信息。

**响应：**
```json
{
  "id": "task-uuid",
  "status": "running",
  "progress": 75,
  "prompt": "生成一个美丽的风景画",
  "result": null,
  ...
}
```

### 4. 更新任务
**PATCH** `/api/tasks/:id`

更新任务属性（主要供内部使用）。

**请求体：**
```json
{
  "status": "running",
  "progress": 50,
  "result": {...}
}
```

### 5. 删除任务
**DELETE** `/api/tasks/:id`

删除指定任务。

### 6. 执行任务
**POST** `/api/tasks/:id/execute`

手动执行一个pending状态的任务。

**响应：**
```json
{
  "message": "Task execution started",
  "taskId": "task-uuid"
}
```

### 7. 取消任务
**POST** `/api/tasks/:id/cancel`

取消正在运行的任务。

### 8. 模拟任务（测试用）
**POST** `/api/tasks/:id/simulate`

模拟任务执行过程，用于测试。

**请求体：**
```json
{
  "duration": 10000  // 模拟持续时间（毫秒）
}
```

### 9. 实时更新流
**GET** `/api/tasks/:id/stream`

Server-Sent Events (SSE) 端点，实时推送任务状态更新。

**响应格式：**
```
data: {"id":"task-uuid","status":"running","progress":50}

data: {"id":"task-uuid","status":"completed","result":{...}}

event: complete
data: {"message":"Task finished"}
```

### 10. 任务统计
**GET** `/api/tasks/stats`

获取任务统计信息。

**响应：**
```json
{
  "total": 50,
  "pending": 5,
  "running": 3,
  "completed": 40,
  "failed": 2,
  "executor": {
    "runningTasks": ["task-1", "task-2"],
    "pollingTasks": ["task-1"],
    "loadedDrivers": ["google", "meshy"]
  }
}
```

### 11. 清理旧任务
**POST** `/api/tasks/cleanup`

清理超过指定时间的已完成/失败任务。

**请求体：**
```json
{
  "maxAge": 86400000  // 最大保留时间（毫秒，默认24小时）
}
```

## 任务自动归档机制

### 概述

系统实现了**自动归档**功能，已完成、失败或取消的任务会自动从活跃任务列表移到归档，保持任务列表清洁。

### 归档特性

1. **自动触发**
   - 任务完成时自动归档
   - 任务失败时自动归档
   - 任务取消时自动归档

2. **延迟归档**
   - 默认延迟 5 秒归档（可配置）
   - 给用户反悔的机会
   - 可设置立即归档

3. **数据分离**
   - 活跃任务：`tasks.json`（只保留进行中的任务）
   - 归档任务：`tasks-archive.json`（历史记录）
   - 成功结果：`live-gen.json`（AI生成历史）

### 归档流程

```javascript
任务完成/失败/取消
    ↓
延迟 5 秒（可配置）
    ↓
从 tasks.json 移除
    ↓
保存到 tasks-archive.json
    ↓
如果成功，同时保存到 live-gen.json
```

### 归档 API

#### 查询归档任务
```
GET /api/tasks/archives?status=completed&limit=10
```

#### 获取归档统计
```
GET /api/tasks/archives/stats
```

#### 手动归档所有完成任务
```
POST /api/tasks/archives/all
```

#### 配置归档延迟
```
POST /api/tasks/archives/settings
{
  "delay": 0  // 立即归档
}
```

#### 清理旧归档（默认30天）
```
POST /api/tasks/archives/cleanup
{
  "maxAge": 2592000000
}
```

### 测试结果

运行 `node test-archive.js` 测试显示：
- ✅ 任务完成后自动归档
- ✅ 取消的任务自动归档
- ✅ 归档后从活跃列表删除
- ✅ 归档记录包含完整信息
- ✅ 成功任务同时保存到 live-gen.json

## 任务取消机制

### 改进的取消实现

系统使用 **AbortController** 机制实现了完善的任务取消功能：

1. **模拟任务**
   - ✅ 可立即停止执行
   - ✅ 清除所有定时器
   - ✅ 进度停止更新

2. **异步任务**（支持TaskID的驱动）
   - ✅ 停止状态轮询
   - ✅ 调用驱动的 `cancelTask` 方法（如果支持）
   - ⚠️ 远程任务是否停止取决于驱动实现

3. **同步任务**（不支持TaskID的驱动）
   - ✅ 检查取消信号，阻止后续处理
   - ✅ 防止结果保存到历史记录
   - ⚠️ 正在执行的 API 调用无法中断

### 实现细节

```javascript
// 每个任务都有 AbortController
const abortController = new AbortController();
this.abortControllers.set(taskId, abortController);

// 取消时发送信号
abortController.abort();

// 执行过程中检查信号
if (signal.aborted) {
  throw new Error('Task cancelled');
}
```

### 测试验证

运行单元测试验证取消功能：

```bash
cd backend
node test-cancel-unit.js
```

测试结果显示：
- 任务在取消后立即停止
- 进度不再更新
- 状态正确设置为 "cancelled"
- 不影响后续新任务的执行

## 驱动适配器模式

### 异步驱动（支持Task）
对于原生支持任务的驱动（如Meshy、LTX2）：

```javascript
// 驱动返回任务ID
const driverTaskId = await driver.createTask(params);

// 轮询任务状态
const status = await driver.getTaskStatus(driverTaskId);
```

### 同步驱动（不支持Task）
对于同步驱动（如Google）：

```javascript
// 包装成异步任务
const taskId = generateInternalTaskId();
setImmediate(async () => {
  const result = await driver.generate(params);
  updateTaskStatus(taskId, 'completed', result);
});
```

## 实现细节

### TaskManager 服务
- 管理任务的CRUD操作
- 维护任务状态
- 持久化到 `tasks.json`
- 提供任务统计

### TaskExecutor 服务
- 执行任务（同步/异步）
- 轮询驱动任务状态
- 管理任务生命周期
- 处理错误和重试
- 完成后保存到 `live-gen.json`

### 关键特性

1. **统一接口**：无论驱动是否支持异步，都提供一致的任务管理API
2. **实时更新**：支持SSE和轮询两种方式获取任务状态
3. **错误处理**：自动重试机制，错误信息记录
4. **并发控制**：防止任务重复执行
5. **任务清理**：自动清理过期任务
6. **向后兼容**：`live-gen.json` 结构保持不变

## 使用示例

### 创建并执行任务
```javascript
// 创建任务
const response = await fetch('/api/tasks', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    type: 'image',
    driverId: 'google',
    prompt: '生成美丽的风景画',
    execute: true  // 立即执行
  })
});

const task = await response.json();
console.log('Task created:', task.id);
```

### 轮询任务状态
```javascript
async function pollTask(taskId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/tasks/${taskId}`);
    const task = await response.json();

    console.log(`Status: ${task.status}, Progress: ${task.progress}%`);

    if (task.status === 'completed' || task.status === 'failed') {
      clearInterval(interval);
      console.log('Task finished:', task.result || task.error);
    }
  }, 2000);
}
```

### 使用SSE实时更新
```javascript
const eventSource = new EventSource(`/api/tasks/${taskId}/stream`);

eventSource.onmessage = (event) => {
  const task = JSON.parse(event.data);
  updateUI(task);
};

eventSource.addEventListener('complete', () => {
  eventSource.close();
});
```

## 测试页面

提供了完整的测试界面 `frontend/task-test.html`，包含：

- 创建不同类型任务的按钮
- 实时任务状态显示
- 进度条动画
- 任务管理操作（执行、取消、删除）
- 任务统计面板
- 自动刷新和手动刷新

访问地址：`http://localhost:5173/task-test.html`

## 未来优化方向

1. **性能优化**
   - 使用 SQLite/LevelDB 替代 JSON 文件
   - 实现任务批处理
   - 增加缓存层

2. **高级功能**
   - 任务优先级队列
   - 任务依赖关系
   - 定时任务
   - 任务重试策略配置

3. **监控和日志**
   - 详细的任务执行日志
   - 性能指标收集
   - 错误追踪和告警

4. **扩展性**
   - 插件化驱动加载
   - WebSocket 双向通信
   - 分布式任务队列

## 总结

该任务管理系统成功解决了AIGC慢速生成的问题，提供了：
- 立即响应的API
- 后台异步执行
- 实时状态更新
- 统一的任务管理接口
- 良好的扩展性

系统设计简洁高效，易于维护和扩展，完全满足项目需求。