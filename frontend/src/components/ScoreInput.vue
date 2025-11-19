<template>
  <div class="score-input">
    <el-form label-width="96px">
      <el-form-item
        v-for="dim in dimensions"
        :key="dim.id"
        :label="dim.name">
        <div class="rate-line">
          <el-rate
            v-model="scores[dim.id]"
            :max="5"
            :allow-half="false"
            :clearable="false" />
          <span class="score-text">{{ scores[dim.id] || 0 }}/5</span>
        </div>
      </el-form-item>
    </el-form>
    <el-form label-width="96px">
      <el-form-item label="主观评价">
        <el-input v-model="comment" type="textarea" :rows="2" placeholder="写下你的评价（可选）" />
      </el-form-item>
    </el-form>
    <div style="margin-top:8px;">
      <el-button type="primary" @click="emit('submit', { ...scores, comment: comment })">提交评分</el-button>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watchEffect } from 'vue';

const props = defineProps({
  dimensions: { type: Array, default: () => [] },
  initialScores: { type: Object, default: () => ({}) }
});
const emit = defineEmits(['submit']);

const scores = reactive({});
const comment = ref('');
watchEffect(() => {
  for (const d of props.dimensions) {
    const val = props.initialScores[d.id] ?? 0;
    scores[d.id] = Math.min(5, Math.max(0, Number(val) || 0));
  }
});
</script>

<style scoped>
.score-input {
  padding: 8px 0;
}
.rate-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.score-text {
  color: #666;
  font-size: 12px;
  min-width: 28px;
}
</style>


