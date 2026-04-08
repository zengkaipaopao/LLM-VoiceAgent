import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined;
          }

          if (
            id.includes('/node_modules/@carbon/charts/') ||
            id.includes('/node_modules/@carbon/charts-react/') ||
            id.includes('/node_modules/d3/')
          ) {
            return 'carbon_charts_vendor';
          }

          if (id.includes('/node_modules/@carbon/icons-react/')) {
            return 'carbon_icons_vendor';
          }

          if (id.includes('/node_modules/@carbon/react/')) {
            return 'carbon_react_vendor';
          }

          if (
            id.includes('/node_modules/react/') ||
            id.includes('/node_modules/react-dom/') ||
            id.includes('/node_modules/react-router-dom/')
          ) {
            return 'react_vendor';
          }

          if (
            id.includes('/node_modules/i18next/') ||
            id.includes('/node_modules/react-i18next/') ||
            id.includes('/node_modules/i18next-browser-languagedetector/') ||
            id.includes('/node_modules/i18next-http-backend/')
          ) {
            return 'i18n_vendor';
          }

          if (id.includes('/node_modules/@twilio/voice-sdk/')) {
            return 'twilio_vendor';
          }

          return undefined;
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
