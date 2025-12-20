<template>
  <div class="live-gen-container">
    <el-image-viewer 
      v-if="showViewer" 
      :url-list="previewUrlList" 
      @close="closeViewer" 
      :z-index="9999"
    />
    
    <!-- 模型选择对话框 -->
    <ModelSelectDialog
      v-model="modelSelectDialogVisible"
      :driver-filter="modelSelectCurrentParam?.driverFilter || ''"
      :task-type-filter="modelSelectCurrentParam?.taskTypeFilter || []"
      :exclude-versions="modelSelectCurrentParam?.excludeModelVersions || []"
      @select="handleModelSelect"
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
            
            <!-- 多槽位图片上传（如 Tripo Multiview） -->
            <el-form-item v-if="showImage && hasImageSlots" label="参考图">
              <div class="image-slots-container">
                <div 
                  v-for="(slot, index) in imageSlots" 
                  :key="slot.name" 
                  class="image-slot"
                >
                  <div class="slot-label">
                    {{ slot.label }}
                    <span v-if="slot.required" class="required-mark">*</span>
                  </div>
                  <el-upload
                    :ref="el => setSlotUploadRef(slot.name, el)"
                    list-type="picture-card"
                    action="/api/examples/upload"
                    :limit="1"
                    :file-list="slotFileLists[slot.name] || []"
                    :on-success="(res, file, list) => onSlotUploadSuccess(slot.name, res, file, list)"
                    :on-remove="(file, list) => onSlotRemove(slot.name, file, list)"
                    :on-preview="handlePreview"
                    accept="image/*"
                    class="slot-upload"
                  >
                    <el-icon class="upload-icon"><Plus /></el-icon>
                  </el-upload>
                  <div class="slot-hint">{{ slot.description }}</div>
                </div>
              </div>
            </el-form-item>
            
            <!-- 通用参考图/文件上传 - 在提示词下方，用v-show保留状态 -->
            <el-form-item v-else-if="showImage" :label="supportsFile ? '上传文件' : '参考图'">
              <div class="upload-zone">
                <el-upload
                  ref="uploadRef"
                  drag
                  :multiple="!isSingleImageInput"
                  :limit="imageUploadLimit"
                  :list-type="supportsFile ? 'text' : 'picture-card'"
                  action="/api/examples/upload"
                  v-model:file-list="fileList"
                  :on-success="onUploadSuccess"
                  :on-remove="onRemove"
                  :on-preview="handlePreview"
                  :accept="supportsFile ? inputAccept : 'image/*'"
                  class="ref-image-upload"
                  :class="{ 
                    'hide-upload-trigger': hasEnoughImages,
                    'file-upload-mode': supportsFile
                  }"
                >
                  <div class="upload-placeholder">
                    <el-icon class="upload-icon"><Plus /></el-icon>
                    <span class="upload-hint">{{ inputHint || imageUploadHint }}</span>
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
              <template v-else-if="param.type === 'model_select'">
                <!-- 模型选择器 -->
                <div class="model-select-trigger">
                  <div 
                    v-if="selectedModelInfo[param.name]" 
                    class="selected-model-preview"
                    @click="openModelSelectDialog(param)"
                  >
                    <img 
                      v-if="selectedModelInfo[param.name].thumbnail" 
                      :src="selectedModelInfo[param.name].thumbnail" 
                      class="preview-thumb"
                    />
                    <div v-else class="preview-placeholder">
                      <el-icon><Picture /></el-icon>
                    </div>
                    <div class="preview-info">
                      <div class="preview-type">{{ formatTaskType(selectedModelInfo[param.name].meta?.taskType) }}</div>
                      <div class="preview-id">{{ truncateId(selectedModelInfo[param.name].meta?.taskId) }}</div>
                    </div>
                    <el-button size="small" type="danger" text @click.stop="clearModelSelect(param.name)">
                      <el-icon><Close /></el-icon>
                    </el-button>
                  </div>
                  <el-button v-else type="primary" plain @click="openModelSelectDialog(param)">
                    <el-icon><FolderOpened /></el-icon>
                    选择模型
                  </el-button>
                </div>
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
          <div class="result-actions">
            <!-- 添加到参考图按钮 - 仅图片类型显示 -->
            <el-button 
              v-if="isImage(result.imagePath)"
              size="small" 
              @click="addResultToRef"
              title="添加到参考图"
            >
              <el-icon><Picture /></el-icon>
              加入参考
            </el-button>
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
              :initial-dimension-ids="existingDimensionIds"
              :initial-scores="result?.dimensionScores || {}"
              :initial-comment="result?.comment || ''"
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
import { Plus, Star, Close, Picture, FolderOpened } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { listModels, generateImage, listDimensions, createQuestion, submitEvaluation } from '../../services/api';
import ScoreInput from '../../components/ScoreInput.vue';
import ModelSelectDialog from '../../components/ModelSelectDialog.vue';
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

// 多槽位图片上传状态（用于 imageSlots 配置的模型）
const slotFileLists = ref({}); // { slotName: fileList }
const slotUploadRefs = ref({}); // { slotName: uploadRef }

const form = ref({
  modelId: '',
  prompt: '',
  imageUrls: [],
  // 用于再次生成同一问题时传递给后端
  questionId: null
});

const dynamicParams = ref({});

// 模型选择相关状态（用于 model_select 类型参数）
const modelSelectDialogVisible = ref(false);
const modelSelectCurrentParam = ref(null);
const selectedModelInfo = ref({}); // { paramName: modelInfo }

const currentModel = computed(() => {
  return models.value.find(m => m.id === form.value.modelId);
});

// 输入配置（新结构）
const inputConfig = computed(() => currentModel.value?.input || { types: ['text', 'image'], mode: 'combined' });
const inputTypes = computed(() => inputConfig.value.types || ['text', 'image']);
const inputMode = computed(() => inputConfig.value.mode || 'combined');

// 是否支持文本/图片/文件输入
const supportsText = computed(() => inputTypes.value.includes('text'));
const supportsImage = computed(() => inputTypes.value.includes('image'));
const supportsFile = computed(() => inputTypes.value.includes('file'));

// 文件上传的 accept 类型和提示
const inputAccept = computed(() => inputConfig.value.accept || 'image/*');
const inputHint = computed(() => inputConfig.value.hint || '');

// 是否有 imageSlots 配置（多槽位图片上传）
const hasImageSlots = computed(() => {
  const slots = inputConfig.value.imageSlots;
  return slots && slots.length > 0;
});

// 获取 imageSlots 配置
const imageSlots = computed(() => inputConfig.value.imageSlots || []);

// 判断是否是单图输入模式
// mode: "single" 表示单图，或者 types 只包含 "image" 且 mode 是 "exclusive"
const isSingleImageInput = computed(() => {
  const mode = inputMode.value;
  // single 模式且只支持图片
  if (mode === 'single' && supportsImage.value && !supportsText.value) return true;
  // exclusive 模式（文本或图片二选一，选图片时只能一张）
  if (mode === 'exclusive') return true;
  return false;
});

// 图片上传数量限制
const imageUploadLimit = computed(() => {
  if (isSingleImageInput.value) return 1;
  return 14;
});

// 图片上传提示文字
const imageUploadHint = computed(() => {
  if (isSingleImageInput.value) return '点击或拖拽上传 1 张图片';
  return '点击或拖拽上传，最多 14 张';
});

// 判断是否已上传足够图片（单图模式下已有1张则隐藏上传框）
const hasEnoughImages = computed(() => {
  if (isSingleImageInput.value && fileList.value.length >= 1) {
    return true;
  }
  return false;
});

// 已有评分的维度 ID 列表（用于编辑历史记录时显示）
const existingDimensionIds = computed(() => {
  if (result.value?.dimensionScores) {
    return Object.keys(result.value.dimensionScores);
  }
  return [];
});
// params_only 模式：不需要提示词或图片，只需要参数
const isParamsOnlyMode = computed(() => inputMode.value === 'params_only');

const showPrompt = computed(() => {
  if (isParamsOnlyMode.value) return false;
  if (!supportsText.value) return false;
  if (inputMode.value === 'exclusive') return activeInput.value === 'prompt';
  return true;
});
const showImage = computed(() => {
  if (isParamsOnlyMode.value) return false;
  // 支持 image 或 file 类型
  if (!supportsImage.value && !supportsFile.value) return false;
  if (inputMode.value === 'exclusive') return activeInput.value === 'image';
  return true;
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
  if (model?.input?.mode === 'exclusive') {
    activeInput.value = model.input.default || 'image';
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
          usage: data.usage || null,
          dimensionScores: data.dimensionScores || {}, // 恢复评分信息
          comment: data.comment || '' // 恢复主观评价
        };
        
        // 如果有评分或主观评价，自动展开评分面板
        if ((data.dimensionScores && Object.keys(data.dimensionScores).length > 0) || data.comment) {
          showScore.value = true;
        }
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

// 多槽位上传相关方法
function setSlotUploadRef(slotName, el) {
  if (el) {
    slotUploadRefs.value[slotName] = el;
  }
}

function onSlotUploadSuccess(slotName, res, file, list) {
  const path = res.path || res.url;
  // 更新该槽位的文件列表
  slotFileLists.value[slotName] = list.map(f => ({
    ...f,
    slotPath: f.response?.path || f.response?.url || path
  }));
}

function onSlotRemove(slotName, file, list) {
  slotFileLists.value[slotName] = list;
}

// 获取多槽位图片路径（按槽位顺序）
function getSlotImagePaths() {
  if (!hasImageSlots.value) return [];
  
  const slots = imageSlots.value;
  const paths = [];
  
  for (const slot of slots) {
    const files = slotFileLists.value[slot.name] || [];
    if (files.length > 0) {
      const file = files[0];
      const path = file.slotPath || file.response?.path || file.response?.url || file.url;
      paths.push({ slot: slot.name, path: path || null });
    } else {
      paths.push({ slot: slot.name, path: null });
    }
  }
  
  return paths;
}

// 验证多槽位图片是否满足要求
function validateSlotImages() {
  if (!hasImageSlots.value) return { valid: true };
  
  const slots = imageSlots.value;
  const missingRequired = [];
  let totalImages = 0;
  
  for (const slot of slots) {
    const files = slotFileLists.value[slot.name] || [];
    if (files.length > 0) {
      totalImages++;
    } else if (slot.required) {
      missingRequired.push(slot.label);
    }
  }
  
  if (missingRequired.length > 0) {
    return { valid: false, message: `请上传必需的图片: ${missingRequired.join(', ')}` };
  }
  
  // Tripo 多视图要求至少 2 张图片
  if (totalImages < 2) {
    return { valid: false, message: '多视图生成至少需要 2 张图片' };
  }
  
  return { valid: true };
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

// ========== 模型选择器相关方法（用于 model_select 类型参数） ==========
function openModelSelectDialog(param) {
  modelSelectCurrentParam.value = param;
  modelSelectDialogVisible.value = true;
}

function handleModelSelect(model) {
  if (!modelSelectCurrentParam.value) return;
  
  const paramName = modelSelectCurrentParam.value.name;
  
  // 保存选中的模型信息（用于显示）
  selectedModelInfo.value[paramName] = model;
  
  // 将 taskId 设置到动态参数
  if (model.meta?.taskId) {
    dynamicParams.value[paramName] = model.meta.taskId;
  }
  
  modelSelectDialogVisible.value = false;
  modelSelectCurrentParam.value = null;
}

function clearModelSelect(paramName) {
  delete selectedModelInfo.value[paramName];
  dynamicParams.value[paramName] = '';
}

function formatTaskType(type) {
  const typeMap = {
    'image_to_model': '图片转3D',
    'text_to_model': '文字转3D',
    'multiview_to_model': '多视图3D',
    'refine_model': '优化模型'
  };
  return typeMap[type] || type || '未知';
}

function truncateId(id) {
  if (!id) return '-';
  if (id.length <= 16) return id;
  return id.slice(0, 8) + '...' + id.slice(-4);
}

// 将生成结果添加到参考图
function addResultToRef() {
  if (!result.value || !result.value.imagePath) return;
  
  const url = normalizeUrl(result.value.imagePath);
  
  // 检查是否已存在
  const exists = fileList.value.some(f => f.url === url || f.response?.url === result.value.imagePath);
  if (exists) {
    ElMessage.warning('该图片已在参考图中');
    return;
  }
  
  // 检查数量限制
  if (fileList.value.length >= 14) {
    ElMessage.warning('参考图最多 14 张');
    return;
  }
  
  // 添加到 fileList
  fileList.value.push({
    name: result.value.imagePath.split('/').pop(),
    url: url,
    response: { url: result.value.imagePath }
  });
  
  ElMessage.success('已添加到参考图');
}

async function handleGenerate() {
  // 根据输入模式验证
  const mode = inputMode.value;
  const hasPrompt = form.value.prompt && form.value.prompt.trim();
  
  // params_only 模式：不需要验证图片或文本（如 Tripo Refine）
  if (mode === 'params_only') {
    // 跳过输入验证，直接进入生成流程
    console.log('[generate] params_only mode, skipping input validation');
  }
  // 检查是否有多槽位图片配置
  else if (hasImageSlots.value) {
    const validation = validateSlotImages();
    if (!validation.valid) {
      ElMessage.warning(validation.message);
      return;
    }
  } else {
    // 通用图片验证
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
  }
  
  loading.value = true;
  // 不再清空 result，保留旧结果直到新结果生成成功
  
  try {
    let cleanPaths = [];
    let imageSlotData = null;
    
    if (hasImageSlots.value) {
      // 多槽位图片模式
      const slotPaths = getSlotImagePaths();
      imageSlotData = slotPaths; // 传递完整的槽位信息给后端
      
      // 也提取非空路径用于兼容
      cleanPaths = slotPaths
        .filter(s => s.path)
        .map(s => {
          let p = String(s.path);
          if (p.startsWith('/')) p = p.slice(1);
          return p;
        });
      
      console.log('Slot image paths:', slotPaths);
    } else {
      // 通用多图上传模式
      const currentFiles = fileList.value;
      const paths = currentFiles.map(f => {
          if(f.response && f.response.path) return f.response.path;
          return f.url; // 可能是回显的，或者是其他情况
      }).filter(Boolean);
      
      // 确保路径格式正确（移除开头可能多余的 /）
      cleanPaths = paths.map(p => {
        let s = String(p);
        if (s.startsWith('/')) s = s.slice(1);
        console.log('cleanPaths', s);
        return s;
      });
    }

    const payload = {
      modelId: form.value.modelId,
      prompt: form.value.prompt,
      imagePaths: cleanPaths,
      // 多槽位图片数据（包含槽位名称和路径）
      ...(imageSlotData ? { imageSlots: imageSlotData } : {}),
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
      imageUrls: cleanPaths,
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

/* 多槽位图片上传（如 Tripo Multiview） */
.image-slots-container {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  background: #fafbfc;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  padding: 12px;
}

.image-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100px;
}

.slot-label {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 6px;
  text-align: center;
}

.required-mark {
  color: #f56c6c;
  margin-left: 2px;
}

.slot-upload {
  width: 80px;
}

.slot-upload :deep(.el-upload--picture-card) {
  width: 80px;
  height: 80px;
  border-radius: 6px;
  border: 2px dashed #dcdfe6;
  background: #fff;
}

.slot-upload :deep(.el-upload-list--picture-card) {
  display: flex;
}

.slot-upload :deep(.el-upload-list__item) {
  width: 80px;
  height: 80px;
  margin: 0;
  border-radius: 6px;
}

/* 隐藏上传成功的绿色对号标记 */
.slot-upload :deep(.el-upload-list__item-status-label) {
  display: none !important;
}

/* 只有一张图片时隐藏上传按钮 */
.slot-upload :deep(.el-upload--picture-card) {
  display: flex;
}

.slot-upload:has(.el-upload-list__item) :deep(.el-upload--picture-card) {
  display: none;
}

.slot-hint {
  font-size: 11px;
  color: #909399;
  margin-top: 4px;
  text-align: center;
  max-width: 100px;
  word-break: break-all;
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

/* 单图模式：已上传图片后隐藏上传触发器 */
.ref-image-upload.hide-upload-trigger :deep(.el-upload--picture-card) {
  display: none !important;
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

/* 文件上传模式（如 GLB 文件） */
.ref-image-upload.file-upload-mode {
  width: 100%;
}

.ref-image-upload.file-upload-mode :deep(.el-upload) {
  width: 100%;
}

.ref-image-upload.file-upload-mode :deep(.el-upload-dragger) {
  width: 100%;
  height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 2px dashed #dcdfe6;
  border-radius: 8px;
  background: #fafafa;
  transition: all 0.2s;
}

.ref-image-upload.file-upload-mode :deep(.el-upload-dragger:hover) {
  border-color: #409eff;
  background: #ecf5ff;
}

.ref-image-upload.file-upload-mode :deep(.el-upload-list) {
  margin-top: 10px;
}

.ref-image-upload.file-upload-mode :deep(.el-upload-list__item) {
  border-radius: 6px;
  border: 1px solid #e4e7ed;
  background: #f5f7fa;
}

.ref-image-upload.file-upload-mode.hide-upload-trigger :deep(.el-upload) {
  display: none !important;
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

.result-actions {
  display: flex;
  gap: 8px;
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

/* 模型选择器样式 */
.model-select-trigger {
  width: 100%;
}

.selected-model-preview {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  background: #fafafa;
}

.selected-model-preview:hover {
  border-color: #409eff;
  background: #ecf5ff;
}

.preview-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 4px;
}

.preview-placeholder {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #e4e7ed;
  border-radius: 4px;
  color: #909399;
}

.preview-info {
  flex: 1;
  min-width: 0;
}

.preview-type {
  font-size: 13px;
  font-weight: 500;
  color: #303133;
}

.preview-id {
  font-size: 11px;
  color: #909399;
  font-family: monospace;
}
</style>

