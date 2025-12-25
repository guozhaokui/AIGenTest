'use strict';

/**
 * 图片管理服务代理
 * 将请求转发到 Python FastAPI 图片管理服务
 */

const express = require('express');
const axios = require('axios');
const multer = require('multer');
const FormData = require('form-data');

const router = express.Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

// 图片管理服务地址
const IMAGEMGR_API = process.env.IMAGEMGR_API || 'http://127.0.0.1:6060';
console.log('[imagemgr] IMAGEMGR_API =', IMAGEMGR_API);

// 创建 axios 实例
const imagemgrClient = axios.create({
  baseURL: IMAGEMGR_API,
  timeout: 60000
});

// ==================== 健康检查 ====================

router.get('/health', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/health');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 统计 ====================

router.get('/stats', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/stats');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 图片列表 ====================

router.get('/images', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/images', { params: req.query });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 上传图片 ====================

router.post('/images', upload.single('file'), async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const form = new FormData();
    form.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype
    });
    
    if (req.body.source) {
      form.append('source', req.body.source);
    }

    const response = await imagemgrClient.post('/api/images', form, {
      headers: form.getHeaders()
    });
    
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 获取单个图片信息 ====================

router.get('/images/:sha256', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get(`/api/images/${req.params.sha256}`);
    res.json(response.data);
  } catch (err) {
    if (err.response?.status === 404) {
      return res.status(404).json({ error: 'Image not found' });
    }
    next(err);
  }
});

// ==================== 获取图片文件 ====================

router.get('/images/:sha256/file', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get(`/api/images/${req.params.sha256}/file`, {
      responseType: 'stream'
    });
    
    res.set('Content-Type', response.headers['content-type']);
    response.data.pipe(res);
  } catch (err) {
    if (err.response?.status === 404) {
      return res.status(404).json({ error: 'Image not found' });
    }
    next(err);
  }
});

// ==================== 获取缩略图 ====================

router.get('/images/:sha256/thumbnail', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get(`/api/images/${req.params.sha256}/thumbnail`, {
      responseType: 'stream'
    });
    
    res.set('Content-Type', response.headers['content-type']);
    response.data.pipe(res);
  } catch (err) {
    if (err.response?.status === 404) {
      return res.status(404).json({ error: 'Thumbnail not found' });
    }
    next(err);
  }
});

// ==================== 删除图片 ====================

router.delete('/images/:sha256', async (req, res, next) => {
  try {
    const response = await imagemgrClient.delete(`/api/images/${req.params.sha256}`, {
      params: req.query
    });
    res.json(response.data);
  } catch (err) {
    if (err.response?.status === 404) {
      return res.status(404).json({ error: 'Image not found' });
    }
    next(err);
  }
});

// ==================== 描述 ====================

router.get('/images/:sha256/descriptions', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get(`/api/images/${req.params.sha256}/descriptions`);
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

router.post('/images/:sha256/descriptions', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post(
      `/api/images/${req.params.sha256}/descriptions`,
      req.body
    );
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 通用 VLM 描述生成（不保存）
router.post('/vlm/generate', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post(
      '/api/vlm/generate',
      req.body,
      { timeout: 120000 }  // 2分钟超时，VLM 可能比较慢
    );
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 保存描述并计算嵌入
router.post('/images/:sha256/descriptions/save', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post(
      `/api/images/${req.params.sha256}/descriptions/save`,
      req.body,
      { timeout: 60000 }
    );
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 重新计算嵌入 ====================

router.post('/images/:sha256/recompute-embedding', async (req, res, next) => {
  try {
    const params = {};
    if (req.query.include_text === 'true') {
      params.include_text = true;
    }
    const response = await imagemgrClient.post(
      `/api/images/${req.params.sha256}/recompute-embedding`,
      null,
      { params }
    );
    res.json(response.data);
  } catch (err) {
    if (err.response?.status === 404) {
      return res.status(404).json({ error: 'Image not found' });
    }
    next(err);
  }
});

// ==================== 文本搜索 ====================

router.post('/search/text', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/search/text', req.body);
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 获取文本搜索可用的索引列表
router.get('/search/text-indexes', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/search/text-indexes');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 通过 sha256 搜索相似图片
router.get('/search/similar/:sha256', async (req, res, next) => {
  try {
    const { sha256 } = req.params;
    const { top_k = 100 } = req.query;
    const response = await imagemgrClient.get(`/api/search/similar/${sha256}`, {
      params: { top_k }
    });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 批量处理 ====================

router.post('/batch/import', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/import', req.body, {
      timeout: 600000  // 10分钟超时
    });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 流式批量导入
router.post('/batch/import/stream', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/import/stream', req.body, {
      responseType: 'stream',
      timeout: 0  // 无超时
    });
    
    res.set({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    });
    
    response.data.pipe(res);
  } catch (err) {
    next(err);
  }
});

router.post('/batch/generate-captions', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/generate-captions', null, {
      params: req.query,
      timeout: 600000
    });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 流式批量生成描述
router.post('/batch/generate-captions/stream', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/generate-captions/stream', null, {
      params: req.query,
      responseType: 'stream',
      timeout: 0
    });
    
    res.set({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    });
    
    response.data.pipe(res);
  } catch (err) {
    next(err);
  }
});

router.get('/batch/pending', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/batch/pending', {
      params: req.query
    });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

router.post('/batch/recompute-embeddings', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/recompute-embeddings', null, {
      params: req.query,
      timeout: 600000
    });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 流式批量更新嵌入
router.post('/batch/recompute-embeddings/stream', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/recompute-embeddings/stream', null, {
      params: req.query,
      responseType: 'stream',
      timeout: 0
    });
    
    res.set({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    });
    
    response.data.pipe(res);
  } catch (err) {
    next(err);
  }
});

// ==================== 索引重建 ====================

// 获取索引重建状态
router.get('/batch/rebuild-index/status', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/batch/rebuild-index/status');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 批量重建索引
router.post('/batch/rebuild-index', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/rebuild-index', req.body, {
      timeout: 600000
    });
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// 流式批量重建索引
router.post('/batch/rebuild-index/stream', async (req, res, next) => {
  try {
    const response = await imagemgrClient.post('/api/batch/rebuild-index/stream', req.body, {
      responseType: 'stream',
      timeout: 0
    });
    
    res.set({
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no'
    });
    
    response.data.pipe(res);
  } catch (err) {
    next(err);
  }
});

// ==================== VLM 配置 ====================

router.get('/vlm/config', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/vlm/config');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

router.get('/vlm/services', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/vlm/services');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

router.get('/vlm/prompts', async (req, res, next) => {
  try {
    const response = await imagemgrClient.get('/api/vlm/prompts');
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

// ==================== 以图搜图 ====================

router.post('/search/image', upload.single('file'), async (req, res, next) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }

    const form = new FormData();
    form.append('file', req.file.buffer, {
      filename: req.file.originalname,
      contentType: req.file.mimetype
    });
    
    if (req.body.top_k) {
      form.append('top_k', req.body.top_k);
    }

    const response = await imagemgrClient.post('/api/search/image', form, {
      headers: form.getHeaders()
    });
    
    res.json(response.data);
  } catch (err) {
    next(err);
  }
});

module.exports = router;

