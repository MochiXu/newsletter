import { useState, type CSSProperties } from 'react'
import type { Signal, SignalGroup } from '../../types'
import { colorFor, fmtSignal, signalSigned } from '../../lib/format'
import { REGIME_LABEL, regimeTooltip, translateRegime } from '../../lib/glossary'
import { Card, SectionHead } from '../../components/Card'
import { Tooltip } from '../../components/Tooltip'

const GROUP_CN: Record<SignalGroup, string> = {
  trend: '趋势',
  momentum: '动量',
  vol: '波动与风险',
  rates: '利率与通胀',
  dollar: '美元',
  cross_asset: '跨资产相关',
  range: '52周分位',
}

const chip: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'baseline',
  gap: 5,
  padding: '3px 8px',
  borderRadius: 4,
  background: 'var(--paper2)',
  border: '1px solid var(--faint)',
  cursor: 'help',
}

/** SIGNALS 技术指标卡:regime 徽章常显 + 29 条 signals 按 group 折叠(默认收起)。 */
export default function SignalsCard({ signals, regime }: { signals: Signal[]; regime: Record<string, string> }) {
  const [open, setOpen] = useState(false)
  const regimeKeys = Object.keys(regime || {})
  if (signals.length === 0 && regimeKeys.length === 0) return null

  const groups: { group: SignalGroup; items: Signal[] }[] = []
  for (const s of signals) {
    let g = groups.find((x) => x.group === s.group)
    if (!g) {
      g = { group: s.group, items: [] }
      groups.push(g)
    }
    g.items.push(s)
  }

  return (
    <Card punch>
      <SectionHead label="SIGNALS" zh="技术指标" margin="0 0 10px" />
      {regimeKeys.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: signals.length ? 10 : 0 }}>
          {regimeKeys.map((k) => (
            <Tooltip key={k} content={regimeTooltip(k, regime[k])} width={220} style={chip}>
              <span style={{ fontSize: 10, color: 'var(--ink2)' }}>{REGIME_LABEL[k] ?? k}</span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink)' }}>
                {translateRegime(regime[k])}
              </span>
            </Tooltip>
          ))}
        </div>
      )}

      {signals.length > 0 && (
        <button
          onClick={() => setOpen((o) => !o)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 7,
            width: '100%',
            border: '1px solid var(--hair)',
            background: 'transparent',
            borderRadius: 7,
            padding: '7px 11px',
            cursor: 'pointer',
            color: 'var(--ink2)',
            fontFamily: 'var(--mono)',
            fontSize: 11,
            letterSpacing: '.5px',
          }}
        >
          <span style={{ transition: 'transform .18s', transform: open ? 'rotate(90deg)' : 'none' }}>▸</span>
          <span>{open ? '收起技术指标' : `展开技术指标 · ${signals.length} 项`}</span>
        </button>
      )}

      {open &&
        groups.map((g) => (
          <div key={g.group} style={{ marginTop: 12 }}>
            <div
              style={{
                fontFamily: 'var(--mono)',
                fontSize: 9.5,
                letterSpacing: '1px',
                color: 'var(--accent)',
                marginBottom: 4,
              }}
            >
              {GROUP_CN[g.group] ?? g.group}
            </div>
            {g.items.map((s) => {
              const col = signalSigned(s.unit) ? colorFor(s.value) : 'var(--ink)'
              return (
                <div
                  key={s.key}
                  style={{
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 10,
                    padding: '3px 0',
                    borderBottom: '1px dashed var(--hair)',
                  }}
                >
                  <span style={{ fontSize: 11.5, color: 'var(--ink2)', minWidth: 0 }}>{s.label}</span>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: col, flex: '0 0 auto' }}>
                    {fmtSignal(s.unit, s.value)}
                  </span>
                </div>
              )
            })}
          </div>
        ))}
    </Card>
  )
}
