import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // REST + SSE (SSE streams fine over the default http proxy).
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      // Generated/placeholder images (ImageRef.url paths).
      '/generated': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './vitest.setup.ts',
    css: false,
  },
});
