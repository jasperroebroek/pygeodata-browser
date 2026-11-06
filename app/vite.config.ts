import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import license from 'rollup-plugin-license';
import { fileURLToPath } from 'node:url';

const BACKEND = process.env.PGB_BACKEND ?? 'http://127.0.0.1:8780';
const THIRD_PARTY_LICENSES = fileURLToPath(new URL('../api/static/app/THIRD_PARTY_LICENSES.txt', import.meta.url));

export default defineConfig(({ command }) => ({
  plugins: [
    svelte(),
    license({
      thirdParty: {
        includePrivate: false,
        output: { file: THIRD_PARTY_LICENSES },
      },
    }),
  ],
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
