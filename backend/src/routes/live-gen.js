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
    
    const { prompt, imagePath, imageUrls, modelId, modelName, params, duration, info3d, usage } = req.body;
    const now = new Date().toISOString();
    
    const newItem = {
      id: randomUUID(),
      prompt: prompt || '',
      imagePath: imagePath || '',
      imageUrls: Array.isArray(imageUrls) ? imageUrls : [], // reference images
      modelId: modelId || '',
      modelName: modelName || '',
      params: params || {}, // Store generation parameters
      duration: duration || 0, // Store generation duration in ms
      info3d: info3d || null, // Store 3D model info (modelDir, pbrPath, rgbPath, etc.)
      usage: usage || null, // Store token usage (completion_tokens, total_tokens)
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

// Upload thumbnail for 3D model
router.post('/:id/thumbnail', async (req, res, next) => {
  try {
    const { id } = req.params;
    const { dataUrl } = req.body;
    
    if (!dataUrl) {
      return res.status(400).json({ error: 'missing_dataUrl' });
    }
    
    const items = await readJson(DATA_FILE);
    const idx = items.findIndex(x => x.id === id);
    
    if (idx === -1) return res.status(404).json({ error: 'not_found' });
    
    // 解析 base64 数据
    const matches = dataUrl.match(/^data:image\/(\w+);base64,(.+)$/);
    if (!matches) {
      return res.status(400).json({ error: 'invalid_dataUrl' });
    }
    
    const ext = matches[1] === 'jpeg' ? 'jpg' : matches[1];
    const base64Data = matches[2];
    const buffer = Buffer.from(base64Data, 'base64');
    
    // 使用 modelDir 作为缩略图保存路径的基础
    const item = items[idx];
    const modelDir = item.info3d?.modelDir;
    
    if (!modelDir) {
      return res.status(400).json({ error: 'no_modelDir' });
    }
    
    // 保存到 modelDir 下的 thumbnail.jpg
    const fs = require('fs/promises');
    const relPath = modelDir.startsWith('/') ? modelDir.slice(1) : modelDir;
    const thumbnailPath = `${modelDir}/thumbnail.${ext}`;
    const absPath = path.resolve(__dirname, '../..', relPath, `thumbnail.${ext}`);
    
    await fs.writeFile(absPath, buffer);
    console.log(`[live-gen] Thumbnail saved: ${absPath}`);
    
    // 更新记录
    items[idx].thumbnailPath = thumbnailPath;
    await writeJson(DATA_FILE, items);
    
    res.json({ thumbnailPath });
  } catch (err) {
    next(err);
  }
});

// Delete
router.delete('/:id', async (req, res, next) => {
  try {
    const { id } = req.params;
    const { fullDelete } = req.query; // Check if full delete (including files) is requested
    
    let items = await readJson(DATA_FILE);
    const initLen = items.length;
    
    const targetItem = items.find(x => x.id === id);
    
    items = items.filter(x => x.id !== id);
    
    if (items.length !== initLen) {
      await writeJson(DATA_FILE, items);
      
      // Handle file deletion if requested
      // 注意：只删除生成的结果，不删除 imageUrls 中引用的输入图片
      if (fullDelete === 'true' && targetItem) {
          const fs = require('fs/promises');
          
          // 检查是否是3D模型（有 modelDir）
          if (targetItem.info3d && targetItem.info3d.modelDir) {
              try {
                  // 删除整个模型目录
                  let relPath = targetItem.info3d.modelDir;
                  if (relPath.startsWith('/')) relPath = relPath.slice(1);
                  const absPath = path.resolve(__dirname, '../..', relPath);
                  
                  // 递归删除目录
                  await fs.rm(absPath, { recursive: true, force: true });
                  console.log(`[live-gen] deleted 3D model directory: ${absPath}`);
                  
                  // 检查问题目录是否为空，如果是则也删除
                  const questionDir = path.dirname(absPath);
                  try {
                      const files = await fs.readdir(questionDir);
                      if (files.length === 0) {
                          await fs.rmdir(questionDir);
                          console.log(`[live-gen] deleted empty question directory: ${questionDir}`);
                      }
                  } catch (e) {
                      // 忽略
                  }
              } catch (e) {
                  console.warn(`[live-gen] failed to delete 3D model for ${id}:`, e.message);
              }
          } else if (targetItem.imagePath) {
              // 普通图片/音频，删除生成的文件
              try {
                  let relPath = targetItem.imagePath;
                  if (relPath.startsWith('/')) relPath = relPath.slice(1);
                  const absPath = path.resolve(__dirname, '../..', relPath);
                  
                  await fs.unlink(absPath);
                  console.log(`[live-gen] deleted file: ${absPath}`);
              } catch (e) {
                  console.warn(`[live-gen] failed to delete file for ${id}:`, e.message);
              }
          }
      }
    }
    res.json({ ok: true });
  } catch (err) {
    next(err);
  }
});

// Export resources
router.post('/:id/export', async (req, res, next) => {
  try {
    const { id } = req.params;
    const fs = require('fs/promises');
    
    const items = await readJson(DATA_FILE);
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
        console.log(`[live-gen] exported file: ${sourceAbsPath} -> ${targetAbsPath}`);
      } catch (e) {
        console.warn(`[live-gen] failed to export file ${sourceAbsPath}:`, e.message);
      }
    }
    
    // Export generated image
    if (targetItem.imagePath) {
      await copyToExports(targetItem.imagePath);
    }
    
    // Export reference images (imageUrls)
    if (Array.isArray(targetItem.imageUrls)) {
      for (const imageUrl of targetItem.imageUrls) {
        await copyToExports(imageUrl);
      }
    }
    
    res.json({ ok: true, message: 'Resources exported successfully' });
  } catch (err) {
    next(err);
  }
});

module.exports = router;

