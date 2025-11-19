<template>
  <section style="padding:16px;">
    <h1 style="margin-bottom:12px;">评估端</h1>

    <el-card header="选择试题集与信息" style="margin-bottom:12px;">
      <div style="display:flex; gap:12px; align-items:center; flex-wrap: wrap;">
        <el-select v-model="selectedSetId" placeholder="请选择试题集" :disabled="started" style="min-width:320px;">
          <el-option v-for="s in questionSets" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-input v-model="modelName" placeholder="模型名称（可选）" :disabled="started" style="width:220px;" />
        <el-input v-model="runName" placeholder="评估名称（必填）" :disabled="started" style="width:220px;" />
        <el-input v-model="runDesc" placeholder="评估描述（可选）" :disabled="started" style="width:260px;" />
        <el-button type="primary" :disabled="!selectedSetId || started" @click="start">开始评估</el-button>
        <el-button type="success" :disabled="!started || finished" @click="finish">结束本次</el-button>
      </div>
    </el-card>

    <el-card v-if="started && !finished" header="整体主观评价" style="margin-bottom:12px;">
      <el-input v-model="overallComment" type="textarea" :rows="3" placeholder="对本次评估的整体评价（可选）" />
    </el-card>

    <template v-if="started && currentQuestion">
      <el-alert :title="progressText" type="info" :closable="false" style="margin-bottom:12px;" />
      <EvaluationPanel
        :dimensions="dimensions"
        :questions="[currentQuestion]"
        :initial-images="initialImages"
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
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import EvaluationPanel from '../components/EvaluationPanel.vue';
import { listDimensions, listQuestions, listQuestionsPaged, listQuestionSets, addRunItem, startRun, finishRun, getRun, getRunItems } from '../services/api';

const route = useRoute();
const router = useRouter();

const dimensions = ref([]);
const questions = ref([]);
const questionSets = ref([]);
const selectedSetId = ref('');
const modelName = ref('');
const runName = ref('');
const runDesc = ref('');
const overallComment = ref('');
const started = ref(false);
const finished = ref(false);
const runId = ref('');
const currentIndex = ref(0);
const currentQuestion = computed(() => questions.value[currentIndex.value] || null);
const progressText = computed(() => {
  if (!questions.value.length) return '';
  return `进度：${currentIndex.value + 1} / ${questions.value.length}`;
});
const initialImages = ref({});

async function init() {
  try {
    dimensions.value = await listDimensions();
    questionSets.value = await listQuestionSets();
    // 支持从历史进入继续/重新评估：?runId=xxx
    const rid = route.query.runId;
    if (typeof rid === 'string' && rid) {
      const meta = await getRun(rid);
      const its = await getRunItems(rid);
      runId.value = rid;
      selectedSetId.value = meta.questionSetId || '';
      started.value = true;
      finished.value = Boolean(meta.endedAt);
      // 预置图片
      const map = {};
      for (const it of its || []) {
        if (it.questionId && it.generatedImagePath) {
          let url = (it.generatedImagePath || '').replace(/\\\\/g, '/').replace(/\\/g, '/');
          if (!url.startsWith('/')) url = '/' + url;
          if (!url.startsWith('/uploads/')) {
            url = url.replace(/^\/backend\/uploads\//, '/uploads/').replace(/^\/uploads\//, '/uploads/');
          }
          map[it.questionId] = url;
        }
      }
      initialImages.value = map;
      await loadSetQuestions();
    }
  } catch (e) {
    ElMessage.error('初始化失败');
  }
}

async function loadSetQuestions() {
  try {
    // 取全量题库（评估需要完整集合）
    const paged = await listQuestionsPaged({ page: 1, pageSize: 100000 });
    const all = Array.isArray(paged?.items) ? paged.items : (Array.isArray(paged) ? paged : []);
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
  if (!runName.value.trim()) return ElMessage.warning('请填写评估名称');
  try {
    const run = await startRun({ modelName: modelName.value, questionSetId: selectedSetId.value, runName: runName.value, runDesc: runDesc.value });
    runId.value = run.id;
    started.value = true;
    finished.value = false;
    initialImages.value = {};
    await loadSetQuestions();
  } catch (e) {
    ElMessage.error('开始失败');
  }
}

async function submitScores({ questionId, scores, comment, generatedImagePath }) {
  try {
    if (!runId.value) return ElMessage.warning('尚未开始评估');
    const commentText = typeof comment === 'string'
      ? comment
      : (scores && typeof scores.comment === 'string' ? scores.comment : '');
    const pureScores = { ...(scores || {}) };
    if ('comment' in pureScores) delete pureScores.comment;
    await addRunItem(runId.value, { questionId, scoresByDimension: pureScores, comment: commentText, generatedImagePath });
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
    await finishRun(runId.value, { overallComment: overallComment.value });
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


