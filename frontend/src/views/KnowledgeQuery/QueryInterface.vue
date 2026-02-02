<template>
  <div class="query-interface">
    <el-card shadow="never" class="header-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <span>智能对话</span>
          </div>
          <el-select
            v-model="selectedModel"
            placeholder="选择模型"
            style="width: 300px"
          >
            <el-option
              v-for="model in models"
              :key="model.id"
              :label="model.name"
              :value="model.id"
            >
              <span>{{ model.name }}</span>
              <el-tag v-if="model.recommended" size="small" type="success" style="margin-left: 8px">
                推荐
              </el-tag>
            </el-option>
          </el-select>
        </div>
      </template>

      <!-- 纯聊天模式 -->
      <div class="chat-mode">
        <!-- 聊天历史 -->
        <div class="chat-history" ref="chatHistory">
          <div v-if="chatMessages.length === 0" class="empty-chat">
            <el-empty description="开始聊天吧！" />
          </div>
          <div v-else>
            <div
              v-for="(msg, index) in chatMessages"
              :key="index"
              :class="['chat-message', msg.role]"
            >
              <div class="message-avatar">
                <el-icon v-if="msg.role === 'user'" :size="24"><User /></el-icon>
                <el-icon v-else :size="24"><Cpu /></el-icon>
              </div>
              <div class="message-content">
                <!-- 思考过程（仅AI消息且有思考内容时显示） -->
                <div v-if="msg.role === 'assistant' && msg.reasoning" class="thinking-section">
                  <div class="thinking-header" @click="toggleThinking(msg)">
                    <span class="thinking-icon" :class="{ expanded: msg.showThinking }">▶</span>
                    <span>思考过程</span>
                    <span v-if="chatting && index === chatMessages.length - 1" class="thinking-status">正在思考...</span>
                  </div>
                  <div v-show="msg.showThinking" class="thinking-content">
                    {{ msg.reasoning }}
                    <span v-if="chatting && index === chatMessages.length - 1" class="typing-cursor">▊</span>
                  </div>
                </div>

                <!-- 回答内容 -->
                <div class="message-text" :class="{ connecting: msg.isConnecting }">
                  {{ msg.content }}
                  <span v-if="msg.role === 'assistant' && chatting && index === chatMessages.length - 1 && !msg.reasoning && !msg.isConnecting" class="typing-cursor">▊</span>
                </div>
                <div class="message-time">{{ formatTime(msg.timestamp) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 聊天输入 -->
        <div class="chat-input">
          <el-input
            v-model="chatMessage"
            type="textarea"
            :rows="3"
            placeholder="输入消息... (Ctrl+Enter 发送)"
            @keydown.ctrl.enter="handleChat"
            :disabled="chatting"
          />
          <div class="chat-actions">
            <el-button
              type="primary"
              :loading="chatting"
              @click="handleChat"
              :disabled="!chatMessage.trim()"
            >
              <el-icon><Promotion /></el-icon>
              发送 (Ctrl+Enter)
            </el-button>
            <el-button @click="clearChat" :disabled="chatMessages.length === 0">
              清空对话
            </el-button>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue';
import { ElMessage } from 'element-plus';
import { User, Cpu, Promotion } from '@element-plus/icons-vue';
import { getKnowledgeModels } from '@/services/api';

// 纯聊天相关
const selectedModel = ref('deepseek-ai/deepseek-v3.2');
const chatMessage = ref('');
const chatMessages = ref([]);
const chatting = ref(false);
const chatHistory = ref(null);

// 模型列表
const models = ref([]);

// 纯聊天处理（流式）
const handleChat = async () => {
  if (!chatMessage.value.trim()) {
    ElMessage.warning('请输入消息');
    return;
  }

  const userMessage = chatMessage.value;

  // 添加用户消息到界面
  chatMessages.value.push({
    role: 'user',
    content: userMessage,
    timestamp: Date.now()
  });

  // 清空输入
  chatMessage.value = '';
  chatting.value = true;

  // 滚动到底部
  await nextTick();
  scrollToBottom();

  // 创建一个临时消息用于流式显示
  chatMessages.value.push({
    role: 'assistant',
    content: '正在连接 AI 服务...',
    reasoning: '',
    showThinking: true,
    timestamp: Date.now(),
    isConnecting: true
  });

  // 获取当前助手消息的索引
  const assistantIndex = chatMessages.value.length - 1;

  try {
    // 构建历史消息（只发送role和content）
    const history = chatMessages.value
      .filter(msg => msg.role && msg.content && !msg.isConnecting) // 排除连接中的消息
      .slice(0, -1) // 排除刚添加的用户消息
      .map(msg => ({
        role: msg.role,
        content: msg.content
      }));

    // 使用 fetch 进行流式请求
    const response = await fetch('http://localhost:5001/api/knowledge/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: userMessage,
        model: selectedModel.value,
        history: history
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    // 添加调试日志
    console.log('[Chat] 开始接收流式数据');

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      console.log(`[Chat] 收到数据块: ${value.length} bytes`);

      // 解码数据
      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;

      // 处理 SSE 消息（按行分割）
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 保留不完整的行

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.error) {
              ElMessage.error('生成失败: ' + data.error);
              break;
            }

            if (data.done) {
              console.log('[Chat] 接收完成');
              break;
            }

            // 首次收到数据，清空连接提示
            if (chatMessages.value[assistantIndex].isConnecting) {
              chatMessages.value[assistantIndex].content = '';
              chatMessages.value[assistantIndex].isConnecting = false;
            }

            // 追加思考内容（直接修改reactive数组中的对象）
            if (data.reasoning) {
              const preview = data.reasoning.length > 50 ? data.reasoning.substring(0, 50) + '...' : data.reasoning;
              console.log('[Chat] 收到思考内容:', preview);
              chatMessages.value[assistantIndex].reasoning += data.reasoning;
              console.log('[Chat] 当前thinking总长度:', chatMessages.value[assistantIndex].reasoning.length);
            }

            // 追加回答内容（直接修改reactive数组中的对象）
            if (data.content) {
              console.log('[Chat] 收到回答内容:', data.content);
              chatMessages.value[assistantIndex].content += data.content;
            }

            // 立即更新 UI
            await nextTick();
            scrollToBottom();
          } catch (e) {
            console.error('解析SSE数据失败:', e, line);
          }
        }
      }
    }

    // 如果既没有内容也没有思考，说明出错了
    if (!chatMessages.value[assistantIndex].content && !chatMessages.value[assistantIndex].reasoning) {
      chatMessages.value.pop(); // 移除空消息
      ElMessage.error('生成失败');
    }

  } catch (error) {
    console.error('聊天失败:', error);
    chatMessages.value.pop(); // 移除空消息
    ElMessage.error('发送失败: ' + error.message);
  } finally {
    chatting.value = false;
  }
};

// 清空聊天
const clearChat = () => {
  chatMessages.value = [];
  ElMessage.success('对话已清空');
};

// 切换思考内容显示
const toggleThinking = (msg) => {
  msg.showThinking = !msg.showThinking;
};

// 滚动到底部
const scrollToBottom = () => {
  if (chatHistory.value) {
    chatHistory.value.scrollTop = chatHistory.value.scrollHeight;
  }
};

// 格式化时间
const formatTime = (timestamp) => {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN');
};

// 加载模型列表
const loadModels = async () => {
  try {
    const result = await getKnowledgeModels();
    if (result.success) {
      models.value = result.data;
    }
  } catch (error) {
    console.error('加载模型列表失败:', error);
  }
};

onMounted(() => {
  loadModels();
});
</script>

<style scoped>
.query-interface {
  padding: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header-card {
  border-radius: 0;
  border-bottom: 1px solid #dcdfe6;
  flex-shrink: 0;
}

.header-card :deep(.el-card__header) {
  padding: 16px;
  border-bottom: 1px solid #dcdfe6;
}

.header-card :deep(.el-card__body) {
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
}

/* 聊天模式样式 */
.chat-mode {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 220px);
}

.chat-history {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  background-color: #f5f7fa;
  border-radius: 0;
  border-top: 1px solid #dcdfe6;
  margin-bottom: 0;
  max-height: none;
}

.empty-chat {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
}

.chat-message {
  display: flex;
  margin-bottom: 20px;
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.chat-message.user {
  flex-direction: row-reverse;
}

.chat-message.user .message-content {
  background-color: #409eff;
  color: white;
  margin-right: 12px;
}

.chat-message.assistant .message-content {
  background-color: white;
  margin-left: 12px;
}

.message-avatar {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-content {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 0;
  box-shadow: none;
  border: 1px solid #e4e7ed;
}

.message-text {
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.message-text.connecting {
  color: #909399;
  font-style: italic;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.message-text.typing {
  font-style: italic;
  color: #909399;
}

/* 思考区域样式 */
.thinking-section {
  margin-bottom: 12px;
  border: 1px solid #e4e7ed;
  border-radius: 0;
  background-color: #f9fafc;
  overflow: hidden;
}

.thinking-header {
  padding: 10px 14px;
  background-color: #f0f2f5;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  user-select: none;
  transition: background-color 0.2s;
}

.thinking-header:hover {
  background-color: #e8eaed;
}

.thinking-icon {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 12px;
  color: #606266;
}

.thinking-icon.expanded {
  transform: rotate(90deg);
}

.thinking-header span:nth-child(2) {
  font-weight: 600;
  color: #303133;
  font-size: 13px;
}

.thinking-status {
  margin-left: auto;
  font-size: 12px;
  color: #909399;
  font-style: italic;
}

.thinking-content {
  padding: 14px;
  background-color: #fafbfc;
  color: #606266;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'Courier New', monospace;
  border-top: 1px solid #e4e7ed;
}

.typing-cursor {
  animation: blink 1s infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 50% {
    opacity: 1;
  }
  51%, 100% {
    opacity: 0;
  }
}

.message-time {
  margin-top: 8px;
  font-size: 12px;
  opacity: 0.6;
}

.chat-message.user .message-time {
  text-align: right;
}

.chat-input {
  border-top: 1px solid #e4e7ed;
  padding: 16px;
  background-color: white;
}

.chat-actions {
  display: flex;
  gap: 10px;
  margin-top: 10px;
}
</style>
