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
  ListPromptsRequestSchema,
  GetPromptRequestSchema,
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
      prompts: {},
    },
  }
);

// Prompts 列表 - 提供使用指南
server.setRequestHandler(ListPromptsRequestSchema, async () => {
  return {
    prompts: [
      {
        name: 'lessons-usage-guide',
        description: 'AI Lessons 知识库的最佳使用方法和场景指南',
      }
    ]
  };
});

// 获取 Prompt 内容
server.setRequestHandler(GetPromptRequestSchema, async (request) => {
  const { name } = request.params;

  if (name === 'lessons-usage-guide') {
    return {
      messages: [
        {
          role: 'user',
          content: {
            type: 'text',
            text: `# AI Lessons 使用指南

## 记录原则

**关键：保持简洁，避免冗余**

- 只记录核心要点和解决方法
- 不要重复解释已知概念
- 通用概念单独记录，其他文档引用即可
- 一个问题一条记录

## 何时记录

解决问题、重要配置、踩坑经验时主动记录，无需询问用户。

## 基本操作

- 记录：record_lesson
- 搜索：search_lessons
- 更新：先搜索获取 doc_id，再 update_lesson（慢，~60秒）`
          }
        }
      ]
    };
  }

  throw new Error(`Unknown prompt: ${name}`);
});

// 工具列表
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'record_lesson',
        description: '记录知识、经验、笔记或任何信息。用于在对话过程中主动记录值得保存的内容（如解决的问题、学到的经验、重要的配置等）',
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
              description: '标题、主题或问题描述'
            },
            solution: {
              type: 'string',
              description: '内容、解决方法或详细说明（支持Markdown格式）'
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: '标签列表（可选）'
            }
          },
          required: ['solution']
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
        name: 'update_lesson',
        description: '更新已有文档内容并重新索引（文档ID可通过搜索、列出最近记录或按标签搜索获取）',
        inputSchema: {
          type: 'object',
          properties: {
            doc_id: {
              type: 'number',
              description: '文档ID（从搜索结果、list_recent 或 search_by_tag 的输出中获取）'
            },
            role: {
              type: 'string',
              description: '角色：AI 或 用户',
              enum: ['AI', '用户']
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
              description: '标题、主题或问题描述'
            },
            solution: {
              type: 'string',
              description: '内容、解决方法或详细说明（支持Markdown格式）'
            },
            tags: {
              type: 'array',
              items: { type: 'string' },
              description: '标签列表（可选）'
            }
          },
          required: ['doc_id', 'solution']
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

        let result = `找到 ${data.count} 条相关经验：\n\n`;

        data.results.forEach((lesson, index) => {
          result += `${'='.repeat(60)}\n`;
          result += `${index + 1}. ${lesson.path}\n`;
          result += `${'='.repeat(60)}\n\n`;

          result += `📋 基本信息\n`;
          result += `  文档ID: ${lesson.doc_id}\n`;
          result += `  角色: ${lesson.role || 'AI'}\n`;
          result += `  项目: ${lesson.project || '-'}\n`;
          result += `  时间: ${lesson.timestamp || '-'}\n`;

          if (lesson.tags && lesson.tags.length > 0) {
            result += `  标签: ${lesson.tags.join(', ')}\n`;
          }

          result += `\n`;

          if (lesson.problem) {
            result += `❓ 主题\n`;
            result += `${lesson.problem}\n\n`;
          }

          result += `📝 内容\n`;
          result += `${lesson.solution || '-'}\n\n`;

          // 匹配详情（可选，用于调试）
          if (lesson.matched_ngrams) {
            result += `📊 匹配详情\n`;
            result += `  得分: ${lesson.total_score.toFixed(2)}\n`;
            result += `  激活片段: ${lesson.matched_ngrams} 个\n`;

            if (lesson.vector_similarity !== undefined) {
              result += `  整篇文档相似度: ${lesson.vector_similarity.toFixed(3)}\n`;
            }

            if (lesson.chunk_max_similarity !== undefined) {
              result += `  最佳块相似度: ${lesson.chunk_max_similarity.toFixed(3)}\n`;
            }

            result += '\n';
          }
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
          result += `   文档ID: ${lesson.doc_id}\n`;
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
          result += `   文档ID: ${lesson.doc_id}\n`;
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

      case 'update_lesson': {
        const response = await fetch(`${MEMGRAPH_URL}/update`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(args)
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();
        logger.info(`Updated lesson doc_id=${args.doc_id}: ${data.path}`);

        return {
          content: [{
            type: 'text',
            text: `成功更新文档: ${data.path}\n文档ID: ${data.doc_id}\n已重新索引向量`
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
