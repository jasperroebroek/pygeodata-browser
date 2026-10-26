import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

const BACKEND = process.env.PGB_BACKEND ?? 'http://127.0.0.1:8780';

export default defineConfig(({ command }) => ({
  plugins: [svelte()],
  // Relative base so the built bundle works behind any mount point (/app).
  base: command === 'build' ? './' : '/',
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: false },
    },
  },
  build: {
    outDir: '../api/static/app',
    emptyOutDir: true,
  },
}));
