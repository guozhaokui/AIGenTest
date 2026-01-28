'use strict';

const { spawn } = require('child_process');
const path = require('path');
const app = require('./src/app');

// ==================== 启动 Python imagemgr 服务 ====================
let imagemgrProcess = null;

function startImagemgr() {
  const imagemgrPath = path.resolve(__dirname, '../imagemgr/src');
  const logPath = path.resolve(__dirname, '../imagemgr/logs');
  
  // 创建日志目录
  require('fs').mkdirSync(logPath, { recursive: true });
  
  console.log('[imagemgr] Starting Python image manager service...');
  
  // 启动 Python 服务
  imagemgrProcess = spawn('python', ['api_server.py'], {
    cwd: imagemgrPath,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env }
  });
  
  imagemgrProcess.stdout.on('data', (data) => {
    console.log(`[imagemgr] ${data.toString().trim()}`);
  });
  
  imagemgrProcess.stderr.on('data', (data) => {
    console.error(`[imagemgr] ${data.toString().trim()}`);
  });
  
  imagemgrProcess.on('close', (code) => {
    console.log(`[imagemgr] Process exited with code ${code}`);
    imagemgrProcess = null;
  });
  
  imagemgrProcess.on('error', (err) => {
    console.error('[imagemgr] Failed to start:', err.message);
  });
}

// ==================== 启动 AI Gateway 服务 ====================
let gatewayProcess = null;

function startGateway() {
  const gatewayPath = path.resolve(__dirname, '../aiserver/gateway');
  const logPath = path.resolve(__dirname, '../logs');

  // 创建日志目录
  require('fs').mkdirSync(logPath, { recursive: true });

  console.log('[gateway] Starting AI Gateway service...');

  // 启动 Python 网关服务
  gatewayProcess = spawn('python', ['ai_gateway.py'], {
    cwd: gatewayPath,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env }
  });

  gatewayProcess.stdout.on('data', (data) => {
    console.log(`[gateway] ${data.toString().trim()}`);
  });

  gatewayProcess.stderr.on('data', (data) => {
    // uvicorn 的普通日志也输出到 stderr，所以用 log 而不是 error
    console.log(`[gateway] ${data.toString().trim()}`);
  });

  gatewayProcess.on('close', (code) => {
    console.log(`[gateway] Process exited with code ${code}`);
    gatewayProcess = null;
  });

  gatewayProcess.on('error', (err) => {
    console.error('[gateway] Failed to start:', err.message);
  });
}

// ==================== 启动知识查询服务 ====================
let knowledgeProcess = null;

function startKnowledge() {
  const knowledgePath = path.resolve(__dirname, '../memory_system');

  console.log('[knowledge] Starting Knowledge Query service...');

  // 启动 Python 知识查询服务
  knowledgeProcess = spawn('python', ['web_service.py'], {
    cwd: knowledgePath,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env }
  });

  knowledgeProcess.stdout.on('data', (data) => {
    console.log(`[knowledge] ${data.toString().trim()}`);
  });

  knowledgeProcess.stderr.on('data', (data) => {
    console.log(`[knowledge] ${data.toString().trim()}`);
  });

  knowledgeProcess.on('close', (code) => {
    console.log(`[knowledge] Process exited with code ${code}`);
    knowledgeProcess = null;
  });

  knowledgeProcess.on('error', (err) => {
    console.error('[knowledge] Failed to start:', err.message);
  });
}

// ==================== 启动 MemGraph 知识图谱服务 ====================
let memgraphProcess = null;

function startMemGraph() {
  const memgraphPath = path.resolve(__dirname, '../MemGraph');

  console.log('[memgraph] Starting MemGraph service...');

  // 启动 Python FastAPI 服务
  memgraphProcess = spawn('python', ['start.py'], {
    cwd: memgraphPath,
    stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env }
  });

  memgraphProcess.stdout.on('data', (data) => {
    console.log(`[memgraph] ${data.toString().trim()}`);
  });

  memgraphProcess.stderr.on('data', (data) => {
    console.log(`[memgraph] ${data.toString().trim()}`);
  });

  memgraphProcess.on('close', (code) => {
    console.log(`[memgraph] Process exited with code ${code}`);
    memgraphProcess = null;
  });

  memgraphProcess.on('error', (err) => {
    console.error('[memgraph] Failed to start:', err.message);
  });
}

// 优雅关闭
function cleanup() {
  if (imagemgrProcess) {
    console.log('[imagemgr] Stopping Python service...');
    imagemgrProcess.kill('SIGTERM');
  }
  if (gatewayProcess) {
    console.log('[gateway] Stopping AI Gateway service...');
    gatewayProcess.kill('SIGTERM');
  }
  if (knowledgeProcess) {
    console.log('[knowledge] Stopping Knowledge Query service...');
    knowledgeProcess.kill('SIGTERM');
  }
  if (memgraphProcess) {
    console.log('[memgraph] Stopping MemGraph service...');
    memgraphProcess.kill('SIGTERM');
  }
}

process.on('SIGINT', () => {
  cleanup();
  process.exit(0);
});

process.on('SIGTERM', () => {
  cleanup();
  process.exit(0);
});

// 启动 Python 服务
startImagemgr();
startKnowledge();
startMemGraph();
// startGateway();  // MemGraph 直接访问 GPU 服务器，不需要 Gateway 中转

// ==================== 启动 Express 服务 ====================
const PORT = process.env.PORT || 3000;
const server = app.listen(PORT, () => {
  /* eslint-disable no-console */
  console.log(`[backend] Listening on http://localhost:${PORT}`);
});

// 设置超时时间为 30 分钟 (1800000 ms)，3D模型生成需要较长时间
server.setTimeout(1800000);
// 同时设置 keep-alive 超时
server.keepAliveTimeout = 1800000;
server.headersTimeout = 1810000; // 需要比 keepAliveTimeout 大一点


