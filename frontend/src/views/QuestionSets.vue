<template>
  <section>
    <h2 style="margin-bottom:12px;">试题集管理</h2>
    <el-card header="新建试题集" style="margin-bottom:16px;">
      <el-form :model="form" label-width="96px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="输入名称" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" placeholder="输入说明" />
        </el-form-item>
        <el-form-item label="选择维度">
          <el-select v-model="form.dimensionIds" multiple filterable placeholder="选择维度">
            <el-option v-for="d in dimensions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="create">创建</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    <el-card header="试题集列表">
      <el-table :data="sets" size="small" style="width:100%" v-loading="loading">
        <el-table-column prop="id" label="ID" width="240" />
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="description" label="说明" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <router-link :to="`/admin/question-sets/${row.id}`">
              <el-button type="primary" size="small">编辑</el-button>
            </router-link>
          </template>
        </el-table-column>
        <el-table-column label="维度" width="220">
          <template #default="{ row }">
            <el-tag v-for="id in row.dimensionIds" :key="id" size="small" style="margin-right:6px;">
              {{ dimName(id) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="200" />
      </el-table>
    </el-card>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import { listDimensions, listQuestionSets, createQuestionSet } from '../services/api';

const loading = ref(false);
const dimensions = ref([]);
const sets = ref([]);
const form = ref({
  name: '',
  description: '',
  dimensionIds: []
});

function reset() {
  form.value = { name: '', description: '', dimensionIds: [] };
}
function dimName(id) {
  const d = dimensions.value.find(x => x.id === id);
  return d ? d.name : id;
}
async function fetchAll() {
  try {
    loading.value = true;
    dimensions.value = await listDimensions();
    sets.value = await listQuestionSets();
  } catch (e) {
    ElMessage.error('加载失败');
  } finally {
    loading.value = false;
  }
}
async function create() {
  if (!form.value.name) {
    return ElMessage.warning('请填写名称');
  }
  try {
    const created = await createQuestionSet({
      name: form.value.name,
      description: form.value.description,
      dimensionIds: form.value.dimensionIds
    });
    ElMessage.success('创建成功');
    reset();
    // 直接跳转到详情页进行具体试题编辑
    window.location.hash = ''; // 防止 hash 干扰
    window.location.assign(`/admin/question-sets/${created.id}`);
  } catch (e) {
    ElMessage.error('创建失败');
  }
}
onMounted(fetchAll);
</script>


