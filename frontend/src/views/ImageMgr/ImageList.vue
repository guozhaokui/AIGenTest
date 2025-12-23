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
      
      <div class="spacer"></div>
      
      <!-- 视图切换 -->
      <el-radio-group v-model="viewMode" size="small" @change="onViewModeChange">
        <el-radio-button value="large">大图</el-radio-button>
        <el-radio-button value="small">小图</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 图片网格 -->
    <div class="image-grid" :class="viewMode" v-loading="loading">
      <div 
        v-for="img in images" 
        :key="img.sha256" 
        class="image-card"
        @click="showDetail(img)"
      >
        <div class="image-thumb">
          <img :src="getThumbnailUrl(img.sha256)" :alt="img.sha256" />
          <div v-if="viewMode === 'large'" class="status-badge" :class="img.status">
            {{ statusText[img.status] }}
          </div>
        </div>
        <div class="image-info" v-if="viewMode === 'large'">
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
        :page-sizes="pageSizeOptions"
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
import { ref, reactive, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { useRouter } from 'vue-router';
import { listImages, getThumbnailUrl } from '@/services/imagemgr';
import ImageDetailDialog from './ImageDetailDialog.vue';

const router = useRouter();

const loading = ref(false);
const images = ref([]);
const viewMode = ref('large'); // 'large' | 'small'

const pagination = reactive({
  page: 1,
  size: 20,
  total: 0
});
const filter = reactive({
  status: '',
  source: ''
});

// 根据视图模式提供不同的分页选项
const pageSizeOptions = computed(() => {
  return viewMode.value === 'small' 
    ? [50, 100, 200] 
    : [20, 50, 100];
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

function onViewModeChange(mode) {
  // 切换视图时调整每页数量
  if (mode === 'small') {
    pagination.size = 100;
  } else {
    pagination.size = 20;
  }
  pagination.page = 1;
  loadImages();
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
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.spacer {
  flex: 1;
}

/* 大图模式 */
.image-grid.large {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
  min-height: 300px;
}

.image-grid.large .image-card {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.image-grid.large .image-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.image-grid.large .image-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
}

.image-grid.large .image-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-grid.large .status-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: white;
}

.image-grid.large .image-info {
  padding: 12px;
}

.image-grid.large .image-info .size {
  font-weight: 500;
  color: #303133;
}

.image-grid.large .image-info .meta {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

/* 小图模式 */
.image-grid.small {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 8px;
  min-height: 300px;
}

.image-grid.small .image-card {
  background: white;
  border-radius: 4px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.image-grid.small .image-card:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  z-index: 1;
}

.image-grid.small .image-thumb {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
}

.image-grid.small .image-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-grid.small .status-badge {
  position: absolute;
  top: 2px;
  right: 2px;
  padding: 1px 4px;
  border-radius: 2px;
  font-size: 10px;
  color: white;
}

/* 通用状态颜色 */
.status-badge.ready { background: #67c23a; }
.status-badge.pending { background: #e6a23c; }
.status-badge.failed { background: #f56c6c; }

.pagination {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}
</style>
