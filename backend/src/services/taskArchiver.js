const taskManager = require('./taskManager');
const database = require('./database');

/**
 * 任务归档服务
 * 负责将完成/失败/取消的任务保存到历史记录，并从活跃任务列表中删除
 * 简化版：所有任务都保存到 generations 表
 */
class TaskArchiver {
  constructor() {
    this.initialized = false;
    this.archiveDelay = 5000; // 归档延迟时间（毫秒）
    this.pendingArchives = new Map(); // 待归档任务的定时器
  }

  async init() {
    if (this.initialized) return;

    try {
      await database.init();
      this.initialized = true;
      console.log('TaskArchiver initialized with database');
    } catch (error) {
      console.error('Failed to initialize TaskArchiver:', error);
      throw error;
    }
  }

  /**
   * 归档任务（保存到历史记录并从活跃列表删除）
   * @param {string} taskId - 任务ID
   * @param {boolean} immediate - 是否立即归档（默认false，有延迟）
   */
  async archiveTask(taskId, immediate = false) {
    await this.init();

    // 如果已有待归档定时器，清除它
    if (this.pendingArchives.has(taskId)) {
      clearTimeout(this.pendingArchives.get(taskId));
      this.pendingArchives.delete(taskId);
    }

    if (immediate) {
      // 立即归档
      await this.performArchive(taskId);
    } else {
      // 延迟归档（给用户一个反悔的机会）
      const timeout = setTimeout(async () => {
        await this.performArchive(taskId);
        this.pendingArchives.delete(taskId);
      }, this.archiveDelay);

      this.pendingArchives.set(taskId, timeout);
      console.log(`Task ${taskId} scheduled for archive in ${this.archiveDelay}ms`);
    }
  }

  /**
   * 执行实际的归档操作
   */
  async performArchive(taskId) {
    try {
      // 获取任务信息
      const task = await taskManager.getTask(taskId);
      if (!task) {
        console.log(`Task ${taskId} not found, skipping archive`);
        return;
      }

      // 只归档已完成、失败或取消的任务
      if (!['completed', 'failed', 'cancelled'].includes(task.status)) {
        console.log(`Task ${taskId} is ${task.status}, not archiving yet`);
        return;
      }

      // 保存到数据库的生成记录表（所有状态的任务都保存）
      await this.saveToGenerations(task);

      // 从活跃任务列表中删除
      await taskManager.deleteTask(taskId);

      console.log(`Task ${taskId} archived successfully (status: ${task.status})`);
    } catch (error) {
      console.error(`Failed to archive task ${taskId}:`, error);
    }
  }

  /**
   * 保存任务到数据库生成记录表
   */
  async saveToGenerations(task) {
    try {
      const generation = {
        id: task.id,
        type: task.type,
        modelId: task.modelId,
        driverId: task.driverId,
        prompt: task.prompt,
        params: task.params,
        result: task.result,
        status: task.status, // 保存实际状态：completed/failed/cancelled
        createdAt: task.createdAt,
        completedAt: task.completedAt || new Date().toISOString(),
        metadata: {
          ...task.metadata,
          archivedAt: new Date().toISOString()
        }
      };

      await database.saveGeneration(generation);
      console.log(`Task ${task.id} saved to generations table (status: ${task.status})`);
    } catch (error) {
      // 如果是重复ID错误，忽略（可能已经存在）
      if (error.code === 'SQLITE_CONSTRAINT_PRIMARYKEY') {
        console.log(`Task ${task.id} already exists in generations table`);
      } else {
        console.error('Failed to save to generations table:', error);
      }
    }
  }

  /**
   * 取消待归档任务
   */
  cancelPendingArchive(taskId) {
    if (this.pendingArchives.has(taskId)) {
      clearTimeout(this.pendingArchives.get(taskId));
      this.pendingArchives.delete(taskId);
      console.log(`Cancelled pending archive for task ${taskId}`);
    }
  }

  /**
   * 设置归档延迟时间
   */
  setArchiveDelay(delayMs) {
    this.archiveDelay = delayMs;
    console.log(`Archive delay set to ${delayMs}ms`);
  }
}

module.exports = new TaskArchiver();