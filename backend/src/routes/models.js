'use strict';

const path = require('path');
const fs = require('fs/promises');
const express = require('express');
const { readJson } = require('../utils/jsonStore');

const router = express.Router();
const MODELS_FILE = path.resolve(__dirname, '../../data/models.json');
const MODEL_DB_DIR = path.resolve(__dirname, '../../modeldb');

router.get('/', async (_req, res, next) => {
  try {
    const list = await readJson(MODELS_FILE);
    res.json(list);
  } catch (err) {
    next(err);
  }
});

/**
 * 列出已生成的 3D 模型目录
 * 返回每个模型的缩略图、meta 信息等
 * 可选参数：
 * - driver: 过滤驱动类型（如 tripo）
 * - taskTypes: 过滤任务类型（逗号分隔，如 image_to_model,text_to_model）
 * - excludeVersions: 排除的模型版本（逗号分隔，如 v2.0,v2.5,v3.0）
 * - limit: 限制返回数量
 */
router.get('/generated', async (req, res, next) => {
  try {
    const { driver, taskTypes, excludeVersions, limit = 50 } = req.query;
    const items = [];
    
    // 解析过滤参数
    const taskTypeList = taskTypes ? taskTypes.split(',').map(t => t.trim()) : null;
    const excludeVersionList = excludeVersions ? excludeVersions.split(',').map(v => v.trim().toLowerCase()) : null;
    
    // 检查 modeldb 目录是否存在
    try {
      await fs.access(MODEL_DB_DIR);
    } catch {
      return res.json({ items: [] });
    }
    
    // 遍历 questionId 目录
    const questionDirs = await fs.readdir(MODEL_DB_DIR, { withFileTypes: true });
    
    for (const questionDir of questionDirs) {
      if (!questionDir.isDirectory()) continue;
      
      const questionPath = path.join(MODEL_DB_DIR, questionDir.name);
      const resultDirs = await fs.readdir(questionPath, { withFileTypes: true });
      
      for (const resultDir of resultDirs) {
        if (!resultDir.isDirectory()) continue;
        
        const resultPath = path.join(questionPath, resultDir.name);
        const metaPath = path.join(resultPath, 'meta.json');
        
        // 尝试读取 meta.json
        let meta = null;
        try {
          const metaContent = await fs.readFile(metaPath, 'utf-8');
          meta = JSON.parse(metaContent);
        } catch {
          // 没有 meta.json，跳过
          continue;
        }
        
        // 根据 driver 过滤
        if (driver && meta.driver !== driver) {
          continue;
        }
        
        // 根据 taskType 过滤
        if (taskTypeList && taskTypeList.length > 0) {
          if (!taskTypeList.includes(meta.taskType)) {
            continue;
          }
        }
        
        // 根据 modelVersion 排除
        if (excludeVersionList && excludeVersionList.length > 0) {
          const metaVersion = (meta.modelVersion || '').toLowerCase();
          // 检查是否包含排除的版本前缀
          const shouldExclude = excludeVersionList.some(ev => {
            if (metaVersion === ev) return true;
            if (metaVersion.startsWith(ev)) return true;
            // 特殊处理 "default"，它通常意味着最新版本
            if (ev === 'default' && metaVersion === 'default') return true;
            return false;
          });
          if (shouldExclude) {
            continue;
          }
        }
        
        // 查找缩略图
        let thumbnail = null;
        const possibleThumbnails = ['thumbnail.jpg', 'thumbnail.png', 'preview.png', 'preview.jpg'];
        for (const thumbName of possibleThumbnails) {
          try {
            await fs.access(path.join(resultPath, thumbName));
            thumbnail = `/modeldb/${questionDir.name}/${resultDir.name}/${thumbName}`;
            break;
          } catch {
            // 继续尝试下一个
          }
        }
        
        items.push({
          questionId: questionDir.name,
          resultId: resultDir.name,
          modelDir: `/modeldb/${questionDir.name}/${resultDir.name}`,
          thumbnail,
          meta,
          createdAt: meta.createdAt || null
        });
        
        // 检查数量限制
        if (items.length >= parseInt(limit)) {
          break;
        }
      }
      
      if (items.length >= parseInt(limit)) {
        break;
      }
    }
    
    // 按创建时间倒序排列
    items.sort((a, b) => {
      const dateA = a.createdAt ? new Date(a.createdAt) : new Date(0);
      const dateB = b.createdAt ? new Date(b.createdAt) : new Date(0);
      return dateB - dateA;
    });
    
    res.json({ items });
  } catch (err) {
    console.error('[models] Error listing generated models:', err);
    next(err);
  }
});

module.exports = router;


