'use strict';

const app = require('./src/app');

const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => {
  /* eslint-disable no-console */
  console.log(`Backend listening on http://localhost:${PORT}`);
});

// 设置超时时间为 5 分钟 (300000 ms)
server.setTimeout(300000);


