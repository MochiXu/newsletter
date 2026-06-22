import { useState, type CSSProperties } from 'react'
import type { Brief, Granularity, Route } from '../../types'
import { nav } from '../../lib/hooks'
import { colorFor, dirInfo, fmtChg, fmtVal, toneCol, viewOf } from '../../lib/format'
import { sparkGeom } from '../../lib/geometry'

const GRAN_TABS: { k: Granularity; zh: string }[] = [
  { k: 'day', zh: '日' },
  { k: 'month', zh: '月' },
  { k: 'quarter', zh: '季' },
  { k: 'half', zh: '半年' },
  { k: 'year', zh: '年' },
]
const GRAN_NOTE: Record<Granularity, string> = {
  day: '逐个交易日 · 悬停预览 · 点击锁定',
  month: '按月聚合(待 V2 评估层)',
  quarter: '按季聚合(待 V2 评估层)',
  half: '按半年聚合(待 V2 评估层)',
  year: '按年聚合(待 V2 评估层)',
}

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

const shortDate = (iso: string) => iso.slice(5).replace('-', '.')

export default function TimelinePage({
  briefs,
  route,
  isMobile,
  model,
}: {
  briefs: Brief[]
  route: Route
  isMobile: boolean
  model: string
}) {
  const gran: Granularity = route.gran ?? 'day'
  const [hover, setHover] = useState<number | null>(null)
  const [selected, setSelected] = useState(0)
  const [expanded, setExpanded] = useState(false)

  const isDay = gran === 'day'
  const len = isDay ? briefs.length : 0
  const sel = Math.max(0, Math.min(selected, Math.max(len - 1, 0)))
  const act = hover != null && hover < len ? hover : sel
  const a = isDay ? briefs[act] : undefined

  return (
    <div style={{ marginTop: 26, maxWidth: 1040, marginLeft: 'auto', marginRight: 'auto' }}>
      {/* 头 */}
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, marginBottom: 18, flexWrap: 'wrap' }}
      >
        <div>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '1.6px', color: 'var(--ink2)' }}>
            TIMELINE
          </span>
          <span style={{ fontSize: 13, color: 'var(--ink2)', marginLeft: 8 }}>{GRAN_NOTE[gran]}</span>
        </div>
        <div style={{ display: 'flex', gap: 2, padding: 3, background: 'var(--paper2)', borderRadius: 9 }}>
          {GRAN_TABS.map((g) => (
            <button key={g.k} style={tab(g.k === gran)} onClick={() => nav(`#/timeline/${g.k}`)}>
              {g.zh}
            </button>
          ))}
        </div>
      </div>

      {!isDay ? (
        <PeriodEmpty />
      ) : (
        <div
          style={
            isMobile
              ? { display: 'flex', flexDirection: 'column', gap: 16 }
              : { display: 'flex', gap: 30, alignItems: 'flex-start', flexWrap: 'wrap' }
          }
        >
          {/* 左:时刻列表 */}
          <div
            className="mb-scroll"
            style={
              isMobile
                ? { display: 'flex', flexDirection: 'row', overflowX: 'auto', gap: 8, paddingBottom: 6 }
                : {
                    flex: '0 0 266px',
                    minWidth: 228,
                    position: 'relative',
                    maxHeight: 'calc(100vh - 238px)',
                    overflowY: 'auto',
                    padding: '6px 10px 6px 6px',
                    WebkitMaskImage:
                      'linear-gradient(to bottom, transparent 0, #000 22px, #000 calc(100% - 22px), transparent 100%)',
                    maskImage:
                      'linear-gradient(to bottom, transparent 0, #000 22px, #000 calc(100% - 22px), transparent 100%)',
                  }
            }
          >
            {!isMobile && (
              <div style={{ position: 'absolute', left: 13, top: 8, bottom: 8, width: 2, background: 'var(--hair)' }} />
            )}
            {briefs.map((b, i) => {
              const isA = i === act
              const v = viewOf(b, model)
              return (
                <button
                  key={b.date}
                  onMouseEnter={isMobile ? undefined : () => setHover(i)}
                  onMouseLeave={isMobile ? undefined : () => setHover(null)}
                  onClick={() => {
                    setSelected(i)
                    setHover(null)
                  }}
                  style={
                    isMobile
                      ? {
                          flex: '0 0 auto',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          gap: 5,
                          minWidth: 64,
                          border: '1px solid var(--hair)',
                          background: isA ? 'var(--paper2)' : 'transparent',
                          borderRadius: 9,
                          padding: '8px 10px',
                          cursor: 'pointer',
                          opacity: isA ? 1 : 0.7,
                        }
                      : {
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
                          opacity: isA ? 1 : 0.62,
                          transition: 'background .18s, opacity .18s',
                        }
                  }
                >
                  <span
                    style={
                      isMobile
                        ? {
                            width: isA ? 11 : 8,
                            height: isA ? 11 : 8,
                            borderRadius: '50%',
                            background: toneCol(v.tone),
                            boxShadow: isA ? '0 0 0 3px var(--accent)' : 'none',
                          }
                        : {
                            position: 'absolute',
                            left: 13,
                            top: 14,
                            width: isA ? 11 : 8,
                            height: isA ? 11 : 8,
                            transform: 'translateX(-50%)',
                            borderRadius: '50%',
                            background: toneCol(v.tone),
                            boxShadow: isA ? '0 0 0 3px var(--paper2), 0 0 0 4.5px var(--accent)' : '0 0 0 3px var(--paper)',
                            transition: 'all .2s',
                          }
                    }
                  />
                  <span style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
                    <span
                      style={{
                        fontFamily: 'var(--mono)',
                        fontSize: 12.5,
                        fontWeight: 600,
                        color: isA ? 'var(--ink)' : 'var(--ink2)',
                      }}
                    >
                      {shortDate(b.date)}
                    </span>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: isMobile ? 9 : 10, color: 'var(--ink2)' }}>
                      {b.weekday}
                    </span>
                  </span>
                  {!isMobile && (
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
                      {v.headline}
                    </span>
                  )}
                </button>
              )
            })}
          </div>

          {/* 右:小票概览 */}
          <div style={{ flex: isMobile ? undefined : '1 1 360px', minWidth: isMobile ? undefined : 300, display: 'flex', justifyContent: 'center' }}>
            {a && <Overview brief={a} model={model} expanded={expanded} setExpanded={setExpanded} />}
          </div>
        </div>
      )}
    </div>
  )
}

function Overview({
  brief: b,
  model,
  expanded,
  setExpanded,
}: {
  brief: Brief
  model: string
  expanded: boolean
  setExpanded: (v: boolean) => void
}) {
  const v = viewOf(b, model)
  return (
    <div className="mb-card mb-punch" style={{ position: 'relative', width: 'min(430px,100%)' }}>
      <button
        onClick={() => nav(`#/brief/${b.date}/timeline`)}
        style={{
          position: 'absolute',
          top: 13,
          right: 15,
          zIndex: 4,
          fontFamily: 'var(--mono)',
          fontSize: 10,
          letterSpacing: '.5px',
          padding: '5px 11px',
          borderRadius: 20,
          border: 'none',
          cursor: 'pointer',
          background: 'var(--accent)',
          color: 'var(--paper)',
          boxShadow: '0 5px 14px -4px rgba(0,0,0,.45)',
        }}
      >
        详情 →
      </button>
      <div className="mb-scroll" style={{ padding: '14px 26px 16px' }}>
        {/* 票头 */}
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '3px', color: 'var(--ink2)' }}>
            宏观简报 · MACRO BRIEF
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 26, fontWeight: 600, color: 'var(--ink)', marginTop: 6 }}>
            {b.date}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)', marginTop: 5 }}>
            {b.weekday} · 第 {b.issue} 刊 · {b.time}
          </div>
        </div>
        <div style={{ borderTop: '1px dashed var(--faint)', margin: '13px 0' }} />
        <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.5, color: 'var(--ink)', textWrap: 'pretty' }}>
          {v.headline}
        </div>

        {/* MARKET DATA(紧凑) */}
        <div style={{ marginTop: 14 }}>
          {b.metrics.map((m) => {
            const col = colorFor(m.change)
            const sp = sparkGeom(m.spark.map((p) => p.value))
            return (
              <div
                key={m.key}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '48px 1fr 60px 46px',
                  alignItems: 'center',
                  gap: 7,
                  padding: '4px 0',
                  borderBottom: '1px dashed var(--hair)',
                }}
              >
                <span style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink2)' }}>{m.label}</span>
                <span style={{ position: 'relative', height: 24 }}>
                  {sp && (
                    <svg viewBox="0 0 100 30" preserveAspectRatio="none" style={{ width: '100%', height: 24, display: 'block' }}>
                      <polyline points={sp.points} fill="none" stroke={col} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
                    </svg>
                  )}
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11.5, color: 'var(--ink)', textAlign: 'right' }}>
                  {fmtVal(m)}
                </span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: col, textAlign: 'right' }}>{fmtChg(m)}</span>
              </div>
            )
          })}
        </div>

        {/* THE CALL */}
        {v.hypotheses.length > 0 && (
          <div style={{ marginTop: 14 }}>
            <div style={{ fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '1.2px', color: 'var(--ink2)', marginBottom: 6 }}>
              THE CALL · 当日判断
            </div>
            {v.hypotheses.map((h, i) => (
              <div key={i} style={{ fontSize: 11.5, lineHeight: 1.5, color: 'var(--ink)', marginBottom: 5, textWrap: 'pretty' }}>
                <span style={{ color: 'var(--blue)', fontFamily: 'var(--mono)', marginRight: 5 }}>·</span>
                {h.ifThen}
              </div>
            ))}
          </div>
        )}

        {/* 可展开新闻 */}
        {b.news.length > 0 && (
          <>
            <button
              onClick={() => setExpanded(!expanded)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 7,
                width: '100%',
                marginTop: 12,
                border: '1px dashed var(--faint)',
                background: 'transparent',
                borderRadius: 7,
                padding: '6px 11px',
                cursor: 'pointer',
                color: 'var(--ink2)',
                fontFamily: 'var(--mono)',
                fontSize: 10.5,
              }}
            >
              <span style={{ transition: 'transform .2s', transform: expanded ? 'rotate(180deg)' : 'none' }}>▾</span>
              <span>{expanded ? '收起新闻' : `展开新闻分类 · ${b.news.length} 条`}</span>
            </button>
            {expanded &&
              b.news.map((n, i) => {
                const di = dirInfo(n.dir)
                return (
                  <div key={i} style={{ padding: '7px 0', borderBottom: '1px dashed var(--hair)' }}>
                    <div style={{ display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                      <span style={{ flex: 1, fontSize: 11, lineHeight: 1.4, color: 'var(--ink)' }}>{n.title}</span>
                      <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: di.col }}>{di.ch}</span>
                    </div>
                    <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--ink2)' }}>{n.source}</span>
                  </div>
                )
              })}
          </>
        )}

        <div
          style={{
            borderTop: '1px dashed var(--faint)',
            marginTop: 14,
            paddingTop: 11,
            textAlign: 'center',
            fontFamily: 'var(--mono)',
            fontSize: 9,
            color: 'var(--ink2)',
            letterSpacing: '.5px',
          }}
        >
          完整事实 / 解读 / 影响 / 复盘 见详情 ↗
        </div>
      </div>
    </div>
  )
}

function PeriodEmpty() {
  return (
    <div
      className="mb-card mb-punch"
      style={{ maxWidth: 640, margin: '8px auto', padding: 36, textAlign: 'center' }}
    >
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ink)', letterSpacing: '.5px' }}>
        区间聚合 · 待 V2 评估层
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink2)', lineHeight: 1.7, marginTop: 10 }}>
        月 / 季 / 半年 / 年的区间综述与命中率聚合,需要后端 V2 评估层(回填 + 打分)产出后接入。
        <br />
        目前请切回「日」查看逐日简报。
      </div>
    </div>
  )
}
