import type { CSSProperties } from 'react'
import type { ThemeMode } from '../types'
import { modelLabel } from '../lib/format'

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

const lab: CSSProperties = { fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', letterSpacing: '1px' }
const seg: CSSProperties = { display: 'flex', gap: 2, padding: 3, background: 'var(--paper2)', borderRadius: 9 }

interface Props {
  themeMode: ThemeMode
  setTheme: (m: ThemeMode) => void
  models?: string[]
  selectedModel?: string
  setModel?: (m: string) => void
}

/** 页眉:站标 + 主标题 + 副标题(左)+ 模型切换(>1 时)+ 主题三档(右)。 */
export default function Header({ themeMode, setTheme, models = [], selectedModel, setModel }: Props) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-end',
        gap: 20,
        flexWrap: 'wrap',
        padding: '0 2px',
      }}
    >
      <div>
        <div style={{ fontFamily: 'var(--mono)', fontSize: 11, letterSpacing: '2.5px', color: 'var(--accent)' }}>
          DAILY MACRO BRIEF
        </div>
        <div style={{ fontSize: 27, fontWeight: 700, letterSpacing: '-.5px', color: 'var(--ink)', marginTop: 6 }}>
          市场走势简报
        </div>
        <div style={{ fontSize: 12.5, color: 'var(--ink2)', marginTop: 5 }}>
          AI 生成 · 金融数据抓取 + 走势研判 · 每个交易日一刊
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        {models.length > 1 && setModel && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={lab}>模型</span>
            <div style={seg}>
              {models.map((m) => (
                <button key={m} style={tab(m === selectedModel)} onClick={() => setModel(m)}>
                  {modelLabel(m)}
                </button>
              ))}
            </div>
          </div>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={lab}>主题</span>
          <div style={seg}>
            <button style={tab(themeMode === 'auto')} onClick={() => setTheme('auto')}>
              自动
            </button>
            <button style={tab(themeMode === 'light')} onClick={() => setTheme('light')}>
              浅色
            </button>
            <button style={tab(themeMode === 'dark')} onClick={() => setTheme('dark')}>
              深色
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
