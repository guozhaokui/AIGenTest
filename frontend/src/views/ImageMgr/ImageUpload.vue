<template>
  <div class="image-upload">
    <h3>上传图片</h3>
    
    <!-- 上传区域 -->
    <div class="upload-section">
      <el-upload
        ref="uploadRef"
        class="upload-area"
        drag
        action="#"
        :auto-upload="false"
        :on-change="onFileChange"
        :file-list="fileList"
        :multiple="true"
        accept="image/*"
        list-type="picture-card"
      >
        <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
        <div class="el-upload__text">将图片拖到此处，或<em>点击上传</em></div>
        <template #tip>
          <div class="el-upload__tip">
            支持 PNG、JPEG、WebP 格式，单文件最大 50MB
          </div>
        </template>
      </el-upload>
    </div>

    <!-- 上传配置 -->
    <div class="upload-config" v-if="fileList.length > 0">
      <el-form :model="uploadConfig" inline>
        <el-form-item label="来源标记">
          <el-input 
            v-model="uploadConfig.source" 
            placeholder="如: manual, crawler"
            style="width: 200px;"
          />
        </el-form-item>
        <el-form-item label="初始描述">
          <el-input 
            v-model="uploadConfig.description" 
            placeholder="可选的描述文本"
            style="width: 300px;"
          />
        </el-form-item>
      </el-form>
    </div>

    <!-- 操作按钮 -->
    <div class="upload-actions" v-if="fileList.length > 0">
      <el-button type="primary" size="large" @click="startUpload" :loading="uploading">
        上传 {{ fileList.length }} 张图片
      </el-button>
      <el-button size="large" @click="clearAll">清空</el-button>
    </div>

    <!-- 上传进度 -->
    <div class="upload-progress" v-if="uploadResults.length > 0">
      <h4>上传结果</h4>
      <div class="result-list">
        <div 
          v-for="(result, idx) in uploadResults" 
          :key="idx"
          class="result-item"
          :class="result.status"
        >
          <div class="result-thumb">
            <img v-if="result.previewUrl" :src="result.previewUrl" />
          </div>
          <div class="result-info">
            <div class="filename">{{ result.filename }}</div>
            <div class="status-text">
              <el-icon v-if="result.status === 'uploading'" class="is-loading">
                <Loading />
              </el-icon>
              <el-icon v-else-if="result.status === 'success'" color="#67c23a">
                <Check />
              </el-icon>
              <el-icon v-else-if="result.status === 'error'" color="#f56c6c">
                <Close />
              </el-icon>
              <span>{{ result.message }}</span>
            </div>
            <div class="sha256" v-if="result.sha256">
              <code>{{ result.sha256.slice(0, 16) }}...</code>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue';
import { ElMessage } from 'element-plus';
import { UploadFilled, Loading, Check, Close } from '@element-plus/icons-vue';
import { uploadImage, addDescription } from '@/services/imagemgr';

const uploadRef = ref(null);
const fileList = ref([]);
const uploading = ref(false);
const uploadResults = ref([]);

const uploadConfig = reactive({
  source: '',
  description: ''
});

function onFileChange(uploadFile, uploadFiles) {
  fileList.value = uploadFiles;
}

function clearAll() {
  fileList.value = [];
  uploadResults.value = [];
  if (uploadRef.value) {
    uploadRef.value.clearFiles();
  }
}

async function startUpload() {
  if (fileList.value.length === 0) {
    return ElMessage.warning('请先选择图片');
  }

  uploading.value = true;
  uploadResults.value = [];

  // 初始化结果列表
  for (const fileItem of fileList.value) {
    uploadResults.value.push({
      filename: fileItem.name,
      previewUrl: fileItem.url || URL.createObjectURL(fileItem.raw),
      status: 'pending',
      message: '等待上传...',
      sha256: null
    });
  }

  // 逐个上传
  for (let i = 0; i < fileList.value.length; i++) {
    const fileItem = fileList.value[i];
    const result = uploadResults.value[i];
    
    result.status = 'uploading';
    result.message = '上传中...';

    try {
      const data = await uploadImage(fileItem.raw, uploadConfig.source || null);
      result.status = 'success';
      result.sha256 = data.sha256;
      
      if (data.is_duplicate) {
        result.message = '已存在（去重）';
      } else {
        result.message = '上传成功';
        
        // 如果有描述，添加描述
        if (uploadConfig.description.trim()) {
          try {
            await addDescription(data.sha256, 'human', uploadConfig.description.trim());
            result.message += '，已添加描述';
          } catch (e) {
            result.message += '，描述添加失败';
          }
        }
      }
    } catch (e) {
      result.status = 'error';
      result.message = e.response?.data?.detail || '上传失败';
      console.error('Upload error:', e);
    }
  }

  uploading.value = false;
  
  // 统计结果
  const successCount = uploadResults.value.filter(r => r.status === 'success').length;
  const errorCount = uploadResults.value.filter(r => r.status === 'error').length;
  
  if (errorCount === 0) {
    ElMessage.success(`全部上传成功 (${successCount} 张)`);
  } else if (successCount === 0) {
    ElMessage.error('全部上传失败');
  } else {
    ElMessage.warning(`成功 ${successCount} 张，失败 ${errorCount} 张`);
  }

  // 清空待上传列表
  fileList.value = [];
  if (uploadRef.value) {
    uploadRef.value.clearFiles();
  }
}
</script>

<style scoped>
.image-upload {
  padding: 24px;
  max-width: 900px;
  margin: 0 auto;
}

.image-upload h3 {
  margin: 0 0 24px 0;
  color: #303133;
}

.upload-section {
  margin-bottom: 24px;
}

.upload-area {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
}

.upload-config {
  background: #f5f7fa;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.upload-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 32px;
}

.upload-progress h4 {
  margin: 0 0 16px 0;
  color: #303133;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-item {
  display: flex;
  gap: 16px;
  padding: 12px;
  background: white;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.result-item.success {
  border-color: #67c23a;
  background: #f0f9eb;
}

.result-item.error {
  border-color: #f56c6c;
  background: #fef0f0;
}

.result-item.uploading {
  border-color: #409eff;
  background: #ecf5ff;
}

.result-thumb {
  width: 60px;
  height: 60px;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
  flex-shrink: 0;
}

.result-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.result-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.result-info .filename {
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
}

.result-info .status-text {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  color: #606266;
}

.result-info .sha256 {
  margin-top: 4px;
}

.result-info .sha256 code {
  font-size: 12px;
  color: #909399;
}
</style>

