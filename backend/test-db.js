#!/usr/bin/env node

/**
 * 测试数据库功能
 */

const database = require('./src/services/database');
const taskArchiver = require('./src/services/taskArchiver');
const taskManager = require('./src/services/taskManager');
const taskExecutor = require('./src/services/taskExecutor');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testDatabase() {
  console.log('\n=== 测试数据库连接 ===\n');

  try {
    await database.init();
    const info = database.getDatabaseInfo();

    console.log('数据库信息:');
    console.log(`  路径: ${info.path}`);
    console.log(`  大小: ${(info.size / 1024 / 1024).toFixed(2)} MB`);
    console.log(`  生成记录: ${info.generations} 条`);
    console.log(`  归档任务: ${info.archivedTasks} 条`);
    console.log('✅ 数据库连接成功\n');
  } catch (error) {
    console.error('❌ 数据库连接失败:', error);
    return false;
  }

  return true;
}

async function testGenerations() {
  console.log('=== 测试生成记录查询 ===\n');

  try {
    // 获取最近10条生成记录
    const generations = await database.getGenerations(10);
    console.log(`找到 ${generations.length} 条生成记录:`);

    generations.slice(0, 3).forEach(gen => {
      console.log(`  - [${gen.type}] ${gen.prompt?.substring(0, 50)}...`);
    });

    // 获取统计
    const stats = await database.getStats();
    console.log('\n生成统计:');
    console.log(`  总计: ${stats.total}`);
    console.log(`  图片: ${stats.images}`);
    console.log(`  3D模型: ${stats.models_3d}`);
    console.log(`  视频: ${stats.videos}`);
    console.log(`  音频: ${stats.audios}`);

    console.log('✅ 生成记录查询成功\n');
  } catch (error) {
    console.error('❌ 生成记录查询失败:', error);
    return false;
  }

  return true;
}

async function testTaskArchiving() {
  console.log('=== 测试任务归档到数据库 ===\n');

  try {
    // 设置归档延迟为1秒（便于测试）
    taskArchiver.setArchiveDelay(1000);

    // 创建测试任务
    console.log('创建测试任务...');
    const task = await taskManager.createTask({
      type: 'test',
      driverId: 'database_test',
      modelId: 'test_model',
      prompt: '数据库归档测试 - ' + new Date().toISOString(),
      params: { test: true }
    });

    console.log(`  任务ID: ${task.id}`);

    // 模拟任务完成
    console.log('模拟任务执行...');
    await taskExecutor.simulateTask(task.id, 2000);

    // 等待任务完成和归档
    console.log('等待任务完成和归档...');
    await sleep(3500);

    // 检查任务是否已归档到数据库
    const archives = await database.getArchivedTasks(10);
    const archivedTask = archives.find(t => t.id === task.id);

    if (archivedTask) {
      console.log('✅ 任务成功归档到数据库');
      console.log(`  归档时间: ${archivedTask.archived_at}`);
      console.log(`  状态: ${archivedTask.status}`);
    } else {
      console.log('❌ 任务未找到在归档中');
      return false;
    }

    // 检查生成记录
    const generations = await database.getGenerations(10);
    const generation = generations.find(g => g.id === task.id);

    if (generation) {
      console.log('✅ 生成记录已保存到数据库');
      console.log(`  类型: ${generation.type}`);
      console.log(`  提示: ${generation.prompt}`);
    } else {
      console.log('⚠️ 生成记录未找到（可能因为是测试任务）');
    }

    console.log('\n✅ 任务归档测试成功\n');
  } catch (error) {
    console.error('❌ 任务归档测试失败:', error);
    return false;
  }

  return true;
}

async function testAPIEndpoints() {
  console.log('=== 测试 API 端点 ===\n');

  const axios = require('axios');
  const API_BASE = 'http://localhost:3000/api';

  try {
    // 测试生成记录 API
    console.log('测试 /api/generations ...');
    const genResponse = await axios.get(`${API_BASE}/generations?limit=5`);
    console.log(`  返回 ${genResponse.data.length} 条记录`);

    // 测试统计 API
    console.log('测试 /api/generations/stats ...');
    const statsResponse = await axios.get(`${API_BASE}/generations/stats`);
    console.log(`  总生成数: ${statsResponse.data.total}`);

    // 测试数据库信息 API
    console.log('测试 /api/generations/info ...');
    const infoResponse = await axios.get(`${API_BASE}/generations/info`);
    console.log(`  数据库大小: ${(infoResponse.data.size / 1024 / 1024).toFixed(2)} MB`);

    console.log('✅ API 端点测试成功\n');
  } catch (error) {
    console.error('❌ API 端点测试失败:', error.message);
    console.log('请确保后端服务器正在运行\n');
    return false;
  }

  return true;
}

async function main() {
  console.log('\n' + '='.repeat(60));
  console.log('        数据库功能测试');
  console.log('='.repeat(60));

  const tests = [
    { name: '数据库连接', fn: testDatabase },
    { name: '生成记录查询', fn: testGenerations },
    { name: '任务归档', fn: testTaskArchiving },
    { name: 'API 端点', fn: testAPIEndpoints }
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    const result = await test.fn();
    if (result) {
      passed++;
    } else {
      failed++;
    }
  }

  console.log('='.repeat(60));
  console.log(`测试完成: ${passed} 通过, ${failed} 失败`);
  console.log('='.repeat(60) + '\n');

  if (failed === 0) {
    console.log('✅ 所有测试通过！数据库功能正常。');
    console.log('\n下一步:');
    console.log('1. 验证所有功能是否正常工作');
    console.log('2. 可以安全删除或归档 live-gen.json 和 tasks-archive.json');
    console.log('3. 数据现在存储在 data/aigc.db SQLite 数据库中\n');
  } else {
    console.log('❌ 有测试失败，请检查错误信息。\n');
  }

  // 关闭数据库连接
  database.close();
  process.exit(failed === 0 ? 0 : 1);
}

if (require.main === module) {
  main().catch(console.error);
}