@ai-eval/shared

用途：
- 提供前后端可复用的常量与（通过 JSDoc 记录的）类型约定。

使用：
```js
// Node / 后端
const Shared = require('@ai-eval/shared');
// or const { MIME_WHITELIST } = require('@ai-eval/shared');

// Vite/前端（也兼容 CJS 导入）
import Shared from '@ai-eval/shared';
// or import { MIME_WHITELIST } from '@ai-eval/shared';
```

导出内容：
- constants.js：MIME_WHITELIST、MAX_UPLOAD_BYTES、DEFAULT_UPLOAD_DIR
- types.js：通过 JSDoc 描述 Domain Type（运行时不导出值）


