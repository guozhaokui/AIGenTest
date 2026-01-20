const axios = require('axios');

const API_BASE = 'http://localhost:3000/api';

async function testCancellation() {
  console.log('=== 测试任务取消功能 ===\n');

  try {
    // 1. 创建一个长时间运行的模拟任务
    console.log('1. 创建一个 20 秒的模拟任务...');
    const createResponse = await axios.post(`${API_BASE}/tasks`, {
      type: 'test',
      driverId: 'simulator',
      modelId: 'test_simulator',
      prompt: '取消测试任务',
      params: { duration: 20000 },
      execute: false
    });

    const task = createResponse.data;
    console.log(`   任务创建成功: ${task.id}`);
    console.log(`   状态: ${task.status}\n`);

    // 2. 启动任务执行
    console.log('2. 开始执行任务...');
    await axios.post(`${API_BASE}/tasks/${task.id}/simulate`, {
      duration: 20000
    });
    console.log('   任务开始执行\n');

    // 3. 等待5秒，让任务运行到一半
    console.log('3. 等待 5 秒，让任务运行一会...');
    await new Promise(resolve => setTimeout(resolve, 5000));

    // 检查进度
    const progressCheck = await axios.get(`${API_BASE}/tasks/${task.id}`);
    console.log(`   当前进度: ${progressCheck.data.progress}%`);
    console.log(`   当前状态: ${progressCheck.data.status}\n`);

    // 4. 取消任务
    console.log('4. 取消任务...');
    const cancelResponse = await axios.post(`${API_BASE}/tasks/${task.id}/cancel`);
    console.log(`   取消请求已发送`);
    console.log(`   返回状态: ${cancelResponse.data.status}\n`);

    // 5. 等待2秒，然后检查任务是否真的停止了
    console.log('5. 等待 2 秒后检查任务状态...');
    await new Promise(resolve => setTimeout(resolve, 2000));

    const finalCheck = await axios.get(`${API_BASE}/tasks/${task.id}`);
    console.log(`   最终状态: ${finalCheck.data.status}`);
    console.log(`   最终进度: ${finalCheck.data.progress}%`);
    console.log(`   错误信息: ${finalCheck.data.error || '无'}\n`);

    // 6. 验证结果
    if (finalCheck.data.status === 'cancelled') {
      console.log('✅ 测试通过！任务成功取消。');

      // 检查进度是否停止更新
      const progress1 = finalCheck.data.progress;
      console.log('\n6. 验证进度是否停止更新...');
      await new Promise(resolve => setTimeout(resolve, 3000));

      const verifyCheck = await axios.get(`${API_BASE}/tasks/${task.id}`);
      const progress2 = verifyCheck.data.progress;

      if (progress1 === progress2) {
        console.log(`   进度保持在 ${progress1}%，没有继续更新`);
        console.log('   ✅ 任务确实已停止执行！');
      } else {
        console.log(`   ⚠️ 进度从 ${progress1}% 变为 ${progress2}%`);
        console.log('   ❌ 任务可能仍在执行！');
      }
    } else {
      console.log(`❌ 测试失败！任务状态为 ${finalCheck.data.status}，而不是 cancelled`);
    }

    // 7. 清理：删除测试任务
    console.log('\n7. 清理测试任务...');
    await axios.delete(`${API_BASE}/tasks/${task.id}`);
    console.log('   任务已删除\n');

  } catch (error) {
    console.error('测试过程中出错:', error.response?.data || error.message);
  }
}

// 测试取消后是否会影响新任务
async function testNewTaskAfterCancel() {
  console.log('\n=== 测试取消后创建新任务 ===\n');

  try {
    // 创建并立即执行一个快速任务
    console.log('创建一个 5 秒的快速任务...');
    const response = await axios.post(`${API_BASE}/tasks`, {
      type: 'test',
      driverId: 'simulator',
      modelId: 'test_simulator',
      prompt: '快速任务测试',
      params: { duration: 5000 },
      execute: false
    });

    const task = response.data;

    // 执行任务
    await axios.post(`${API_BASE}/tasks/${task.id}/simulate`, {
      duration: 5000
    });

    // 等待任务完成
    console.log('等待任务完成...');
    await new Promise(resolve => setTimeout(resolve, 6000));

    // 检查状态
    const check = await axios.get(`${API_BASE}/tasks/${task.id}`);
    console.log(`任务状态: ${check.data.status}`);
    console.log(`任务进度: ${check.data.progress}%`);

    if (check.data.status === 'completed' && check.data.progress === 100) {
      console.log('✅ 新任务正常执行完成！');
    } else {
      console.log('❌ 新任务执行异常！');
    }

    // 清理
    await axios.delete(`${API_BASE}/tasks/${task.id}`);

  } catch (error) {
    console.error('测试失败:', error.response?.data || error.message);
  }
}

// 执行测试
async function runTests() {
  console.log('开始任务取消功能测试...\n');
  console.log('请确保后端服务器已经重启并运行在 http://localhost:3000\n');
  console.log('===============================================\n');

  await testCancellation();
  await testNewTaskAfterCancel();

  console.log('\n===============================================');
  console.log('测试完成！');
}

runTests();