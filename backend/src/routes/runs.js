'use strict';

const path = require('path');
const fs = require('fs/promises');
const { randomUUID } = require('crypto');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();

const BASE_DIR = path.resolve(__dirname, '../../data/runs');

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
    res.json(meta);
  } catch (err) {
    next(err);
  }
});

// 获取运行列表（registry）
router.get('/', async (_req, res, next) => {
  try {
    await ensureDir(BASE_DIR);
    const entries = await fs.readdir(BASE_DIR, { withFileTypes: true });
    const metas = [];
    for (const ent of entries) {
      if (!ent.isDirectory()) continue;
      const dir = path.join(BASE_DIR, ent.name);
      const runFile = path.join(dir, 'run.json');
      try {
        const meta = await readJson(runFile);
        // 仅返回列表需要的字段（也可直接返回全部）
        metas.push({
          id: meta.id || ent.name,
          runName: meta.runName || '',
          modelName: meta.modelName || '',
          questionSetId: meta.questionSetId || '',
          startedAt: meta.startedAt || null,
          endedAt: meta.endedAt || null
        });
      } catch {
        // ignore invalid dirs
      }
    }
    metas.sort((a, b) => String(b.startedAt || '').localeCompare(String(a.startedAt || '')));
    res.json(metas);
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

// 克隆某次运行（重新评估用）
router.post('/:runId/clone', async (req, res, next) => {
  try {
    const { runId } = req.params;
    const { runName } = req.body || {};
    const srcDir = path.join(BASE_DIR, runId);
    const srcMeta = await readJson(path.join(srcDir, 'run.json'));
    const srcItems = await readJson(path.join(srcDir, 'items.json'));

    const now = new Date().toISOString();
    const newId = `run_${now.replace(/[-:.TZ]/g, '').slice(0, 14)}_${Math.random().toString(36).slice(2, 6)}`;
    const dstDir = path.join(BASE_DIR, newId);
    await ensureDir(dstDir);

    const dstMeta = {
      id: newId,
      modelName: srcMeta.modelName || '',
      questionSetId: srcMeta.questionSetId || '',
      runName: runName || `${srcMeta.runName || ''}_retry`,
      runDesc: srcMeta.runDesc || '',
      itemIds: [],
      totalScore: null,
      dimensionScores: {},
      startedAt: now,
      endedAt: null,
      overallComment: ''
    };
    const dstItems = (srcItems || []).map(() => ({
      // 评分与评论清空，图片路径沿用
      id: undefined, // 让后续新增时生成新的 itemId；这里仅作为占位展示
      runId: newId,
      questionId: undefined,
      generatedImagePath: undefined,
      scoresByDimension: {},
      comment: '',
      createdAt: now
    }));
    // 实际更合理：把已有条目中的 questionId 与图片拷贝，清空分数
    for (let i = 0; i < dstItems.length; i += 1) {
      const s = srcItems[i];
      if (!s) continue;
      dstItems[i].questionId = s.questionId;
      dstItems[i].generatedImagePath = s.generatedImagePath || null;
    }

    await writeJson(path.join(dstDir, 'run.json'), dstMeta);
    await writeJson(path.join(dstDir, 'items.json'), dstItems);

    res.json(dstMeta);
  } catch (err) {
    next(err);
  }
});

module.exports = router;


