import { useEffect, useRef, useState } from 'react'
import type { BriefsPayload, ThemeMode, Tweaks } from './types'
import { loadBriefs } from './data/load'
import { readTheme, readTweaks, useHashRoute, useIsMobile, writeTheme, writeTweaks } from './lib/hooks'
import Header from './components/Header'
import NavTabs from './components/NavTabs'
import TweaksPanel from './components/TweaksPanel'
import BriefPage from './pages/brief/BriefPage'
import TimelinePage from './pages/timeline/TimelinePage'
import TrackPage from './pages/track/TrackPage'

function LoadingPulse() {
  return (
    <div
      style={{
        maxWidth: 1040,
        height: 520,
        margin: '24px auto 0',
        background: 'var(--paper)',
        boxShadow: 'var(--shadow)',
        animation: 'mbpulse 1.4s ease-in-out infinite',
      }}
    />
  )
}

function EmptyState() {
  return (
    <div
      className="mb-card mb-punch"
      style={{ maxWidth: 560, margin: '40px auto', padding: 36, textAlign: 'center', color: 'var(--ink2)' }}
    >
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ink)', letterSpacing: '.5px' }}>
        暂无简报数据
      </div>
      <div style={{ fontSize: 12, lineHeight: 1.7, marginTop: 10 }}>请先运行后端管线生成 data/briefs.json。</div>
    </div>
  )
}

export default function App() {
  const [themeMode, setThemeMode] = useState<ThemeMode>(readTheme)
  const [tweaks, setTweaksState] = useState<Tweaks>(readTweaks)
  const [payload, setPayload] = useState<BriefsPayload | null>(null)
  const rootRef = useRef<HTMLDivElement>(null)
  const route = useHashRoute()
  const isMobile = useIsMobile()

  useEffect(() => {
    loadBriefs().then(setPayload)
  }, [])

  // 注入 --accent(自定义主题色)+ --panel-tex(纸纹开关)
  useEffect(() => {
    const el = rootRef.current
    if (!el) return
    if (tweaks.accent) el.style.setProperty('--accent', tweaks.accent)
    else el.style.removeProperty('--accent')
    el.style.setProperty(
      '--panel-tex',
      tweaks.paperTexture
        ? 'radial-gradient(color-mix(in srgb,var(--faint),transparent 72%) .5px,transparent .6px)'
        : 'none',
    )
  }, [tweaks.accent, tweaks.paperTexture])

  const setTheme = (m: ThemeMode) => {
    setThemeMode(m)
    writeTheme(m)
  }
  const setTweaks = (t: Tweaks) => {
    setTweaksState(t)
    writeTweaks(t)
  }

  const briefs = payload?.briefs ?? []
  const model = payload?.model ?? ''

  let body: React.ReactNode
  if (!payload) body = <LoadingPulse />
  else if (briefs.length === 0) body = <EmptyState />
  else if (route.page === 'timeline') body = <TimelinePage briefs={briefs} route={route} isMobile={isMobile} />
  else if (route.page === 'track') body = <TrackPage mode={route.mode ?? 'year'} />
  else body = <BriefPage briefs={briefs} model={model} route={route} tweaks={tweaks} />

  return (
    <div
      ref={rootRef}
      data-theme={themeMode}
      style={{
        minHeight: '100vh',
        background: 'var(--bg)',
        color: 'var(--ink)',
        fontFamily: 'var(--sans)',
        padding: isMobile ? '22px 14px 64px' : '30px 22px 72px',
        transition: 'background .35s ease, color .35s ease',
      }}
    >
      <div style={{ maxWidth: 1080, margin: '0 auto' }}>
        <Header themeMode={themeMode} setTheme={setTheme} />
        <NavTabs page={route.page} />
        {body}
      </div>
      <TweaksPanel tweaks={tweaks} setTweaks={setTweaks} />
    </div>
  )
}
