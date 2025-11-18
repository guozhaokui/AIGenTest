<template>
  <el-card header="评估面板">
    <div style="margin-bottom:8px;">
      <ImageUpload @upload="onUpload" @clear="onClear" />
    </div>
    <QuestionCard
      v-for="q in questions"
      :key="q.id"
      :title="q.title"
      :prompt="q.prompt"
      :dimension-names="q.dimensionNames">
      <ScoreInput :dimensions="dimensions" @submit="onSubmit(q.id, $event)" />
    </QuestionCard>
  </el-card>
 </template>

<script setup>
import ImageUpload from './ImageUpload.vue';
import QuestionCard from './QuestionCard.vue';
import ScoreInput from './ScoreInput.vue';
import { ElMessage } from 'element-plus';

const props = defineProps({
  dimensions: { type: Array, default: () => [] },
  questions: { type: Array, default: () => [] }
});

function onUpload(file) {
  ElMessage.success(`选择文件：${file?.name || ''}`);
  // 实际上传逻辑由上层通过事件接收后调用 services 实现
}
function onClear() {
  ElMessage.info('已清除文件选择');
}
function onSubmit(questionId, scores) {
  // 将评分提交给上层，由上层调用 services 发送到后端
  emit('submit', { questionId, scores });
}

const emit = defineEmits(['submit']);
</script>


