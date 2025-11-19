<template>
  <section style="padding:16px;">
    <h1 style="margin-bottom:12px;">评估端</h1>

    <el-card header="选择试题集" style="margin-bottom:12px;">
      <div style="display:flex; gap:12px; align-items:center; flex-wrap: wrap;">
        <el-select v-model="selectedSetId" placeholder="请选择试题集" :disabled="started" style="min-width:320px;">
          <el-option v-for="s in questionSets" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-input v-model="modelName" placeholder="模型名称（可选）" :disabled="started" style="width:260px;" />
        <el-button type="primary" :disabled="!selectedSetId || started" @click="start">开始评估</el-button>
        <el-button type="success" :disabled="!started || finished" @click="finish">结束本次</el-button>
      </div>
    </el-card>

    <template v-if="started && currentQuestion">
      <el-alert :title="progressText" type="info" :closable="false" style="margin-bottom:12px;" />
      <EvaluationPanel
        :dimensions="dimensions"
        :questions="[currentQuestion]"
        @submit="submitScores" />
      <div style="display:flex; gap:8px; margin-top:12px;">
        <el-button :disabled="currentIndex===0" @click="prev">上一题</el-button>
        <el-button type="warning" :disabled="currentIndex>=questions.length-1" @click="skip">跳过</el-button>
      </div>
    </template>

    <el-empty v-else description="请选择试题集以开始评估" />
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import EvaluationPanel from '../components/EvaluationPanel.vue';
import { listDimensions, listQuestions, listQuestionSets, addRunItem, startRun, finishRun } from '../services/api';

const dimensions = ref([]);
const questions = ref([]);
const questionSets = ref([]);
const selectedSetId = ref('');
const modelName = ref('');
const started = ref(false);
const finished = ref(false);
const runId = ref('');
const currentIndex = ref(0);
const currentQuestion = computed(() => questions.value[currentIndex.value] || null);
const progressText = computed(() => {
  if (!questions.value.length) return '';
  return `进度：${currentIndex.value + 1} / ${questions.value.length}`;
});

async function init() {
  try {
    dimensions.value = await listDimensions();
    questionSets.value = await listQuestionSets();
  } catch (e) {
    ElMessage.error('初始化失败');
  }
}

async function loadSetQuestions() {
  try {
    const all = await listQuestions();
    const set = questionSets.value.find(s => s.id === selectedSetId.value);
    if (!set) {
      questions.value = [];
      return;
    }
    const filtered = all.filter(q => (set.questionIds || []).includes(q.id));
    questions.value = filtered.map(q => ({
      id: q.id,
      title: q.title ?? '试题',
      prompt: q.prompt,
      dimensionNames: (q.dimensionIds || []).map(id => {
        const d = dimensions.value.find(x => x.id === id);
        return d ? d.name : id;
      })
    }));
    currentIndex.value = 0;
  } catch (e) {
    ElMessage.error('加载试题失败');
  }
}

async function start() {
  if (!selectedSetId.value) return ElMessage.warning('请先选择试题集');
  try {
    const run = await startRun({ modelName: modelName.value, questionSetId: selectedSetId.value });
    runId.value = run.id;
    started.value = true;
    finished.value = false;
    await loadSetQuestions();
  } catch (e) {
    ElMessage.error('开始失败');
  }
}

async function submitScores({ questionId, scores, generatedImagePath }) {
  try {
    if (!runId.value) return ElMessage.warning('尚未开始评估');
    await addRunItem(runId.value, { questionId, scoresByDimension: scores, generatedImagePath });
    if (currentIndex.value < questions.value.length - 1) {
      currentIndex.value += 1;
    } else {
      ElMessage.success('本试题集评估已全部提交，可点击“结束本次”结算');
    }
  } catch (e) {
    ElMessage.error('提交失败');
  }
}

async function finish() {
  try {
    if (!runId.value) return;
    await finishRun(runId.value);
    finished.value = true;
    ElMessage.success('已结束并汇总本次评估');
  } catch (e) {
    ElMessage.error('结束失败');
  }
}

function prev() {
  if (currentIndex.value > 0) currentIndex.value -= 1;
}
function skip() {
  if (currentIndex.value < questions.value.length - 1) currentIndex.value += 1;
}

onMounted(init);
</script>


