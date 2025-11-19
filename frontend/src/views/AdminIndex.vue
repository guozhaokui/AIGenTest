<template>
  <div class="admin-layout" style="display:flex; min-height: calc(100vh - 48px);">
    <aside style="width:220px; border-right:1px solid #eee; padding:12px;">
      <el-menu :default-active="active" @select="onSelect" router>
        <el-menu-item index="/admin">概览</el-menu-item>
        <el-menu-item index="/admin/dimensions">维度编辑</el-menu-item>
        <el-menu-item index="/admin/question-sets">试题集管理</el-menu-item>
        <el-menu-item index="/admin/questions">问题管理</el-menu-item>
      </el-menu>
    </aside>
    <main style="flex:1; padding:16px;">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';

const route = useRoute();
const router = useRouter();
const active = computed(() => route.path);
function onSelect(index) {
  router.push(index);
}
</script>


