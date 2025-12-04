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

    <el-table :data="items" v-loading="loading" style="width: 100%" :row-class-name="tableRowClassName">
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
             <el-popover
                v-if="row.params && Object.keys(row.params).length"
                placement="top"
                title="生成参数"
                :width="200"
                trigger="hover"
              >
                <template #reference>
                  <el-tag size="small" type="info" effect="plain" style="cursor: pointer;">Params</el-tag>
                </template>
                <div v-for="(val, key) in row.params" :key="key" style="font-size: 12px; margin-bottom: 4px;">
                  <span style="color: #666;">{{ key }}:</span> {{ val }}
                </div>
              </el-popover>
             <el-tag size="small" type="success" v-if="row.duration">{{ row.duration }}ms</el-tag>
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
          <el-dropdown trigger="click" style="margin-left: 12px;" @command="(cmd) => handleCommand(cmd, row)">
             <el-button size="small" type="danger">
               删除<el-icon class="el-icon--right"><ArrowDown /></el-icon>
             </el-button>
             <template #dropdown>
               <el-dropdown-menu>
                 <el-dropdown-item command="delete">删除记录</el-dropdown-item>
                 <el-dropdown-item command="fullDelete" divided style="color: #f56c6c;">完全删除 (含图片)</el-dropdown-item>
               </el-dropdown-menu>
             </template>
          </el-dropdown>
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
import { useRouter, useRoute } from 'vue-router';
import { Search, ArrowDown } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { listDimensions } from '../../services/api';

const router = useRouter();
const route = useRoute();
const items = ref([]);
const loading = ref(false);
const keyword = ref('');
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const dimensions = ref([]);
const dimMap = ref({});
const highlightId = ref('');

onMounted(async () => {
  try {
    if (route.query.page) {
      page.value = parseInt(route.query.page);
    }
    if (route.query.highlight) {
      highlightId.value = route.query.highlight;
    }

    const dims = await listDimensions();
    dimensions.value = dims;
    dims.forEach(d => { dimMap.value[d.id] = d.name; });
    fetchList();
  } catch (e) {
    console.error(e);
  }
});

function tableRowClassName({ row }) {
  if (row.id === highlightId.value) {
    return 'highlight-row';
  }
  return '';
}

function formatTime(t) {
  if (!t) return '';
  return new Date(t).toLocaleString();
}

function normalizeUrl(p) {
  if (!p) return '';
  let url = String(p).replace(/\\/g, '/');
  if (!url.startsWith('/')) url = '/' + url;
  url = url.replace(/^\/backend\/imagedb\//, '/imagedb/');
  url = url.replace(/^\/?imagedb\//, '/imagedb/');
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

async function handleCommand(cmd, row) {
  if (cmd === 'delete') {
      handleDelete(row, false);
  } else if (cmd === 'fullDelete') {
      handleDelete(row, true);
  }
}

async function handleDelete(row, fullDelete = false) {
  try {
    const msg = fullDelete 
       ? '确定完全删除该记录？生成的图片文件也将被物理删除，无法恢复！'
       : '确定删除该记录？（图片文件将保留）';
       
    await ElMessageBox.confirm(msg, '警告', { 
        type: 'warning', 
        confirmButtonText: fullDelete ? '完全删除' : '删除',
        confirmButtonClass: fullDelete ? 'el-button--danger' : ''
    });
    
    const url = fullDelete ? `/api/live-gen/${row.id}?fullDelete=true` : `/api/live-gen/${row.id}`;
    await fetch(url, { method: 'DELETE' });
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
    imageUrls: row.imageUrls || [],
    params: row.params || {}
  }));
  
  router.push({
    path: '/live', // Ensure this path is correct for LiveGenHome
    state: {
      reEditData: data,
      fromPage: page.value,
      fromId: row.id
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
  line-clamp: 2;
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
:deep(.highlight-row) {
  background-color: #f0f9eb;
}
</style>

