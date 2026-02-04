<template>
  <div class="graph-viewer">
    <!-- 搜索和控制区 -->
    <el-card shadow="never" :body-style="{ padding: '16px' }" class="search-card">
      <el-row :gutter="20">
        <el-col :span="18">
          <el-input
            v-model="searchQuery"
            placeholder="输入搜索关键词，如：什么是 MemGraph"
            @keyup.enter="handleSearch"
            clearable
          >
            <template #prepend>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-button type="primary" @click="handleSearch" :loading="searching" style="width: 100%;">
            搜索节点
          </el-button>
        </el-col>
      </el-row>

      <el-row :gutter="10" style="margin-top: 15px;">
        <el-col :span="8">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 13px;">初始节点数:</span>
            <el-input-number v-model="options.initialNodes" :min="1" :max="10" size="small" />
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 图谱和详情区 -->
    <el-row :gutter="0" class="content-row">
      <!-- 图谱画布 -->
      <el-col :span="16" class="graph-col">
        <el-card shadow="never" :body-style="{ padding: '0' }" class="graph-card">
          <div ref="networkContainer" class="network-container"></div>

          <!-- 控制按钮 -->
          <div class="canvas-controls">
            <el-button-group>
              <el-button @click="resetZoom" circle>
                <el-icon><Refresh /></el-icon>
              </el-button>
              <el-button @click="zoomIn" circle>
                <el-icon><ZoomIn /></el-icon>
              </el-button>
              <el-button @click="zoomOut" circle>
                <el-icon><ZoomOut /></el-icon>
              </el-button>
            </el-button-group>
          </div>

          <!-- 图例 -->
          <div class="legend">
            <div class="legend-title">图例</div>
            <div class="legend-item">
              <div class="legend-color" style="background: #667eea;"></div>
              <span>主节点（Layer 0）</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #48bb78;"></div>
              <span>一级关联（Layer 1）</span>
            </div>
            <div class="legend-item">
              <div class="legend-color" style="background: #ed8936;"></div>
              <span>二级关联（Layer 2）</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 节点详情 -->
      <el-col :span="8" class="detail-col">
        <el-card shadow="never" :body-style="{ padding: '16px' }" class="detail-card">
          <template #header>
            <div style="font-weight: 600;">节点详情</div>
          </template>

          <div v-if="selectedNode">
            <!-- 节点信息 -->
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="标题">
                {{ selectedNode.problem || '无标题' }}
              </el-descriptions-item>
              <el-descriptions-item label="文档ID">
                {{ selectedNode.doc_id }}
              </el-descriptions-item>
              <el-descriptions-item label="层级">
                Layer {{ selectedNode.layer }}
              </el-descriptions-item>
              <el-descriptions-item label="相似度" v-if="selectedNode.similarity_score">
                {{ (selectedNode.similarity_score * 100).toFixed(1) }}%
              </el-descriptions-item>
            </el-descriptions>

            <!-- 内容 -->
            <el-divider content-position="left">内容</el-divider>
            <div class="node-content" style="white-space: pre-wrap;">{{ selectedNode.solution || '无内容' }}</div>

            <!-- 标签 -->
            <el-divider content-position="left">标签</el-divider>
            <el-tag v-for="tag in selectedNode.tags" :key="tag" size="small" style="margin-right: 5px;">
              {{ tag }}
            </el-tag>
            <span v-if="!selectedNode.tags || selectedNode.tags.length === 0" style="color: #999;">无标签</span>

            <!-- 展开设置 -->
            <el-divider content-position="left">展开设置</el-divider>
            <div style="padding: 0 10px;">
              <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 10px;">
                <span style="font-size: 13px;">最小相似度:</span>
                <el-slider v-model="expandSimilarity" :min="0" :max="100" :step="5" style="flex: 1;" />
                <span style="font-weight: 600; color: #667eea; min-width: 45px;">{{ expandSimilarity }}%</span>
              </div>
            </div>

            <!-- 操作按钮 -->
            <div class="action-buttons">
              <el-button type="primary" @click="expandNode">
                <el-icon><Connection /></el-icon>
                展开关联节点
              </el-button>
              <el-button type="danger" @click="deleteNode">
                <el-icon><Delete /></el-icon>
                删除此节点
              </el-button>
            </div>
          </div>

          <el-empty v-else description="点击节点查看详细信息" :image-size="100" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 关联详情对话框 -->
    <el-dialog
      v-model="relationsDialogVisible"
      title="关联节点详情"
      width="70%"
      :close-on-click-modal="false"
    >
      <div v-if="nodeRelations">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 20px;">
          <el-descriptions-item label="源节点">
            {{ nodeRelations.sourceNode?.problem || 'N/A' }}
          </el-descriptions-item>
          <el-descriptions-item label="关联节点数">
            {{ nodeRelations.relatedCount }}
          </el-descriptions-item>
          <el-descriptions-item label="总匹配数">
            {{ nodeRelations.totalMatches }}
          </el-descriptions-item>
          <el-descriptions-item label="平均匹配">
            {{ nodeRelations.avgMatches }} 个/节点
          </el-descriptions-item>
        </el-descriptions>

        <el-collapse v-model="activeRelations">
          <el-collapse-item
            v-for="(relation, index) in nodeRelations.relations"
            :key="index"
            :name="index"
          >
            <template #title>
              <div style="width: 100%; display: flex; justify-content: space-between; align-items: center; padding-right: 20px;">
                <span>{{ relation.problem || `文档 ${relation.doc_id}` }}</span>
                <el-tag size="small">{{ relation.matchCount }} 个匹配</el-tag>
              </div>
            </template>
            <div v-for="(match, mIndex) in relation.matches" :key="mIndex" style="margin-bottom: 15px; padding: 12px; background: #f8f9fa; border-radius: 6px;">
              <div style="margin-bottom: 8px;">
                <el-tag type="info" size="small">匹配 #{{ mIndex + 1 }}</el-tag>
                <el-tag type="success" size="small" style="margin-left: 10px;">
                  相似度: {{ (match.similarity * 100).toFixed(1) }}%
                </el-tag>
              </div>
              <div style="font-size: 12px; color: #666; margin-bottom: 5px;">
                📄 {{ nodeRelations.sourceNode?.problem || 'N/A' }} [{{ match.vec1_granularity }}]
              </div>
              <div style="padding: 8px; background: white; border-radius: 4px; margin-bottom: 10px; font-size: 13px;">
                {{ match.vec1_content || '(无内容)' }}
              </div>
              <div style="text-align: center; margin: 8px 0; color: #999;">⬍</div>
              <div style="font-size: 12px; color: #666; margin-bottom: 5px;">
                📄 {{ relation.problem || 'N/A' }} [{{ match.vec2_granularity }}]
              </div>
              <div style="padding: 8px; background: white; border-radius: 4px; font-size: 13px;">
                {{ match.vec2_content || '(无内容)' }}
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
    </el-dialog>

    <!-- 边详情对话框 -->
    <el-dialog
      v-model="edgeDialogVisible"
      title="向量匹配详情"
      width="70%"
      :close-on-click-modal="false"
    >
      <div v-if="edgeDetails">
        <el-descriptions :column="2" border size="small" style="margin-bottom: 20px;">
          <el-descriptions-item label="节点1">
            {{ edgeDetails.node1?.problem || `文档 ${edgeDetails.fromId}` }}
          </el-descriptions-item>
          <el-descriptions-item label="节点2">
            {{ edgeDetails.node2?.problem || `文档 ${edgeDetails.toId}` }}
          </el-descriptions-item>
          <el-descriptions-item label="总匹配数">
            {{ edgeDetails.matches.length }}
          </el-descriptions-item>
          <el-descriptions-item label="平均相似度">
            {{ edgeDetails.avgSimilarity }}%
          </el-descriptions-item>
        </el-descriptions>

        <div v-for="(match, index) in edgeDetails.matches" :key="index" style="margin-bottom: 15px; padding: 12px; background: #f8f9fa; border-radius: 6px; border-left: 3px solid #667eea;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <el-tag type="primary" size="small">匹配 #{{ index + 1 }}</el-tag>
            <el-tag type="success" size="small">
              相似度: {{ (match.similarity * 100).toFixed(1) }}%
            </el-tag>
          </div>

          <div style="margin-bottom: 10px;">
            <div style="font-size: 11px; color: #667eea; font-weight: 600; margin-bottom: 4px;">
              📄 {{ match.doc1_title || edgeDetails.node1?.title || edgeDetails.node1?.label || `文档 ${edgeDetails.fromId}` }} [{{ match.vec1_granularity || 'N/A' }}]
            </div>
            <div style="font-size: 13px; color: #333; line-height: 1.5; padding: 6px; background: white; border-radius: 4px;">
              {{ match.vec1_content || '(无内容)' }}
            </div>
          </div>

          <div style="text-align: center; margin: 8px 0; color: #999;">⬍</div>

          <div>
            <div style="font-size: 11px; color: #48bb78; font-weight: 600; margin-bottom: 4px;">
              📄 {{ match.doc2_title || edgeDetails.node2?.title || edgeDetails.node2?.label || `文档 ${edgeDetails.toId}` }} [{{ match.vec2_granularity || 'N/A' }}]
            </div>
            <div style="font-size: 13px; color: #333; line-height: 1.5; padding: 6px; background: white; border-radius: 4px;">
              {{ match.vec2_content || '(无内容)' }}
            </div>
          </div>
        </div>

        <el-empty v-if="edgeDetails.matches.length === 0" description="未找到匹配的向量对" :image-size="100" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { Search, Refresh, ZoomIn, ZoomOut, Connection, View, Delete } from '@element-plus/icons-vue';
import { Network } from 'vis-network/standalone';
import axios from 'axios';

const API_BASE = 'http://localhost:8848';

// 数据
const searchQuery = ref('');
const searching = ref(false);
const options = ref({
  initialNodes: 5
});
const expandSimilarity = ref(70);
const selectedNode = ref(null);
const relationsDialogVisible = ref(false);
const nodeRelations = ref(null);
const activeRelations = ref([]);
const edgeDialogVisible = ref(false);
const edgeDetails = ref(null);

// 网络图
const networkContainer = ref(null);
let network = null;
let nodesDataSet = null;
let edgesDataSet = null;

// 初始化网络图
onMounted(async () => {
  await nextTick();
  initNetwork();
});

onUnmounted(() => {
  if (network) {
    network.destroy();
  }
});

function initNetwork() {
  // 动态导入 vis-network 的数据集
  import('vis-network/standalone').then((vis) => {
    const { DataSet } = vis;

    nodesDataSet = new DataSet([]);
    edgesDataSet = new DataSet([]);

    const data = {
      nodes: nodesDataSet,
      edges: edgesDataSet
    };

    const networkOptions = {
      nodes: {
        shape: 'dot',
        size: 20,
        font: {
          size: 14,
          color: '#333'
        },
        borderWidth: 2,
        shadow: true
      },
      edges: {
        width: 2,
        color: { inherit: 'both' },
        smooth: {
          type: 'continuous',
          roundness: 0.5
        },
        arrows: {
          to: {
            enabled: false
          }
        }
      },
      physics: {
        enabled: true,
        stabilization: {
          iterations: 200
        },
        barnesHut: {
          gravitationalConstant: -8000,
          springConstant: 0.04,
          springLength: 150
        }
      },
      interaction: {
        hover: true,
        tooltipDelay: 200,
        zoomView: true,
        dragView: true
      }
    };

    network = new Network(networkContainer.value, data, networkOptions);

    // 事件监听
    network.on('click', (params) => {
      if (params.nodes.length > 0) {
        // 点击节点
        handleNodeClick(params.nodes[0]);
      } else if (params.edges.length > 0) {
        // 点击边
        handleEdgeClick(params.edges[0]);
      }
    });

    network.on('doubleClick', (params) => {
      if (params.nodes.length > 0) {
        expandNodeFromClick(params.nodes[0]);
      }
    });
  });
}

// 搜索节点
async function handleSearch() {
  if (!searchQuery.value.trim()) {
    ElMessage.warning('请输入搜索关键词');
    return;
  }

  searching.value = true;
  try {
    const response = await fetch(`${API_BASE}/graph/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: searchQuery.value,
        initial_k: options.value.initialNodes
      })
    });

    const data = await response.json();

    if (data.success) {
      // 清空现有图谱
      nodesDataSet.clear();
      edgesDataSet.clear();

      // 后端返回格式: { success, query, layers: { layer0: [...], layer1: [...], ... } }
      // 需要转换为节点和边
      const allNodes = [];
      const allEdges = [];

      if (data.layers) {
        // 遍历每一层
        for (const [layerKey, layerNodes] of Object.entries(data.layers)) {
          const layerNum = parseInt(layerKey.replace('layer', ''));

          layerNodes.forEach(node => {
            allNodes.push({
              id: node.doc_id,
              label: (node.problem || `Doc ${node.doc_id}`).substring(0, 30) + (node.problem?.length > 30 ? '...' : ''),
              title: node.problem || `Document ${node.doc_id}`,
              color: getNodeColor(layerNum),
              layer: layerNum,
              ...node
            });

            // 如果有父节点ID，创建边
            if (node.parent_doc_id) {
              allEdges.push({
                id: `${node.parent_doc_id}-${node.doc_id}`,
                from: node.parent_doc_id,
                to: node.doc_id
              });
            }
          });
        }
      }

      if (allNodes.length > 0) {
        nodesDataSet.add(allNodes);

        if (allEdges.length > 0) {
          edgesDataSet.add(allEdges);
        }

        ElMessage.success(`找到 ${allNodes.length} 个节点`);

        // 适应视图
        setTimeout(() => {
          network.fit({ animation: true });
        }, 300);
      } else {
        ElMessage.warning('没有找到相关节点');
      }
    } else {
      ElMessage.error(data.error || data.message || '搜索失败');
    }
  } catch (error) {
    console.error('搜索失败:', error);
    ElMessage.error('搜索失败: ' + error.message);
  } finally {
    searching.value = false;
  }
}

// 节点点击
function handleNodeClick(nodeId) {
  const node = nodesDataSet.get(nodeId);
  if (node) {
    // 先恢复之前选中节点的样式
    if (selectedNode.value && selectedNode.value.id !== nodeId) {
      const prevNode = nodesDataSet.get(selectedNode.value.id);
      if (prevNode) {
        nodesDataSet.update({
          id: selectedNode.value.id,
          borderWidth: 2,
          color: getNodeColor(prevNode.layer)
        });
      }
    }

    selectedNode.value = node;

    // 高亮选中节点（保持原有颜色，只加粗边框）
    nodesDataSet.update({
      id: nodeId,
      borderWidth: 4,
      color: {
        ...getNodeColor(node.layer),
        border: '#ff6b6b'
      }
    });
  }
}

// 边点击 - 查看向量匹配详情
async function handleEdgeClick(edgeId) {
  const edge = edgesDataSet.get(edgeId);
  if (!edge) return;

  const fromId = edge.from;
  const toId = edge.to;

  const node1 = nodesDataSet.get(fromId);
  const node2 = nodesDataSet.get(toId);

  try {
    // 调用后端 API 获取边的详细匹配信息
    const response = await fetch(`${API_BASE}/graph/edge-details`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doc_id1: fromId,
        doc_id2: toId,
        top_k: 20
      })
    });
    const data = await response.json();

    if (data.success && data.matches) {
      // 计算平均相似度
      const avgSim = data.matches.length > 0
        ? data.matches.reduce((sum, m) => sum + m.similarity, 0) / data.matches.length
        : 0;

      edgeDetails.value = {
        fromId,
        toId,
        node1,
        node2,
        matches: data.matches,
        avgSimilarity: (avgSim * 100).toFixed(1)
      };

      edgeDialogVisible.value = true;
    } else {
      ElMessage.warning('未找到匹配信息');
    }
  } catch (error) {
    console.error('获取边详情失败:', error);
    ElMessage.error('获取边详情失败');
  }
}

// 双击扩展节点
async function expandNodeFromClick(nodeId) {
  await expandNodeById(nodeId);
}

// 扩展节点
async function expandNode() {
  if (!selectedNode.value) {
    ElMessage.warning('请先选择一个节点');
    return;
  }

  await expandNodeById(selectedNode.value.doc_id);
}

async function expandNodeById(docId) {
  try {
    const minSimilarity = expandSimilarity.value / 100;

    const response = await fetch(`${API_BASE}/graph/expand`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        doc_id: docId,
        top_k: 5,
        min_similarity: minSimilarity
      })
    });

    const data = await response.json();

    if (data.success && data.related_nodes.length > 0) {
      // 添加新节点
      const parentLayer = nodesDataSet.get(docId).layer || 0;
      const newLayer = parentLayer + 1;

      const newNodes = data.related_nodes.map(node => ({
        id: node.doc_id,
        label: (node.problem || `Doc ${node.doc_id}`).substring(0, 30) + (node.problem?.length > 30 ? '...' : ''),
        title: node.problem || `Document ${node.doc_id}`,
        color: getNodeColor(newLayer),
        layer: newLayer,
        ...node
      })).filter(node => !nodesDataSet.get(node.id)); // 过滤已存在的节点

      if (newNodes.length > 0) {
        nodesDataSet.add(newNodes);

        // 添加边
        const newEdges = newNodes.map(node => ({
          id: `${docId}-${node.id}`,
          from: docId,
          to: node.id
        }));

        edgesDataSet.add(newEdges);

        ElMessage.success(`展开了 ${newNodes.length} 个关联节点`);
      } else {
        ElMessage.info('没有新的关联节点');
      }
    } else {
      ElMessage.info('没有找到关联节点');
    }
  } catch (error) {
    console.error('展开节点失败:', error);
    ElMessage.error('展开节点失败');
  }
}

// 查看关联详情
async function showRelations() {
  if (!selectedNode.value) {
    ElMessage.warning('请先选择一个节点');
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/graph/relations/${selectedNode.value.doc_id}?top_k_per_vector=5&min_similarity=0.1`);
    const data = await response.json();

    if (data.success) {
      const relations = [];
      let totalMatches = 0;

      for (const [docId, matches] of Object.entries(data.relations)) {
        const relatedNode = nodesDataSet.get(parseInt(docId));
        if (relatedNode || matches.length > 0) {
          relations.push({
            doc_id: parseInt(docId),
            problem: relatedNode?.problem || `文档 ${docId}`,
            matchCount: matches.length,
            matches: matches
          });
          totalMatches += matches.length;
        }
      }

      relations.sort((a, b) => b.matchCount - a.matchCount);

      nodeRelations.value = {
        sourceNode: selectedNode.value,
        relatedCount: relations.length,
        totalMatches: totalMatches,
        avgMatches: relations.length > 0 ? (totalMatches / relations.length).toFixed(1) : 0,
        relations: relations
      };

      relationsDialogVisible.value = true;
      activeRelations.value = [0]; // 默认展开第一个
    }
  } catch (error) {
    console.error('获取关联详情失败:', error);
    ElMessage.error('获取关联详情失败');
  }
}

// 删除节点
async function deleteNode() {
  if (!selectedNode.value) {
    ElMessage.warning('请先选择一个节点');
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除节点吗？\n\n节点: ${selectedNode.value.problem || `文档 ${selectedNode.value.doc_id}`}\nID: ${selectedNode.value.doc_id}\n\n此操作将：\n• 删除物理文件\n• 删除数据库记录\n• 删除所有向量数据\n• 从图谱中移除节点\n\n此操作不可撤销！`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    const response = await fetch(`${API_BASE}/document/${selectedNode.value.doc_id}`, {
      method: 'DELETE'
    });

    const data = await response.json();

    if (data.success) {
      // 从图谱中移除节点
      nodesDataSet.remove(selectedNode.value.doc_id);

      // 移除相关边
      const connectedEdges = edgesDataSet.get({
        filter: edge => edge.from === selectedNode.value.doc_id || edge.to === selectedNode.value.doc_id
      });
      edgesDataSet.remove(connectedEdges.map(e => e.id));

      ElMessage.success(`删除成功 (向量:${data.stats.vectors}, n-grams:${data.stats.ngrams})`);
      selectedNode.value = null;
    } else {
      ElMessage.error('删除失败');
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除节点失败:', error);
      ElMessage.error('删除节点失败');
    }
  }
}

// 工具函数
function getNodeColor(layer) {
  const colors = {
    0: { background: '#667eea', border: '#667eea' },
    1: { background: '#48bb78', border: '#48bb78' },
    2: { background: '#ed8936', border: '#ed8936' }
  };
  return colors[layer] || { background: '#999', border: '#999' };
}

function resetZoom() {
  network.fit({ animation: true });
}

function zoomIn() {
  const scale = network.getScale();
  network.moveTo({ scale: scale * 1.2, animation: true });
}

function zoomOut() {
  const scale = network.getScale();
  network.moveTo({ scale: scale * 0.8, animation: true });
}
</script>

<style scoped>
.graph-viewer {
  padding: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.search-card {
  border-radius: 0;
  border-bottom: 1px solid #dcdfe6;
  flex-shrink: 0;
}

.content-row {
  flex: 1;
  margin: 0 !important;
  min-height: 0;
  display: flex !important;
  height: 100%;
}

.graph-col,
.detail-col {
  padding: 0 !important;
  height: 100%;
  display: flex !important;
  flex-direction: column;
}

.graph-card,
.detail-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  border-radius: 0;
}

.graph-card {
  position: relative;
  border-right: 1px solid #dcdfe6;
}

.graph-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  position: relative;
}

.detail-card {
  overflow: hidden;
  border-left: none;
}

.detail-card :deep(.el-card__header) {
  padding: 16px;
  border-bottom: 1px solid #dcdfe6;
  flex-shrink: 0;
}

.detail-card :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.network-container {
  width: 100%;
  height: 100%;
  border: none;
  border-radius: 0;
}

.canvas-controls {
  position: absolute;
  top: 20px;
  right: 20px;
  z-index: 10;
}

.legend {
  position: absolute;
  bottom: 20px;
  left: 20px;
  background: white;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  font-size: 12px;
  z-index: 10;
}

.legend-title {
  font-weight: 600;
  margin-bottom: 10px;
  color: #333;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.legend-item:last-child {
  margin-bottom: 0;
}

.legend-color {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid white;
  box-shadow: 0 0 0 1px #ddd;
}

.node-content {
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
}

.action-buttons {
  margin-top: 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.action-buttons .el-button {
  width: 100%;
  margin: 0 !important;
}
</style>
