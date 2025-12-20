# Models.json 配置说明

本文档描述 `backend/data/models.json` 配置文件的结构和用法。

## 概述

`models.json` 定义了系统中可用的所有生成模型，包括图像生成、3D 模型生成等。每个模型配置决定了：
- 使用哪个后端驱动（driver）
- 支持什么类型的输入（文本、图片、多视图等）
- 输出什么类型的内容
- 有哪些可调参数

---

## 配置结构

每个模型配置是一个 JSON 对象，包含以下字段：

```json
{
  "id": "model_unique_id",
  "name": "模型显示名称",
  "driver": "driver_name",
  "input": { ... },
  "output": "image|mesh|audio|video",
  "options": { ... },
  "parameters": [ ... ]
}
```

---

## 字段说明

### `id` (必需)
- **类型**: `string`
- **说明**: 模型的唯一标识符，用于 API 调用和内部引用
- **示例**: `"tripo_3d"`, `"google_gemini_image"`

### `name` (必需)
- **类型**: `string`
- **说明**: 模型的显示名称，用于前端 UI 展示
- **示例**: `"Tripo3D (3D生成)"`, `"Gemini 2.5 Flash"`

### `driver` (必需)
- **类型**: `string`
- **说明**: 后端驱动名称，对应 `backend/src/services/modelDrivers/` 下的文件
- **可用值**:
  - `google` - Google Gemini API
  - `doubao` - 字节跳动豆包 API
  - `tripo` - Tripo3D API
  - `meshy` - Meshy API
  - `trellis` - TRELLIS.2 本地服务
  - `z_image` - 自定义图像生成服务

### `output` (必需)
- **类型**: `string`
- **说明**: 输出类型
- **可用值**:
  - `image` - 图片
  - `mesh` - 3D 模型
  - `audio` - 音频
  - `video` - 视频

---

## `input` 对象

定义模型的输入方式和约束。

```json
"input": {
  "types": ["text", "image"],
  "mode": "combined",
  "default": "text",
  "imageSlots": [ ... ],
  "maxImages": 4
}
```

### `input.types` (必需)
- **类型**: `string[]`
- **说明**: 支持的输入类型列表
- **可用值**:
  - `"text"` - 文本提示词
  - `"image"` - 图片

### `input.mode` (必需)
- **类型**: `string`
- **说明**: 输入模式，决定文本和图片的使用方式
- **可用值**:

| 模式 | 说明 | 示例 |
|------|------|------|
| `single` | 仅支持一种输入 | 仅文本或仅单图 |
| `combined` | 可同时使用文本和图片 | 图文混合生成 |
| `exclusive` | 文本或图片二选一 | Tripo 文本/图片转3D |
| `multiple` | 支持多张图片 | Meshy 多图转3D |
| `multiview` | 多视图模式（需配置 imageSlots） | Tripo 多视图 |
| `params_only` | 仅参数输入（无文本/图片） | Tripo 优化 (Refine) |

### `input.default` (可选)
- **类型**: `string`
- **说明**: `exclusive` 模式下的默认输入类型
- **可用值**: `"text"` 或 `"image"`

### `input.imageSlots` (可选)
- **类型**: `object[]`
- **说明**: `multiview` 模式下的图片槽位配置
- **结构**:

```json
{
  "name": "front",        // 槽位标识（front/left/back/right）
  "label": "正面",         // 显示名称
  "required": true,       // 是否必需
  "description": "正面视图（必需）"  // 描述
}
```

### `input.maxImages` (可选)
- **类型**: `number`
- **说明**: `multiple` 模式下允许的最大图片数量
- **示例**: `4`

---

## `options` 对象

传递给驱动的固定配置，不会在前端显示为可调参数。

```json
"options": {
  "model": "gemini-2.5-flash-image",
  "useProxy": true,
  "url": "http://localhost:8000"
}
```

### 常用选项

| 字段 | 类型 | 说明 |
|------|------|------|
| `model` | string | API 模型标识符 |
| `useProxy` | boolean | 是否使用代理（用于国内访问国外 API） |
| `url` | string | 本地服务地址 |

---

## `parameters` 数组

定义前端可调参数，用户可以在生成时修改这些值。

```json
"parameters": [
  {
    "name": "paramName",
    "label": "参数显示名称",
    "type": "select|number|text",
    "default": "defaultValue",
    "options": [ ... ],
    "min": 0,
    "max": 100,
    "step": 1,
    "description": "参数说明"
  }
]
```

### 参数字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `name` | string | ✅ | 参数标识符，传递给驱动 |
| `label` | string | ✅ | 前端显示名称 |
| `type` | string | ✅ | 参数类型：`select`、`number`、`text`、`model_select` |
| `default` | any | ✅ | 默认值 |
| `options` | array | 仅 select | 选项列表 |
| `min` | number | 仅 number | 最小值 |
| `max` | number | 仅 number | 最大值 |
| `step` | number | 仅 number | 步进值 |
| `driverFilter` | string | 仅 model_select | 过滤驱动类型（如 "tripo"） |
| `description` | string | ❌ | 参数说明/提示 |

### 参数类型示例

#### `select` 类型
```json
{
  "name": "texture",
  "label": "纹理",
  "type": "select",
  "default": "true",
  "options": [
    { "label": "启用", "value": "true" },
    { "label": "禁用", "value": "false" }
  ]
}
```

#### `number` 类型
```json
{
  "name": "faceLimit",
  "label": "面数限制",
  "type": "number",
  "default": 50000,
  "min": 1000,
  "max": 500000,
  "step": 1000,
  "description": "输出网格的最大面数"
}
```

#### `text` 类型
```json
{
  "name": "negativePrompt",
  "label": "负面提示词",
  "type": "text",
  "default": "",
  "description": "不希望出现的内容"
}
```

#### `model_select` 类型

用于从已生成的 3D 模型中选择一个。前端会显示一个带缩略图的选择对话框。

```json
{
  "name": "draftTaskId",
  "label": "选择要优化的模型",
  "type": "model_select",
  "default": "",
  "driverFilter": "tripo",
  "description": "点击选择之前生成的 Tripo 草稿模型"
}
```

**特殊字段**：
- `driverFilter`：可选，过滤只显示特定驱动生成的模型（如 `"tripo"`、`"meshy"`）

**工作原理**：
1. 前端显示"选择模型"按钮
2. 点击后弹出对话框，显示已生成模型的缩略图网格
3. 选中后，自动从 `meta.json` 读取 `taskId` 并填入参数

---

## 完整示例

### 图像生成模型

```json
{
  "id": "google_gemini_image",
  "name": "Gemini 2.5 Flash",
  "driver": "google",
  "input": {
    "types": ["text", "image"],
    "mode": "combined",
    "default": "text"
  },
  "output": "image",
  "options": {
    "model": "gemini-2.5-flash-image",
    "useProxy": true
  },
  "parameters": [
    {
      "name": "aspectRatio",
      "label": "宽高比",
      "type": "select",
      "default": "1:1",
      "options": [
        { "label": "1:1 (方形)", "value": "1:1" },
        { "label": "16:9 (宽屏)", "value": "16:9" }
      ]
    }
  ]
}
```

### 3D 生成模型（单图）

```json
{
  "id": "meshy_image_to_3d",
  "name": "Meshy 图片转3D",
  "driver": "meshy",
  "input": {
    "types": ["image"],
    "mode": "single"
  },
  "output": "mesh",
  "options": {
    "useProxy": false
  },
  "parameters": [
    {
      "name": "enablePbr",
      "label": "PBR材质",
      "type": "select",
      "default": "true",
      "options": [
        { "label": "启用", "value": "true" },
        { "label": "禁用", "value": "false" }
      ]
    },
    {
      "name": "targetPolycount",
      "label": "目标面数",
      "type": "number",
      "default": 30000,
      "min": 1000,
      "max": 200000,
      "step": 1000
    }
  ]
}
```

### 3D 生成模型（多视图）

```json
{
  "id": "tripo_3d_multiview",
  "name": "Tripo3D 多视图 (3D生成)",
  "driver": "tripo",
  "input": {
    "types": ["image"],
    "mode": "multiview",
    "imageSlots": [
      { "name": "front", "label": "正面", "required": true, "description": "正面视图（必需）" },
      { "name": "left", "label": "左侧", "required": false, "description": "左侧视图" },
      { "name": "back", "label": "背面", "required": false, "description": "背面视图" },
      { "name": "right", "label": "右侧", "required": false, "description": "右侧视图" }
    ]
  },
  "output": "mesh",
  "options": {
    "useProxy": false
  },
  "parameters": [
    {
      "name": "modelVersion",
      "label": "版本",
      "type": "select",
      "default": "v3.0-20250812",
      "options": [
        { "label": "最新版 (3.0)", "value": "v3.0-20250812" },
        { "label": "v2.5", "value": "v2.5-20241101" }
      ]
    },
    {
      "name": "modelSeed",
      "label": "随机种子",
      "type": "number",
      "default": -1,
      "min": -1,
      "max": 2147483647,
      "step": 1,
      "description": "-1 表示随机，设置相同种子可生成相同模型 (v2.0+)"
    }
  ]
}
```

### 文本或图片二选一模型

```json
{
  "id": "tripo_3d",
  "name": "Tripo3D (3D生成)",
  "driver": "tripo",
  "input": {
    "types": ["text", "image"],
    "mode": "exclusive",
    "default": "image"
  },
  "output": "mesh",
  "options": {
    "useProxy": false
  },
  "parameters": [ ... ]
}
```

### 仅参数输入模型（params_only）

用于不需要文本或图片输入，仅需要参数的场景（如 Tripo 模型优化）。

```json
{
  "id": "tripo_3d_refine",
  "name": "Tripo3D 优化 (Refine)",
  "driver": "tripo",
  "input": {
    "types": [],
    "mode": "params_only"
  },
  "output": "mesh",
  "options": {
    "useProxy": false,
    "taskType": "refine_model"
  },
  "parameters": [
    {
      "name": "draftTaskId",
      "label": "选择要优化的模型",
      "type": "model_select",
      "default": "",
      "driverFilter": "tripo",
      "description": "点击选择之前生成的 Tripo 草稿模型"
    }
  ]
}
```

**使用说明**：
1. 选择 "Tripo3D 优化 (Refine)" 模型
2. 点击"选择模型"按钮
3. 在弹出的对话框中选择之前生成的 Tripo 模型（支持缩略图预览）
4. 点击生成，等待约 2 分钟获得优化后的模型

**注意**：不支持 `model_version >= v2.0-20240919` 的模型进行优化。

---

## 已配置模型列表

| ID | 名称 | 驱动 | 输入 | 输出 |
|----|------|------|------|------|
| `google_gemini_image` | Gemini 2.5 Flash | google | 文本+图片 | image |
| `google_gemini_image2` | Gemini 3 Pro Image | google | 文本+图片 | image |
| `doubao_seedream_4_5` | Doubao Seedream 4.5 | doubao | 文本+图片 | image |
| `z_image_local` | Z-Image (本地) | z_image | 文本 | image |
| `doubao_seed3d` | Doubao Seed3D | doubao | 图片 | mesh |
| `tripo_3d` | Tripo3D | tripo | 文本或图片 | mesh |
| `tripo_3d_multiview` | Tripo3D 多视图 | tripo | 多视图图片 | mesh |
| `tripo_3d_refine` | Tripo3D 优化 | tripo | 仅参数 | mesh |
| `meshy_image_to_3d` | Meshy 图片转3D | meshy | 图片 | mesh |
| `meshy_text_to_3d` | Meshy 文字转3D | meshy | 文本 | mesh |
| `meshy_multi_image_to_3d` | Meshy 多图转3D | meshy | 多图片 | mesh |
| `meshy_rigging` | Meshy 自动绑骨 | meshy | GLB文件或选择模型 | mesh |
| `meshy_animation` | Meshy 自动动画 | meshy | 仅参数 | mesh |
| `trellis2_image_to_3d` | TRELLIS.2 (本地3D) | trellis | 图片 | mesh |

---

## 添加新模型

1. 在 `backend/data/models.json` 中添加配置
2. 如需新驱动，在 `backend/src/services/modelDrivers/` 创建驱动文件
3. 驱动需导出 `generate({ apiKey, model, prompt, images, config })` 函数
4. 返回格式：`{ dataBase64, mimeType, usage?, meta?, modelPath? }`

---

## 注意事项

1. **布尔值**: 在 `parameters` 中，布尔值使用字符串 `"true"` / `"false"`，便于 select 类型统一处理
2. **默认值一致性**: `parameters` 中的 `default` 值应与驱动的默认行为一致
3. **语言统一**: 所有 `label` 和 `description` 使用中文
4. **options 与 parameters**: `options` 放固定配置，`parameters` 放用户可调参数

