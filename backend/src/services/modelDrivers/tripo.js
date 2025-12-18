'use strict';

/**
 * Tripo3D 驱动
 * 用于 Tripo3D 图生 3D 模型
 * 文档: https://platform.tripo3d.ai/docs/quick-start
 */

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
 * @param {string} url - 下载地址
 * @param {object} dispatcher - 网络分发器
 * @param {string} apiKey - API 密钥（如需要）
 */
async function downloadContent(url, dispatcher, apiKey) {
  const headers = {};
  // Tripo 下载链接可能需要认证
  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }
  
  const resp = await fetch(url, { 
    dispatcher,
    headers 
  });
  if (!resp.ok) {
    throw new Error(`下载失败: ${resp.status}`);
  }
  const arrayBuffer = await resp.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const contentType = resp.headers.get('content-type');
  return { buffer, contentType };
}

/**
 * 轮询任务状态
 * @param {string} taskId - 任务 ID
 * @param {string} apiKey - API 密钥
 * @param {object} dispatcher - 网络分发器
 */
async function pollTask(taskId, apiKey, dispatcher) {
  const pollUrl = `https://api.tripo3d.com/v2/openapi/task/${taskId}`;
  const maxAttempts = 120; // 最多轮询 120 次（间隔 10 秒，共 20 分钟）
  const intervalMs = 10000; // 轮询间隔 10 秒

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
      throw new Error(`Tripo API 轮询失败: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    // Tripo API 响应格式: { code: 0, data: { status: 'success'|'running'|'failed', ... } }
    if (result.code !== 0) {
      throw new Error(`Tripo API 错误: ${result.message || JSON.stringify(result)}`);
    }
    
    const status = result.data?.status;
    const progress = result.data?.progress || 0;
    
    console.log(`[tripo-3d] 轮询第 ${attempt + 1}/${maxAttempts} 次, 状态: ${status}, 进度: ${progress}%`);

    if (status === 'success') {
      return result.data;
    } else if (status === 'failed') {
      throw new Error(`3D 生成失败: ${result.data?.error || '未知错误'}`);
    } else if (status === 'cancelled') {
      throw new Error('3D 生成任务已取消');
    }

    // 等待后继续轮询
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('3D 生成超时，已达到最大轮询次数');
}

/**
 * 上传图片并获取文件 token
 * @param {string} imageBase64 - Base64 编码的图片数据
 * @param {string} mimeType - 图片 MIME 类型
 * @param {string} apiKey - API 密钥
 * @param {object} dispatcher - 网络分发器
 */
async function uploadImage(imageBase64, mimeType, apiKey, dispatcher) {
  const uploadUrl = 'https://api.tripo3d.com/v2/openapi/upload';
  
  // 将 Base64 转换为二进制 Buffer
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
  
  // 使用 form-data 包创建 FormData
  const FormData = require('form-data');
  const formData = new FormData();
  formData.append('file', buffer, {
    filename: filename,
    contentType: mimeType
  });
  
  // 发送上传请求
  const response = await fetch(uploadUrl, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      ...formData.getHeaders()
    },
    body: formData,
    dispatcher
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Tripo 上传失败: ${response.status} ${response.statusText} - ${errorText}`);
  }

  const result = await response.json();
  
  if (result.code !== 0) {
    throw new Error(`Tripo 上传错误: ${result.message || JSON.stringify(result)}`);
  }
  
  console.log('[tripo-3d] 图片上传成功, token:', result.data?.image_token);
  return result.data?.image_token;
}

/**
 * 获取本地时间字符串
 */
function getLocalTimeString() {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60000;
  const localTime = new Date(now.getTime() - offset);
  return localTime.toISOString().replace('Z', '') + '+' + String(Math.abs(now.getTimezoneOffset() / 60)).padStart(2, '0') + ':00';
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
  
  // 3D 生成
  return generate3D({ apiKey, model, prompt, images, config, dispatcher });
}

/**
 * 3D 生成函数
 */
async function generate3D({ apiKey, model, prompt, images, config, dispatcher }) {
  const apiUrl = 'https://api.tripo3d.com/v2/openapi/task';
  
  const hasImage = images && images.length > 0;
  const hasPrompt = prompt && prompt.trim();
  
  // 需要至少有图片或提示词
  if (!hasImage && !hasPrompt) {
    throw new Error('Tripo 3D 生成需要输入图片或提示词');
  }
  
  let payload = {};
  
  if (hasImage) {
    // 检查是否有多张图片（多视图模式 - Tripo 3.0 特性）
    if (images.length > 1) {
      // 多视图转 3D 模式（Tripo 3.0）
      console.log(`[tripo-3d] 上传 ${images.length} 张图片用于多视图模式...`);
      const imageTokens = [];
      for (const img of images) {
        const token = await uploadImage(img.dataBase64, img.mimeType, apiKey, dispatcher);
        imageTokens.push(token);
      }
      
      payload = {
        type: 'multiview_to_model',
        files: imageTokens.map(token => ({
          type: 'image',
          file_token: token
        }))
      };
    } else {
      // 单图转 3D 模式
      const img = images[0];
      
      // 先上传图片获取文件 token
      console.log('[tripo-3d] 上传图片...');
      const imageToken = await uploadImage(img.dataBase64, img.mimeType, apiKey, dispatcher);
      
      payload = {
        type: 'image_to_model',
        file: {
          type: 'image',
          file_token: imageToken
        }
      };
    }
  } else {
    // 文本转 3D 模式（无图片，仅提示词）
    payload = {
      type: 'text_to_model',
      prompt: prompt.trim()
    };
  }
  
  // 添加可选的模型版本（如果是 "default" 则跳过，使用 API 的最新版本）
  if (config.modelVersion && config.modelVersion !== 'default') {
    payload.model_version = config.modelVersion;
  }
  
  // 添加可选的面数限制
  if (config.faceLimit) {
    payload.face_limit = parseInt(config.faceLimit);
  }
  
  // 添加纹理设置
  if (config.texture !== undefined) {
    payload.texture = config.texture !== false && config.texture !== 'false';
  }
  
  // 添加 PBR 设置
  if (config.pbr !== undefined) {
    payload.pbr = config.pbr === true || config.pbr === 'true';
  }
  
  // Tripo 3.0 新特性
  // 添加方向控制（auto, align_image, none）
  if (config.orientation) {
    payload.orientation = config.orientation;
  }
  
  // 添加文本转 3D 的风格控制
  if (payload.type === 'text_to_model' && config.style) {
    payload.style = config.style;
  }
  
  // 添加文本转 3D 的负面提示词
  if (payload.type === 'text_to_model' && config.negativePrompt) {
    payload.negative_prompt = config.negativePrompt;
  }

  console.log('[tripo-3d] 创建任务，参数:', JSON.stringify(payload, null, 2));
  console.log('[tripo-3d] 使用 API Key:', apiKey ? `${apiKey.slice(0, 8)}...${apiKey.slice(-4)}` : '未设置');

  try {
    // 可选：检查账户余额（调试用）
    console.log('[tripo-3d] 检查账户余额...');
    try {
      const balanceResp = await fetch('https://api.tripo3d.com/v2/openapi/user/balance', {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${apiKey}` },
        dispatcher
      });
      const balanceData = await balanceResp.json();
      console.log('[tripo-3d] 账户余额信息:', JSON.stringify(balanceData, null, 2));
    } catch (e) {
      console.log('[tripo-3d] 无法获取余额:', e.message);
    }

    // 创建 3D 生成任务
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify(payload),
      dispatcher
    });

    // 获取 Trace ID 用于跟踪
    const traceId = response.headers.get('X-Tripo-Trace-ID') || response.headers.get('x-tripo-trace-id');
    if (traceId) {
      console.log(`[tripo-3d] Trace ID: ${traceId}`);
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Tripo API 失败: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    if (result.code !== 0) {
      throw new Error(`Tripo API 错误: ${result.message || JSON.stringify(result)}`);
    }
    
    const taskId = result.data?.task_id;
    
    if (!taskId) {
      throw new Error('Tripo API 未返回任务 ID');
    }
    
    console.log(`[tripo-3d] 任务已创建，ID: ${taskId}`);
    
    // 轮询获取结果
    const taskResult = await pollTask(taskId, apiKey, dispatcher);
    
    // 打印完整的任务结果（调试用）
    console.log('[tripo-3d] 任务成功，完整结果:', JSON.stringify(taskResult, null, 2));
    
    // 从结果中提取模型 URL
    // Tripo 返回格式: { output: { model: "url_to_glb" } } 或 { output: { pbr_model: "url" } }
    let modelUrl = null;
    
    if (taskResult.output) {
      // 优先使用 PBR 模型（如果有）
      modelUrl = taskResult.output.pbr_model || taskResult.output.model;
    }
    
    if (!modelUrl) {
      throw new Error(`Tripo API 未返回模型 URL。可用输出: ${JSON.stringify(taskResult.output)}`);
    }
    
    console.log(`[tripo-3d] 3D 生成成功，模型 URL: ${modelUrl}`);
    
    // 下载 3D 模型（Tripo URL 通常不需要认证头）
    console.log('[tripo-3d] 下载模型...');
    const startDownload = Date.now();
    const { buffer, contentType } = await downloadContent(modelUrl, dispatcher, null);
    console.log(`[tripo-3d] 下载完成，耗时 ${Date.now() - startDownload}ms，大小: ${buffer.length} 字节`);
    
    const base64 = buffer.toString('base64');
    
    // 提取使用信息（如果有）
    const usage = taskResult.running_left_credits !== undefined ? {
      credits_used: taskResult.running_left_credits,
      total_tokens: taskResult.running_left_credits * 1000 // 近似 token 等价
    } : null;
    
    // 构建元数据
    const meta = {
      traceId: traceId || null,
      taskId: taskId,
      createdAt: getLocalTimeString(),
      taskType: payload.type,
      modelVersion: payload.model_version || 'default',
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
        output: taskResult.output
      }
    };
    
    return {
      dataBase64: base64,
      mimeType: contentType || 'model/gltf-binary',
      usage,
      meta,
      // 返回模型文件的相对路径（相对于模型目录），供前端显示
      modelPath: 'model.glb'
    };

  } catch (error) {
    throw new Error(`Tripo 3D 驱动错误: ${error.message}`);
  }
}

module.exports = { generate };
