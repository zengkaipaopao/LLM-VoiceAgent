import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react_vendor: ['react', 'react-dom', 'react-router-dom'],
          carbon_vendor: [
            '@carbon/react',
            '@carbon/icons-react',
            '@carbon/charts',
            '@carbon/charts-react',
          ],
          i18n_vendor: [
            'i18next',
            'react-i18next',
            'i18next-browser-languagedetector',
            'i18next-http-backend',
          ],
          twilio_vendor: ['@twilio/voice-sdk'],
        },
      },
    },
  },
  // 强制 Vite 重新加载配置 (Force Reload)
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
  css: {
    preprocessorOptions: {
      scss: {
        silenceDeprecations: ['legacy-js-api', 'import', 'if-function', 'global-builtin'],
      },
    },
  },
  preview: {
    port: 4173,
  },
});
