<template>
  <div class="model-viewer-container">
    <!-- 模型类型选择器 (仅对 ZIP 解压的模型显示) -->
    <div class="model-controls" v-if="!isSingleFile">
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
import { computed, ref, onMounted, onUnmounted } from 'vue';

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

// 当前选择的模型类型：pbr 或 rgb
const selectedType = ref('pbr');

// 是否为单个文件模式 (Tripo 等返回单个 GLB)
const isSingleFile = computed(() => props.info3d?.isSingleFile === true);

// 固定的文件路径结构
const currentModelUrl = computed(() => {
  const dir = props.info3d?.modelDir;
  if (!dir) return '';
  
  // 单文件模式：直接使用 modelDir/modelFile
  if (isSingleFile.value) {
    const filename = props.info3d?.modelFile || 'model.glb';
    return `${dir}/${filename}`;
  }
  
  // ZIP 解压模式：pbr/rgb 目录结构
  return selectedType.value === 'pbr' 
    ? `${dir}/pbr/mesh_textured_pbr.glb`
    : `${dir}/rgb/mesh_textured.glb`;
});

// 拼接 viewer 地址
const viewerUrl = computed(() => {
  if (!currentModelUrl.value) return '';
  let url = `/laya-viewer/index.html?url=${encodeURIComponent(currentModelUrl.value)}`;
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
