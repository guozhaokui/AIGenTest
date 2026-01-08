<template>
  <div class="query-interface">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>智能问答</span>
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
    <div class="query-history" v-if="queryHistory.length > 0">
      <el-card
        v-for="(item, index) in queryHistory"
        :key="index"
        style="margin-top: 20px"
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
            title="未配置NVIDIA API或生成失败"
            type="warning"
            :closable="false"
          />
          <div v-else class="answer-content">
            <strong>回答:</strong>
            <div class="answer-text">{{ item.answer }}</div>
            <el-tag size="small" style="margin-top: 10px">
              模型: {{ item.model }}
            </el-tag>
          </div>
        </div>

        <!-- 检索到的文档 -->
        <el-divider content-position="left">检索到的相关文档</el-divider>
        <div class="context-docs">
          <el-collapse>
            <el-collapse-item
              v-for="doc in item.context"
              :key="doc.index"
              :title="`文档${doc.index}: ${doc.source} (相似度: ${(doc.similarity * 100).toFixed(1)}%)`"
            >
              <pre class="doc-content">{{ doc.content }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-card>
    </div>

    <!-- 空状态 -->
    <el-empty
      v-if="queryHistory.length === 0 && !querying"
      description="请输入问题开始查询"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { Search } from '@element-plus/icons-vue';
import { queryKnowledge, getKnowledgeModels } from '@/services/api';

const question = ref('');
const selectedModel = ref('deepseek-ai/deepseek-v3.2');
const querying = ref(false);
const queryHistory = ref([]);
const models = ref([]);

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

const loadModels = async () => {
  try {
    const result = await getKnowledgeModels();
    if (result.success) {
      models.value = result.data;
    }
  } catch (error) {
    console.error('加载模型列表失败:', error);
  }
};

onMounted(() => {
  loadModels();
});
</script>

<style scoped>
.query-interface {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.query-input {
  margin-bottom: 20px;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  background-color: #f5f7fa;
  border-radius: 4px;
}

.answer-text {
  margin-top: 10px;
  white-space: pre-wrap;
  line-height: 1.6;
}

.context-docs {
  margin-top: 10px;
}

.doc-content {
  white-space: pre-wrap;
  background-color: #f9f9f9;
  padding: 10px;
  border-radius: 4px;
  max-height: 300px;
  overflow-y: auto;
}
</style>
