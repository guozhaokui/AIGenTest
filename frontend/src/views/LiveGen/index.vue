<template>
  <div class="live-layout">
    <!-- 极简侧边栏：仅图标 -->
    <aside class="live-sidebar">
      <div class="sidebar-logo">
        <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2">
          <polygon points="12 2 2 7 12 12 22 7 12 2"/>
          <polyline points="2 17 12 22 22 17"/>
          <polyline points="2 12 12 17 22 12"/>
        </svg>
      </div>
      <div class="sidebar-icons">
        <div class="sidebar-item" :class="{ active: isGenerate }" @click="$router.push('/live/generate')" title="实时生成">
          <el-icon :size="20"><VideoPlay /></el-icon>
        </div>
        <div class="sidebar-item" :class="{ active: isHistory }" @click="$router.push('/live/history')" title="历史记录">
          <el-icon :size="20"><Clock /></el-icon>
        </div>
      </div>
      <div class="sidebar-bottom">
        <div class="sidebar-item" @click="$router.push('/admin')" title="管理">
          <el-icon :size="18"><Setting /></el-icon>
        </div>
        <div class="sidebar-item" @click="$router.push('/')" title="退出">
          <el-icon :size="18"><SwitchButton /></el-icon>
        </div>
      </div>
    </aside>
    <main class="live-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { VideoPlay, Clock, Setting, SwitchButton } from '@element-plus/icons-vue';

const route = useRoute();
const isGenerate = computed(() => route.path === '/live/generate' || route.path === '/live');
const isHistory = computed(() => route.path === '/live/history');
</script>

<style scoped>
.live-layout {
  display: flex;
  min-height: 100vh;
  background: #f5f7fa;
}

.live-sidebar {
  width: 48px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 12px 0;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.04);
}

.sidebar-logo {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #409eff;
  margin-bottom: 24px;
}

.sidebar-icons {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar-item {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  color: #909399;
  cursor: pointer;
  transition: all 0.2s;
}

.sidebar-item:hover {
  background: #f5f7fa;
  color: #606266;
}

.sidebar-item.active {
  background: #409eff;
  color: #fff;
}

.sidebar-bottom {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.live-main {
  flex: 1;
  overflow-y: auto;
  background: #f5f7fa;
}
</style>
