'use strict';

/**
 * Hyper3D (Rodin) 驱动
 * 用于 Hyper3D 文本/图片 生成 3D 模型
 * 
 * API 文档: https://developer.hyper3d.ai/zh_cn/get-started/minimal-example
 * 
 * 流程:
 * 1. 提交任务到 /rodin -> 获取 uuid 和 subscription_key
 * 2. 轮询 /status -> 检查任务状态
 * 3. 下载结果 /download -> 获取模型文件
 */

const axios = require('axios');
const FormData = require('form-data');
const path = require('path');

const API_BASE = 'https://api.hyper3d.com/api/v2';

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
 * 提交任务到 Hyper3D Rodin API
 * 
 * 支持两种模式：
 * 1. 文本转3D: 传入 prompt 参数
 * 2. 图片转3D: 传入 images 数组
 */
async function submitTask({ prompt, images, config, apiKey }) {
  const url = `${API_BASE}/rodin`;
  
  const formData = new FormData();
  
  // 设置生成参数
  const tier = config.tier || 'Gen-2';
  formData.append('tier', tier);
  
  // mesh_mode: Raw 或 Quad
  const meshMode = config.meshMode || 'Raw';
  formData.append('mesh_mode', meshMode);
  
  // 质量覆盖（面数）
  const qualityOverride = config.qualityOverride || 500000;
  formData.append('quality_override', String(qualityOverride));
  
  // 材质类型: PBR 或 Unlit
  const material = config.material || 'PBR';
  formData.append('material', material);
  
  // 条件模式（仅 Gen-2）
  if (config.conditionMode) {
    formData.append('condition_mode', config.conditionMode);
  }
  
  // 几何条件（仅 Gen-2，可选）
  if (config.geometryCondition) {
    formData.append('geometry_condition', config.geometryCondition);
  }
  
  // 添加输入：文本提示词或图片
  if (prompt && prompt.trim()) {
    formData.append('prompt', prompt.trim());
    console.log(`[hyper3d] 文本转3D模式，提示词: "${prompt.trim().substring(0, 50)}..."`);
  }
  
  if (images && images.length > 0) {
    // 图片转3D模式
    for (let i = 0; i < images.length; i++) {
      const img = images[i];
      const buffer = Buffer.from(img.dataBase64, 'base64');
      
      // 确定文件扩展名
      const extMap = {
        'image/jpeg': 'jpg',
        'image/jpg': 'jpg',
        'image/png': 'png',
        'image/webp': 'webp'
      };
      const ext = extMap[img.mimeType] || 'png';
      const filename = `image_${i}.${ext}`;
      
      formData.append('images', buffer, {
        filename: filename,
        contentType: img.mimeType
      });
      
      console.log(`[hyper3d] 添加图片 ${i + 1}: ${filename}, 大小: ${buffer.length} 字节`);
    }
  }
  
  console.log(`[hyper3d] 提交任务到 ${url}`);
  console.log(`[hyper3d] 参数: tier=${tier}, mesh_mode=${meshMode}, quality=${qualityOverride}, material=${material}`);
  
  try {
    const response = await axios.post(url, formData, {
      headers: {
        ...formData.getHeaders(),
        'Authorization': `Bearer ${apiKey}`
      },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
      proxy: false
    });
    
    const result = response.data;
    console.log(`[hyper3d] 任务提交成功:`, JSON.stringify(result, null, 2));
    
    return result;
  } catch (error) {
    if (error.response) {
      const errData = error.response.data;
      throw new Error(`提交任务失败: ${error.response.status} - ${JSON.stringify(errData)}`);
    }
    throw error;
  }
}

/**
 * 检查任务状态
 * 
 * API: POST /status
 * 请求体: { subscription_key: "xxx" }
 * 响应: { jobs: [{ uuid, status: "Done"|"Running"|"Failed", ... }] }
 */
async function checkStatus(subscriptionKey, apiKey) {
  const url = `${API_BASE}/status`;
  
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  };
  
  const response = await axios.post(url, {
    subscription_key: subscriptionKey
  }, { headers, proxy: false });
  
  return response.data;
}

/**
 * 轮询任务状态直到完成
 */
async function pollTask(subscriptionKey, apiKey) {
  const maxAttempts = 180; // 最多 15 分钟（每 5 秒一次）
  const intervalMs = 5000; // 5 秒间隔
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const statusResponse = await checkStatus(subscriptionKey, apiKey);
    const jobs = statusResponse.jobs || [];
    
    if (jobs.length === 0) {
      console.log(`[hyper3d] 轮询 ${attempt + 1}/${maxAttempts}: 无任务信息`);
      await new Promise(resolve => setTimeout(resolve, intervalMs));
      continue;
    }
    
    // 打印所有任务状态
    for (const job of jobs) {
      console.log(`[hyper3d] 轮询 ${attempt + 1}/${maxAttempts}: job ${job.uuid} - ${job.status}`);
    }
    
    // 检查是否所有任务都完成
    const allDone = jobs.every(j => j.status === 'Done' || j.status === 'Failed');
    
    if (allDone) {
      // 检查是否有失败的任务
      const failed = jobs.find(j => j.status === 'Failed');
      if (failed) {
        throw new Error(`任务失败: ${failed.message || failed.error || 'Unknown error'}`);
      }
      
      return jobs;
    }
    
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }
  
  throw new Error('任务超时');
}

/**
 * 下载生成结果
 * 
 * API: POST /download
 * 请求体: { task_uuid: "xxx" }
 * 响应: { list: [{ name: "xxx.glb", url: "https://..." }, ...] }
 */
async function downloadResults(taskUuid, apiKey) {
  const url = `${API_BASE}/download`;
  
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'Content-Type': 'application/json'
  };
  
  const response = await axios.post(url, {
    task_uuid: taskUuid
  }, { headers, proxy: false });
  
  return response.data;
}

/**
 * 下载文件内容
 */
async function downloadFile(url) {
  console.log(`[hyper3d] 下载文件: ${url}`);
  
  const response = await axios.get(url, {
    responseType: 'arraybuffer',
    timeout: 300000, // 5 分钟超时
    proxy: false
  });
  
  const buffer = Buffer.from(response.data);
  const contentType = response.headers['content-type'];
  
  console.log(`[hyper3d] 下载完成, 大小: ${buffer.length} 字节, 类型: ${contentType}`);
  
  return { buffer, contentType };
}

/**
 * 主生成函数
 */
async function generate({ apiKey, model, prompt, images, config }) {
  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = '请在环境变量中设置 HYPER3D_API_KEY';
    throw err;
  }
  
  const hasImage = images && images.length > 0;
  const hasPrompt = prompt && prompt.trim();
  
  if (!hasImage && !hasPrompt) {
    throw new Error('需要提供图片或提示词');
  }
  
  console.log('[hyper3d] ===== 开始 3D 生成 =====');
  console.log('[hyper3d] API Key:', apiKey ? `${apiKey.slice(0, 8)}...${apiKey.slice(-4)}` : '未设置');
  console.log('[hyper3d] 模式:', hasImage ? '图片转3D' : '文本转3D');
  
  // ========== 步骤 1: 提交任务 ==========
  const taskResponse = await submitTask({ prompt, images, config, apiKey });
  
  const taskUuid = taskResponse.uuid;
  const subscriptionKey = taskResponse.jobs?.subscription_key;
  
  if (!taskUuid) {
    throw new Error(`任务提交成功但未返回 uuid: ${JSON.stringify(taskResponse)}`);
  }
  
  if (!subscriptionKey) {
    throw new Error(`任务提交成功但未返回 subscription_key: ${JSON.stringify(taskResponse)}`);
  }
  
  console.log(`[hyper3d] 任务 UUID: ${taskUuid}`);
  console.log(`[hyper3d] Subscription Key: ${subscriptionKey}`);
  
  // ========== 步骤 2: 轮询状态 ==========
  console.log('[hyper3d] 开始轮询任务状态...');
  const completedJobs = await pollTask(subscriptionKey, apiKey);
  console.log(`[hyper3d] 任务完成, 共 ${completedJobs.length} 个子任务`);
  
  // ========== 步骤 3: 下载结果 ==========
  console.log('[hyper3d] 获取下载链接...');
  const downloadResponse = await downloadResults(taskUuid, apiKey);
  const downloadItems = downloadResponse.list || [];
  
  console.log(`[hyper3d] 可下载文件:`, downloadItems.map(i => i.name));
  
  if (downloadItems.length === 0) {
    throw new Error('未返回任何下载文件');
  }
  
  // 优先下载 GLB 文件
  let targetFile = downloadItems.find(i => i.name.endsWith('.glb'));
  if (!targetFile) {
    // 尝试找其他 3D 格式
    targetFile = downloadItems.find(i => 
      i.name.endsWith('.fbx') || 
      i.name.endsWith('.obj') || 
      i.name.endsWith('.usdz')
    );
  }
  if (!targetFile) {
    // 使用第一个文件
    targetFile = downloadItems[0];
  }
  
  console.log(`[hyper3d] 选择下载: ${targetFile.name}`);
  
  // ========== 步骤 4: 下载模型文件 ==========
  const startDownload = Date.now();
  const { buffer, contentType } = await downloadFile(targetFile.url);
  console.log(`[hyper3d] 下载耗时: ${Date.now() - startDownload}ms`);
  
  // ========== 步骤 5: 确定 MIME 类型 ==========
  let mimeType = contentType;
  const ext = path.extname(targetFile.name).toLowerCase();
  if (ext === '.glb') {
    mimeType = 'model/gltf-binary';
  } else if (ext === '.gltf') {
    mimeType = 'model/gltf+json';
  } else if (ext === '.fbx') {
    mimeType = 'application/octet-stream';
  } else if (ext === '.obj') {
    mimeType = 'text/plain';
  } else if (ext === '.usdz') {
    mimeType = 'model/vnd.usdz+zip';
  }
  
  // ========== 构建返回结果 ==========
  const meta = {
    taskUuid: taskUuid,
    createdAt: getLocalTimeString(),
    taskType: hasImage ? 'image_to_model' : 'text_to_model',
    tier: config.tier || 'Gen-2',
    meshMode: config.meshMode || 'Raw',
    material: config.material || 'PBR',
    qualityOverride: config.qualityOverride || 500000,
    downloadedFile: targetFile.name,
    allFiles: downloadItems.map(i => i.name)
  };
  
  return {
    dataBase64: buffer.toString('base64'),
    mimeType: mimeType,
    usage: null,
    meta,
    modelPath: targetFile.name
  };
}

module.exports = { generate };

