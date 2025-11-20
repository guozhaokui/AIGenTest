'use strict';

const path = require('path');
const fs = require('fs/promises');
const { randomUUID } = require('crypto');
const express = require('express');
const { readJson, writeJson } = require('../utils/jsonStore');

const router = express.Router();

const BASE_DIR = path.resolve(__dirname, '../../data/runs');
const QUESTIONS_FILE = path.resolve(__dirname, '../../data/questions.json');
const DIMENSIONS_FILE = path.resolve(__dirname, '../../data/dimensions.json');

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

    // 构造题目快照（避免题库后续变更影响历史回看）
    let questionSnapshot = null;
    try {
      const [allQuestions, allDims] = await Promise.all([
        readJson(QUESTIONS_FILE),
        readJson(DIMENSIONS_FILE)
      ]);
      const q = allQuestions.find(x => x.id === questionId);
      if (q) {
        const dimIds = Array.isArray(q.dimensionIds) ? q.dimensionIds : [];
        const dimNameMap = {};
        for (const did of dimIds) {
          const d = allDims.find(x => x.id === did);
          dimNameMap[did] = d ? d.name : did;
        }
        questionSnapshot = {
          id: q.id,
          prompt: q.prompt,
          dimensionIds: dimIds,
          scoringRule: q.scoringRule || '',
          dimNameMap,
          imageUrls: Array.isArray(q.imageUrls) ? q.imageUrls.filter(Boolean).slice(0, 3) : []
        };
        // 将本次评分里出现但快照中没有的维度名也写入快照，保证回看名称稳定
        if (scoresByDimension && typeof scoresByDimension === 'object') {
          for (const extraId of Object.keys(scoresByDimension)) {
            if (!(extraId in questionSnapshot.dimNameMap)) {
              const d = allDims.find(x => x.id === extraId);
              questionSnapshot.dimNameMap[extraId] = d ? d.name : extraId;
            }
          }
        }
      }
    } catch (e) {
      // ignore snapshot errors
    }
    const item = {
      id,
      runId,
      questionId,
      generatedImagePath: generatedImagePath || null,
      scoresByDimension: scoresByDimension || {},
      comment: comment || '',
      createdAt: now,
      questionSnapshot
    };
    let items = [];
    try { items = await readJson(itemsFile); } catch {}
    // 若为“重新评估”从 clone 过来的占位条目，尝试用同一 questionId 的空评分占位进行更新，避免重复
    let replaced = false;
    const idx = items.findIndex(it => it && it.questionId === questionId && (!it.scoresByDimension || Object.keys(it.scoresByDimension).length === 0));
    if (idx !== -1) {
      // 保留已有的 generatedImagePath（若本次也传入，则以本次为准）
      const prev = items[idx] || {};
      const next = {
        ...prev,
        ...item,
        id, // 确保有新 id
        generatedImagePath: item.generatedImagePath || prev.generatedImagePath || null
      };
      items[idx] = next;
      replaced = true;
    }
    if (!replaced) {
      items.push(item);
    }
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
    const QUESTION_SETS_FILE = path.resolve(__dirname, '../../data/questionSets.json');

    const items = await readJson(itemsFile);
    const meta = await readJson(runFile);

    // 维度累计总分（不做平均）
    const dimSums = {};
    for (const it of items) {
      const scores = it.scoresByDimension || {};
      for (const [dimId, score] of Object.entries(scores)) {
        if (!dimSums[dimId]) dimSums[dimId] = 0;
        dimSums[dimId] += Number(score) || 0;
      }
    }

    // 题目总数：优先取试题集的题目数，其次取已记录的条目数
    let totalQuestions = Array.isArray(items) ? items.length : 0;
    let dimensionUniverse = Object.keys(dimSums);
    try {
      if (meta?.questionSetId) {
        const sets = await readJson(QUESTION_SETS_FILE);
        const found = (sets || []).find(s => s.id === meta.questionSetId);
        if (found) {
          const qs = Array.isArray(found.questionIds) ? found.questionIds.length : 0;
          if (qs > 0) totalQuestions = qs;
          if (Array.isArray(found.dimensionIds) && found.dimensionIds.length) {
            dimensionUniverse = found.dimensionIds;
          }
        }
      }
    } catch {
      // ignore errors, fall back to items/dimSums
    }

    // 维度分 = 维度总分 / 总题目
    const dimensionScores = {};
    const denom = totalQuestions > 0 ? totalQuestions : 1; // 防止除0
    for (const dimId of dimensionUniverse) {
      const sum = dimSums[dimId] || 0;
      dimensionScores[dimId] = Number((sum / denom).toFixed(3));
    }

    // 总分 = 维度分之和 / 维度总数（使用参与本次试题集的维度）
    const dimCount = dimensionUniverse.length || Object.keys(dimensionScores).length;
    const totalScore = dimCount
      ? Number((Object.values(dimensionScores).reduce((a, b) => a + b, 0) / dimCount).toFixed(3))
      : 0;

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

// 删除某次运行（删除目录）
router.delete('/:runId', async (req, res, next) => {
  try {
    const { runId } = req.params;
    const dir = path.join(BASE_DIR, runId);
    // 仅允许删除 BASE_DIR 下的子目录
    if (!dir.startsWith(BASE_DIR)) return res.status(400).json({ error: 'invalid_path' });
    await fs.rm(dir, { recursive: true, force: true });
    res.json({ ok: true });
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
    // 实际更合理：把已有条目中的 questionId 与图片、题目快照拷贝，清空分数
    for (let i = 0; i < dstItems.length; i += 1) {
      const s = srcItems[i];
      if (!s) continue;
      dstItems[i].questionId = s.questionId;
      dstItems[i].generatedImagePath = s.generatedImagePath || null;
      if (s.questionSnapshot) {
        dstItems[i].questionSnapshot = s.questionSnapshot;
      }
    }

    await writeJson(path.join(dstDir, 'run.json'), dstMeta);
    await writeJson(path.join(dstDir, 'items.json'), dstItems);

    res.json(dstMeta);
  } catch (err) {
    next(err);
  }
});

module.exports = router;


