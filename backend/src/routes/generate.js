'use strict';

const path = require('path');
const fs = require('fs/promises');
const crypto = require('crypto');
const express = require('express');
const multer = require('multer');

const router = express.Router();

const UPLOAD_DIR = path.resolve(__dirname, '../../imagedb');
// 新增：模型存储目录
const MODEL_DIR = path.resolve(__dirname, '../../modeldb');
// 新增：音频存储目录
const SOUND_DIR = path.resolve(__dirname, '../../sounddb');
// 新增：视频存储目录
const VIDEO_DIR = path.resolve(__dirname, '../../videodb');
const GOOGLE_API_KEY = process.env.GOOGLE_API_KEY || process.env.GENAI_API_KEY || process.env.GEMINI_API_KEY || process.env.API_KEY;
const MODELS_FILE = path.resolve(__dirname, '../../data/models.json');
const { readJson } = require('../utils/jsonStore');

function getDriver(driverName) {
  try {
    const safeName = String(driverName).replace(/[^a-z0-9_-]/gi, '');
    return require(`../services/modelDrivers/${safeName}`);
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn(`[generate] driver load failed for "${driverName}":`, e.message);
    return null;
  }
}

const upload = multer({ storage: multer.memoryStorage() });

router.post('/', upload.any(), async (req, res, next) => {
  try {
    console.log('[generate] ==== INCOMING REQUEST ====');
    // 只打印关键字段，避免打印 base64 等大数据
    const { prompt, modelId, modelName, imagePath, imagePaths, ...otherParams } = req.body || {};
    console.log('[generate] modelId:', modelId, '| prompt:', prompt?.slice(0, 100) || '(empty)');
    console.log('[generate] imagePath:', imagePath, '| imagePaths:', imagePaths);
    console.log('[generate] Request files:', req.files ? req.files.length : 0);
    // 打印其他参数（排除可能的大数据字段）
    const safeParams = Object.keys(otherParams).filter(k => !['imageSlots'].includes(k));
    if (safeParams.length > 0) {
      console.log('[generate] Other params:', safeParams.join(', '));
    }
    
    const { count, numberOfImages } = req.body || {};
    console.log('[generate] Extracted prompt:', prompt?.slice(0, 100) || '(empty)');
    
    // 读取模型配置，根据 inputMode 判断是否需要 prompt
    const models = await readJson(MODELS_FILE).catch(() => []);
    let selectedModel = null;
    if (req.body && req.body.modelId) {
      selectedModel = models.find(m => m.id === req.body.modelId);
    }
    
    // 根据新的 input 配置判断是否需要 prompt/image：
    // input.types: ["text"] / ["image"] / ["text", "image"] / []
    // input.mode: "single" | "combined" | "exclusive" | "multiple" | "multiview" | "params_only"
    const inputConfig = selectedModel?.input || { types: ['text', 'image'], mode: 'combined' };
    const inputTypes = inputConfig.types || ['text', 'image'];
    const inputMode = inputConfig.mode || 'combined';
    const hasImages = (req.files && req.files.length > 0) || imagePath || imagePaths;
    
    const supportsText = inputTypes.includes('text');
    const supportsImage = inputTypes.includes('image');
    
    // params_only 模式：不需要图片或文本，只需要参数（如 Tripo Refine）
    if (inputMode === 'params_only') {
      console.log('[generate] params_only mode, skipping input validation');
    }
    // 仅支持文本输入时，必须有 prompt
    else if (supportsText && !supportsImage && !prompt) {
      console.log('[generate] ERROR: Missing prompt for text-only model');
      return res.status(400).json({ error: 'missing_prompt', message: '该模型需要提示词' });
    }
    // 仅支持图片输入时，必须有图片
    else if (supportsImage && !supportsText && !hasImages) {
      console.log('[generate] ERROR: Missing image for image-only model');
      return res.status(400).json({ error: 'missing_image', message: '该模型需要参考图' });
    }
    // exclusive 模式，需要至少有 prompt 或 image
    else if (inputMode === 'exclusive' && !prompt && !hasImages) {
      console.log('[generate] ERROR: Missing prompt or image for exclusive mode');
      return res.status(400).json({ error: 'missing_prompt_or_image', message: '请输入提示词或上传参考图' });
    }
    // combined 模式，同时支持 text 和 image 时，至少需要一个
    else if (inputMode === 'combined' && supportsText && supportsImage && !prompt && !hasImages) {
      console.log('[generate] ERROR: Missing prompt or image for combined mode');
      return res.status(400).json({ error: 'missing_input', message: '请输入提示词或上传参考图' });
    }
    
    console.log('[generate] Input config:', inputConfig, 'hasPrompt:', !!prompt, 'hasImages:', !!hasImages);
    
    if (!GOOGLE_API_KEY) {
      console.log('[generate] ERROR: Missing API key, returning 500');
      return res.status(500).json({ error: 'missing_api_key', message: 'Set GOOGLE_API_KEY in environment' });
    }

    // 仅使用 GoogleGenAI SDK：统一使用 generateContent
    // 解析模型：支持传 modelId（优先），兼容 modelName（后备）
    //const models = await readJson(MODELS_FILE).catch(() => []);
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
    
    // eslint-disable-next-line no-console
    if (pathCandidates.length > 0) console.log('[generate] pathCandidates:', pathCandidates);

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
            mimeType: ct,
            originalPath: raw  // 保存原始 URL
          });
          continue;
        }
        // 本地图片路径（支持 imagedb/ ）
        let rel = raw.replace(/\\/g, '/');
        if (rel.startsWith('/')) rel = rel.slice(1);
        
        // 智能提取 imagedb/ 部分，兼容新旧路径
        const imgDbIdx = rel.indexOf('imagedb/');
        if (imgDbIdx >= 0) {
          rel = rel.slice(imgDbIdx);
        } else {
          // 默认尝试 imagedb 目录
          rel = `imagedb/${rel}`;
        }

        const abs = path.resolve(path.join(__dirname, '../..', rel));
        // eslint-disable-next-line no-console
        console.log(`[generate] reading local image: raw="${raw}" rel="${rel}" abs="${abs}"`);

        const buf = await fs.readFile(abs);
        const ext = (abs.split('.').pop() || 'png').toLowerCase();
        inputImages.push({
          dataBase64: buf.toString('base64'),
          mimeType: extToMime(ext),
          originalPath: `/${rel}`  // 保存相对路径（以 / 开头）
        });
      } catch (e) {
        // eslint-disable-next-line no-console
        console.warn('[generate] read imagePaths item failed:', p, e?.message || e);
      }
    }
    // eslint-disable-next-line no-console
    console.log('[generate] input images:', inputImages.length);

    try {
      let dataBase64 = null;
      let mimeType = null;

      const driver = getDriver(selected.driver);
      if (!driver) {
        const err = new Error(`unsupported_driver: ${selected.driver}`);
        err.code = 'UNSUPPORTED_DRIVER';
        throw err;
      }

      // 简单的 API Key 映射策略，也可放到 driver 内部处理
      let apiKey = process.env.API_KEY;
      if (selected.driver === 'google') {
        apiKey = process.env.GOOGLE_API_KEY || process.env.GENAI_API_KEY || process.env.GEMINI_API_KEY;
      } else if (selected.driver === 'dashscope' || selected.driver === 'qwen') {
        apiKey = process.env.DASHSCOPE_API_KEY || process.env.QWEN_API_KEY;
      } else if (selected.driver === 'doubao') {
        apiKey = process.env.ARK_API_KEY;
      } else if (selected.driver === 'tripo') {
        apiKey = process.env.TRIPO_API_KEY;
      } else if (selected.driver === 'meshy') {
        apiKey = process.env.MESHY_API_KEY;
      } else if (selected.driver === 'hyper3d') {
        apiKey = process.env.HYPER3D_API_KEY;
      } else if (selected.driver === 'ltx2') {
        apiKey = null; // LTX2 是本地服务，不需要 API Key
      }

      const startT = Date.now();
      // 合并 imageSlots：优先使用前端传递的（带有实际 path），否则使用配置中的定义
      let frontendSlots = req.body?.imageSlots;
      // 如果是 JSON 字符串（来自 FormData），需要解析
      if (typeof frontendSlots === 'string') {
        try { frontendSlots = JSON.parse(frontendSlots); } catch { frontendSlots = null; }
      }
      const configSlots = selected.input?.imageSlots || [];
      // 如果前端传递了 imageSlots（带有 path），直接使用；否则使用配置定义
      const mergedImageSlots = (frontendSlots && frontendSlots.length > 0) ? frontendSlots : configSlots;
      
      const out = await driver.generate({
        apiKey,
        model: selected.options?.model,
        prompt,
        images: inputImages,
        config: { 
          ...(selected.options || {}), 
          ...(req.body || {}),
          imageSlots: mergedImageSlots
        }
      });
      const duration = Date.now() - startT;

      dataBase64 = out?.dataBase64;
      mimeType = out?.mimeType;
      const usage = out?.usage || null; // 提取 token 使用信息
      
      if (!dataBase64) {
        return res.status(500).json({ error: 'no_image_returned' });
      }
      const buf = Buffer.from(dataBase64, 'base64');
      const hash = crypto.createHash('md5').update(buf).digest('hex');
      const sub1 = hash.slice(0, 2);
      
      // 先计算 ext，以便判断是否为 zip
      const ext = mimeToExt(mimeType);
      
      // Check if it's a zip file (3D generation result)
      const isZip = mimeType === 'application/zip' || mimeType === 'application/x-zip-compressed' || ext === '.zip';
      
      if (isZip) {
        // Handle 3D zip file
        // 使用前端传递的 questionId 作为问题目录，如果没有则创建新的
        const questionUuid = req.body.questionId || crypto.randomUUID();
        // 每次生成创建一个新的结果 uuid
        const resultUuid = crypto.randomUUID();
        
        const baseDir = path.resolve(__dirname, '../../modeldb');
        // 目录结构：modeldb/{questionUuid}/{resultUuid}/
        const outputDir = path.join(baseDir, questionUuid, resultUuid);
        
        // Install adm-zip if not available
        let admZip;
        try {
          admZip = require('adm-zip');
        } catch (e) {
          console.log('[generate] Installing adm-zip...');
          const { execSync } = require('child_process');
          execSync('npm install adm-zip', { cwd: path.resolve(__dirname, '../..') });
          admZip = require('adm-zip');
        }
        
        // Extract zip
        const zip = new admZip(buf);
        zip.extractAllTo(outputDir, true);
        console.log(`[generate] Extracted 3D zip to ${outputDir}`);
        
        // 返回目录路径，文件结构固定为 pbr/mesh_textured_pbr.glb 和 rgb/mesh_textured.glb
        const modelDir = `/modeldb/${questionUuid}/${resultUuid}`;
        console.log(`[generate] 3D model extracted to ${modelDir}`);
        
        // 保存 meta.json 元数据文件（使用本地时间）
        const metaData = {
          generatedAt: getLocalTimeString(),
          modelId: selected.id,
          driver: selected.driver,
          prompt: prompt || null,
          inputImageCount: inputImages.length,
          duration: duration,
          usage: usage,
          // 来自驱动的元数据
          ...(out.meta || {})
        };
        
        const metaPath = path.join(outputDir, 'meta.json');
        await fs.writeFile(metaPath, JSON.stringify(metaData, null, 2), 'utf-8');
        console.log(`[generate] Meta saved to ${modelDir}/meta.json`);
          
        return res.json({ 
          imagePath: modelDir,
          duration,
          info3d: { modelDir },
          usage
        });
      } else {
        // Regular file handling (images, single 3D models, sounds, videos)
        const sub2 = hash.slice(2, 4);
        // ext 已在前面定义
        
        // 判断是存入 imagedb, modeldb, sounddb 还是 videodb
        const isModel = ['.glb', '.gltf', '.fbx', '.obj'].includes(ext);
        const isSound = ['.mp3', '.wav', '.ogg', '.flac'].includes(ext);
        const isVideo = ['.mp4', '.webm', '.mov', '.avi'].includes(ext);
        
        // 对于视频，使用与 3D 模型相似的目录结构
        if (isVideo) {
          const questionUuid = req.body.questionId || crypto.randomUUID();
          const resultUuid = crypto.randomUUID();
          
          const baseDir = path.resolve(__dirname, '../../videodb');
          const outputDir = path.join(baseDir, questionUuid, resultUuid);
          
          await fs.mkdir(outputDir, { recursive: true });
          
          // 从驱动返回的 videoPath 获取视频文件名，默认为 video.mp4
          const videoFilename = out.videoPath || 'video.mp4';
          const abs = path.join(outputDir, videoFilename);
          await fs.writeFile(abs, buf);
          
          const videoDir = `/videodb/${questionUuid}/${resultUuid}`;
          console.log(`[generate] Video saved to ${videoDir}/${videoFilename}`);
          
          // 保存 meta.json 元数据文件（使用本地时间）
          const metaData = {
            generatedAt: getLocalTimeString(),
            modelId: selected.id,
            driver: selected.driver,
            prompt: prompt || null,
            inputImageCount: inputImages.length,
            duration: duration,
            usage: usage,
            // 来自驱动的元数据（如 LTX2 的 taskId 等）
            ...(out.meta || {})
          };
          
          const metaPath = path.join(outputDir, 'meta.json');
          await fs.writeFile(metaPath, JSON.stringify(metaData, null, 2), 'utf-8');
          console.log(`[generate] Meta saved to ${videoDir}/meta.json`);
          
          return res.json({ 
            imagePath: videoDir,
            duration,
            infoVideo: { 
              videoDir,
              videoPath: videoFilename  // 返回视频文件相对路径
            },
            usage
          });
        }
        
        // 对于 3D 模型，使用与 ZIP 相同的目录结构
        if (isModel) {
          const questionUuid = req.body.questionId || crypto.randomUUID();
          const resultUuid = crypto.randomUUID();
          
          const baseDir = path.resolve(__dirname, '../../modeldb');
          const outputDir = path.join(baseDir, questionUuid, resultUuid);
          
          await fs.mkdir(outputDir, { recursive: true });
          
          // 从驱动返回的 modelPath 获取模型文件名，默认为 model.glb
          const modelFilename = out.modelPath || 'model.glb';
          const abs = path.join(outputDir, modelFilename);
          await fs.writeFile(abs, buf);
          
          const modelDir = `/modeldb/${questionUuid}/${resultUuid}`;
          console.log(`[generate] 3D model saved to ${modelDir}/${modelFilename}`);
          
          // 保存 meta.json 元数据文件（使用本地时间）
          const metaData = {
            generatedAt: getLocalTimeString(),
            modelId: selected.id,
            driver: selected.driver,
            prompt: prompt || null,
            inputImageCount: inputImages.length,
            duration: duration,
            usage: usage,
            // 来自驱动的元数据（如 Tripo 的 traceId 等）
            ...(out.meta || {})
          };
          
          const metaPath = path.join(outputDir, 'meta.json');
          await fs.writeFile(metaPath, JSON.stringify(metaData, null, 2), 'utf-8');
          console.log(`[generate] Meta saved to ${modelDir}/meta.json`);
          
          return res.json({ 
            imagePath: modelDir,
            duration,
            info3d: { 
              modelDir,
              isSingleFile: true,  // 标记为单个文件，非 ZIP 解压
              modelPath: modelFilename  // 返回模型文件相对路径
            },
            usage
          });
        }
        
        let baseDir = UPLOAD_DIR;
        if (isSound) baseDir = SOUND_DIR;

        const dir = path.join(baseDir, sub1, sub2);
        
        await fs.mkdir(dir, { recursive: true });
        const filename = `${hash}${ext}`;
        const abs = path.join(dir, filename);
        await fs.writeFile(abs, buf);
        
        // 修改公共路径生成逻辑，使其通用化
        const relFromProject = path.relative(path.resolve(__dirname, '../..'), abs).replace(/\\/g, '/'); 
        // relFromProject 例如: 'imagedb/xx.png', 'modeldb/xx.glb', 'sounddb/xx.mp3'
        const publicPath = `/${relFromProject}`;
        
        return res.json({ imagePath: publicPath, duration, usage });
      }
      
      // eslint-disable-next-line no-console
      console.log(`[generate] success: saved 1 file, duration=${duration}ms, path=${publicPath}`);
      return res.json({ imagePath: publicPath, imagePaths: [publicPath], duration });
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

/**
 * 获取本地时间字符串（带时区偏移）
 */
function getLocalTimeString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  const ms = String(now.getMilliseconds()).padStart(3, '0');
  
  // 计算时区偏移
  const tzOffset = -now.getTimezoneOffset();
  const tzSign = tzOffset >= 0 ? '+' : '-';
  const tzHours = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, '0');
  const tzMinutes = String(Math.abs(tzOffset) % 60).padStart(2, '0');
  
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}.${ms}${tzSign}${tzHours}:${tzMinutes}`;
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
  // 新增：3D 模型 MIME 支持
  if (mime === 'model/gltf-binary') return '.glb';
  if (mime === 'model/gltf+json') return '.gltf';
  if (mime === 'application/octet-stream') return '.glb'; 
  // 新增：音频 MIME 支持
  if (mime === 'audio/mpeg') return '.mp3';
  if (mime === 'audio/wav' || mime === 'audio/x-wav') return '.wav';
  if (mime === 'audio/ogg') return '.ogg';
  // 新增：视频 MIME 支持
  if (mime === 'video/mp4') return '.mp4';
  if (mime === 'video/webm') return '.webm';
  if (mime === 'video/quicktime') return '.mov';
  if (mime === 'video/x-msvideo') return '.avi';
  return '.png'; // 默认回退
}

function extToMime(ext) {
  const e = ext.startsWith('.') ? ext.slice(1).toLowerCase() : ext.toLowerCase();
  if (e === 'png') return 'image/png';
  if (e === 'jpg' || e === 'jpeg') return 'image/jpeg';
  if (e === 'webp') return 'image/webp';
  return 'image/png';
}

module.exports = router;


