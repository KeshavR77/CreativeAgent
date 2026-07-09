import { defineConfig } from 'vitest/config';

// Node 20.6.x + @babel/core trigger "Cannot redefine property: File", which
// crashes @vitejs/plugin-react (babel) in the dev server. Use the SWC React
// plugin for serve/build (no babel, no File collision); keep the babel plugin
// under Vitest, where the suite is already green.
const react = process.env.VITEST
  ? (await import('@vitejs/plugin-react')).default
  : (await import('@vitejs/plugin-react-swc')).default;

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Backend runs on 8080 — 8000 is reserved for a locally-tunneled
      // Conceptial server (see CONCEPTIAL_BASE_URL in .env.example).
      // REST + SSE (SSE streams fine over the default http proxy).
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: true },
      // Generated/placeholder images (ImageRef.url paths).
      '/generated': { target: 'http://127.0.0.1:8080', changeOrigin: true },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './vitest.setup.ts',
    css: false,
  },
});
