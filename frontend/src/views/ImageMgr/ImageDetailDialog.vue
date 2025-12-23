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
          <h4>描述信息</h4>
          <div v-if="descriptions.length === 0" class="no-desc">暂无描述</div>
          <div v-for="desc in descriptions" :key="desc.method" class="desc-item">
            <el-tag size="small">{{ desc.method }}</el-tag>
            <span>{{ desc.content }}</span>
          </div>
        </div>

        <!-- 添加描述 -->
        <div class="add-desc-section">
          <h4>添加描述</h4>
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
  deleteImage
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
  } catch (e) {
    ElMessage.error('加载图片信息失败');
    console.error(e);
  } finally {
    loading.value = false;
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
  margin-bottom: 6px;
  font-size: 13px;
}

.desc-item span {
  line-height: 1.5;
  word-break: break-all;
}

.add-desc-form {
  display: flex;
  gap: 8px;
}

.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid #eee;
}
</style>

