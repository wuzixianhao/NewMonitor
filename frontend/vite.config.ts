import { fileURLToPath } from 'node:url'
import { PrimeVueResolver } from '@primevue/auto-import-resolver'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import components from 'unplugin-vue-components/vite'
import { defineConfig } from 'vite'

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  plugins: [
    tailwindcss(),
    vue(),
    components({
      resolvers: [PrimeVueResolver()],
    }),
  ],
  server: {
    proxy: {
      '/monitor': {
        target: 'http://172.17.58.32',
        changeOrigin: true,
      },
      '/servers': {
        target: 'http://172.17.58.32',
        changeOrigin: true,
      },
      '/report': {
        target: 'http://172.17.58.32',
        changeOrigin: true,
      },
      '/ws': {
        target: 'http://172.17.58.32:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
