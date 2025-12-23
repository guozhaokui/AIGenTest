<template>
  <div class="image-list">
    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filter.status" placeholder="状态" clearable style="width: 120px;">
        <el-option label="全部" value="" />
        <el-option label="就绪" value="ready" />
        <el-option label="待处理" value="pending" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-input v-model="filter.source" placeholder="来源" clearable style="width: 150px;" />
      <el-button type="primary" @click="loadImages">刷新</el-button>
    </div>

    <!-- 图片网格 -->
    <div class="image-grid" v-loading="loading">
      <div 
        v-for="img in images" 
        :key="img.sha256" 
        class="image-card"
        @click="showDetail(img)"
      >
        <div class="image-thumb">
          <img :src="getThumbnailUrl(img.sha256)" :alt="img.sha256" />
          <div class="status-badge" :class="img.status">
            {{ statusText[img.status] }}
          </div>
        </div>
        <div class="image-info">
          <div class="size">{{ img.width }} × {{ img.height }}</div>
          <div class="meta">{{ formatSize(img.file_size) }} · {{ img.format }}</div>
        </div>
      </div>
    </div>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.size"
        :total="pagination.total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadImages"
        @current-change="loadImages"
      />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="图片详情" width="800px">
      <div class="detail-content" v-if="selectedImage">
        <div class="detail-left">
          <img :src="getImageUrl(selectedImage.sha256)" class="detail-image" />
        </div>
        <div class="detail-right">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="SHA256">
              <code>{{ selectedImage.sha256 }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="尺寸">
              {{ selectedImage.width }} × {{ selectedImage.height }}
            </el-descriptions-item>
            <el-descriptions-item label="大小">
              {{ formatSize(selectedImage.file_size) }}
            </el-descriptions-item>
            <el-descriptions-item label="格式">
              {{ selectedImage.format }}
            </el-descriptions-item>
            <el-descriptions-item label="来源">
              {{ selectedImage.source || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag :type="statusType[selectedImage.status]">
                {{ statusText[selectedImage.status] }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">
              {{ selectedImage.created_at }}
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
            <el-input v-model="newDesc.method" placeholder="类型 (如: human)" style="width: 120px; margin-right: 8px;" />
            <el-input v-model="newDesc.content" placeholder="描述内容" style="flex: 1; margin-right: 8px;" />
            <el-button type="primary" @click="handleAddDesc" :loading="addingDesc">添加</el-button>
          </div>

          <!-- 操作按钮 -->
          <div class="actions">
            <el-button type="info" @click="handleSearchSimilar" :loading="searchingSimilar">
              搜索相似图片
            </el-button>
            <el-button type="primary" @click="handleRecompute(false)" :loading="recomputing">
              更新图片嵌入
            </el-button>
            <el-button type="success" @click="handleRecompute(true)" :loading="recomputing">
              更新全部嵌入
            </el-button>
            <el-button type="danger" @click="handleDelete">删除图片</el-button>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useRouter } from 'vue-router';
import { 
  listImages, 
  getImage,
  deleteImage, 
  getThumbnailUrl, 
  getImageUrl,
  addDescription,
  getDescriptions,
  recomputeEmbedding,
  searchSimilar
} from '@/services/imagemgr';

const router = useRouter();

const loading = ref(false);
const images = ref([]);
const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
});
const filter = reactive({
  status: '',
  source: ''
});

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

// 详情相关
const detailVisible = ref(false);
const selectedImage = ref(null);
const descriptions = ref([]);
const newDesc = reactive({ method: '', content: '' });
const addingDesc = ref(false);
const recomputing = ref(false);
const searchingSimilar = ref(false);

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1024 / 1024).toFixed(1) + ' MB';
}

async function loadImages() {
  loading.value = true;
  try {
    const params = {
      offset: (pagination.page - 1) * pagination.size,
      limit: pagination.size
    };
    if (filter.status) params.status = filter.status;
    if (filter.source) params.source = filter.source;
    
    const data = await listImages(params);
    images.value = data.images;
    pagination.total = data.total;
  } catch (e) {
    ElMessage.error('加载图片列表失败');
    console.error(e);
  } finally {
    loading.value = false;
  }
}

async function showDetail(img) {
  selectedImage.value = img;
  detailVisible.value = true;
  
  // 加载描述
  try {
    const data = await getDescriptions(img.sha256);
    descriptions.value = data.descriptions || [];
  } catch (e) {
    descriptions.value = [];
  }
}

async function handleAddDesc() {
  if (!newDesc.method || !newDesc.content) {
    return ElMessage.warning('请填写类型和内容');
  }
  
  addingDesc.value = true;
  try {
    await addDescription(selectedImage.value.sha256, newDesc.method, newDesc.content);
    ElMessage.success('添加成功');
    
    // 刷新描述列表
    const data = await getDescriptions(selectedImage.value.sha256);
    descriptions.value = data.descriptions || [];
    
    newDesc.method = '';
    newDesc.content = '';
  } catch (e) {
    ElMessage.error('添加失败');
  } finally {
    addingDesc.value = false;
  }
}

async function handleRecompute(includeText) {
  recomputing.value = true;
  try {
    const result = await recomputeEmbedding(selectedImage.value.sha256, includeText);
    
    // 构建结果消息
    const msgs = [];
    if (result.image_embedding?.status === 'success') {
      msgs.push('图片嵌入已更新');
    } else if (result.image_embedding?.status === 'failed') {
      msgs.push(`图片嵌入失败: ${result.image_embedding.error}`);
    }
    
    if (includeText && result.text_embeddings?.length > 0) {
      const successCount = result.text_embeddings.filter(e => e.status === 'success').length;
      msgs.push(`文本嵌入: ${successCount}/${result.text_embeddings.length} 成功`);
    }
    
    ElMessage.success(msgs.join(', ') || '更新完成');
    
    // 刷新图片信息
    const data = await getImage(selectedImage.value.sha256);
    selectedImage.value = data;
  } catch (e) {
    ElMessage.error('更新嵌入失败: ' + (e.response?.data?.error || e.message));
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
    
    await deleteImage(selectedImage.value.sha256);
    ElMessage.success('删除成功');
    detailVisible.value = false;
    loadImages();
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败');
    }
  }
}

async function handleSearchSimilar() {
  if (!selectedImage.value) return;
  
  // 关闭详情弹窗，跳转到搜索页面并自动搜索
  const sha256 = selectedImage.value.sha256;
  detailVisible.value = false;
  
  // 跳转到搜索页面，并传递参数
  router.push({
    path: '/imagemgr/search',
    query: { similar: sha256 }
  });
}

onMounted(() => {
  loadImages();
});
</script>

<style scoped>
.image-list {
  padding: 16px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  min-height: 300px;
}

.image-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.image-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.image-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
}

.image-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.status-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: white;
}

.status-badge.ready { background: #67c23a; }
.status-badge.pending { background: #e6a23c; }
.status-badge.failed { background: #f56c6c; }

.image-info {
  padding: 12px;
}

.image-info .size {
  font-weight: 500;
  color: #303133;
}

.image-info .meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.pagination {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}

/* 详情弹窗 */
.detail-content {
  display: flex;
  gap: 24px;
}

.detail-left {
  flex: 0 0 350px;
}

.detail-image {
  width: 100%;
  border-radius: 8px;
}

.detail-right {
  flex: 1;
}

.descriptions-section {
  margin-top: 16px;
}

.descriptions-section h4 {
  margin: 0 0 8px 0;
  color: #303133;
}

.no-desc {
  color: #909399;
  font-size: 14px;
}

.desc-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.add-desc-section {
  margin-top: 16px;
  display: flex;
  align-items: center;
}

.add-desc-section h4 {
  margin: 0 12px 0 0;
  white-space: nowrap;
}

.actions {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #eee;
}
</style>

