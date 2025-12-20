'use strict';

/**
 * Tripo3D 驱动
 * 用于 Tripo3D 图生 3D 模型
 * 
 * API 文档:
 * - 生成: https://platform.tripo3d.com/docs/generation
 * - 上传: https://platform.tripo3d.com/docs/upload
 * 
 * 流程:
 * 1. 上传图片 -> 获取 image_token
 * 2. 创建生成任务 -> 获取 task_id
 * 3. 轮询任务状态 -> 获取模型 URL
 * 4. 下载模型文件
 */

const API_BASE = 'https://api.tripo3d.com/v2/openapi';

/**
 * 获取网络请求分发器（用于处理代理设置）
 */
function getDispatcher(config) {
  let dispatcher = undefined;
  if (config.useProxy === false || config.useProxy === 'false') {
    try {
      const { Agent } = require('undici');
      dispatcher = new Agent();
    } catch (e) {
      // 忽略 undici 不可用的情况
    }
  }
  return dispatcher;
}

/**
 * 从 URL 下载内容
 */
async function downloadContent(url, dispatcher, apiKey) {
  const headers = {};
  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }
  
  const resp = await fetch(url, { dispatcher, headers });
  if (!resp.ok) {
    throw new Error(`下载失败: ${resp.status}`);
  }
  const arrayBuffer = await resp.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const contentType = resp.headers.get('content-type');
  return { buffer, contentType };
}

/**
 * 上传图片到 Tripo3D
 * 
 * API: POST /upload
 * 请求: multipart/form-data, file 字段
 * 响应: { code: 0, data: { image_token: "xxx" } }
 */
async function uploadImage(imageBase64, mimeType, apiKey, dispatcher) {
  const uploadUrl = `${API_BASE}/upload`;
  
  const buffer = Buffer.from(imageBase64, 'base64');
  
  // 根据 MIME 类型确定文件扩展名
  const extMap = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp'
  };
  const ext = extMap[mimeType] || 'png';
  const filename = `image.${ext}`;
  
  console.log(`[tripo] 上传图片到 ${uploadUrl}, 大小: ${buffer.length} 字节, 类型: ${mimeType}`);
  
  // 使用 form-data 包 + axios 进行上传（更稳定的 multipart 支持）
  const FormData = require('form-data');
  const axios = require('axios');
  const https = require('https');
  
  const formData = new FormData();
  formData.append('file', buffer, {
    filename: filename,
    contentType: mimeType
  });
  
  try {
    const response = await axios.post(uploadUrl, formData, {
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        ...formData.getHeaders()
      },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      // 禁用代理，直接连接
      proxy: false,
      httpsAgent: new https.Agent({ rejectUnauthorized: true })
    });
    
    const result = response.data;
    
    if (result.code !== 0) {
      throw new Error(`上传错误: ${result.message || JSON.stringify(result)}`);
    }
    
    const imageToken = result.data?.image_token;
    if (!imageToken) {
      throw new Error(`上传成功但未返回 image_token: ${JSON.stringify(result.data)}`);
    }
    
    console.log('[tripo] 图片上传成功, token:', imageToken);
    return imageToken;
  } catch (error) {
    if (error.response) {
      throw new Error(`上传失败: ${error.response.status} - ${JSON.stringify(error.response.data)}`);
    }
    throw error;
  }
}

/**
 * 创建 3D 生成任务
 * 
 * API: POST /task
 * 请求体:
 * - type: "image_to_model" | "text_to_model" | "multiview_to_model"
 * - file/files: 图片 token
 * - prompt: 文本提示词
 * - model_version: 模型版本
 * - 其他可选参数
 */
async function createTask(payload, apiKey, dispatcher) {
  const taskUrl = `${API_BASE}/task`;
  
  console.log('[tripo] 创建任务:', JSON.stringify(payload, null, 2));
  
  const response = await fetch(taskUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify(payload),
    dispatcher
  });

  // 获取 Trace ID
  const traceId = response.headers.get('X-Tripo-Trace-ID') || response.headers.get('x-tripo-trace-id');
  if (traceId) {
    console.log(`[tripo] Trace ID: ${traceId}`);
  }

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`创建任务失败: ${response.status} ${response.statusText} - ${errorText}`);
  }

  const result = await response.json();
  
  if (result.code !== 0) {
    throw new Error(`任务创建错误: ${result.message || JSON.stringify(result)}`);
  }
  
  const taskId = result.data?.task_id;
  if (!taskId) {
    throw new Error(`任务创建成功但未返回 task_id: ${JSON.stringify(result.data)}`);
  }
  
  console.log(`[tripo] 任务已创建, ID: ${taskId}`);
  return { taskId, traceId };
}

/**
 * 轮询任务状态
 * 
 * API: GET /task/{task_id}
 * 响应: { code: 0, data: { status: "success"|"running"|"failed", output: {...} } }
 */
async function pollTask(taskId, apiKey, dispatcher) {
  const pollUrl = `${API_BASE}/task/${taskId}`;
  const maxAttempts = 120; // 最多 20 分钟
  const intervalMs = 10000; // 10 秒间隔

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(pollUrl, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${apiKey}`
      },
      dispatcher
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`轮询失败: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    if (result.code !== 0) {
      throw new Error(`轮询错误: ${result.message || JSON.stringify(result)}`);
    }
    
    const data = result.data;
    const status = data?.status;
    const progress = data?.progress || 0;
    
    console.log(`[tripo] 轮询 ${attempt + 1}/${maxAttempts}, 状态: ${status}, 进度: ${progress}%`);

    if (status === 'success') {
      return data;
    } else if (status === 'failed') {
      throw new Error(`生成失败: ${data?.error || data?.message || '未知错误'}`);
    } else if (status === 'cancelled') {
      throw new Error('任务已取消');
    }

    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('生成超时');
}

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
 * 检查账户余额（调试用）
 */
async function checkBalance(apiKey, dispatcher) {
  try {
    const response = await fetch(`${API_BASE}/user/balance`, {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${apiKey}` },
      dispatcher
    });
    const data = await response.json();
    console.log('[tripo] 账户余额:', JSON.stringify(data, null, 2));
    return data;
  } catch (e) {
    console.log('[tripo] 无法获取余额:', e.message);
    return null;
  }
}

/**
 * 主生成函数
 */
async function generate({ apiKey, model, prompt, images, config }) {
  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = '请在环境变量中设置 TRIPO_API_KEY';
    throw err;
  }

  const dispatcher = getDispatcher(config);
  
  console.log('[tripo] ===== 开始 3D 生成 =====');
  console.log('[tripo] API Key:', apiKey ? `${apiKey.slice(0, 8)}...${apiKey.slice(-4)}` : '未设置');
  
  // 检查余额
  await checkBalance(apiKey, dispatcher);
  
  return generate3D({ apiKey, model, prompt, images, config, dispatcher });
}

/**
 * 3D 生成主流程
 */
async function generate3D({ apiKey, model, prompt, images, config, dispatcher }) {
  const hasImage = images && images.length > 0;
  const hasPrompt = prompt && prompt.trim();
  
  if (!hasImage && !hasPrompt) {
    throw new Error('需要提供图片或提示词');
  }
  
  // ========== 步骤 1: 构建任务参数 ==========
  let payload = {};
  let uploadedTokens = [];
  let inputImages = []; // 保存输入图片信息
  
  if (hasImage) {
    // 检查是否有 imageSlots 配置（多视图模式）
    const imageSlots = config.imageSlots;
    const isMultiview = imageSlots && imageSlots.length > 0;
    
    if (isMultiview) {
      // ========== 多视图模式（Tripo Multiview API） ==========
      // API 要求：files 必须恰好包含 4 个项目，顺序为 [front, left, back, right]
      // 可以省略 file_token 来跳过某个视角，但正面必须提供
      
      const slotOrder = ['front', 'left', 'back', 'right'];
      const slotMap = {}; // slotName -> image
      
      // imageSlots 包含 4 个槽位信息，每个槽位有 slot 和 path
      // images 数组只包含有图片的槽位（按 imageSlots 中非空 path 的顺序）
      // 需要将 images 按照 imageSlots 中有 path 的槽位进行匹配
      
      const slotsWithPath = imageSlots.filter(s => s.path);
      console.log(`[tripo] 有图片的槽位:`, slotsWithPath.map(s => s.slot));
      console.log(`[tripo] 图片数量:`, images.length);
      
      // 按顺序将图片匹配到有 path 的槽位
      for (let i = 0; i < slotsWithPath.length && i < images.length; i++) {
        const slotInfo = slotsWithPath[i];
        slotMap[slotInfo.slot] = images[i];
      }
      
      console.log(`[tripo] 多视图模式，槽位映射:`, Object.keys(slotMap));
      
      // 上传有图片的槽位
      const slotTokens = {}; // slotName -> token
      for (const slotName of Object.keys(slotMap)) {
        const img = slotMap[slotName];
        console.log(`[tripo] 上传 ${slotName} 视角图片...`);
        const token = await uploadImage(img.dataBase64, img.mimeType, apiKey, dispatcher);
        slotTokens[slotName] = token;
        inputImages.push({
          slot: slotName,
          originalPath: img.originalPath || null,
          mimeType: img.mimeType,
          size: img.dataBase64.length,
          fileToken: token
        });
      }
      
      // 构建 files 数组（始终 4 个元素，按 [front, left, back, right] 顺序）
      const files = slotOrder.map(slotName => {
        const token = slotTokens[slotName];
        if (token) {
          return { type: 'image', file_token: token };
        } else {
          // 没有该视角的图片，返回空对象（不含 file_token）
          return { type: 'image' };
        }
      });
      
      payload = {
        type: 'multiview_to_model',
        files: files
      };
      
      console.log(`[tripo] 多视图 files 数组:`, files.map((f, i) => `${slotOrder[i]}: ${f.file_token ? '有' : '无'}`));
      
    } else {
      // ========== 普通模式（单图或多图） ==========
      console.log(`[tripo] 上传 ${images.length} 张图片...`);
      for (let i = 0; i < images.length; i++) {
        const img = images[i];
        const token = await uploadImage(img.dataBase64, img.mimeType, apiKey, dispatcher);
        uploadedTokens.push(token);
        // 保存图片信息（原始路径和 file_token）
        inputImages.push({
          index: i,
          originalPath: img.originalPath || null,
          mimeType: img.mimeType,
          size: img.dataBase64.length,
          fileToken: token
        });
      }
      
      if (images.length > 1) {
        // 多图模式（非结构化的多视图，按顺序传递）
        payload = {
          type: 'multiview_to_model',
          files: uploadedTokens.map(token => ({
            type: 'image',
            file_token: token
          }))
        };
      } else {
        // 单图模式
        payload = {
          type: 'image_to_model',
          file: {
            type: 'image',
            file_token: uploadedTokens[0]
          }
        };
      }
    }
  } else {
    // 文本模式
    payload = {
      type: 'text_to_model',
      prompt: prompt.trim()
    };
  }
  
  // ========== 步骤 2: 添加可选参数 ==========
  
  // 模型版本（跳过 default）
  if (config.modelVersion && config.modelVersion !== 'default') {
    payload.model_version = config.modelVersion;
  }
  
  // 面数限制
  if (config.faceLimit) {
    payload.face_limit = parseInt(config.faceLimit);
  }
  
  // 纹理设置
  if (config.texture !== undefined) {
    payload.texture = config.texture !== false && config.texture !== 'false';
  }
  
  // PBR 材质
  if (config.pbr !== undefined) {
    payload.pbr = config.pbr === true || config.pbr === 'true';
  }
  
  // 方向控制
  if (config.orientation && config.orientation !== 'auto') {
    payload.orientation = config.orientation;
  }
  
  // 文本模式专用参数
  if (payload.type === 'text_to_model') {
    if (config.style) {
      payload.style = config.style;
    }
    if (config.negativePrompt) {
      payload.negative_prompt = config.negativePrompt;
    }
  }
  
  // ========== 步骤 3: 创建任务 ==========
  const { taskId, traceId } = await createTask(payload, apiKey, dispatcher);
  
  // ========== 步骤 4: 轮询结果 ==========
  const taskResult = await pollTask(taskId, apiKey, dispatcher);
  console.log('[tripo] 任务完成:', JSON.stringify(taskResult, null, 2));
  
  // ========== 步骤 5: 提取模型 URL ==========
  let modelUrl = null;
  const output = taskResult.output || {};
  
  // 优先使用 PBR 模型
  modelUrl = output.pbr_model || output.model || output.base_model;
  
  if (!modelUrl) {
    throw new Error(`未返回模型 URL: ${JSON.stringify(output)}`);
  }
  
  console.log(`[tripo] 模型 URL: ${modelUrl}`);
  
  // ========== 步骤 6: 下载模型 ==========
  console.log('[tripo] 下载模型...');
  const startDownload = Date.now();
  const { buffer, contentType } = await downloadContent(modelUrl, dispatcher, null);
  console.log(`[tripo] 下载完成, 耗时 ${Date.now() - startDownload}ms, 大小 ${buffer.length} 字节`);
  
  // ========== 步骤 7: 构建返回结果 ==========
  const usage = taskResult.running_left_credits !== undefined ? {
    credits_used: taskResult.running_left_credits,
    total_tokens: taskResult.running_left_credits * 1000
  } : null;
  
  const meta = {
    traceId: traceId || null,
    taskId: taskId,
    createdAt: getLocalTimeString(),
    taskType: payload.type,
    modelVersion: payload.model_version || 'default',
    // 保存参考图片信息
    inputImages: inputImages.length > 0 ? inputImages : null,
    parameters: {
      texture: payload.texture,
      pbr: payload.pbr,
      faceLimit: payload.face_limit,
      orientation: payload.orientation,
      style: payload.style,
      negativePrompt: payload.negative_prompt
    },
    taskResult: {
      status: taskResult.status,
      progress: taskResult.progress,
      output: output
    }
  };
  
  return {
    dataBase64: buffer.toString('base64'),
    mimeType: contentType || 'model/gltf-binary',
    usage,
    meta,
    modelPath: 'model.glb'
  };
}

module.exports = { generate };
