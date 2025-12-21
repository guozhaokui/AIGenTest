const fs = require('fs');
const path = require('path');

// Configuration
const API_URL = 'http://localhost:6006/generate';
const OUTPUT_FILE = path.join(__dirname, 'output_node.png');

async function generateImage() {
    const payload = {
        prompt: "a futuristic city with flying cars, cinematic lighting",
        height: 1024,
        width: 1024,
        num_inference_steps: 9,
        guidance_scale: 0.0,
        seed: 42
    };

    console.log(`Sending request to ${API_URL}...`);
    console.log(`Prompt: "${payload.prompt}"`);

    try {
        // Note: 'fetch' is available globally in Node.js v18+
        // For older versions, you might need to install 'node-fetch'
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API Request failed: ${response.status} ${response.statusText} - ${errorText}`);
        }

        // Get the image data as an ArrayBuffer
        const arrayBuffer = await response.arrayBuffer();
        const buffer = Buffer.from(arrayBuffer);

        // Save to file
        fs.writeFileSync(OUTPUT_FILE, buffer);
        console.log(`Success! Image saved to: ${OUTPUT_FILE}`);

    } catch (error) {
        console.error('Error generating image:', error.message);
    }
}

generateImage();

