import { useState, type CSSProperties } from 'react'
import type { TrackMode } from '../../types'

const MODES: { k: TrackMode; zh: string }[] = [
  { k: 'month', zh: '月度' },
  { k: 'quarter', zh: '季度' },
  { k: 'year', zh: '年度' },
  { k: 'all', zh: 'ALL' },
]

const tab = (active: boolean): CSSProperties => ({
  padding: '5px 13px',
  fontSize: 11,
  fontFamily: 'var(--mono)',
  letterSpacing: '.5px',
  border: 'none',
  borderRadius: 7,
  cursor: 'pointer',
  background: active ? 'var(--paper)' : 'transparent',
  color: active ? 'var(--ink)' : 'var(--ink2)',
  boxShadow: active ? '0 1px 3px rgba(0,0,0,.14)' : 'none',
  transition: 'all .18s',
})

/** 命中率页:后端 V2 评估层未就绪 → 维度 tab 可切但统一空态(绝不显示假命中率)。 */
export default function TrackPage({ mode: initial }: { mode: TrackMode }) {
  const [mode, setMode] = useState<TrackMode>(initial || 'year')
  return (
    <div style={{ marginTop: 26, maxWidth: 1040, marginLeft: 'auto', marginRight: 'auto' }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, marginBottom: 18, flexWrap: 'wrap' }}
      >
        <div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '1.6px', color: 'var(--ink2)' }}>
            TRACK RECORD
          </span>
          <span style={{ fontSize: 13, color: 'var(--ink2)', marginLeft: 8 }}>命中率统计 · 待 V2 评估层</span>
        </div>
        <div style={{ display: 'flex', gap: 2, padding: 3, background: 'var(--paper2)', borderRadius: 9 }}>
          {MODES.map((m) => (
            <button key={m.k} style={tab(m.k === mode)} onClick={() => setMode(m.k)}>
              {m.zh}
            </button>
          ))}
        </div>
      </div>

      <div className="mb-card mb-punch" style={{ padding: '40px 32px', textAlign: 'center' }}>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 30, fontWeight: 600, color: 'var(--ink2)', letterSpacing: '1px' }}>
          —— %
        </div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ink)', letterSpacing: '.5px', marginTop: 14 }}>
          评估层未就绪(V2)
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ink2)', lineHeight: 1.8, marginTop: 12, maxWidth: 560, margin: '12px auto 0' }}>
          命中率需要对历史预测用「未来真实走势」逐条打分(回测),这是 V2 评估层的产物,目前后端尚未实现。
          <br />
          在真实打分跑出来前,这里不会显示任何命中率数字——避免编造。
          <br />
          <br />
          逐条的假设 <span style={{ color: 'var(--up)' }}>✓兑现</span> / <span style={{ color: 'var(--down)' }}>✕失效</span> /{' '}
          <span style={{ color: 'var(--accent)' }}>○待观察</span> 复盘,已经在「简报页 · 假设复盘」里逐日呈现。
        </div>
      </div>
    </div>
  )
}
