<template>
  <section>
    <h2 style="margin-bottom:12px;">评估历史</h2>

    <!-- 未选择时：仅显示列表 -->
    <el-row v-if="!currentRun" :gutter="12">
      <el-col :span="24">
        <el-card header="批次列表">
          <el-table :data="runs" size="small" @row-click="selectRun" style="width:100%;" v-loading="loading">
            <el-table-column prop="id" label="ID" />
            <el-table-column prop="runName" label="名称" width="220" />
            <el-table-column label="试题集" width="220">
              <template #default="{ row }">{{ setName(row.questionSetId) }}</template>
            </el-table-column>
            <el-table-column label="总分" width="120">
              <template #default="{ row }">{{ scores[row.id] ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="已答题数" width="120">
              <template #default="{ row }">{{ counts[row.id] ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="开始时间" width="220">
              <template #default="{ row }">{{ formatTime(row.startedAt) }}</template>
            </el-table-column>
            <el-table-column label="结束时间" width="220">
              <template #default="{ row }">{{ formatTime(row.endedAt) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button v-if="(counts[row.id] || 0) === 0" size="small" type="danger" @click.stop="removeRun(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 已选择时：隐藏列表，详情占满 -->
    <el-row v-else :gutter="12">
      <el-col :span="24">
        <el-card>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <span style="font-weight:600;">批次详情</span>
            <div style="display:flex; gap:8px;">
              <el-button size="small" type="primary" @click="retry">重新评估</el-button>
              <el-button size="small" @click="backToList">返回列表</el-button>
            </div>
          </div>
          <p><b>名称：</b>{{ currentRun.runName || '-' }}</p>
          <p><b>描述：</b>{{ currentRun.runDesc || '-' }}</p>
          <p><b>模型：</b>{{ currentRun.modelName || '-' }}</p>
          <p><b>总分：</b>{{ currentRun.totalScore ?? '-' }}</p>
          <p><b>整体评价：</b>{{ currentRun.overallComment || '-' }}</p>
          <div style="margin:8px 0;">
            <el-tag v-for="(v,k) in currentRun.dimensionScores || {}" :key="k" size="small" style="margin-right:6px;">
              {{ dimName(k) }}: {{ v }}
            </el-tag>
          </div>
          <el-divider />
          <div v-if="items.length">
            <el-alert :title="progressText" type="info" :closable="false" style="margin-bottom:8px;" />
            <el-card :header="'题目 ' + currentItem.questionId">
              <!-- 生成图片（最上面） -->
              <div v-if="currentItem.generatedImagePath" style="margin-bottom:8px;">
                <img :src="normalize(currentItem.generatedImagePath)" style="max-width:100%; border:1px solid #eee; border-radius:4px;" />
              </div>
              <!-- 问题文本 -->
              <p style="white-space: pre-wrap;">{{ promptByQuestion(currentItem.questionId, currentItem) }}</p>
              <!-- 题目输入图片（最下面，优先快照，其次当前题库） -->
              <div v-if="imagesForItem(currentItem).length" style="margin:8px 0; display:flex; gap:8px; flex-wrap: wrap;">
                <img v-for="(u, idx) in imagesForItem(currentItem)" :key="idx" :src="normalize(u)" style="max-width:180px; border:1px solid #eee; border-radius:4px;" />
              </div>
              <div style="margin:6px 0;">
                <el-tag v-for="(v,k) in currentItem.scoresByDimension || {}" :key="k" size="small" style="margin-right:6px;">{{ dimNameForItem(k, currentItem) }}: {{ v }}</el-tag>
              </div>
              <p><b>主观评价：</b>{{ currentItem.comment || '-' }}</p>
              <p style="color:#999;">{{ formatTime(currentItem.createdAt) }}</p>
            </el-card>
            <div style="display:flex; gap:8px; margin-top:8px;">
              <el-button :disabled="currentIndex===0" @click="prev">上一题</el-button>
              <el-button :disabled="currentIndex>=items.length-1" @click="next">下一题</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </section>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { ElMessage } from 'element-plus';
import { listRuns, getRun, getRunItems, listQuestions, listDimensions, cloneRun, listQuestionSets, deleteRun } from '../services/api';
import { useRouter } from 'vue-router';

const runs = ref([]);
const questions = ref([]);
const dimensions = ref([]);
const questionSets = ref([]);
const loading = ref(false);
const currentRun = ref(null);
const items = ref([]);
const currentIndex = ref(0);
const currentItem = computed(() => items.value[currentIndex.value] || {});
const progressText = computed(() => items.value.length ? `进度：${currentIndex.value + 1} / ${items.value.length}` : '');
const counts = ref({}); // runId -> answered count
const scores = ref({}); // runId -> totalScore

function normalize(p) {
  let url = (p || '').replace(/\\/g, '/');
  if (!url.startsWith('/')) url = '/' + url;
  if (!url.startsWith('/uploads/')) {
    url = url.replace(/^\/backend\/uploads\//, '/uploads/');
    url = url.replace(/^\/uploads\//, '/uploads/');
  }
  return url;
}
function promptByQuestion(qid, item) {
  const snap = item?.questionSnapshot?.prompt;
  if (snap) return snap;
  const q = questions.value.find(x => x.id === qid);
  return q ? q.prompt : '';
}
function dimName(id) {
  const d = dimensions.value.find(x => x.id === id);
  return d ? d.name : id;
}
function dimNameForItem(id, item) {
  const map = item?.questionSnapshot?.dimNameMap;
  if (map && map[id]) return map[id];
  return dimName(id);
}
function setName(id) {
  const s = questionSets.value.find(x => x.id === id);
  return s ? s.name : id;
}
function formatTime(value) {
  if (!value) return '-';
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  });
}

function imagesForItem(item) {
  const snapImgs = item?.questionSnapshot?.imageUrls;
  if (Array.isArray(snapImgs) && snapImgs.length) return snapImgs;
  const q = questions.value.find(x => x.id === item?.questionId);
  return Array.isArray(q?.imageUrls) ? q.imageUrls : [];
}

async function loadAll() {
  try {
    loading.value = true;
    runs.value = await listRuns();
    questions.value = await listQuestions();
    dimensions.value = await listDimensions();
    questionSets.value = await listQuestionSets();
    // 异步拉取每个批次的条目与总分
    for (const r of runs.value) {
      // 获取 run 元数据（带 totalScore）
      try {
        const meta = await getRun(r.id);
        scores.value[r.id] = meta?.totalScore ?? undefined;
      } catch {}
      // 获取 items 计数
      try {
        const its = await getRunItems(r.id);
        counts.value[r.id] = Array.isArray(its) ? its.length : 0;
      } catch {}
    }
  } catch (e) {
    ElMessage.error('加载失败');
  } finally {
    loading.value = false;
  }
}
async function selectRun(row) {
  try {
    currentRun.value = await getRun(row.id);
    items.value = await getRunItems(row.id);
    currentIndex.value = 0;
  } catch (e) {
    ElMessage.error('加载详情失败');
  }
}

onMounted(loadAll);

function prev() {
  if (currentIndex.value > 0) currentIndex.value -= 1;
}
function next() {
  if (currentIndex.value < items.value.length - 1) currentIndex.value += 1;
}
function backToList() {
  currentRun.value = null;
  items.value = [];
  currentIndex.value = 0;
}

const router = useRouter();
async function retry() {
  try {
    if (!currentRun.value) return;
    const name = window.prompt('输入新的评估名称（可修改）', (currentRun.value.runName || '') + '_retry');
    if (!name) return;
    const newRun = await cloneRun(currentRun.value.id, { runName: name });
    // 跳转到开始页面，并携带 runId 直接进入评估（复用已有图片）
    router.push({ path: '/eval/start', query: { runId: newRun.id } });
  } catch (e) {
    ElMessage.error('重新评估失败');
  }
}

async function removeRun(row) {
  try {
    await deleteRun(row.id);
    runs.value = runs.value.filter(r => r.id !== row.id);
    delete counts.value[row.id];
    delete scores.value[row.id];
    ElMessage.success('已删除');
  } catch (e) {
    ElMessage.error('删除失败');
  }
}
</script>


