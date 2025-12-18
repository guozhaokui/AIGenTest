<template>
  <div class="model-viewer-container">
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
import { computed, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  info3d: {
    type: Object,
    required: true
  },
  recordId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['thumbnail']);

// 根据 info3d 构建模型列表
const modelList = computed(() => {
  const info = props.info3d;
  const dir = info?.modelDir;
  if (!dir) return [];
  
  // 单文件模式（如 Tripo）：只有一个模型
  if (info.isSingleFile) {
    const modelPath = info.modelPath || 'model.glb';
    return [
      { name: '3D模型', path: `${dir}/${modelPath}` }
    ];
  }
  
  // 多文件模式（如 Doubao ZIP 解压）：pbr/rgb 目录结构
  // 也可以通过 info3d.models 自定义模型列表
  if (info.models && Array.isArray(info.models)) {
    return info.models.map(m => ({
      name: m.name,
      path: m.path.startsWith('/') ? m.path : `${dir}/${m.path}`
    }));
  }
  
  // 默认 pbr/rgb 结构
  return [
    { name: 'PBR模型', path: `${dir}/pbr/mesh_textured_pbr.glb` },
    { name: 'RGB模型', path: `${dir}/rgb/mesh_textured.glb` }
  ];
});

// 拼接 viewer 地址
const viewerUrl = computed(() => {
  if (modelList.value.length === 0) return '';
  
  // 使用 models 参数传递模型列表
  const modelsJson = JSON.stringify(modelList.value);
  let url = `/laya-viewer/index.html?models=${encodeURIComponent(modelsJson)}`;
  
  if (props.recordId) {
    url += `&id=${props.recordId}`;
  }
  
  return url;
});

// 接收 iframe 的截图消息
function handleMessage(event) {
  if (event.data?.type === 'thumbnail' && event.data?.dataUrl) {
    emit('thumbnail', event.data.dataUrl);
  }
}

onMounted(() => {
  window.addEventListener('message', handleMessage);
});

onUnmounted(() => {
  window.removeEventListener('message', handleMessage);
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
.empty {
  color: #fff;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}
</style>
