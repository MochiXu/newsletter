import type { CSSProperties, ReactNode } from 'react'

/** 暖纸卡片(mb-card 纹理 + 阴影)。punch=加撕齿边。 */
export function Card({
  children,
  punch = false,
  style,
}: {
  children: ReactNode
  punch?: boolean
  style?: CSSProperties
}) {
  return (
    <div className={'mb-card' + (punch ? ' mb-punch' : '')} style={{ padding: '20px 22px', ...style }}>
      {children}
    </div>
  )
}

/** 卡内小节标题行:● 圆点 + 英文 mono 标签 + 中文副标签 + 虚线填充。 */
export function SectionHead({ label, zh, margin = '0 0 12px' }: { label: string; zh: string; margin?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent)', flex: '0 0 auto' }} />
      <span
        style={{
          fontFamily: 'var(--mono)',
          fontSize: 10,
          letterSpacing: '1.6px',
          color: 'var(--ink2)',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </span>
      <span style={{ fontSize: 11, color: 'var(--ink2)', whiteSpace: 'nowrap' }}>{zh}</span>
      <span style={{ flex: 1, height: 1, borderTop: '1px dashed var(--faint)' }} />
    </div>
  )
}
