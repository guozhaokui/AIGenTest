'use strict';

const path = require('path');
const fs = require('fs/promises');
const crypto = require('crypto');
const express = require('express');

const router = express.Router();

const UPLOAD_DIR = path.resolve(__dirname, '../../uploads/eval-images');
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || process.env.GENAI_API_KEY || process.env.API_KEY;
const GOOGLE_API_BASE = process.env.GOOGLE_API_BASE || 'https://generativelanguage.googleapis.com';

router.post('/', async (req, res, next) => {
  try {
    const { prompt, modelName } = req.body || {};
    if (!prompt) return res.status(400).json({ error: 'missing_prompt' });
    if (!GOOGLE_API_KEY) return res.status(500).json({ error: 'missing_api_key', message: 'Set GOOGLE_API_KEY in environment' });
    const model = modelName || 'gemini-2.5-flash-image';
    const resp = await callGoogleGenerate({ apiKey: GOOGLE_API_KEY, model, prompt });
    const { dataBase64, mimeType } = extractImage(resp);
    if (!dataBase64) {
      return res.status(500).json({ error: 'no_image_returned', raw: resp });
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
    const rel = path
      .relative(process.cwd(), abs)
      .replace(/\\/g, '/');
    res.json({ imagePath: rel });
  } catch (err) {
    next(err);
  }
});

function mimeToExt(mime) {
  if (mime === 'image/png') return '.png';
  if (mime === 'image/jpeg') return '.jpg';
  if (mime === 'image/webp') return '.webp';
  return '.png';
}

async function callGoogleGenerate({ apiKey, model, prompt }) {
  // REST 调用 Google Generative Language API
  const endpoint = `${GOOGLE_API_BASE.replace(/\/$/, '')}/v1beta/models/${encodeURIComponent(model)}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const body = {
    contents: [
      {
        role: 'user',
        parts: [{ text: prompt }]
      }
    ]
  };
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Google API error: ${res.status} ${text}`);
    }
    return await res.json();
  } catch (err) {
    // 提供更可读的错误信息（常见为网络不可达或被防火墙阻断）
    const code = err?.cause?.code || err?.code;
    const msg = err?.message || String(err);
    console.error('Generate fetch failed:', code, msg);
    throw new Error(`fetch_failed${code ? ` (${code})` : ''}: ${msg}`);
  }
}

function extractImage(resp) {
  // 尝试从 candidates[].content.parts[] 提取 inlineData
  try {
    const candidates = resp.candidates || [];
    for (const c of candidates) {
      const parts = (c.content && c.content.parts) || [];
      for (const p of parts) {
        if (p.inlineData && p.inlineData.mimeType && p.inlineData.data) {
          return { dataBase64: p.inlineData.data, mimeType: p.inlineData.mimeType };
        }
        // 某些返回可能是 image 结构或 base64 字段，尽量兜底
        if (p.inline_data && p.inline_data.mime_type && p.inline_data.data) {
          return { dataBase64: p.inline_data.data, mimeType: p.inline_data.mime_type };
        }
      }
    }
  } catch {}
  return { dataBase64: null, mimeType: null };
}

module.exports = router;


