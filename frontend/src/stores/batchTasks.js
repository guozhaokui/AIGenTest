/**
 * 批量任务状态管理
 * 支持后台运行，切换页面不丢失进度
 */
import { defineStore } from 'pinia';
import { ref } from 'vue';
import { rebuildIndexStream } from '@/services/imagemgr';

export const useBatchTasksStore = defineStore('batchTasks', () => {
  // 更新嵌入任务状态
  const rebuildTask = ref({
    running: false,
    indexName: null,
    model: null,
    progress: null,
    result: null,
    startTime: null,
    error: null
  });
  
  let cancelRebuildFn = null;

  /**
   * 开始更新嵌入任务
   */
  function startRebuildTask(indexName, concurrency = 4) {
    // 如果已有任务在运行，先取消
    if (rebuildTask.value.running) {
      cancelRebuildTask();
    }
    
    rebuildTask.value = {
      running: true,
      indexName,
      model: null,
      progress: null,
      result: null,
      startTime: Date.now(),
      error: null
    };
    
    const options = {
      index_name: indexName,
      concurrency
    };
    
    cancelRebuildFn = rebuildIndexStream(
      options,
      // 进度回调
      (data) => {
        const elapsed = (Date.now() - rebuildTask.value.startTime) / 1000;
        const current = data.processed + data.failed;
        const percent = data.total > 0 ? Math.round((current / data.total) * 100) : 0;
        const speed = elapsed > 0 ? (current / elapsed).toFixed(1) : 0;
        const remaining = data.total - current;
        const eta = speed > 0 ? remaining / parseFloat(speed) : 0;
        
        rebuildTask.value.model = data.model || rebuildTask.value.model;
        rebuildTask.value.progress = {
          ...data,
          percent,
          speed,
          elapsed,
          eta
        };
      },
      // 完成回调
      (data) => {
        rebuildTask.value.result = data;
        rebuildTask.value.running = false;
        cancelRebuildFn = null;
      },
      // 错误回调
      (err) => {
        rebuildTask.value.error = err.message;
        rebuildTask.value.running = false;
        cancelRebuildFn = null;
      }
    );
  }

  /**
   * 取消更新嵌入任务
   */
  function cancelRebuildTask() {
    if (cancelRebuildFn) {
      cancelRebuildFn();
      cancelRebuildFn = null;
    }
    rebuildTask.value.running = false;
  }

  /**
   * 清除任务结果（用于开始新任务前）
   */
  function clearRebuildResult() {
    rebuildTask.value.result = null;
    rebuildTask.value.error = null;
    rebuildTask.value.progress = null;
  }

  return {
    rebuildTask,
    startRebuildTask,
    cancelRebuildTask,
    clearRebuildResult
  };
});

