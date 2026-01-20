// 测试任务自动归档功能
const taskManager = require('./src/services/taskManager');
const taskExecutor = require('./src/services/taskExecutor');
const taskArchiver = require('./src/services/taskArchiver');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testAutoArchive() {
  console.log('=== 测试任务自动归档功能 ===\n');

  try {
    // 1. 设置归档延迟为2秒（便于测试）
    console.log('1. 设置归档延迟为 2 秒...');
    taskArchiver.setArchiveDelay(2000);

    // 2. 创建并执行一个快速任务
    console.log('\n2. 创建并执行一个 3 秒的模拟任务...');
    const task = await taskManager.createTask({
      type: 'test',
      driverId: 'simulator',
      modelId: 'test_simulator',
      prompt: '自动归档测试',
      params: { duration: 3000 }
    });
    console.log(`   任务ID: ${task.id}`);

    // 执行任务
    taskExecutor.simulateTask(task.id, 3000);

    // 3. 等待任务完成
    console.log('\n3. 等待任务完成...');
    await sleep(3500);

    // 检查任务状态
    let currentTask = await taskManager.getTask(task.id);
    console.log(`   任务状态: ${currentTask ? currentTask.status : '已从活跃列表移除'}`);

    if (currentTask) {
      console.log('   任务仍在活跃列表中，等待归档...');

      // 4. 等待归档延迟
      console.log('\n4. 等待 2 秒归档延迟...');
      await sleep(2500);

      // 再次检查
      currentTask = await taskManager.getTask(task.id);
      if (!currentTask) {
        console.log('   ✅ 任务已自动从活跃列表移除！');
      } else {
        console.log('   ❌ 任务仍在活跃列表中，归档可能失败');
      }
    }

    // 5. 检查归档
    console.log('\n5. 检查归档记录...');
    const archives = await taskArchiver.getArchivedTasks({ limit: 5 });
    const archivedTask = archives.find(t => t.id === task.id);

    if (archivedTask) {
      console.log('   ✅ 找到归档记录！');
      console.log(`   归档时间: ${archivedTask.archivedAt}`);
      console.log(`   任务状态: ${archivedTask.status}`);
      console.log(`   任务进度: ${archivedTask.progress}%`);
    } else {
      console.log('   ❌ 未找到归档记录');
    }

    // 6. 测试取消任务的归档
    console.log('\n6. 测试取消任务的自动归档...');
    const task2 = await taskManager.createTask({
      type: 'test',
      driverId: 'simulator',
      modelId: 'test_simulator',
      prompt: '取消任务归档测试',
      params: { duration: 10000 }
    });

    // 执行并立即取消
    taskExecutor.simulateTask(task2.id, 10000);
    await sleep(1000);
    await taskExecutor.cancelTask(task2.id);

    console.log('   任务已取消，等待归档...');
    await sleep(2500);

    // 检查是否归档
    const task2Active = await taskManager.getTask(task2.id);
    const task2Archived = (await taskArchiver.getArchivedTasks({ limit: 5 }))
      .find(t => t.id === task2.id);

    if (!task2Active && task2Archived) {
      console.log('   ✅ 取消的任务已自动归档！');
      console.log(`   归档状态: ${task2Archived.status}`);
    } else {
      console.log('   ❌ 取消的任务归档失败');
    }

    // 7. 检查归档统计
    console.log('\n7. 归档统计:');
    const stats = await taskArchiver.getArchiveStats();
    console.log(`   总归档数: ${stats.total}`);
    console.log(`   已完成: ${stats.completed}`);
    console.log(`   已失败: ${stats.failed}`);
    console.log(`   已取消: ${stats.cancelled}`);
    console.log(`   最后归档: ${stats.lastArchived || '无'}`);

    // 8. 测试手动归档所有完成任务
    console.log('\n8. 测试手动归档所有完成任务...');

    // 先检查当前活跃任务
    const activeTasks = await taskManager.getTasks();
    const completedCount = activeTasks.filter(t =>
      ['completed', 'failed', 'cancelled'].includes(t.status)
    ).length;

    if (completedCount > 0) {
      console.log(`   找到 ${completedCount} 个可归档任务`);
      const archivedCount = await taskArchiver.archiveAllCompleted();
      console.log(`   ✅ 归档了 ${archivedCount} 个任务`);
    } else {
      console.log('   没有需要归档的任务');
    }

    console.log('\n✅ 自动归档功能测试完成！');

  } catch (error) {
    console.error('❌ 测试失败:', error);
    console.error(error.stack);
  }
}

async function showCurrentStatus() {
  console.log('\n=== 当前系统状态 ===\n');

  const activeTasks = await taskManager.getTasks();
  const archives = await taskArchiver.getArchivedTasks({ limit: 10 });

  console.log(`活跃任务数: ${activeTasks.length}`);
  console.log(`归档任务数: ${archives.length}`);

  if (activeTasks.length > 0) {
    console.log('\n活跃任务:');
    activeTasks.forEach(t => {
      console.log(`  - ${t.id.slice(0, 8)}... [${t.status}] ${t.prompt}`);
    });
  }

  if (archives.length > 0) {
    console.log('\n最近归档:');
    archives.slice(0, 5).forEach(t => {
      console.log(`  - ${t.id.slice(0, 8)}... [${t.status}] ${t.prompt} (${new Date(t.archivedAt).toLocaleString()})`);
    });
  }
}

async function runTests() {
  console.log('开始任务自动归档测试...\n');
  console.log('===============================================\n');

  await showCurrentStatus();
  await testAutoArchive();
  await showCurrentStatus();

  console.log('\n===============================================');
  console.log('测试完成！');

  // 等待确保所有异步操作完成
  await sleep(1000);
  process.exit(0);
}

runTests().catch(error => {
  console.error('测试失败:', error);
  process.exit(1);
});