'use strict';

/**
 * LTX-2 视频生成驱动
 * 支持文生视频 (Text-to-Video) 和图生视频 (Image-to-Video)
 * 
 * API 端点:
 * - POST /generate/text2video - 文生视频
 * - POST /generate/image2video/upload - 图生视频（上传图片）
 * - GET /health - 健康检查
 */

const FormData = require('form-data');
const axios = require('axios');
const http = require('http');
const https = require('https');

// 默认配置
const DEFAULT_URL = 'http://localhost:6070';
const DEFAULT_HEIGHT = 512;
const DEFAULT_WIDTH = 768;
const DEFAULT_NUM_FRAMES = 25;
const DEFAULT_FRAME_RATE = 25;
const DEFAULT_SEED = 42;
const DEFAULT_GPU = 0;

/**
 * 获取本地时间字符串
 */
function getLocalTimeString() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  const hours = String(now.getHours()).padStart(2, '0');
  const minutes = String(now.getMinutes()).padStart(2, '0');
  const seconds = String(now.getSeconds()).padStart(2, '0');
  
  const tzOffset = -now.getTimezoneOffset();
  const tzSign = tzOffset >= 0 ? '+' : '-';
  const tzHours = String(Math.floor(Math.abs(tzOffset) / 60)).padStart(2, '0');
  const tzMinutes = String(Math.abs(tzOffset) % 60).padStart(2, '0');
  
  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${tzSign}${tzHours}:${tzMinutes}`;
}

/**
 * 主生成函数
 */
async function generate({ apiKey, model, prompt, images, config }) {
  console.log('[ltx2] ===== 开始视频生成 =====');
  console.log('[ltx2] prompt:', prompt?.slice(0, 100) || '(empty)');
  console.log('[ltx2] images count:', images?.length || 0);
  
  // 判断是文生视频还是图生视频
  const hasImages = images && images.length > 0;
  
  if (hasImages) {
    return generateImage2Video({ prompt, images, config });
  } else {
    return generateText2Video({ prompt, config });
  }
}

/**
 * 文生视频
 */
async function generateText2Video({ prompt, config }) {
  const baseUrl = config.url || DEFAULT_URL;
  const apiUrl = `${baseUrl}/generate/text2video`;
  
  const payload = {
    prompt: prompt || '',
    height: parseInt(config.height) || DEFAULT_HEIGHT,
    width: parseInt(config.width) || DEFAULT_WIDTH,
    num_frames: parseInt(config.numFrames) || parseInt(config.num_frames) || DEFAULT_NUM_FRAMES,
    frame_rate: parseFloat(config.frameRate) || parseFloat(config.frame_rate) || DEFAULT_FRAME_RATE,
    seed: parseInt(config.seed) ?? DEFAULT_SEED,
    gpu_id: parseInt(config.gpuId) || parseInt(config.gpu_id) || DEFAULT_GPU
  };
  
  // 如果 seed 为 -1，表示随机
  if (payload.seed === -1) {
    payload.seed = Math.floor(Math.random() * 2147483647);
  }
  
  console.log('[ltx2] Text2Video 请求:', apiUrl);
  console.log('[ltx2] 参数:', payload);
  
  const startTime = Date.now();
  
  try {
    const response = await axios.post(apiUrl, payload, {
      headers: { 'Content-Type': 'application/json' },
      timeout: 600000, // 10分钟超时
      proxy: false,
      httpAgent: new http.Agent({ keepAlive: true }),
      httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false })
    });
    
    const duration = Date.now() - startTime;
    const result = response.data;
    
    console.log('[ltx2] Text2Video 响应:', result);
    
    if (!result.success) {
      throw new Error(result.message || '视频生成失败');
    }
    
    // 下载生成的视频
    const videoUrl = `${baseUrl}${result.video_url}`;
    console.log('[ltx2] 下载视频:', videoUrl);
    
    const videoResponse = await axios.get(videoUrl, {
      responseType: 'arraybuffer',
      timeout: 60000,
      proxy: false,
      httpAgent: new http.Agent({ keepAlive: true }),
      httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false })
    });
    
    const videoBuffer = Buffer.from(videoResponse.data);
    console.log('[ltx2] 视频大小:', videoBuffer.length, '字节');
    
    return {
      dataBase64: videoBuffer.toString('base64'),
      mimeType: 'video/mp4',
      usage: null,
      meta: {
        createdAt: getLocalTimeString(),
        service: 'LTX-2',
        serviceUrl: baseUrl,
        taskId: result.task_id,
        taskType: 'text_to_video',
        prompt: prompt,
        parameters: {
          height: payload.height,
          width: payload.width,
          numFrames: payload.num_frames,
          frameRate: payload.frame_rate,
          seed: payload.seed,
          gpuId: payload.gpu_id
        },
        generationTime: result.duration || (duration / 1000),
        videoPath: result.video_path
      },
      videoPath: `${result.task_id}.mp4`
    };
    
  } catch (error) {
    if (error.response) {
      let errorMessage = `HTTP ${error.response.status}`;
      try {
        if (error.response.data) {
          const errorData = typeof error.response.data === 'string' 
            ? JSON.parse(error.response.data) 
            : error.response.data;
          errorMessage = errorData.detail || errorData.message || errorMessage;
        }
      } catch {
        // 忽略解析错误
      }
      throw new Error(`LTX-2 文生视频失败: ${errorMessage}`);
    }
    throw new Error(`LTX-2 驱动错误: ${error.message}`);
  }
}

/**
 * 图生视频
 */
async function generateImage2Video({ prompt, images, config }) {
  const baseUrl = config.url || DEFAULT_URL;
  const apiUrl = `${baseUrl}/generate/image2video/upload`;
  
  // 获取第一张图片
  const img = images[0];
  const imageBuffer = Buffer.from(img.dataBase64, 'base64');
  
  // 根据 MIME 类型确定文件扩展名
  const extMap = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp'
  };
  const ext = extMap[img.mimeType] || 'jpg';
  const filename = `image.${ext}`;
  
  // 构建 FormData
  const formData = new FormData();
  formData.append('prompt', prompt || '');
  formData.append('image', imageBuffer, {
    filename: filename,
    contentType: img.mimeType
  });
  formData.append('height', String(parseInt(config.height) || DEFAULT_HEIGHT));
  formData.append('width', String(parseInt(config.width) || DEFAULT_WIDTH));
  formData.append('num_frames', String(parseInt(config.numFrames) || parseInt(config.num_frames) || DEFAULT_NUM_FRAMES));
  formData.append('frame_rate', String(parseFloat(config.frameRate) || parseFloat(config.frame_rate) || DEFAULT_FRAME_RATE));
  
  let seed = parseInt(config.seed) ?? DEFAULT_SEED;
  if (seed === -1) {
    seed = Math.floor(Math.random() * 2147483647);
  }
  formData.append('seed', String(seed));
  formData.append('gpu_id', String(parseInt(config.gpuId) || parseInt(config.gpu_id) || DEFAULT_GPU));
  
  console.log('[ltx2] Image2Video 请求:', apiUrl);
  console.log('[ltx2] 图片大小:', imageBuffer.length, '字节, 类型:', img.mimeType);
  console.log('[ltx2] 参数:', {
    prompt: prompt?.slice(0, 50),
    height: config.height,
    width: config.width,
    numFrames: config.numFrames || config.num_frames,
    frameRate: config.frameRate || config.frame_rate,
    seed: seed
  });
  
  const startTime = Date.now();
  
  try {
    const response = await axios.post(apiUrl, formData, {
      headers: {
        ...formData.getHeaders()
      },
      timeout: 600000, // 10分钟超时
      proxy: false,
      httpAgent: new http.Agent({ keepAlive: true }),
      httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false })
    });
    
    const duration = Date.now() - startTime;
    const result = response.data;
    
    console.log('[ltx2] Image2Video 响应:', result);
    
    if (!result.success) {
      throw new Error(result.message || '视频生成失败');
    }
    
    // 下载生成的视频
    const videoUrl = `${baseUrl}${result.video_url}`;
    console.log('[ltx2] 下载视频:', videoUrl);
    
    const videoResponse = await axios.get(videoUrl, {
      responseType: 'arraybuffer',
      timeout: 60000,
      proxy: false,
      httpAgent: new http.Agent({ keepAlive: true }),
      httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false })
    });
    
    const videoBuffer = Buffer.from(videoResponse.data);
    console.log('[ltx2] 视频大小:', videoBuffer.length, '字节');
    
    return {
      dataBase64: videoBuffer.toString('base64'),
      mimeType: 'video/mp4',
      usage: null,
      meta: {
        createdAt: getLocalTimeString(),
        service: 'LTX-2',
        serviceUrl: baseUrl,
        taskId: result.task_id,
        taskType: 'image_to_video',
        prompt: prompt,
        inputImages: [{
          index: 0,
          originalPath: img.originalPath || null,
          mimeType: img.mimeType,
          size: imageBuffer.length
        }],
        parameters: {
          height: parseInt(config.height) || DEFAULT_HEIGHT,
          width: parseInt(config.width) || DEFAULT_WIDTH,
          numFrames: parseInt(config.numFrames) || parseInt(config.num_frames) || DEFAULT_NUM_FRAMES,
          frameRate: parseFloat(config.frameRate) || parseFloat(config.frame_rate) || DEFAULT_FRAME_RATE,
          seed: seed,
          gpuId: parseInt(config.gpuId) || parseInt(config.gpu_id) || DEFAULT_GPU
        },
        generationTime: result.duration || (duration / 1000),
        videoPath: result.video_path
      },
      videoPath: `${result.task_id}.mp4`
    };
    
  } catch (error) {
    if (error.response) {
      let errorMessage = `HTTP ${error.response.status}`;
      try {
        if (error.response.data) {
          const errorData = typeof error.response.data === 'string' 
            ? JSON.parse(error.response.data) 
            : error.response.data;
          errorMessage = errorData.detail || errorData.message || errorMessage;
        }
      } catch {
        // 忽略解析错误
      }
      throw new Error(`LTX-2 图生视频失败: ${errorMessage}`);
    }
    throw new Error(`LTX-2 驱动错误: ${error.message}`);
  }
}

/**
 * 健康检查
 */
async function healthCheck(baseUrl = DEFAULT_URL) {
  try {
    const response = await axios.get(`${baseUrl}/health`, { 
      timeout: 5000,
      proxy: false
    });
    return response.data;
  } catch (error) {
    return { status: 'error', message: error.message };
  }
}

module.exports = { generate, healthCheck };

