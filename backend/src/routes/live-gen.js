'use strict';

const path = require('path');
const express = require('express');
const { randomUUID } = require('crypto');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/live-gen.json');

async function ensureDataFile() {
  try {
    await readJson(DATA_FILE);
  } catch {
    await writeJson(DATA_FILE, []);
  }
}

// List (with search and pagination)
router.get('/', async (req, res, next) => {
  try {
    await ensureDataFile();
    let items = await readJson(DATA_FILE);
    
    const { page = 1, pageSize = 10, q = '' } = req.query;
    const p = parseInt(page, 10) || 1;
    const ps = parseInt(pageSize, 10) || 10;
    
    if (q) {
      const lower = q.toLowerCase();
      items = items.filter(i => (i.prompt || '').toLowerCase().includes(lower));
    }
    
    // Sort by time desc
    items.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    
    const total = items.length;
    const start = (p - 1) * ps;
    const sliced = items.slice(start, start + ps);
    
    res.json({
      items: sliced,
      total,
      page: p,
      pageSize: ps
    });
  } catch (err) {
    next(err);
  }
});

// Add new record
router.post('/', async (req, res, next) => {
  try {
    await ensureDataFile();
    const items = await readJson(DATA_FILE);
    
    const { prompt, imagePath, imageUrls, modelId, modelName } = req.body;
    const now = new Date().toISOString();
    
    const newItem = {
      id: randomUUID(),
      prompt: prompt || '',
      imagePath: imagePath || '',
      imageUrls: Array.isArray(imageUrls) ? imageUrls : [], // reference images
      modelId: modelId || '',
      modelName: modelName || '',
      createdAt: now,
      dimensionScores: {} // Stores score per dimension ID
    };
    
    items.push(newItem);
    await writeJson(DATA_FILE, items);
    
    res.json(newItem);
  } catch (err) {
    next(err);
  }
});

// Update score (Patch)
router.patch('/:id/score', async (req, res, next) => {
  try {
    const { id } = req.params;
    const scores = req.body; // Expected { [dimId]: score }
    
    const items = await readJson(DATA_FILE);
    const idx = items.findIndex(x => x.id === id);
    
    if (idx === -1) return res.status(404).json({ error: 'not_found' });
    
    items[idx].dimensionScores = { 
        ...(items[idx].dimensionScores || {}),
        ...scores 
    };
    
    await writeJson(DATA_FILE, items);
    res.json(items[idx]);
  } catch (err) {
    next(err);
  }
});

// Delete
router.delete('/:id', async (req, res, next) => {
  try {
    const { id } = req.params;
    let items = await readJson(DATA_FILE);
    const initLen = items.length;
    items = items.filter(x => x.id !== id);
    
    if (items.length !== initLen) {
      await writeJson(DATA_FILE, items);
    }
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

module.exports = router;

