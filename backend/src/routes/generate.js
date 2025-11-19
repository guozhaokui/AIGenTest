'use strict';

const path = require('path');
const fs = require('fs/promises');
const crypto = require('crypto');
const express = require('express');

const router = express.Router();

const UPLOAD_DIR = path.resolve(__dirname, '../../uploads/eval-images');
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || process.env.GENAI_API_KEY || process.env.GEMINI_API_KEY || process.env.API_KEY;

router.post('/', async (req, res, next) => {
  try {
    const { prompt, modelName, count, numberOfImages } = req.body || {};
    if (!prompt) return res.status(400).json({ error: 'missing_prompt' });
    if (!GOOGLE_API_KEY) return res.status(500).json({ error: 'missing_api_key', message: 'Set GOOGLE_API_KEY in environment' });

    // 仅使用 GoogleGenAI SDK：统一使用 generateContent
    const imagesModel = modelName || 'gemini-2.5-flash-image';

    // 调试信息：代理、模型、数量、掩码后的 key
    const httpsProxy = process.env.HTTPS_PROXY || '';
    const httpProxy = process.env.HTTP_PROXY || '';
    // eslint-disable-next-line no-console
    console.log('[generate] proxy:', { HTTPS_PROXY: httpsProxy || null, HTTP_PROXY: httpProxy || null });
    // eslint-disable-next-line no-console
    console.log('[generate] request:', {
      model: imagesModel,
      prompt,
      apiKey: maskKey(GOOGLE_API_KEY)
    });

    try {
      const { dataBase64, mimeType } = await callGoogleGenerateContentSDK({
        apiKey: GOOGLE_API_KEY,
        model: imagesModel,
        prompt
      });
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
      const rel = path.relative(process.cwd(), abs).replace(/\\/g, '/');
      // eslint-disable-next-line no-console
      console.log('[generate] success: saved 1 image (generateContent)');
      return res.json({ imagePath: rel, imagePaths: [rel] });
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
    next(err);
  }
});

async function callGoogleGenerateContentSDK({ apiKey, model, prompt }) {
  // 动态引入，避免未安装时报错
  let GoogleGenAI;
  try {
    // eslint-disable-next-line global-require
    ({ GoogleGenAI } = require('@google/genai'));
  } catch (e) {
    throw new Error('sdk_not_available');
  }
  const ai = new GoogleGenAI({ apiKey });
  const response = await ai.models.generateContent({
    model,
    contents: [
      {
        role: 'user',
        parts: [{ text: prompt }]
      }
    ]
  });
  // 提取 inlineData
  try {
    const candidates = response?.candidates || [];
    for (const c of candidates) {
      const parts = c?.content?.parts || [];
      for (const p of parts) {
        if (p?.inlineData?.data) {
          return { dataBase64: p.inlineData.data, mimeType: p.inlineData.mimeType || 'image/png' };
        }
        if (p?.inline_data?.data) {
          return { dataBase64: p.inline_data.data, mimeType: p.inline_data.mime_type || 'image/png' };
        }
      }
    }
  } catch {}
  return { dataBase64: null, mimeType: null };
}

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

module.exports = router;


