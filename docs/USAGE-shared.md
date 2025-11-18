# 在前后端中使用 @ai-eval/shared

## 安装依赖
在工作区根目录执行（首次）：

```bash
pnpm install
```

## 导入用法
### 后端（Node）
```js
const { MIME_WHITELIST, MAX_UPLOAD_BYTES, DEFAULT_UPLOAD_DIR } = require('@ai-eval/shared');
```

### 前端（Vite + Vue）
```js
import { MIME_WHITELIST, MAX_UPLOAD_BYTES } from '@ai-eval/shared';
```

## 注意
- 默认导出为 CommonJS，Vite/webpack 会自动兼容。
- 如需新增共享内容，建议在 `shared/` 内新增文件并在 `index.js` 聚合导出。


