const taskManager = require('./taskManager');
const database = require('./database');

/**
 * 任务归档服务
 * 负责将完成/失败/取消的任务移动到归档，保持活跃任务列表清洁
 * 现在使用 SQLite 数据库存储数据
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

      // 获取归档统计
      const stats = await this.getArchiveStats();
      console.log('TaskArchiver initialized with database, archived tasks:', stats.total);
    } catch (error) {
      console.error('Failed to initialize TaskArchiver:', error);
      throw error;
    }
  }

  /**
   * 归档任务（从活跃列表移到归档）
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

      // 添加归档信息
      const archivedTask = {
        ...task,
        archivedAt: new Date().toISOString()
      };

      // 保存到数据库的归档表
      await database.saveArchivedTask(archivedTask);

      // 如果是成功完成的任务，也保存到数据库的生成记录表
      if (task.status === 'completed' && task.result) {
        await this.saveToGenerations(task);
      }

      // 从活跃任务列表中删除
      await taskManager.deleteTask(taskId);

      console.log(`Task ${taskId} archived successfully to database`);
    } catch (error) {
      console.error(`Failed to archive task ${taskId}:`, error);
    }
  }

  /**
   * 保存成功完成的任务到数据库生成记录表
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
        status: 'completed',
        createdAt: task.createdAt,
        completedAt: task.completedAt || new Date().toISOString(),
        metadata: task.metadata || {}
      };

      await database.saveGeneration(generation);
      console.log(`Task ${task.id} saved to database generations table`);
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
   * 获取归档任务
   */
  async getArchivedTasks(filter = {}) {
    await this.init();

    try {
      // 使用数据库查询
      const limit = filter.limit || 100;
      let tasks = await database.getArchivedTasks(limit);

      // 应用过滤器（在内存中过滤，后续可优化为SQL查询）
      if (filter.status) {
        tasks = tasks.filter(t => t.status === filter.status);
      }
      if (filter.type) {
        tasks = tasks.filter(t => t.type === filter.type);
      }
      if (filter.dateFrom) {
        const fromDate = new Date(filter.dateFrom);
        tasks = tasks.filter(t => new Date(t.archived_at) >= fromDate);
      }
      if (filter.dateTo) {
        const toDate = new Date(filter.dateTo);
        tasks = tasks.filter(t => new Date(t.archived_at) <= toDate);
      }

      return tasks;
    } catch (error) {
      console.error('Failed to get archived tasks:', error);
      return [];
    }
  }

  /**
   * 清理旧归档
   */
  async cleanupOldArchives(maxAge = 30 * 24 * 60 * 60 * 1000) { // 默认30天
    await this.init();

    try {
      const daysToKeep = Math.floor(maxAge / (24 * 60 * 60 * 1000));
      const result = await database.cleanup(daysToKeep);

      console.log(`Cleaned up ${result.archivedTasks} old archived tasks`);
      return result.archivedTasks;
    } catch (error) {
      console.error('Failed to cleanup old archives:', error);
      return 0;
    }
  }

  /**
   * 获取归档统计
   */
  async getArchiveStats() {
    await this.init();

    try {
      // 从数据库获取统计
      const dbInfo = database.getDatabaseInfo();
      const archives = await database.getArchivedTasks(1000); // 获取最近1000条用于统计

      const stats = {
        total: dbInfo ? dbInfo.archivedTasks : 0,
        completed: 0,
        failed: 0,
        cancelled: 0,
        byType: {},
        byDriver: {},
        lastArchived: null
      };

      archives.forEach(task => {
        // 按状态统计
        if (stats[task.status] !== undefined) {
          stats[task.status]++;
        }

        // 按类型统计
        stats.byType[task.type] = (stats.byType[task.type] || 0) + 1;

        // 按驱动统计
        if (task.driver_id) {
          stats.byDriver[task.driver_id] = (stats.byDriver[task.driver_id] || 0) + 1;
        }
      });

      // 最后归档时间
      if (archives.length > 0) {
        stats.lastArchived = archives[0].archived_at; // 已按时间倒序排列
      }

      return stats;
    } catch (error) {
      console.error('Failed to get archive stats:', error);
      return {
        total: 0,
        completed: 0,
        failed: 0,
        cancelled: 0,
        byType: {},
        byDriver: {},
        lastArchived: null
      };
    }
  }

  /**
   * 设置归档延迟时间
   */
  setArchiveDelay(delayMs) {
    this.archiveDelay = Math.max(0, delayMs);
    console.log(`Archive delay set to ${this.archiveDelay}ms`);
  }

  /**
   * 立即归档所有符合条件的任务
   */
  async archiveAllCompleted() {
    await this.init();

    const tasks = await taskManager.getTasks();
    let archivedCount = 0;

    for (const task of tasks) {
      if (['completed', 'failed', 'cancelled'].includes(task.status)) {
        await this.performArchive(task.id);
        archivedCount++;
      }
    }

    console.log(`Archived ${archivedCount} completed tasks to database`);
    return archivedCount;
  }
}

// 导出单例
module.exports = new TaskArchiver();