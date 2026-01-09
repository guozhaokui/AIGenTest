import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        timeout: 1800000, // 30分钟超时
        proxyTimeout: 1800000, // 代理连接超时
        configure: (proxy, options) => {
          // 设置代理 socket 超时
          proxy.on('proxyReq', (proxyReq, req, res) => {
            req.socket.setTimeout(1800000);
            proxyReq.socket && proxyReq.socket.setTimeout(1800000);
          });
        }
      },
      // 添加新路径代理
      '/imagedb': {
        target: 'http://localhost:3000',
        changeOrigin: true
      },
      '/modeldb': {
        target: 'http://localhost:3000',
        changeOrigin: true
      },
      '/videodb': {
        target: 'http://localhost:3000',
        changeOrigin: true
      }
    }
  },
  optimizeDeps: {
    include: ['@ai-eval/shared']
  }
});


