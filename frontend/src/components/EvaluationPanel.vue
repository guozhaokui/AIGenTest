<template>
  <el-card header="评估面板">
    <QuestionCard
      v-for="q in questions"
      :key="q.id"
      :title="q.title"
      :dimension-names="q.dimensionNames">
      <!-- 生成图片（最上面） -->
      <div v-if="imageByQ[q.id]" style="margin:8px 0;">
        <img :src="imageByQ[q.id]" style="max-width: 100%; border:1px solid #eee; border-radius:4px;" />
      </div>
      <!-- 问题文本与生成按钮 -->
      <div style="margin:8px 0;">
        <p style="white-space: pre-wrap; margin: 0 0 8px 0;">{{ q.prompt }}</p>
        <el-space>
          <el-button type="primary" :loading="genLoading[q.id]" @click="generate(q)">生成</el-button>
          <el-button :loading="genLoading[q.id]" @click="generate(q)">重新生成</el-button>
        </el-space>
      </div>
      <!-- 问题自带图片（放在最下面） -->
      <div v-if="(q.imageUrls && q.imageUrls.length)" style="margin:8px 0; display:flex; gap:8px; flex-wrap: wrap;">
        <img
          v-for="(u, idx) in q.imageUrls"
          :key="idx"
          :src="normalizeUploadUrl(u)"
          style="max-width: 180px; border:1px solid #eee; border-radius:4px;" />
      </div>
      <ScoreInput :catalog="dimensions" :initial-dimension-ids="q.dimensionIds || []" @submit="onSubmit(q.id, $event)" />
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
    modelName: { type: String, default: '' },
    initialImages: { type: Object, default: () => ({}) } // { [questionId]: imageUrl }
  },
  emits: ['submit'],
  setup(props, { emit }) {
    const imageByQ = ref({});
    const genLoading = ref({});

    // 预置已有图片（用于重新评估）
    imageByQ.value = { ...(props.initialImages || {}) };

    async function generate(q) {
      try {
        genLoading.value = { ...genLoading.value, [q.id]: true };
        // 传入题目自带的图片用于单图/多图编辑
        const paths = Array.isArray(q.imageUrls) ? q.imageUrls.filter(Boolean).map(p => normalizeUploadUrl(p)) : [];
        const { imagePath } = await generateImage({ prompt: q.prompt, modelName: props.modelName, questionId: q.id, imagePaths: paths });
        // 后端已返回形如 '/uploads/...' 的公共路径，这里仅做兜底规范化
        let publicUrl = (imagePath || '').split('\\').join('/');
        if (!publicUrl.startsWith('/')) publicUrl = '/' + publicUrl;
        if (!publicUrl.startsWith('/uploads/')) {
          // 若仍非 /uploads 前缀，尽量纠正
          publicUrl = publicUrl.replace(/^\/?backend\/uploads\//, '/uploads/');
          if (!publicUrl.startsWith('/uploads/')) {
            publicUrl = publicUrl.replace(/^\/?uploads\//, '/uploads/');
          }
        }
        imageByQ.value = { ...imageByQ.value, [q.id]: publicUrl };
      } catch (e) {
        const msg = e?.code === 'ECONNABORTED' ? '生成超时，请稍后重试' : (e?.message || '生成失败');
        ElMessage.error(msg);
      } finally {
        genLoading.value = { ...genLoading.value, [q.id]: false };
      }
    }

    function normalizeUploadUrl(p) {
      if (!p) return '';
      let url = String(p).replace(/\\/g, '/');
      if (!url.startsWith('/')) url = '/' + url;
      url = url.replace(/^\/backend\/uploads\//, '/uploads/');
      url = url.replace(/^\/?uploads\//, '/uploads/');
      return url;
    }

    function onSubmit(questionId, scores) {
      const generatedImagePath = imageByQ.value[questionId] || null;
      emit('submit', { questionId, scores, generatedImagePath });
    }

    return {
      imageByQ,
      genLoading,
      generate,
      normalizeUploadUrl,
      onSubmit
    };
  }
};
</script>

