<template>
  <section style="padding:16px;">
    <h1 style="margin-bottom:12px;">评估端</h1>

    <el-card header="选择试题集与信息" style="margin-bottom:12px;">
      <div style="display:flex; gap:12px; align-items:center; flex-wrap: wrap;">
        <el-select v-model="selectedSetId" placeholder="请选择试题集" :disabled="started" style="min-width:320px;">
          <el-option v-for="s in questionSets" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="selectedModelId" placeholder="选择模型" :disabled="started" style="min-width:240px;">
          <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <el-input v-model="modelName" placeholder="自定义模型名（可选）" :disabled="started" style="width:220px;" />
        <el-input v-model="runName" placeholder="评估名称（必填）" :disabled="started" style="width:220px;" />
        <el-input v-model="runDesc" placeholder="评估描述（可选）" :disabled="started" style="width:260px;" />
        <el-button type="primary" :disabled="!selectedSetId || started" @click="start">开始评估</el-button>
        <el-button type="success" :disabled="!started || finished" @click="finish">结束本次</el-button>
        <el-button type="warning" :disabled="!selectedSetId || autoRunning || finished" @click="autoEvaluate">自动评估（生成并保存全部）</el-button>
        <el-progress v-if="autoRunning" :percentage="Math.round((autoIdx / Math.max(questions.length,1)) * 100)" style="width:240px;" />
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
import { listDimensions, listQuestions, listQuestionsPaged, listQuestionSets, addRunItem, startRun, finishRun, getRun, getRunItems, listModels, generateImage } from '../services/api';

const route = useRoute();
const router = useRouter();

const dimensions = ref([]);
const questions = ref([]);
const questionSets = ref([]);
const selectedSetId = ref('');
const modelName = ref('');
const models = ref([]);
const selectedModelId = ref('');
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
const autoRunning = ref(false);
const autoIdx = ref(0);

async function init() {
  try {
    dimensions.value = await listDimensions();
    questionSets.value = await listQuestionSets();
    models.value = await listModels();
    if (models.value.length && !selectedModelId.value) selectedModelId.value = models.value[0].id;
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
      imageUrls: Array.isArray(q.imageUrls) ? q.imageUrls : [],
      modelId: selectedModelId.value || '',
      dimensionIds: Array.isArray(q.dimensionIds) ? q.dimensionIds : [],
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
    const chosen = models.value.find(m => m.id === selectedModelId.value);
    const run = await startRun({
      modelName: modelName.value || (chosen ? chosen.name : ''),
      questionSetId: selectedSetId.value,
      runName: runName.value,
      runDesc: runDesc.value
    });
    runId.value = run.id;
    started.value = true;
    finished.value = false;
    initialImages.value = {};
    await loadSetQuestions();
  } catch (e) {
    ElMessage.error('开始失败');
  }
}

// 默认评分构造：按题目维度，若无则用试题集维度；分值为 0（-2..2 规则下的默认）
function buildDefaultScores(q, set) {
  const ids = (Array.isArray(q.dimensionIds) && q.dimensionIds.length)
    ? q.dimensionIds
    : (Array.isArray(set.dimensionIds) ? set.dimensionIds : []);
  const m = {};
  for (const id of ids) m[id] = 0;
  return m;
}

// 自动评估：逐题生成并保存条目，最后结束本次
async function autoEvaluate() {
  if (!selectedSetId.value) return ElMessage.warning('请先选择试题集');
  try {
    autoRunning.value = true;
    autoIdx.value = 0;

    // 若题目尚未载入，先载入
    if (!questions.value.length) {
      await loadSetQuestions();
    }
    if (!questions.value.length) {
      return ElMessage.warning('试题为空，请在试题集内添加题目');
    }

    // 若未开始则先创建 run
    if (!started.value) {
      const chosen = models.value.find(m => m.id === selectedModelId.value);
      const run = await startRun({
        modelName: modelName.value || (chosen ? chosen.name : ''),
        questionSetId: selectedSetId.value,
        runName: runName.value || 'AutoRun',
        runDesc: runDesc.value || 'Auto generated'
      });
      runId.value = run.id;
      started.value = true;
      finished.value = false;
    }

    const set = questionSets.value.find(s => s.id === selectedSetId.value) || {};
    for (let i = 0; i < questions.value.length; i += 1) {
      const q = questions.value[i];
      autoIdx.value = i;

      const payload = {
        prompt: q.prompt,
        questionId: q.id,
        imagePaths: Array.isArray(q.imageUrls) ? q.imageUrls.filter(Boolean) : []
      };
      if (selectedModelId.value) payload.modelId = selectedModelId.value;

      let imagePath = null;
      try {
        const r = await generateImage(payload);
        imagePath = r?.imagePath || null;
      } catch (e) {
        // 不中断，继续下一个
        // console.error('auto generate failed:', e);
      }

      const scores = buildDefaultScores(q, set);
      await addRunItem(runId.value, {
        questionId: q.id,
        generatedImagePath: imagePath,
        scoresByDimension: scores,
        comment: '[AUTO] 默认得分 0'
      });
    }

    await finishRun(runId.value, { overallComment: '[AUTO] 已自动生成并保存全部题目，默认得分 0' });
    finished.value = true;
    ElMessage.success('自动评估完成');
  } catch (e) {
    ElMessage.error('自动评估失败');
  } finally {
    autoRunning.value = false;
    autoIdx.value = questions.value.length;
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


