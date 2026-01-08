<template>
  <div class="document-management">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>文档管理</span>
          <el-button type="primary" @click="handleScan" :loading="scanning">
            <el-icon><Folder /></el-icon>
            扫描目录
          </el-button>
        </div>
      </template>

      <!-- 目录路径配置 -->
      <div class="path-config">
        <el-input
          v-model="docsPath"
          placeholder="文档目录路径"
          style="width: 500px"
        >
          <template #prepend>文档路径</template>
        </el-input>
      </div>
    </el-card>

    <!-- 文档列表 -->
    <el-card style="margin-top: 20px" v-if="files.length > 0">
      <template #header>
        <div class="card-header">
          <span>文档列表（共 {{ files.length }} 个文件）</span>
          <div>
            <el-button
              type="success"
              @click="handleIndexSelected"
              :disabled="selectedFiles.length === 0"
              :loading="indexing"
            >
              <el-icon><Upload /></el-icon>
              索引选中（{{ selectedFiles.length }}）
            </el-button>
            <el-button
              type="danger"
              @click="handleClearAll"
              :loading="clearing"
            >
              <el-icon><Delete /></el-icon>
              清空知识库
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="files"
        @selection-change="handleSelectionChange"
        style="width: 100%"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="name" label="文件名" min-width="200">
          <template #default="scope">
            <el-tooltip :content="scope.row.path" placement="top">
              <span>{{ scope.row.name }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="size" label="大小" width="120">
          <template #default="scope">
            {{ formatSize(scope.row.size) }}
          </template>
        </el-table-column>
        <el-table-column prop="length" label="字数" width="120" />
        <el-table-column prop="modified" label="修改时间" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.modified) }}
          </template>
        </el-table-column>
        <el-table-column prop="indexed" label="状态" width="100">
          <template #default="scope">
            <el-tag v-if="scope.row.indexed" type="success" size="small">
              已索引
            </el-tag>
            <el-tag v-else type="info" size="small">未索引</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button
              v-if="!scope.row.indexed"
              size="small"
              type="primary"
              @click="handleIndexSingle(scope.row)"
            >
              索引
            </el-button>
            <el-button
              v-else
              size="small"
              type="warning"
              @click="handleReindex(scope.row)"
            >
              重新索引
            </el-button>
            <el-button
              v-if="scope.row.indexed"
              size="small"
              type="danger"
              @click="handleDelete(scope.row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 索引进度 -->
    <el-dialog v-model="showProgress" title="索引进度" width="500px" :close-on-click-modal="false">
      <div v-if="indexResults.length > 0">
        <el-timeline>
          <el-timeline-item
            v-for="result in indexResults"
            :key="result.file"
            :type="result.success ? 'success' : 'danger'"
            :timestamp="result.file"
          >
            <template v-if="result.success">
              成功索引，生成 {{ result.chunks }} 个文档块
            </template>
            <template v-else>
              索引失败: {{ result.error }}
            </template>
          </el-timeline-item>
        </el-timeline>
      </div>
      <div v-else style="text-align: center; padding: 20px;">
        <el-icon class="is-loading" :size="40"><Loading /></el-icon>
        <p style="margin-top: 10px;">正在索引文档...</p>
      </div>
      <template #footer>
        <el-button @click="showProgress = false" :disabled="indexing">
          关闭
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Folder, Upload, Delete, Loading } from '@element-plus/icons-vue';
import {
  scanDocuments,
  indexDocuments,
  deleteDocument,
  clearKnowledge
} from '@/services/api';

const docsPath = ref('/mnt/e/TEST/work/日志');
const scanning = ref(false);
const indexing = ref(false);
const clearing = ref(false);
const files = ref([]);
const selectedFiles = ref([]);
const showProgress = ref(false);
const indexResults = ref([]);

const handleScan = async () => {
  scanning.value = true;
  try {
    const result = await scanDocuments({ path: docsPath.value });
    if (result.success) {
      files.value = result.data.files;
      ElMessage.success(`扫描完成，找到 ${result.data.total} 个文档`);
    } else {
      ElMessage.error(result.error || '扫描失败');
    }
  } catch (error) {
    console.error('扫描失败:', error);
    ElMessage.error('扫描失败: ' + error.message);
  } finally {
    scanning.value = false;
  }
};

const handleSelectionChange = (selection) => {
  selectedFiles.value = selection;
};

const handleIndexSelected = async () => {
  if (selectedFiles.value.length === 0) {
    ElMessage.warning('请先选择要索引的文件');
    return;
  }

  indexing.value = true;
  showProgress.value = true;
  indexResults.value = [];

  try {
    const filePaths = selectedFiles.value.map(f => f.path);
    const result = await indexDocuments({ files: filePaths });

    if (result.success) {
      indexResults.value = result.data.results;

      // 更新文件状态
      selectedFiles.value.forEach(file => {
        file.indexed = true;
      });

      ElMessage.success(
        `索引完成：成功 ${result.data.success_count}/${result.data.total_files} 个文件，` +
        `共 ${result.data.total_chunks} 个文档块`
      );
    } else {
      ElMessage.error(result.error || '索引失败');
    }
  } catch (error) {
    console.error('索引失败:', error);
    ElMessage.error('索引失败: ' + error.message);
  } finally {
    indexing.value = false;
  }
};

const handleIndexSingle = async (file) => {
  selectedFiles.value = [file];
  await handleIndexSelected();
};

const handleReindex = async (file) => {
  try {
    await ElMessageBox.confirm(
      '重新索引会先删除该文件的旧索引，确定继续吗？',
      '确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    // 先删除
    await deleteDocument({ source: file.name });

    // 再索引
    file.indexed = false;
    await handleIndexSingle(file);
  } catch (error) {
    if (error !== 'cancel') {
      console.error('重新索引失败:', error);
      ElMessage.error('重新索引失败');
    }
  }
};

const handleDelete = async (file) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${file.name}" 的索引吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    const result = await deleteDocument({ source: file.name });
    if (result.success) {
      file.indexed = false;
      ElMessage.success(`删除成功，共删除 ${result.data.deleted_count} 个文档块`);
    } else {
      ElMessage.error(result.error || '删除失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除失败:', error);
      ElMessage.error('删除失败');
    }
  }
};

const handleClearAll = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要清空整个知识库吗？此操作不可恢复！',
      '警告',
      {
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    clearing.value = true;
    const result = await clearKnowledge();

    if (result.success) {
      // 更新所有文件状态
      files.value.forEach(file => {
        file.indexed = false;
      });
      ElMessage.success('知识库已清空');
    } else {
      ElMessage.error(result.error || '清空失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('清空失败:', error);
      ElMessage.error('清空失败');
    }
  } finally {
    clearing.value = false;
  }
};

const formatSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

const formatDate = (dateStr) => {
  const date = new Date(dateStr);
  return date.toLocaleString('zh-CN');
};

onMounted(() => {
  // 自动扫描
  handleScan();
});
</script>

<style scoped>
.document-management {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.path-config {
  margin-bottom: 20px;
}
</style>
