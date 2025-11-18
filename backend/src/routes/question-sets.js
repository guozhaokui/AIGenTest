'use strict';

const path = require('path');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/questionSets.json');

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
    const { name, description, dimensionIds, questionIds } = req.body || {};
    if (!name) return res.status(400).json({ error: 'missing_name' });
    const now = new Date().toISOString();
    const id = `set_${now.replace(/[-:.TZ]/g, '').slice(0, 12)}`;
    const record = {
      id,
      name,
      description: description || '',
      dimensionIds: Array.isArray(dimensionIds) ? dimensionIds : [],
      questionIds: Array.isArray(questionIds) ? questionIds : [],
      createdAt: now,
      updatedAt: now
    };
    const list = await readJson(DATA_FILE);
    list.push(record);
    await writeJson(DATA_FILE, list);
    res.json(record);
  } catch (err) {
    next(err);
  }
});

router.patch('/:id', async (req, res, next) => {
  try {
    const { id } = req.params;
    const list = await readJson(DATA_FILE);
    const idx = list.findIndex(x => x.id === id);
    if (idx === -1) return res.status(404).json({ error: 'not_found' });
    const now = new Date().toISOString();
    const current = list[idx];
    const nextObj = {
      ...current,
      ...req.body,
      updatedAt: now
    };
    list[idx] = nextObj;
    await writeJson(DATA_FILE, list);
    res.json(nextObj);
  } catch (err) {
    next(err);
  }
});

module.exports = router;


