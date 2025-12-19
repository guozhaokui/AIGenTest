'use strict';

/**
 * Meshy Driver
 * Meshy 3D 生成 API (文本转3D, 图片转3D, 多图转3D)
 * 文档: https://docs.meshy.ai/en
 */

const axios = require('axios');

const BASE_URL = 'https://api.meshy.ai';

// 辅助函数：处理代理设置
function getDispatcher(config) {
  let dispatcher = undefined;
  if (config.useProxy === false || config.useProxy === 'false') {
    try {
      const { Agent } = require('undici');
      dispatcher = new Agent();
    } catch (e) {
      // ignore if undici not available
    }
  }
  return dispatcher;
}

// 辅助函数：使用 axios 下载内容（支持超时和重试）
async function downloadContent(url, maxRetries = 3) {
  let lastError;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      console.log(`[meshy-3d] 下载尝试 ${attempt}/${maxRetries}...`);
      
      const response = await axios.get(url, {
        responseType: 'arraybuffer',
        timeout: 600000, // 10 分钟超时
        maxContentLength: Infinity,
        maxBodyLength: Infinity,
        proxy: false, // 禁用代理，避免 HTTP/HTTPS 问题
        headers: {
          'Accept': '*/*',
          'User-Agent': 'AIGenTest/1.0'
        }
      });
      
      const buffer = Buffer.from(response.data);
      const contentType = response.headers['content-type'];
      
      console.log(`[meshy-3d] 下载成功，大小: ${buffer.length} 字节`);
      return { buffer, contentType };
      
    } catch (error) {
      lastError = error;
      console.error(`[meshy-3d] 下载尝试 ${attempt} 失败:`, error.message);
      
      // 如果是最后一次尝试，直接抛出错误
      if (attempt === maxRetries) {
        break;
      }
      
      // 等待一段时间后重试（指数退避）
      const waitTime = Math.min(1000 * Math.pow(2, attempt - 1), 10000);
      console.log(`[meshy-3d] ${waitTime}ms 后重试...`);
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
  }
  
  throw new Error(`下载失败 (${maxRetries} 次尝试): ${lastError?.message || 'Unknown error'}`);
}

// Helper function for polling task status
async function pollTask(taskId, taskType, apiKey, dispatcher) {
  // Meshy API endpoints for different task types
  const endpointMap = {
    'text-to-3d': `/openapi/v2/text-to-3d/${taskId}`,
    'image-to-3d': `/openapi/v1/image-to-3d/${taskId}`,
    'multi-image-to-3d': `/openapi/v1/multi-image-to-3d/${taskId}`
  };
  
  const pollUrl = `${BASE_URL}${endpointMap[taskType] || endpointMap['image-to-3d']}`;
  const maxAttempts = 180; // 180 attempts (30 minutes with 10s interval)
  const intervalMs = 10000; // 10 seconds

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
      throw new Error(`Meshy API poll failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    const status = result.status;
    const progress = result.progress || 0;
    
    console.log(`[meshy-3d] Polling attempt ${attempt + 1}/${maxAttempts}, status: ${status}, progress: ${progress}%`);

    if (status === 'SUCCEEDED') {
      return result;
    } else if (status === 'FAILED') {
      throw new Error(`3D generation failed: ${result.message || result.error || 'Unknown error'}`);
    } else if (status === 'EXPIRED') {
      throw new Error('3D generation task expired');
    }

    // Wait before next attempt
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('3D generation timed out after maximum attempts');
}

// Convert base64 image to data URL for Meshy API
function toDataUrl(base64, mimeType) {
  return `data:${mimeType};base64,${base64}`;
}

// Create a single text-to-3d task (preview or refine)
async function createTextTo3DTask({ apiKey, prompt, config, dispatcher, isRefine = false, previewTaskId = null }) {
  const apiUrl = `${BASE_URL}/openapi/v2/text-to-3d`;
  let payload;
  
  if (isRefine && previewTaskId) {
    // Refine mode - requires a preview task ID
    payload = {
      mode: 'refine',
      preview_task_id: previewTaskId
    };
    
    // Optional texture richness for refine mode
    if (config.textureRichness) {
      payload.texture_richness = config.textureRichness; // 'low', 'medium', 'high'
    }
  } else {
    // Preview mode
    payload = {
      mode: 'preview',
      prompt: prompt.trim()
    };
    
    // Optional art style
    if (config.artStyle) {
      payload.art_style = config.artStyle;
    }
    
    // Optional negative prompt
    if (config.negativePrompt) {
      payload.negative_prompt = config.negativePrompt;
    }
    
    // Optional seed for reproducibility
    if (config.seed !== undefined) {
      payload.seed = parseInt(config.seed);
    }
    
    // AI model version
    if (config.aiModel) {
      payload.ai_model = config.aiModel;
    }
    
    // Target polycount
    if (config.targetPolycount) {
      payload.target_polycount = parseInt(config.targetPolycount);
    }
    
    // Topology
    if (config.topology) {
      payload.topology = config.topology; // 'quad', 'triangle'
    }
  }

  console.log(`[meshy-3d] Creating text-to-3d ${isRefine ? 'refine' : 'preview'} task with payload:`, JSON.stringify(payload, null, 2));

  const response = await fetch(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify(payload),
    dispatcher
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Meshy API failed: ${response.status} ${response.statusText} - ${errorText}`);
  }

  const result = await response.json();
  const taskId = result.result;
  
  if (!taskId) {
    throw new Error(`Meshy API returned no task ID: ${JSON.stringify(result)}`);
  }
  
  console.log(`[meshy-3d] Created text-to-3d ${isRefine ? 'refine' : 'preview'} task with ID: ${taskId}`);
  
  return taskId;
}

// Text to 3D generation with support for auto-refine
// mode: 'preview' - only preview, 'refine' - only refine (needs previewTaskId), 'full' - auto preview then refine
async function textTo3D({ apiKey, prompt, config, dispatcher }) {
  const mode = config.mode || 'preview'; // 'preview', 'refine', or 'full'
  
  // If refine mode with existing preview task ID
  if (mode === 'refine' && config.previewTaskId) {
    const taskId = await createTextTo3DTask({ 
      apiKey, prompt, config, dispatcher, 
      isRefine: true, 
      previewTaskId: config.previewTaskId 
    });
    return { taskId, taskType: 'text-to-3d', isRefine: true };
  }
  
  // If full mode (auto preview + refine) or just preview
  const previewTaskId = await createTextTo3DTask({ 
    apiKey, prompt, config, dispatcher, 
    isRefine: false 
  });
  
  // If only preview mode, return now
  if (mode === 'preview') {
    return { taskId: previewTaskId, taskType: 'text-to-3d', isRefine: false };
  }
  
  // Full mode: wait for preview to complete, then start refine
  console.log('[meshy-3d] Full mode: waiting for preview task to complete...');
  const previewResult = await pollTask(previewTaskId, 'text-to-3d', apiKey, dispatcher);
  console.log('[meshy-3d] Preview completed, starting refine task...');
  
  // Now create refine task using the preview task ID
  const refineTaskId = await createTextTo3DTask({ 
    apiKey, prompt, config, dispatcher, 
    isRefine: true, 
    previewTaskId: previewTaskId 
  });
  
  return { 
    taskId: refineTaskId, 
    taskType: 'text-to-3d', 
    isRefine: true,
    previewTaskId: previewTaskId,
    previewResult: previewResult
  };
}

// Image to 3D generation
async function imageTo3D({ apiKey, images, config, dispatcher }) {
  const apiUrl = `${BASE_URL}/openapi/v1/image-to-3d`;
  
  const img = images[0];
  const imageUrl = toDataUrl(img.dataBase64, img.mimeType);
  
  const payload = {
    image_url: imageUrl
  };
  
  // Optional: enable PBR (Physically Based Rendering)
  if (config.enablePbr !== undefined) {
    payload.enable_pbr = config.enablePbr === true || config.enablePbr === 'true';
  }
  
  // Optional: should remesh
  if (config.shouldRemesh !== undefined) {
    payload.should_remesh = config.shouldRemesh === true || config.shouldRemesh === 'true';
  }
  
  // Optional: should texture
  if (config.shouldTexture !== undefined) {
    payload.should_texture = config.shouldTexture === true || config.shouldTexture === 'true';
  }
  
  // Optional: AI model version
  if (config.aiModel) {
    payload.ai_model = config.aiModel;
  }
  
  // Optional: target polycount
  if (config.targetPolycount) {
    payload.target_polycount = parseInt(config.targetPolycount);
  }
  
  // Optional: topology
  if (config.topology) {
    payload.topology = config.topology; // 'quad', 'triangle'
  }

  console.log('[meshy-3d] Creating image-to-3d task...');
  console.log('[meshy-3d] Image size:', img.dataBase64.length, 'bytes (base64)');

  const response = await fetch(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify(payload),
    dispatcher
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Meshy API failed: ${response.status} ${response.statusText} - ${errorText}`);
  }

  const result = await response.json();
  const taskId = result.result;
  
  if (!taskId) {
    throw new Error(`Meshy API returned no task ID: ${JSON.stringify(result)}`);
  }
  
  console.log(`[meshy-3d] Created image-to-3d task with ID: ${taskId}`);
  
  return { taskId, taskType: 'image-to-3d' };
}

// Multi-Image to 3D generation
async function multiImageTo3D({ apiKey, images, config, dispatcher }) {
  const apiUrl = `${BASE_URL}/openapi/v1/multi-image-to-3d`;
  
  // Convert all images to data URLs
  const imageUrls = images.map(img => toDataUrl(img.dataBase64, img.mimeType));
  
  const payload = {
    image_urls: imageUrls
  };
  
  // Optional: AI model version
  if (config.aiModel) {
    payload.ai_model = config.aiModel;
  }
  
  // Optional: target polycount
  if (config.targetPolycount) {
    payload.target_polycount = parseInt(config.targetPolycount);
  }
  
  // Optional: topology
  if (config.topology) {
    payload.topology = config.topology; // 'quad', 'triangle'
  }

  console.log(`[meshy-3d] Creating multi-image-to-3d task with ${images.length} images...`);

  const response = await fetch(apiUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify(payload),
    dispatcher
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Meshy API failed: ${response.status} ${response.statusText} - ${errorText}`);
  }

  const result = await response.json();
  const taskId = result.result;
  
  if (!taskId) {
    throw new Error(`Meshy API returned no task ID: ${JSON.stringify(result)}`);
  }
  
  console.log(`[meshy-3d] Created multi-image-to-3d task with ID: ${taskId}`);
  
  return { taskId, taskType: 'multi-image-to-3d' };
}

async function generate({ apiKey, model, prompt, images, config }) {
  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = 'Set MESHY_API_KEY in environment';
    throw err;
  }

  const dispatcher = getDispatcher(config);
  
  const hasImage = images && images.length > 0;
  const hasPrompt = prompt && prompt.trim();
  
  // Determine generation mode
  let taskInfo;
  
  if (hasImage && images.length > 1) {
    // Multi-image to 3D
    taskInfo = await multiImageTo3D({ apiKey, images, config, dispatcher });
  } else if (hasImage) {
    // Single image to 3D
    taskInfo = await imageTo3D({ apiKey, images, config, dispatcher });
  } else if (hasPrompt) {
    // Text to 3D
    taskInfo = await textTo3D({ apiKey, prompt, config, dispatcher });
  } else {
    throw new Error('Meshy 3D generation requires an input image or prompt');
  }
  
  const { taskId, taskType } = taskInfo;
  
  // Poll for result
  const taskResult = await pollTask(taskId, taskType, apiKey, dispatcher);
  
  // Log the complete task result for debugging
  console.log('[meshy-3d] Task succeeded, complete result:', JSON.stringify(taskResult, null, 2));
  
  // Extract model URL from result
  // Meshy returns model_urls with different formats (glb, fbx, obj, etc.)
  let modelUrl = null;
  
  if (taskResult.model_urls) {
    // Prefer GLB format, then FBX, then OBJ
    modelUrl = taskResult.model_urls.glb || 
               taskResult.model_urls.fbx || 
               taskResult.model_urls.obj ||
               Object.values(taskResult.model_urls)[0];
  } else if (taskResult.model_url) {
    modelUrl = taskResult.model_url;
  }
  
  if (!modelUrl) {
    throw new Error(`Meshy API returned no model URL. Available output: ${JSON.stringify(taskResult)}`);
  }
  
  console.log(`[meshy-3d] 3D 生成成功, 模型 URL: ${modelUrl}`);
  
  // 下载 3D 模型（带重试机制）
  console.log('[meshy-3d] 开始下载模型...');
  const startDownload = Date.now();
  const { buffer, contentType } = await downloadContent(modelUrl, 3); // 最多重试 3 次
  console.log(`[meshy-3d] 下载完成，耗时 ${Date.now() - startDownload}ms，大小: ${buffer.length} 字节`);
  
  const base64 = buffer.toString('base64');
  
  // 根据 URL 或 content-type 确定 MIME 类型
  let mimeType = contentType || 'model/gltf-binary';
  let modelPath = 'model.glb'; // 默认模型文件名
  
  if (modelUrl.includes('.glb')) {
    mimeType = 'model/gltf-binary';
    modelPath = 'model.glb';
  } else if (modelUrl.includes('.fbx')) {
    mimeType = 'application/octet-stream';
    modelPath = 'model.fbx';
  } else if (modelUrl.includes('.obj')) {
    mimeType = 'text/plain';
    modelPath = 'model.obj';
  }
  
  // 提取 usage 信息
  const usage = taskResult.credits !== undefined ? {
    credits_used: taskResult.credits,
    total_tokens: taskResult.credits * 1000 // 近似 token 计算
  } : null;
  
  // 构建元数据
  const meta = {
    taskId: taskId,
    taskType: taskType,
    createdAt: new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' }),
    meshyResult: {
      modelUrls: taskResult.model_urls,
      textureUrls: taskResult.texture_urls,
      thumbnailUrl: taskResult.thumbnail_url
    },
    inputImages: images ? images.map((img, index) => ({
      index: index,
      originalPath: img.originalPath || null,
      mimeType: img.mimeType,
      size: Buffer.from(img.dataBase64, 'base64').length
    })) : []
  };
  
  return {
    dataBase64: base64,
    mimeType: mimeType,
    modelPath: modelPath, // 返回模型文件名，供前端使用
    usage,
    meta // 返回元数据，保存到 meta.json
  };
}

// Export additional functions for direct access if needed
module.exports = { 
  generate,
  textTo3D,
  imageTo3D,
  multiImageTo3D,
  pollTask
};

