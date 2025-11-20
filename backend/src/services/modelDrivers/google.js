'use strict';

let GoogleGenAIClass = null;
try {
  // eslint-disable-next-line global-require
  const mod = require('@google/genai');
  // 该 SDK 按官方示例导出名为 GoogleGenAI 的构造函数
  GoogleGenAIClass = mod.GoogleGenAI || mod.GoogleGenerativeAI || null;
} catch (e) {
  GoogleGenAIClass = null;
}

function ensureSdk() {
  if (!GoogleGenAIClass) {
    const err = new Error('sdk_not_available');
    err.code = 'SDK_NOT_AVAILABLE';
    throw err;
  }
}

async function generate({ apiKey, model, prompt, images }) {
  ensureSdk();
  const ai = new GoogleGenAIClass({ apiKey });
  const parts = [];
  const imgs = Array.isArray(images) ? images : [];
  for (const img of imgs) {
    if (!img?.dataBase64) continue;
    parts.push({
      inlineData: {
        data: img.dataBase64,
        mimeType: img.mimeType || 'image/png'
      }
    });
  }
  parts.push({ text: prompt });
  const response = await ai.models.generateContent({ model, contents: [{ role: 'user', parts }] });
  // 提取图片
  const candidates = response?.candidates || [];
  for (const c of candidates) {
    const pts = c?.content?.parts || [];
    for (const p of pts) {
      if (p?.inlineData?.data) {
        return { dataBase64: p.inlineData.data, mimeType: p.inlineData.mimeType || 'image/png' };
      }
      if (p?.inline_data?.data) {
        return { dataBase64: p.inline_data.data, mimeType: p.inline_data.mime_type || 'image/png' };
      }
    }
  }
  return { dataBase64: null, mimeType: null };
}

module.exports = { generate };


