/**
 * 图片管理服务 API
 * 通过 backend 代理访问 Python 图片管理服务
 */
import axios from 'axios';

const imagemgrApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/imagemgr',
  timeout: 30000
});

// ==================== 图片操作 ====================

/**
 * 上传图片
 * @param {File} file 图片文件
 * @param {string} source 来源标记
 */
export function uploadImage(file, source = null) {
  const form = new FormData();
  form.append('file', file);
  if (source) {
    form.append('source', source);
  }
  return imagemgrApi.post('/images', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(r => r.data);
}

/**
 * 获取图片信息
 * @param {string} sha256 图片哈希
 */
export function getImage(sha256) {
  return imagemgrApi.get(`/images/${sha256}`).then(r => r.data);
}

/**
 * 列出图片
 * @param {object} params 查询参数
 */
export function listImages(params = {}) {
  return imagemgrApi.get('/images', { params }).then(r => r.data);
}

/**
 * 删除图片
 * @param {string} sha256 图片哈希
 * @param {boolean} hard 是否硬删除
 */
export function deleteImage(sha256, hard = false) {
  return imagemgrApi.delete(`/images/${sha256}`, {
    params: { hard }
  }).then(r => r.data);
}

/**
 * 获取缩略图 URL
 * @param {string} sha256 图片哈希
 */
export function getThumbnailUrl(sha256) {
  return `/api/imagemgr/images/${sha256}/thumbnail`;
}

/**
 * 获取原图 URL
 * @param {string} sha256 图片哈希
 */
export function getImageUrl(sha256) {
  return `/api/imagemgr/images/${sha256}/file`;
}

// ==================== 描述操作 ====================

/**
 * 添加描述
 * @param {string} sha256 图片哈希
 * @param {string} method 描述方法
 * @param {string} content 描述内容
 */
export function addDescription(sha256, method, content) {
  return imagemgrApi.post(`/images/${sha256}/descriptions`, {
    method,
    content
  }).then(r => r.data);
}

/**
 * 获取描述列表
 * @param {string} sha256 图片哈希
 */
export function getDescriptions(sha256) {
  return imagemgrApi.get(`/images/${sha256}/descriptions`).then(r => r.data);
}

/**
 * 重新计算嵌入
 * @param {string} sha256 图片哈希
 * @param {boolean} includeText 是否同时更新文本嵌入
 */
export function recomputeEmbedding(sha256, includeText = false) {
  return imagemgrApi.post(`/images/${sha256}/recompute-embedding`, null, {
    params: { include_text: includeText }
  }).then(r => r.data);
}

// ==================== 批量处理 ====================

/**
 * 批量导入目录
 * @param {object} options 导入选项
 * @param {string} options.directory 目录路径
 * @param {string} options.source 来源标记
 * @param {boolean} options.recursive 是否递归
 * @param {boolean} options.generate_caption 是否生成描述
 * @param {string} options.caption_method 描述方法
 */
export function batchImport(options) {
  return imagemgrApi.post('/batch/import', options, {
    timeout: 600000
  }).then(r => r.data);
}

/**
 * 批量导入目录（流式，实时进度）
 * @param {object} options 导入选项
 * @param {function} onProgress 进度回调 (data) => void
 * @param {function} onComplete 完成回调 (data) => void
 * @param {function} onError 错误回调 (error) => void
 * @returns {function} 取消函数
 */
export function batchImportStream(options, onProgress, onComplete, onError) {
  const controller = new AbortController();
  
  fetch('/api/imagemgr/batch/import/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(options),
    signal: controller.signal
  }).then(response => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    function processChunk({ done, value }) {
      if (done) return;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      let eventType = '';
      for (const line of lines) {
        if (line.startsWith('event:')) {
          eventType = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          try {
            const data = JSON.parse(line.slice(5).trim());
            if (eventType === 'progress' && onProgress) onProgress(data);
            if (eventType === 'complete' && onComplete) onComplete(data);
            if (eventType === 'init' && onProgress) onProgress({ ...data, current: 0, percent: 0 });
          } catch (e) {}
        }
      }
      
      reader.read().then(processChunk);
    }
    
    reader.read().then(processChunk);
  }).catch(err => {
    if (err.name !== 'AbortError' && onError) onError(err);
  });
  
  return () => controller.abort();
}

/**
 * 批量生成描述
 * @param {object} params 参数
 */
export function batchGenerateCaptions(params = {}) {
  return imagemgrApi.post('/batch/generate-captions', null, {
    params,
    timeout: 600000
  }).then(r => r.data);
}

/**
 * 批量生成描述（流式，实时进度）
 */
export function batchGenerateCaptionsStream(params, onProgress, onComplete, onError) {
  const controller = new AbortController();
  const queryStr = new URLSearchParams(params).toString();
  
  fetch(`/api/imagemgr/batch/generate-captions/stream?${queryStr}`, {
    method: 'POST',
    signal: controller.signal
  }).then(response => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    function processChunk({ done, value }) {
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      let eventType = '';
      for (const line of lines) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim();
        else if (line.startsWith('data:')) {
          try {
            const data = JSON.parse(line.slice(5).trim());
            if (eventType === 'progress' && onProgress) onProgress(data);
            if (eventType === 'complete' && onComplete) onComplete(data);
            if (eventType === 'init' && onProgress) onProgress({ ...data, current: 0, percent: 0 });
          } catch (e) {}
        }
      }
      reader.read().then(processChunk);
    }
    reader.read().then(processChunk);
  }).catch(err => {
    if (err.name !== 'AbortError' && onError) onError(err);
  });
  
  return () => controller.abort();
}

/**
 * 获取待处理图片
 * @param {number} limit 数量限制
 */
export function getPendingImages(limit = 100) {
  return imagemgrApi.get('/batch/pending', {
    params: { limit }
  }).then(r => r.data);
}

/**
 * 批量重新计算嵌入
 * @param {object} params 参数
 */
export function batchRecomputeEmbeddings(params = {}) {
  return imagemgrApi.post('/batch/recompute-embeddings', null, {
    params,
    timeout: 600000
  }).then(r => r.data);
}

/**
 * 批量重新计算嵌入（流式，实时进度）
 */
export function batchRecomputeEmbeddingsStream(params, onProgress, onComplete, onError) {
  const controller = new AbortController();
  const queryStr = new URLSearchParams(params).toString();
  
  fetch(`/api/imagemgr/batch/recompute-embeddings/stream?${queryStr}`, {
    method: 'POST',
    signal: controller.signal
  }).then(response => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    function processChunk({ done, value }) {
      if (done) return;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      
      let eventType = '';
      for (const line of lines) {
        if (line.startsWith('event:')) eventType = line.slice(6).trim();
        else if (line.startsWith('data:')) {
          try {
            const data = JSON.parse(line.slice(5).trim());
            if (eventType === 'progress' && onProgress) onProgress(data);
            if (eventType === 'complete' && onComplete) onComplete(data);
            if (eventType === 'init' && onProgress) onProgress({ ...data, current: 0, percent: 0 });
          } catch (e) {}
        }
      }
      reader.read().then(processChunk);
    }
    reader.read().then(processChunk);
  }).catch(err => {
    if (err.name !== 'AbortError' && onError) onError(err);
  });
  
  return () => controller.abort();
}

// ==================== 搜索 ====================

/**
 * 文本搜索
 * @param {string} query 搜索文本
 * @param {number} topK 返回数量
 */
export function searchByText(query, topK = 20) {
  return imagemgrApi.post('/search/text', {
    query,
    top_k: topK
  }).then(r => r.data);
}

/**
 * 以图搜图
 * @param {File} file 图片文件
 * @param {number} topK 返回数量
 */
export function searchByImage(file, topK = 20) {
  const form = new FormData();
  form.append('file', file);
  form.append('top_k', topK);
  return imagemgrApi.post('/search/image', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }).then(r => r.data);
}

// ==================== VLM 配置 ====================

/**
 * 获取 VLM 配置
 */
export function getVlmConfig() {
  return imagemgrApi.get('/vlm/config').then(r => r.data);
}

/**
 * 获取可用的 VLM 服务列表
 */
export function getVlmServices() {
  return imagemgrApi.get('/vlm/services').then(r => r.data);
}

/**
 * 获取 VLM 可用提示词列表
 */
export function getVlmPrompts() {
  return imagemgrApi.get('/vlm/prompts').then(r => r.data);
}

// ==================== 统计 ====================

/**
 * 获取统计信息
 */
export function getStats() {
  return imagemgrApi.get('/stats').then(r => r.data);
}

/**
 * 健康检查
 */
export function healthCheck() {
  return imagemgrApi.get('/health').then(r => r.data);
}

export default imagemgrApi;

