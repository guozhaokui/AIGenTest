'use strict';

const app = require('./src/app');

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => {
  /* eslint-disable no-console */
  console.log(`Backend listening on http://localhost:${PORT}`);
});

// 设置超时时间为 30 分钟 (1800000 ms)，3D模型生成需要较长时间
server.setTimeout(1800000);
// 同时设置 keep-alive 超时
server.keepAliveTimeout = 1800000;
server.headersTimeout = 1810000; // 需要比 keepAliveTimeout 大一点


