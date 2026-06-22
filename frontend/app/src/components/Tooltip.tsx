import { useRef, useState, type CSSProperties, type MouseEvent as ReactMouseEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

// 统一 hover 提示:内容 portal 到 #mb-root(非 transform 祖先)用 fixed 定位,
// 故①不被 mb-punch 的 mask 裁剪 ②不受 receiptIn 残留 transform 影响而漂移。
// 触发元素在边缘时水平夹取、靠顶时翻到下方。
const BOX: CSSProperties = {
  position: 'fixed',
  zIndex: 1000,
  background: 'var(--ink)',
  color: 'var(--paper)',
  fontFamily: 'var(--sans)',
  fontWeight: 400,
  fontSize: 10.5,
  lineHeight: 1.5,
  letterSpacing: 0,
  textAlign: 'left',
  whiteSpace: 'normal',
  padding: '7px 9px',
  borderRadius: 5,
  boxShadow: '0 6px 18px rgba(0,0,0,.22)',
  pointerEvents: 'none',
}

export function Tooltip({
  content,
  children,
  width = 210,
  style,
}: {
  content: ReactNode
  children: ReactNode
  width?: number
  style?: CSSProperties
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const [p, setP] = useState<{ x: number; y: number; below: boolean } | null>(null)

  const show = (e: ReactMouseEvent) => {
    const el = ref.current
    if (!el) return
    const half = width / 2
    const clampX = (x: number) => Math.min(Math.max(x, half + 8), window.innerWidth - half - 8)
    const rects = el.getClientRects()
    if (rects.length > 1) {
      // 词条跨行(inline 换行):元素 bounding rect 会横跨整行导致居中 → 改用鼠标位置
      const below = e.clientY < 90
      setP({ x: clampX(e.clientX), y: below ? e.clientY + 16 : e.clientY - 14, below })
    } else {
      const r = rects[0] ?? el.getBoundingClientRect()
      const below = r.top < 90 // 太靠顶 → 翻到下方
      setP({ x: clampX(r.left + r.width / 2), y: below ? r.bottom + 8 : r.top - 8, below })
    }
  }

  const root = typeof document !== 'undefined' ? document.getElementById('mb-root') : null

  return (
    <span
      ref={ref}
      onMouseEnter={show}
      onMouseLeave={() => setP(null)}
      style={{ display: 'inline-flex', alignItems: 'center', ...style }}
    >
      {children}
      {p &&
        root &&
        createPortal(
          <span
            role="tooltip"
            style={{
              ...BOX,
              width,
              left: p.x,
              top: p.y,
              transform: p.below ? 'translate(-50%, 0)' : 'translate(-50%, -100%)',
            }}
          >
            {content}
          </span>,
          root,
        )}
    </span>
  )
}
