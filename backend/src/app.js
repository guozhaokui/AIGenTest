'use strict';

const path = require('path');
// 优先加载根目录 .env，再加载 backend/.env（不覆盖已存在变量）
require('dotenv').config({ path: path.resolve(__dirname, '../../.env') });
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const morgan = require('morgan');

const app = express();

app.use(cors());
app.use(express.json({ limit: '2mb' }));
app.use(morgan('dev'));

// 静态文件（如需直接访问上传的图片）
app.use('/uploads', express.static(path.resolve(__dirname, '../..', 'uploads')));

// API
const dimensions = require('./routes/dimensions');
const questions = require('./routes/questions');
const examples = require('./routes/examples');
const evaluations = require('./routes/evaluations');
const questionSets = require('./routes/question-sets');
const runs = require('./routes/runs');
const generate = require('./routes/generate');

app.use('/api/dimensions', dimensions);
app.use('/api/questions', questions);
app.use('/api/examples', examples);
app.use('/api/evaluations', evaluations);
app.use('/api/question-sets', questionSets);
app.use('/api/runs', runs);
app.use('/api/generate', generate);

app.get('/api/health', (_req, res) => res.json({ ok: true }));

module.exports = app;


