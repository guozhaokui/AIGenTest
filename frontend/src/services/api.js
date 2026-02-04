import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000
});

export function uploadExampleImage(file) {
  const form = new FormData();
  form.append('file', file);
  return api.post('/examples/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });
}

export function listDimensions() {
  return api.get('/dimensions').then(r => r.data);
}

export function createDimension(payload) {
  return api.post('/dimensions', payload).then(r => r.data);
}

export function updateDimension(id, payload) {
  return api.patch(`/dimensions/${id}`, payload).then(r => r.data);
}

export function deleteDimension(id) {
  return api.delete(`/dimensions/${id}`).then(r => r.data);
}

export function listQuestions() {
  return api.get('/questions').then(r => {
    const data = r.data;
    if (Array.isArray(data)) return data;
    if (data && Array.isArray(data.items)) return data.items;
    return [];
  });
}
export function listQuestionsPaged(params = {}) {
  return api.get('/questions', { params }).then(r => r.data);
}
export function cloneQuestion(id) {
  return api.post(`/questions/${id}/clone`).then(r => r.data);
}

export function listQuestionSets() {
  return api.get('/question-sets').then(r => r.data);
}

export function createQuestionSet(payload) {
  return api.post('/question-sets', payload).then(r => r.data);
}

export function updateQuestionSet(id, payload) {
  return api.patch(`/question-sets/${id}`, payload).then(r => r.data);
}

export function createQuestion(payload) {
  return api.post('/questions', payload).then(r => r.data);
}

export function updateQuestion(id, payload) {
  return api.patch(`/questions/${id}`, payload).then(r => r.data);
}

export function deleteQuestion(id) {
  return api.delete(`/questions/${id}`).then(r => r.data);
}

export function submitEvaluation(payload) {
  // { questionId, scores, comment? }
  return api.post('/evaluations', payload).then(r => r.data);
}

// Runs API
export function startRun(payload) {
  // { modelName?, questionSetId, runName?, runDesc? }
  return api.post('/runs/start', payload).then(r => r.data);
}
export function addRunItem(runId, payload) {
  // { questionId, scoresByDimension, comment?, generatedImagePath? }
  return api.post(`/runs/${runId}/items`, payload).then(r => r.data);
}
export function finishRun(runId, payload) {
  return api.post(`/runs/${runId}/finish`, payload).then(r => r.data);
}
export function listRuns() {
  return api.get('/runs').then(r => r.data);
}
export function getRun(runId) {
  return api.get(`/runs/${runId}`).then(r => r.data);
}
export function getRunItems(runId) {
  return api.get(`/runs/${runId}/items`).then(r => r.data);
}
export function cloneRun(runId, payload) {
  return api.post(`/runs/${runId}/clone`, payload).then(r => r.data);
}
export function deleteRun(runId) {
  return api.delete(`/runs/${runId}`).then(r => r.data);
}

// Generate image
export function generateImage(payload) {
  // { prompt, modelId?, modelName?, questionId?, imagePaths? }
  // timeout: 0 表示无超时限制
  return api.post('/generate', payload, { timeout: 0 }).then(r => r.data);
}

// Models
export function listModels() {
  return api.get('/models').then(r => r.data);
}

// Knowledge Query API - 使用 MemGraph 服务 (port 8848)
const knowledgeApi = axios.create({
  baseURL: 'http://localhost:8848',
  timeout: 30000
});

export function getKnowledgeStatus() {
  return knowledgeApi.get('/status').then(r => r.data);
}

export function scanDocuments() {
  // 刷新索引：扫描records目录并增量索引新文档/修改的文档
  return knowledgeApi.post('/rebuild', {}).then(r => r.data);
}

export function indexDocuments(payload) {
  // { files: string[] }
  return knowledgeApi.post('/index', payload).then(r => r.data);
}

export function queryKnowledge(payload) {
  // { question: string, model: string, top_k: number }
  // 适配 MemGraph API: 使用 /search 端点
  const memgraphPayload = {
    query: payload.question,
    limit: payload.top_k || 3,
    min_score: 0.1,
    use_vector: true
  };

  return knowledgeApi.post('/search', memgraphPayload).then(response => {
    const data = response.data;

    // 将 MemGraph 响应格式转换为前端期望的格式
    // MemGraph 返回: { query: string, count: number, results: [...] }
    // 前端期望: { success: boolean, data: { question, answer, context, model } }

    const contextDocs = data.results.slice(0, payload.top_k || 3).map((result, index) => ({
      index: index + 1,
      source: result.path || result.problem || 'Unknown',
      // 直接使用文档的原始内容，保持Markdown结构
      content: result.solution || result.solution_preview || '(无内容)',
      similarity: result.vector_similarity || result.total_score / 100 || 0,
      segments: result.segments || []  // 添加细粒度匹配片段
    }));

    return {
      success: true,
      data: {
        question: data.query,
        answer: null, // MemGraph 不提供 LLM 生成的答案
        context: contextDocs,
        model: payload.model
      }
    };
  }).catch(error => {
    return {
      success: false,
      error: error.message || '查询失败'
    };
  });
}

export function getKnowledgeModels() {
  return knowledgeApi.get('/models').then(r => r.data);
}

export function clearKnowledge() {
  return knowledgeApi.post('/clear').then(r => r.data);
}

export function deleteDocument(payload) {
  // { source: string }
  return knowledgeApi.post('/delete', payload).then(r => r.data);
}

export function getStats() {
  // MemGraph /stats 返回: { documents, ngrams, unique_ngrams, faiss_vectors }
  // 前端期望: { success: boolean, data: { total_documents, dimension } }
  return knowledgeApi.get('/stats').then(response => {
    const data = response.data;
    return {
      success: true,
      data: {
        total_documents: data.documents || 0,
        dimension: 512, // MemGraph 使用 512 维向量
        faiss_vectors: data.faiss_vectors || 0
      }
    };
  }).catch(error => {
    return {
      success: false,
      error: error.message
    };
  });
}

export function chat(payload) {
  // { message: string, model: string, history: array, system_prompt: string }
  return knowledgeApi.post('/chat', payload).then(r => r.data);
}

export function searchDocuments(payload) {
  // { query: string, top_k: number }
  // 纯向量检索，不调用LLM
  return knowledgeApi.post('/search', payload).then(r => r.data);
}

// Alias for compatibility with MemoryManagement component
export const getStatus = getKnowledgeStatus;

export default api;


