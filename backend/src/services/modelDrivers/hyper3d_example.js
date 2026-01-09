#!/usr/bin/env node
/**
 * Hyper3D API 示例脚本
 * 
 * 功能：从文本生成带纹理的 3D 模型 (GLB 格式)
 * 
 * 使用方法：
 *   node hyper3d_example.js "一只可爱的猫咪"
 *   node hyper3d_example.js "一个红色的机器人"
 * 
 * 环境变量：
 *   HYPER3D_API_KEY - 你的 Hyper3D API 密钥
 * 
 * API 文档: https://developer.hyper3d.ai/zh_cn/get-started/minimal-example
 */

require('dotenv').config({ path: require('path').resolve(__dirname, '../../../../.env') });

const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');

// API 配置
const API_BASE = 'https://api.hyper3d.com/api/v2';
const API_KEY = process.env.HYPER3D_API_KEY;

// 默认参数
const DEFAULT_CONFIG = {
  tier: 'Gen-2',           // 生成等级: Gen-2 (高质量) 或 Regular (Gen-1.5)
  meshMode: 'Raw',         // 网格模式: Raw 或 Quad
  material: 'PBR',         // 材质: PBR 或 Unlit
  qualityOverride: 500000  // 面数
};

/**
 * 提交生成任务
 */
async function submitTask(prompt, config = {}) {
  const url = `${API_BASE}/rodin`;
  const mergedConfig = { ...DEFAULT_CONFIG, ...config };
  
  const formData = new FormData();
  formData.append('prompt', prompt);
  formData.append('tier', mergedConfig.tier);
  formData.append('mesh_mode', mergedConfig.meshMode);
  formData.append('quality_override', String(mergedConfig.qualityOverride));
  formData.append('material', mergedConfig.material);
  
  console.log(`\n📤 提交任务...`);
  console.log(`   提示词: "${prompt}"`);
  console.log(`   参数: tier=${mergedConfig.tier}, mesh_mode=${mergedConfig.meshMode}, material=${mergedConfig.material}, quality=${mergedConfig.qualityOverride}`);
  
  const https = require('https');
  const response = await axios.post(url, formData, {
    headers: {
      ...formData.getHeaders(),
      'Authorization': `Bearer ${API_KEY}`
    },
    maxBodyLength: Infinity,
    proxy: false,
    httpsAgent: new https.Agent({ rejectUnauthorized: true })
  });
  
  return response.data;
}

/**
 * 检查任务状态
 */
async function checkStatus(subscriptionKey) {
  const url = `${API_BASE}/status`;
  const https = require('https');
  
  const response = await axios.post(url, {
    subscription_key: subscriptionKey
  }, {
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    },
    proxy: false,
    httpsAgent: new https.Agent({ rejectUnauthorized: true })
  });
  
  return response.data;
}

/**
 * 轮询任务直到完成
 */
async function pollUntilDone(subscriptionKey) {
  const maxAttempts = 180;
  const intervalMs = 5000;
  
  console.log(`\n⏳ 等待生成完成...`);
  
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    const statusResponse = await checkStatus(subscriptionKey);
    const jobs = statusResponse.jobs || [];
    
    if (jobs.length === 0) {
      process.stdout.write(`\r   轮询 ${attempt}/${maxAttempts}: 等待任务启动...`);
      await sleep(intervalMs);
      continue;
    }
    
    // 显示所有任务状态
    const statusStr = jobs.map(j => `${j.status}`).join(', ');
    process.stdout.write(`\r   轮询 ${attempt}/${maxAttempts}: ${statusStr}                    `);
    
    // 检查是否全部完成
    const allDone = jobs.every(j => j.status === 'Done' || j.status === 'Failed');
    
    if (allDone) {
      console.log(''); // 换行
      
      const failed = jobs.find(j => j.status === 'Failed');
      if (failed) {
        throw new Error(`任务失败: ${failed.message || 'Unknown error'}`);
      }
      
      console.log(`✅ 所有任务完成!`);
      return jobs;
    }
    
    await sleep(intervalMs);
  }
  
  throw new Error('任务超时');
}

/**
 * 下载结果
 */
async function downloadResults(taskUuid) {
  const url = `${API_BASE}/download`;
  const https = require('https');
  
  const response = await axios.post(url, {
    task_uuid: taskUuid
  }, {
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'Content-Type': 'application/json'
    },
    proxy: false,
    httpsAgent: new https.Agent({ rejectUnauthorized: true })
  });
  
  return response.data;
}

/**
 * 下载文件并保存
 */
async function downloadAndSave(fileUrl, outputPath) {
  console.log(`\n📥 下载模型...`);
  
  const response = await axios.get(fileUrl, {
    responseType: 'arraybuffer',
    timeout: 300000,
    proxy: false
  });
  
  const buffer = Buffer.from(response.data);
  fs.writeFileSync(outputPath, buffer);
  
  console.log(`✅ 已保存到: ${outputPath}`);
  console.log(`   文件大小: ${(buffer.length / 1024 / 1024).toFixed(2)} MB`);
  
  return outputPath;
}

/**
 * 辅助函数：延迟
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * 主函数
 */
async function main() {
  // 获取命令行参数
  const prompt = process.argv[2];
  
  if (!prompt) {
    console.log(`
╔════════════════════════════════════════════════════════════╗
║           Hyper3D 文本转3D 示例                              ║
╚════════════════════════════════════════════════════════════╝

使用方法:
  node hyper3d_example.js "提示词"

示例:
  node hyper3d_example.js "一只可爱的卡通猫咪"
  node hyper3d_example.js "一个红色的机器人战士"
  node hyper3d_example.js "一把中世纪骑士剑"

环境变量:
  HYPER3D_API_KEY - 你的 API 密钥 (已从 .env 读取)
`);
    process.exit(1);
  }
  
  if (!API_KEY) {
    console.error('❌ 错误: 未设置 HYPER3D_API_KEY 环境变量');
    console.error('   请在项目根目录的 .env 文件中添加: HYPER3D_API_KEY=你的密钥');
    process.exit(1);
  }
  
  console.log(`
╔════════════════════════════════════════════════════════════╗
║           Hyper3D 文本转3D                                   ║
╚════════════════════════════════════════════════════════════╝
`);
  console.log(`🔑 API Key: ${API_KEY.slice(0, 8)}...${API_KEY.slice(-4)}`);
  
  try {
    // 1. 提交任务
    const taskResponse = await submitTask(prompt);
    const taskUuid = taskResponse.uuid;
    const subscriptionKey = taskResponse.jobs?.subscription_key;
    
    console.log(`\n📋 任务信息:`);
    console.log(`   UUID: ${taskUuid}`);
    console.log(`   Subscription Key: ${subscriptionKey}`);
    
    if (!taskUuid || !subscriptionKey) {
      throw new Error('任务提交失败: 未返回必要信息');
    }
    
    // 2. 轮询状态
    await pollUntilDone(subscriptionKey);
    
    // 3. 获取下载链接
    console.log(`\n📦 获取下载链接...`);
    const downloadResponse = await downloadResults(taskUuid);
    const files = downloadResponse.list || [];
    
    console.log(`   可用文件: ${files.map(f => f.name).join(', ')}`);
    
    if (files.length === 0) {
      throw new Error('未返回任何文件');
    }
    
    // 4. 下载 GLB 文件
    const glbFile = files.find(f => f.name.endsWith('.glb')) || files[0];
    const outputDir = path.resolve(__dirname, '../../../../output');
    
    // 确保输出目录存在
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const outputPath = path.join(outputDir, `hyper3d_${timestamp}_${glbFile.name}`);
    
    await downloadAndSave(glbFile.url, outputPath);
    
    console.log(`
╔════════════════════════════════════════════════════════════╗
║           🎉 生成完成!                                       ║
╚════════════════════════════════════════════════════════════╝
`);
    
  } catch (error) {
    console.error(`\n❌ 错误: ${error.message}`);
    if (error.response) {
      console.error(`   HTTP ${error.response.status}:`, error.response.data);
    }
    process.exit(1);
  }
}

// 运行
main();

