import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [
    vue()],
  server: {
    proxy: {
      // 只要是 /monitor, /servers, /report 开头的请求，都转发给 Python 后端
      '/monitor': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/servers': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/report': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  }
})