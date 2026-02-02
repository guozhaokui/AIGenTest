<template>
  <div class="document-management">
    <el-card shadow="never" class="main-card">
      <template #header>
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <span style="font-size: 18px; font-weight: 600;">文档管理</span>
        </div>
      </template>

      <!-- 统计信息 -->
      <div class="stats-container">
        <el-row :gutter="20">
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-icon" style="background: #ecf5ff; color: #409eff;">
                <el-icon :size="32"><Document /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats.documents }}</div>
                <div class="stat-label">文档数量</div>
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-icon" style="background: #f0f9ff; color: #67c23a;">
                <el-icon :size="32"><Grid /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats.faiss_vectors }}</div>
                <div class="stat-label">向量数量</div>
              </div>
            </div>
          </el-col>
          <el-col :span="8">
            <div class="stat-card">
              <div class="stat-icon" style="background: #fef0f0; color: #f56c6c;">
                <el-icon :size="32"><DataAnalysis /></el-icon>
              </div>
              <div class="stat-content">
                <div class="stat-value">{{ stats.dimension }}</div>
                <div class="stat-label">向量维度</div>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 操作按钮 -->
      <el-divider content-position="left">操作</el-divider>
      <div class="action-area">
        <el-space :size="15" wrap>
          <el-button type="primary" @click="handleRefresh" :loading="refreshing" size="large">
            <el-icon><Refresh /></el-icon>
            刷新索引
          </el-button>
          <el-upload
            :action="uploadUrl"
            :show-file-list="false"
            :on-success="handleUploadSuccess"
            :on-error="handleUploadError"
            :before-upload="beforeUpload"
            accept=".txt,.md,.py,.js,.json,.csv,.xml,.html,.css,.yaml,.yml,.log"
          >
            <el-button type="success" :loading="uploading" size="large">
              <el-icon><Upload /></el-icon>
              上传文件
            </el-button>
          </el-upload>
          <el-button type="danger" @click="handleClearAll" :loading="clearing" size="large">
            <el-icon><Delete /></el-icon>
            清空知识库
          </el-button>
        </el-space>
      </div>

      <!-- 进度提示 -->
      <div v-if="progressMessage" class="progress-message">
        <el-alert :title="progressMessage" type="info" :closable="false" show-icon>
          <template #default>
            <div v-if="progressDetails">
              {{ progressDetails }}
            </div>
          </template>
        </el-alert>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Refresh, Upload, Delete, Document, Grid, DataAnalysis } from '@element-plus/icons-vue';
import { scanDocuments, clearKnowledge, getStats } from '@/services/api';

const refreshing = ref(false);
const clearing = ref(false);
const uploading = ref(false);
const progressMessage = ref('');
const progressDetails = ref('');
const stats = ref({
  documents: 0,
  faiss_vectors: 0,
  dimension: 512
});

// 上传URL
const uploadUrl = 'http://localhost:8848/upload';

// 加载统计信息
const loadStats = async () => {
  try {
    const result = await getStats();
    if (result.success) {
      stats.value = result.data;
    }
  } catch (error) {
    console.error('加载统计失败:', error);
  }
};

const handleRefresh = async () => {
  refreshing.value = true;
  progressMessage.value = '正在刷新索引...';
  progressDetails.value = '';

  try {
    // 启动rebuild
    const result = await scanDocuments();
    if (result.success) {
      // 轮询进度
      const checkProgress = async () => {
        try {
          const progressRes = await fetch('http://localhost:8848/rebuild/progress');
          const progress = await progressRes.json();

          if (progress.in_progress) {
            progressMessage.value = '正在刷新索引...';
            progressDetails.value = `${progress.message} (${progress.current}/${progress.total})`;
          }

          if (progress.phase === 'completed') {
            progressMessage.value = '';
            progressDetails.value = '';
            ElMessage.success('刷新完成');
            refreshing.value = false;
            // 重新加载统计信息
            await loadStats();
          } else if (progress.phase === 'error') {
            progressMessage.value = '';
            progressDetails.value = '';
            ElMessage.error('刷新失败: ' + progress.message);
            refreshing.value = false;
          } else if (progress.in_progress) {
            // 继续轮询
            setTimeout(checkProgress, 1000);
          } else {
            progressMessage.value = '';
            progressDetails.value = '';
            refreshing.value = false;
          }
        } catch (error) {
          console.error('检查进度失败:', error);
          progressMessage.value = '';
          progressDetails.value = '';
          refreshing.value = false;
        }
      };

      // 开始轮询
      setTimeout(checkProgress, 1000);
    } else {
      ElMessage.error(result.error || '刷新失败');
      progressMessage.value = '';
      progressDetails.value = '';
      refreshing.value = false;
    }
  } catch (error) {
    console.error('刷新失败:', error);
    ElMessage.error('刷新失败: ' + error.message);
    progressMessage.value = '';
    progressDetails.value = '';
    refreshing.value = false;
  }
};

const handleClearAll = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空整个知识库吗？此操作不可恢复！',
      '警告',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    clearing.value = true;
    const result = await clearKnowledge();

    if (result.success) {
      ElMessage.success('知识库已清空');
      await loadStats();
    } else {
      ElMessage.error(result.error || '清空失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空失败:', error);
      ElMessage.error('清空失败');
    }
  } finally {
    clearing.value = false;
  }
};

// 上传前验证
const beforeUpload = (file) => {
  const maxSize = 10 * 1024 * 1024; // 10MB
  if (file.size > maxSize) {
    ElMessage.error('文件大小不能超过 10MB');
    return false;
  }
  uploading.value = true;
  return true;
};

// 上传成功
const handleUploadSuccess = (response) => {
  uploading.value = false;
  if (response.success) {
    ElMessage.success(`文件上传成功: ${response.filename}`);
    // 刷新索引
    handleRefresh();
  } else {
    ElMessage.error('上传失败: ' + (response.error || '未知错误'));
  }
};

// 上传失败
const handleUploadError = (error) => {
  uploading.value = false;
  console.error('上传失败:', error);
  ElMessage.error('上传失败: ' + error.message);
};

onMounted(() => {
  // 加载统计信息
  loadStats();
});
</script>

<style scoped>
.document-management {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.main-card {
  max-width: 1200px;
  margin: 0 auto;
}

.stats-container {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  background: white;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  transition: all 0.3s;
}

.stat-card:hover {
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  transform: translateY(-2px);
}

.stat-icon {
  width: 64px;
  height: 64px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 16px;
}

.stat-content {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  line-height: 1;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
}

.action-area {
  margin-top: 20px;
}

.progress-message {
  margin-top: 20px;
}
</style>
