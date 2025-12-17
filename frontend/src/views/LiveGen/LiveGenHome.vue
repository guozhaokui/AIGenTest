<template>
  <div class="live-gen-container">
    <el-image-viewer 
      v-if="showViewer" 
      :url-list="previewUrlList" 
      @close="closeViewer" 
      :z-index="9999"
    />
    
    <!-- 两栏布局：左侧输入 | 右侧结果 -->
    <div class="main-layout" :class="{ 'no-result': !result }">
      <!-- 左侧输入区域 -->
      <div class="left-panel">
        <!-- 上半部分：主要输入（模型、提示词、参考图） -->
        <div class="input-section">
          <div class="section-header">
            <span>  </span>
            <el-button type="primary" link size="small" @click="handleBack">
              {{ returnState ? '返回' : '历史' }}
            </el-button>
          </div>
          
          <el-form :model="form" label-position="top" class="main-form">
            <!-- 模型选择 -->
            <el-form-item label="模型">
              <el-select v-model="form.modelId" placeholder="选择模型" style="width: 100%;">
                <el-option v-for="m in models" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </el-form-item>
            
            <!-- 互斥模式切换按钮 -->
            <el-form-item v-if="isExclusiveMode" label="输入方式">
              <el-radio-group v-model="activeInput" size="small">
                <el-radio-button value="prompt">文本</el-radio-button>
                <el-radio-button value="image">图片</el-radio-button>
              </el-radio-group>
            </el-form-item>
            
            <!-- 提示词输入 -->
            <el-form-item v-if="showPrompt" label="提示词">
              <el-input 
                v-model="form.prompt" 
                type="textarea" 
                :rows="4" 
                placeholder="输入提示词..."
                resize="vertical"
              />
            </el-form-item>
            
            <!-- 参考图上传 - 在提示词下方，用v-show保留状态 -->
            <el-form-item v-show="showImage" label="参考图">
              <div class="upload-zone">
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
                  class="ref-image-upload"
                >
                  <div class="upload-placeholder">
                    <el-icon class="upload-icon"><Plus /></el-icon>
                    <span class="upload-hint">点击或拖拽上传，最多 14 张</span>
                  </div>
                </el-upload>
              </div>
            </el-form-item>
          </el-form>
        </div>
        
        <!-- 下半部分：详细参数（仅在有参数时显示） -->
        <div class="params-section" v-if="currentModel && currentModel.parameters && currentModel.parameters.length">
          <div class="section-header">
            <span>参数设置</span>
          </div>
          <el-form :model="dynamicParams" label-position="left" label-width="90px" class="params-form">
            <el-form-item 
              v-for="param in currentModel.parameters" 
              :key="param.name"
              :label="param.label || param.name"
            >
              <template v-if="param.type === 'number'">
                <el-input-number 
                  v-model="dynamicParams[param.name]" 
                  :min="param.min" 
                  :max="param.max" 
                  :step="param.step"
                  controls-position="right"
                  size="small"
                />
              </template>
              <template v-else-if="param.type === 'select'">
                <el-select v-model="dynamicParams[param.name]" placeholder="请选择" size="small">
                  <el-option v-for="opt in param.options" :key="opt.value" :label="opt.label" :value="opt.value" />
                </el-select>
              </template>
              <template v-else>
                <el-input v-model="dynamicParams[param.name]" :placeholder="param.description" size="small" />
              </template>
            </el-form-item>
          </el-form>
        </div>
        
        <!-- 生成按钮 -->
        <el-button 
          type="primary" 
          :loading="loading" 
          @click="handleGenerate" 
          class="generate-btn"
        >
          {{ loading ? '生成中...' : '立即生成' }}
        </el-button>
      </div>

      <!-- 结果区域 - 有结果时才显示 -->
      <div class="result-panel" v-if="result">
        <div class="result-header">
          <span>生成结果</span>
          <el-button 
            size="small" 
            :type="showScore ? 'primary' : 'default'"
            @click="showScore = !showScore"
            class="score-toggle-btn"
          >
            <el-icon><Star /></el-icon>
            {{ showScore ? '收起' : '评分' }}
          </el-button>
        </div>
        <div class="result-content">
          <div class="image-wrapper">
            <!-- 图片预览 -->
            <template v-if="isImage(result.imagePath)">
              <el-image 
                :src="normalizeUrl(result.imagePath)" 
                :preview-src-list="[normalizeUrl(result.imagePath)]"
                fit="contain"
                class="result-image"
                :preview-teleported="true"
                :z-index="9999"
              />
            </template>
            
            <!-- 3D模型预览 -->
            <template v-else-if="result.info3d">
              <ModelViewer :info3d="result.info3d" :recordId="result.id" @thumbnail="handleThumbnail" />
            </template>

            <!-- 音频播放 -->
            <template v-else-if="isSound(result.imagePath)">
              <div class="audio-wrapper">
                <div style="font-size: 48px;">🎵</div>
                <audio controls :src="normalizeUrl(result.imagePath)"></audio>
              </div>
            </template>
            
            <div v-else class="unsupported">暂不支持: {{ result.imagePath }}</div>
          </div>
        </div>
      </div>

      <!-- 最右侧评分面板 -->
      <transition name="slide-right">
        <div class="score-panel" v-if="showScore && result">
          <div class="score-header">
            <span>评分</span>
            <el-button size="small" text @click="showScore = false">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
          <div class="score-content">
            <ScoreInput 
              :catalog="dimensions" 
              :initial-dimension-ids="[]"
              :allow-add="true"
              @submit="handleScoreSubmit" 
            />
          </div>
        </div>
      </transition>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { Plus, Star, Close } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { listModels, generateImage, listDimensions, createQuestion, submitEvaluation } from '../../services/api';
import ScoreInput from '../../components/ScoreInput.vue';
import ModelViewer from '../../components/ModelViewer.vue';
import { useRouter } from 'vue-router';

const router = useRouter();
const models = ref([]);
const dimensions = ref([]);
const loading = ref(false);
const fileList = ref([]);
const result = ref(null);
const returnState = ref(null);
const showScore = ref(false); // 评分区域是否展开

const form = ref({
  modelId: '',
  prompt: '',
  imageUrls: [],
  // 用于再次生成同一问题时传递给后端
  questionId: null
});

const dynamicParams = ref({});

const currentModel = computed(() => {
  return models.value.find(m => m.id === form.value.modelId);
});

// 输入模式配置
const inputMode = computed(() => currentModel.value?.inputMode || 'both');
const showPrompt = computed(() => {
  const mode = inputMode.value;
  if (mode === 'image') return false;
  if (mode === 'exclusive') return activeInput.value === 'prompt';
  return true; // both 或 prompt
});
const showImage = computed(() => {
  const mode = inputMode.value;
  if (mode === 'prompt') return false;
  if (mode === 'exclusive') return activeInput.value === 'image';
  return true; // both 或 image
});
const isExclusiveMode = computed(() => inputMode.value === 'exclusive');

// 互斥模式下当前激活的输入类型
const activeInput = ref('image');

// 互斥模式切换时清除另一种输入
watch(activeInput, (newVal) => {
  if (inputMode.value === 'exclusive') {
    if (newVal === 'prompt') {
      // 切换到提示词模式，清除图片
      fileList.value = [];
      form.value.imageUrls = [];
    } else if (newVal === 'image') {
      // 切换到图片模式，清除提示词
      form.value.prompt = '';
    }
  }
});

// 监听模型切换，初始化动态参数和输入模式
watch(() => form.value.modelId, (newVal) => {
  const model = models.value.find(m => m.id === newVal);
  if (model && Array.isArray(model.parameters)) {
    const params = {};
    model.parameters.forEach(p => {
      params[p.name] = p.default !== undefined ? p.default : '';
    });
    dynamicParams.value = params;
  } else {
    dynamicParams.value = {};
  }
  
  // 重置互斥模式的默认输入类型
  if (model?.inputMode === 'exclusive') {
    activeInput.value = model.defaultInput || 'image';
  }
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
      // 回显动态参数
      if (data.params && typeof data.params === 'object') {
        // 需要在 nextTick 或者稍后执行，因为 modelId 变化会触发 watch 重置 dynamicParams
        // 或者我们可以直接在这里赋值，但 watch 可能会覆盖
        // 更好的方式是：等 watch 执行完后再覆盖
        // 由于 watch 是同步触发（如果 modelId 变了），但 watch 内部可能有异步？
        // 这里 watch 是同步的。
        // 所以：设置 modelId -> watch 触发 -> 重置 dynamicParams -> 我们再覆盖 params
        setTimeout(() => {
           dynamicParams.value = { ...dynamicParams.value, ...data.params };
        }, 100);
      }
      // 如果有 info3d，提取 questionId 以便再次生成时存到同一问题目录下
      if (data.info3d && data.info3d.questionUuid) {
        form.value.questionId = data.info3d.questionUuid;
      }
      // 恢复之前的生成结果
      if (data.imagePath || data.info3d) {
        result.value = {
          id: data.id,
          imagePath: data.imagePath,
          prompt: data.prompt,
          imageUrls: data.imageUrls || [],
          modelId: data.modelId,
          params: data.params || {},
          duration: data.duration || 0,
          info3d: data.info3d || null,
          usage: data.usage || null
        };
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
  // 移除旧的特定替换逻辑，保留通用替换
  url = url.replace(/^\/backend\//, '/');
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
  // 根据输入模式验证
  const mode = inputMode.value;
  const hasPrompt = form.value.prompt && form.value.prompt.trim();
  const hasImages = fileList.value.length > 0;
  
  if (mode === 'prompt' && !hasPrompt) {
    ElMessage.warning('请输入提示词');
    return;
  }
  if (mode === 'image' && !hasImages) {
    ElMessage.warning('请上传参考图');
    return;
  }
  if (mode === 'exclusive') {
    if (activeInput.value === 'prompt' && !hasPrompt) {
      ElMessage.warning('请输入提示词');
      return;
    }
    if (activeInput.value === 'image' && !hasImages) {
      ElMessage.warning('请上传参考图');
      return;
    }
  }
  if (mode === 'both' && !hasPrompt && !hasImages) {
    ElMessage.warning('请输入提示词或上传图片');
    return;
  }
  
  loading.value = true;
  // 不再清空 result，保留旧结果直到新结果生成成功
  
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
      imagePaths: cleanPaths,
      // 如果是再次生成同一问题，传递 questionId
      ...(form.value.questionId ? { questionId: form.value.questionId } : {}),
      ...dynamicParams.value
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
      params: { ...dynamicParams.value },
      duration: res.duration || 0, // Store generation time
      timestamp: new Date().toISOString(),
      // 保存 3D 模型信息
      info3d: res.info3d || null,
      // 保存 token 使用信息
      usage: res.usage || null
    };
    
    // 自动保存到历史记录 (通过后端 API)
    await saveToHistory(result.value);
    
  } catch (e) {
    // 优先获取后端返回的详细错误信息
    const serverMessage = e.response?.data?.message;
    const errorMsg = serverMessage || e.message || '生成失败';
    ElMessage.error({
      message: errorMsg,
      duration: 10000,  // 显示更长时间，方便用户阅读
      showClose: true
    });
    console.error('生成失败:', e.response?.data || e);
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

function isImage(path) {
  if (!path) return false;
  return /\.(png|jpg|jpeg|webp|gif)$/i.test(path);
}

function isSound(path) {
  if (!path) return false;
  return /\.(mp3|wav|ogg|flac)$/i.test(path);
}

// 处理3D模型缩略图
async function handleThumbnail(dataUrl) {
  if (!result.value?.id) return;
  
  try {
    // 上传缩略图
    const res = await fetch(`/api/live-gen/${result.value.id}/thumbnail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataUrl })
    });
    const json = await res.json();
    if (json.thumbnailPath) {
      result.value.thumbnailPath = json.thumbnailPath;
      console.log('缩略图已保存:', json.thumbnailPath);
    }
  } catch (e) {
    console.error('缩略图上传失败:', e);
  }
}
</script>

<style scoped>
.live-gen-container {
  padding: 12px 16px;
  background: #f5f7fa;
  min-height: calc(100vh - 48px);
  color: #303133;
}

/* 布局 */
.main-layout {
  display: flex;
  gap: 20px;
  height: calc(100vh - 72px);
}

/* 无结果时居中显示左侧面板 */
.main-layout.no-result {
  justify-content: center;
}

/* 左侧输入区域 - 可被内容撑大 */
.left-panel {
  min-width: 400px;
  max-width: 550px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-self: flex-start;
}

/* 通用 section 头部 */
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

/* 上半部分：主要输入区域 */
.input-section {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.main-form :deep(.el-form-item) {
  margin-bottom: 14px;
}

.main-form :deep(.el-form-item__label) {
  color: #606266;
  font-size: 13px;
  font-weight: 500;
  padding-bottom: 4px;
}

.main-form :deep(.el-select) {
  width: 100%;
}

/* 参考图上传区域 - 固定大小图片，一行最多5张 */
.upload-zone {
  background: #fafbfc;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 10px;
  transition: border-color 0.2s;
}

.upload-zone:hover {
  border-color: #409eff;
}

.ref-image-upload {
  width: 100%;
}

.ref-image-upload :deep(.el-upload-dragger) {
  background: transparent;
  border: none;
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
}

.ref-image-upload :deep(.el-upload-list--picture-card) {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 0;
  max-width: calc(80px * 5 + 10px * 4); /* 一行最多5个 */
}

.ref-image-upload :deep(.el-upload-list__item) {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  background: #fafafa;
  margin: 0;
  flex-shrink: 0;
}

/* 隐藏上传成功的绿色对号标记 */
.ref-image-upload :deep(.el-upload-list__item-status-label) {
  display: none !important;
}

.ref-image-upload :deep(.el-upload--picture-card) {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  border: 2px dashed #dcdfe6;
  background: #fafafa;
  margin: 0;
  flex-shrink: 0;
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: #909399;
}

.upload-icon {
  font-size: 24px;
  color: #c0c4cc;
}

.upload-hint {
  font-size: 11px;
  color: #909399;
  text-align: center;
}

/* 下半部分：参数设置区域 */
.params-section {
  background: #fff;
  border-radius: 10px;
  padding: 14px;
  border: 1px solid #e4e7ed;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.params-form {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 16px;
}

.params-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.params-form :deep(.el-form-item__label) {
  color: #606266;
  font-size: 12px;
  line-height: 28px;
}

.params-form :deep(.el-input-number) {
  width: 100%;
}

.params-form :deep(.el-select) {
  width: 100%;
}

/* 生成按钮 */
.generate-btn {
  width: 100%;
  height: 42px;
  font-size: 15px;
  font-weight: 500;
  border-radius: 8px;
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  border: none;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
  transition: all 0.2s;
}

.generate-btn:hover {
  background: linear-gradient(135deg, #66b1ff 0%, #409eff 100%);
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(64, 158, 255, 0.4);
}


/* 右侧结果区域 */
.result-panel {
  flex: 1;
  min-width: 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.result-header {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-toggle-btn {
  padding: 4px 10px;
}

.score-toggle-btn .el-icon {
  margin-right: 4px;
}

.result-content {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.image-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f5f7fa;
  border-radius: 6px;
  padding: 12px;
  flex: 1;
  min-height: 0;
}

.result-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.audio-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.audio-wrapper audio {
  width: 100%;
}

.unsupported {
  color: #909399;
  font-size: 12px;
}

/* 最右侧评分面板 */
.score-panel {
  width: 320px;
  flex-shrink: 0;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.score-header {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  background: #fafafa;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.score-content {
  padding: 12px;
  overflow-y: auto;
  overflow-x: hidden;
  flex: 1;
}

/* 评分面板过渡动画 */
.slide-right-enter-active,
.slide-right-leave-active {
  transition: all 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
  opacity: 0;
  width: 0;
  padding: 0;
  margin-left: -16px;
}

.slide-right-enter-to,
.slide-right-leave-from {
  opacity: 1;
  width: 320px;
  margin-left: 0;
}

/* 评分面板内部样式覆盖 */
.score-content :deep(.el-form-item) {
  margin-bottom: 12px;
}

.score-content :deep(.el-form-item__label) {
  font-size: 12px;
  color: #606266;
}

.score-content :deep(.el-rate) {
  height: 20px;
}

.score-content :deep(.el-rate__icon) {
  font-size: 16px;
}
</style>

