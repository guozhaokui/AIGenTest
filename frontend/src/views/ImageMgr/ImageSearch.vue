<template>
  <div class="image-search">
    <!-- 搜索方式切换 -->
    <el-radio-group v-model="searchMode" class="search-mode">
      <el-radio-button value="text">文本搜索</el-radio-button>
      <el-radio-button value="image">以图搜图</el-radio-button>
      <el-radio-button value="similar">相似图片</el-radio-button>
    </el-radio-group>

    <!-- 相似图片搜索 -->
    <div v-if="searchMode === 'similar'" class="similar-input">
      <div class="similar-source" v-if="similarSource">
        <img :src="getThumbnailUrl(similarSource)" class="source-thumb" />
        <div class="source-info">
          <div class="source-label">搜索与此图片相似的图片</div>
          <code class="source-sha">{{ similarSource }}</code>
        </div>
        <el-button @click="clearSimilar">清除</el-button>
      </div>
      <div v-else class="no-source">
        <el-empty description="请从图片详情页点击【搜索相似图片】按钮" />
      </div>
    </div>

    <!-- 文本搜索 -->
    <div v-if="searchMode === 'text'" class="search-input">
      <div class="search-row">
        <el-input
          v-model="textQuery"
          placeholder="输入搜索内容，如：一只猫在晒太阳"
          size="large"
          @keyup.enter="handleTextSearch"
        >
          <template #append>
            <el-button type="primary" @click="handleTextSearch" :loading="searching">
              搜索
            </el-button>
          </template>
        </el-input>
      </div>
      <div class="search-options">
        <span class="option-label">嵌入模型：</span>
        <el-select v-model="selectedIndex" placeholder="选择嵌入模型" style="width: 200px;">
          <el-option label="全部模型" value="" />
          <el-option 
            v-for="idx in textIndexes" 
            :key="idx.id" 
            :label="idx.name" 
            :value="idx.id"
          />
        </el-select>
        <span class="option-tip">选择特定模型可能获得更准确的结果</span>
      </div>
    </div>

    <!-- 以图搜图 -->
    <div v-if="searchMode === 'image'" class="image-input">
      <el-upload
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :on-change="onFileChange"
        :show-file-list="false"
        accept="image/*"
      >
        <div v-if="!previewUrl" class="upload-placeholder">
          <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
          <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
        </div>
        <img v-else :src="previewUrl" class="preview-image" />
      </el-upload>
      <div class="image-actions" v-if="queryFile">
        <el-button type="primary" @click="handleImageSearch" :loading="searching">搜索相似图片</el-button>
        <el-button @click="clearImage">清除</el-button>
      </div>
    </div>

    <!-- 搜索结果 -->
    <div class="search-results" v-if="results.length > 0">
      <h3>搜索结果 ({{ results.length }} 张)</h3>
      <div class="result-grid">
        <div 
          v-for="(item, idx) in results" 
          :key="item.sha256"
          class="result-card"
          @click="showDetail(item)"
        >
          <div class="rank">{{ idx + 1 }}</div>
          <div class="result-thumb">
            <img :src="getThumbnailUrl(item.sha256)" />
          </div>
          <div class="result-info">
            <div class="score">
              相似度: <strong>{{ (item.score * 100).toFixed(1) }}%</strong>
            </div>
            <div class="matched" v-if="item.matched_by">
              匹配: {{ item.matched_by }}
            </div>
            <div class="matched-text" v-if="item.matched_text">
              "{{ truncate(item.matched_text, 50) }}"
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 无结果 -->
    <div v-else-if="searched && !searching" class="no-results">
      <el-empty description="未找到匹配的图片" />
    </div>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="图片详情" width="600px">
      <div class="detail-content" v-if="selectedImage">
        <img :src="getImageUrl(selectedImage.sha256)" class="detail-image" />
        <el-descriptions :column="2" border style="margin-top: 16px;">
          <el-descriptions-item label="SHA256" :span="2">
            <code>{{ selectedImage.sha256 }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="相似度">
            {{ (selectedImage.score * 100).toFixed(1) }}%
          </el-descriptions-item>
          <el-descriptions-item label="匹配方式">
            {{ selectedImage.matched_by }}
          </el-descriptions-item>
          <el-descriptions-item label="尺寸">
            {{ selectedImage.width }} × {{ selectedImage.height }}
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="selectedImage.matched_text" class="matched-text-full">
          <strong>匹配文本:</strong> {{ selectedImage.matched_text }}
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import { ElMessage } from 'element-plus';
import { UploadFilled } from '@element-plus/icons-vue';
import { 
  searchByText, 
  searchByImage, 
  searchSimilar,
  getTextIndexes,
  getThumbnailUrl, 
  getImageUrl 
} from '@/services/imagemgr';

const route = useRoute();

const searchMode = ref('text');
const textQuery = ref('');
const queryFile = ref(null);
const previewUrl = ref('');
const searching = ref(false);
const searched = ref(false);
const results = ref([]);

// 文本搜索选项
const textIndexes = ref([]);
const selectedIndex = ref('');

// 相似图片搜索
const similarSource = ref('');

// 详情
const detailVisible = ref(false);
const selectedImage = ref(null);

// 加载文本索引列表
async function loadTextIndexes() {
  try {
    const data = await getTextIndexes();
    textIndexes.value = data.indexes || [];
  } catch (e) {
    console.error('加载索引列表失败:', e);
  }
}

// 处理路由参数（从图片详情页跳转过来）
function handleRouteQuery() {
  const similar = route.query.similar;
  if (similar) {
    similarSource.value = similar;
    searchMode.value = 'similar';
    // 自动执行搜索
    handleSimilarSearch();
  }
}

// 监听路由变化
watch(() => route.query.similar, (newVal) => {
  if (newVal) {
    similarSource.value = newVal;
    searchMode.value = 'similar';
    handleSimilarSearch();
  }
});

onMounted(() => {
  loadTextIndexes();
  handleRouteQuery();
});

function truncate(text, len) {
  if (!text) return '';
  return text.length > len ? text.slice(0, len) + '...' : text;
}

function onFileChange(uploadFile) {
  const file = uploadFile.raw;
  if (!file) return;
  
  queryFile.value = file;
  previewUrl.value = URL.createObjectURL(file);
}

function clearImage() {
  queryFile.value = null;
  previewUrl.value = '';
  results.value = [];
  searched.value = false;
}

async function handleTextSearch() {
  if (!textQuery.value.trim()) {
    return ElMessage.warning('请输入搜索内容');
  }
  
  searching.value = true;
  searched.value = true;
  try {
    const data = await searchByText(textQuery.value.trim(), 100, selectedIndex.value || null);
    results.value = data.results || [];
    if (results.value.length === 0) {
      ElMessage.info('未找到匹配的图片');
    }
  } catch (e) {
    ElMessage.error('搜索失败');
    console.error(e);
  } finally {
    searching.value = false;
  }
}

async function handleImageSearch() {
  if (!queryFile.value) {
    return ElMessage.warning('请先上传图片');
  }
  
  searching.value = true;
  searched.value = true;
  try {
    const data = await searchByImage(queryFile.value, 100);
    results.value = data.results || [];
    if (results.value.length === 0) {
      ElMessage.info('未找到相似的图片');
    }
  } catch (e) {
    ElMessage.error('搜索失败');
    console.error(e);
  } finally {
    searching.value = false;
  }
}

async function handleSimilarSearch() {
  if (!similarSource.value) {
    return ElMessage.warning('请先选择一张图片');
  }
  
  searching.value = true;
  searched.value = true;
  try {
    const data = await searchSimilar(similarSource.value, 100);
    results.value = data.results || [];
    if (results.value.length === 0) {
      ElMessage.info('未找到相似的图片');
    }
  } catch (e) {
    ElMessage.error('搜索失败: ' + (e.response?.data?.detail || e.message));
    console.error(e);
  } finally {
    searching.value = false;
  }
}

function clearSimilar() {
  similarSource.value = '';
  results.value = [];
  searched.value = false;
}

function showDetail(item) {
  selectedImage.value = item;
  detailVisible.value = true;
}
</script>

<style scoped>
.image-search {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.search-mode {
  margin-bottom: 24px;
}

.search-input {
  max-width: 700px;
}

.search-row {
  margin-bottom: 12px;
}

.search-options {
  display: flex;
  align-items: center;
  gap: 12px;
}

.option-label {
  color: #606266;
  font-size: 14px;
}

.option-tip {
  color: #909399;
  font-size: 12px;
}

.image-input {
  max-width: 400px;
}

.similar-input {
  max-width: 600px;
}

.similar-source {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.source-thumb {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.source-info {
  flex: 1;
}

.source-label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 8px;
}

.source-sha {
  font-size: 12px;
  color: #909399;
  word-break: break-all;
}

.no-source {
  padding: 40px 0;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 250px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.upload-placeholder {
  text-align: center;
  color: #909399;
}

.preview-image {
  max-width: 100%;
  max-height: 230px;
  object-fit: contain;
}

.image-actions {
  margin-top: 16px;
  display: flex;
  gap: 12px;
}

.search-results {
  margin-top: 32px;
}

.search-results h3 {
  margin: 0 0 16px 0;
  color: #303133;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px;
}

.result-card {
  position: relative;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  cursor: pointer;
  transition: transform 0.2s;
}

.result-card:hover {
  transform: translateY(-4px);
}

.rank {
  position: absolute;
  top: 8px;
  left: 8px;
  width: 28px;
  height: 28px;
  background: #409eff;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  font-size: 14px;
  z-index: 1;
}

.result-thumb {
  width: 100%;
  aspect-ratio: 1;
  background: #f5f7fa;
}

.result-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-info {
  padding: 12px;
}

.result-info .score {
  color: #303133;
}

.result-info .score strong {
  color: #409eff;
}

.result-info .matched {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.result-info .matched-text {
  font-size: 12px;
  color: #606266;
  margin-top: 4px;
  font-style: italic;
}

.no-results {
  margin-top: 48px;
}

/* 详情 */
.detail-image {
  width: 100%;
  max-height: 400px;
  object-fit: contain;
  border-radius: 8px;
}

.matched-text-full {
  margin-top: 16px;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}
</style>

