import type { ReactNode } from 'react'
import type { Figure } from '../types'

// 由后端 figures 驱动给文本里的关键数字上色(不再用前端正则猜)。
// figures[].t 是 text 的原样子串(后端已与 text 一起规范化);dir:up→绿、down→红、flat→中性等宽。
// 没被 figures 标注的数字 = 普通文字(后端决定"哪些数字上色、什么方向"),符合"不是每个数字都上色"。
const COL: Record<string, string> = { up: 'var(--up)', down: 'var(--down)', flat: 'var(--ink)' }

/** 文本 + figures → React 节点数组,figures 命中的子串被等宽+方向色包裹。 */
export function highlightFigures(text: string, figures?: Figure[]): ReactNode[] {
  const figs = (figures ?? []).filter((f) => f.t)
  if (figs.length === 0) return [text]
  // 长 token 优先,避免短 token 抢占(如 '2' 抢 '-2bp')
  const ordered = [...figs].sort((a, b) => b.t.length - a.t.length)
  const out: ReactNode[] = []
  let buf = ''
  let i = 0
  let k = 0
  while (i < text.length) {
    const hit = ordered.find((f) => text.startsWith(f.t, i))
    if (hit) {
      if (buf) {
        out.push(buf)
        buf = ''
      }
      out.push(
        <span key={k++} style={{ fontFamily: 'var(--mono)', color: COL[hit.dir] ?? 'var(--ink)' }}>
          {hit.t}
        </span>,
      )
      i += hit.t.length
    } else {
      buf += text[i]
      i++
    }
  }
  if (buf) out.push(buf)
  return out
}
