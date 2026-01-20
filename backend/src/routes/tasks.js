const express = require('express');
const router = express.Router();
const taskManager = require('../services/taskManager');
const taskExecutor = require('../services/taskExecutor');
const taskArchiver = require('../services/taskArchiver');

/**
 * @api {post} /api/tasks Create a new task
 * @apiName CreateTask
 * @apiGroup Tasks
 *
 * @apiParam {String} type Task type (image, 3d, video, audio)
 * @apiParam {String} modelId Model identifier
 * @apiParam {String} driverId Driver identifier (google, meshy, ltx2, etc.)
 * @apiParam {String} prompt Generation prompt
 * @apiParam {Object} [params] Additional parameters for the driver
 * @apiParam {Object} [metadata] Additional metadata
 * @apiParam {Boolean} [execute=true] Whether to execute immediately
 */
router.post('/', async (req, res) => {
  try {
    const {
      type,
      modelId,
      driverId,
      prompt,
      params = {},
      metadata = {},
      execute = true
    } = req.body;

    // Validate required fields
    if (!type || !driverId || !prompt) {
      return res.status(400).json({
        error: 'Missing required fields: type, driverId, and prompt are required'
      });
    }

    // Create task
    const task = await taskManager.createTask({
      type,
      modelId,
      driverId,
      prompt,
      params,
      metadata
    });

    // Execute task if requested
    if (execute) {
      // Execute asynchronously (don't wait)
      taskExecutor.executeTask(task.id).catch(error => {
        console.error(`Failed to execute task ${task.id}:`, error);
      });
    }

    res.status(201).json(task);
  } catch (error) {
    console.error('Failed to create task:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/tasks Get all tasks
 * @apiName GetTasks
 * @apiGroup Tasks
 *
 * @apiParam {String} [status] Filter by status (pending, running, completed, failed, cancelled)
 * @apiParam {String} [type] Filter by type
 * @apiParam {String} [modelId] Filter by model ID
 */
router.get('/', async (req, res) => {
  try {
    const { status, type, modelId } = req.query;

    const filter = {};
    if (status) filter.status = status;
    if (type) filter.type = type;
    if (modelId) filter.modelId = modelId;

    const tasks = await taskManager.getTasks(filter);
    res.json(tasks);
  } catch (error) {
    console.error('Failed to get tasks:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/tasks/:id Get task by ID
 * @apiName GetTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 */
router.get('/:id', async (req, res) => {
  try {
    const task = await taskManager.getTask(req.params.id);

    if (!task) {
      return res.status(404).json({ error: 'Task not found' });
    }

    res.json(task);
  } catch (error) {
    console.error('Failed to get task:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {patch} /api/tasks/:id Update task
 * @apiName UpdateTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 * @apiParam {Object} updates Task updates
 */
router.patch('/:id', async (req, res) => {
  try {
    const task = await taskManager.updateTask(req.params.id, req.body);
    res.json(task);
  } catch (error) {
    console.error('Failed to update task:', error);
    if (error.message.includes('not found')) {
      res.status(404).json({ error: error.message });
    } else {
      res.status(500).json({ error: error.message });
    }
  }
});

/**
 * @api {delete} /api/tasks/:id Delete task
 * @apiName DeleteTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 */
router.delete('/:id', async (req, res) => {
  try {
    const deleted = await taskManager.deleteTask(req.params.id);

    if (!deleted) {
      return res.status(404).json({ error: 'Task not found' });
    }

    res.json({ message: 'Task deleted successfully' });
  } catch (error) {
    console.error('Failed to delete task:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {post} /api/tasks/:id/execute Execute a pending task
 * @apiName ExecuteTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 */
router.post('/:id/execute', async (req, res) => {
  try {
    const task = await taskManager.getTask(req.params.id);

    if (!task) {
      return res.status(404).json({ error: 'Task not found' });
    }

    if (task.status !== 'pending') {
      return res.status(400).json({
        error: `Task is ${task.status}, can only execute pending tasks`
      });
    }

    // Execute task asynchronously
    taskExecutor.executeTask(task.id).catch(error => {
      console.error(`Failed to execute task ${task.id}:`, error);
    });

    res.json({ message: 'Task execution started', taskId: task.id });
  } catch (error) {
    console.error('Failed to execute task:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {post} /api/tasks/:id/cancel Cancel a running task
 * @apiName CancelTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 */
router.post('/:id/cancel', async (req, res) => {
  try {
    const task = await taskExecutor.cancelTask(req.params.id);
    res.json(task);
  } catch (error) {
    console.error('Failed to cancel task:', error);
    if (error.message.includes('not found')) {
      res.status(404).json({ error: error.message });
    } else {
      res.status(500).json({ error: error.message });
    }
  }
});

/**
 * @api {post} /api/tasks/:id/simulate Simulate task execution (for testing)
 * @apiName SimulateTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 * @apiParam {Number} [duration=10000] Simulation duration in ms
 */
router.post('/:id/simulate', async (req, res) => {
  try {
    const { duration = 10000 } = req.body;

    const task = await taskManager.getTask(req.params.id);
    if (!task) {
      return res.status(404).json({ error: 'Task not found' });
    }

    // Start simulation asynchronously
    taskExecutor.simulateTask(task.id, duration).catch(error => {
      console.error(`Failed to simulate task ${task.id}:`, error);
    });

    res.json({ message: 'Task simulation started', taskId: task.id, duration });
  } catch (error) {
    console.error('Failed to simulate task:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/tasks/stats Get task statistics
 * @apiName GetTaskStats
 * @apiGroup Tasks
 */
router.get('/stats', async (req, res) => {
  try {
    const stats = await taskManager.getTaskStats();
    const executorStatus = taskExecutor.getStatus();

    res.json({
      ...stats,
      executor: executorStatus
    });
  } catch (error) {
    console.error('Failed to get task stats:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/tasks/:id/stream Server-Sent Events stream for task updates
 * @apiName StreamTask
 * @apiGroup Tasks
 *
 * @apiParam {String} id Task ID
 */
router.get('/:id/stream', async (req, res) => {
  const taskId = req.params.id;

  // Check if task exists
  const task = await taskManager.getTask(taskId);
  if (!task) {
    return res.status(404).json({ error: 'Task not found' });
  }

  // Set up SSE headers
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*'
  });

  // Send initial task state
  res.write(`data: ${JSON.stringify(task)}\n\n`);

  // Poll for updates
  const interval = setInterval(async () => {
    try {
      const updatedTask = await taskManager.getTask(taskId);

      if (!updatedTask) {
        res.write('event: error\ndata: {"error": "Task not found"}\n\n');
        clearInterval(interval);
        res.end();
        return;
      }

      // Send update
      res.write(`data: ${JSON.stringify(updatedTask)}\n\n`);

      // Stop streaming if task is complete
      if (updatedTask.status === 'completed' ||
          updatedTask.status === 'failed' ||
          updatedTask.status === 'cancelled') {
        res.write('event: complete\ndata: {"message": "Task finished"}\n\n');
        clearInterval(interval);
        res.end();
      }
    } catch (error) {
      console.error('Stream error:', error);
      res.write(`event: error\ndata: ${JSON.stringify({ error: error.message })}\n\n`);
      clearInterval(interval);
      res.end();
    }
  }, 1000); // Update every second

  // Clean up on client disconnect
  req.on('close', () => {
    clearInterval(interval);
  });
});

/**
 * @api {post} /api/tasks/cleanup Clean up old tasks
 * @apiName CleanupTasks
 * @apiGroup Tasks
 *
 * @apiParam {Number} [maxAge=86400000] Maximum age in milliseconds (default 24 hours)
 */
router.post('/cleanup', async (req, res) => {
  try {
    const { maxAge = 24 * 60 * 60 * 1000 } = req.body;
    const deletedCount = await taskManager.cleanupOldTasks(maxAge);

    res.json({
      message: `Cleaned up ${deletedCount} old tasks`,
      deletedCount
    });
  } catch (error) {
    console.error('Failed to cleanup tasks:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/tasks/archives Get archived tasks
 * @apiName GetArchivedTasks
 * @apiGroup Tasks
 *
 * @apiParam {String} [status] Filter by status
 * @apiParam {String} [type] Filter by type
 * @apiParam {String} [dateFrom] Filter by archive date from
 * @apiParam {String} [dateTo] Filter by archive date to
 * @apiParam {Number} [limit] Limit number of results
 */
router.get('/archives', async (req, res) => {
  try {
    const { status, type, dateFrom, dateTo, limit } = req.query;

    const filter = {};
    if (status) filter.status = status;
    if (type) filter.type = type;
    if (dateFrom) filter.dateFrom = dateFrom;
    if (dateTo) filter.dateTo = dateTo;
    if (limit) filter.limit = parseInt(limit);

    const archives = await taskArchiver.getArchivedTasks(filter);
    res.json(archives);
  } catch (error) {
    console.error('Failed to get archived tasks:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/tasks/archives/stats Get archive statistics
 * @apiName GetArchiveStats
 * @apiGroup Tasks
 */
router.get('/archives/stats', async (req, res) => {
  try {
    const stats = await taskArchiver.getArchiveStats();
    res.json(stats);
  } catch (error) {
    console.error('Failed to get archive stats:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {post} /api/tasks/archives/cleanup Clean up old archives
 * @apiName CleanupArchives
 * @apiGroup Tasks
 *
 * @apiParam {Number} [maxAge=2592000000] Maximum age in milliseconds (default 30 days)
 */
router.post('/archives/cleanup', async (req, res) => {
  try {
    const { maxAge = 30 * 24 * 60 * 60 * 1000 } = req.body;
    const deletedCount = await taskArchiver.cleanupOldArchives(maxAge);

    res.json({
      message: `Cleaned up ${deletedCount} old archived tasks`,
      deletedCount
    });
  } catch (error) {
    console.error('Failed to cleanup archives:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {post} /api/tasks/archives/all Archive all completed tasks
 * @apiName ArchiveAllCompleted
 * @apiGroup Tasks
 */
router.post('/archives/all', async (req, res) => {
  try {
    const archivedCount = await taskArchiver.archiveAllCompleted();

    res.json({
      message: `Archived ${archivedCount} completed tasks`,
      archivedCount
    });
  } catch (error) {
    console.error('Failed to archive all completed tasks:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {post} /api/tasks/archives/settings Update archive settings
 * @apiName UpdateArchiveSettings
 * @apiGroup Tasks
 *
 * @apiParam {Number} [delay] Archive delay in milliseconds
 */
router.post('/archives/settings', async (req, res) => {
  try {
    const { delay } = req.body;

    if (delay !== undefined) {
      taskArchiver.setArchiveDelay(delay);
    }

    res.json({
      message: 'Archive settings updated',
      settings: {
        delay: taskArchiver.archiveDelay
      }
    });
  } catch (error) {
    console.error('Failed to update archive settings:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;