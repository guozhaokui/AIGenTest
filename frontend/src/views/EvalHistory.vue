<template>
  <section>
    <h2 style="margin-bottom:12px;">评估历史</h2>
    <el-row :gutter="12">
      <el-col :span="8">
        <el-card header="批次列表" style="margin-bottom:12px;">
          <el-table :data="runs" size="small" @row-click="selectRun" style="width:100%;" v-loading="loading">
            <el-table-column prop="id" label="ID" />
            <el-table-column prop="runName" label="名称" width="160" />
            <el-table-column prop="startedAt" label="开始时间" width="180" />
            <el-table-column prop="endedAt" label="结束时间" width="180" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="16">
        <el-card header="批次详情" v-if="currentRun">
          <p><b>名称：</b>{{ currentRun.runName || '-' }}</p>
          <p><b>描述：</b>{{ currentRun.runDesc || '-' }}</p>
          <p><b>模型：</b>{{ currentRun.modelName || '-' }}</p>
          <p><b>总分：</b>{{ currentRun.totalScore ?? '-' }}</p>
          <div style="margin:8px 0;">
            <el-tag v-for="(v,k) in currentRun.dimensionScores || {}" :key="k" size="small" style="margin-right:6px;">
              {{ k }}: {{ v }}
            </el-tag>
          </div>
          <el-divider />
          <div v-if="items.length">
            <el-alert :title="progressText" type="info" :closable="false" style="margin-bottom:8px;" />
            <el-card :header="'题目 ' + currentItem.questionId">
              <div v-if="currentItem.generatedImagePath" style="margin-bottom:8px;">
                <img :src="normalize(currentItem.generatedImagePath)" style="max-width:100%; border:1px solid #eee; border-radius:4px;" />
              </div>
              <p style="white-space: pre-wrap;">{{ promptByQuestion(currentItem.questionId) }}</p>
              <div style="margin:6px 0;">
                <el-tag v-for="(v,k) in currentItem.scoresByDimension || {}" :key="k" size="small" style="margin-right:6px;">{{ k }}: {{ v }}</el-tag>
              </div>
              <p><b>主观评价：</b>{{ currentItem.comment || '-' }}</p>
              <p style="color:#999;">{{ currentItem.createdAt }}</p>
            </el-card>
            <div style="display:flex; gap:8px; margin-top:8px;">
              <el-button :disabled="currentIndex===0" @click="prev">上一题</el-button>
              <el-button :disabled="currentIndex>=items.length-1" @click="next">下一题</el-button>
            </div>
          </div>
        </el-card>
        <el-empty v-else description="请选择左侧批次" />
      </el-col>
    </el-row>
  </section>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { listRuns, getRun, getRunItems, listQuestions } from '../services/api';

const runs = ref([]);
const questions = ref([]);
const loading = ref(false);
const currentRun = ref(null);
const items = ref([]);
const currentIndex = ref(0);
const currentItem = computed(() => items.value[currentIndex.value] || {});
const progressText = computed(() => items.value.length ? `进度：${currentIndex.value + 1} / ${items.value.length}` : '');

function normalize(p) {
  let url = (p || '').replace(/\\/g, '/');
  if (!url.startsWith('/')) url = '/' + url;
  if (!url.startsWith('/uploads/')) {
    url = url.replace(/^\/backend\/uploads\//, '/uploads/');
    url = url.replace(/^\/uploads\//, '/uploads/');
  }
  return url;
}
function promptByQuestion(qid) {
  const q = questions.value.find(x => x.id === qid);
  return q ? q.prompt : '';
}

async function loadAll() {
  try {
    loading.value = true;
    runs.value = await listRuns();
    questions.value = await listQuestions();
  } catch (e) {
    ElMessage.error('加载失败');
  } finally {
    loading.value = false;
  }
}
async function selectRun(row) {
  try {
    currentRun.value = await getRun(row.id);
    items.value = await getRunItems(row.id);
    currentIndex.value = 0;
  } catch (e) {
    ElMessage.error('加载详情失败');
  }
}

onMounted(loadAll);

function prev() {
  if (currentIndex.value > 0) currentIndex.value -= 1;
}
function next() {
  if (currentIndex.value < items.value.length - 1) currentIndex.value += 1;
}
</script>


