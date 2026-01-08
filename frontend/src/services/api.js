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

// Knowledge Query API (separate service on port 5001)
const knowledgeApi = axios.create({
  baseURL: 'http://localhost:5001/api/knowledge',
  timeout: 30000
});

export function getKnowledgeStatus() {
  return knowledgeApi.get('/status').then(r => r.data);
}

export function scanDocuments(payload) {
  // { path: string }
  return knowledgeApi.post('/scan', payload).then(r => r.data);
}

export function indexDocuments(payload) {
  // { files: string[] }
  return knowledgeApi.post('/index', payload).then(r => r.data);
}

export function queryKnowledge(payload) {
  // { question: string, model: string, top_k: number }
  return knowledgeApi.post('/query', payload).then(r => r.data);
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
  return knowledgeApi.get('/stats').then(r => r.data);
}

// Alias for compatibility with MemoryManagement component
export const getStatus = getKnowledgeStatus;

export default api;


