import { useEffect, useRef, useState, type CSSProperties } from 'react'
import type { BriefsPayload, ThemeMode, Tweaks } from './types'
import { loadBriefs } from './data/loadBriefs'
import { useIsNarrow } from './lib/useMediaQuery'
import Header from './components/Header'
import Timeline from './components/Timeline'
import Receipt from './components/Receipt'
import TweaksPanel from './components/TweaksPanel'
import MarketData from './components/sections/MarketData'
import AiBrief from './components/sections/AiBrief'
import Review from './components/sections/Review'
import News from './components/sections/News'

const THEME_KEY = 'mb_theme'
const TWEAKS_KEY = 'mb_tweaks'
const DEFAULT_TWEAKS: Tweaks = { accent: null, showSparklines: true, paperTexture: true }

function readTheme(): ThemeMode {
  try {
    const t = localStorage.getItem(THEME_KEY)
    if (t === 'auto' || t === 'light' || t === 'dark') return t
  } catch {
    /* localStorage 不可用:用默认 */
  }
  return 'auto'
}

function readTweaks(): Tweaks {
  try {
    const raw = localStorage.getItem(TWEAKS_KEY)
    if (raw) return { ...DEFAULT_TWEAKS, ...(JSON.parse(raw) as Partial<Tweaks>) }
  } catch {
    /* 解析失败:用默认 */
  }
  return DEFAULT_TWEAKS
}

function LoadingPulse() {
  return (
    <div
      style={{
        width: 'min(440px,100%)',
        height: 560,
        background: 'var(--paper)',
        boxShadow: 'var(--shadow)',
        animation: 'mbpulse 1.4s ease-in-out infinite',
      }}
    />
  )
}

export default function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(readTheme)
  const [tweaks, setTweaksState] = useState<Tweaks>(readTweaks)
  const [payload, setPayload] = useState<BriefsPayload | null>(null)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [hoverIdx, setHoverIdx] = useState<number | null>(null)
  const isNarrow = useIsNarrow()
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    loadBriefs().then(setPayload)
  }, [])

  // 自定义主题色:注入到根元素的 --accent(覆盖主题默认);null 时移除回退默认。
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    if (tweaks.accent) el.style.setProperty('--accent', tweaks.accent)
    else el.style.removeProperty('--accent')
  }, [tweaks.accent])

  const setTheme = (m: ThemeMode) => {
    setThemeMode(m)
    try {
      localStorage.setItem(THEME_KEY, m)
    } catch {
      /* 忽略持久化失败 */
    }
  }

  const setTweaks = (t: Tweaks) => {
    setTweaksState(t)
    try {
      localStorage.setItem(TWEAKS_KEY, JSON.stringify(t))
    } catch {
      /* 忽略持久化失败 */
    }
  }

  const briefs = payload?.briefs ?? []
  const loaded = briefs.length > 0
  // activeIndex = 悬停预览优先,否则锁定项;并夹在合法范围内。
  const activeIndex = Math.min(hoverIdx ?? selectedIdx, Math.max(briefs.length - 1, 0))
  const active = briefs[activeIndex]

  // 移动端无 hover:点击直切;桌面:悬停预览 + 点击锁定。
  const onHover = isNarrow ? () => {} : setHoverIdx
  const onSelect = (i: number) => {
    setSelectedIdx(i)
    setHoverIdx(null)
  }

  const cols: CSSProperties = isNarrow
    ? { display: 'flex', flexDirection: 'column', gap: 20 }
    : { display: 'flex', gap: 34, alignItems: 'flex-start', flexWrap: 'wrap' }
  const receiptCol: CSSProperties = isNarrow
    ? { display: 'flex', justifyContent: 'center' }
    : { flex: '2 1 440px', display: 'flex', justifyContent: 'center', minWidth: 300 }

  const receiptNode = active ? (
    <Receipt brief={active} model={payload?.model ?? 'DeepSeek'} texture={tweaks.paperTexture} animKey={activeIndex}>
      <MarketData metrics={active.metrics} date={active.date} showSparklines={tweaks.showSparklines} />
      <AiBrief brief={active} />
      <Review reviews={active.reviews} />
      <News news={active.news} />
    </Receipt>
  ) : (
    <LoadingPulse />
  )

  return (
    <div
      ref={rootRef}
      data-theme={themeMode}
      style={{
        minHeight: '100vh',
        background: 'var(--bg)',
        color: 'var(--ink)',
        fontFamily: 'var(--sans)',
        padding: isNarrow ? '22px 14px 64px' : '32px 22px 64px',
        transition: 'background .35s ease, color .35s ease',
      }}
    >
      <div style={{ maxWidth: 1060, margin: '0 auto' }}>
        <Header themeMode={themeMode} setTheme={setTheme} />
        <div style={{ borderTop: '1px solid var(--hair)', margin: '20px 0 24px' }} />

        <div style={cols}>
          {loaded && (
            <Timeline
              briefs={briefs}
              activeIndex={activeIndex}
              isNarrow={isNarrow}
              onHover={onHover}
              onSelect={onSelect}
            />
          )}
          <div style={receiptCol}>
            {isNarrow ? (
              receiptNode
            ) : (
              <div
                className="mb-scroll"
                style={{
                  position: 'sticky',
                  top: 16,
                  maxHeight: 'calc(100vh - 32px)',
                  overflowY: 'auto',
                  overflowX: 'hidden',
                  overscrollBehavior: 'contain',
                  padding: '4px 22px 40px',
                }}
              >
                {receiptNode}
              </div>
            )}
          </div>
        </div>
      </div>

      <TweaksPanel tweaks={tweaks} setTweaks={setTweaks} />
    </div>
  )
}
