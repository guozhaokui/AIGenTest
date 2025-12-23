<template>
  <el-dialog 
    :model-value="modelValue" 
    @update:model-value="$emit('update:modelValue', $event)"
    title="图片详情" 
    width="850px"
  >
    <div class="detail-content" v-if="imageData" v-loading="loading">
      <div class="detail-left">
        <el-image 
          :src="getImageUrl(imageData.sha256)" 
          :preview-src-list="[getImageUrl(imageData.sha256)]"
          fit="contain"
          class="detail-image"
        />
      </div>
      <div class="detail-right">
        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="SHA256">
            <code class="sha-code" @click="copySha256" title="点击复制">{{ imageData.sha256 }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="尺寸">
            {{ imageData.width }} × {{ imageData.height }}
          </el-descriptions-item>
          <el-descriptions-item label="大小">
            {{ formatSize(imageData.file_size) }}
          </el-descriptions-item>
          <el-descriptions-item label="格式">
            {{ imageData.format }}
          </el-descriptions-item>
          <el-descriptions-item label="来源">
            {{ imageData.source || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType[imageData.status]" size="small">
              {{ statusText[imageData.status] }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ imageData.created_at }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 描述列表 -->
        <div class="descriptions-section">
          <h4>
            描述信息
            <el-tag v-if="previewCaption" type="warning" size="small" style="margin-left: 8px;">预览中</el-tag>
          </h4>
          <!-- 预览模式：显示生成的描述 -->
          <div v-if="previewCaption" class="preview-section">
            <div class="desc-item preview-item">
              <el-tag size="small" type="warning">{{ previewCaption.method }}</el-tag>
              <span>{{ previewCaption.content }}</span>
            </div>
            <div class="preview-actions">
              <el-button type="success" size="small" @click="handleConfirmCaption" :loading="confirming">
                接受
              </el-button>
              <el-button size="small" @click="handleCancelPreview">
                取消
              </el-button>
            </div>
          </div>
          <!-- 正常模式：显示已保存的描述 -->
          <template v-else>
            <div v-if="descriptions.length === 0" class="no-desc">暂无描述</div>
            <div v-for="(desc, index) in descriptions" :key="desc.method" class="desc-item">
              <el-tag size="small">{{ desc.method }}</el-tag>
              <!-- 编辑模式 -->
              <template v-if="editingIndex === index">
                <el-input 
                  v-model="editingContent" 
                  type="textarea" 
                  :rows="2" 
                  size="small"
                  style="flex: 1;"
                />
                <div class="edit-actions">
                  <el-button type="success" size="small" @click="handleSaveEdit(desc.method)" :loading="savingEdit">
                    保存
                  </el-button>
                  <el-button size="small" @click="handleCancelEdit">取消</el-button>
                </div>
              </template>
              <!-- 查看模式 -->
              <template v-else>
                <span class="desc-content" @dblclick="handleStartEdit(index, desc.content)">{{ desc.content }}</span>
                <el-button link type="primary" size="small" @click="handleStartEdit(index, desc.content)">
                  编辑
                </el-button>
              </template>
            </div>
          </template>
        </div>

        <!-- AI 生成描述 -->
        <div class="generate-desc-section" v-if="!previewCaption">
          <h4>AI 生成描述</h4>
          <div class="generate-form">
            <el-select v-model="generateForm.vlmService" placeholder="VLM服务" size="small" style="width: 140px;">
              <el-option 
                v-for="svc in vlmServices" 
                :key="svc.id" 
                :label="svc.name" 
                :value="svc.id"
              />
            </el-select>
            <el-select v-model="generateForm.promptType" placeholder="提示词" size="small" style="width: 100px;">
              <el-option label="预设" value="preset" />
              <el-option label="自定义" value="custom" />
            </el-select>
            <el-select 
              v-if="generateForm.promptType === 'preset'"
              v-model="generateForm.promptName" 
              placeholder="选择提示词" 
              size="small" 
              style="width: 120px;"
            >
              <el-option 
                v-for="p in vlmPrompts" 
                :key="p.name" 
                :label="p.name" 
                :value="p.name"
              />
            </el-select>
            <el-button type="success" size="small" @click="handleGenerateCaption" :loading="generating">
              生成
            </el-button>
          </div>
          <div v-if="generateForm.promptType === 'custom'" class="custom-prompt">
            <el-input 
              v-model="generateForm.customPrompt" 
              type="textarea" 
              :rows="2"
              placeholder="输入自定义提示词，如：请用中文详细描述这张图片的内容、风格和构图"
              size="small"
            />
          </div>
        </div>

        <!-- 手动添加描述 -->
        <div class="add-desc-section">
          <h4>手动添加描述</h4>
          <div class="add-desc-form">
            <el-input v-model="newDesc.method" placeholder="类型" style="width: 100px;" size="small" />
            <el-input v-model="newDesc.content" placeholder="描述内容" style="flex: 1;" size="small" />
            <el-button type="primary" size="small" @click="handleAddDesc" :loading="addingDesc">添加</el-button>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="actions">
          <el-button type="info" size="small" @click="handleSearchSimilar">
            搜索相似图片
          </el-button>
          <el-button type="primary" size="small" @click="handleRecompute(false)" :loading="recomputing">
            更新图片嵌入
          </el-button>
          <el-button type="success" size="small" @click="handleRecompute(true)" :loading="recomputing">
            更新全部嵌入
          </el-button>
          <el-button type="danger" size="small" @click="handleDelete">
            删除图片
          </el-button>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, reactive, watch } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { 
  getImage,
  getImageUrl,
  getDescriptions,
  addDescription,
  recomputeEmbedding,
  deleteImage,
  vlmGenerate,
  saveDescription,
  getVlmServices,
  getVlmPrompts
} from '@/services/imagemgr';

const props = defineProps({
  modelValue: Boolean,
  sha256: String
});

const emit = defineEmits(['update:modelValue', 'deleted', 'search-similar']);

const loading = ref(false);
const imageData = ref(null);
const descriptions = ref([]);
const newDesc = reactive({ method: '', content: '' });
const addingDesc = ref(false);
const recomputing = ref(false);

// AI 生成描述
const generating = ref(false);
const confirming = ref(false);
const vlmServices = ref([]);
const vlmPrompts = ref([]);
const generateForm = reactive({
  vlmService: '',
  promptType: 'preset',
  promptName: 'default',
  customPrompt: ''
});

// 预览状态
const previewCaption = ref(null);  // { method: 'vlm', content: '...' }

// 编辑状态
const editingIndex = ref(-1);  // 正在编辑的描述索引，-1 表示没有编辑
const editingContent = ref('');  // 编辑中的内容
const savingEdit = ref(false);  // 是否正在保存

const statusText = {
  ready: '就绪',
  pending: '待处理',
  failed: '失败'
};
const statusType = {
  ready: 'success',
  pending: 'warning',
  failed: 'danger'
};

function formatSize(bytes) {
  if (!bytes) return '-';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

function copySha256() {
  if (!imageData.value) return;
  navigator.clipboard.writeText(imageData.value.sha256);
  ElMessage.success('已复制 SHA256');
}

// 监听 sha256 变化，加载数据
watch(() => props.sha256, async (newSha256) => {
  if (newSha256 && props.modelValue) {
    await loadImageData(newSha256);
  }
}, { immediate: true });

watch(() => props.modelValue, async (visible) => {
  if (visible && props.sha256) {
    await loadImageData(props.sha256);
  }
});

async function loadImageData(sha256) {
  loading.value = true;
  try {
    const data = await getImage(sha256);
    imageData.value = data;
    
    const descData = await getDescriptions(sha256);
    descriptions.value = descData.descriptions || [];
    
    // 加载 VLM 配置（只加载一次）
    if (vlmServices.value.length === 0) {
      loadVlmConfig();
    }
  } catch (e) {
    ElMessage.error('加载图片信息失败');
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function loadVlmConfig() {
  try {
    const [servicesData, promptsData] = await Promise.all([
      getVlmServices(),
      getVlmPrompts()
    ]);
    vlmServices.value = servicesData.services || [];
    vlmPrompts.value = promptsData.prompts || [];
    
    // 设置默认值
    if (vlmServices.value.length > 0 && !generateForm.vlmService) {
      generateForm.vlmService = vlmServices.value[0].id;
    }
    if (promptsData.default) {
      generateForm.promptName = promptsData.default;
    }
  } catch (e) {
    console.error('加载 VLM 配置失败:', e);
  }
}

async function handleGenerateCaption() {
  if (!imageData.value) return;
  
  generating.value = true;
  try {
    // 使用通用 VLM 生成 API
    const result = await vlmGenerate({
      sha256: imageData.value.sha256,
      vlm_service: generateForm.vlmService || null,
      prompt: generateForm.promptType === 'custom' 
        ? generateForm.customPrompt 
        : generateForm.promptName
    });
    
    // 显示预览
    previewCaption.value = {
      method: 'vlm',
      content: result.caption
    };
    
    ElMessage.info('描述已生成，请确认是否保存');
  } catch (e) {
    ElMessage.error('生成失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    generating.value = false;
  }
}

// 确认保存描述
async function handleConfirmCaption() {
  if (!previewCaption.value || !imageData.value) return;
  
  confirming.value = true;
  try {
    await saveDescription(
      imageData.value.sha256,
      previewCaption.value.method,
      previewCaption.value.content,
      true  // 计算嵌入
    );
    
    ElMessage.success('描述已保存并计算嵌入');
    
    // 刷新描述列表
    const descData = await getDescriptions(imageData.value.sha256);
    descriptions.value = descData.descriptions || [];
    
    // 清除预览
    previewCaption.value = null;
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    confirming.value = false;
  }
}

// 取消预览，恢复原始描述显示
function handleCancelPreview() {
  previewCaption.value = null;
  ElMessage.info('已取消');
}

// 开始编辑描述
function handleStartEdit(index, content) {
  editingIndex.value = index;
  editingContent.value = content;
}

// 取消编辑
function handleCancelEdit() {
  editingIndex.value = -1;
  editingContent.value = '';
}

// 保存编辑的描述
async function handleSaveEdit(method) {
  if (!editingContent.value.trim()) {
    return ElMessage.warning('描述内容不能为空');
  }
  
  savingEdit.value = true;
  try {
    await saveDescription(
      imageData.value.sha256,
      method,
      editingContent.value.trim(),
      true  // 重新计算嵌入
    );
    
    ElMessage.success('描述已更新并重新计算嵌入');
    
    // 刷新描述列表
    const descData = await getDescriptions(imageData.value.sha256);
    descriptions.value = descData.descriptions || [];
    
    // 退出编辑模式
    editingIndex.value = -1;
    editingContent.value = '';
  } catch (e) {
    ElMessage.error('保存失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    savingEdit.value = false;
  }
}

async function handleAddDesc() {
  if (!newDesc.method || !newDesc.content) {
    return ElMessage.warning('请填写类型和描述内容');
  }
  
  addingDesc.value = true;
  try {
    await addDescription(imageData.value.sha256, newDesc.method, newDesc.content);
    ElMessage.success('添加成功');
    
    const descData = await getDescriptions(imageData.value.sha256);
    descriptions.value = descData.descriptions || [];
    
    newDesc.method = '';
    newDesc.content = '';
  } catch (e) {
    ElMessage.error('添加失败');
    console.error(e);
  } finally {
    addingDesc.value = false;
  }
}

async function handleRecompute(includeText) {
  recomputing.value = true;
  try {
    const result = await recomputeEmbedding(imageData.value.sha256, includeText);
    
    const msgs = [];
    if (result.image_embedding?.status === 'success') {
      msgs.push('图片嵌入已更新');
    }
    if (includeText && result.text_embeddings?.length > 0) {
      const successCount = result.text_embeddings.filter(e => e.status === 'success').length;
      msgs.push(`文本嵌入: ${successCount}/${result.text_embeddings.length} 成功`);
    }
    
    ElMessage.success(msgs.join(', ') || '更新完成');
    
    // 刷新图片信息
    const data = await getImage(imageData.value.sha256);
    imageData.value = data;
  } catch (e) {
    ElMessage.error('更新嵌入失败');
    console.error(e);
  } finally {
    recomputing.value = false;
  }
}

async function handleDelete() {
  try {
    await ElMessageBox.confirm('确定要删除这张图片吗？', '警告', {
      type: 'warning'
    });
    
    await deleteImage(imageData.value.sha256);
    ElMessage.success('删除成功');
    emit('update:modelValue', false);
    emit('deleted', imageData.value.sha256);
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败');
      console.error(e);
    }
  }
}

function handleSearchSimilar() {
  emit('search-similar', imageData.value.sha256);
  emit('update:modelValue', false);
}
</script>

<style scoped>
.detail-content {
  display: flex;
  gap: 20px;
}

.detail-left {
  flex: 0 0 380px;
  background: #f5f7fa;
  border-radius: 8px;
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

.detail-image {
  width: 100%;
  height: 100%;
  max-height: 450px;
  border-radius: 4px;
}

.detail-image :deep(.el-image__inner) {
  object-fit: contain !important;
  width: 100%;
  height: 100%;
}

.detail-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 0;
}

.sha-code {
  font-size: 11px;
  cursor: pointer;
  word-break: break-all;
}

.sha-code:hover {
  color: #409eff;
}

.descriptions-section h4,
.add-desc-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #303133;
}

.no-desc {
  color: #909399;
  font-size: 13px;
}

.desc-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
  padding: 6px 8px;
  background: #fafafa;
  border-radius: 4px;
  flex-wrap: wrap;
}

.desc-item:hover {
  background: #f0f0f0;
}

.desc-item .el-tag {
  flex-shrink: 0;
}

.desc-content {
  flex: 1;
  line-height: 1.5;
  word-break: break-all;
  cursor: pointer;
}

.desc-content:hover {
  color: #409eff;
}

.edit-actions {
  display: flex;
  gap: 6px;
  width: 100%;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #ddd;
}

.add-desc-form {
  display: flex;
  gap: 8px;
}

.generate-desc-section {
  padding: 10px;
  background: #f0f9eb;
  border-radius: 6px;
}

.generate-desc-section h4 {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: #67c23a;
}

.generate-form {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.custom-prompt {
  margin-top: 8px;
}

.preview-section {
  background: #fef0e6;
  padding: 10px;
  border-radius: 6px;
  border: 1px dashed #e6a23c;
}

.preview-item {
  background: transparent;
}

.preview-item span {
  color: #e6a23c;
}

.preview-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #e6a23c;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}
</style>

