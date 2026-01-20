const taskManager = require('./taskManager');
const taskArchiver = require('./taskArchiver');
const fs = require('fs').promises;
const path = require('path');
// Node.js 15+ has built-in AbortController, no need to import

class TaskExecutor {
  constructor() {
    this.runningTasks = new Map();
    this.pollIntervals = new Map();
    this.driverModules = new Map();
    this.abortControllers = new Map(); // 新增：存储 AbortController
    this.simulationTimeouts = new Map(); // 新增：存储模拟任务的定时器
  }

  /**
   * Load driver module dynamically
   */
  async getDriver(driverId) {
    if (!this.driverModules.has(driverId)) {
      try {
        const driverPath = path.join(__dirname, 'modelDrivers', `${driverId}.js`);
        const driver = require(driverPath);
        this.driverModules.set(driverId, driver);
      } catch (error) {
        console.error(`Failed to load driver ${driverId}:`, error);
        throw new Error(`Driver ${driverId} not found or failed to load`);
      }
    }
    return this.driverModules.get(driverId);
  }

  /**
   * Execute a task
   */
  async executeTask(taskId) {
    const task = await taskManager.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    if (this.runningTasks.has(taskId)) {
      console.log(`Task ${taskId} is already running`);
      return task;
    }

    this.runningTasks.set(taskId, true);

    // 创建 AbortController 用于取消
    const abortController = new AbortController();
    this.abortControllers.set(taskId, abortController);

    try {
      // Update task status to running
      await taskManager.updateTask(taskId, { status: 'running' });

      // Get the appropriate driver
      const driver = await this.getDriver(task.driverId);

      if (driver.supportsAsyncTask && driver.supportsAsyncTask()) {
        // Driver supports async tasks (like Meshy, LTX2)
        await this.executeAsyncTask(task, driver, abortController.signal);
      } else {
        // Driver is synchronous (like Google)
        await this.executeSyncTask(task, driver, abortController.signal);
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log(`Task ${taskId} was cancelled`);
        await taskManager.updateTask(taskId, {
          status: 'cancelled',
          error: 'Task was cancelled by user'
        });
        // 自动归档取消的任务
        await taskArchiver.archiveTask(taskId);
      } else {
        console.error(`Task ${taskId} execution failed:`, error);
        await taskManager.updateTask(taskId, {
          status: 'failed',
          error: error.message
        });
        // 自动归档失败的任务
        await taskArchiver.archiveTask(taskId);
      }
    } finally {
      this.runningTasks.delete(taskId);
      this.abortControllers.delete(taskId);
    }

    return await taskManager.getTask(taskId);
  }

  /**
   * Execute async task (driver returns a task ID)
   */
  async executeAsyncTask(task, driver, signal) {
    try {
      // Check if cancelled before starting
      if (signal.aborted) {
        throw new Error('Task cancelled before execution');
      }

      // Create task on the driver's platform
      const driverResponse = await driver.createTask({
        prompt: task.prompt,
        ...task.params
      });

      // Store driver task ID
      await taskManager.updateTask(task.id, {
        driverTaskId: driverResponse.taskId,
        progress: 10
      });

      // Start polling for task status
      this.startPolling(task.id, driver, signal);
    } catch (error) {
      throw new Error(`Failed to create async task: ${error.message}`);
    }
  }

  /**
   * Execute synchronous task with cancellation support
   */
  async executeSyncTask(task, driver, signal) {
    try {
      // Check if cancelled before starting
      if (signal.aborted) {
        throw new Error('Task cancelled before execution');
      }

      // For synchronous drivers, simulate progress
      await taskManager.updateTask(task.id, { progress: 20 });

      // Check cancellation again
      if (signal.aborted) {
        throw new Error('Task cancelled');
      }

      // Execute the generation with timeout and cancellation check
      const result = await this.executeWithCancellation(
        driver.generate({
          prompt: task.prompt,
          ...task.params
        }),
        signal,
        task.id
      );

      // Check if cancelled after generation
      if (signal.aborted) {
        throw new Error('Task cancelled after generation');
      }

      // Save result
      const savedResult = await this.saveResult(task, result);

      // Update task as completed
      await taskManager.updateTask(task.id, {
        status: 'completed',
        progress: 100,
        result: savedResult
      });

      // 自动归档完成的任务（归档服务会处理live-gen.json）
      await taskArchiver.archiveTask(task.id);

      this.runningTasks.delete(task.id);
    } catch (error) {
      if (signal.aborted || error.message.includes('cancelled')) {
        throw Object.assign(new Error('Task cancelled'), { name: 'AbortError' });
      }
      throw new Error(`Sync task execution failed: ${error.message}`);
    }
  }

  /**
   * Execute promise with cancellation support
   */
  async executeWithCancellation(promise, signal, taskId) {
    return new Promise((resolve, reject) => {
      // Listen for abort signal
      const abortHandler = () => {
        reject(new Error('Task cancelled'));
      };
      signal.addEventListener('abort', abortHandler);

      // Execute the promise
      promise
        .then(result => {
          signal.removeEventListener('abort', abortHandler);
          if (signal.aborted) {
            reject(new Error('Task cancelled'));
          } else {
            resolve(result);
          }
        })
        .catch(error => {
          signal.removeEventListener('abort', abortHandler);
          reject(error);
        });
    });
  }

  /**
   * Start polling for async task status with cancellation support
   */
  startPolling(taskId, driver, signal) {
    const pollInterval = setInterval(async () => {
      try {
        // Check if cancelled
        if (signal && signal.aborted) {
          this.stopPolling(taskId);
          return;
        }

        const task = await taskManager.getTask(taskId);
        if (!task || !task.driverTaskId) {
          this.stopPolling(taskId);
          return;
        }

        // Get status from driver
        const status = await driver.getTaskStatus(task.driverTaskId);

        // Update progress
        if (status.progress !== undefined) {
          await taskManager.updateTask(taskId, { progress: status.progress });
        }

        // Check if task is complete
        if (status.status === 'completed' || status.status === 'succeeded') {
          // Get result from driver
          const result = await driver.getTaskResult(task.driverTaskId);
          const savedResult = await this.saveResult(task, result);

          // Update task as completed
          await taskManager.updateTask(taskId, {
            status: 'completed',
            progress: 100,
            result: savedResult
          });

          // 自动归档完成的任务
          await taskArchiver.archiveTask(taskId);

          // Stop polling
          this.stopPolling(taskId);
          this.runningTasks.delete(taskId);
        } else if (status.status === 'failed' || status.status === 'error') {
          // Task failed
          await taskManager.updateTask(taskId, {
            status: 'failed',
            error: status.error || 'Task failed on driver platform'
          });

          // 自动归档失败的任务
          await taskArchiver.archiveTask(taskId);

          this.stopPolling(taskId);
          this.runningTasks.delete(taskId);
        }
      } catch (error) {
        console.error(`Polling error for task ${taskId}:`, error);

        // Don't immediately fail, might be temporary network issue
        // But increment error count and fail after multiple attempts
        const task = await taskManager.getTask(taskId);
        const errorCount = (task.metadata.pollErrors || 0) + 1;

        if (errorCount >= 5) {
          await taskManager.updateTask(taskId, {
            status: 'failed',
            error: `Polling failed after ${errorCount} attempts: ${error.message}`
          });
          // 自动归档失败的任务
          await taskArchiver.archiveTask(taskId);
          this.stopPolling(taskId);
          this.runningTasks.delete(taskId);
        } else {
          await taskManager.updateTask(taskId, {
            metadata: { ...task.metadata, pollErrors: errorCount }
          });
        }
      }
    }, 5000); // Poll every 5 seconds

    this.pollIntervals.set(taskId, pollInterval);
  }

  /**
   * Stop polling for a task
   */
  stopPolling(taskId) {
    const interval = this.pollIntervals.get(taskId);
    if (interval) {
      clearInterval(interval);
      this.pollIntervals.delete(taskId);
    }
  }

  /**
   * Save task result to appropriate location
   */
  async saveResult(task, result) {
    const timestamp = Date.now();
    const resultData = {
      taskId: task.id,
      type: task.type,
      timestamp,
      ...result
    };

    // Different handling based on task type
    switch (task.type) {
      case 'image':
        resultData.imagePath = result.imagePath || `/imagedb/${task.driverId}/${timestamp}.png`;
        break;
      case '3d':
        resultData.modelPath = result.modelPath || `/3dmodels/${task.driverId}/${timestamp}.glb`;
        break;
      case 'video':
        resultData.videoPath = result.videoPath || `/videodb/${task.driverId}/${timestamp}.mp4`;
        break;
      case 'audio':
        resultData.audioPath = result.audioPath || `/audiodb/${task.driverId}/${timestamp}.mp3`;
        break;
    }

    return resultData;
  }

  // saveToHistory method removed - now handled by TaskArchiver

  /**
   * Cancel a running task (improved version)
   */
  async cancelTask(taskId) {
    const task = await taskManager.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    // Stop polling if active
    this.stopPolling(taskId);

    // Abort the task execution
    const abortController = this.abortControllers.get(taskId);
    if (abortController) {
      abortController.abort();
    }

    // Cancel simulation timeouts
    const timeouts = this.simulationTimeouts.get(taskId);
    if (timeouts) {
      timeouts.forEach(timeout => clearTimeout(timeout));
      this.simulationTimeouts.delete(taskId);
    }

    // Try to cancel on driver platform if supported
    if (task.driverTaskId) {
      try {
        const driver = await this.getDriver(task.driverId);
        if (driver.cancelTask) {
          await driver.cancelTask(task.driverTaskId);
        }
      } catch (error) {
        console.error(`Failed to cancel task on driver platform:`, error);
      }
    }

    // Update task status only if not already completed
    if (task.status === 'running' || task.status === 'pending') {
      await taskManager.updateTask(taskId, {
        status: 'cancelled',
        error: 'Task cancelled by user'
      });
      // 自动归档取消的任务
      await taskArchiver.archiveTask(taskId);
    }

    this.runningTasks.delete(taskId);
    this.abortControllers.delete(taskId);

    return await taskManager.getTask(taskId);
  }

  /**
   * Get executor status
   */
  getStatus() {
    return {
      runningTasks: Array.from(this.runningTasks.keys()),
      pollingTasks: Array.from(this.pollIntervals.keys()),
      loadedDrivers: Array.from(this.driverModules.keys()),
      activeAbortControllers: Array.from(this.abortControllers.keys()),
      activeSimulations: Array.from(this.simulationTimeouts.keys())
    };
  }

  /**
   * Simulate task execution for testing (with proper cancellation)
   */
  async simulateTask(taskId, duration = 10000) {
    const task = await taskManager.getTask(taskId);
    if (!task) {
      throw new Error(`Task ${taskId} not found`);
    }

    this.runningTasks.set(taskId, true);

    // Create abort controller
    const abortController = new AbortController();
    this.abortControllers.set(taskId, abortController);

    // Update to running
    await taskManager.updateTask(taskId, { status: 'running' });

    // Store timeouts for cancellation
    const timeouts = [];
    this.simulationTimeouts.set(taskId, timeouts);

    try {
      // Simulate progress updates
      const steps = 10;
      const stepDuration = duration / steps;

      for (let i = 1; i <= steps; i++) {
        // Check if cancelled
        if (abortController.signal.aborted) {
          throw new Error('Simulation cancelled');
        }

        await new Promise((resolve, reject) => {
          const timeout = setTimeout(resolve, stepDuration);
          timeouts.push(timeout);

          // Listen for abort
          abortController.signal.addEventListener('abort', () => {
            clearTimeout(timeout);
            reject(new Error('Simulation cancelled'));
          }, { once: true });
        });

        // Update progress
        if (!abortController.signal.aborted) {
          await taskManager.updateTask(taskId, {
            progress: i * 10
          });
        }
      }

      // Complete task if not aborted
      if (!abortController.signal.aborted) {
        const result = {
          simulated: true,
          imagePath: `/imagedb/simulated/${taskId}.png`,
          message: 'This is a simulated result for testing'
        };

        await taskManager.updateTask(taskId, {
          status: 'completed',
          progress: 100,
          result
        });

        // 自动归档完成的模拟任务
        await taskArchiver.archiveTask(taskId);
      }
    } catch (error) {
      if (error.message.includes('cancelled')) {
        console.log(`Simulation ${taskId} was cancelled`);
        // Status already updated in cancelTask
      } else {
        await taskManager.updateTask(taskId, {
          status: 'failed',
          error: error.message
        });
        // 自动归档失败的模拟任务
        await taskArchiver.archiveTask(taskId);
      }
    } finally {
      this.runningTasks.delete(taskId);
      this.abortControllers.delete(taskId);
      this.simulationTimeouts.delete(taskId);
    }

    return await taskManager.getTask(taskId);
  }
}

// Export singleton instance
module.exports = new TaskExecutor();