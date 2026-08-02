import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// El puerto 3000 lo ocupa otra app en la maquina del usuario, por eso 3001.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3001,
    strictPort: true,
  },
  build: {
    outDir: 'build',
  },
});
