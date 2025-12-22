<template>
  <div class="batch-import">
    <el-tabs v-model="activeTab">
      <!-- 目录导入 -->
      <el-tab-pane label="目录导入" name="import">
        <el-form :model="importForm" label-width="120px" class="import-form">
          <el-form-item label="目录路径" required>
            <el-input 
              v-model="importForm.directory" 
              placeholder="输入服务器上的目录绝对路径，如 /data/images"
              :disabled="importing"
            />
          </el-form-item>
          <el-form-item label="来源标记">
            <el-input v-model="importForm.source" placeholder="可选，用于标记图片来源" :disabled="importing" />
          </el-form-item>
          <el-form-item label="递归扫描">
            <el-switch v-model="importForm.recursive" :disabled="importing" />
            <span class="form-tip">扫描子目录中的图片</span>
          </el-form-item>
          <el-form-item label="强制重导入">
            <el-switch v-model="importForm.force_reimport" :disabled="importing" />
            <span class="form-tip">已存在的图片也重新计算嵌入</span>
          </el-form-item>
          <el-form-item label="生成描述">
            <el-switch v-model="importForm.generate_caption" :disabled="importing" />
            <span class="form-tip">使用 VLM 自动生成图片描述</span>
          </el-form-item>
          <el-form-item label="VLM 服务" v-if="importForm.generate_caption">
            <el-select v-model="importForm.vlm_service" placeholder="选择 VLM 服务" clearable style="width: 200px;" :disabled="importing">
              <el-option v-for="s in vlmServices" :key="s.id" :label="s.name" :value="s.id">
                <span>{{ s.name }}</span>
                <span class="service-desc">{{ s.description }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">留空使用默认服务</span>
          </el-form-item>
          <el-form-item label="描述方法" v-if="importForm.generate_caption">
            <el-input v-model="importForm.caption_method" style="width: 200px;" :disabled="importing" />
          </el-form-item>
          <el-form-item label="提示词" v-if="importForm.generate_caption">
            <el-select v-model="importForm.caption_prompt" placeholder="选择提示词模板" style="width: 200px;" :disabled="importing">
              <el-option v-for="p in vlmPrompts" :key="p.name" :label="p.name" :value="p.name">
                <span>{{ p.name }}</span>
                <span class="prompt-preview">{{ p.text }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">或留空使用默认提示词</span>
          </el-form-item>
          <el-form-item label="并发数">
            <el-input-number v-model="importForm.concurrency" :min="1" :max="16" :disabled="importing" />
            <span class="form-tip">同时处理的图片数量（并发请求嵌入服务）</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleImport" :loading="importing">
              {{ importing ? '导入中...' : '开始导入' }}
            </el-button>
            <el-button v-if="importing" @click="cancelImport" type="danger">取消</el-button>
          </el-form-item>
        </el-form>

        <!-- 进度显示 -->
        <div v-if="importProgress" class="progress-panel">
          <div class="progress-header">
            <span class="progress-title">导入进度</span>
            <span class="progress-stats">
              {{ importProgress.current }} / {{ importProgress.total }}
              <span class="speed">{{ importProgress.speed }} 张/秒</span>
            </span>
          </div>
          <el-progress :percentage="importProgress.percent" :stroke-width="20" />
          <div class="progress-info">
            <div class="info-row">
              <span class="label">已导入:</span>
              <el-tag type="success" size="small">{{ importProgress.imported }}</el-tag>
              <span class="label">跳过:</span>
              <el-tag type="info" size="small">{{ importProgress.skipped }}</el-tag>
              <span class="label">失败:</span>
              <el-tag type="danger" size="small">{{ importProgress.failed }}</el-tag>
            </div>
            <div class="info-row">
              <span class="label">已用时:</span>
              <span>{{ formatTime(importProgress.elapsed) }}</span>
              <span class="label">预计剩余:</span>
              <span>{{ formatTime(importProgress.eta) }}</span>
            </div>
            <div class="current-item" v-if="importProgress.item">
              <span class="label">当前:</span>
              <span class="filename">{{ importProgress.item.file }}</span>
              <el-tag :type="statusType[importProgress.item.status]" size="small">{{ importProgress.item.status }}</el-tag>
            </div>
          </div>
        </div>

        <!-- 完成结果 -->
        <div v-if="importResult && !importing" class="import-result">
          <el-alert 
            :title="`导入完成: ${importResult.imported} 成功, ${importResult.skipped} 跳过, ${importResult.failed} 失败`"
            :type="importResult.failed > 0 ? 'warning' : 'success'"
            show-icon
          >
            <template #default>
              <div>总耗时: {{ formatTime(importResult.elapsed) }}，平均速度: {{ importResult.avg_speed }} 张/秒</div>
            </template>
          </el-alert>
        </div>
      </el-tab-pane>

      <!-- 批量生成描述 -->
      <el-tab-pane label="批量生成描述" name="captions">
        <el-form :model="captionForm" label-width="120px" class="import-form">
          <el-form-item label="来源筛选">
            <el-input v-model="captionForm.source" placeholder="只处理指定来源的图片（可选）" :disabled="generatingCaptions" />
          </el-form-item>
          <el-form-item label="VLM 服务">
            <el-select v-model="captionForm.vlm_service" placeholder="选择 VLM 服务" clearable style="width: 200px;" :disabled="generatingCaptions">
              <el-option v-for="s in vlmServices" :key="s.id" :label="s.name" :value="s.id">
                <span>{{ s.name }}</span>
                <span class="service-desc">{{ s.description }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">留空使用默认服务</span>
          </el-form-item>
          <el-form-item label="描述方法">
            <el-input v-model="captionForm.method" style="width: 200px;" :disabled="generatingCaptions" />
          </el-form-item>
          <el-form-item label="提示词">
            <el-select v-model="captionForm.prompt" placeholder="选择提示词模板" clearable style="width: 200px;" :disabled="generatingCaptions">
              <el-option v-for="p in vlmPrompts" :key="p.name" :label="p.name" :value="p.name">
                <span>{{ p.name }}</span>
                <span class="prompt-preview">{{ p.text }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">留空使用默认提示词</span>
          </el-form-item>
          <el-form-item label="覆盖已有">
            <el-switch v-model="captionForm.overwrite" :disabled="generatingCaptions" />
            <span class="form-tip">覆盖已有的同类型描述</span>
          </el-form-item>
          <el-form-item label="最大数量">
            <el-input-number v-model="captionForm.limit" :min="1" :max="1000" :disabled="generatingCaptions" />
          </el-form-item>
          <el-form-item label="并发数">
            <el-input-number v-model="captionForm.concurrency" :min="1" :max="16" :disabled="generatingCaptions" />
            <span class="form-tip">同时处理的图片数量</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleGenerateCaptions" :loading="generatingCaptions">
              {{ generatingCaptions ? '生成中...' : '开始生成' }}
            </el-button>
            <el-button v-if="generatingCaptions" @click="cancelCaptions" type="danger">取消</el-button>
          </el-form-item>
        </el-form>

        <!-- 进度显示 -->
        <div v-if="captionProgress" class="progress-panel">
          <div class="progress-header">
            <span class="progress-title">生成进度</span>
            <span class="progress-stats">
              {{ captionProgress.current }} / {{ captionProgress.total }}
              <span class="speed">{{ captionProgress.speed }} 张/秒</span>
            </span>
          </div>
          <el-progress :percentage="captionProgress.percent" :stroke-width="20" />
          <div class="progress-info">
            <div class="info-row">
              <span class="label">成功:</span>
              <el-tag type="success" size="small">{{ captionProgress.processed }}</el-tag>
              <span class="label">跳过:</span>
              <el-tag type="info" size="small">{{ captionProgress.skipped }}</el-tag>
              <span class="label">失败:</span>
              <el-tag type="danger" size="small">{{ captionProgress.failed }}</el-tag>
            </div>
            <div class="info-row">
              <span class="label">已用时:</span>
              <span>{{ formatTime(captionProgress.elapsed) }}</span>
              <span class="label">预计剩余:</span>
              <span>{{ formatTime(captionProgress.eta) }}</span>
            </div>
            <div class="current-item" v-if="captionProgress.item">
              <span class="label">当前:</span>
              <span class="filename">{{ captionProgress.item.sha256 }}</span>
              <span class="message">{{ captionProgress.item.message }}</span>
            </div>
          </div>
        </div>

        <div v-if="captionResult && !generatingCaptions" class="import-result">
          <el-alert 
            :title="`生成完成: ${captionResult.processed} 成功, ${captionResult.skipped} 跳过, ${captionResult.failed} 失败`"
            :type="captionResult.failed > 0 ? 'warning' : 'success'"
            show-icon
          >
            <template #default>
              <div>总耗时: {{ formatTime(captionResult.elapsed) }}，平均速度: {{ captionResult.avg_speed }} 张/秒</div>
            </template>
          </el-alert>
        </div>
      </el-tab-pane>

      <!-- 批量更新嵌入 -->
      <el-tab-pane label="批量更新嵌入" name="embeddings">
        <el-form :model="embeddingForm" label-width="120px" class="import-form">
          <el-form-item label="来源筛选">
            <el-input v-model="embeddingForm.source" placeholder="只处理指定来源的图片（可选）" :disabled="recomputing" />
          </el-form-item>
          <el-form-item label="状态筛选">
            <el-select v-model="embeddingForm.status" clearable placeholder="全部" :disabled="recomputing">
              <el-option label="全部" value="" />
              <el-option label="就绪" value="ready" />
              <el-option label="待处理" value="pending" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
          <el-form-item label="更新文本嵌入">
            <el-switch v-model="embeddingForm.include_text" :disabled="recomputing" />
            <span class="form-tip">同时更新描述的文本嵌入</span>
          </el-form-item>
          <el-form-item label="最大数量">
            <el-input-number v-model="embeddingForm.limit" :min="1" :max="1000" :disabled="recomputing" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleRecomputeEmbeddings" :loading="recomputing">
              {{ recomputing ? '更新中...' : '开始更新' }}
            </el-button>
            <el-button v-if="recomputing" @click="cancelEmbeddings" type="danger">取消</el-button>
          </el-form-item>
        </el-form>

        <!-- 进度显示 -->
        <div v-if="embeddingProgress" class="progress-panel">
          <div class="progress-header">
            <span class="progress-title">更新进度</span>
            <span class="progress-stats">
              {{ embeddingProgress.current }} / {{ embeddingProgress.total }}
              <span class="speed">{{ embeddingProgress.speed }} 张/秒</span>
            </span>
          </div>
          <el-progress :percentage="embeddingProgress.percent" :stroke-width="20" />
          <div class="progress-info">
            <div class="info-row">
              <span class="label">成功:</span>
              <el-tag type="success" size="small">{{ embeddingProgress.processed }}</el-tag>
              <span class="label">失败:</span>
              <el-tag type="danger" size="small">{{ embeddingProgress.failed }}</el-tag>
            </div>
            <div class="info-row">
              <span class="label">已用时:</span>
              <span>{{ formatTime(embeddingProgress.elapsed) }}</span>
              <span class="label">预计剩余:</span>
              <span>{{ formatTime(embeddingProgress.eta) }}</span>
            </div>
          </div>
        </div>

        <div v-if="embeddingResult && !recomputing" class="import-result">
          <el-alert 
            :title="`更新完成: ${embeddingResult.processed} 成功, ${embeddingResult.failed} 失败`"
            :type="embeddingResult.failed > 0 ? 'warning' : 'success'"
            show-icon
          >
            <template #default>
              <div>总耗时: {{ formatTime(embeddingResult.elapsed) }}，平均速度: {{ embeddingResult.avg_speed }} 张/秒</div>
            </template>
          </el-alert>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import { 
  batchImportStream, 
  batchGenerateCaptionsStream, 
  batchRecomputeEmbeddingsStream, 
  getVlmPrompts, 
  getVlmServices 
} from '@/services/imagemgr';

const activeTab = ref('import');

// VLM 服务和提示词列表
const vlmServices = ref([]);
const vlmPrompts = ref([]);

// 目录导入
const importForm = reactive({
  directory: '',
  source: '',
  recursive: false,
  force_reimport: false,
  generate_caption: false,
  vlm_service: '',
  caption_method: 'vlm',
  caption_prompt: '',
  concurrency: 4
});
const importing = ref(false);
const importProgress = ref(null);
const importResult = ref(null);
let cancelImportFn = null;

// 批量生成描述
const captionForm = reactive({
  source: '',
  vlm_service: '',
  method: 'vlm',
  prompt: '',
  overwrite: false,
  limit: 100,
  concurrency: 4
});
const generatingCaptions = ref(false);
const captionProgress = ref(null);
const captionResult = ref(null);
let cancelCaptionsFn = null;

// 批量更新嵌入
const embeddingForm = reactive({
  source: '',
  status: '',
  include_text: false,
  limit: 100
});
const recomputing = ref(false);
const embeddingProgress = ref(null);
const embeddingResult = ref(null);
let cancelEmbeddingsFn = null;

const statusType = {
  imported: 'success',
  skipped: 'info',
  failed: 'danger',
  success: 'success',
  processing: 'warning'
};

function formatTime(seconds) {
  if (!seconds || seconds < 0) return '--';
  if (seconds < 60) return `${Math.round(seconds)}秒`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  if (mins < 60) return `${mins}分${secs}秒`;
  const hours = Math.floor(mins / 60);
  return `${hours}时${mins % 60}分`;
}

// 加载 VLM 服务和提示词
async function loadVlmServices() {
  try {
    const data = await getVlmServices();
    vlmServices.value = data.services || [];
  } catch (e) {
    console.warn('加载 VLM 服务列表失败:', e);
  }
}

async function loadVlmPrompts() {
  try {
    const data = await getVlmPrompts();
    vlmPrompts.value = data.prompts || [];
  } catch (e) {
    console.warn('加载 VLM 提示词失败:', e);
  }
}

// 导入操作
function handleImport() {
  if (!importForm.directory) {
    return ElMessage.warning('请输入目录路径');
  }
  
  importing.value = true;
  importProgress.value = null;
  importResult.value = null;
  
  cancelImportFn = batchImportStream(
    importForm,
    (data) => { importProgress.value = data; },
    (data) => {
      importResult.value = data;
      importing.value = false;
      ElMessage.success(`导入完成: ${data.imported} 张图片`);
    },
    (err) => {
      importing.value = false;
      ElMessage.error('导入失败: ' + err.message);
    }
  );
}

function cancelImport() {
  if (cancelImportFn) cancelImportFn();
  importing.value = false;
  ElMessage.info('已取消导入');
}

// 生成描述操作
function handleGenerateCaptions() {
  generatingCaptions.value = true;
  captionProgress.value = null;
  captionResult.value = null;
  
  const params = { ...captionForm };
  if (!params.source) delete params.source;
  if (!params.vlm_service) delete params.vlm_service;
  if (!params.prompt) delete params.prompt;
  
  cancelCaptionsFn = batchGenerateCaptionsStream(
    params,
    (data) => { captionProgress.value = data; },
    (data) => {
      captionResult.value = data;
      generatingCaptions.value = false;
      ElMessage.success(`生成完成: ${data.processed} 张图片`);
    },
    (err) => {
      generatingCaptions.value = false;
      ElMessage.error('生成失败: ' + err.message);
    }
  );
}

function cancelCaptions() {
  if (cancelCaptionsFn) cancelCaptionsFn();
  generatingCaptions.value = false;
  ElMessage.info('已取消生成');
}

// 更新嵌入操作
function handleRecomputeEmbeddings() {
  recomputing.value = true;
  embeddingProgress.value = null;
  embeddingResult.value = null;
  
  const params = { ...embeddingForm };
  if (!params.source) delete params.source;
  if (!params.status) delete params.status;
  
  cancelEmbeddingsFn = batchRecomputeEmbeddingsStream(
    params,
    (data) => { embeddingProgress.value = data; },
    (data) => {
      embeddingResult.value = data;
      recomputing.value = false;
      ElMessage.success(`更新完成: ${data.processed} 张图片`);
    },
    (err) => {
      recomputing.value = false;
      ElMessage.error('更新失败: ' + err.message);
    }
  );
}

function cancelEmbeddings() {
  if (cancelEmbeddingsFn) cancelEmbeddingsFn();
  recomputing.value = false;
  ElMessage.info('已取消更新');
}

onMounted(() => {
  loadVlmServices();
  loadVlmPrompts();
});

onUnmounted(() => {
  // 组件卸载时取消所有进行中的操作
  if (cancelImportFn) cancelImportFn();
  if (cancelCaptionsFn) cancelCaptionsFn();
  if (cancelEmbeddingsFn) cancelEmbeddingsFn();
});
</script>

<style scoped>
.batch-import {
  padding: 16px;
}

.import-form {
  max-width: 600px;
}

.form-tip {
  margin-left: 12px;
  color: #909399;
  font-size: 13px;
}

.progress-panel {
  margin-top: 24px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.progress-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}

.progress-stats {
  font-size: 14px;
  color: #606266;
}

.speed {
  margin-left: 12px;
  color: #409eff;
  font-weight: 500;
}

.progress-info {
  margin-top: 16px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.info-row .label {
  color: #909399;
  font-size: 13px;
}

.current-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border-radius: 4px;
  margin-top: 12px;
}

.current-item .filename {
  font-family: monospace;
  color: #606266;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.current-item .message {
  color: #909399;
  font-size: 12px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.import-result {
  margin-top: 24px;
}

.prompt-preview {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-desc {
  margin-left: 8px;
  color: #909399;
  font-size: 12px;
}
</style>
