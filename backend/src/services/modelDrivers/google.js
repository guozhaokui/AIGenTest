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

async function generate({ apiKey, model, prompt, images, config = {} }) {
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

  // 构建可选配置 (参考: https://ai.google.dev/gemini-api/docs/image-generation?hl=zh-cn#optional_configurations)
  const generationConfig = {
    responseModalities: ['image', 'text'],
    imageConfig:{}
  };

  // 宽高比
  if (config.aspectRatio) {
    generationConfig.imageConfig.aspectRatio = config.aspectRatio;
  }

  // 生成图片数量
  if (config.numberOfImages) {
    const num = parseInt(config.numberOfImages, 10);
    if (num >= 1 && num <= 4) {
      generationConfig.imageConfig.numberOfImages = num;
    }
  }

  // 人物生成控制
  if (config.personGeneration) {
    generationConfig.imageConfig.personGeneration = config.personGeneration;
  }

  // 输出格式
  if (config.outputMimeType) {
    generationConfig.imageConfig.outputMimeType = config.outputMimeType;
  }

  // 输出分辨率 (仅 Gemini 3 Pro 支持)
  if (config.outputResolution) {
    generationConfig.imageConfig.outputResolution = config.outputResolution;
  }

  // console.log('[google] generateContent config:', generationConfig);

  const response = await ai.models.generateContent({
    model,
    contents: [{ role: 'user', parts }],
    config: generationConfig
  });

  // 提取图片 - 可能返回多张
  const candidates = response?.candidates || [];
  const results = [];
  
  for (const c of candidates) {
    const pts = c?.content?.parts || [];
    for (const p of pts) {
      if (p?.inlineData?.data) {
        results.push({ dataBase64: p.inlineData.data, mimeType: p.inlineData.mimeType || 'image/png' });
      } else if (p?.inline_data?.data) {
        results.push({ dataBase64: p.inline_data.data, mimeType: p.inline_data.mime_type || 'image/png' });
      }
    }
  }

  // 返回第一张图片 (后续可扩展为返回多张)
  if (results.length > 0) {
    // 记录 usage 信息
    const usage = response?.usageMetadata || null;
    return { ...results[0], usage, allImages: results };
  }
  
  return { dataBase64: null, mimeType: null };
}

module.exports = { generate };


