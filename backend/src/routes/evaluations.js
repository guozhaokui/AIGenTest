'use strict';

const path = require('path');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/evaluations.json');

router.get('/', async (_req, res, next) => {
  try {
    const data = await readJson(DATA_FILE);
    res.json(data);
  } catch (err) {
    next(err);
  }
});

router.post('/', async (req, res, next) => {
  try {
    const { questionId, scores, scoresByDimension, comment, generatedImagePath, runId } = req.body || {};
    if (!questionId) return res.status(400).json({ error: 'missing_questionId' });
    const now = new Date().toISOString();
    const id = `ev_${now.replace(/[-:.TZ]/g, '').slice(0, 14)}`;
    const record = {
      id,
      runId: runId || null,
      questionId,
      generatedImagePath: generatedImagePath || null,
      scoresByDimension: scoresByDimension || scores || {},
      comment: comment || '',
      createdAt: now
    };
    const list = await readJson(DATA_FILE);
    list.push(record);
    await writeJson(DATA_FILE, list);
    res.json(record);
  } catch (err) {
    next(err);
  }
});

module.exports = router;


