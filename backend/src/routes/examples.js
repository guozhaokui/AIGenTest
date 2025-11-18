'use strict';

const path = require('path');
const fs = require('fs/promises');
const express = require('express');
const multer = require('multer');
const crypto = require('crypto');

const router = express.Router();

const UPLOAD_DIR = path.resolve(__dirname, '../../uploads/examples');
const storage = multer.memoryStorage();
const upload = multer({ storage });

router.post('/upload', upload.single('file'), async (req, res, next) => {
  try {
    const file = req.file;
    if (!file) return res.status(400).json({ error: 'no_file' });
    const hash = crypto.createHash('md5').update(file.buffer).digest('hex');
    const sub1 = hash.slice(0, 2);
    const sub2 = hash.slice(2, 4);
    const ext = mimeToExt(file.mimetype);
    const dir = path.join(UPLOAD_DIR, sub1, sub2);
    await fs.mkdir(dir, { recursive: true });
    const filename = `${hash}${ext}`;
    const abs = path.join(dir, filename);
    await fs.writeFile(abs, file.buffer);
    const rel = path.relative(process.cwd(), abs).replace(/\\/g, '/');
    res.json({ path: rel });
  } catch (err) {
    next(err);
  }
});

function mimeToExt(mime) {
  if (mime === 'image/png') return '.png';
  if (mime === 'image/jpeg') return '.jpg';
  if (mime === 'image/webp') return '.webp';
  return '';
}

module.exports = router;


