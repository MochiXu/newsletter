import { useEffect, useRef, type CSSProperties } from 'react'
import type { Brief, Route, Tweaks } from '../../types'
import { nav } from '../../lib/hooks'
import { modelLabel, resolveModel, viewOf } from '../../lib/format'
import { Card } from '../../components/Card'
import MarketData from './MarketData'
import PriceChart from './PriceChart'
import SignalsCard from './SignalsCard'
import NewsCard from './NewsCard'
import AiBrief from './AiBrief'
import ReviewCard from './ReviewCard'

interface Props {
  briefs: Brief[]
  model: string // 选中的模型 id(空 = 用各日主模型)
  route: Route
  tweaks: Tweaks
}

function ReturnBar({ from }: { from?: string; detail?: string }) {
  if (!from) return null
  const label = from === 'track' ? '‹ 命中率' : '‹ 时间线'
  const to = from === 'track' ? '#/track' : '#/timeline'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
      <button
        onClick={() => nav(to)}
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 11,
          color: 'var(--ink2)',
          background: 'transparent',
          border: '1px solid var(--hair)',
          borderRadius: 7,
          padding: '5px 11px',
          cursor: 'pointer',
        }}
      >
        {label}
      </button>
      <span style={{ flex: 1, borderTop: '1px dashed var(--faint)' }} />
    </div>
  )
}

function AggEmpty() {
  return (
    <Card punch style={{ maxWidth: 700, margin: '0 auto', padding: 36, textAlign: 'center' }}>
      <div style={{ fontFamily: 'var(--mono)', fontSize: 13, color: 'var(--ink)', letterSpacing: '.5px' }}>
        区间简报 · 待 V2 评估层
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink2)', lineHeight: 1.7, marginTop: 10 }}>
        月 / 季 / 年区间聚合简报需要后端先做出周期聚合与命中率评估(V2),目前仅产出逐日简报。
        <br />
        请切回「简报 / 时间线」查看逐日内容。
      </div>
    </Card>
  )
}

const colStyle = (basis: string): CSSProperties => ({
  flex: `${basis} 1 ${basis === '4' ? '350px' : '400px'}`,
  minWidth: basis === '4' ? 280 : 300,
  display: 'flex',
  flexDirection: 'column',
  gap: 18,
})

export default function BriefPage({ briefs, model, route, tweaks }: Props) {
  const receiptRef = useRef<HTMLDivElement>(null)
  const isAgg = !!route.date && route.gran && route.gran !== 'day'
  const idx = route.date ? Math.max(0, briefs.findIndex((b) => b.date === route.date)) : 0
  const b: Brief | undefined = briefs[idx]

  // 切换不同的一天:重放入场动画
  useEffect(() => {
    const el = receiptRef.current
    if (!el) return
    el.style.animation = 'none'
    void el.offsetWidth
    el.style.animation = 'receiptIn .42s cubic-bezier(.22,.61,.36,1) both'
  }, [idx, isAgg])

  if (isAgg) {
    return (
      <div style={{ marginTop: 24 }}>
        <ReturnBar from={route.from} />
        <AggEmpty />
      </div>
    )
  }
  if (!b) return null

  const view = viewOf(b, model) // 当前模型视图(缺失回退主模型 / 空视图)
  const activeModel = resolveModel(b, model)

  return (
    <div style={{ marginTop: 24 }}>
      <ReturnBar from={route.from} />
      <div ref={receiptRef} style={{ maxWidth: 1040, margin: '0 auto' }}>
        {/* 简报头 */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '2px', color: 'var(--ink2)' }}>
            MACRO BRIEF · {b.weekday} · 第 {b.issue} 刊 · {b.time}
          </div>
          <div
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 34,
              fontWeight: 600,
              letterSpacing: '1px',
              color: 'var(--ink)',
              marginTop: 6,
            }}
          >
            {b.date}
          </div>
          <div
            style={{
              fontSize: 17,
              fontWeight: 700,
              lineHeight: 1.5,
              color: 'var(--ink)',
              marginTop: 8,
              maxWidth: 620,
              textWrap: 'pretty',
            }}
          >
            {view.headline}
          </div>
        </div>

        {/* 双栏卡片 */}
        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-start' }}>
          <div style={colStyle('4')}>
            <MarketData metrics={b.metrics} showSparklines={tweaks.showSparklines} />
            <PriceChart priceSeries={b.priceSeries} />
            <SignalsCard signals={b.signals} regime={b.regime} />
            <NewsCard news={b.news} />
          </div>
          <div style={colStyle('5')}>
            <AiBrief
              facts={view.facts}
              reads={view.reads}
              hypotheses={view.hypotheses}
              impacts={view.impacts}
              consensus={b.consensus}
            />
            <ReviewCard reviews={b.reviews} />
          </div>
        </div>

        {/* 页脚 */}
        <div
          style={{
            borderTop: '1px dashed var(--faint)',
            marginTop: 18,
            paddingTop: 13,
            textAlign: 'center',
            fontFamily: 'var(--mono)',
            fontSize: 9.5,
            color: 'var(--ink2)',
            letterSpacing: '.6px',
          }}
        >
          本简报仅供研究 · 非投资建议 · NOT INVESTMENT ADVICE · GEN {modelLabel(activeModel) || 'LLM'}
        </div>
      </div>
    </div>
  )
}
