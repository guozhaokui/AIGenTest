const fs = require('fs');
const path = require('path');

// 手动读取 .env 文件
const envPath = path.join(__dirname, '../../../.env');
const envContent = fs.readFileSync(envPath, 'utf-8');
envContent.split('\n').forEach(line => {
  const trimmedLine = line.trim();
  if (!trimmedLine || trimmedLine.startsWith('#')) return;
  const match = trimmedLine.match(/^([^=]+)=(.*)$/);
  if (match) {
    const key = match[1].trim();
    const value = match[2].trim();
    if (key) process.env[key] = value;
  }
});

const { GoogleGenAI } = require('@google/genai');

async function testSimpleAPI() {
  const apiKey = process.env.GOOGLE_API_KEY;
  console.log('测试 API Key:', apiKey.substring(0, 10) + '...');

  const ai = new GoogleGenAI({ apiKey });

  try {
    console.log('\n========== 测试简单文本生成 ==========');
    const response = await ai.models.generateContent({
      model: 'gemini-2.0-flash-exp',
      contents: [{
        role: 'user',
        parts: [{ text: 'Say hello in 5 different languages.' }]
      }]
    });

    console.log('响应成功!');
    if (response?.candidates?.[0]?.content?.parts?.[0]?.text) {
      console.log('生成内容:\n', response.candidates[0].content.parts[0].text);
    }

    if (response?.usageMetadata) {
      console.log('\nToken 使用:', response.usageMetadata);
    }

  } catch (error) {
    console.error('测试失败:', error.message);
    console.error('错误栈:', error.stack);
  }
}

testSimpleAPI().catch(console.error);
