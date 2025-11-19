'use strict';

const path = require('path');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');
const { randomUUID } = require('crypto');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/questions.json');

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
    const { prompt, dimensionIds, scoringRule, exampleIds } = req.body || {};
    if (!prompt) return res.status(400).json({ error: 'missing_prompt' });
    const now = new Date().toISOString();
    const id = randomUUID();
    const record = {
      id,
      prompt,
      dimensionIds: Array.isArray(dimensionIds) ? dimensionIds : [],
      scoringRule: scoringRule || '',
      exampleIds: Array.isArray(exampleIds) ? exampleIds : [],
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

router.delete('/:id', async (req, res, next) => {
  try {
    const { id } = req.params;
    const list = await readJson(DATA_FILE);
    const idx = list.findIndex(x => x.id === id);
    if (idx === -1) return res.status(404).json({ error: 'not_found' });
    const [removed] = list.splice(idx, 1);
    await writeJson(DATA_FILE, list);
    res.json({ ok: true, removed });
  } catch (err) {
    next(err);
  }
});

module.exports = router;


