import { useEffect, useRef, type ReactNode } from 'react'
import type { Brief } from '../types'
import ReceiptFooter from './ReceiptFooter'

interface Props {
  brief: Brief
  model: string
  texture: boolean
  animKey: number // = activeIndex;变化时重放 receiptIn 入场动画
  children?: ReactNode // 内容区(指标 / 四层 / 复盘 / 新闻),F3 注入
}

// 扇贝撕边:顶部 / 底部一排白色半圆,模拟小票锯齿(yPx 决定圆心纵向位置)。
const scallop = (yPx: number) => ({
  height: 9,
  backgroundImage: `radial-gradient(circle 5px at 7px ${yPx}px,var(--bg) 99%,transparent 100%)`,
  backgroundRepeat: 'repeat-x',
  backgroundSize: '14px 9px',
})

/** 小票卡片容器:撕边 + 抬头 + headline + 内容区 + 页脚。activeIndex 变化时重放入场动画。 */
export default function Receipt({ brief, model, texture, animKey, children }: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const prevKey = useRef<number | null>(null)

  useEffect(() => {
    // 仅当切换到不同的一天才重放(首次挂载不放),沿用设计稿的 reflow 技巧。
    if (prevKey.current !== null && prevKey.current !== animKey && ref.current) {
      const el = ref.current
      el.style.animation = 'none'
      void el.offsetWidth // 强制 reflow
      el.style.animation = 'receiptIn .42s cubic-bezier(.22,.61,.36,1) both'
    }
    prevKey.current = animKey
  }, [animKey])

  return (
    <div
      ref={ref}
      style={{ position: 'relative', width: 'min(442px,100%)', background: 'var(--paper)', boxShadow: 'var(--shadow)' }}
    >
      {texture && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            backgroundImage: 'radial-gradient(var(--faint) .5px,transparent .6px)',
            backgroundSize: '5px 5px',
            opacity: 0.28,
          }}
        />
      )}

      <div style={scallop(0)} />

      <div style={{ position: 'relative', padding: '14px 28px 4px' }}>
        {/* 抬头 */}
        <div style={{ textAlign: 'center', paddingTop: 4 }}>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10, letterSpacing: '3px', color: 'var(--ink2)' }}>
            宏观简报 · MACRO BRIEF
          </div>
          <div
            style={{
              fontFamily: 'var(--mono)',
              fontSize: 28,
              fontWeight: 600,
              letterSpacing: '1px',
              color: 'var(--ink)',
              marginTop: 7,
            }}
          >
            {brief.date}
          </div>
          <div style={{ fontFamily: 'var(--mono)', fontSize: 10.5, color: 'var(--ink2)', marginTop: 6 }}>
            {brief.weekday} · 第 {brief.issue} 刊 · {brief.time}
          </div>
        </div>

        <div style={{ borderTop: '1px dashed var(--faint)', margin: '14px 0' }} />

        {/* 一句话标题 */}
        <div style={{ fontSize: 14.5, lineHeight: 1.55, fontWeight: 600, color: 'var(--ink)', textWrap: 'pretty' }}>
          {brief.headline}
        </div>

        {/* 内容区(F3 注入:MARKET DATA / AI BRIEF / REVIEW / NEWS) */}
        {children}

        <ReceiptFooter date={brief.date} model={model} />
      </div>

      <div style={scallop(9)} />
    </div>
  )
}
