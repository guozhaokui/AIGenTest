#!/usr/bin/env node

/**
 * MCP Lessons V3 - 客户端
 * 通过HTTP调用MemGraph服务
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { fetch } from 'undici';
import winston from 'winston';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// MemGraph服务地址
const MEMGRAPH_URL = process.env.MEMGRAPH_URL || 'http://localhost:8800';

// 配置日志
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

// 创建MCP服务器
const server = new Server(
  {
    name: 'lessons-recorder-v3',
    version: '3.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// 工具列表
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
        description: '搜索经验教训（激活式搜索+向量相似度）',
        inputSchema: {
          type: 'object',
          properties: {
            query: {
              type: 'string',
              description: '搜索关键词'
            },
            limit: {
              type: 'number',
              description: '返回记录数量（默认10）',
              default: 10
            },
            min_score: {
              type: 'number',
              description: '最小得分阈值（默认0.1）',
              default: 0.1
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
            },
            limit: {
              type: 'number',
              description: '返回记录数量（默认10）',
              default: 10
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
        description: '重建知识库索引',
        inputSchema: {
          type: 'object',
          properties: {}
        }
      }
    ]
  };
});

// 工具调用处理
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'record_lesson': {
        const response = await fetch(`${MEMGRAPH_URL}/record`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args)
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();
        logger.info(`Recorded new lesson: ${data.path}`);

        return {
          content: [{
            type: 'text',
            text: `成功记录经验到: ${data.path}\n文档ID: ${data.doc_id}`
          }]
        };
      }

      case 'search_lessons': {
        const response = await fetch(`${MEMGRAPH_URL}/search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: args.query,
            limit: args.limit || 10,
            min_score: args.min_score || 0.1,
            use_vector: true
          })
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();

        if (data.count === 0) {
          return {
            content: [{
              type: 'text',
              text: `未找到包含 "${args.query}" 的经验记录`
            }]
          };
        }

        let result = `找到 ${data.count} 条相关经验（激活式搜索+向量相似度）：\n\n`;

        data.results.forEach((lesson, index) => {
          result += `${index + 1}. [${lesson.path}] (得分: ${lesson.total_score.toFixed(2)})\n`;
          result += `   角色: ${lesson.role || 'AI'}\n`;
          result += `   项目: ${lesson.project || '-'}\n`;

          if (lesson.tags && lesson.tags.length > 0) {
            result += `   标签: ${lesson.tags.join(', ')}\n`;
          }

          result += `   问题: ${lesson.problem_preview || '-'}\n`;
          result += `   时间: ${lesson.timestamp || '-'}\n`;

          if (lesson.matched_ngrams) {
            result += `   激活: ${lesson.matched_ngrams} 个片段, 激活得分: ${lesson.activation_score.toFixed(2)}`;

            if (lesson.vector_similarity !== undefined) {
              result += `, 向量相似度: ${lesson.vector_similarity.toFixed(3)}`;
            }

            result += '\n';
          }

          result += '\n';
        });

        return {
          content: [{
            type: 'text',
            text: result
          }]
        };
      }

      case 'list_recent': {
        const response = await fetch(`${MEMGRAPH_URL}/recent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ limit: args.limit || 10 })
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();

        if (data.count === 0) {
          return {
            content: [{
              type: 'text',
              text: '暂无经验记录'
            }]
          };
        }

        let result = `最近 ${data.count} 条经验记录：\n\n`;

        data.results.forEach((lesson, index) => {
          result += `${index + 1}. [${lesson.path}]\n`;
          result += `   角色: ${lesson.role || 'AI'}\n`;
          result += `   项目: ${lesson.project || '-'}\n`;
          result += `   问题: ${lesson.problem_preview || '-'}\n`;
          result += `   时间: ${lesson.timestamp || '-'}\n\n`;
        });

        return {
          content: [{
            type: 'text',
            text: result
          }]
        };
      }

      case 'list_tags': {
        const response = await fetch(`${MEMGRAPH_URL}/tags`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();

        if (data.count === 0) {
          return {
            content: [{
              type: 'text',
              text: '暂无标签'
            }]
          };
        }

        return {
          content: [{
            type: 'text',
            text: `所有标签 (${data.count}):\n${data.tags.join(', ')}`
          }]
        };
      }

      case 'search_by_tag': {
        const response = await fetch(`${MEMGRAPH_URL}/search/tag`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            tag: args.tag,
            limit: args.limit || 10
          })
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();

        if (data.count === 0) {
          return {
            content: [{
              type: 'text',
              text: `未找到标签为 "${args.tag}" 的经验记录`
            }]
          };
        }

        let result = `标签 "${args.tag}" 的经验记录 (${data.count})：\n\n`;

        data.results.forEach((lesson, index) => {
          result += `${index + 1}. [${lesson.path}]\n`;
          result += `   问题: ${lesson.problem_preview || '-'}\n`;
          result += `   时间: ${lesson.timestamp || '-'}\n\n`;
        });

        return {
          content: [{
            type: 'text',
            text: result
          }]
        };
      }

      case 'get_stats': {
        const response = await fetch(`${MEMGRAPH_URL}/stats`);

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const stats = await response.json();

        let result = '# 知识库统计信息\n\n';
        result += `- 文档数量: ${stats.documents}\n`;
        result += `- N-gram总数: ${stats.ngrams}\n`;
        result += `- 唯一N-gram: ${stats.unique_ngrams}\n`;
        result += `- FAISS向量数: ${stats.faiss_vectors}\n`;

        return {
          content: [{
            type: 'text',
            text: result
          }]
        };
      }

      case 'rebuild_index': {
        logger.info('Rebuilding index...');

        const response = await fetch(`${MEMGRAPH_URL}/rebuild`, {
          method: 'POST'
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();
        const stats = data.stats;

        let result = '# 索引重建完成\n\n';
        result += `- 文档数量: ${stats.documents}\n`;
        result += `- N-gram总数: ${stats.ngrams}\n`;
        result += `- 唯一N-gram: ${stats.unique_ngrams}\n`;
        result += `- FAISS向量数: ${stats.faiss_vectors}\n`;

        return {
          content: [{
            type: 'text',
            text: result
          }]
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    logger.error(`Error executing tool ${name}:`, error);
    return {
      content: [{
        type: 'text',
        text: `错误: ${error.message}`
      }]
    };
  }
});

// 启动服务器
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  logger.info('MCP Lessons V3 (MemGraph client) server started');
  console.error('MCP Lessons V3 (MemGraph client) server started');
}

// 优雅关闭
process.on('SIGINT', () => {
  logger.info('Shutting down server...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down server...');
  process.exit(0);
});

// 运行服务器
main().catch((error) => {
  logger.error('Failed to start server:', error);
  console.error('Failed to start server:', error);
  process.exit(1);
});
