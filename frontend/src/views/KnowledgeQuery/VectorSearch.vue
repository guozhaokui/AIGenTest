<template>
  <div class="knowledge-query">
    <el-card shadow="never" class="query-card">
      <template #header>
        <div class="card-header">
          <span>知识问答</span>
          <el-select
            v-model="selectedModel"
            placeholder="选择模型"
            style="width: 300px"
          >
            <el-option
              v-for="model in models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            >
              <span>{{ model.name }}</span>
              <el-tag v-if="model.recommended" size="small" type="success" style="margin-left: 8px">
                推荐
              </el-tag>
            </el-option>
          </el-select>
        </div>
      </template>

      <!-- 问题输入 -->
      <div class="query-input">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          placeholder="请输入你的问题..."
          @keydown.ctrl.enter="handleQuery"
        />
        <el-button
          type="primary"
          :loading="querying"
          @click="handleQuery"
          style="margin-top: 10px"
        >
          <el-icon><Search /></el-icon>
          查询 (Ctrl+Enter)
        </el-button>
      </div>
    </el-card>

    <!-- 查询历史 -->
    <div class="query-history">
      <div v-if="queryHistory.length === 0 && !querying">
        <el-empty description="请输入问题开始查询" />
      </div>
      <el-card
        v-for="(item, index) in queryHistory"
        :key="index"
        shadow="never"
        class="history-card"
      >
        <template #header>
          <div class="history-header">
            <strong>问题:</strong> {{ item.question }}
            <span class="timestamp">{{ formatTime(item.timestamp) }}</span>
          </div>
        </template>

        <!-- AI回答 -->
        <div class="answer-section">
          <el-alert
            v-if="!item.answer"
            title="MemGraph 搜索引擎 - 仅提供文档检索，不生成AI回答"
            type="info"
            :closable="false"
          >
            <template #default>
              提示：MemGraph 使用激活式搜索 + FAISS向量检索，快速找到最相关的文档。
              如需 AI 生成答案，请使用"智能问答"中的"纯聊天"模式。
            </template>
          </el-alert>
          <div v-else class="answer-content">
            <strong>回答:</strong>
            <div class="answer-text">{{ item.answer }}</div>
            <el-tag size="small" style="margin-top: 10px">
              模型: {{ item.model }}
            </el-tag>
          </div>
        </div>

        <!-- 检索到的文档 -->
        <el-divider content-position="left">
          MemGraph 检索结果 (共 {{ item.context.length }} 条)
        </el-divider>
        <div class="context-docs">
          <el-collapse>
            <el-collapse-item
              v-for="doc in item.context"
              :key="doc.index"
            >
              <template #title>
                <div class="doc-title">
                  <span class="doc-index">#{{ doc.index }}</span>
                  <span class="doc-source">{{ doc.source }}</span>
                  <el-tag
                    :type="getSimilarityType(doc.similarity)"
                    size="small"
                  >
                    相似度: {{ (doc.similarity * 100).toFixed(1) }}%
                  </el-tag>
                </div>
              </template>

              <!-- 左右分栏布局 -->
              <el-row :gutter="20">
                <!-- 左侧：最相似片段列表 -->
                <el-col :span="8" v-if="doc.segments && doc.segments.length > 0">
                  <div class="segments-panel">
                    <div class="segments-header">
                      <el-icon><Connection /></el-icon>
                      最相似片段 ({{ doc.segments.length }})
                    </div>
                    <div class="segments-list">
                      <div
                        v-for="(seg, segIndex) in doc.segments"
                        :key="segIndex"
                        :class="['segment-item', { active: doc.activeSegment === segIndex }]"
                        @click="highlightSegment(doc, segIndex)"
                      >
                        <div class="segment-header">
                          <el-tag :type="getSegmentType(seg.granularity)" size="small">
                            {{ seg.granularity === 'paragraph' ? '段落' : '句子' }}
                          </el-tag>
                          <span class="segment-similarity">
                            {{ (seg.similarity * 100).toFixed(1) }}%
                          </span>
                        </div>
                        <div class="segment-preview">
                          {{ seg.content.substring(0, 60) }}{{ seg.content.length > 60 ? '...' : '' }}
                        </div>
                      </div>
                    </div>
                  </div>
                </el-col>

                <!-- 右侧：完整文档内容 -->
                <el-col :span="doc.segments && doc.segments.length > 0 ? 16 : 24">
                  <div
                    :id="`doc-content-${doc.index}`"
                    class="doc-content"
                    v-html="getHighlightedContent(doc, item.question)"
                  ></div>
                </el-col>
              </el-row>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import { Search, Connection } from '@element-plus/icons-vue';
import { queryKnowledge, getKnowledgeModels } from '@/services/api';

const question = ref('');
const selectedModel = ref('deepseek-ai/deepseek-v3.2');
const querying = ref(false);
const queryHistory = ref([]);
const models = ref([]);

// 知识问答处理
const handleQuery = async () => {
  if (!question.value.trim()) {
    ElMessage.warning('请输入问题');
    return;
  }

  querying.value = true;

  try {
    const result = await queryKnowledge({
      question: question.value,
      model: selectedModel.value,
      top_k: 3
    });

    if (result.success) {
      queryHistory.value.unshift({
        ...result.data,
        timestamp: Date.now()
      });

      // 清空输入
      question.value = '';

      ElMessage.success('查询完成');
    } else {
      ElMessage.error(result.error || '查询失败');
    }
  } catch (error) {
    console.error('查询失败:', error);
    ElMessage.error('查询失败: ' + error.message);
  } finally {
    querying.value = false;
  }
};

const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN');
};

// 相似度类型
const getSimilarityType = (similarity) => {
  if (similarity >= 0.8) return 'success';
  if (similarity >= 0.6) return 'warning';
  return 'info';
};

// 关键词高亮
const highlightKeywords = (content, query) => {
  if (!content || !query) return content;

  // 分词：简单按空格和标点分割
  const keywords = query
    .split(/[\s,，.。!！?？;；:：、]+/)
    .filter(word => word.length >= 2) // 过滤太短的词
    .map(word => word.trim())
    .filter(word => word.length > 0);

  if (keywords.length === 0) return escapeHtml(content);

  let result = escapeHtml(content);

  // 按关键词长度排序(长的先匹配,避免短词覆盖长词)
  const sortedKeywords = [...keywords].sort((a, b) => b.length - a.length);

  // 为每个关键词创建不同深度的高亮
  sortedKeywords.forEach((keyword, index) => {
    // 计算颜色深度(第一个关键词最深,后续逐渐变浅)
    const intensity = Math.max(0.9 - index * 0.15, 0.4);
    const backgroundColor = `rgba(255, 235, 59, ${intensity})`; // 黄色高亮
    const color = intensity > 0.6 ? '#333' : '#666';

    // 使用正则表达式进行不区分大小写的匹配
    const regex = new RegExp(`(${escapeRegex(keyword)})`, 'gi');
    result = result.replace(
      regex,
      `<mark style="background-color: ${backgroundColor}; color: ${color}; padding: 2px 4px; border-radius: 2px; font-weight: 500;">$1</mark>`
    );
  });

  return result;
};

// HTML转义
const escapeHtml = (text) => {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
};

// 正则表达式特殊字符转义
const escapeRegex = (text) => {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
};

// 获取片段类型标签颜色
const getSegmentType = (granularity) => {
  return granularity === 'paragraph' ? 'primary' : 'success';
};

// 点击片段项，在正文中高亮显示
const highlightSegment = async (doc, segIndex) => {
  doc.activeSegment = segIndex;

  // 等待DOM更新
  await nextTick();

  const segment = doc.segments[segIndex];
  if (!segment) return;

  // 滚动到文档内容区域
  const contentEl = document.getElementById(`doc-content-${doc.index}`);
  if (!contentEl) return;

  // 移除现有高亮
  contentEl.querySelectorAll('.segment-highlight').forEach(el => {
    const parent = el.parentNode;
    while (el.firstChild) {
      parent.insertBefore(el.firstChild, el);
    }
    parent.removeChild(el);
  });

  // 获取纯文本内容用于查找位置
  const textContent = contentEl.textContent || '';
  const segmentText = segment.content;

  // 查找片段在文本中的位置
  const startIndex = textContent.indexOf(segmentText);

  if (startIndex === -1) {
    console.warn('未找到片段内容在文档中的位置');
    return;
  }

  // 使用 TreeWalker 遍历文本节点
  const walker = document.createTreeWalker(
    contentEl,
    NodeFilter.SHOW_TEXT,
    null,
    false
  );

  let currentPos = 0;
  let startNode = null;
  let startOffset = 0;
  let endNode = null;
  let endOffset = 0;

  // 查找起始和结束位置
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const nodeLength = node.textContent.length;

    if (startNode === null && currentPos + nodeLength > startIndex) {
      startNode = node;
      startOffset = startIndex - currentPos;
    }

    if (startNode !== null && currentPos + nodeLength >= startIndex + segmentText.length) {
      endNode = node;
      endOffset = startIndex + segmentText.length - currentPos;
      break;
    }

    currentPos += nodeLength;
  }

  // 如果找到了起始和结束节点，创建高亮
  if (startNode && endNode) {
    const range = document.createRange();
    range.setStart(startNode, startOffset);
    range.setEnd(endNode, endOffset);

    const highlightSpan = document.createElement('span');
    highlightSpan.className = 'segment-highlight';

    try {
      range.surroundContents(highlightSpan);

      // 滚动到高亮位置
      highlightSpan.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (e) {
      // 如果 surroundContents 失败（跨元素边界），使用备用方法
      console.warn('高亮失败，使用备用方法', e);

      // 在原始内容中查找片段位置
      const originalContent = doc.content;
      const segmentIndexInOriginal = originalContent.indexOf(segmentText);

      if (segmentIndexInOriginal !== -1) {
        // 分割原始内容
        const beforeSegment = originalContent.substring(0, segmentIndexInOriginal);
        const segmentContent = segmentText;
        const afterSegment = originalContent.substring(segmentIndexInOriginal + segmentText.length);

        // 对各部分应用关键词高亮（但不对片段本身应用，避免冲突）
        const highlightedBefore = highlightKeywords(beforeSegment, '');
        const highlightedAfter = highlightKeywords(afterSegment, '');

        // 片段内容需要转义HTML
        const escapedSegment = escapeHtml(segmentContent);

        contentEl.innerHTML = highlightedBefore +
          `<span class="segment-highlight">${escapedSegment}</span>` +
          highlightedAfter;

        // 滚动到高亮位置
        const highlightEl = contentEl.querySelector('.segment-highlight');
        if (highlightEl) {
          highlightEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }
    }
  }
};

// 获取带高亮的内容
const getHighlightedContent = (doc, query) => {
  if (!doc.content) return '';

  // 首先应用关键词高亮
  let content = highlightKeywords(doc.content, query);

  // 初始化activeSegment
  if (doc.activeSegment === undefined) {
    doc.activeSegment = -1;
  }

  return content;
};

// 加载模型列表
onMounted(async () => {
  try {
    const result = await getKnowledgeModels();
    if (result.success) {
      models.value = result.data.models || [];
    }
  } catch (error) {
    console.error('加载模型列表失败:', error);
  }
});
</script>

<style scoped>
.knowledge-query {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.query-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.query-input {
  display: flex;
  flex-direction: column;
}

.query-history {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.history-card {
  background: #fff;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
}

.timestamp {
  color: #909399;
  font-size: 12px;
}

.answer-section {
  margin-bottom: 20px;
}

.answer-content {
  padding: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.answer-text {
  margin-top: 10px;
  line-height: 1.8;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.context-docs {
  margin-top: 10px;
}

.doc-title {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding-right: 20px;
}

.doc-index {
  font-size: 16px;
  font-weight: bold;
  color: #409eff;
  min-width: 40px;
}

.doc-source {
  flex: 1;
  font-weight: 500;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-content {
  padding: 15px;
  background: #fafafa;
  border-radius: 4px;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.8;
  margin: 0;
  max-height: 400px;
  overflow-y: auto;
}

/* 高亮标记样式 */
.doc-content :deep(mark) {
  transition: all 0.2s ease;
}

.doc-content :deep(mark:hover) {
  transform: scale(1.05);
  box-shadow: 0 2px 8px rgba(255, 235, 59, 0.5);
}

/* 片段高亮样式 */
.doc-content :deep(.segment-highlight) {
  background: linear-gradient(120deg, #84fab0 0%, #8fd3f4 100%);
  padding: 3px 6px;
  border-radius: 4px;
  font-weight: 600;
  color: #0066cc;
  box-shadow: 0 2px 12px rgba(132, 250, 176, 0.5);
  animation: pulse 1.5s ease-in-out;
}

@keyframes pulse {
  0%, 100% { box-shadow: 0 2px 12px rgba(132, 250, 176, 0.5); }
  50% { box-shadow: 0 4px 20px rgba(132, 250, 176, 0.8); }
}

/* 左侧片段面板 */
.segments-panel {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 12px;
  max-height: 500px;
  overflow-y: auto;
}

.segments-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 2px solid #e4e7ed;
}

.segments-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.segment-item {
  background: white;
  border: 2px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.segment-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.2);
  transform: translateX(4px);
}

.segment-item.active {
  border-color: #67c23a;
  background: linear-gradient(135deg, #e8f5e9 0%, #f1f8ff 100%);
  box-shadow: 0 2px 12px rgba(103, 194, 58, 0.3);
}

.segment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.segment-similarity {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
}

.segment-preview {
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
