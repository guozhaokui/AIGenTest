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

export function listQuestions() {
  return api.get('/questions').then(r => r.data);
}

export function submitEvaluation(payload) {
  // { questionId, scores, comment? }
  return api.post('/evaluations', payload).then(r => r.data);
}

export default api;


