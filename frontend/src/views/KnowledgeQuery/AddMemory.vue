<template>
  <div class="memory-management">
    <!-- 统计信息 -->
    <el-card shadow="never" class="stats-card">
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
    </el-card>

    <!-- 操作区域 -->
    <el-card shadow="never" class="action-card">
      <template #header>
        <span style="font-weight: 600;">操作</span>
      </template>
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

    <!-- 添加记忆 -->
    <el-card shadow="never" class="add-card">
      <template #header>
        <div class="card-header">
          <span style="font-weight: 600;">添加记忆</span>
          <el-button type="primary" @click="handleAddMemory" :loading="adding">
            <el-icon><Plus /></el-icon>
            保存记忆 (Ctrl+Enter)
          </el-button>
        </div>
      </template>

      <div class="form-content">
        <div class="title-input">
          <el-input
            v-model="memoryTitle"
            placeholder="输入记忆标题（必填）"
            clearable
          >
            <template #prepend>标题</template>
          </el-input>
        </div>

        <el-input
          v-model="memoryContent"
          type="textarea"
          :rows="12"
          placeholder="输入记忆内容..."
          @keydown.ctrl.enter="handleAddMemory"
        />

        <div class="tags-section">
          <div class="tags-label">标签：</div>
          <div class="tags-input">
            <el-tag
              v-for="tag in tags"
              :key="tag"
              closable
              @close="removeTag(tag)"
              style="margin-right: 8px; margin-bottom: 8px"
            >
              {{ tag }}
            </el-tag>
            <el-input
              v-if="inputVisible"
              ref="inputRef"
              v-model="inputValue"
              size="small"
              style="width: 120px"
              @keyup.enter="handleInputConfirm"
              @blur="handleInputConfirm"
            />
            <el-button v-else size="small" @click="showInput">
              <el-icon><Plus /></el-icon>
              添加标签
            </el-button>
          </div>
        </div>

        <div class="meta-section">
          <el-form label-width="80px" size="small">
            <el-form-item label="项目名称">
              <el-input v-model="project" placeholder="可选" style="width: 300px" />
            </el-form-item>
            <el-form-item label="目录路径">
              <el-input v-model="directory" placeholder="可选" style="width: 400px" />
            </el-form-item>
          </el-form>
        </div>
      </div>
    </el-card>

    <!-- 最近添加的记忆 -->
    <el-card shadow="never" class="recent-card" v-if="recentMemories.length > 0">
      <template #header>
        <span>最近添加的记忆（{{ recentMemories.length }}）</span>
      </template>

      <div class="recent-list">
        <div v-for="(memory, index) in recentMemories" :key="index" class="memory-item">
          <div class="memory-header">
            <span class="memory-title">{{ memory.title }}</span>
            <span class="memory-time">{{ memory.time }}</span>
          </div>
          <div class="memory-tags" v-if="memory.tags && memory.tags.length > 0">
            <el-tag v-for="tag in memory.tags" :key="tag" size="small">
              {{ tag }}
            </el-tag>
          </div>
          <div class="memory-content">{{ memory.content }}</div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Plus, Refresh, Upload, Delete, Document, Grid, DataAnalysis } from '@element-plus/icons-vue';
import { scanDocuments, clearKnowledge, getStats } from '@/services/api';

const memoryTitle = ref('');
const memoryContent = ref('');
const adding = ref(false);
const tags = ref([]);
const inputVisible = ref(false);
const inputValue = ref('');
const inputRef = ref(null);
const project = ref('');
const directory = ref('');
const recentMemories = ref([]);

// 文档管理相关
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

// 刷新索引
const handleRefresh = async () => {
  refreshing.value = true;
  progressMessage.value = '正在刷新索引...';
  progressDetails.value = '';

  try {
    const result = await scanDocuments();
    if (result.success) {
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
            await loadStats();
          } else if (progress.phase === 'error') {
            progressMessage.value = '';
            progressDetails.value = '';
            ElMessage.error('刷新失败: ' + progress.message);
            refreshing.value = false;
          } else if (progress.in_progress) {
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

// 清空知识库
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

const handleAddMemory = async () => {
  if (!memoryTitle.value.trim()) {
    ElMessage.warning('请输入记忆标题');
    return;
  }

  if (!memoryContent.value.trim()) {
    ElMessage.warning('请输入记忆内容');
    return;
  }

  adding.value = true;

  try {
    const response = await fetch('http://localhost:8848/record', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        role: 'AI',
        project: project.value,
        directory: directory.value,
        problem: memoryTitle.value,
        solution: memoryContent.value,
        tags: tags.value
      })
    });

    const result = await response.json();

    if (result.success) {
      ElMessage.success('记忆已保存');

      // 添加到最近记忆列表
      recentMemories.value.unshift({
        time: new Date().toLocaleString('zh-CN'),
        title: memoryTitle.value,
        content: memoryContent.value,
        tags: [...tags.value]
      });

      // 只保留最近10条
      if (recentMemories.value.length > 10) {
        recentMemories.value = recentMemories.value.slice(0, 10);
      }

      // 清空输入
      memoryTitle.value = '';
      memoryContent.value = '';
      tags.value = [];

      // 更新统计信息
      await loadStats();
    } else {
      ElMessage.error('保存失败: ' + (result.error || '未知错误'));
    }
  } catch (error) {
    console.error('保存失败:', error);
    ElMessage.error('保存失败: ' + error.message);
  } finally {
    adding.value = false;
  }
};

const removeTag = (tag) => {
  tags.value = tags.value.filter(t => t !== tag);
};

const showInput = () => {
  inputVisible.value = true;
  nextTick(() => {
    inputRef.value.focus();
  });
};

const handleInputConfirm = () => {
  if (inputValue.value && !tags.value.includes(inputValue.value)) {
    tags.value.push(inputValue.value);
  }
  inputVisible.value = false;
  inputValue.value = '';
};

onMounted(() => {
  loadStats();
});
</script>

<style scoped>
.memory-management {
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.stats-card,
.action-card,
.add-card,
.recent-card {
  margin-bottom: 20px;
  max-width: 1200px;
  margin-left: auto;
  margin-right: auto;
}

.stats-container {
  padding: 10px 0;
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

.progress-message {
  margin-top: 20px;
}

.add-card :deep(.el-card__header) {
  padding: 16px;
  border-bottom: 1px solid #dcdfe6;
}

.add-card :deep(.el-card__body) {
  padding: 16px;
}

.recent-card {
  border-radius: 0;
  margin-top: 0;
  flex: 1;
  overflow: hidden;
}

.recent-card :deep(.el-card__header) {
  padding: 16px;
  border-bottom: 1px solid #dcdfe6;
}

.recent-card :deep(.el-card__body) {
  padding: 16px;
  height: calc(100% - 56px);
  overflow-y: auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tags-section {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.tags-label {
  padding-top: 4px;
  color: #606266;
  font-size: 14px;
  white-space: nowrap;
}

.tags-input {
  flex: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.meta-section {
  padding-top: 8px;
  border-top: 1px solid #dcdfe6;
}

.recent-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.title-input {
  margin-bottom: 16px;
}

.memory-item {
  padding: 12px;
  background-color: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 0;
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e4e7ed;
}

.memory-title {
  font-weight: 600;
  color: #303133;
  font-size: 14px;
}

.memory-time {
  color: #909399;
  font-size: 12px;
}

.memory-tags {
  margin-bottom: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.memory-content {
  white-space: pre-wrap;
  line-height: 1.6;
  color: #606266;
  font-size: 14px;
}
</style>
