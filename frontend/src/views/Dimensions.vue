<template>
  <section>
    <h2 style="margin-bottom:12px;">维度编辑</h2>

    <el-card header="新增维度" style="margin-bottom:16px;">
      <el-form :model="form" label-width="96px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="维度名称" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" placeholder="维度说明" />
        </el-form-item>
        <el-form-item label="加分项">
          <el-input
            v-model="form.bonusCriteriaText"
            type="textarea"
            :rows="2"
            placeholder="多项可用换行或逗号分隔" />
        </el-form-item>
        <el-form-item label="减分项">
          <el-input
            v-model="form.penaltyCriteriaText"
            type="textarea"
            :rows="2"
            placeholder="多项可用换行或逗号分隔" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="create">创建</el-button>
          <el-button @click="reset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card header="维度列表">
      <el-table :data="dimensions" size="small" style="width: 100%;" v-loading="loading">
        <el-table-column prop="id" label="ID" width="220" />
        <el-table-column prop="name" label="名称" width="120" />
        <el-table-column prop="description" label="说明" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑维度" width="640px">
      <el-form :model="edit" label-width="96px">
        <el-form-item label="ID">
          <el-input v-model="edit.id" disabled />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="edit.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="edit.description" />
        </el-form-item>
        <el-form-item label="加分项">
          <el-input v-model="edit.bonusCriteriaText" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="减分项">
          <el-input v-model="edit.penaltyCriteriaText" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { listDimensions, createDimension, updateDimension, deleteDimension } from '../services/api';

const loading = ref(false);
const dimensions = ref([]);

const form = ref({
  name: '',
  description: '',
  bonusCriteriaText: '',
  penaltyCriteriaText: ''
});

function reset() {
  form.value = { name: '', description: '', bonusCriteriaText: '', penaltyCriteriaText: '' };
}

async function fetchDimensions() {
  try {
    loading.value = true;
    dimensions.value = await listDimensions();
  } catch (e) {
    ElMessage.error('获取维度失败');
  } finally {
    loading.value = false;
  }
}

function splitText(text) {
  return (text || '')
    .split(/[\n,]/g)
    .map(s => s.trim())
    .filter(Boolean);
}

async function create() {
  if (!form.value.name) return ElMessage.warning('请填写名称');
  try {
    await createDimension({
      name: form.value.name,
      description: form.value.description,
      bonusCriteria: splitText(form.value.bonusCriteriaText),
      penaltyCriteria: splitText(form.value.penaltyCriteriaText)
    });
    ElMessage.success('创建成功');
    reset();
    await fetchDimensions();
  } catch (e) {
    ElMessage.error('创建失败');
  }
}

const editVisible = ref(false);
const edit = ref({ id: '', name: '', description: '', bonusCriteriaText: '', penaltyCriteriaText: '' });

function openEdit(row) {
  edit.value = {
    id: row.id,
    name: row.name,
    description: row.description || '',
    bonusCriteriaText: (row.bonusCriteria || []).join('\n'),
    penaltyCriteriaText: (row.penaltyCriteria || []).join('\n')
  };
  editVisible.value = true;
}

async function saveEdit() {
  try {
    await updateDimension(edit.value.id, {
      name: edit.value.name,
      description: edit.value.description,
      bonusCriteria: splitText(edit.value.bonusCriteriaText),
      penaltyCriteria: splitText(edit.value.penaltyCriteriaText)
    });
    ElMessage.success('已保存');
    editVisible.value = false;
    await fetchDimensions();
  } catch (e) {
    ElMessage.error('保存失败');
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除维度「${row.name}」吗？`, '提示', { type: 'warning' });
    await deleteDimension(row.id);
    ElMessage.success('已删除');
    await fetchDimensions();
  } catch (e) {
    // cancel or error
  }
}

onMounted(fetchDimensions);
</script>

