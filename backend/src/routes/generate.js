'use strict';

const path = require('path');
const fs = require('fs/promises');
const crypto = require('crypto');
const express = require('express');
const multer = require('multer');

const router = express.Router();

const UPLOAD_DIR = path.resolve(__dirname, '../../uploads/eval-images');
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || process.env.GENAI_API_KEY || process.env.GEMINI_API_KEY || process.env.API_KEY;
const MODELS_FILE = path.resolve(__dirname, '../../data/models.json');
const { readJson } = require('../utils/jsonStore');
const googleDriver = require('../services/modelDrivers/google');

const upload = multer({ storage: multer.memoryStorage() });

router.post('/', upload.any(), async (req, res, next) => {
  try {
    const { prompt, modelName, count, numberOfImages, imagePath, imagePaths } = req.body || {};
    if (!prompt) return res.status(400).json({ error: 'missing_prompt' });
    if (!GOOGLE_API_KEY) return res.status(500).json({ error: 'missing_api_key', message: 'Set GOOGLE_API_KEY in environment' });

    // 仅使用 GoogleGenAI SDK：统一使用 generateContent
    // 解析模型：支持传 modelId（优先），兼容 modelName（后备）
    const models = await readJson(MODELS_FILE).catch(() => []);
    let selected = null;
    if (req.body && req.body.modelId) {
      selected = models.find(m => m.id === req.body.modelId);
    }
    if (!selected && modelName) {
      selected = models.find(m => (m.options && m.options.model) === modelName);
    }
    if (!selected) {
      selected = models[0] || { id: 'google_gemini_image', driver: 'google', options: { model: 'gemini-2.5-flash-image' } };
    }

    // 调试信息：代理、模型、数量、掩码后的 key
    const httpsProxy = process.env.HTTPS_PROXY || '';
    const httpProxy = process.env.HTTP_PROXY || '';
    // eslint-disable-next-line no-console
    console.log('[generate] proxy:', { HTTPS_PROXY: httpsProxy || null, HTTP_PROXY: httpProxy || null });
    // eslint-disable-next-line no-console
    console.log('[generate] request:', {
      modelId: selected.id,
      driver: selected.driver,
      model: selected.options?.model,
      prompt,
      apiKey: maskKey(GOOGLE_API_KEY)
    });

    // 可选：编辑模式输入图片（多张）
    const inputImages = [];
    const files = Array.isArray(req.files) ? req.files : [];
    for (const f of files) {
      if (!f || !f.buffer || !(f.mimetype || '').startsWith('image/')) continue;
      inputImages.push({
        dataBase64: f.buffer.toString('base64'),
        mimeType: f.mimetype || 'image/png'
      });
    }
    // 支持 imagePath（单个）与 imagePaths（数组或逗号分隔字符串）
    const pathCandidates = [];
    if (typeof imagePath === 'string' && imagePath) pathCandidates.push(imagePath);
    if (Array.isArray(imagePaths)) pathCandidates.push(...imagePaths);
    else if (typeof imagePaths === 'string' && imagePaths.trim()) {
      try {
        const parsed = JSON.parse(imagePaths);
        if (Array.isArray(parsed)) pathCandidates.push(...parsed);
      } catch {
        pathCandidates.push(...imagePaths.split(','));
      }
    }
    for (let p of pathCandidates) {
      try {
        if (!p) continue;
        const raw = String(p).trim();
        // 远程 URL
        if (/^https?:\/\//i.test(raw)) {
          const resp = await fetch(raw);
          if (!resp.ok) throw new Error(`fetch_failed: ${resp.status}`);
          const ab = await resp.arrayBuffer();
          const buf = Buffer.from(ab);
          const ct = resp.headers.get('content-type') || 'image/png';
          inputImages.push({
            dataBase64: buf.toString('base64'),
            mimeType: ct
          });
          continue;
        }
        // 本地 uploads 路径
        let rel = raw.replace(/\\/g, '/');
        if (rel.startsWith('/')) rel = rel.slice(1);
        if (!rel.startsWith('uploads/')) rel = `uploads/${rel}`;
        const abs = path.resolve(path.join(__dirname, '../..', rel));
        const buf = await fs.readFile(abs);
        const ext = (abs.split('.').pop() || 'png').toLowerCase();
        inputImages.push({
          dataBase64: buf.toString('base64'),
          mimeType: extToMime(ext)
        });
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[generate] read imagePaths item failed:', e?.message || e);
      }
    }
    // eslint-disable-next-line no-console
    console.log('[generate] input images:', inputImages.length);

    try {
      let dataBase64 = null;
      let mimeType = null;
      if (selected.driver === 'google') {
        const out = await googleDriver.generate({
          apiKey: GOOGLE_API_KEY,
          model: selected.options?.model || 'gemini-2.5-flash-image',
          prompt,
          images: inputImages
        });
        dataBase64 = out?.dataBase64;
        mimeType = out?.mimeType;
      } else {
        const err = new Error(`unsupported_driver: ${selected.driver}`);
        err.code = 'UNSUPPORTED_DRIVER';
        throw err;
      }
      if (!dataBase64) {
        return res.status(500).json({ error: 'no_image_returned' });
      }
      const buf = Buffer.from(dataBase64, 'base64');
      const hash = crypto.createHash('md5').update(buf).digest('hex');
      const sub1 = hash.slice(0, 2);
      const sub2 = hash.slice(2, 4);
      const ext = mimeToExt(mimeType);
      const dir = path.join(UPLOAD_DIR, sub1, sub2);
      await fs.mkdir(dir, { recursive: true });
      const filename = `${hash}${ext}`;
      const abs = path.join(dir, filename);
      await fs.writeFile(abs, buf);
      // 统一返回以 /uploads 开头的可访问路径
      const relFromProject = path.relative(path.resolve(__dirname, '../..'), abs).replace(/\\/g, '/'); // e.g. 'uploads/eval-images/...'
      const publicPath = relFromProject.startsWith('uploads/') ? `/${relFromProject}` : `/uploads/${relFromProject}`;
      // eslint-disable-next-line no-console
      console.log('[generate] success: saved 1 image (generateContent)');
      return res.json({ imagePath: publicPath, imagePaths: [publicPath] });
    } catch (sdkErr) {
      // eslint-disable-next-line no-console
      console.error('[generate] generateContent error:', serializeError(sdkErr));
      return res.status(500).json({
        error: 'sdk_generate_failed',
        name: sdkErr?.name,
        code: sdkErr?.code,
        status: sdkErr?.status,
        message: sdkErr?.message || String(sdkErr)
      });
    }
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error('[generate] unhandled error:', serializeError(err));
    // 返回可读的详细错误，便于前端弹窗与排查
    return res.status(500).json({
      error: 'unhandled_error',
      ...serializeError(err)
    });
  }
});

// 移除内联 Google 生成函数，改由驱动实现

function maskKey(key) {
  if (!key || typeof key !== 'string') return null;
  if (key.length <= 8) return `${'*'.repeat(Math.max(0, key.length - 2))}${key.slice(-2)}`;
  return `${key.slice(0, 2)}${'*'.repeat(key.length - 6)}${key.slice(-4)}`;
}

function serializeError(err) {
  try {
    return {
      name: err?.name,
      message: err?.message || String(err),
      code: err?.code,
      status: err?.status,
      cause: err?.cause ? (err.cause.message || String(err.cause)) : undefined,
      stack: err?.stack
    };
  } catch {
    return { message: String(err) };
  }
}

function mimeToExt(mime) {
  if (mime === 'image/png') return '.png';
  if (mime === 'image/jpeg') return '.jpg';
  if (mime === 'image/webp') return '.webp';
  return '.png';
}

function extToMime(ext) {
  const e = ext.startsWith('.') ? ext.slice(1).toLowerCase() : ext.toLowerCase();
  if (e === 'png') return 'image/png';
  if (e === 'jpg' || e === 'jpeg') return 'image/jpeg';
  if (e === 'webp') return 'image/webp';
  return 'image/png';
}

module.exports = router;


