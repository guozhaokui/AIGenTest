const express = require('express');
const router = express.Router();
const database = require('../services/database');

/**
 * @api {get} /api/generations Get AI generation history
 * @apiName GetGenerations
 * @apiGroup Generations
 *
 * @apiParam {Number} [limit=100] Maximum number of records to return
 * @apiParam {String} [type] Filter by generation type (image, 3d, video, audio)
 */
router.get('/', async (req, res) => {
  try {
    await database.init();

    const limit = parseInt(req.query.limit) || 100;
    const filter = {};
    if (req.query.type) {
      filter.type = req.query.type;
    }

    const generations = await database.getGenerations(limit, filter);
    res.json(generations);
  } catch (error) {
    console.error('Failed to get generations:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/generations/stats Get generation statistics
 * @apiName GetGenerationStats
 * @apiGroup Generations
 */
router.get('/stats', async (req, res) => {
  try {
    await database.init();
    const stats = await database.getStats();
    res.json(stats);
  } catch (error) {
    console.error('Failed to get generation stats:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {get} /api/generations/info Get database information
 * @apiName GetDatabaseInfo
 * @apiGroup Generations
 */
router.get('/info', async (req, res) => {
  try {
    await database.init();
    const info = database.getDatabaseInfo();
    res.json(info);
  } catch (error) {
    console.error('Failed to get database info:', error);
    res.status(500).json({ error: error.message });
  }
});

/**
 * @api {post} /api/generations/cleanup Clean up old generation records
 * @apiName CleanupGenerations
 * @apiGroup Generations
 *
 * @apiParam {Number} [daysToKeep=30] Number of days to keep records
 */
router.post('/cleanup', async (req, res) => {
  try {
    await database.init();

    const daysToKeep = parseInt(req.body.daysToKeep) || 30;
    const result = await database.cleanup(daysToKeep);

    res.json({
      message: `Cleaned up ${result.generations} generation records and ${result.archivedTasks} archived tasks`,
      ...result
    });
  } catch (error) {
    console.error('Failed to cleanup generations:', error);
    res.status(500).json({ error: error.message });
  }
});

module.exports = router;