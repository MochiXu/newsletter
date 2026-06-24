// 把仓库根的 data/{briefs,scorecard}.json(智能平面产出)拷进 public/data/,供前端 fetch。
// 在 predev / prebuild 钩子里跑。文件不存在时静默跳过(前端走空态)。
import { copyFileSync, existsSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url)) // frontend/app/scripts
const destDir = resolve(here, '../public/data')
mkdirSync(destDir, { recursive: true })

for (const f of ['briefs.json', 'scorecard.json']) {
  const src = resolve(here, '../../../data', f) // -> 仓库根 data/<f>
  if (existsSync(src)) {
    copyFileSync(src, resolve(destDir, f))
    console.log(`[copy-data] data/${f} -> public/data/${f}`)
  } else {
    console.log(`[copy-data] 仓库根无 data/${f},跳过(前端走空态)`)
  }
}
