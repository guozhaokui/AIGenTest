<template>
  <el-upload
    class="upload-demo"
    drag
    action="#"
    :auto-upload="false"
    :on-change="onFileChange"
    :limit="1"
    accept="image/png,image/jpeg,image/webp">
    <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
    <div class="el-upload__text">将文件拖到此处，或<em>点击上传</em></div>
    <template #tip>
      <div class="el-upload__tip">仅支持 PNG/JPEG/WebP，最大 10MB</div>
    </template>
  </el-upload>
  <div style="margin-top:12px;">
    <el-button type="primary" :disabled="!file" @click="emit('upload', file)">上传</el-button>
    <el-button :disabled="!file" @click="clear">清除</el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { UploadFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import Shared from '@ai-eval/shared';
const { MIME_WHITELIST, MAX_UPLOAD_BYTES } = Shared;

const file = ref(null);
const emit = defineEmits(['upload', 'clear']);

function onFileChange(uploadFile) {
  const f = uploadFile.raw;
  if (!f) return;
  if (!MIME_WHITELIST.includes(f.type)) {
    return ElMessage.error('不支持的文件类型');
  }
  if (f.size > MAX_UPLOAD_BYTES) {
    return ElMessage.error('文件过大');
  }
  file.value = f;
}
function clear() {
  file.value = null;
  emit('clear');
}
</script>


