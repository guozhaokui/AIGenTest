import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class LessonsStorage {
  constructor(recordsPath = '../records') {
    this.recordsDir = path.join(__dirname, recordsPath);
    this.ensureDirectoryExists();
  }

  ensureDirectoryExists() {
    if (!fs.existsSync(this.recordsDir)) {
      fs.mkdirSync(this.recordsDir, { recursive: true });
    }
  }

  /**
   * 生成文件名
   * 格式: YYYY/MM/DD_HH-MM-SS_slug.md
   */
  generateFilename(problem) {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hour = String(now.getHours()).padStart(2, '0');
    const minute = String(now.getMinutes()).padStart(2, '0');
    const second = String(now.getSeconds()).padStart(2, '0');

    // 生成slug: 从问题描述中提取关键词
    const slug = problem
      .substring(0, 50)  // 限制长度
      .toLowerCase()
      .replace(/[^\u4e00-\u9fa5a-z0-9\s-]/g, '')  // 保留中文、字母、数字、空格、横线
      .replace(/\s+/g, '-')  // 空格转横线
      .replace(/-+/g, '-')  // 多个横线合并
      .replace(/^-|-$/g, '');  // 去掉首尾横线

    const filename = `${day}_${hour}-${minute}-${second}_${slug || 'lesson'}.md`;
    const yearMonth = `${year}/${month}`;

    return { yearMonth, filename };
  }

  /**
   * 创建Markdown内容
   */
  createMarkdown(data) {
    const {
      role = 'AI',
      project = '',
      directory = '',
      problem = '',
      solution = '',
      tags = []
    } = data;

    const timestamp = new Date().toISOString();

    let content = '---\n';
    content += `role: ${role}\n`;
    content += `project: ${project}\n`;
    content += `directory: ${directory}\n`;
    content += `timestamp: ${timestamp}\n`;
    if (tags && tags.length > 0) {
      content += `tags: [${tags.join(', ')}]\n`;
    }
    content += '---\n\n';

    content += `# ${problem}\n\n`;

    content += '## 问题\n\n';
    content += `${problem}\n\n`;

    content += '## 解决方法\n\n';
    content += `${solution}\n`;

    return content;
  }

  /**
   * 解析Markdown文件
   */
  parseMarkdown(content) {
    const lines = content.split('\n');
    const metadata = {};
    let inFrontmatter = false;
    let problemSection = '';
    let solutionSection = '';
    let currentSection = '';

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // 解析frontmatter
      if (line === '---') {
        if (!inFrontmatter && i === 0) {
          inFrontmatter = true;
          continue;
        } else if (inFrontmatter) {
          inFrontmatter = false;
          continue;
        }
      }

      if (inFrontmatter) {
        const match = line.match(/^(\w+):\s*(.+)$/);
        if (match) {
          const key = match[1];
          let value = match[2];

          // 处理tags数组
          if (key === 'tags') {
            value = value.replace(/^\[|\]$/g, '').split(',').map(t => t.trim());
          }

          metadata[key] = value;
        }
        continue;
      }

      // 解析内容部分
      if (line.startsWith('## 问题')) {
        currentSection = 'problem';
        continue;
      } else if (line.startsWith('## 解决方法') || line.startsWith('## 解决办法')) {
        currentSection = 'solution';
        continue;
      } else if (line.startsWith('#')) {
        currentSection = '';
        continue;
      }

      if (currentSection === 'problem') {
        problemSection += line + '\n';
      } else if (currentSection === 'solution') {
        solutionSection += line + '\n';
      }
    }

    return {
      ...metadata,
      problem: problemSection.trim(),
      solution: solutionSection.trim()
    };
  }

  /**
   * 保存经验记录
   */
  saveLesson(data) {
    const { yearMonth, filename } = this.generateFilename(data.problem || 'lesson');
    const dirPath = path.join(this.recordsDir, yearMonth);

    // 确保年月目录存在
    if (!fs.existsSync(dirPath)) {
      fs.mkdirSync(dirPath, { recursive: true });
    }

    const filePath = path.join(dirPath, filename);
    const content = this.createMarkdown(data);

    fs.writeFileSync(filePath, content, 'utf8');

    return {
      path: path.relative(this.recordsDir, filePath),
      fullPath: filePath
    };
  }

  /**
   * 读取经验记录
   */
  readLesson(relativePath) {
    const filePath = path.join(this.recordsDir, relativePath);

    if (!fs.existsSync(filePath)) {
      throw new Error(`File not found: ${relativePath}`);
    }

    const content = fs.readFileSync(filePath, 'utf8');
    return this.parseMarkdown(content);
  }

  /**
   * 搜索经验记录
   */
  searchLessons(query) {
    const results = [];
    const searchTerm = query.toLowerCase();

    // 递归搜索所有md文件
    const searchDir = (dir) => {
      const items = fs.readdirSync(dir);

      for (const item of items) {
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
          searchDir(fullPath);
        } else if (item.endsWith('.md')) {
          const content = fs.readFileSync(fullPath, 'utf8');

          // 简单的全文搜索
          if (content.toLowerCase().includes(searchTerm)) {
            const lesson = this.parseMarkdown(content);
            results.push({
              ...lesson,
              path: path.relative(this.recordsDir, fullPath)
            });
          }
        }
      }
    };

    if (fs.existsSync(this.recordsDir)) {
      searchDir(this.recordsDir);
    }

    // 按时间戳排序（最新的在前）
    results.sort((a, b) => {
      const timeA = new Date(a.timestamp || 0).getTime();
      const timeB = new Date(b.timestamp || 0).getTime();
      return timeB - timeA;
    });

    return results;
  }

  /**
   * 列出最近的经验记录
   */
  listRecent(limit = 10) {
    const allFiles = [];

    // 递归获取所有md文件
    const collectFiles = (dir) => {
      if (!fs.existsSync(dir)) return;

      const items = fs.readdirSync(dir);

      for (const item of items) {
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
          collectFiles(fullPath);
        } else if (item.endsWith('.md')) {
          allFiles.push({
            path: fullPath,
            mtime: stat.mtime
          });
        }
      }
    };

    collectFiles(this.recordsDir);

    // 按修改时间排序
    allFiles.sort((a, b) => b.mtime - a.mtime);

    // 读取并返回最近的记录
    const results = [];
    for (let i = 0; i < Math.min(limit, allFiles.length); i++) {
      const content = fs.readFileSync(allFiles[i].path, 'utf8');
      const lesson = this.parseMarkdown(content);
      results.push({
        ...lesson,
        path: path.relative(this.recordsDir, allFiles[i].path)
      });
    }

    return results;
  }

  /**
   * 获取所有标签
   */
  getAllTags() {
    const tagsSet = new Set();

    const collectTags = (dir) => {
      if (!fs.existsSync(dir)) return;

      const items = fs.readdirSync(dir);

      for (const item of items) {
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
          collectTags(fullPath);
        } else if (item.endsWith('.md')) {
          const content = fs.readFileSync(fullPath, 'utf8');
          const lesson = this.parseMarkdown(content);

          if (lesson.tags && Array.isArray(lesson.tags)) {
            lesson.tags.forEach(tag => tagsSet.add(tag));
          }
        }
      }
    };

    collectTags(this.recordsDir);

    return Array.from(tagsSet).sort();
  }

  /**
   * 按标签搜索
   */
  searchByTag(tag) {
    const results = [];

    const searchDir = (dir) => {
      if (!fs.existsSync(dir)) return;

      const items = fs.readdirSync(dir);

      for (const item of items) {
        const fullPath = path.join(dir, item);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
          searchDir(fullPath);
        } else if (item.endsWith('.md')) {
          const content = fs.readFileSync(fullPath, 'utf8');
          const lesson = this.parseMarkdown(content);

          if (lesson.tags && lesson.tags.includes(tag)) {
            results.push({
              ...lesson,
              path: path.relative(this.recordsDir, fullPath)
            });
          }
        }
      }
    };

    searchDir(this.recordsDir);

    return results;
  }
}

export default LessonsStorage;