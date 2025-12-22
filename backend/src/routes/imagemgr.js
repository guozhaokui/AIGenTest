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

