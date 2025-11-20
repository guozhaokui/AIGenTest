<template>
  <section>
    <h2 style="margin-bottom:12px;">问题管理</h2>
    <div style="margin-bottom:12px; display:flex; gap:8px; flex-wrap: wrap;">
      <el-input v-model="keyword" placeholder="搜索提示词" style="width:280px;" clearable />
      <el-button type="primary" @click="fetchList">查询</el-button>
      <el-button @click="resetAndFetch">重置</el-button>
    </div>
    <el-card>
      <el-table :data="items" size="small" style="width:100%;" v-loading="loading">
        <el-table-column prop="id" label="ID" width="260" />
        <el-table-column prop="prompt" label="提示词" />
        <el-table-column label="更新时间" width="200">
          <template #default="{ row }">{{ formatTime(row.updatedAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="cloneRow(row)">复制</el-button>
            <el-button size="small" type="danger" @click="removeRow(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex; justify-content:flex-end; margin-top:12px;">
        <el-pagination
          background
          layout="prev, pager, next, sizes, total"
          :page-sizes="[10,20,50,100]"
          :page-size="pageSize"
          :current-page="page"
          :total="total"
          @size-change="onSizeChange"
          @current-change="onPageChange" />
      </div>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑问题" width="720px">
      <el-form :model="edit" label-width="96px">
        <el-form-item label="ID">
          <el-input v-model="edit.id" disabled />
        </el-form-item>
        <el-form-item label="提示词">
          <el-input v-model="edit.prompt" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="评分规则">
          <el-input v-model="edit.scoringRule" />
        </el-form-item>
        <el-form-item label="维度">
          <el-select v-model="edit.dimensionIds" multiple filterable placeholder="选择维度">
            <el-option v-for="d in dimensions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </section>
 </template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { listQuestionsPaged, updateQuestion, deleteQuestion, cloneQuestion, listDimensions } from '../services/api';

const loading = ref(false);
const items = ref([]);
const page = ref(1);
const pageSize = ref(10);
const total = ref(0);
const keyword = ref('');

const dimensions = ref([]);
const editVisible = ref(false);
const edit = ref({ id: '', prompt: '', scoringRule: '', dimensionIds: [] });

async function fetchList() {
  try {
    loading.value = true;
    const data = await listQuestionsPaged({ page: page.value, pageSize: pageSize.value, q: keyword.value });
    items.value = data.items || [];
    total.value = data.total || 0;
  } catch (e) {
    ElMessage.error('加载失败');
  } finally {
    loading.value = false;
  }
}
function onPageChange(p) {
  page.value = p;
  fetchList();
}
function onSizeChange(s) {
  pageSize.value = s;
  page.value = 1;
  fetchList();
}
function resetAndFetch() {
  keyword.value = '';
  page.value = 1;
  fetchList();
}

function openEdit(row) {
  edit.value = { id: row.id, prompt: row.prompt, scoringRule: row.scoringRule || '', dimensionIds: [...(row.dimensionIds || [])] };
  editVisible.value = true;
}
async function saveEdit() {
  try {
    await updateQuestion(edit.value.id, {
      prompt: edit.value.prompt,
      scoringRule: edit.value.scoringRule,
      dimensionIds: edit.value.dimensionIds
    });
    ElMessage.success('已保存');
    editVisible.value = false;
    fetchList();
  } catch (e) {
    ElMessage.error('保存失败');
  }
}
async function removeRow(row) {
  try {
    await ElMessageBox.confirm(`确定删除该问题？`, '提示', { type: 'warning' });
    await deleteQuestion(row.id);
    ElMessage.success('已删除');
    fetchList();
  } catch (e) {
    // cancel or error
  }
}
async function cloneRow(row) {
  try {
    const newQ = await cloneQuestion(row.id);
    ElMessage.success(`已复制，新的ID：${newQ.id}`);
    fetchList();
  } catch (e) {
    ElMessage.error('复制失败');
  }
}

onMounted(async () => {
  try {
    dimensions.value = await listDimensions();
  } catch {}
  fetchList();
});

function formatTime(value) {
  if (!value) return '-';
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}
</script>


