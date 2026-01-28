#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListResourcesRequestSchema,
  ListToolsRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import StorageV2 from './storage-v2.js';
import winston from 'winston';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configure logger
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.File({
      filename: path.join(__dirname, '../logs/error.log'),
      level: 'error'
    }),
    new winston.transports.File({
      filename: path.join(__dirname, '../logs/combined.log')
    })
  ]
});

// Initialize storage with new activation search engine
const storage = new StorageV2();

// Create MCP server
const server = new Server(
  {
    name: 'lessons-recorder',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
      resources: {},
    },
  }
);

// Handle tool listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'record_lesson',
        description: '记录一个新的经验教训',
        inputSchema: {
          type: 'object',
          properties: {
            role: {
              type: 'string',
              description: '角色：AI 或 用户',
              enum: ['AI', '用户'],
              default: 'AI'
            },
            project: {
              type: 'string',
              description: '项目名称或简单描述'
            },
            directory: {
              type: 'string',
              description: '项目目录路径'
            },
            problem: {
              type: 'string',
              description: '遇到的问题描述'
            },
            solution: {
              type: 'string',
              description: '解决方法（支持Markdown格式）'
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: '标签列表（可选）'
            }
          },
          required: ['problem', 'solution']
        }
      },
      {
        name: 'search_lessons',
        description: '搜索经验教训',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: '搜索关键词'
            }
          },
          required: ['query']
        }
      },
      {
        name: 'list_recent',
        description: '列出最近的经验记录',
        inputSchema: {
          type: 'object',
          properties: {
            limit: {
              type: 'number',
              description: '返回记录数量（默认10）',
              default: 10
            }
          }
        }
      },
      {
        name: 'read_lesson',
        description: '读取特定的经验记录',
        inputSchema: {
          type: 'object',
          properties: {
            path: {
              type: 'string',
              description: '记录文件的相对路径（如：2024/01/21_10-30-00_bug-fix.md）'
            }
          },
          required: ['path']
        }
      },
      {
        name: 'list_tags',
        description: '列出所有标签',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      },
      {
        name: 'search_by_tag',
        description: '按标签搜索经验',
        inputSchema: {
          type: 'object',
          properties: {
            tag: {
              type: 'string',
              description: '标签名称'
            }
          },
          required: ['tag']
        }
      },
      {
        name: 'get_stats',
        description: '获取知识库统计信息',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      },
      {
        name: 'rebuild_index',
        description: '重建知识库索引（从Markdown文件同步）',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      }
    ]
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'record_lesson': {
        const result = storage.saveLesson(args);
        logger.info(`Recorded new lesson: ${result.path}`);
        return {
          content: [
            {
              type: 'text',
              text: `成功记录经验到: ${result.path}\n完整路径: ${result.fullPath}`
            }
          ]
        };
      }

      case 'search_lessons': {
        const lessons = storage.searchLessons(args.query, {
          limit: args.limit || 10,
          minScore: args.minScore || 0.1
        });

        if (lessons.length === 0) {
          return {
            content: [
              {
                type: 'text',
                text: `未找到包含 "${args.query}" 的经验记录`
              }
            ]
          };
        }

        let result = `找到 ${lessons.length} 条相关经验（使用激活式搜索）：\n\n`;
        lessons.forEach((lesson, index) => {
          result += `${index + 1}. [${lesson.path}] (得分: ${lesson.totalScore.toFixed(2)})\n`;
          result += `   角色: ${lesson.role || 'AI'}\n`;
          result += `   项目: ${lesson.project || '-'}\n`;
          if (lesson.tags && lesson.tags.length > 0) {
            result += `   标签: ${lesson.tags.join(', ')}\n`;
          }
          result += `   问题: ${lesson.problemPreview || '-'}\n`;
          result += `   时间: ${lesson.timestamp || '-'}\n`;

          // 显示匹配详情
          if (lesson.matchedNgrams) {
            result += `   匹配: ${lesson.matchedNgrams} 个片段`;
            if (lesson.vectorSimilarity !== undefined) {
              result += `, 向量相似度: ${lesson.vectorSimilarity.toFixed(3)}`;
            }
            result += '\n';
          }
          result += '\n';
        });

        return {
          content: [
            {
              type: 'text',
              text: result
            }
          ]
        };
      }

      case 'list_recent': {
        const limit = args.limit || 10;
        const lessons = storage.listRecent(limit);

        if (lessons.length === 0) {
          return {
            content: [
              {
                type: 'text',
                text: '暂无经验记录'
              }
            ]
          };
        }

        let result = `最近 ${lessons.length} 条经验记录：\n\n`;
        lessons.forEach((lesson, index) => {
          result += `${index + 1}. [${lesson.path}]\n`;
          result += `   角色: ${lesson.role || 'AI'}\n`;
          result += `   项目: ${lesson.project || '-'}\n`;
          result += `   问题: ${lesson.problem?.split('\n')[0] || '-'}\n`;
          result += `   时间: ${lesson.timestamp || '-'}\n\n`;
        });

        return {
          content: [
            {
              type: 'text',
              text: result
            }
          ]
        };
      }

      case 'read_lesson': {
        const lesson = storage.readLesson(args.path);

        let result = '# 经验记录\n\n';
        result += `**路径:** ${args.path}\n`;
        result += `**角色:** ${lesson.role || 'AI'}\n`;
        result += `**项目:** ${lesson.project || '-'}\n`;
        result += `**目录:** ${lesson.directory || '-'}\n`;
        result += `**时间:** ${lesson.timestamp || '-'}\n`;

        if (lesson.tags && lesson.tags.length > 0) {
          result += `**标签:** ${lesson.tags.join(', ')}\n`;
        }

        result += '\n## 问题\n\n';
        result += lesson.problem || '-';
        result += '\n\n## 解决方法\n\n';
        result += lesson.solution || '-';

        return {
          content: [
            {
              type: 'text',
              text: result
            }
          ]
        };
      }

      case 'list_tags': {
        const tags = storage.getAllTags();

        if (tags.length === 0) {
          return {
            content: [
              {
                type: 'text',
                text: '暂无标签'
              }
            ]
          };
        }

        return {
          content: [
            {
              type: 'text',
              text: `所有标签 (${tags.length}):\n${tags.join(', ')}`
            }
          ]
        };
      }

      case 'search_by_tag': {
        const lessons = storage.searchByTag(args.tag);

        if (lessons.length === 0) {
          return {
            content: [
              {
                type: 'text',
                text: `未找到标签为 "${args.tag}" 的经验记录`
              }
            ]
          };
        }

        let result = `标签 "${args.tag}" 的经验记录 (${lessons.length})：\n\n`;
        lessons.forEach((lesson, index) => {
          result += `${index + 1}. [${lesson.path}]\n`;
          result += `   问题: ${lesson.problemPreview || '-'}\n`;
          result += `   时间: ${lesson.timestamp || '-'}\n\n`;
        });

        return {
          content: [
            {
              type: 'text',
              text: result
            }
          ]
        };
      }

      case 'get_stats': {
        const stats = storage.getStats();

        let result = '# 知识库统计信息\n\n';
        result += `- 文档数量: ${stats.documents}\n`;
        result += `- N-gram总数: ${stats.ngrams}\n`;
        result += `- 唯一N-gram: ${stats.uniqueNgrams}\n`;
        result += `- 词汇表大小: ${stats.vocabularySize}\n`;
        result += `- IDF得分数: ${stats.idfScoresCount}\n`;

        return {
          content: [
            {
              type: 'text',
              text: result
            }
          ]
        };
      }

      case 'rebuild_index': {
        logger.info('Rebuilding index...');
        const stats = storage.rebuildIndex();

        let result = '# 索引重建完成\n\n';
        result += `- 文档数量: ${stats.documents}\n`;
        result += `- N-gram总数: ${stats.ngrams}\n`;
        result += `- 唯一N-gram: ${stats.uniqueNgrams}\n`;
        result += `- 词汇表大小: ${stats.vocabularySize}\n`;

        return {
          content: [
            {
              type: 'text',
              text: result
            }
          ]
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    logger.error(`Error executing tool ${name}:`, error);
    return {
      content: [
        {
          type: 'text',
          text: `错误: ${error.message}`
        }
      ]
    };
  }
});

// Handle resource listing
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'lessons://recent',
        name: '最近的经验记录',
        description: '查看最近添加的经验记录',
        mimeType: 'text/plain'
      },
      {
        uri: 'lessons://tags',
        name: '所有标签',
        description: '查看所有标签',
        mimeType: 'text/plain'
      }
    ]
  };
});

// Handle resource reading
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  try {
    if (uri === 'lessons://recent') {
      const lessons = storage.listRecent(10);

      let result = '# 最近的经验记录\n\n';
      lessons.forEach((lesson, index) => {
        result += `## ${index + 1}. ${lesson.problem?.split('\n')[0] || '未命名'}\n`;
        result += `- 路径: ${lesson.path}\n`;
        result += `- 时间: ${lesson.timestamp || '-'}\n`;
        result += `- 项目: ${lesson.project || '-'}\n\n`;
      });

      return {
        contents: [
          {
            uri,
            mimeType: 'text/plain',
            text: result
          }
        ]
      };
    } else if (uri === 'lessons://tags') {
      const tags = storage.getAllTags();

      return {
        contents: [
          {
            uri,
            mimeType: 'text/plain',
            text: `标签列表 (${tags.length}):\n${tags.join(', ')}`
          }
        ]
      };
    } else {
      throw new Error(`Unknown resource: ${uri}`);
    }
  } catch (error) {
    logger.error(`Error reading resource ${uri}:`, error);
    throw error;
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  logger.info('MCP Lessons Recorder server started');
  console.error('MCP Lessons Recorder server started');
}

// Handle shutdown gracefully
process.on('SIGINT', () => {
  logger.info('Shutting down server...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down server...');
  process.exit(0);
});

// Run the server
main().catch((error) => {
  logger.error('Failed to start server:', error);
  console.error('Failed to start server:', error);
  process.exit(1);
});