'use strict';

const path = require('path');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');
const { randomUUID } = require('crypto');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/questions.json');

router.get('/', async (req, res, next) => {
  try {
    const list = await readJson(DATA_FILE);
    // 分页与搜索
    const page = Math.max(parseInt(req.query.page, 10) || 1, 1);
    const pageSize = Math.min(Math.max(parseInt(req.query.pageSize, 10) || 10, 1), 200);
    const q = (req.query.q || '').toString().trim();
    let filtered = list;
    if (q) {
      const kw = q.toLowerCase();
      filtered = list.filter(it => (it.prompt || '').toLowerCase().includes(kw));
    }
    const total = filtered.length;
    const start = (page - 1) * pageSize;
    const items = filtered.slice(start, start + pageSize);
    res.json({ items, total, page, pageSize });
  } catch (err) {
    next(err);
  }
});

router.post('/', async (req, res, next) => {
  try {
    const { prompt, dimensionIds, scoringRule, exampleIds, imageUrls } = req.body || {};
    if (!prompt) return res.status(400).json({ error: 'missing_prompt' });
    const now = new Date().toISOString();
    const id = randomUUID();
    const images = Array.isArray(imageUrls) ? imageUrls.map(x => String(x)).filter(Boolean).slice(0, 3) : [];
    const record = {
      id,
      prompt,
      dimensionIds: Array.isArray(dimensionIds) ? dimensionIds : [],
      scoringRule: scoringRule || '',
      exampleIds: Array.isArray(exampleIds) ? exampleIds : [],
      imageUrls: images,
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
  let images = undefined;
  if (req.body && 'imageUrls' in req.body) {
    const raw = req.body.imageUrls;
    images = Array.isArray(raw) ? raw.map(x => String(x)).filter(Boolean).slice(0, 3) : [];
  }
    const nextObj = {
      ...current,
      ...req.body,
    ...(images !== undefined ? { imageUrls: images } : {}),
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

// 复制问题（生成新 UUID）
router.post('/:id/clone', async (req, res, next) => {
  try {
    const { id } = req.params;
    const list = await readJson(DATA_FILE);
    const src = list.find(x => x.id === id);
    if (!src) return res.status(404).json({ error: 'not_found' });
    const now = new Date().toISOString();
    const newQ = {
      ...src,
      id: randomUUID(),
    imageUrls: Array.isArray(src.imageUrls) ? src.imageUrls.slice(0, 3) : [],
      createdAt: now,
      updatedAt: now
    };
    list.push(newQ);
    await writeJson(DATA_FILE, list);
    res.json(newQ);
  } catch (err) {
    next(err);
  }
});

module.exports = router;


