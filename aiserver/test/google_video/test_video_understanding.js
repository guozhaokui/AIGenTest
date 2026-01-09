const fs = require('fs');
const path = require('path');

// 手动读取 .env 文件
const envPath = path.join(__dirname, '../../../.env');
console.log('正在读取 .env 文件:', envPath);

if (!fs.existsSync(envPath)) {
  console.error('.env 文件不存在:', envPath);
  process.exit(1);
}

const envContent = fs.readFileSync(envPath, 'utf-8');
const loadedKeys = [];
envContent.split('\n').forEach(line => {
  const trimmedLine = line.trim();
  if (!trimmedLine || trimmedLine.startsWith('#')) return;

  const match = trimmedLine.match(/^([^=]+)=(.*)$/);
  if (match) {
    const key = match[1].trim();
    const value = match[2].trim();
    if (key) {
      process.env[key] = value;
      loadedKeys.push(key);
    }
  }
});

console.log('环境变量已加载，共加载', loadedKeys.length, '个变量');
console.log('加载的键:', loadedKeys.join(', '));

const { GoogleGenAI } = require('@google/genai');

async function testVideoUnderstanding() {
  const apiKey = process.env.GOOGLE_API_KEY;

  if (!apiKey) {
    console.error('错误: 未找到 GOOGLE_API_KEY');
    return;
  }

  console.log('API Key:', apiKey.substring(0, 10) + '...');

  const ai = new GoogleGenAI({ apiKey });

  // 测试用例1: 使用 YouTube 视频链接
  console.log('\n========== 测试 YouTube 视频理解 ==========');
  try {
    const videoUrl = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'; // 示例视频

    const response = await ai.models.generateContent({
      model: 'gemini-2.0-flash-exp',
      contents: [{
        role: 'user',
        parts: [
          {
            fileData: {
              fileUri: videoUrl
            }
          },
          {
            text: '请描述这个视频的主要内容，包括视觉元素和音频信息。'
          }
        ]
      }]
    });

    console.log('响应:', JSON.stringify(response, null, 2));

    if (response?.candidates?.[0]?.content?.parts?.[0]?.text) {
      console.log('\n视频理解结果:\n', response.candidates[0].content.parts[0].text);
    }

    if (response?.usageMetadata) {
      console.log('\nToken 使用情况:', response.usageMetadata);
    }

  } catch (error) {
    console.error('YouTube 视频测试失败:', error.message);
    if (error.response) {
      console.error('错误详情:', JSON.stringify(error.response, null, 2));
    }
  }

  // 测试用例2: 使用 File API 上传本地视频
  console.log('\n========== 测试本地视频上传 ==========');
  console.log('(需要先上传视频文件，此处仅展示代码结构)');

  try {
    // 注意: 实际使用时需要先通过 File API 上传视频
    // const file = await ai.files.upload({
    //   file: fs.createReadStream('./sample.mp4'),
    //   mimeType: 'video/mp4'
    // });
    //
    // console.log('视频上传成功:', file.uri);
    //
    // const response = await ai.models.generateContent({
    //   model: 'gemini-2.0-flash-exp',
    //   contents: [{
    //     role: 'user',
    //     parts: [
    //       { fileData: { fileUri: file.uri } },
    //       { text: '请分析这个视频的内容' }
    //     ]
    //   }]
    // });

    console.log('本地视频上传功能需要准备测试视频文件');

  } catch (error) {
    console.error('本地视频测试失败:', error.message);
  }
}

// 运行测试
testVideoUnderstanding().catch(console.error);
