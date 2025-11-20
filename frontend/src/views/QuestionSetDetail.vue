<template>
  <section>
    <h2 style="margin-bottom:12px;">试题集详情</h2>
    <el-card header="基本信息" style="margin-bottom:16px;">
      <el-form :model="setForm" label-width="96px">
        <el-form-item label="ID">
          <el-input v-model="setForm.id" disabled />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="setForm.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="setForm.description" />
        </el-form-item>
        <el-form-item label="选择维度">
          <el-select v-model="setForm.dimensionIds" multiple filterable>
            <el-option v-for="d in dimensions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="saveSet">保存</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card header="试题列表" style="margin-bottom:16px;">
      <el-table :data="pageQuestions" size="small" style="width: 100%;">
        <el-table-column prop="id" label="ID" width="220" />
        <el-table-column prop="prompt" label="提示词" />
        <el-table-column prop="scoringRule" label="评分规则" width="240" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeFromSet(row)">移出</el-button>
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
          :total="questionsInSet.length"
          @size-change="onSizeChange"
          @current-change="onPageChange" />
      </div>
    </el-card>

    <el-card header="新增试题">
      <el-form :model="qForm" label-width="96px">
        <el-form-item label="提示词">
          <el-input v-model="qForm.prompt" />
        </el-form-item>
        <el-form-item label="维度">
          <el-select v-model="qForm.dimensionIds" multiple filterable>
            <el-option v-for="d in dimensions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="评分规则">
          <el-input v-model="qForm.scoringRule" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="createQ">创建并加入集合</el-button>
          <el-button @click="resetQ">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-dialog v-model="editVisible" title="编辑试题" width="600px">
      <el-form :model="editQ" label-width="96px">
        <el-form-item label="ID">
          <el-input v-model="editQ.id" disabled />
        </el-form-item>
        <el-form-item label="提示词">
          <el-input v-model="editQ.prompt" />
        </el-form-item>
        <el-form-item label="维度">
          <el-select v-model="editQ.dimensionIds" multiple filterable>
            <el-option v-for="d in dimensions" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="评分规则">
          <el-input v-model="editQ.scoringRule" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveQ">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { listDimensions, listQuestions, listQuestionsPaged, listQuestionSets, updateQuestionSet, createQuestion, updateQuestion } from '../services/api';

const route = useRoute();
const setId = route.params.id;

const dimensions = ref([]);
const allSets = ref([]);
const allQuestions = ref([]);

const setForm = ref({ id: '', name: '', description: '', dimensionIds: [], questionIds: [] });
const questionsInSet = computed(() => {
  const ids = new Set(setForm.value.questionIds || []);
  return allQuestions.value.filter(q => ids.has(q.id));
});
const page = ref(1);
const pageSize = ref(10);
const pageQuestions = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return questionsInSet.value.slice(start, start + pageSize.value);
});
function onPageChange(p) { page.value = p; }
function onSizeChange(s) { pageSize.value = s; page.value = 1; }

async function loadAll() {
  try {
    const [dims, sets, qsPaged] = await Promise.all([
      listDimensions(),
      listQuestionSets(),
      listQuestionsPaged({ page: 1, pageSize: 100000 })
    ]);
    dimensions.value = dims;
    allSets.value = sets;
    allQuestions.value = Array.isArray(qsPaged?.items) ? qsPaged.items : (Array.isArray(qsPaged) ? qsPaged : []);
    const current = sets.find(s => s.id === setId);
    if (!current) {
      ElMessage.error('未找到试题集');
      return;
    }
    setForm.value = { ...current };
  } catch (e) {
    ElMessage.error('加载失败');
  }
}

async function saveSet() {
  try {
    const updated = await updateQuestionSet(setForm.value.id, {
      name: setForm.value.name,
      description: setForm.value.description,
      dimensionIds: setForm.value.dimensionIds,
      questionIds: setForm.value.questionIds
    });
    setForm.value = { ...updated };
    ElMessage.success('已保存');
  } catch (e) {
    ElMessage.error('保存失败');
  }
}

const qForm = ref({ prompt: '', dimensionIds: [], scoringRule: '' });
function resetQ() {
  qForm.value = { prompt: '', dimensionIds: [], scoringRule: '' };
}
async function createQ() {
  if (!qForm.value.prompt) return ElMessage.warning('请输入提示词');
  try {
    const q = await createQuestion({
      prompt: qForm.value.prompt,
      dimensionIds: qForm.value.dimensionIds.length ? qForm.value.dimensionIds : setForm.value.dimensionIds,
      scoringRule: qForm.value.scoringRule,
      exampleIds: []
    });
    allQuestions.value.push(q);
    setForm.value.questionIds = [...(setForm.value.questionIds || []), q.id];
    await saveSet();
    resetQ();
    ElMessage.success('已创建并加入集合');
  } catch (e) {
    ElMessage.error('创建失败');
  }
}

const editVisible = ref(false);
const editQ = ref({ id: '', prompt: '', dimensionIds: [], scoringRule: '' });
function openEdit(row) {
  editQ.value = { id: row.id, prompt: row.prompt, dimensionIds: [...(row.dimensionIds || [])], scoringRule: row.scoringRule || '' };
  editVisible.value = true;
}
async function saveQ() {
  try {
    const q = await updateQuestion(editQ.value.id, {
      prompt: editQ.value.prompt,
      dimensionIds: editQ.value.dimensionIds,
      scoringRule: editQ.value.scoringRule
    });
    const idx = allQuestions.value.findIndex(x => x.id === q.id);
    if (idx !== -1) allQuestions.value[idx] = q;
    editVisible.value = false;
    ElMessage.success('已保存试题');
  } catch (e) {
    ElMessage.error('保存失败');
  }
}
async function removeFromSet(row) {
  try {
    setForm.value.questionIds = (setForm.value.questionIds || []).filter(id => id !== row.id);
    await saveSet();
    ElMessage.success('已移出集合');
  } catch (e) {
    ElMessage.error('操作失败');
  }
}

onMounted(loadAll);
</script>


