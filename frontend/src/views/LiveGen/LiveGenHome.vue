<template>
  <div class="live-gen-container">
    <div class="header">
      <h2>实时生成</h2>
      <el-button type="primary" link @click="handleBack">
        {{ returnState ? '返回' : '查看历史记录' }}
      </el-button>
    </div>

    <div class="content">
      <el-image-viewer 
        v-if="showViewer" 
        :url-list="previewUrlList" 
        @close="closeViewer" 
        :z-index="9999"
      />
      <el-card class="input-card">
        <template #header>
          <div class="card-header">
            <span>输入配置</span>
          </div>
        </template>
        
        <el-form :model="form" label-width="80px">
          <el-form-item label="模型">
            <el-select v-model="form.modelId" placeholder="选择模型" style="width: 100%">
               <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-form-item>
          
          <el-form-item label="提示词">
            <el-input 
              v-model="form.prompt" 
              type="textarea" 
              :rows="4" 
              placeholder="请输入提示词..."
            />
          </el-form-item>

          <el-form-item label="参考图">
            <el-upload
              ref="uploadRef"
              drag
              multiple
              :limit="14"
              list-type="picture-card"
              action="/api/examples/upload"
              v-model:file-list="fileList"
              :on-success="onUploadSuccess"
              :on-remove="onRemove"
              :on-preview="handlePreview"
              accept="image/*"
            >
              <el-icon><Plus /></el-icon>
            </el-upload>
            <div style="font-size: 12px; color: #666; margin-top: 4px;">最多上传 14 张参考图</div>
          </el-form-item>

          <el-form-item>
            <el-button type="primary" :loading="loading" @click="handleGenerate" style="width: 100%">
              {{ loading ? '生成中...' : '立即生成' }}
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <div class="result-section" v-if="result">
        <el-card class="result-card">
          <template #header>
            <div class="card-header">
              <span>生成结果</span>
            </div>
          </template>
          
          <div class="image-wrapper">
            <el-image 
              :src="normalizeUrl(result.imagePath)" 
              :preview-src-list="[normalizeUrl(result.imagePath)]"
              fit="contain"
              style="max-width: 100%; max-height: 500px;"
              :preview-teleported="true"
              :z-index="9999"
            />
          </div>
          
          <!-- 评分组件 -->
          <div style="margin-top: 20px;">
            <el-divider content-position="left">评估打分</el-divider>
            <ScoreInput 
              :catalog="dimensions" 
              :initial-dimension-ids="[]"
              :allow-add="true"
              @submit="handleScoreSubmit" 
            />
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Plus } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { listModels, generateImage, listDimensions, createQuestion, submitEvaluation } from '../../services/api';
import ScoreInput from '../../components/ScoreInput.vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const models = ref([]);
const dimensions = ref([]);
const loading = ref(false);
const fileList = ref([]);
const result = ref(null);
const returnState = ref(null);

const form = ref({
  modelId: '',
  prompt: '',
  imageUrls: []
});

// 复用 Question 结构来保存 Live Gen 记录，方便统一管理
// 这里我们实际上是在生成后创建一个临时的 Question 记录和 Evaluation 记录
// 或者我们可以创建一个新的 LiveGen 实体，但用户要求"生成形式与问题管理差不多"
// 我们可以复用 Question 和 Run 的概念，每次 Live Gen 实际上是一个微型的 Run
// 为了简化，我们可以在后端增加一个专门存储 Live Gen 记录的地方，或者直接复用

onMounted(async () => {
  try {
    const [mList, dList] = await Promise.all([listModels(), listDimensions()]);
    models.value = mList || [];
    dimensions.value = dList || [];
    if (models.value.length > 0) {
      form.value.modelId = models.value[0].id;
    }
    
    // 检查是否有历史记录传参 (reEditData)
    // 优先使用 window.history.state，因为 vue-router 有时封装 state
    const state = window.history.state;
    if (state && state.reEditData) {
      const data = state.reEditData;
      // console.log('ReEdit Data:', data); // Debug
      if (data.prompt) form.value.prompt = data.prompt;
      if (data.modelId) form.value.modelId = data.modelId;
      if (Array.isArray(data.imageUrls)) {
        form.value.imageUrls = [...data.imageUrls];
        // 还要回显到 fileList 以便组件显示预览
        fileList.value = data.imageUrls.map((url, i) => ({
          name: `img_${i}`,
          url: normalizeUrl(url), // 预览用
          response: { path: url } // 提交用原始路径
        }));
      }
    }

    if (state && state.fromPage) {
      returnState.value = {
        page: state.fromPage,
        highlightId: state.fromId
      };
    }
  } catch (e) {
    ElMessage.error('初始化数据失败');
  }
});

function handleBack() {
  if (returnState.value) {
    router.push({
      path: '/live/history',
      query: {
        page: returnState.value.page,
        highlight: returnState.value.highlightId
      }
    });
  } else {
    router.push('/live/history');
  }
}

function normalizeUrl(p) {
  if (!p) return '';
  let url = String(p).replace(/\\/g, '/');
  if (!url.startsWith('/')) url = '/' + url;
  url = url.replace(/^\/backend\/uploads\//, '/uploads/');
  url = url.replace(/^\/?uploads\//, '/uploads/');
  return url;
}

function onUploadSuccess(res) {
  const path = res.path || res.url; 
  // 假设后端返回 { path: 'backend/uploads/...' }
  form.value.imageUrls.push(path);
}

// 增加一个 el-image-viewer 的引用状态
const showViewer = ref(false);
const previewUrlList = ref([]);

function onRemove(file) {
  // file.response 是上传成功后的响应
  // 或者 file.url 是预览地址
  // 需要根据 fileList 的变化更新 form.imageUrls
  // 简单起见，这里直接重建 imageUrls
  const newUrls = fileList.value.map(f => f.response?.path || f.url).filter(Boolean);
  // 注意 el-upload 的 file-list 是双向绑定的，但 remove 事件触发时 fileList 可能还未更新
  // 这里我们依赖 el-upload 自动维护 fileList，我们手动同步一下
  // 但更好的方式是 upload 组件维护 fileList, 我们在提交时再提取
}

function handlePreview(file) {
  previewUrlList.value = [file.url];
  showViewer.value = true;
}

function closeViewer() {
  showViewer.value = false;
}

async function handleGenerate() {
  if (!form.value.prompt && form.value.imageUrls.length === 0) {
    ElMessage.warning('请输入提示词或上传图片');
    return;
  }
  
  loading.value = true;
  result.value = null;
  
  try {
    // 整理图片路径
    // el-upload 的 fileList 包含所有文件
    const currentFiles = fileList.value;
    const paths = currentFiles.map(f => {
        if(f.response && f.response.path) return f.response.path;
        return f.url; // 可能是回显的，或者是其他情况
    }).filter(Boolean);
    
    // 确保路径格式正确（移除开头可能多余的 /）
    const cleanPaths = paths.map(p => {
      // 如果是回显的 url (如 /uploads/examples/...), 需要转回相对路径或保持原样供后端处理
      // 后端 generate.js 会尝试加上 uploads/ 前缀，所以这里如果已经是 /uploads 开头，可以去掉开头的 /
      let s = String(p);
      if (s.startsWith('/')) s = s.slice(1);
      console.log('cleanPaths', s);
      return s;
    });

    const payload = {
      modelId: form.value.modelId,
      prompt: form.value.prompt,
      imagePaths: cleanPaths
    };
    
    const res = await generateImage(payload);
    
    // 生成成功后，我们先只是显示结果
    // 用户可以在结果出来后进行打分
    // 为了保存历史，我们需要在后端存储这次生成记录
    // 我们可以调用一个新的接口来保存 "Live Generation" 记录
    // 或者，我们可以把它看作是一个特殊的 Run Item
    
    result.value = {
      imagePath: res.imagePath,
      prompt: form.value.prompt,
      imageUrls: paths,
      modelId: form.value.modelId,
      timestamp: new Date().toISOString()
    };
    
    // 自动保存到历史记录 (通过后端 API)
    await saveToHistory(result.value);
    
  } catch (e) {
    ElMessage.error(e.message || '生成失败');
  } finally {
    loading.value = false;
  }
}

async function handleScoreSubmit(scores) {
    if (!result.value || !result.value.id) {
         // 如果 saveToHistory 没有返回 ID，我们这里需要 ID 来更新分数
         // 假设 saveToHistory 返回了记录 ID
         ElMessage.warning('正在保存记录，请稍后...');
         return; 
    }
    
    try {
        // 更新该条记录的评分
        await fetch(`/api/live-gen/${result.value.id}/score`, {
            method: 'PATCH',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(scores)
        });
        ElMessage.success('评分已保存');
    } catch(e) {
        ElMessage.error('评分保存失败');
    }
}

// 修改 saveToHistory 以获取 ID
async function saveToHistory(data) {
    const res = await fetch('/api/live-gen', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data)
    });
    const json = await res.json();
    if (json.id) {
        result.value.id = json.id;
    }
}

</script>

<style scoped>
.live-gen-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.content {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
}
.input-card {
  flex: 1;
  min-width: 300px;
}
.result-section {
  flex: 1;
  min-width: 300px;
}
.image-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f7fa;
  min-height: 200px;
  border-radius: 4px;
}
</style>

