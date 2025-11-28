'use strict';

/**
 * DashScope (Aliyun) Driver
 * Supports Wanx (Tongyi Wanxiang) for image generation.
 * 
 * Note: Wanx API is typically asynchronous (Task Submission -> Polling).
 */

const POLL_INTERVAL = 1000; // 1 second
const MAX_POLL_TIME = 60 * 1000; // 60 seconds timeout

async function generate({ apiKey, model, prompt, images, config }) {
  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = 'Set DASHSCOPE_API_KEY in environment';
    throw err;
  }

  // Wanx (Text to Image)
  // Docs: https://help.aliyun.com/zh/model-studio/developer-reference/wanx-v1-generic-text-to-image
  // API Endpoint: https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis
  
  const isWanx = model.toLowerCase().includes('wanx');
  
  if (isWanx) {
    return await generateWanx({ apiKey, model, prompt, images, config });
  }

  throw new Error(`dashscope driver: model "${model}" not supported for image generation (only wanx supported currently)`);
}

async function generateWanx({ apiKey, model, prompt, images, config }) {
  // 1. Submit Task
  const url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis';
  
  const headers = {
    'Authorization': `Bearer ${apiKey}`,
    'X-DashScope-Async': 'enable',
    'Content-Type': 'application/json'
  };

  // Wanx supports ref_img? Check docs. For now, basic text2image.
  // prompt is required.
  const body = {
    model: model || 'wanx-v1',
    input: {
      prompt: prompt
    },
    parameters: {
      style: config?.style || '<auto>',
      size: config?.size || '1024*1024',
      n: 1
    }
  };
  
  // If there are input images (e.g. image-to-image or reference), Wanx might support it depending on model version.
  // wanx-v1 supports ref_img for style/structure? 
  // Simplification: ignoring input images for text-to-image unless config specifies specialized handling.

  const submitResp = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body)
  });

  if (!submitResp.ok) {
    const txt = await submitResp.text();
    throw new Error(`Wanx submit failed: ${submitResp.status} ${txt}`);
  }

  const submitData = await submitResp.json();
  if (submitData.code) { // Error code present
    throw new Error(`Wanx submit error: ${submitData.code} - ${submitData.message}`);
  }

  const taskId = submitData.output.task_id;
  // console.log('[dashscope] task submitted:', taskId);

  // 2. Poll Task Status
  const taskUrl = `https://dashscope.aliyuncs.com/api/v1/tasks/${taskId}`;
  const startTime = Date.now();

  while (Date.now() - startTime < MAX_POLL_TIME) {
    await new Promise(r => setTimeout(r, POLL_INTERVAL));
    
    const taskResp = await fetch(taskUrl, { headers: { 'Authorization': `Bearer ${apiKey}` } });
    if (!taskResp.ok) {
      throw new Error(`Wanx poll failed: ${taskResp.status}`);
    }
    
    const taskData = await taskResp.json();
    const status = taskData.output.task_status;

    if (status === 'SUCCEEDED') {
      // Download the image
      const resultUrl = taskData.output.results[0].url;
      // console.log('[dashscope] task succeeded, downloading:', resultUrl);
      
      const imgResp = await fetch(resultUrl);
      const arrayBuffer = await imgResp.arrayBuffer();
      const buffer = Buffer.from(arrayBuffer);
      const base64 = buffer.toString('base64');
      
      return {
        dataBase64: base64,
        mimeType: 'image/png' // Wanx usually returns png or jpg
      };
    } else if (status === 'FAILED' || status === 'CANCELED') {
        throw new Error(`Wanx task failed: ${status} - ${taskData.output.message || ''}`);
    }
    // PENDING or RUNNING, continue
  }

  throw new Error('Wanx task timed out');
}

module.exports = { generate };

