<template>
  <section style="padding:16px;">
    <h1 style="margin-bottom:12px;">评估端</h1>

    <el-card header="选择试题集" style="margin-bottom:12px;">
      <el-select v-model="selectedSetId" placeholder="请选择试题集" @change="onSelectSet" style="min-width:320px;">
        <el-option v-for="s in questionSets" :key="s.id" :label="s.name" :value="s.id" />
      </el-select>
    </el-card>

    <template v-if="selectedSetId && currentQuestion">
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
import { listDimensions, listQuestions, listQuestionSets, submitEvaluation } from '../services/api';

const dimensions = ref([]);
const questions = ref([]);
const questionSets = ref([]);
const selectedSetId = ref('');
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

async function onSelectSet() {
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

async function submitScores({ questionId, scores }) {
  try {
    await submitEvaluation({ questionId, scores });
    if (currentIndex.value < questions.value.length - 1) {
      currentIndex.value += 1;
    } else {
      ElMessage.success('本试题集评估完成');
    }
  } catch (e) {
    ElMessage.error('提交失败');
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


