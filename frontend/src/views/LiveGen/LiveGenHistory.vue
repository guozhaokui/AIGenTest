<template>
  <div class="history-container">
    <div class="header">
      <el-page-header @back="$router.back()" content="实时生成历史" />
    </div>
    
    <div class="filter-bar">
      <el-input v-model="keyword" placeholder="搜索提示词..." style="width: 300px;" clearable @clear="fetchList" @keyup.enter="fetchList">
        <template #append>
           <el-button @click="fetchList"><el-icon><Search /></el-icon></el-button>
        </template>
      </el-input>
    </div>

    <el-table :data="items" v-loading="loading" style="width: 100%">
      <el-table-column label="图片" width="120">
        <template #default="{ row }">
          <el-image 
            :src="normalizeUrl(row.imagePath)" 
            :preview-src-list="[normalizeUrl(row.imagePath)]"
            fit="cover" 
            style="width: 80px; height: 80px; border-radius: 4px;"
            :preview-teleported="true"
            :z-index="9999"
          />
        </template>
      </el-table-column>
      
      <el-table-column label="提示词" min-width="200">
        <template #default="{ row }">
           <div class="prompt-text">{{ row.prompt }}</div>
           <div class="meta-info">
             <el-tag size="small" v-if="row.modelName">{{ row.modelName }}</el-tag>
             <span class="time">{{ formatTime(row.createdAt) }}</span>
           </div>
        </template>
      </el-table-column>
      
      <el-table-column label="评分" width="150">
        <template #default="{ row }">
           <div v-if="row.dimensionScores && Object.keys(row.dimensionScores).length > 0">
              <div v-for="(score, dimId) in row.dimensionScores" :key="dimId" style="font-size: 12px;">
                 {{ getDimName(dimId) }}: {{ score }}
              </div>
           </div>
           <span v-else style="color: #999;">未评分</span>
        </template>
      </el-table-column>

      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="handleReEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        background
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { Search } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { listDimensions } from '../../services/api';

const router = useRouter();
const items = ref([]);
const loading = ref(false);
const keyword = ref('');
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const dimensions = ref([]);
const dimMap = ref({});

onMounted(async () => {
  try {
    const dims = await listDimensions();
    dimensions.value = dims;
    dims.forEach(d => { dimMap.value[d.id] = d.name; });
    fetchList();
  } catch (e) {
    console.error(e);
  }
});

function formatTime(t) {
  if (!t) return '';
  return new Date(t).toLocaleString();
}

function normalizeUrl(p) {
  if (!p) return '';
  let url = String(p).replace(/\\/g, '/');
  if (!url.startsWith('/')) url = '/' + url;
  url = url.replace(/^\/backend\/uploads\//, '/uploads/');
  url = url.replace(/^\/?uploads\//, '/uploads/');
  return url;
}

function getDimName(id) {
  return dimMap.value[id] || id;
}

async function fetchList() {
  loading.value = true;
  try {
    // 调用后端 API 获取历史
    const res = await fetch(`/api/live-gen?page=${page.value}&pageSize=${pageSize.value}&q=${encodeURIComponent(keyword.value)}`);
    const data = await res.json();
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e) {
    ElMessage.error('加载失败');
  } finally {
    loading.value = false;
  }
}

function onPageChange(p) {
  page.value = p;
  fetchList();
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm('确定删除该记录？', '提示', { type: 'warning' });
    await fetch(`/api/live-gen/${row.id}`, { method: 'DELETE' });
    ElMessage.success('已删除');
    fetchList();
  } catch (e) {
    // cancel or error
  }
}

function handleReEdit(row) {
  // 跳转到生成页，并携带参数
  // 深度拷贝，避免 Proxy 代理问题
  const data = JSON.parse(JSON.stringify({
    prompt: row.prompt,
    modelId: row.modelId,
    imageUrls: row.imageUrls || []
  }));
  
  router.push({
    name: 'LiveGenHome',
    state: {
      reEditData: data
    }
  });
}
</script>

<style scoped>
.history-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.header {
  margin-bottom: 20px;
}
.filter-bar {
  margin-bottom: 20px;
}
.prompt-text {
  font-weight: 500;
  margin-bottom: 4px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.meta-info {
  font-size: 12px;
  color: #999;
  display: flex;
  gap: 8px;
  align-items: center;
}
.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>

