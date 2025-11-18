<template>
  <section style="padding:16px;">
    <h1 style="margin-bottom:12px;">管理端</h1>
    <el-space direction="vertical" style="width:100%;">
      <el-card header="图片上传（示例）">
        <ImageUpload @upload="handleUpload" @clear="onClear" />
      </el-card>
      <el-card header="维度列表（示例）">
        <el-table :data="dimensions" size="small" style="width: 100%;">
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="description" label="说明" />
        </el-table>
        <div style="margin-top:8px;">
          <el-button type="primary" @click="fetchDimensions">刷新</el-button>
        </div>
      </el-card>
    </el-space>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import ImageUpload from '../components/ImageUpload.vue';
import { listDimensions, uploadExampleImage } from '../services/api';

const dimensions = ref([]);

async function fetchDimensions() {
  try {
    dimensions.value = await listDimensions();
  } catch (e) {
    ElMessage.error('获取维度失败');
  }
}
async function handleUpload(file) {
  try {
    await uploadExampleImage(file);
    ElMessage.success('上传成功');
  } catch (e) {
    ElMessage.error('上传失败');
  }
}
function onClear() {
  // no-op
}

onMounted(fetchDimensions);
</script>


