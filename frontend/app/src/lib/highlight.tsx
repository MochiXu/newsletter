import { Fragment, type ReactNode } from 'react'
import type { Figure } from '../types'
import { Tooltip } from '../components/Tooltip'
import { GLOSSARY_RE, glossaryExplain } from './glossary'

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

/** 在一段纯文本里把已知术语(regime token / 行话)包成带 hover 的虚下划线。无解释的不包。 */
function highlightGlossary(text: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  GLOSSARY_RE.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = GLOSSARY_RE.exec(text)) !== null) {
    const exp = glossaryExplain(m[0])
    if (!exp) continue // 无解释 → 留作普通文字
    if (m.index > last) out.push(text.slice(last, m.index))
    out.push(
      <Tooltip content={exp} width={232} style={{ display: 'inline' }}>
        <span style={{ borderBottom: '1px dotted var(--ink2)', cursor: 'help' }}>{m[0]}</span>
      </Tooltip>,
    )
    last = m.index + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out.length ? out : [text]
}

/** 事实/解读正文渲染:先按 figures 给数字方向上色,再把 regime/行话术语包成 hover(两者不重叠)。 */
export function renderRichText(text: string, figures?: Figure[]): ReactNode[] {
  const out: ReactNode[] = []
  highlightFigures(text, figures).forEach((n, i) => {
    if (typeof n === 'string') {
      highlightGlossary(n).forEach((seg, j) =>
        out.push(typeof seg === 'string' ? seg : <Fragment key={`g${i}-${j}`}>{seg}</Fragment>),
      )
    } else {
      out.push(n) // figures 上色 span(已带 key)原样保留
    }
  })
  return out
}
