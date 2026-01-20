// 单元测试 - 直接测试任务取消逻辑
const taskManager = require('./src/services/taskManager');
const taskExecutor = require('./src/services/taskExecutor');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testDirectCancellation() {
  console.log('=== 直接测试任务取消逻辑 ===\n');

  try {
    // 1. 创建任务
    console.log('1. 创建模拟任务...');
    const task = await taskManager.createTask({
      type: 'test',
      driverId: 'simulator',
      modelId: 'test_simulator',
      prompt: '取消测试',
      params: { duration: 15000 }
    });
    console.log(`   任务ID: ${task.id}`);
    console.log(`   初始状态: ${task.status}\n`);

    // 2. 启动任务（异步执行）
    console.log('2. 启动任务执行（15秒）...');
    const executionPromise = taskExecutor.simulateTask(task.id, 15000);

    // 3. 等待3秒
    console.log('3. 等待3秒...');
    await sleep(3000);

    // 检查进度
    let currentTask = await taskManager.getTask(task.id);
    console.log(`   3秒后进度: ${currentTask.progress}%`);
    console.log(`   状态: ${currentTask.status}\n`);

    // 4. 取消任务
    console.log('4. 执行取消操作...');
    const cancelledTask = await taskExecutor.cancelTask(task.id);
    console.log(`   取消后状态: ${cancelledTask.status}`);
    console.log(`   错误信息: ${cancelledTask.error || '无'}\n`);

    // 5. 等待2秒，检查进度是否停止
    console.log('5. 等待2秒，检查进度是否停止更新...');
    const progress1 = cancelledTask.progress;
    await sleep(2000);

    currentTask = await taskManager.getTask(task.id);
    const progress2 = currentTask.progress;

    console.log(`   取消时进度: ${progress1}%`);
    console.log(`   2秒后进度: ${progress2}%`);

    if (progress1 === progress2) {
      console.log('   ✅ 进度没有继续更新，任务已停止！');
    } else {
      console.log('   ❌ 进度仍在更新，任务可能未停止！');
    }

    // 6. 等待原始执行完成
    console.log('\n6. 等待原始执行结束...');
    try {
      await executionPromise;
      console.log('   执行结束');
    } catch (error) {
      console.log('   执行被取消:', error.message);
    }

    // 7. 最终检查
    const finalTask = await taskManager.getTask(task.id);
    console.log('\n7. 最终检查:');
    console.log(`   最终状态: ${finalTask.status}`);
    console.log(`   最终进度: ${finalTask.progress}%`);

    if (finalTask.status === 'cancelled' && finalTask.progress < 100) {
      console.log('\n✅ 测试通过！任务成功取消。');
    } else {
      console.log('\n❌ 测试失败！任务取消不完全。');
    }

    // 清理
    await taskManager.deleteTask(task.id);
    console.log('\n任务已清理');

  } catch (error) {
    console.error('测试出错:', error.message);
    console.error(error.stack);
  }
}

async function testAbortController() {
  console.log('\n=== 测试 AbortController 机制 ===\n');

  const controller = new AbortController();
  const signal = controller.signal;

  console.log('1. 创建一个可取消的异步操作...');

  const asyncOperation = new Promise((resolve, reject) => {
    const timeouts = [];

    const runSteps = async () => {
      for (let i = 1; i <= 10; i++) {
        if (signal.aborted) {
          console.log(`   步骤 ${i}: 检测到取消信号，停止执行`);
          reject(new Error('Operation cancelled'));
          return;
        }

        console.log(`   步骤 ${i}/10 执行中...`);

        await new Promise((stepResolve, stepReject) => {
          const timeout = setTimeout(stepResolve, 500);
          timeouts.push(timeout);

          signal.addEventListener('abort', () => {
            clearTimeout(timeout);
            stepReject(new Error('Step cancelled'));
          }, { once: true });
        }).catch(() => {
          // 步骤被取消
          timeouts.forEach(t => clearTimeout(t));
          throw new Error('Operation cancelled');
        });
      }
      resolve('完成');
    };

    runSteps().catch(reject);
  });

  // 3秒后取消
  setTimeout(() => {
    console.log('\n2. 发送取消信号...');
    controller.abort();
  }, 2500);

  try {
    const result = await asyncOperation;
    console.log('   操作完成:', result);
    console.log('   ❌ 操作未被取消！');
  } catch (error) {
    console.log('   操作被取消:', error.message);
    console.log('   ✅ AbortController 正常工作！');
  }
}

async function runTests() {
  console.log('开始任务取消单元测试...\n');
  console.log('===============================================\n');

  await testAbortController();
  await testDirectCancellation();

  console.log('\n===============================================');
  console.log('单元测试完成！');

  // 等待一下确保清理完成
  await sleep(1000);
  process.exit(0);
}

runTests().catch(error => {
  console.error('测试失败:', error);
  process.exit(1);
});