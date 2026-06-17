import type { CSSProperties } from 'react'
import type { Brief } from '../types'
import { toneCol } from '../lib/tone'

interface Props {
  briefs: Brief[]
  activeIndex: number
  isNarrow: boolean
  onHover: (idx: number | null) => void
  onSelect: (idx: number) => void
}

const dateShort = (date: string) => date.slice(5).replace('-', '.') // '2026-06-16' -> '06.16'

// 章节小标题:TIMELINE 时间线 ------
function SectionHead() {
  return (
    <div
      style={{
        fontFamily: 'var(--mono)',
        fontSize: 10,
        letterSpacing: '1.5px',
        color: 'var(--ink2)',
        marginBottom: 12,
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}
    >
      <span>TIMELINE</span>
      <span>时间线</span>
      <span style={{ flex: 1, borderTop: '1px dashed var(--faint)' }} />
    </div>
  )
}

/** 时间线导航。桌面:竖直列表 + 悬停预览/点击锁定;移动:横向滚动日期条 + 点击直切。 */
export default function Timeline({ briefs, activeIndex, isNarrow, onHover, onSelect }: Props) {
  if (isNarrow) return <NarrowTimeline {...{ briefs, activeIndex, onSelect }} />
  return <WideTimeline {...{ briefs, activeIndex, onHover, onSelect }} />
}

// ── 桌面:竖直时间线 ────────────────────────────────────────────────────
function WideTimeline({
  briefs,
  activeIndex,
  onHover,
  onSelect,
}: Omit<Props, 'isNarrow'>) {
  return (
    <div
      className="mb-scroll"
      style={{
        flex: '1 1 230px',
        maxWidth: 288,
        minWidth: 206,
        position: 'sticky',
        top: 16,
        maxHeight: 'calc(100vh - 32px)',
        overflowY: 'auto',
        overscrollBehavior: 'contain',
        paddingRight: 4,
      }}
    >
      <SectionHead />
      <div style={{ position: 'relative' }}>
        {/* 竖直主线 */}
        <div
          style={{
            position: 'absolute',
            left: 9,
            top: 10,
            bottom: 10,
            width: 2,
            background: 'var(--hair)',
            borderRadius: 2,
          }}
        />
        {briefs.map((b, i) => {
          const isA = i === activeIndex
          return (
            <button
              key={b.date}
              onMouseEnter={() => onHover(i)}
              onMouseLeave={() => onHover(null)}
              onClick={() => onSelect(i)}
              style={{
                position: 'relative',
                display: 'block',
                width: '100%',
                textAlign: 'left',
                border: 'none',
                background: isA ? 'var(--paper2)' : 'transparent',
                borderRadius: 8,
                padding: '9px 12px 9px 30px',
                marginBottom: 1,
                cursor: 'pointer',
                transition: 'background .18s, opacity .18s',
                opacity: isA ? 1 : 0.6,
              }}
            >
              <span style={dotStyle(isA, b.tone)} />
              <span style={{ display: 'flex', alignItems: 'baseline' }}>
                <span
                  style={{
                    fontFamily: 'var(--mono)',
                    fontSize: 12.5,
                    fontWeight: 600,
                    color: isA ? 'var(--ink)' : 'var(--ink2)',
                    letterSpacing: '.3px',
                  }}
                >
                  {dateShort(b.date)}
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', marginLeft: 7 }}>
                  {b.weekday}
                </span>
              </span>
              <span
                style={{
                  fontSize: 11.5,
                  lineHeight: 1.4,
                  marginTop: 3,
                  color: isA ? 'var(--ink)' : 'var(--ink2)',
                  display: '-webkit-box',
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}
              >
                {b.headline}
              </span>
            </button>
          )
        })}
      </div>
      <div
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 9.5,
          color: 'var(--ink2)',
          letterSpacing: '.5px',
          marginTop: 14,
          paddingLeft: 6,
          opacity: 0.85,
        }}
      >
        悬停预览 · 点击锁定
      </div>
    </div>
  )
}

function dotStyle(isA: boolean, tone: Brief['tone']): CSSProperties {
  return {
    position: 'absolute',
    left: 9,
    top: 14,
    width: isA ? 11 : 8,
    height: isA ? 11 : 8,
    transform: 'translateX(-50%)',
    borderRadius: '50%',
    background: toneCol(tone),
    boxShadow: isA
      ? '0 0 0 3px var(--paper2), 0 0 0 4.5px var(--accent)'
      : '0 0 0 3px var(--paper)',
    transition: 'all .2s',
  }
}

// ── 移动:横向滚动日期条 ─────────────────────────────────────────────────
function NarrowTimeline({
  briefs,
  activeIndex,
  onSelect,
}: Pick<Props, 'briefs' | 'activeIndex' | 'onSelect'>) {
  return (
    <div>
      <SectionHead />
      <div
        style={{
          display: 'flex',
          gap: 8,
          overflowX: 'auto',
          paddingBottom: 6,
          WebkitOverflowScrolling: 'touch',
        }}
      >
        {briefs.map((b, i) => {
          const isA = i === activeIndex
          return (
            <button
              key={b.date}
              onClick={() => onSelect(i)}
              style={{
                flex: '0 0 auto',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 5,
                minWidth: 62,
                border: '1px solid var(--hair)',
                background: isA ? 'var(--paper2)' : 'transparent',
                borderRadius: 9,
                padding: '8px 10px',
                cursor: 'pointer',
                opacity: isA ? 1 : 0.6,
                transition: 'background .18s, opacity .18s',
              }}
            >
              <span
                style={{
                  width: isA ? 11 : 8,
                  height: isA ? 11 : 8,
                  borderRadius: '50%',
                  background: toneCol(b.tone),
                  boxShadow: isA ? '0 0 0 3px var(--accent)' : 'none',
                  transition: 'all .2s',
                }}
              />
              <span
                style={{
                  fontFamily: 'var(--mono)',
                  fontSize: 12,
                  fontWeight: 600,
                  color: isA ? 'var(--ink)' : 'var(--ink2)',
                }}
              >
                {dateShort(b.date)}
              </span>
              <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)' }}>{b.weekday}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
