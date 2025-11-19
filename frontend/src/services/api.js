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
  return api.get('/questions').then(r => r.data);
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

// Generate image
export function generateImage(payload) {
  // { prompt, modelName?, questionId? }
  return api.post('/generate', payload, { timeout: 120000 }).then(r => r.data);
}

export default api;


