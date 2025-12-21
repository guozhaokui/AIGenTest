'use strict';

const path = require('path');
// 优先加载根目录 .env，再加载 backend/.env（不覆盖已存在变量）
require('dotenv').config({ path: path.resolve(__dirname, '../../.env') });
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');

// 配置 HTTP(S) 代理（如存在）
try {
  const proxy = process.env.HTTPS_PROXY || process.env.HTTP_PROXY;
  if (proxy) {
    // 动态引入，避免未安装时报错
    // eslint-disable-next-line global-require
    const { setGlobalDispatcher, ProxyAgent } = require('undici');
    setGlobalDispatcher(new ProxyAgent(proxy));
    /* eslint-disable no-console */
    console.log('[backend] Using proxy:', proxy);
  }
} catch (e) {
  // ignore
}

const app = express();

app.use(cors());
app.use(express.json({ limit: '2mb' }));
app.use(morgan('dev'));

// 静态文件（如需直接访问上传的图片）
// 新路径
app.use('/imagedb', express.static(path.resolve(__dirname, '..', 'imagedb')));
// 新增：开启模型文件的静态服务
app.use('/modeldb', express.static(path.resolve(__dirname, '..', 'modeldb')));
// 新增：开启音频文件的静态服务
app.use('/sounddb', express.static(path.resolve(__dirname, '..', 'sounddb')));

// API
const dimensions = require('./routes/dimensions');
const questions = require('./routes/questions');
const examples = require('./routes/examples');
const evaluations = require('./routes/evaluations');
const questionSets = require('./routes/question-sets');
const runs = require('./routes/runs');
const generate = require('./routes/generate');
const models = require('./routes/models');
const liveGen = require('./routes/live-gen');
const imagemgr = require('./routes/imagemgr');

app.use('/api/dimensions', dimensions);
app.use('/api/questions', questions);
app.use('/api/examples', examples);
app.use('/api/evaluations', evaluations);
app.use('/api/question-sets', questionSets);
app.use('/api/runs', runs);
app.use('/api/generate', generate);
app.use('/api/models', models);
app.use('/api/live-gen', liveGen);
app.use('/api/imagemgr', imagemgr);

app.get('/api/health', (_req, res) => res.json({ ok: true }));

// Global error handler
app.use((err, req, res, next) => {
  console.error('[Global Error]', err);
  if (res.headersSent) {
    return next(err);
  }
  res.status(err.status || 500).json({
    error: 'internal_server_error',
    message: err.message || 'Unknown error',
    stack: process.env.NODE_ENV === 'production' ? undefined : err.stack,
    code: err.code
  });
});

module.exports = app;


