// 把仓库根的 data/briefs.json(智能平面产出)拷进 public/data/,供前端 fetch。
// 在 predev / prebuild 钩子里跑。文件不存在时静默跳过(前端回退到 bundled demo)。
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url)) // frontend/app/scripts
const src = resolve(here, '../../../data/briefs.json') // -> 仓库根 data/briefs.json
const destDir = resolve(here, '../public/data')
const dest = resolve(destDir, 'briefs.json')

if (existsSync(src)) {
  mkdirSync(destDir, { recursive: true })
  copyFileSync(src, dest)
  console.log('[copy-data] data/briefs.json -> public/data/briefs.json')
} else {
  console.log('[copy-data] 仓库根无 data/briefs.json,前端将使用内置 demo 数据')
}
