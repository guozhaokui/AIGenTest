'use strict';

const path = require('path');
const fs = require('fs/promises');
const { randomUUID } = require('crypto');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();

const BASE_DIR = path.resolve(__dirname, '../../data/runs');
const REGISTRY_FILE = path.resolve(__dirname, '../../data/runs.json');

async function ensureDir(p) {
  await fs.mkdir(p, { recursive: true });
}

router.post('/start', async (req, res, next) => {
  try {
    const { modelName, questionSetId, runName, runDesc } = req.body || {};
    const now = new Date().toISOString();
    const runId = `run_${now.replace(/[-:.TZ]/g, '').slice(0, 14)}_${Math.random().toString(36).slice(2, 6)}`;
    const runDir = path.join(BASE_DIR, runId);
    await ensureDir(runDir);
    const runMeta = {
      id: runId,
      modelName: modelName || '',
      questionSetId: questionSetId || '',
      runName: runName || '',
      runDesc: runDesc || '',
      itemIds: [],
      totalScore: null,
      dimensionScores: {},
      startedAt: now,
      endedAt: null
    };
    await writeJson(path.join(runDir, 'run.json'), runMeta);
    await writeJson(path.join(runDir, 'items.json'), []);
    // registry
    let reg = [];
    try { reg = await readJson(REGISTRY_FILE); } catch {}
    reg.push({ id: runId, modelName: runMeta.modelName, questionSetId: runMeta.questionSetId, runName: runMeta.runName, startedAt: now, endedAt: null });
    await writeJson(REGISTRY_FILE, reg);
    res.json(runMeta);
  } catch (err) {
    next(err);
  }
});

router.post('/:runId/items', async (req, res, next) => {
  try {
    const { runId } = req.params;
    const { questionId, scoresByDimension, comment, generatedImagePath } = req.body || {};
    if (!questionId) return res.status(400).json({ error: 'missing_questionId' });
    const runDir = path.join(BASE_DIR, runId);
    const itemsFile = path.join(runDir, 'items.json');
    const runFile = path.join(runDir, 'run.json');
    const now = new Date().toISOString();
    const id = randomUUID();
    const item = {
      id,
      runId,
      questionId,
      generatedImagePath: generatedImagePath || null,
      scoresByDimension: scoresByDimension || {},
      comment: comment || '',
      createdAt: now
    };
    let items = [];
    try { items = await readJson(itemsFile); } catch {}
    items.push(item);
    await writeJson(itemsFile, items);
    // update run meta itemIds
    let meta = await readJson(runFile);
    meta.itemIds = Array.from(new Set([...(meta.itemIds || []), id]));
    await writeJson(runFile, meta);
    res.json(item);
  } catch (err) {
    next(err);
  }
});

router.post('/:runId/finish', async (req, res, next) => {
  try {
    const { runId } = req.params;
    const { overallComment } = req.body || {};
    const runDir = path.join(BASE_DIR, runId);
    const itemsFile = path.join(runDir, 'items.json');
    const runFile = path.join(runDir, 'run.json');
    const items = await readJson(itemsFile);
    const dimTotals = {};
    let count = 0;
    for (const it of items) {
      const scores = it.scoresByDimension || {};
      for (const [dimId, score] of Object.entries(scores)) {
        if (!dimTotals[dimId]) dimTotals[dimId] = { sum: 0, n: 0 };
        dimTotals[dimId].sum += Number(score) || 0;
        dimTotals[dimId].n += 1;
        count += 1;
      }
    }
    const dimensionScores = {};
    for (const [dimId, { sum, n }] of Object.entries(dimTotals)) {
      dimensionScores[dimId] = n ? Number((sum / n).toFixed(3)) : 0;
    }
    const totalScore = count ? Number((Object.values(dimensionScores).reduce((a, b) => a + b, 0) / Object.keys(dimensionScores).length).toFixed(3)) : 0;
    const meta = await readJson(runFile);
    meta.dimensionScores = dimensionScores;
    meta.totalScore = totalScore;
    meta.endedAt = new Date().toISOString();
    if (typeof overallComment === 'string') {
      meta.overallComment = overallComment;
    }
    await writeJson(runFile, meta);
    // update registry endedAt
    let reg = [];
    try { reg = await readJson(REGISTRY_FILE); } catch {}
    const idx = reg.findIndex(r => r.id === runId);
    if (idx !== -1) {
      reg[idx] = { ...reg[idx], endedAt: meta.endedAt };
      await writeJson(REGISTRY_FILE, reg);
    }
    res.json(meta);
  } catch (err) {
    next(err);
  }
});

// 获取运行列表（registry）
router.get('/', async (_req, res, next) => {
  try {
    let reg = [];
    try { reg = await readJson(REGISTRY_FILE); } catch {}
    res.json(reg);
  } catch (err) {
    next(err);
  }
});

// 获取某次运行的元数据
router.get('/:runId', async (req, res, next) => {
  try {
    const { runId } = req.params;
    const meta = await readJson(path.join(BASE_DIR, runId, 'run.json'));
    res.json(meta);
  } catch (err) {
    next(err);
  }
});

// 获取某次运行的条目
router.get('/:runId/items', async (req, res, next) => {
  try {
    const { runId } = req.params;
    const items = await readJson(path.join(BASE_DIR, runId, 'items.json'));
    res.json(items);
  } catch (err) {
    next(err);
  }
});

module.exports = router;


