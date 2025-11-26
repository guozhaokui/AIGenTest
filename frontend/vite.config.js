import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true
      },
      // 保留旧路径代理，兼容历史数据
      '/uploads': {
        target: 'http://localhost:3000',
        changeOrigin: true
      },
      // 添加新路径代理
      '/imagedb': {
        target: 'http://localhost:3000',
        changeOrigin: true
      }
    }
  },
  optimizeDeps: {
    include: ['@ai-eval/shared']
  }
});


