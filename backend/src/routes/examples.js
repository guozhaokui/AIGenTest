'use strict';

const path = require('path');
const fs = require('fs/promises');
const express = require('express');
const multer = require('multer');
const crypto = require('crypto');

const router = express.Router();

const UPLOAD_DIR = path.resolve(__dirname, '../../imagedb');
const storage = multer.memoryStorage();
const upload = multer({ storage });

router.post('/upload', upload.single('file'), async (req, res, next) => {
  try {
    const file = req.file;
    if (!file) return res.status(400).json({ error: 'no_file' });
    const hash = crypto.createHash('md5').update(file.buffer).digest('hex');
    const sub1 = hash.slice(0, 2);
    const sub2 = hash.slice(2, 4);
    // 传入原始文件名以推断扩展名（尤其是 .glb 等 3D 模型）
    const ext = mimeToExt(file.mimetype, file.originalname);
    const dir = path.join(UPLOAD_DIR, sub1, sub2);
    await fs.mkdir(dir, { recursive: true });
    const filename = `${hash}${ext}`;
    const abs = path.join(dir, filename);
    await fs.writeFile(abs, file.buffer);
    // 返回以 /imagedb 开头的路径
    const rel = path.relative(path.resolve(__dirname, '../..'), abs).replace(/\\/g, '/');
    const publicPath = rel.startsWith('imagedb/') ? `/${rel}` : `/imagedb/${rel}`;
    // 同时返回 mimeType 供前端使用
    res.json({ 
      path: publicPath,
      mimeType: file.mimetype,
      originalName: file.originalname,
      size: file.size
    });
  } catch (err) {
    next(err);
  }
});

function mimeToExt(mime, originalName) {
  // 图片类型
  if (mime === 'image/png') return '.png';
  if (mime === 'image/jpeg') return '.jpg';
  if (mime === 'image/webp') return '.webp';
  if (mime === 'image/gif') return '.gif';
  
  // 3D 模型类型
  if (mime === 'model/gltf-binary' || originalName?.endsWith('.glb')) return '.glb';
  if (mime === 'model/gltf+json' || originalName?.endsWith('.gltf')) return '.gltf';
  if (originalName?.endsWith('.fbx')) return '.fbx';
  if (originalName?.endsWith('.obj')) return '.obj';
  
  // 其他二进制文件
  if (mime === 'application/octet-stream') {
    // 尝试从原始文件名推断扩展名
    if (originalName) {
      const ext = originalName.match(/\.[^.]+$/);
      if (ext) return ext[0].toLowerCase();
    }
  }
  
  return '';
}

module.exports = router;


