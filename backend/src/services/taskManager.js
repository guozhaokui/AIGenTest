const fs = require('fs').promises;
const path = require('path');
const { randomUUID } = require('crypto');

class TaskManager {
  constructor() {
    this.tasksFile = path.resolve(__dirname, '../../data/tasks.json');
    this.tasks = new Map();
    this.initialized = false;
    this.initPromise = this.init();
  }

  async init() {
    if (this.initialized) return;

    try {
      await this.loadTasks();
      this.initialized = true;
      console.log('TaskManager initialized with', this.tasks.size, 'tasks');
    } catch (error) {
      console.error('Failed to initialize TaskManager:', error);
      // Create empty tasks file if it doesn't exist
      await this.saveTasks();
      this.initialized = true;
    }
  }

  async ensureInitialized() {
    if (!this.initialized) {
      await this.initPromise;
    }
  }

  async loadTasks() {
    try {
      const data = await fs.readFile(this.tasksFile, 'utf-8');
      const tasksArray = JSON.parse(data);
      this.tasks.clear();
      tasksArray.forEach(task => this.tasks.set(task.id, task));
    } catch (error) {
      if (error.code === 'ENOENT') {
        // File doesn't exist, create empty tasks
        this.tasks.clear();
      } else {
        throw error;
      }
    }
  }

  async saveTasks() {
    const tasksArray = Array.from(this.tasks.values());
    await fs.writeFile(
      this.tasksFile,
      JSON.stringify(tasksArray, null, 2),
      'utf-8'
    );
  }

  async createTask(params) {
    await this.ensureInitialized();

    const task = {
      id: randomUUID(),
      type: params.type || 'unknown',
      status: 'pending',
      modelId: params.modelId,
      driverId: params.driverId,
      prompt: params.prompt,
      params: params.params || {},
      progress: 0,
      result: null,
      error: null,
      driverTaskId: null, // For drivers that support async tasks
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      startedAt: null,
      completedAt: null,
      metadata: params.metadata || {}
    };

    this.tasks.set(task.id, task);
    await this.saveTasks();

    return task;
  }

  async updateTask(taskId, updates) {
    await this.ensureInitialized();

    const task = this.tasks.get(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    // Update task fields
    Object.assign(task, updates);
    task.updatedAt = new Date().toISOString();

    // Set timestamps based on status changes
    if (updates.status === 'running' && !task.startedAt) {
      task.startedAt = new Date().toISOString();
    }
    if (updates.status === 'completed' || updates.status === 'failed') {
      task.completedAt = new Date().toISOString();
    }

    await this.saveTasks();
    return task;
  }

  async getTask(taskId) {
    await this.ensureInitialized();
    return this.tasks.get(taskId);
  }

  async getTasks(filter = {}) {
    await this.ensureInitialized();

    let tasks = Array.from(this.tasks.values());

    // Apply filters
    if (filter.status) {
      tasks = tasks.filter(t => t.status === filter.status);
    }
    if (filter.type) {
      tasks = tasks.filter(t => t.type === filter.type);
    }
    if (filter.modelId) {
      tasks = tasks.filter(t => t.modelId === filter.modelId);
    }

    // Sort by creation time (newest first)
    tasks.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

    return tasks;
  }

  async deleteTask(taskId) {
    await this.ensureInitialized();

    const deleted = this.tasks.delete(taskId);
    if (deleted) {
      await this.saveTasks();
    }
    return deleted;
  }

  async cleanupOldTasks(maxAge = 24 * 60 * 60 * 1000) {
    await this.ensureInitialized();

    const now = Date.now();
    const tasksToDelete = [];

    for (const [id, task] of this.tasks) {
      const taskAge = now - new Date(task.createdAt).getTime();
      if (taskAge > maxAge && (task.status === 'completed' || task.status === 'failed')) {
        tasksToDelete.push(id);
      }
    }

    for (const id of tasksToDelete) {
      this.tasks.delete(id);
    }

    if (tasksToDelete.length > 0) {
      await this.saveTasks();
      console.log(`Cleaned up ${tasksToDelete.length} old tasks`);
    }

    return tasksToDelete.length;
  }

  async getTaskStats() {
    await this.ensureInitialized();

    const stats = {
      total: this.tasks.size,
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0
    };

    for (const task of this.tasks.values()) {
      stats[task.status]++;
    }

    return stats;
  }
}

// Export singleton instance
module.exports = new TaskManager();