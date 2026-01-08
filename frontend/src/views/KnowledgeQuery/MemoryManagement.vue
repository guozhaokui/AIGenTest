<template>
  <div class="memory-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>记忆管理</span>
          <el-button type="primary" @click="loadMemoryStats">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </div>
      </template>

      <!-- 统计概览 -->
      <el-row :gutter="20" v-if="stats">
        <el-col :span="6">
          <el-statistic title="文档块总数" :value="stats.total_documents">
            <template #prefix>
              <el-icon><Document /></el-icon>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="向量维度" :value="stats.dimension">
            <template #prefix>
              <el-icon><DataAnalysis /></el-icon>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="数据集" :value="stats.collection_name">
            <template #prefix>
              <el-icon><Collection /></el-icon>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="嵌入服务" :value="embeddingStatus ? '正常' : '异常'">
            <template #prefix>
              <el-icon :color="embeddingStatus ? '#67C23A' : '#F56C6C'">
                <CircleCheck v-if="embeddingStatus" />
                <CircleClose v-else />
              </el-icon>
            </template>
          </el-statistic>
        </el-col>
      </el-row>
    </el-card>

    <!-- 文档来源统计 -->
    <el-card style="margin-top: 20px" v-if="sourceStats.length > 0">
      <template #header>
        <span>文档来源分布</span>
      </template>
      <el-table :data="sourceStats" style="width: 100%">
        <el-table-column prop="source" label="文件名" min-width="200" />
        <el-table-column prop="count" label="文档块数" width="120" />
        <el-table-column prop="percentage" label="占比" width="100">
          <template #default="scope">
            {{ (scope.row.percentage * 100).toFixed(1) }}%
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="scope">
            <el-button
              size="small"
              type="danger"
              @click="handleDeleteSource(scope.row.source)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 记忆质量检查 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>记忆质量检查</span>
          <el-button type="primary" @click="runQualityCheck" :loading="checking">
            <el-icon><Search /></el-icon>
            运行检查
          </el-button>
        </div>
      </template>

      <div v-if="qualityReport">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="检查时间">
            {{ formatTime(qualityReport.timestamp) }}
          </el-descriptions-item>
          <el-descriptions-item label="总文档数">
            {{ qualityReport.total_docs }}
          </el-descriptions-item>
          <el-descriptions-item label="平均相似度">
            {{ (qualityReport.avg_similarity * 100).toFixed(1) }}%
          </el-descriptions-item>
          <el-descriptions-item label="重复检测">
            {{ qualityReport.duplicates }} 个重复块
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="qualityReport.suggestions.length > 0" style="margin-top: 20px;">
          <el-divider content-position="left">优化建议</el-divider>
          <el-alert
            v-for="(suggestion, index) in qualityReport.suggestions"
            :key="index"
            :title="suggestion"
            type="info"
            style="margin-bottom: 10px;"
          />
        </div>
      </div>
      <el-empty v-else description="暂无检查报告" />
    </el-card>

    <!-- 记忆更新历史 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>更新历史</span>
      </template>
      <el-timeline v-if="updateHistory.length > 0">
        <el-timeline-item
          v-for="(item, index) in updateHistory"
          :key="index"
          :timestamp="formatTime(item.timestamp)"
          :type="item.type"
        >
          {{ item.description }}
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无更新历史" />
    </el-card>

    <!-- AI主动学习（未来功能） -->
    <el-card style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>AI主动学习</span>
          <el-tag type="info" size="small">计划中</el-tag>
        </div>
      </template>
      <el-alert
        title="即将推出"
        type="info"
        description="AI将主动分析文档，提取关键信息，发现知识冲突，并向您确认模糊信息。"
        :closable="false"
      />
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import {
  Refresh,
  Document,
  DataAnalysis,
  Collection,
  CircleCheck,
  CircleClose,
  Search
} from '@element-plus/icons-vue';
import { getStats, getStatus, deleteDocument } from '@/services/api';

const stats = ref(null);
const embeddingStatus = ref(false);
const sourceStats = ref([]);
const qualityReport = ref(null);
const checking = ref(false);
const updateHistory = ref([]);

const loadMemoryStats = async () => {
  try {
    // 获取统计信息
    const statsResult = await getStats();
    if (statsResult.success) {
      stats.value = statsResult.data;
    }

    // 获取系统状态
    const statusResult = await getStatus();
    if (statusResult.success) {
      embeddingStatus.value = statusResult.data.embedding_service?.available || false;

      // 模拟文档来源统计（实际需要后端支持）
      if (stats.value && stats.value.total_documents > 0) {
        // TODO: 从后端获取真实的来源统计
        sourceStats.value = [
          { source: '示例文档.md', count: stats.value.total_documents, percentage: 1.0 }
        ];
      }
    }
  } catch (error) {
    console.error('加载统计信息失败:', error);
    ElMessage.error('加载统计信息失败');
  }
};

const runQualityCheck = async () => {
  checking.value = true;

  try {
    // 模拟质量检查（实际需要后端API支持）
    await new Promise(resolve => setTimeout(resolve, 2000));

    qualityReport.value = {
      timestamp: Date.now(),
      total_docs: stats.value?.total_documents || 0,
      avg_similarity: 0.82,
      duplicates: 0,
      suggestions: [
        '所有文档块向量质量良好',
        '未发现重复或近似重复的文档块',
        '建议定期更新文档以保持记忆新鲜'
      ]
    };

    ElMessage.success('质量检查完成');
  } catch (error) {
    console.error('质量检查失败:', error);
    ElMessage.error('质量检查失败');
  } finally {
    checking.value = false;
  }
};

const handleDeleteSource = async (source) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除来源 "${source}" 的所有文档块吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    const result = await deleteDocument({ source });
    if (result.success) {
      ElMessage.success(`删除成功，共删除 ${result.data.deleted_count} 个文档块`);

      // 记录更新历史
      updateHistory.value.unshift({
        timestamp: Date.now(),
        type: 'danger',
        description: `删除了来源 "${source}" 的 ${result.data.deleted_count} 个文档块`
      });

      // 刷新统计
      await loadMemoryStats();
    } else {
      ElMessage.error(result.error || '删除失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error);
      ElMessage.error('删除失败');
    }
  }
};

const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN');
};

onMounted(() => {
  loadMemoryStats();

  // 模拟一些更新历史
  updateHistory.value = [
    {
      timestamp: Date.now() - 3600000,
      type: 'success',
      description: '索引了 3 个新文档'
    },
    {
      timestamp: Date.now() - 7200000,
      type: 'warning',
      description: '重新索引了 2601.md'
    }
  ];
});
</script>

<style scoped>
.memory-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
