#!/usr/bin/env node

/**
 * 将所有Markdown文件导出为JSON格式
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import LessonsStorage from '../src/storage.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const outputPath = process.argv[2] || path.join(__dirname, '../records/export.json');
const storage = new LessonsStorage();

// 获取所有记录
const allLessons = [];

function collectAllLessons(dir) {
  if (!fs.existsSync(dir)) {
    console.log(`Records directory not found: ${dir}`);
    return;
  }

  const items = fs.readdirSync(dir);

  for (const item of items) {
    const fullPath = path.join(dir, item);
    const stat = fs.statSync(fullPath);

    if (stat.isDirectory()) {
      collectAllLessons(fullPath);
    } else if (item.endsWith('.md')) {
      const relativePath = path.relative(storage.recordsDir, fullPath);
      try {
        const lesson = storage.readLesson(relativePath);
        allLessons.push({
          ...lesson,
          path: relativePath
        });
      } catch (error) {
        console.error(`Error reading ${relativePath}:`, error.message);
      }
    }
  }
}

collectAllLessons(storage.recordsDir);

// 按时间排序
allLessons.sort((a, b) => {
  const timeA = new Date(a.timestamp || 0).getTime();
  const timeB = new Date(b.timestamp || 0).getTime();
  return timeB - timeA;
});

// 写入JSON文件
fs.writeFileSync(outputPath, JSON.stringify(allLessons, null, 2), 'utf8');

console.log(`已导出 ${allLessons.length} 条记录到: ${outputPath}`);