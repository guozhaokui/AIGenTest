<template>
  <div class="model-viewer-container">
    <!-- 模型类型选择器 -->
    <div class="model-controls">
      <el-radio-group v-model="selectedType" size="small">
        <el-radio-button value="pbr">PBR 模型</el-radio-button>
        <el-radio-button value="rgb">RGB 模型</el-radio-button>
      </el-radio-group>
    </div>
    
    <iframe 
      :src="viewerUrl" 
      frameborder="0" 
      width="100%" 
      height="100%"
      allow="fullscreen"
    ></iframe>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  info3d: {
    type: Object,
    required: true
  }
});

// 当前选择的模型类型：pbr 或 rgb
const selectedType = ref('pbr');

// 固定的文件路径结构
const currentModelUrl = computed(() => {
  const dir = props.info3d?.modelDir;
  if (!dir) return '';
  return selectedType.value === 'pbr' 
    ? `${dir}/pbr/mesh_textured_pbr.glb`
    : `${dir}/rgb/mesh_textured.glb`;
});

// 拼接 viewer 地址
const viewerUrl = computed(() => {
  if (!currentModelUrl.value) return '';
  return `/laya-viewer/index.html?url=${encodeURIComponent(currentModelUrl.value)}`;
});
</script>

<style scoped>
.model-viewer-container {
  width: 100%;
  height: 500px; /* 给定高度 */
  background: #000;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}
.model-controls {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  padding: 5px 10px;
  border-radius: 4px;
}
.empty {
  color: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
