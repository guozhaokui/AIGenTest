#!/usr/bin/env node

/**
 * 便捷脚本：直接使用MCP Lessons服务的功能
 * 用法：node use-lessons.js <command> [args]
 */

import LessonsStorage from './src/storage.js';

const storage = new LessonsStorage();
const command = process.argv[2];
const args = process.argv.slice(3);

function printHelp() {
  console.log(`
MCP Lessons 便捷使用脚本

用法：
  node use-lessons.js <command> [args]

命令：
  record <problem> <solution>    记录新经验（会提示输入其他信息）
  search <keyword>               搜索经验
  recent [limit]                 显示最近的记录（默认10条）
  read <path>                    读取特定记录
  tags                           列出所有标签
  tag <tagname>                  按标签搜索

示例：
  node use-lessons.js record "遇到的问题" "解决方案"
  node use-lessons.js search "React"
  node use-lessons.js recent 5
  node use-lessons.js tags
`);
}

async function main() {
  if (!command || command === 'help') {
    printHelp();
    return;
  }

  try {
    switch (command) {
      case 'record': {
        const problem = args[0] || '未指定问题';
        const solution = args[1] || '未指定解决方案';

        // 交互式输入其他信息
        const readline = await import('readline');
        const rl = readline.createInterface({
          input: process.stdin,
          output: process.stdout
        });

        const question = (prompt) => new Promise(resolve => {
          rl.question(prompt, resolve);
        });

        console.log('\n=== 记录新经验 ===\n');
        const project = await question('项目名称 (回车跳过): ') || '';
        const directory = await question('项目目录 (回车使用当前目录): ') || process.cwd();
        const role = await question('角色 [AI/用户] (默认AI): ') || 'AI';
        const tagsInput = await question('标签 (逗号分隔，回车跳过): ') || '';
        const tags = tagsInput ? tagsInput.split(',').map(t => t.trim()) : [];

        rl.close();

        const result = storage.saveLesson({
          role,
          project,
          directory,
          problem,
          solution,
          tags
        });

        console.log(`\n✅ 成功记录到: ${result.path}`);
        console.log(`完整路径: ${result.fullPath}`);
        break;
      }

      case 'search': {
        const query = args.join(' ');
        if (!query) {
          console.error('请提供搜索关键词');
          return;
        }

        const results = storage.searchLessons(query);
        if (results.length === 0) {
          console.log(`未找到包含 "${query}" 的记录`);
        } else {
          console.log(`\n找到 ${results.length} 条记录：\n`);
          results.forEach((r, i) => {
            console.log(`${i + 1}. [${r.path}]`);
            console.log(`   问题: ${r.problem?.split('\n')[0] || '-'}`);
            console.log(`   时间: ${r.timestamp || '-'}\n`);
          });
        }
        break;
      }

      case 'recent': {
        const limit = parseInt(args[0]) || 10;
        const results = storage.listRecent(limit);

        if (results.length === 0) {
          console.log('暂无记录');
        } else {
          console.log(`\n最近 ${results.length} 条记录：\n`);
          results.forEach((r, i) => {
            console.log(`${i + 1}. [${r.path}]`);
            console.log(`   项目: ${r.project || '-'}`);
            console.log(`   问题: ${r.problem?.split('\n')[0] || '-'}`);
            console.log(`   时间: ${r.timestamp || '-'}\n`);
          });
        }
        break;
      }

      case 'read': {
        const path = args[0];
        if (!path) {
          console.error('请提供文件路径');
          return;
        }

        const lesson = storage.readLesson(path);
        console.log('\n=== 经验记录 ===\n');
        console.log(`角色: ${lesson.role || 'AI'}`);
        console.log(`项目: ${lesson.project || '-'}`);
        console.log(`目录: ${lesson.directory || '-'}`);
        console.log(`时间: ${lesson.timestamp || '-'}`);
        if (lesson.tags?.length > 0) {
          console.log(`标签: ${lesson.tags.join(', ')}`);
        }
        console.log('\n## 问题\n');
        console.log(lesson.problem || '-');
        console.log('\n## 解决方法\n');
        console.log(lesson.solution || '-');
        break;
      }

      case 'tags': {
        const tags = storage.getAllTags();
        if (tags.length === 0) {
          console.log('暂无标签');
        } else {
          console.log(`\n所有标签 (${tags.length}):\n`);
          console.log(tags.join(', '));
        }
        break;
      }

      case 'tag': {
        const tag = args[0];
        if (!tag) {
          console.error('请提供标签名');
          return;
        }

        const results = storage.searchByTag(tag);
        if (results.length === 0) {
          console.log(`未找到标签为 "${tag}" 的记录`);
        } else {
          console.log(`\n标签 "${tag}" 的记录 (${results.length}):\n`);
          results.forEach((r, i) => {
            console.log(`${i + 1}. [${r.path}]`);
            console.log(`   问题: ${r.problem?.split('\n')[0] || '-'}`);
            console.log(`   时间: ${r.timestamp || '-'}\n`);
          });
        }
        break;
      }

      default:
        console.error(`未知命令: ${command}`);
        printHelp();
    }
  } catch (error) {
    console.error(`错误: ${error.message}`);
  }
}

main();