<template>
  <div class="imagemgr-layout">
    <el-container>
      <el-header class="header">
        <h2>图片管理</h2>
        <div class="nav-links">
          <router-link to="/imagemgr/list">图片列表</router-link>
          <router-link to="/imagemgr/search">搜索</router-link>
          <router-link to="/imagemgr/upload">上传</router-link>
          <router-link to="/imagemgr/batch">批量处理</router-link>
        </div>
        <div class="stats" v-if="stats">
          <el-tag type="info">总计: {{ stats.total_images }}</el-tag>
          <el-tag type="success">就绪: {{ stats.ready_images }}</el-tag>
          <el-tag type="warning">待处理: {{ stats.pending_images }}</el-tag>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { getStats } from '@/services/imagemgr';

const stats = ref(null);

onMounted(async () => {
  try {
    stats.value = await getStats();
  } catch (e) {
    console.error('获取统计信息失败:', e);
  }
});
</script>

<style scoped>
.imagemgr-layout {
  height: 100%;
}

.header {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #f5f7fa;
  border-bottom: 1px solid #e4e7ed;
}

.header h2 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

.nav-links {
  display: flex;
  gap: 16px;
}

.nav-links a {
  text-decoration: none;
  color: #606266;
  padding: 4px 12px;
  border-radius: 4px;
  transition: all 0.2s;
}

.nav-links a:hover {
  background: #ecf5ff;
  color: #409eff;
}

.nav-links a.router-link-active {
  background: #409eff;
  color: white;
}

.stats {
  margin-left: auto;
  display: flex;
  gap: 8px;
}
</style>

