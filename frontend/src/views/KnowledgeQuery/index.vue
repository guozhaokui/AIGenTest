<template>
  <div class="knowledge-query-layout">
    <el-container style="height: 100vh">
      <el-aside width="250px" style="background-color: #f5f7fa; padding: 20px;">
        <h3 style="margin: 0 0 20px 0;">知识查询</h3>
        <el-menu
          :default-active="activeTab"
          @select="handleMenuSelect"
        >
          <el-menu-item index="query">
            <el-icon><Search /></el-icon>
            <span>智能问答</span>
          </el-menu-item>
          <el-menu-item index="docs">
            <el-icon><Document /></el-icon>
            <span>文档管理</span>
          </el-menu-item>
          <el-menu-item index="memory">
            <el-icon><Memo /></el-icon>
            <span>记忆管理</span>
          </el-menu-item>
        </el-menu>

        <!-- 统计信息 -->
        <el-card style="margin-top: 20px;" v-if="stats">
          <template #header>
            <div class="card-header">
              <span>统计信息</span>
            </div>
          </template>
          <div class="stats-item">
            <span>文档块数</span>
            <strong>{{ stats.total_documents }}</strong>
          </div>
          <div class="stats-item">
            <span>向量维度</span>
            <strong>{{ stats.dimension }}</strong>
          </div>
        </el-card>
      </el-aside>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { Search, Document, Memo } from '@element-plus/icons-vue';
import { getStats } from '@/services/api';

const router = useRouter();
const route = useRoute();
const activeTab = ref('query');
const stats = ref(null);

const handleMenuSelect = (index) => {
  activeTab.value = index;
  router.push(`/knowledge/${index}`);
};

const loadStats = async () => {
  try {
    const result = await getStats();
    if (result.success) {
      stats.value = result.data;
    }
  } catch (error) {
    console.error('加载统计信息失败:', error);
  }
};

onMounted(() => {
  // 根据路由设置active
  if (route.path.includes('/knowledge/')) {
    const parts = route.path.split('/');
    activeTab.value = parts[parts.length - 1];
  }

  loadStats();

  // 定期刷新统计
  setInterval(loadStats, 10000);
});
</script>

<style scoped>
.knowledge-query-layout {
  height: 100vh;
}

.stats-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}

.stats-item:last-child {
  border-bottom: none;
}

.stats-item strong {
  color: #409eff;
}
</style>
