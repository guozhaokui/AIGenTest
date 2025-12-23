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

    <!-- 详情弹窗组件 -->
    <ImageDetailDialog 
      v-model="detailVisible"
      :sha256="selectedSha256"
      @deleted="onImageDeleted"
      @search-similar="onSearchSimilar"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { listImages, getThumbnailUrl } from '@/services/imagemgr';
import ImageDetailDialog from './ImageDetailDialog.vue';

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

// 详情弹窗
const detailVisible = ref(false);
const selectedSha256 = ref('');

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

function showDetail(img) {
  selectedSha256.value = img.sha256;
  detailVisible.value = true;
}

function onImageDeleted() {
  loadImages();
}

function onSearchSimilar(sha256) {
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
</style>
