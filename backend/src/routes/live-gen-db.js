'use strict';

const path = require('path');
const express = require('express');
const { randomUUID } = require('crypto');
const database = require('../services/database');
const { readJson } = require('../utils/jsonStore');

const router = express.Router();

// 初始化数据库
async function ensureDatabase() {
  await database.init();
}

// List (with search and pagination) - 兼容原接口
router.get('/', async (req, res, next) => {
  try {
    await ensureDatabase();

    const { page = 1, pageSize = 10, q = '', modelId = '' } = req.query;
    const p = parseInt(page, 10) || 1;
    const ps = parseInt(pageSize, 10) || 10;

    // 获取所有记录（后续可优化为SQL查询）
    let items = await database.getGenerations(1000);

    // 按模型 ID 过滤
    if (modelId) {
      items = items.filter(i => i.model_id === modelId || i.modelId === modelId);
    }

    // 搜索
    if (q) {
      const lower = q.toLowerCase();
      items = items.filter(i => (i.prompt || '').toLowerCase().includes(lower));
    }

    // 转换字段名以保持兼容性
    items = items.map(item => ({
      id: item.id,
      prompt: item.prompt,
      imagePath: item.result?.imagePath || item.result?.videoPath || item.result?.modelPath || '',
      imageUrls: item.result?.imageUrls || [],
      modelId: item.model_id || item.modelId,
      modelName: item.result?.modelName || '',
      params: item.params || {},
      duration: item.result?.duration || 0,
      info3d: item.result?.info3d || null,
      infoVideo: item.result?.infoVideo || null,
      usage: item.result?.usage || null,
      createdAt: item.created_at || item.createdAt,
      dimensionScores: item.result?.dimensionScores || {},
      comment: item.result?.comment,
      thumbnailPath: item.result?.thumbnailPath
    }));

    // Sort by time desc (already sorted from database)

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

// Add new record - 保存到数据库
router.post('/', async (req, res, next) => {
  try {
    await ensureDatabase();

    const { prompt, imagePath, imageUrls, modelId, modelName, params, duration, info3d, infoVideo, usage } = req.body;
    const now = new Date().toISOString();

    // 根据模型的 input 配置决定是否保存 prompt
    let effectivePrompt = prompt || '';

    if (modelId) {
      try {
        const MODELS_FILE = path.resolve(__dirname, '../../data/models.json');
        const models = await readJson(MODELS_FILE);
        const model = models.find(m => m.id === modelId);

        // 如果模型只支持图片输入（不支持文本），则清空 prompt
        if (model && model.input) {
          const types = model.input.types || [];
          const supportsText = types.includes('text');
          if (!supportsText) {
            effectivePrompt = '';
            console.log(`[live-gen-db] Model ${modelId} is image-only, clearing prompt`);
          }
        }
      } catch (e) {
        console.warn('[live-gen-db] Failed to read model config:', e.message);
      }
    }

    // 确定类型
    let type = 'unknown';
    if (info3d) {
      type = '3d';
    } else if (infoVideo) {
      type = 'video';
    } else if (imagePath && imagePath.includes('/sounddb/')) {
      type = 'audio';
    } else if (imagePath) {
      type = 'image';
    }

    const newItem = {
      id: randomUUID(),
      type,
      modelId: modelId || '',
      driverId: modelId ? modelId.split('_')[0] : '', // 从modelId推断driverId
      prompt: effectivePrompt,
      params: params || {},
      result: {
        imagePath: imagePath || '',
        imageUrls: Array.isArray(imageUrls) ? imageUrls : [],
        modelName: modelName || '',
        duration: duration || 0,
        info3d: info3d || null,
        infoVideo: infoVideo || null,
        usage: usage || null,
        dimensionScores: {}
      },
      status: 'completed',
      createdAt: now,
      completedAt: now,
      metadata: {}
    };

    // 保存到数据库
    await database.saveGeneration(newItem);

    // 返回兼容格式
    res.json({
      id: newItem.id,
      prompt: newItem.prompt,
      imagePath: imagePath || '',
      imageUrls: Array.isArray(imageUrls) ? imageUrls : [],
      modelId: modelId || '',
      modelName: modelName || '',
      params: params || {},
      duration: duration || 0,
      info3d: info3d || null,
      infoVideo: infoVideo || null,
      usage: usage || null,
      createdAt: now,
      dimensionScores: {}
    });
  } catch (err) {
    next(err);
  }
});

// Update score (Patch) - 需要更新数据库记录
router.patch('/:id/score', async (req, res, next) => {
  try {
    await ensureDatabase();
    const { id } = req.params;
    const { comment, ...scores } = req.body;

    // 获取现有记录
    const items = await database.getGenerations(1000);
    const item = items.find(x => x.id === id);

    if (!item) {
      return res.status(404).json({ error: 'not_found' });
    }

    // 更新记录
    const updatedResult = {
      ...item.result,
      dimensionScores: {
        ...(item.result?.dimensionScores || {}),
        ...scores
      }
    };

    if (comment !== undefined) {
      updatedResult.comment = comment;
    }

    // 更新数据库
    const updated = await database.updateGeneration(id, {
      result: updatedResult
    });

    if (!updated) {
      return res.status(500).json({ error: 'update_failed' });
    }

    // 返回更新后的记录（兼容格式）
    res.json({
      id: item.id,
      prompt: item.prompt,
      imagePath: item.result?.imagePath || '',
      imageUrls: item.result?.imageUrls || [],
      modelId: item.model_id || item.modelId,
      modelName: item.result?.modelName || '',
      params: item.params || {},
      duration: item.result?.duration || 0,
      info3d: item.result?.info3d || null,
      infoVideo: item.result?.infoVideo || null,
      usage: item.result?.usage || null,
      createdAt: item.created_at || item.createdAt,
      dimensionScores: updatedResult.dimensionScores,
      comment: updatedResult.comment
    });
  } catch (err) {
    next(err);
  }
});

// Upload thumbnail for 3D model - 保持原逻辑，更新数据库
router.post('/:id/thumbnail', async (req, res, next) => {
  try {
    await ensureDatabase();
    const { id } = req.params;
    const { dataUrl } = req.body;

    if (!dataUrl) {
      return res.status(400).json({ error: 'missing_dataUrl' });
    }

    // 获取记录
    const items = await database.getGenerations(1000);
    const item = items.find(x => x.id === id);

    if (!item) {
      return res.status(404).json({ error: 'not_found' });
    }

    // 解析 base64 数据
    const matches = dataUrl.match(/^data:image\/(\w+);base64,(.+)$/);
    if (!matches) {
      return res.status(400).json({ error: 'invalid_dataUrl' });
    }

    const ext = matches[1] === 'jpeg' ? 'jpg' : matches[1];
    const base64Data = matches[2];
    const buffer = Buffer.from(base64Data, 'base64');

    // 使用 modelDir 作为缩略图保存路径的基础
    const modelDir = item.result?.info3d?.modelDir;

    if (!modelDir) {
      return res.status(400).json({ error: 'no_modelDir' });
    }

    // 保存到 modelDir 下的 thumbnail.jpg
    const fs = require('fs/promises');
    const relPath = modelDir.startsWith('/') ? modelDir.slice(1) : modelDir;
    const thumbnailPath = `${modelDir}/thumbnail.${ext}`;
    const absPath = path.resolve(__dirname, '../..', relPath, `thumbnail.${ext}`);

    await fs.writeFile(absPath, buffer);
    console.log(`[live-gen-db] Thumbnail saved: ${absPath}`);

    // TODO: 更新数据库记录

    res.json({ thumbnailPath });
  } catch (err) {
    next(err);
  }
});

// Delete - 从数据库删除（文件删除保持原逻辑）
router.delete('/:id', async (req, res, next) => {
  try {
    await ensureDatabase();
    const { id } = req.params;
    const { fullDelete } = req.query;

    // 获取要删除的记录
    const items = await database.getGenerations(1000);
    const targetItem = items.find(x => x.id === id);

    if (!targetItem) {
      return res.status(404).json({ error: 'not_found' });
    }

    // 从数据库删除记录
    const deleted = await database.deleteGenerationById(id);
    if (!deleted) {
      return res.status(500).json({ error: 'delete_failed' });
    }

    // 处理文件删除（如果需要）
    if (fullDelete === 'true' && targetItem) {
      const fs = require('fs/promises');

      // 检查是否是3D模型（有 modelDir）
      if (targetItem.result?.info3d?.modelDir) {
        try {
          let relPath = targetItem.result.info3d.modelDir;
          if (relPath.startsWith('/')) relPath = relPath.slice(1);
          const absPath = path.resolve(__dirname, '../..', relPath);

          await fs.rm(absPath, { recursive: true, force: true });
          console.log(`[live-gen-db] deleted 3D model directory: ${absPath}`);

          // 检查问题目录是否为空
          const questionDir = path.dirname(absPath);
          try {
            const files = await fs.readdir(questionDir);
            if (files.length === 0) {
              await fs.rmdir(questionDir);
              console.log(`[live-gen-db] deleted empty question directory: ${questionDir}`);
            }
          } catch (e) {
            // 忽略
          }
        } catch (e) {
          console.warn(`[live-gen-db] failed to delete 3D model for ${id}:`, e.message);
        }
      }
      // 检查是否是视频
      else if (targetItem.result?.infoVideo?.videoDir) {
        try {
          let relPath = targetItem.result.infoVideo.videoDir;
          if (relPath.startsWith('/')) relPath = relPath.slice(1);
          const absPath = path.resolve(__dirname, '../..', relPath);

          await fs.rm(absPath, { recursive: true, force: true });
          console.log(`[live-gen-db] deleted video directory: ${absPath}`);

          // 检查问题目录是否为空
          const questionDir = path.dirname(absPath);
          try {
            const files = await fs.readdir(questionDir);
            if (files.length === 0) {
              await fs.rmdir(questionDir);
              console.log(`[live-gen-db] deleted empty question directory: ${questionDir}`);
            }
          } catch (e) {
            // 忽略
          }
        } catch (e) {
          console.warn(`[live-gen-db] failed to delete video for ${id}:`, e.message);
        }
      }
      else if (targetItem.result?.imagePath) {
        // 普通图片/音频，删除生成的文件
        try {
          let relPath = targetItem.result.imagePath;
          if (relPath.startsWith('/')) relPath = relPath.slice(1);
          const absPath = path.resolve(__dirname, '../..', relPath);

          await fs.unlink(absPath);
          console.log(`[live-gen-db] deleted file: ${absPath}`);
        } catch (e) {
          console.warn(`[live-gen-db] failed to delete file for ${id}:`, e.message);
        }
      }
    }

    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

// Export resources - 保持原逻辑
router.post('/:id/export', async (req, res, next) => {
  try {
    await ensureDatabase();
    const { id } = req.params;
    const fs = require('fs/promises');

    const items = await database.getGenerations(1000);
    const targetItem = items.find(x => x.id === id);

    if (!targetItem) {
      return res.status(404).json({ error: 'not_found' });
    }

    const exportsDir = path.resolve(__dirname, '../../exports');

    // Ensure exports directory exists
    await fs.mkdir(exportsDir, { recursive: true });

    // Function to copy a file to exports directory
    async function copyToExports(sourcePath) {
      if (!sourcePath) return;

      let relPath = String(sourcePath);

      // Normalize path - remove leading slashes
      if (relPath.startsWith('/')) {
        relPath = relPath.slice(1);
      }

      // All images go to exports/imagedb/ with same structure
      const targetDir = path.resolve(exportsDir, 'imagedb');

      const sourceAbsPath = path.resolve(__dirname, '../../', relPath);
      const targetAbsPath = path.resolve(targetDir, relPath.replace(/^imagedb\//, ''));

      try {
        // Ensure target directory exists
        await fs.mkdir(path.dirname(targetAbsPath), { recursive: true });

        // Copy file
        await fs.copyFile(sourceAbsPath, targetAbsPath);
        console.log(`[live-gen-db] exported file: ${sourceAbsPath} -> ${targetAbsPath}`);
      } catch (e) {
        console.warn(`[live-gen-db] failed to export file ${sourceAbsPath}:`, e.message);
      }
    }

    // Function to recursively copy a directory to exports
    async function copyDirToExports(sourceDir, targetBaseDir) {
      if (!sourceDir) return;

      let relPath = String(sourceDir);

      // Normalize path - remove leading slashes
      if (relPath.startsWith('/')) {
        relPath = relPath.slice(1);
      }

      const sourceAbsPath = path.resolve(__dirname, '../../', relPath);
      const targetAbsPath = path.resolve(targetBaseDir, relPath);

      try {
        // Check if source exists and is a directory
        const stat = await fs.stat(sourceAbsPath);
        if (!stat.isDirectory()) {
          // If it's a file, just copy it
          await fs.mkdir(path.dirname(targetAbsPath), { recursive: true });
          await fs.copyFile(sourceAbsPath, targetAbsPath);
          console.log(`[live-gen-db] exported file: ${sourceAbsPath} -> ${targetAbsPath}`);
          return;
        }

        // Ensure target directory exists
        await fs.mkdir(targetAbsPath, { recursive: true });

        // Read all files in source directory
        const entries = await fs.readdir(sourceAbsPath, { withFileTypes: true });

        for (const entry of entries) {
          const srcPath = path.join(sourceAbsPath, entry.name);
          const dstPath = path.join(targetAbsPath, entry.name);

          if (entry.isDirectory()) {
            // Recursively copy subdirectory
            await copyDirToExports(path.join(relPath, entry.name), targetBaseDir);
          } else {
            // Copy file
            await fs.copyFile(srcPath, dstPath);
            console.log(`[live-gen-db] exported file: ${srcPath} -> ${dstPath}`);
          }
        }

        console.log(`[live-gen-db] exported directory: ${sourceAbsPath} -> ${targetAbsPath}`);
      } catch (e) {
        console.warn(`[live-gen-db] failed to export directory ${sourceAbsPath}:`, e.message);
      }
    }

    // Export 3D model directory if exists
    if (targetItem.result?.info3d?.modelDir) {
      await copyDirToExports(targetItem.result.info3d.modelDir, exportsDir);
    }

    // Export video directory if exists
    if (targetItem.result?.infoVideo?.videoDir) {
      await copyDirToExports(targetItem.result.infoVideo.videoDir, exportsDir);
    }

    // Export generated image
    if (targetItem.result?.imagePath) {
      await copyToExports(targetItem.result.imagePath);
    }

    // Export reference images (imageUrls)
    if (Array.isArray(targetItem.result?.imageUrls)) {
      for (const imageUrl of targetItem.result.imageUrls) {
        await copyToExports(imageUrl);
      }
    }

    res.json({ ok: true, message: 'Resources exported successfully' });
  } catch (err) {
    next(err);
  }
});

module.exports = router;