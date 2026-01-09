<template>
  <div class="vector-search">
    <el-card class="search-card">
      <template #header>
        <div class="card-header">
          <span>纯向量检索</span>
          <el-tag type="info">不调用LLM，用于测试检索速度</el-tag>
        </div>
      </template>

      <!-- 搜索输入 -->
      <div class="search-input">
        <el-input
          v-model="query"
          type="textarea"
          :rows="2"
          placeholder="输入检索内容... (Ctrl+Enter 搜索)"
          @keydown.ctrl.enter="handleSearch"
        />
        <div class="search-actions">
          <el-input-number
            v-model="topK"
            :min="1"
            :max="20"
            :step="1"
            size="default"
            style="width: 120px"
          >
            <template #prefix>Top K:</template>
          </el-input-number>
          <el-button
            type="primary"
            :loading="searching"
            @click="handleSearch"
          >
            <el-icon><Search /></el-icon>
            检索 (Ctrl+Enter)
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 搜索结果 -->
    <div class="search-results" v-if="lastResult">
      <el-card>
        <template #header>
          <div class="result-header">
            <span>
              检索结果：<strong>{{ lastResult.total }}</strong> 条
            </span>
            <div class="timing-info">
              <el-tag type="success" effect="plain">
                <el-icon><Timer /></el-icon>
                检索耗时: {{ lastResult.search_time_ms }} ms
              </el-tag>
            </div>
          </div>
        </template>

        <div class="query-info">
          <strong>查询内容：</strong>{{ lastResult.query }}
        </div>

        <el-divider />

        <div v-if="lastResult.results.length === 0" class="empty-results">
          <el-empty description="未找到相关文档" />
        </div>

        <div v-else class="result-list">
          <div
            v-for="doc in lastResult.results"
            :key="doc.index"
            class="result-item"
          >
            <div class="result-item-header">
              <div class="result-rank">#{{ doc.index }}</div>
              <div class="result-source">{{ doc.source }}</div>
              <el-tag
                :type="getSimilarityType(doc.similarity)"
                effect="plain"
              >
                相似度: {{ (doc.similarity * 100).toFixed(1) }}%
              </el-tag>
            </div>
            <div class="result-content">
              <pre>{{ doc.content }}</pre>
            </div>
            <div class="result-metadata" v-if="showMetadata">
              <el-descriptions :column="2" size="small" border>
                <el-descriptions-item
                  v-for="(value, key) in doc.metadata"
                  :key="key"
                  :label="key"
                >
                  {{ value }}
                </el-descriptions-item>
              </el-descriptions>
            </div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 搜索历史 -->
    <div class="search-history" v-if="searchHistory.length > 0">
      <el-card>
        <template #header>
          <div class="history-header">
            <span>搜索历史</span>
            <el-button text type="danger" @click="clearHistory">
              清空历史
            </el-button>
          </div>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="(item, index) in searchHistory"
            :key="index"
            :timestamp="formatTime(item.timestamp)"
            placement="top"
          >
            <el-card shadow="hover" class="history-item" @click="rerunSearch(item)">
              <div class="history-query">{{ item.query }}</div>
              <div class="history-stats">
                <el-tag size="small" type="info">{{ item.total }} 条结果</el-tag>
                <el-tag size="small" type="success">{{ item.search_time_ms }} ms</el-tag>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </div>

    <!-- 空状态 -->
    <div v-if="!lastResult && searchHistory.length === 0" class="empty-state">
      <el-empty description="输入内容开始检索">
        <template #image>
          <el-icon :size="80" color="#c0c4cc"><Search /></el-icon>
        </template>
      </el-empty>
      <div class="tips">
        <h4>💡 提示</h4>
        <ul>
          <li>纯向量检索只进行文档相似度匹配，不会调用LLM</li>
          <li>可用于测试检索速度，判断延迟是来自检索还是LLM</li>
          <li>支持调整 Top K 参数，返回更多或更少结果</li>
        </ul>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import { Search, Timer } from '@element-plus/icons-vue';
import { searchDocuments } from '@/services/api';

const query = ref('');
const topK = ref(5);
const searching = ref(false);
const lastResult = ref(null);
const searchHistory = ref([]);
const showMetadata = ref(false);

const handleSearch = async () => {
  if (!query.value.trim()) {
    ElMessage.warning('请输入检索内容');
    return;
  }

  searching.value = true;

  try {
    const result = await searchDocuments({
      query: query.value,
      top_k: topK.value
    });

    if (result.success) {
      lastResult.value = result.data;
      
      // 添加到历史记录
      searchHistory.value.unshift({
        ...result.data,
        timestamp: Date.now()
      });
      
      // 只保留最近10条历史
      if (searchHistory.value.length > 10) {
        searchHistory.value = searchHistory.value.slice(0, 10);
      }

      ElMessage.success(`检索完成，耗时 ${result.data.search_time_ms} ms`);
    } else {
      ElMessage.error(result.error || '检索失败');
    }
  } catch (error) {
    console.error('检索失败:', error);
    ElMessage.error('检索失败: ' + error.message);
  } finally {
    searching.value = false;
  }
};

const getSimilarityType = (similarity) => {
  if (similarity >= 0.8) return 'success';
  if (similarity >= 0.6) return 'warning';
  return 'info';
};

const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN');
};

const clearHistory = () => {
  searchHistory.value = [];
  ElMessage.success('历史已清空');
};

const rerunSearch = (item) => {
  query.value = item.query;
  handleSearch();
};
</script>

<style scoped>
.vector-search {
  padding: 20px;
}

.search-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: flex-end;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.timing-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.query-info {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  margin-bottom: 16px;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.result-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 16px;
  transition: box-shadow 0.2s;
}

.result-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.result-item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.result-rank {
  font-size: 18px;
  font-weight: bold;
  color: #409eff;
  min-width: 40px;
}

.result-source {
  flex: 1;
  font-weight: 500;
  color: #303133;
}

.result-content {
  background-color: #fafafa;
  border-radius: 4px;
  padding: 12px;
  max-height: 200px;
  overflow-y: auto;
}

.result-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.result-metadata {
  margin-top: 12px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.history-item {
  cursor: pointer;
  transition: transform 0.2s;
}

.history-item:hover {
  transform: translateX(4px);
}

.history-query {
  font-weight: 500;
  margin-bottom: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-stats {
  display: flex;
  gap: 8px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 40px;
}

.tips {
  margin-top: 24px;
  padding: 20px;
  background-color: #f5f7fa;
  border-radius: 8px;
  max-width: 500px;
}

.tips h4 {
  margin-top: 0;
  margin-bottom: 12px;
}

.tips ul {
  margin: 0;
  padding-left: 20px;
}

.tips li {
  margin-bottom: 8px;
  color: #606266;
}

.empty-results {
  padding: 40px 0;
}
</style>

