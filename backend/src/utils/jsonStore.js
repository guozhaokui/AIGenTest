'use strict';

const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');

async function readJson(filePath) {
  const resolved = path.resolve(filePath);
  const buf = await fsp.readFile(resolved);
  // 允许结尾空白
  const text = buf.toString('utf-8');
  return JSON.parse(text || '[]');
}

async function writeJson(filePath, data) {
  const resolved = path.resolve(filePath);
  await fsp.mkdir(path.dirname(resolved), { recursive: true });
  const tmp = resolved + '.tmp';
  const text = JSON.stringify(data, null, 2);
  await fsp.writeFile(tmp, text, 'utf-8');
  // Windows 下 rename 也是原子性的（同分区）
  await fsp.rename(tmp, resolved);
}

module.exports = {
  readJson,
  writeJson
};


