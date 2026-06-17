import { useState, type CSSProperties } from 'react'
import type { Tweaks } from '../types'

// 主题色候选(含设计稿默认 #fa5700 与各主题色);null = 跟随主题默认 --accent。
const ACCENTS: { name: string; value: string | null }[] = [
  { name: '默认', value: null },
  { name: '橙赭', value: '#c0612f' },
  { name: '暖橙', value: '#e0824a' },
  { name: '艳橙', value: '#fa5700' },
  { name: '钢蓝', value: '#3a6ea5' },
  { name: '墨绿', value: '#2f7d50' },
]

interface Props {
  tweaks: Tweaks
  setTweaks: (t: Tweaks) => void
}

const rowStyle: CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 12,
  marginTop: 12,
}
const labelStyle: CSSProperties = { fontSize: 11, color: 'var(--ink2)', fontFamily: 'var(--mono)', letterSpacing: '.5px' }

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      style={{
        fontFamily: 'var(--mono)',
        fontSize: 10,
        letterSpacing: '.5px',
        padding: '3px 12px',
        borderRadius: 7,
        cursor: 'pointer',
        border: '1px solid var(--hair)',
        background: on ? 'var(--accent)' : 'transparent',
        color: on ? 'var(--paper)' : 'var(--ink2)',
        transition: 'all .18s',
      }}
    >
      {on ? '开' : '关'}
    </button>
  )
}

/** 用户可调项浮层(对应设计稿「宿主右侧面板」):主题色 / 走势线 / 纸纹理。固定右下角。 */
export default function TweaksPanel({ tweaks, setTweaks }: Props) {
  const [open, setOpen] = useState(false)
  const set = (patch: Partial<Tweaks>) => setTweaks({ ...tweaks, ...patch })

  return (
    <div style={{ position: 'fixed', right: 18, bottom: 18, zIndex: 50 }}>
      {open ? (
        <div
          style={{
            width: 226,
            background: 'var(--paper)',
            border: '1px solid var(--hair)',
            borderRadius: 12,
            boxShadow: 'var(--shadow)',
            padding: '14px 16px 16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '1.6px', color: 'var(--ink2)' }}>
              TWEAKS 调整
            </span>
            <button
              onClick={() => setOpen(false)}
              style={{ border: 'none', background: 'transparent', color: 'var(--ink2)', cursor: 'pointer', fontSize: 14, lineHeight: 1 }}
              aria-label="关闭"
            >
              ✕
            </button>
          </div>

          <div style={{ marginTop: 12 }}>
            <span style={labelStyle}>主题色</span>
            <div style={{ display: 'flex', gap: 7, marginTop: 8, flexWrap: 'wrap' }}>
              {ACCENTS.map((a) => {
                const selected = tweaks.accent === a.value
                return (
                  <button
                    key={a.name}
                    title={a.name}
                    onClick={() => set({ accent: a.value })}
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: '50%',
                      cursor: 'pointer',
                      background: a.value ?? 'var(--accent)',
                      border: selected ? '2px solid var(--ink)' : '1px solid var(--hair)',
                      boxShadow: a.value === null ? 'inset 0 0 0 6px var(--paper)' : 'none',
                    }}
                  />
                )
              })}
            </div>
          </div>

          <div style={rowStyle}>
            <span style={labelStyle}>走势线</span>
            <Toggle on={tweaks.showSparklines} onToggle={() => set({ showSparklines: !tweaks.showSparklines })} />
          </div>
          <div style={rowStyle}>
            <span style={labelStyle}>纸纹理</span>
            <Toggle on={tweaks.paperTexture} onToggle={() => set({ paperTexture: !tweaks.paperTexture })} />
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          aria-label="打开调整面板"
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 11,
            letterSpacing: '.5px',
            padding: '8px 14px',
            borderRadius: 10,
            cursor: 'pointer',
            border: '1px solid var(--hair)',
            background: 'var(--paper)',
            color: 'var(--ink2)',
            boxShadow: 'var(--shadow)',
          }}
        >
          ⚙ 调整
        </button>
      )}
    </div>
  )
}
