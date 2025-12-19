'use strict';

/**
 * TRELLIS.2 驱动
 * 用于访问本地 TRELLIS.2 图转 3D 模型服务
 * 
 * API 文档:
 * - POST /generate - 上传图片生成 3D 模型
 * - GET /health - 健康检查
 */

const https = require('https');
const http = require('http');

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
  // TRELLIS.2 是本地服务，不需要 API Key
  
  if (!images || images.length === 0) {
    throw new Error('TRELLIS.2 需要输入图片');
  }
  
  console.log('[trellis] ===== 开始 3D 生成 =====');
  
  return generate3D({ images, config });
}

/**
 * 3D 生成主流程
 */
async function generate3D({ images, config }) {
  // 服务地址
  const baseUrl = config.url || 'http://localhost:8000';
  const generateUrl = `${baseUrl}/generate`;
  
  // 获取第一张图片
  const img = images[0];
  const buffer = Buffer.from(img.dataBase64, 'base64');
  
  // 根据 MIME 类型确定文件扩展名
  const extMap = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp'
  };
  const ext = extMap[img.mimeType] || 'png';
  const filename = `image.${ext}`;
  
  console.log(`[trellis] 上传图片到 ${generateUrl}, 大小: ${buffer.length} 字节, 类型: ${img.mimeType}`);
  
  // 使用 form-data 包 + axios 进行上传
  const FormData = require('form-data');
  const axios = require('axios');
  
  const formData = new FormData();
  formData.append('image', buffer, {
    filename: filename,
    contentType: img.mimeType
  });
  
  // 添加可选参数
  if (config.simplifyFaces) {
    formData.append('simplify_faces', String(config.simplifyFaces));
  }
  if (config.decimationTarget) {
    formData.append('decimation_target', String(config.decimationTarget));
  }
  if (config.textureSize) {
    formData.append('texture_size', String(config.textureSize));
  }
  if (config.remesh !== undefined) {
    formData.append('remesh', config.remesh ? 'true' : 'false');
  }
  
  console.log('[trellis] 参数:', {
    simplifyFaces: config.simplifyFaces,
    decimationTarget: config.decimationTarget,
    textureSize: config.textureSize,
    remesh: config.remesh
  });
  
  try {
    const startTime = Date.now();
    
    const response = await axios.post(generateUrl, formData, {
      headers: {
        ...formData.getHeaders()
      },
      responseType: 'arraybuffer',
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      timeout: 600000, // 10 分钟超时
      // 不使用代理
      proxy: false,
      httpAgent: new http.Agent({ keepAlive: true }),
      httpsAgent: new https.Agent({ keepAlive: true, rejectUnauthorized: false })
    });
    
    const duration = Date.now() - startTime;
    console.log(`[trellis] 生成完成, 耗时 ${duration}ms, 大小 ${response.data.length} 字节`);
    
    const modelBuffer = Buffer.from(response.data);
    const contentType = response.headers['content-type'] || 'model/gltf-binary';
    
    // 构建元数据
    const meta = {
      createdAt: getLocalTimeString(),
      service: 'TRELLIS.2',
      serviceUrl: baseUrl,
      inputImages: [{
        index: 0,
        originalPath: img.originalPath || null,
        mimeType: img.mimeType,
        size: buffer.length
      }],
      parameters: {
        simplifyFaces: config.simplifyFaces,
        decimationTarget: config.decimationTarget,
        textureSize: config.textureSize,
        remesh: config.remesh
      },
      generationTime: duration
    };
    
    return {
      dataBase64: modelBuffer.toString('base64'),
      mimeType: contentType,
      usage: null,
      meta,
      modelPath: 'model.glb'
    };
    
  } catch (error) {
    if (error.response) {
      // 尝试解析错误响应
      let errorMessage = `HTTP ${error.response.status}`;
      try {
        const errorData = JSON.parse(error.response.data.toString());
        errorMessage = errorData.detail || errorMessage;
      } catch {
        // 忽略解析错误
      }
      throw new Error(`TRELLIS.2 生成失败: ${errorMessage}`);
    }
    throw new Error(`TRELLIS.2 驱动错误: ${error.message}`);
  }
}

/**
 * 健康检查
 */
async function healthCheck(baseUrl = 'http://localhost:8000') {
  const axios = require('axios');
  try {
    const response = await axios.get(`${baseUrl}/health`, { timeout: 5000 });
    return response.data;
  } catch (error) {
    return { status: 'error', message: error.message };
  }
}

module.exports = { generate, healthCheck };

