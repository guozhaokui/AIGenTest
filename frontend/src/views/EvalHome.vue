<template>
  <section style="padding:16px;">
    <h1 style="margin-bottom:12px;">评估端</h1>
    <EvaluationPanel
      :dimensions="dimensions"
      :questions="questions"
      @submit="submitScores" />
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage } from 'element-plus';
import EvaluationPanel from '../components/EvaluationPanel.vue';
import { listDimensions, listQuestions, submitEvaluation } from '../services/api';

const dimensions = ref([]);
const questions = ref([]);

async function init() {
  try {
    dimensions.value = await listDimensions();
    const qs = await listQuestions();
    questions.value = qs.map(q => ({
      id: q.id,
      title: q.title ?? '试题',
      prompt: q.prompt,
      dimensionNames: (q.dimensionIds || []).map(id => {
        const d = dimensions.value.find(x => x.id === id);
        return d ? d.name : id;
      })
    }));
  } catch (e) {
    ElMessage.error('初始化失败');
  }
}

async function submitScores({ questionId, scores }) {
  try {
    await submitEvaluation({ questionId, scores });
    ElMessage.success('提交成功');
  } catch (e) {
    ElMessage.error('提交失败');
  }
}

onMounted(init);
</script>


