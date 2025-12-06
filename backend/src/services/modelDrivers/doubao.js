'use strict';

/**
 * Doubao (ByteDance/Volcengine) Driver
 * API for Doubao Seedream (image generation) and Seed3D (3D generation)
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
async function downloadContent(url, dispatcher) {
  const resp = await fetch(url, { dispatcher });
  if (!resp.ok) {
    throw new Error(`Failed to download from URL: ${resp.status}`);
  }
  const arrayBuffer = await resp.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);
  const contentType = resp.headers.get('content-type');
  return { buffer, contentType };
}

// Helper function to handle zip extraction
async function extractZip(buffer, outputDir) {
  const fs = require('fs/promises');
  const path = require('path');
  
  // Create output directory
  await fs.mkdir(outputDir, { recursive: true });
  
  // Check if we have adm-zip available (recommended) or use built-in modules
  let admZip;
  try {
    admZip = require('adm-zip');
    
    // Use adm-zip to extract
    const zip = new admZip(buffer);
    zip.extractAllTo(outputDir, true);
    console.log(`[doubao-3d] Extracted zip to ${outputDir}`);
    
    // Return list of extracted files
    return zip.getEntries().map(entry => entry.entryName);
  } catch (e) {
    console.log('[doubao-3d] adm-zip not available, trying built-in modules...');
    
    // Fallback: use built-in zlib and tar if it's a gzip tarball
    // Note: This won't work for regular zip files, only .tar.gz
    throw new Error(`Need adm-zip module for zip extraction. Please run: npm install adm-zip`);
  }
}

// Helper function for 3D generation polling
async function poll3DTask(taskId, apiKey, dispatcher) {
  const pollUrl = `https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks/${taskId}`;
  const maxAttempts = 60; // 60 attempts
  const intervalMs = 10000; // 10 seconds

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(pollUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      dispatcher
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Doubao API failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    const status = result.status;
    
    console.log(`[doubao-3d] Polling attempt ${attempt + 1}/${maxAttempts}, status: ${status}`);

    if (status === 'succeeded') {
      return result;
    } else if (status === 'failed') {
      throw new Error(`3D generation failed: ${result.error || 'Unknown error'}`);
    } else if (status === 'canceled') {
      throw new Error('3D generation was canceled');
    }

    // Wait before next attempt
    await new Promise(resolve => setTimeout(resolve, intervalMs));
  }

  throw new Error('3D generation timed out after maximum attempts');
}

async function generate({ apiKey, model, prompt, images, config }) {
  // Test mode: if config contains testUrl, use it instead of actual API
  if (config.testUrl) {
    console.log('[doubao] ===== TEST MODE ENABLED =====');
    console.log('[doubao] Using test URL:', config.testUrl);
    return test3DGeneration(config.testUrl, config);
  }

  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = 'Set ARK_API_KEY in environment';
    throw err;
  }

  const dispatcher = getDispatcher(config);
  
  // Check if it's a 3D model
  if (model && model.startsWith('doubao-seed3d')) {
    // 3D generation
    return generate3D({ apiKey, model, prompt, images, config, dispatcher });
  } else {
    // Image generation (existing functionality)
    return generateImage({ apiKey, model, prompt, images, config, dispatcher });
  }
}

// Test function for 3D generation
async function test3DGeneration(testUrl, config) {
  console.log('[doubao-test] Starting test 3D generation with URL:', testUrl);
  
  // Download the test zip file
  const dispatcher = getDispatcher(config);
  const { buffer, contentType } = await downloadContent(testUrl, dispatcher);
  
  console.log('[doubao-test] Downloaded zip file, size:', buffer.length, 'bytes');
  
  // Return the zip buffer directly for generate.js to handle
  return {
    dataBase64: buffer.toString('base64'),
    mimeType: contentType || 'application/zip'
  };
}

// Existing image generation function
async function generateImage({ apiKey, model, prompt, images, config, dispatcher }) {
  // Default endpoint
  const apiUrl = config.url || 'https://ark.cn-beijing.volces.com/api/v3/images/generations';

  // Construct payload
  const payload = {
    model: model || 'doubao-seedream-4-5-251128',
    prompt: prompt,
    size: config.size || '2K',
    watermark: config.watermark === true || config.watermark === 'true'
  };

  // Handle Image Edit (Image-to-Image)
  if (images && images.length > 0) {
    const img = images[0];
    const base64Image = `data:${img.mimeType};base64,${img.dataBase64}`;
    payload.image = base64Image;
  }

  try {
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
      throw new Error(`Doubao API failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    // 打印完整返回结果，用于查看 token 信息
    console.log('[doubao-image] Complete API response:', JSON.stringify(result, null, 2));
    
    // Extract image URL from response
    const imageUrl = result.data?.[0]?.url;
    
    if (!imageUrl) {
      throw new Error('Doubao API returned no image URL');
    }

    // Download image
    const { buffer, contentType } = await downloadContent(imageUrl, dispatcher);
    const base64 = buffer.toString('base64');
    
    // 提取 usage/token 信息（如果存在）
    const usage = result.usage || null;

    return {
      dataBase64: base64,
      mimeType: contentType || 'image/jpeg',
      usage
    };

  } catch (error) {
    throw new Error(`doubao image driver error: ${error.message}`);
  }
}

// New 3D generation function
async function generate3D({ apiKey, model, prompt, images, config, dispatcher }) {
  // 3D generation endpoint
  const apiUrl = 'https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks';
  
  // Construct 3D generation payload
  const content = [];
  
  // Add 3D generation parameters (this is required)
  const textParams = config.textParams || '--subdivisionlevel medium --fileformat glb';
  content.push({
    type: 'text',
    text: textParams
  });
  
  // Add prompt if provided (but 3D model might not require it)
  if (prompt && prompt.trim()) {
    content.push({
      type: 'text',
      text: prompt
    });
  }
  
  // Add image if provided (image-to-3D) - this is the main input for 3D generation
  if (images && images.length > 0) {
    const img = images[0];
    const base64Image = `data:${img.mimeType};base64,${img.dataBase64}`;
    content.push({
      type: 'image_url',
      image_url: {
        url: base64Image
      }
    });
  }
  
  const payload = {
    model: model || 'doubao-seed3d-1-0-250928',
    content: content
  };
  
  //console.log('[doubao-3d] Request payload:', JSON.stringify(payload, null, 2));

  try {
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
      throw new Error(`Doubao 3D API failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    const taskId = result.id;
    
    if (!taskId) {
      throw new Error('Doubao 3D API returned no task ID');
    }
    
    console.log(`[doubao-3d] Created 3D generation task with ID: ${taskId}`);
    
    // Poll for 3D generation result
    const taskResult = await poll3DTask(taskId, apiKey, dispatcher);
    
    // Log the complete task result for debugging
    console.log('[doubao-3d] Task succeeded, complete result:', JSON.stringify(taskResult, null, 2));
    
    // Extract 3D model URL from result - try different possible field names
    let modelUrl = null;
    
    // Check various possible field names based on API documentation and actual response
    if (taskResult.content) {
      modelUrl = taskResult.content.file_url;
    }
    
    if (!modelUrl) {
      throw new Error(`Doubao 3D API returned no model URL. Available content: ${JSON.stringify(taskResult.content)}`);
    }
    
    console.log(`[doubao-3d] 3D generation succeeded, model URL: ${modelUrl}`);
    
    // Download 3D model
    const { buffer, contentType } = await downloadContent(modelUrl, dispatcher);
    const base64 = buffer.toString('base64');
    
    // 提取 usage/token 信息（如果存在）
    const usage = taskResult.usage || null;
    
    return {
      dataBase64: base64,
      mimeType: contentType || 'model/gltf-binary', // Default to glb mime type
      usage
    };

  } catch (error) {
    throw new Error(`doubao 3D driver error: ${error.message}`);
  }
}

module.exports = { generate };

