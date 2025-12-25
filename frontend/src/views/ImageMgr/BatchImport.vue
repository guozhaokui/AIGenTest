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

      <!-- 更新嵌入（补充缺失的模型嵌入） -->
      <el-tab-pane label="批量更新嵌入" name="rebuild">
        <div class="rebuild-section">
          <div class="section-header">
            <h4>嵌入模型状态</h4>
            <el-button size="small" @click="loadIndexStatus" :loading="loadingIndexStatus">
              刷新状态
            </el-button>
          </div>
          
          <!-- 后台任务提示 -->
          <el-alert 
            v-if="rebuilding" 
            type="info" 
            :closable="false"
            style="margin-bottom: 16px;"
          >
            <template #title>
              <span>任务正在后台运行：{{ getModelNameByIndex(rebuildingIndex) }}</span>
            </template>
            <template #default>
              切换到其他页面后任务会继续运行，回到此页面可查看进度
            </template>
          </el-alert>

          <!-- 索引状态表格 -->
          <el-table :data="indexStatus" v-loading="loadingIndexStatus" style="width: 100%; margin-bottom: 20px;">
            <el-table-column prop="model" label="模型" width="180" />
            <el-table-column prop="index_name" label="索引名称" width="160" />
            <el-table-column prop="dimension" label="维度" width="80" align="center" />
            <el-table-column prop="current_count" label="已索引" width="100" align="center">
              <template #default="{ row }">
                <el-tag type="success" size="small">{{ row.current_count }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="missing_count" label="待补充" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.missing_count > 0 ? 'warning' : 'info'" size="small">
                  {{ row.missing_count }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.needs_rebuild ? 'warning' : 'success'" size="small">
                  {{ row.needs_rebuild ? '待补充' : '完整' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="center">
              <template #default="{ row }">
                <el-button 
                  size="small" 
                  type="primary" 
                  :disabled="!row.needs_rebuild || rebuilding"
                  @click="selectIndex(row.index_name)"
                >
                  补充
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <!-- 更新配置（显示选中的索引或正在运行的任务） -->
          <el-form label-width="120px" class="import-form" v-if="selectedIndex || rebuildingIndex">
            <el-form-item label="目标模型">
              <el-tag size="large">{{ getModelNameByIndex(selectedIndex || rebuildingIndex) }}</el-tag>
              <span class="form-tip">索引: {{ selectedIndex || rebuildingIndex }}</span>
            </el-form-item>
            <el-form-item label="并发数" v-if="!rebuilding">
              <el-input-number v-model="concurrency" :min="1" :max="16" />
              <span class="form-tip">同时请求嵌入服务的数量</span>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="handleRebuild" :loading="rebuilding" :disabled="rebuilding">
                {{ rebuilding ? '更新中...' : '开始更新' }}
              </el-button>
              <el-button v-if="rebuilding" @click="cancelRebuild" type="danger">取消</el-button>
              <el-button v-if="!rebuilding && selectedIndex" @click="selectedIndex = null">取消选择</el-button>
            </el-form-item>
          </el-form>

          <!-- 进度显示 -->
          <div v-if="rebuildProgress" class="progress-panel">
            <div class="progress-header">
              <span class="progress-title">更新进度 - {{ rebuildProgress.model || rebuildingIndex }}</span>
              <span class="progress-stats">
                {{ rebuildProgress.processed + rebuildProgress.failed }} / {{ rebuildProgress.total }}
                <span class="speed" v-if="rebuildProgress.speed">{{ rebuildProgress.speed }} 条/秒</span>
              </span>
            </div>
            <el-progress :percentage="rebuildProgress.percent || 0" :stroke-width="20" />
            <div class="progress-info">
              <div class="info-row">
                <span class="label">成功:</span>
                <el-tag type="success" size="small">{{ rebuildProgress.processed }}</el-tag>
                <span class="label">失败:</span>
                <el-tag type="danger" size="small">{{ rebuildProgress.failed }}</el-tag>
              </div>
              <div class="info-row">
                <span class="label">已用时:</span>
                <span>{{ formatTime(rebuildProgress.elapsed) }}</span>
                <span class="label">预计剩余:</span>
                <span>{{ formatTime(rebuildProgress.eta) }}</span>
              </div>
              <div class="current-item" v-if="rebuildProgress.current">
                <span class="label">当前:</span>
                <span class="filename">{{ rebuildProgress.current.sha256?.slice(0, 16) }}...</span>
                <el-tag :type="rebuildProgress.current.status === 'success' ? 'success' : 'danger'" size="small">
                  {{ rebuildProgress.current.status }}
                </el-tag>
              </div>
            </div>
          </div>

          <!-- 完成结果 -->
          <div v-if="rebuildResult && !rebuilding" class="import-result">
            <el-alert 
              :title="`更新完成: ${rebuildResult.processed} 成功, ${rebuildResult.failed} 失败`"
              :type="rebuildResult.failed > 0 ? 'warning' : 'success'"
              show-icon
            >
              <template #default>
                <div>索引当前数量: {{ rebuildResult.index_count }}</div>
              </template>
            </el-alert>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue';
import { ElMessage } from 'element-plus';
import { 
  batchImportStream, 
  batchGenerateCaptionsStream, 
  getVlmPrompts, 
  getVlmServices,
  getRebuildIndexStatus
} from '@/services/imagemgr';
import { useBatchTasksStore } from '@/stores/batchTasks';

const activeTab = ref('import');

// 使用全局 store 管理更新嵌入任务（支持后台运行）
const batchStore = useBatchTasksStore();

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

// 更新嵌入（使用全局 store，支持后台运行）
const indexStatus = ref([]);
const loadingIndexStatus = ref(false);
const selectedIndex = ref(null);  // 选中的索引（用于配置）
const concurrency = ref(4);

// 从 store 读取状态
const rebuilding = computed(() => batchStore.rebuildTask.running);
const rebuildProgress = computed(() => batchStore.rebuildTask.progress);
const rebuildResult = computed(() => batchStore.rebuildTask.result);
const rebuildError = computed(() => batchStore.rebuildTask.error);
const rebuildingIndex = computed(() => batchStore.rebuildTask.indexName);

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

// 更新嵌入操作（使用全局 store，支持后台运行）
async function loadIndexStatus() {
  loadingIndexStatus.value = true;
  try {
    const data = await getRebuildIndexStatus();
    indexStatus.value = data.indexes || [];
  } catch (e) {
    ElMessage.error('加载索引状态失败: ' + e.message);
  } finally {
    loadingIndexStatus.value = false;
  }
}

function getModelNameByIndex(indexName) {
  const idx = indexStatus.value.find(i => i.index_name === indexName);
  return idx ? idx.model : indexName;
}

function selectIndex(indexName) {
  // 如果任务正在运行，不允许切换
  if (rebuilding.value) {
    ElMessage.warning('请等待当前任务完成或取消后再选择');
    return;
  }
  selectedIndex.value = indexName;
  batchStore.clearRebuildResult();
}

function handleRebuild() {
  if (!selectedIndex.value) return;
  
  batchStore.startRebuildTask(selectedIndex.value, concurrency.value);
  ElMessage.info('任务已开始，可以切换到其他页面，任务会在后台继续运行');
}

function cancelRebuild() {
  batchStore.cancelRebuildTask();
  ElMessage.info('已取消更新');
}

// 监听任务完成
watch(() => batchStore.rebuildTask.result, (result) => {
  if (result) {
    ElMessage.success(`更新完成: ${result.processed} 条`);
    loadIndexStatus();
  }
});

// 监听任务错误
watch(() => batchStore.rebuildTask.error, (error) => {
  if (error) {
    ElMessage.error('更新失败: ' + error);
  }
});

onMounted(() => {
  loadVlmServices();
  loadVlmPrompts();
  loadIndexStatus();
});

onUnmounted(() => {
  // 组件卸载时取消导入和生成描述操作（这些不需要后台运行）
  // 注意：更新嵌入任务由 store 管理，不在这里取消，支持后台运行
  if (cancelImportFn) cancelImportFn();
  if (cancelCaptionsFn) cancelCaptionsFn();
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

.rebuild-section {
  padding: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-header h4 {
  margin: 0;
  font-size: 16px;
  color: #303133;
}
</style>
