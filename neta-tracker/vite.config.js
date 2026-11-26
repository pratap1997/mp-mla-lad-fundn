import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  base: '/mp-mla-lad-fundn/',   // GitHub Pages path
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  }
})
