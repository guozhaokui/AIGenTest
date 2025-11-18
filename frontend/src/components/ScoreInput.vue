<template>
  <div class="score-input">
    <el-form :inline="true">
      <el-form-item v-for="dim in dimensions" :key="dim.id" :label="dim.name">
        <el-input-number v-model="scores[dim.id]" :min="0" :max="10" />
      </el-form-item>
    </el-form>
    <div style="margin-top:8px;">
      <el-button type="primary" @click="emit('submit', { ...scores })">提交评分</el-button>
    </div>
  </div>
</template>

<script setup>
import { reactive, watchEffect } from 'vue';

const props = defineProps({
  dimensions: { type: Array, default: () => [] },
  initialScores: { type: Object, default: () => ({}) }
});
const emit = defineEmits(['submit']);

const scores = reactive({});
watchEffect(() => {
  for (const d of props.dimensions) {
    scores[d.id] = props.initialScores[d.id] ?? 0;
  }
});
</script>

<style scoped>
.score-input {
  padding: 8px 0;
}
</style>


