'use strict';

const path = require('path');
const express = require('express');
const { randomUUID } = require('crypto');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();
const DATA_FILE = path.resolve(__dirname, '../../data/dimensions.json');

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
    const { id: incomingId, name, description, bonusCriteria, penaltyCriteria } = req.body || {};
    if (!name) return res.status(400).json({ error: 'missing_name' });
    const now = new Date().toISOString();
    let list = await readJson(DATA_FILE);

    // 如果传入了 id 且已存在，则视为“覆盖更新”（避免产生重复项）
    if (incomingId) {
      const idx = list.findIndex(x => x.id === incomingId);
      if (idx !== -1) {
        const current = list[idx];
        const nextObj = {
          ...current,
          name,
          description: description || '',
          bonusCriteria: Array.isArray(bonusCriteria) ? bonusCriteria : (typeof bonusCriteria === 'string' ? splitCriteria(bonusCriteria) : current.bonusCriteria || []),
          penaltyCriteria: Array.isArray(penaltyCriteria) ? penaltyCriteria : (typeof penaltyCriteria === 'string' ? splitCriteria(penaltyCriteria) : current.penaltyCriteria || []),
          updatedAt: now
        };
        list[idx] = nextObj;
        list = dedupeById(list);
        await writeJson(DATA_FILE, list);
        return res.json(nextObj);
      }
    }

    // 正常创建新维度
    const id = randomUUID();
    const record = {
      id,
      name,
      description: description || '',
      bonusCriteria: Array.isArray(bonusCriteria) ? bonusCriteria : (typeof bonusCriteria === 'string' ? splitCriteria(bonusCriteria) : []),
      penaltyCriteria: Array.isArray(penaltyCriteria) ? penaltyCriteria : (typeof penaltyCriteria === 'string' ? splitCriteria(penaltyCriteria) : []),
      createdAt: now,
      updatedAt: now
    };
    list.push(record);
    list = dedupeById(list);
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
      bonusCriteria: normalizeCriteria(req.body.bonusCriteria, current.bonusCriteria),
      penaltyCriteria: normalizeCriteria(req.body.penaltyCriteria, current.penaltyCriteria),
      updatedAt: now
    };
    list[idx] = nextObj;
    list = dedupeById(list);
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

function splitCriteria(text) {
  return text
    .split(/[\n,]/g)
    .map(s => s.trim())
    .filter(Boolean);
}
function normalizeCriteria(input, fallback) {
  if (Array.isArray(input)) return input;
  if (typeof input === 'string') return splitCriteria(input);
  return fallback;
}
function dedupeById(arr) {
  const seen = new Map();
  for (const item of arr) {
    seen.set(item.id, item);
  }
  return Array.from(seen.values());
}

module.exports = router;

