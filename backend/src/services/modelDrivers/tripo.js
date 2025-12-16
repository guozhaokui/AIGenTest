'use strict';

/**
 * Tripo3D Driver
 * API for Tripo3D image-to-3D generation
 * 文档: https://platform.tripo3d.ai/docs/quick-start
 */

// Helper function to handle proxy settings
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

// Helper function to download content from URL
async function downloadContent(url, dispatcher, apiKey) {
  const headers = {};
  // Tripo download URLs may require auth
  if (apiKey) {
    headers['Authorization'] = `Bearer ${apiKey}`;
  }
  
  const resp = await fetch(url, { 
    dispatcher,
    headers 
  });
  if (!resp.ok) {
    throw new Error(`Failed to download from URL: ${resp.status}`);
  }
  const arrayBuffer = await resp.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const contentType = resp.headers.get('content-type');
  return { buffer, contentType };
}

// Helper function for polling task status
async function pollTask(taskId, apiKey, dispatcher) {
  const pollUrl = `https://api.tripo3d.ai/v2/openapi/task/${taskId}`;
  const maxAttempts = 120; // 120 attempts (20 minutes with 10s interval)
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
      throw new Error(`Tripo API poll failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    // Tripo API response format: { code: 0, data: { status: 'success'|'running'|'failed', ... } }
    if (result.code !== 0) {
      throw new Error(`Tripo API error: ${result.message || JSON.stringify(result)}`);
    }
    
    const status = result.data?.status;
    const progress = result.data?.progress || 0;
    
    console.log(`[tripo-3d] Polling attempt ${attempt + 1}/${maxAttempts}, status: ${status}, progress: ${progress}%`);

    if (status === 'success') {
      return result.data;
    } else if (status === 'failed') {
      throw new Error(`3D generation failed: ${result.data?.error || 'Unknown error'}`);
    } else if (status === 'cancelled') {
      throw new Error('3D generation was cancelled');
    }

    // Wait before next attempt
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('3D generation timed out after maximum attempts');
}

// Upload image and get file token
async function uploadImage(imageBase64, mimeType, apiKey, dispatcher) {
  const uploadUrl = 'https://api.tripo3d.ai/v2/openapi/upload';
  
  // Convert base64 to binary buffer
  const buffer = Buffer.from(imageBase64, 'base64');
  
  // Determine file extension from mime type
  const extMap = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp'
  };
  const ext = extMap[mimeType] || 'png';
  const filename = `image.${ext}`;
  
  // Create FormData using the form-data package
  const FormData = require('form-data');
  const formData = new FormData();
  formData.append('file', buffer, {
    filename: filename,
    contentType: mimeType
  });
  
  // Use node-fetch style with form-data
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
    throw new Error(`Tripo upload failed: ${response.status} ${response.statusText} - ${errorText}`);
  }

  const result = await response.json();
  
  if (result.code !== 0) {
    throw new Error(`Tripo upload error: ${result.message || JSON.stringify(result)}`);
  }
  
  console.log('[tripo-3d] Image uploaded, token:', result.data?.image_token);
  return result.data?.image_token;
}

async function generate({ apiKey, model, prompt, images, config }) {
  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = 'Set TRIPO_API_KEY in environment';
    throw err;
  }

  const dispatcher = getDispatcher(config);
  
  // 3D generation
  return generate3D({ apiKey, model, prompt, images, config, dispatcher });
}

// 3D generation function
async function generate3D({ apiKey, model, prompt, images, config, dispatcher }) {
  const apiUrl = 'https://api.tripo3d.ai/v2/openapi/task';
  
  const hasImage = images && images.length > 0;
  const hasPrompt = prompt && prompt.trim();
  
  // 需要至少有图片或提示词
  if (!hasImage && !hasPrompt) {
    throw new Error('Tripo 3D generation requires an input image or prompt');
  }
  
  let payload = {};
  
  if (hasImage) {
    // Check if multiple images provided (multiview mode - Tripo 3.0 feature)
    if (images.length > 1) {
      // Multiview to 3D mode (Tripo 3.0)
      console.log(`[tripo-3d] Uploading ${images.length} images for multiview mode...`);
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
      // Single image to 3D mode
      const img = images[0];
      
      // Upload image first to get file token
      console.log('[tripo-3d] Uploading image...');
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
    // Text to 3D mode (no image, only prompt)
    payload = {
      type: 'text_to_model',
      prompt: prompt.trim()
    };
  }
  
  // Add optional model version (skip if "default" to use API's latest version)
  if (config.modelVersion && config.modelVersion !== 'default') {
    payload.model_version = config.modelVersion;
  }
  
  // Add optional face limit
  if (config.faceLimit) {
    payload.face_limit = parseInt(config.faceLimit);
  }
  
  // Add texture settings
  if (config.texture !== undefined) {
    payload.texture = config.texture !== false && config.texture !== 'false';
  }
  
  // Add PBR settings
  if (config.pbr !== undefined) {
    payload.pbr = config.pbr === true || config.pbr === 'true';
  }
  
  // Tripo 3.0 new features
  // Add orientation control (auto, align_image, none)
  if (config.orientation) {
    payload.orientation = config.orientation;
  }
  
  // Add style control for text_to_model
  if (payload.type === 'text_to_model' && config.style) {
    payload.style = config.style;
  }
  
  // Add negative prompt for text_to_model
  if (payload.type === 'text_to_model' && config.negativePrompt) {
    payload.negative_prompt = config.negativePrompt;
  }

  console.log('[tripo-3d] Creating task with payload:', JSON.stringify(payload, null, 2));
  console.log('[tripo-3d] Using API Key:', apiKey ? `${apiKey.slice(0, 8)}...${apiKey.slice(-4)}` : 'NOT SET');

  try {
    // First, check account balance (optional debug)
    try {
      const balanceResp = await fetch('https://api.tripo3d.ai/v2/openapi/user/balance', {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${apiKey}` },
        dispatcher
      });
      const balanceData = await balanceResp.json();
      console.log('[tripo-3d] Account balance info:', JSON.stringify(balanceData, null, 2));
    } catch (e) {
      console.log('[tripo-3d] Could not fetch balance:', e.message);
    }

    // Create 3D generation task
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
      throw new Error(`Tripo API failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    if (result.code !== 0) {
      throw new Error(`Tripo API error: ${result.message || JSON.stringify(result)}`);
    }
    
    const taskId = result.data?.task_id;
    
    if (!taskId) {
      throw new Error('Tripo API returned no task ID');
    }
    
    console.log(`[tripo-3d] Created task with ID: ${taskId}`);
    
    // Poll for result
    const taskResult = await pollTask(taskId, apiKey, dispatcher);
    
    // Log the complete task result for debugging
    console.log('[tripo-3d] Task succeeded, complete result:', JSON.stringify(taskResult, null, 2));
    
    // Extract model URL from result
    // Tripo returns: { output: { model: "url_to_glb" } } or { output: { pbr_model: "url" } }
    let modelUrl = null;
    
    if (taskResult.output) {
      // Prefer PBR model if available
      modelUrl = taskResult.output.pbr_model || taskResult.output.model;
    }
    
    if (!modelUrl) {
      throw new Error(`Tripo API returned no model URL. Available output: ${JSON.stringify(taskResult.output)}`);
    }
    
    console.log(`[tripo-3d] 3D generation succeeded, model URL: ${modelUrl}`);
    
    // Download 3D model (Tripo URLs don't need auth header typically)
    console.log('[tripo-3d] Downloading model...');
    const startDownload = Date.now();
    const { buffer, contentType } = await downloadContent(modelUrl, dispatcher, null);
    console.log(`[tripo-3d] Download completed in ${Date.now() - startDownload}ms, size: ${buffer.length} bytes`);
    
    const base64 = buffer.toString('base64');
    
    // Extract usage info if available
    const usage = taskResult.running_left_credits !== undefined ? {
      credits_used: taskResult.running_left_credits,
      total_tokens: taskResult.running_left_credits * 1000 // Approximate token equivalent
    } : null;
    
    return {
      dataBase64: base64,
      mimeType: contentType || 'model/gltf-binary',
      usage
    };

  } catch (error) {
    throw new Error(`Tripo 3D driver error: ${error.message}`);
  }
}

module.exports = { generate };

