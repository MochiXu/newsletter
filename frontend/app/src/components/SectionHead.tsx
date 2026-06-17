// 小票内各节的章节小标题:· LABEL  中文 -------(左小圆点 + 英文 mono + 中文 + 虚线)。
interface Props {
  label: string
  zh: string
  margin: string
}

export default function SectionHead({ label, zh, margin }: Props) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--accent)' }} />
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
      <span style={{ fontSize: 11, color: 'var(--ink2)' }}>{zh}</span>
      <span style={{ flex: 1, height: 1, borderTop: '1px dashed var(--faint)' }} />
    </div>
  )
}
