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
            />
          </el-form-item>
          <el-form-item label="来源标记">
            <el-input v-model="importForm.source" placeholder="可选，用于标记图片来源" />
          </el-form-item>
          <el-form-item label="递归扫描">
            <el-switch v-model="importForm.recursive" />
            <span class="form-tip">扫描子目录中的图片</span>
          </el-form-item>
          <el-form-item label="生成描述">
            <el-switch v-model="importForm.generate_caption" />
            <span class="form-tip">使用 VLM 自动生成图片描述</span>
          </el-form-item>
          <el-form-item label="VLM 服务" v-if="importForm.generate_caption">
            <el-select v-model="importForm.vlm_service" placeholder="选择 VLM 服务" clearable style="width: 200px;">
              <el-option 
                v-for="s in vlmServices" 
                :key="s.id" 
                :label="s.name" 
                :value="s.id"
              >
                <span>{{ s.name }}</span>
                <span class="service-desc">{{ s.description }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">留空使用默认服务</span>
          </el-form-item>
          <el-form-item label="描述方法" v-if="importForm.generate_caption">
            <el-input v-model="importForm.caption_method" style="width: 200px;" />
          </el-form-item>
          <el-form-item label="提示词" v-if="importForm.generate_caption">
            <el-select v-model="importForm.caption_prompt" placeholder="选择提示词模板" style="width: 200px;">
              <el-option 
                v-for="p in vlmPrompts" 
                :key="p.name" 
                :label="p.name" 
                :value="p.name"
              >
                <span>{{ p.name }}</span>
                <span class="prompt-preview">{{ p.text }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">或留空使用默认提示词</span>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleImport" :loading="importing">
              开始导入
            </el-button>
          </el-form-item>
        </el-form>

        <!-- 导入结果 -->
        <div v-if="importResult" class="import-result">
          <el-alert 
            :title="`导入完成: ${importResult.imported} 成功, ${importResult.skipped} 跳过, ${importResult.failed} 失败`"
            :type="importResult.failed > 0 ? 'warning' : 'success'"
            show-icon
          />
          <el-table :data="importResult.details" max-height="400" style="margin-top: 12px;">
            <el-table-column prop="file" label="文件" min-width="200" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusType[row.status]">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="message" label="消息" min-width="150" />
            <el-table-column label="尺寸" width="120">
              <template #default="{ row }">
                <span v-if="row.width">{{ row.width }} × {{ row.height }}</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- 批量生成描述 -->
      <el-tab-pane label="批量生成描述" name="captions">
        <el-form :model="captionForm" label-width="120px" class="import-form">
          <el-form-item label="来源筛选">
            <el-input v-model="captionForm.source" placeholder="只处理指定来源的图片（可选）" />
          </el-form-item>
          <el-form-item label="VLM 服务">
            <el-select v-model="captionForm.vlm_service" placeholder="选择 VLM 服务" clearable style="width: 200px;">
              <el-option 
                v-for="s in vlmServices" 
                :key="s.id" 
                :label="s.name" 
                :value="s.id"
              >
                <span>{{ s.name }}</span>
                <span class="service-desc">{{ s.description }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">留空使用默认服务</span>
          </el-form-item>
          <el-form-item label="描述方法">
            <el-input v-model="captionForm.method" style="width: 200px;" />
          </el-form-item>
          <el-form-item label="提示词">
            <el-select v-model="captionForm.prompt" placeholder="选择提示词模板" clearable style="width: 200px;">
              <el-option 
                v-for="p in vlmPrompts" 
                :key="p.name" 
                :label="p.name" 
                :value="p.name"
              >
                <span>{{ p.name }}</span>
                <span class="prompt-preview">{{ p.text }}</span>
              </el-option>
            </el-select>
            <span class="form-tip">留空使用默认提示词</span>
          </el-form-item>
          <el-form-item label="覆盖已有">
            <el-switch v-model="captionForm.overwrite" />
            <span class="form-tip">覆盖已有的同类型描述</span>
          </el-form-item>
          <el-form-item label="最大数量">
            <el-input-number v-model="captionForm.limit" :min="1" :max="1000" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleGenerateCaptions" :loading="generatingCaptions">
              开始生成
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="captionResult" class="import-result">
          <el-alert 
            :title="`处理完成: ${captionResult.processed} 成功, ${captionResult.skipped} 跳过, ${captionResult.failed} 失败`"
            :type="captionResult.failed > 0 ? 'warning' : 'success'"
            show-icon
          />
        </div>
      </el-tab-pane>

      <!-- 批量更新嵌入 -->
      <el-tab-pane label="批量更新嵌入" name="embeddings">
        <el-form :model="embeddingForm" label-width="120px" class="import-form">
          <el-form-item label="来源筛选">
            <el-input v-model="embeddingForm.source" placeholder="只处理指定来源的图片（可选）" />
          </el-form-item>
          <el-form-item label="状态筛选">
            <el-select v-model="embeddingForm.status" clearable placeholder="全部">
              <el-option label="全部" value="" />
              <el-option label="就绪" value="ready" />
              <el-option label="待处理" value="pending" />
              <el-option label="失败" value="failed" />
            </el-select>
          </el-form-item>
          <el-form-item label="更新文本嵌入">
            <el-switch v-model="embeddingForm.include_text" />
            <span class="form-tip">同时更新描述的文本嵌入</span>
          </el-form-item>
          <el-form-item label="最大数量">
            <el-input-number v-model="embeddingForm.limit" :min="1" :max="1000" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="handleRecomputeEmbeddings" :loading="recomputing">
              开始更新
            </el-button>
          </el-form-item>
        </el-form>

        <div v-if="embeddingResult" class="import-result">
          <el-alert 
            :title="`处理完成: ${embeddingResult.processed} 成功, ${embeddingResult.failed} 失败`"
            :type="embeddingResult.failed > 0 ? 'warning' : 'success'"
            show-icon
          />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { batchImport, batchGenerateCaptions, batchRecomputeEmbeddings, getVlmPrompts, getVlmServices } from '@/services/imagemgr';

const activeTab = ref('import');

// VLM 服务和提示词列表
const vlmServices = ref([]);
const vlmPrompts = ref([]);

// 目录导入表单
const importForm = reactive({
  directory: '',
  source: '',
  recursive: false,
  generate_caption: false,
  vlm_service: '',
  caption_method: 'vlm',
  caption_prompt: ''
});
const importing = ref(false);
const importResult = ref(null);

// 批量生成描述表单
const captionForm = reactive({
  source: '',
  vlm_service: '',
  method: 'vlm',
  prompt: '',
  overwrite: false,
  limit: 100
});

// 加载 VLM 服务列表
async function loadVlmServices() {
  try {
    const data = await getVlmServices();
    vlmServices.value = data.services || [];
  } catch (e) {
    console.warn('加载 VLM 服务列表失败:', e);
  }
}

// 加载 VLM 提示词列表
async function loadVlmPrompts() {
  try {
    const data = await getVlmPrompts();
    vlmPrompts.value = data.prompts || [];
  } catch (e) {
    console.warn('加载 VLM 提示词失败:', e);
  }
}

onMounted(() => {
  loadVlmServices();
  loadVlmPrompts();
});
const generatingCaptions = ref(false);
const captionResult = ref(null);

// 批量更新嵌入表单
const embeddingForm = reactive({
  source: '',
  status: '',
  include_text: false,
  limit: 100
});
const recomputing = ref(false);
const embeddingResult = ref(null);

const statusType = {
  imported: 'success',
  skipped: 'info',
  failed: 'danger',
  success: 'success'
};

async function handleImport() {
  if (!importForm.directory) {
    return ElMessage.warning('请输入目录路径');
  }
  
  importing.value = true;
  importResult.value = null;
  
  try {
    const result = await batchImport(importForm);
    importResult.value = result;
    ElMessage.success(`导入完成: ${result.imported} 张图片`);
  } catch (e) {
    ElMessage.error('导入失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    importing.value = false;
  }
}

async function handleGenerateCaptions() {
  generatingCaptions.value = true;
  captionResult.value = null;
  
  try {
    const params = { ...captionForm };
    if (!params.source) delete params.source;
    
    const result = await batchGenerateCaptions(params);
    captionResult.value = result;
    ElMessage.success(`生成完成: ${result.processed} 张图片`);
  } catch (e) {
    ElMessage.error('生成失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    generatingCaptions.value = false;
  }
}

async function handleRecomputeEmbeddings() {
  recomputing.value = true;
  embeddingResult.value = null;
  
  try {
    const params = { ...embeddingForm };
    if (!params.source) delete params.source;
    if (!params.status) delete params.status;
    
    const result = await batchRecomputeEmbeddings(params);
    embeddingResult.value = result;
    ElMessage.success(`更新完成: ${result.processed} 张图片`);
  } catch (e) {
    ElMessage.error('更新失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    recomputing.value = false;
  }
}
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

