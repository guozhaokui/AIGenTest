<template>
  <div class="model-viewer-container">
    <iframe 
      v-if="src" 
      :src="viewerUrl" 
      frameborder="0" 
      width="100%" 
      height="100%"
      allow="fullscreen"
    ></iframe>
    <div v-else class="empty">无模型数据</div>
  </div>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  src: {
    type: String,
    required: true
  }
});

// 拼接 viewer 地址
const viewerUrl = computed(() => {
  if (!props.src) return '';
  // 假设 viewer 放在 public/laya-viewer/index.html
  // 后端返回的 src 可能是 /modeldb/xx/xx.glb
  // 需要加上当前服务的 base url 或者是相对路径
  return `/laya-viewer/index.html?url=${encodeURIComponent(props.src)}`;
});
</script>

<style scoped>
.model-viewer-container {
  width: 100%;
  height: 500px; /* 给定高度 */
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}
.empty {
  color: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
