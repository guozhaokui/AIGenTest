<template>
  <el-card :header="title" class="q-card">
    <div style="margin-bottom:8px;">
      <el-tag v-for="d in dimensionNames" :key="d" size="small" style="margin-right:6px;">{{ d }}</el-tag>
    </div>
    <slot />
  </el-card>
  </template>

<script setup>
defineProps({
  title: { type: String, default: '试题' },
  dimensionNames: { type: Array, default: () => [] }
});
</script>

<style scoped>
.q-card {
  margin-bottom: 12px;
}
</style>


