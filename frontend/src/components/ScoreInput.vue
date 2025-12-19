<template>
  <div class="score-input">
    <el-form label-width="80px">
      <!-- 基础维度：用星级表示，默认0 => 3星 -->
      <el-form-item
        v-for="id in baseIds"
        :key="'base-' + id"
        :label="catalogMap[id]?.name || id">
        <div class="line">
          <el-rate
            v-model="starValues[id]"
            :max="5"
            :allow-half="false"
            :clearable="false"
            @change="onStarChange(id)" />
          <span class="score-text">{{ scores[id] ?? 0 }}</span>
        </div>
      </el-form-item>

      <!-- 额外维度：同样用星级表示（内部仍为 -2..2） -->
      <el-form-item
        v-for="id in extraIds"
        :key="'extra-' + id"
        :label="catalogMap[id]?.name || id">
        <div class="line">
          <el-rate
            v-model="starValues[id]"
            :max="5"
            :allow-half="false"
            :clearable="false"
            @change="onStarChange(id)" />
          <span class="score-text">{{ scores[id] ?? 0 }}</span>
        </div>
      </el-form-item>

      <el-form-item label="增加维度" v-if="allowAdd" class="add-dim-item">
        <div class="add-dim-row">
          <el-select v-model="newDimId" filterable placeholder="选择" size="small" style="width: 120px;">
            <el-option v-for="d in availableDims" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
          <el-button size="small" @click="addDim" :disabled="!newDimId">加入</el-button>
        </div>
      </el-form-item>

      <el-form-item label="主观评价">
        <el-input v-model="comment" type="textarea" :rows="2" placeholder="写下你的评价（可选）" />
      </el-form-item>
    </el-form>
    <div style="margin-top:8px;">
      <el-button type="primary" @click="submit">提交评分</el-button>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch, computed } from 'vue';

const props = defineProps({
  catalog: { type: Array, default: () => [] },               // 维度目录（全部）
  initialDimensionIds: { type: Array, default: () => [] },   // 默认显示的维度ID（来自题目）
  initialScores: { type: Object, default: () => ({}) },      // 已有分数（来自历史或继续评估）
  initialComment: { type: String, default: '' },             // 已有主观评价
  allowAdd: { type: Boolean, default: true }
});
const emit = defineEmits(['submit']);

const scores = reactive({});
const comment = ref(props.initialComment || '');
const selectedIds = ref([]);     // base + extra（顺序不重要）
const newDimId = ref('');

const catalogMap = computed(() => {
  const m = {};
  for (const d of props.catalog) m[d.id] = d;
  return m;
});
const availableDims = computed(() => {
  const chosen = new Set(selectedIds.value);
  return props.catalog.filter(d => !chosen.has(d.id));
});

// 基础/额外维度计算
const baseIds = computed(() => Array.isArray(props.initialDimensionIds) ? props.initialDimensionIds : []);
const extraIds = computed(() => selectedIds.value.filter(id => !baseIds.value.includes(id)));

// 星级映射：-2..2 <-> 1..5（0 => 3星）
const starValues = reactive({}); // id -> 1..5
function scoreToStars(n) { return Math.max(1, Math.min(5, Number(n) + 3)); }
function starsToScore(s) { return Math.max(-2, Math.min(2, Number(s) - 3)); }
function onStarChange(id) {
  scores[id] = starsToScore(starValues[id]);
}

// 初始化/更新：仅在 props 变化时运行，保留用户添加的额外维度
watch(
  () => ({ dimIds: props.initialDimensionIds, initScores: props.initialScores, initComment: props.initialComment }),
  () => {
    const base = Array.isArray(props.initialDimensionIds) ? [...props.initialDimensionIds] : [];
    // 保留已添加的额外维度
    const currentExtras = (selectedIds.value || []).filter(id => !base.includes(id));
    selectedIds.value = [...base, ...currentExtras];
    // 初始化分数与星值
    const init = props.initialScores || {};
    for (const id of selectedIds.value) {
      const n = Number.isFinite(init[id]) ? Number(init[id]) : 0;
      scores[id] = Math.max(-2, Math.min(2, n));
      starValues[id] = scoreToStars(scores[id]);
    }
    // 初始化主观评价
    if (props.initialComment) {
      comment.value = props.initialComment;
    }
  },
  { immediate: true, deep: true }
);

function addDim() {
  const id = newDimId.value;
  if (!id) return;
  if (!selectedIds.value.includes(id)) {
    selectedIds.value.push(id);
    scores[id] = 0;
    starValues[id] = scoreToStars(0);
  }
  newDimId.value = '';
}

function submit() {
  const payload = {};
  for (const id of selectedIds.value) {
    payload[id] = Number(scores[id] ?? 0) || 0;
  }
  emit('submit', { ...payload, comment: comment.value });
}
</script>

<style scoped>
.score-input {
  padding: 8px 0;
}
.line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.score-text {
  color: #666;
  font-size: 12px;
  min-width: 24px;
}
.add-dim-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.add-dim-item :deep(.el-form-item__content) {
  flex-wrap: nowrap;
}
</style>


