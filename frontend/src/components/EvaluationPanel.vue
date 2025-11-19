<template>
  <el-card header="评估面板">
    <QuestionCard
      v-for="q in questions"
      :key="q.id"
      :title="q.title"
      :prompt="q.prompt"
      :dimension-names="q.dimensionNames">
      <div style="margin:8px 0;">
        <el-space>
          <el-button type="primary" :loading="genLoading[q.id]" @click="generate(q)">生成</el-button>
          <el-button :loading="genLoading[q.id]" @click="generate(q)">重新生成</el-button>
        </el-space>
      </div>
      <div v-if="imageByQ[q.id]" style="margin:8px 0;">
        <img :src="imageByQ[q.id]" style="max-width: 100%; border:1px solid #eee; border-radius:4px;" />
      </div>
      <ScoreInput :dimensions="dimensions" @submit="onSubmit(q.id, $event)" />
    </QuestionCard>
  </el-card>
 </template>

<script>
import { ref } from 'vue';
import { ElMessage } from 'element-plus';
import QuestionCard from './QuestionCard.vue';
import ScoreInput from './ScoreInput.vue';
import { generateImage } from '../services/api';

export default {
  name: 'EvaluationPanel',
  components: { QuestionCard, ScoreInput },
  props: {
    dimensions: { type: Array, default: () => [] },
    questions: { type: Array, default: () => [] },
    modelName: { type: String, default: '' }
  },
  emits: ['submit'],
  setup(props, { emit }) {
    const imageByQ = ref({});
    const genLoading = ref({});

    async function generate(q) {
      try {
        genLoading.value = { ...genLoading.value, [q.id]: true };
        const { imagePath } = await generateImage({ prompt: q.prompt, modelName: props.modelName });
        // 统一分隔符并将 backend/ 前缀转为站点可访问路径
        const normalized = (imagePath || '').split('\\').join('/');
        let publicUrl = normalized;
        if (publicUrl.startsWith('backend/')) {
          publicUrl = '/' + publicUrl.slice('backend/'.length);
        }
        imageByQ.value = { ...imageByQ.value, [q.id]: publicUrl };
      } catch (e) {
        ElMessage.error('生成失败');
      } finally {
        genLoading.value = { ...genLoading.value, [q.id]: false };
      }
    }

    function onSubmit(questionId, scores) {
      const generatedImagePath = imageByQ.value[questionId] || null;
      emit('submit', { questionId, scores, generatedImagePath });
    }

    return {
      imageByQ,
      genLoading,
      generate,
      onSubmit
    };
  }
};
</script>

