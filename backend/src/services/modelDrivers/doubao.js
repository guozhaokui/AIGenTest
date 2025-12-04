'use strict';

/**
 * Doubao (ByteDance/Volcengine) Driver
 * API for Doubao Seedream (image generation)
 */

async function generate({ apiKey, model, prompt, images, config }) {
  if (!apiKey) {
    const err = new Error('missing_api_key');
    err.code = 'MISSING_API_KEY';
    err.message = 'Set ARK_API_KEY in environment';
    throw err;
  }

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
    // Use the first image for generation
    // The Python example uses base64 data URI: "data:image/png;base64,..."
    // backend/src/routes/generate.js provides images as { dataBase64, mimeType }
    const img = images[0];
    const base64Image = `data:${img.mimeType};base64,${img.dataBase64}`;
    payload.image = base64Image;
    
    // Log that we are using base64 image
    // console.log('[doubao] using base64 image input, length:', base64Image.length);
  }

  // console.log('[doubao] request:', apiUrl, payload);

  // Handle proxy: if config.useProxy is explicitly false, or env vars not set, use default fetch.
  // But `undici` global dispatcher handles proxy automatically if set in app.js.
  // To BYPASS proxy for a specific request in undici, we might need a custom dispatcher.
  let dispatcher = undefined;
  if (config.useProxy === false || config.useProxy === 'false') {
     // Create a fresh Agent/Dispatcher that ignores global proxy settings if possible,
     // or just use default undici Agent which usually doesn't pick up env vars unless global dispatcher is set.
     // If global dispatcher IS set to ProxyAgent, we need to pass a new Agent() to bypass it.
     try {
       const { Agent } = require('undici');
       dispatcher = new Agent(); 
     } catch (e) {
       // ignore if undici not available (though it is a dependency)
     }
  }

  try {
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify(payload),
      dispatcher // Pass dispatcher option (works with Node's fetch if backed by undici, or undici.fetch)
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Doubao API failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    const result = await response.json();
    
    // Extract image URL from response
    // Response format: { data: [ { url: '...' } ], ... }
    const imageUrl = result.data?.[0]?.url;
    
    if (!imageUrl) {
      throw new Error('Doubao API returned no image URL');
    }

    // Download image
    const imgResp = await fetch(imageUrl, { dispatcher });
    if (!imgResp.ok) {
      throw new Error(`Failed to download image from Doubao URL: ${imgResp.status}`);
    }

    const arrayBuffer = await imgResp.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const base64 = buffer.toString('base64');
    const contentType = imgResp.headers.get('content-type') || 'image/jpeg'; // Doubao usually returns jpeg or png

    return {
      dataBase64: base64,
      mimeType: contentType
    };

  } catch (error) {
    throw new Error(`doubao driver error: ${error.message}`);
  }
}

module.exports = { generate };

