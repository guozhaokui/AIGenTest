const fs = require('fs').promises;
const path = require('path');
const taskManager = require('./taskManager');

/**
 * 任务归档服务
 * 负责将完成/失败/取消的任务移动到归档，保持活跃任务列表清洁
 */
class TaskArchiver {
  constructor() {
    this.archiveFile = path.resolve(__dirname, '../../data/tasks-archive.json');
    this.liveGenFile = path.resolve(__dirname, '../../data/live-gen.json');
    this.archives = [];
    this.initialized = false;
    this.archiveDelay = 5000; // 归档延迟时间（毫秒）
    this.pendingArchives = new Map(); // 待归档任务的定时器
  }

  async init() {
    if (this.initialized) return;

    try {
      const data = await fs.readFile(this.archiveFile, 'utf-8');
      this.archives = JSON.parse(data);
    } catch (error) {
      // 文件不存在，创建空归档
      this.archives = [];
      await this.saveArchives();
    }

    this.initialized = true;
    console.log('TaskArchiver initialized with', this.archives.length, 'archived tasks');
  }

  async saveArchives() {
    await fs.writeFile(
      this.archiveFile,
      JSON.stringify(this.archives, null, 2),
      'utf-8'
    );
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

      // 保存到归档
      this.archives.push(archivedTask);
      await this.saveArchives();

      // 如果是成功完成的任务，也保存到 live-gen.json
      if (task.status === 'completed' && task.result) {
        await this.saveToLiveGen(task);
      }

      // 从活跃任务列表中删除
      await taskManager.deleteTask(taskId);

      console.log(`Task ${taskId} archived successfully`);
    } catch (error) {
      console.error(`Failed to archive task ${taskId}:`, error);
    }
  }

  /**
   * 保存成功完成的任务到 live-gen.json
   */
  async saveToLiveGen(task) {
    try {
      let liveGen = [];
      try {
        const data = await fs.readFile(this.liveGenFile, 'utf-8');
        liveGen = JSON.parse(data);
      } catch (error) {
        // 文件不存在或格式错误
        liveGen = [];
      }

      // 添加到历史记录
      liveGen.push({
        id: task.id,
        type: task.type,
        modelId: task.modelId,
        driverId: task.driverId,
        prompt: task.prompt,
        params: task.params,
        result: task.result,
        createdAt: task.createdAt,
        completedAt: task.completedAt || new Date().toISOString()
      });

      // 限制历史记录数量
      if (liveGen.length > 1000) {
        liveGen = liveGen.slice(-1000);
      }

      await fs.writeFile(
        this.liveGenFile,
        JSON.stringify(liveGen, null, 2),
        'utf-8'
      );

      console.log(`Task ${task.id} saved to live-gen.json`);
    } catch (error) {
      console.error('Failed to save to live-gen.json:', error);
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

    let tasks = [...this.archives];

    // 应用过滤器
    if (filter.status) {
      tasks = tasks.filter(t => t.status === filter.status);
    }
    if (filter.type) {
      tasks = tasks.filter(t => t.type === filter.type);
    }
    if (filter.dateFrom) {
      const fromDate = new Date(filter.dateFrom);
      tasks = tasks.filter(t => new Date(t.archivedAt) >= fromDate);
    }
    if (filter.dateTo) {
      const toDate = new Date(filter.dateTo);
      tasks = tasks.filter(t => new Date(t.archivedAt) <= toDate);
    }

    // 按归档时间倒序排列
    tasks.sort((a, b) => new Date(b.archivedAt) - new Date(a.archivedAt));

    // 限制返回数量
    if (filter.limit) {
      tasks = tasks.slice(0, filter.limit);
    }

    return tasks;
  }

  /**
   * 清理旧归档
   */
  async cleanupOldArchives(maxAge = 30 * 24 * 60 * 60 * 1000) { // 默认30天
    await this.init();

    const now = Date.now();
    const originalCount = this.archives.length;

    this.archives = this.archives.filter(task => {
      const taskAge = now - new Date(task.archivedAt).getTime();
      return taskAge <= maxAge;
    });

    if (this.archives.length < originalCount) {
      await this.saveArchives();
      const deleted = originalCount - this.archives.length;
      console.log(`Cleaned up ${deleted} old archived tasks`);
      return deleted;
    }

    return 0;
  }

  /**
   * 获取归档统计
   */
  async getArchiveStats() {
    await this.init();

    const stats = {
      total: this.archives.length,
      completed: 0,
      failed: 0,
      cancelled: 0,
      byType: {},
      byDriver: {},
      lastArchived: null
    };

    this.archives.forEach(task => {
      // 按状态统计
      stats[task.status]++;

      // 按类型统计
      stats.byType[task.type] = (stats.byType[task.type] || 0) + 1;

      // 按驱动统计
      stats.byDriver[task.driverId] = (stats.byDriver[task.driverId] || 0) + 1;
    });

    // 最后归档时间
    if (this.archives.length > 0) {
      const lastArchived = this.archives.reduce((latest, task) => {
        const taskTime = new Date(task.archivedAt);
        return taskTime > latest ? taskTime : latest;
      }, new Date(0));
      stats.lastArchived = lastArchived.toISOString();
    }

    return stats;
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
    const tasks = await taskManager.getTasks();
    let archivedCount = 0;

    for (const task of tasks) {
      if (['completed', 'failed', 'cancelled'].includes(task.status)) {
        await this.performArchive(task.id);
        archivedCount++;
      }
    }

    console.log(`Archived ${archivedCount} completed tasks`);
    return archivedCount;
  }
}

// 导出单例
module.exports = new TaskArchiver();