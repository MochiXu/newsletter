import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 纯静态产物。data/briefs.json 由 predev/prebuild 的 scripts/copy-data.mjs 拷进 public/data/;
// 相对 base 便于将来挂到 GitHub Pages 等任意子路径静态托管。
export default defineConfig({
  plugins: [react()],
  base: './',
})
