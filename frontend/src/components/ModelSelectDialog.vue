<template>
  <el-dialog
    v-model="visible"
    title="选择 3D 模型"
    width="800px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <!-- 过滤器 -->
    <div class="filter-bar">
      <el-select v-model="filterDriver" placeholder="按驱动过滤" clearable size="small" style="width: 150px;">
        <el-option label="全部" value="" />
        <el-option label="Tripo" value="tripo" />
        <el-option label="Meshy" value="meshy" />
        <el-option label="Doubao" value="doubao" />
        <el-option label="Trellis" value="trellis" />
      </el-select>
      <el-button size="small" @click="loadModels" :loading="loading">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <!-- 模型网格 -->
    <div class="model-grid" v-loading="loading">
      <div v-if="models.length === 0 && !loading" class="empty-state">
        <el-empty description="暂无生成的 3D 模型" />
      </div>
      
      <div
        v-for="model in models"
        :key="model.modelDir"
        class="model-card"
        :class="{ selected: selectedModel?.modelDir === model.modelDir }"
        @click="selectModel(model)"
      >
        <div class="thumbnail-wrapper">
          <img
            v-if="model.thumbnail"
            :src="model.thumbnail"
            :alt="model.meta?.taskType || '3D模型'"
            class="thumbnail"
          />
          <div v-else class="no-thumbnail">
            <el-icon :size="32"><Picture /></el-icon>
            <span>无缩略图</span>
          </div>
        </div>
        
        <div class="model-info">
          <div class="task-type">{{ formatTaskType(model.meta?.taskType) }}</div>
          <div class="model-version" v-if="model.meta?.modelVersion">
            {{ model.meta.modelVersion }}
          </div>
          <div class="task-id" :title="model.meta?.taskId">
            {{ truncateId(model.meta?.taskId) }}
          </div>
          <div class="created-at">{{ formatDate(model.createdAt) }}</div>
        </div>
        
        <div class="driver-badge" :class="model.meta?.driver">
          {{ model.meta?.driver || '未知' }}
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" :disabled="!selectedModel" @click="handleConfirm">
          确认选择
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue';
import { Refresh, Picture } from '@element-plus/icons-vue';
import axios from 'axios';

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  driverFilter: { type: String, default: '' },
  // 过滤任务类型（数组，如 ['image_to_model', 'text_to_model']）
  taskTypeFilter: { type: Array, default: () => [] },
  // 排除的模型版本（数组，如 ['v2.0', 'v2.5', 'v3.0']）
  excludeVersions: { type: Array, default: () => [] }
});

const emit = defineEmits(['update:modelValue', 'select']);

const visible = ref(props.modelValue);
const loading = ref(false);
const models = ref([]);
const selectedModel = ref(null);
const filterDriver = ref(props.driverFilter);

watch(() => props.modelValue, (val) => {
  visible.value = val;
  if (val) {
    loadModels();
  }
});

watch(visible, (val) => {
  emit('update:modelValue', val);
});

watch(filterDriver, () => {
  loadModels();
});

async function loadModels() {
  loading.value = true;
  try {
    const params = { limit: 100 };
    if (filterDriver.value) {
      params.driver = filterDriver.value;
    }
    // 添加任务类型过滤
    if (props.taskTypeFilter && props.taskTypeFilter.length > 0) {
      params.taskTypes = props.taskTypeFilter.join(',');
    }
    // 添加版本排除过滤
    if (props.excludeVersions && props.excludeVersions.length > 0) {
      params.excludeVersions = props.excludeVersions.join(',');
    }
    const res = await axios.get('/api/models/generated', { params });
    models.value = res.data.items || [];
  } catch (e) {
    console.error('Failed to load models:', e);
    models.value = [];
  } finally {
    loading.value = false;
  }
}

function selectModel(model) {
  selectedModel.value = model;
}

function handleClose() {
  visible.value = false;
  selectedModel.value = null;
}

function handleConfirm() {
  if (selectedModel.value) {
    emit('select', selectedModel.value);
  }
  handleClose();
}

function formatTaskType(type) {
  const typeMap = {
    'image_to_model': '图片转3D',
    'text_to_model': '文字转3D',
    'multiview_to_model': '多视图3D',
    'refine_model': '优化模型'
  };
  return typeMap[type] || type || '未知';
}

function truncateId(id) {
  if (!id) return '-';
  if (id.length <= 16) return id;
  return id.slice(0, 8) + '...' + id.slice(-4);
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch {
    return dateStr;
  }
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  max-height: 500px;
  overflow-y: auto;
  padding: 4px;
}

.model-card {
  border: 2px solid #e4e7ed;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.2s;
  background: #fff;
  position: relative;
}

.model-card:hover {
  border-color: #409eff;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.15);
}

.model-card.selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.thumbnail-wrapper {
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.thumbnail {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.no-thumbnail {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #909399;
}

.model-info {
  padding: 8px;
  font-size: 12px;
}

.task-type {
  font-weight: 500;
  color: #303133;
  margin-bottom: 2px;
}

.model-version {
  color: #67c23a;
  font-size: 11px;
  font-weight: 500;
}

.task-id {
  color: #909399;
  font-family: monospace;
  font-size: 11px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.created-at {
  color: #909399;
  font-size: 11px;
  margin-top: 2px;
}

.driver-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
  text-transform: uppercase;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
}

.driver-badge.tripo {
  background: #409eff;
}

.driver-badge.meshy {
  background: #67c23a;
}

.driver-badge.doubao {
  background: #e6a23c;
}

.driver-badge.trellis {
  background: #909399;
}

.empty-state {
  grid-column: 1 / -1;
  padding: 40px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>

