'use strict';

const { fetch, Agent } = require('undici');

/**
 * Z-Image Driver
 * Custom model driver for "z-image" service.
 * Supports setting URL, port, and generation parameters (height, width, steps, etc.)
 */

const directAgent = new Agent({
  connect: { timeout: 60000 },
  headersTimeout: 300000,
  bodyTimeout: 300000,
});

async function generate({ apiKey, model, prompt, images, config }) {
  // 1. Determine API Endpoint
  // config.url can be full URL "http://localhost:6006/generate"
  // or constructed from defaults.
  let apiUrl = config.url || process.env.Z_IMAGE_URL || 'http://localhost:6006/generate';
  
  // Optional: Handle standalone port config if provided
  if (config.port && !config.url) {
     const host = config.host || 'localhost';
     apiUrl = `http://${host}:${config.port}/generate`;
  }

  // 2. Construct Payload
  // Extract parameters from config (merged from model options and req.body)
  const payload = {
    prompt: prompt,
    height: parseInt(config.height) || 1024,
    width: parseInt(config.width) || 1024,
    num_inference_steps: parseInt(config.num_inference_steps) || parseInt(config.steps) || 20,
    guidance_scale: config.guidance_scale !== undefined ? parseFloat(config.guidance_scale) : 7.5,
    seed: config.seed !== undefined ? parseInt(config.seed) : 42
  };

  // eslint-disable-next-line no-console
  console.log(`[z_image] sending request to ${apiUrl}`, payload);

  // 3. Call Service
  try {
    // Check proxy configuration
    const useProxy = config.useProxy === true || config.useProxy === 'true';
    
    const fetchOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        // Add API Key if your service needs it, though the example didn't use one.
        ...(apiKey ? { 'Authorization': `Bearer ${apiKey}` } : {})
      },
      body: JSON.stringify(payload)
    };

    // Use direct agent to bypass proxy if useProxy is not explicitly enabled
    if (!useProxy) {
      fetchOptions.dispatcher = directAgent;
    }

    const response = await fetch(apiUrl, fetchOptions);

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`z_image API failed: ${response.status} ${response.statusText} - ${errorText}`);
    }

    // 4. Process Response
    // The example code returns raw binary image data (Buffer)
    const arrayBuffer = await response.arrayBuffer();
    const buffer = Buffer.from(arrayBuffer);
    const base64 = buffer.toString('base64');

    // Detect mime-type from response headers or default
    const contentType = response.headers.get('content-type') || 'image/png';

    return {
      dataBase64: base64,
      mimeType: contentType
    };

  } catch (error) {
    throw new Error(`z_image driver error: ${error.message}`);
  }
}

module.exports = { generate };


