#!/usr/bin/env node

/**
 * 测试数据库版本的 live-gen 端点
 */

const axios = require('axios');
const { randomUUID } = require('crypto');

const API_BASE = 'http://localhost:3000/api/live-gen';

async function testListEndpoint() {
  console.log('\n=== 测试 GET /api/live-gen (列表) ===\n');

  try {
    const response = await axios.get(API_BASE, {
      params: { page: 1, pageSize: 5 }
    });

    console.log(`✅ 获取成功`);
    console.log(`  总记录数: ${response.data.total}`);
    console.log(`  返回条数: ${response.data.items.length}`);

    if (response.data.items.length > 0) {
      const first = response.data.items[0];
      console.log(`  第一条记录:`);
      console.log(`    ID: ${first.id}`);
      console.log(`    提示词: ${first.prompt?.substring(0, 50)}...`);
      console.log(`    模型: ${first.modelId}`);
      console.log(`    创建时间: ${first.createdAt}`);
    }

    return true;
  } catch (error) {
    console.error('❌ 列表端点测试失败:', error.message);
    return false;
  }
}

async function testCreateEndpoint() {
  console.log('\n=== 测试 POST /api/live-gen (创建) ===\n');

  try {
    const testData = {
      prompt: `数据库测试 - ${new Date().toISOString()}`,
      imagePath: '/imagedb/test/test.png',
      imageUrls: ['/imagedb/ref1.png', '/imagedb/ref2.png'],
      modelId: 'test_model_db',
      modelName: 'Test Model DB',
      params: { temperature: 0.8, steps: 50 },
      duration: 1234,
      usage: { completion_tokens: 100, total_tokens: 150 }
    };

    const response = await axios.post(API_BASE, testData);

    console.log(`✅ 创建成功`);
    console.log(`  ID: ${response.data.id}`);
    console.log(`  提示词: ${response.data.prompt}`);
    console.log(`  模型: ${response.data.modelId}`);

    return response.data.id;
  } catch (error) {
    console.error('❌ 创建端点测试失败:', error.message);
    return null;
  }
}

async function testUpdateScoreEndpoint(id) {
  console.log('\n=== 测试 PATCH /api/live-gen/:id/score (更新评分) ===\n');

  if (!id) {
    console.log('⚠️ 跳过：需要先创建记录');
    return false;
  }

  try {
    const scoreData = {
      dimension1: 4.5,
      dimension2: 3.8,
      comment: '数据库版本测试评论'
    };

    const response = await axios.patch(`${API_BASE}/${id}/score`, scoreData);

    console.log(`✅ 更新成功`);
    console.log(`  评分: dimension1=${response.data.dimensionScores.dimension1}, dimension2=${response.data.dimensionScores.dimension2}`);
    console.log(`  评论: ${response.data.comment}`);

    return true;
  } catch (error) {
    console.error('❌ 更新评分端点测试失败:', error.message);
    return false;
  }
}

async function testDeleteEndpoint(id) {
  console.log('\n=== 测试 DELETE /api/live-gen/:id (删除) ===\n');

  if (!id) {
    console.log('⚠️ 跳过：需要先创建记录');
    return false;
  }

  try {
    const response = await axios.delete(`${API_BASE}/${id}`);

    console.log(`✅ 删除成功`);
    console.log(`  响应: ${JSON.stringify(response.data)}`);

    // 验证删除
    const listResponse = await axios.get(API_BASE);
    const found = listResponse.data.items.find(item => item.id === id);

    if (!found) {
      console.log(`  验证: 记录已从数据库删除`);
    } else {
      console.log(`  ⚠️ 记录仍存在于数据库`);
      return false;
    }

    return true;
  } catch (error) {
    console.error('❌ 删除端点测试失败:', error.message);
    return false;
  }
}

async function testSearchEndpoint() {
  console.log('\n=== 测试搜索功能 ===\n');

  try {
    const response = await axios.get(API_BASE, {
      params: { q: '测试', pageSize: 5 }
    });

    console.log(`✅ 搜索成功`);
    console.log(`  搜索词: "测试"`);
    console.log(`  结果数: ${response.data.total}`);

    if (response.data.items.length > 0) {
      console.log(`  前${response.data.items.length}条结果:`);
      response.data.items.forEach((item, i) => {
        console.log(`    ${i + 1}. ${item.prompt?.substring(0, 40)}...`);
      });
    }

    return true;
  } catch (error) {
    console.error('❌ 搜索测试失败:', error.message);
    return false;
  }
}

async function testModelFilterEndpoint() {
  console.log('\n=== 测试模型过滤 ===\n');

  try {
    const response = await axios.get(API_BASE, {
      params: { modelId: 'comfyui_flux', pageSize: 5 }
    });

    console.log(`✅ 模型过滤成功`);
    console.log(`  模型ID: comfyui_flux`);
    console.log(`  结果数: ${response.data.total}`);

    return true;
  } catch (error) {
    console.error('❌ 模型过滤测试失败:', error.message);
    return false;
  }
}

async function main() {
  console.log('\n' + '='.repeat(60));
  console.log('        数据库版 live-gen 端点测试');
  console.log('='.repeat(60));

  let passed = 0;
  let failed = 0;

  // 测试列表
  if (await testListEndpoint()) passed++; else failed++;

  // 测试创建
  const createdId = await testCreateEndpoint();
  if (createdId) passed++; else failed++;

  // 测试更新评分
  if (await testUpdateScoreEndpoint(createdId)) passed++; else failed++;

  // 测试搜索
  if (await testSearchEndpoint()) passed++; else failed++;

  // 测试模型过滤
  if (await testModelFilterEndpoint()) passed++; else failed++;

  // 测试删除（最后执行）
  if (await testDeleteEndpoint(createdId)) passed++; else failed++;

  console.log('\n' + '='.repeat(60));
  console.log(`测试完成: ${passed} 通过, ${failed} 失败`);
  console.log('='.repeat(60) + '\n');

  if (failed === 0) {
    console.log('✅ 所有测试通过！数据库版 live-gen 端点工作正常。');
    console.log('\n下一步:');
    console.log('1. 确认所有功能正常后，可以删除旧的 live-gen.js');
    console.log('2. 删除或归档 data/live-gen.json 文件');
    console.log('3. 所有数据现在都存储在 SQLite 数据库中');
  } else {
    console.log('❌ 有测试失败，请检查错误信息。');
  }

  process.exit(failed === 0 ? 0 : 1);
}

if (require.main === module) {
  main().catch(console.error);
}