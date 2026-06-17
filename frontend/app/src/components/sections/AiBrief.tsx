import type { Brief } from '../../types'
import { dirInfo } from '../../lib/tone'
import SectionHead from '../SectionHead'

interface Props {
  brief: Brief
}

// 每层小标题:■ 图标(层色) + 英文 mono + 中文粗体。
function LayerHead({ label, zh, color, margin }: { label: string; zh: string; color: string; margin: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, margin }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '1.2px', color: 'var(--ink2)' }}>
        {label}
      </span>
      <span style={{ fontSize: 11, color: 'var(--ink)', fontWeight: 600 }}>{zh}</span>
    </div>
  )
}

// 事实层 / 解读层的要点行(bullet 字形与颜色不同)。
function Bullet({ mark, markColor, text }: { mark: string; markColor: string; text: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, fontSize: 12.5, lineHeight: 1.55, color: 'var(--ink)', marginBottom: 5 }}>
      <span style={{ color: markColor, flex: '0 0 auto', fontFamily: 'var(--mono)' }}>{mark}</span>
      <span style={{ textWrap: 'pretty' }}>{text}</span>
    </div>
  )
}

/** 四层 AI 简报:FACTS / INTERPRETATION / HYPOTHESIS / IMPACT。 */
export default function AiBrief({ brief }: Props) {
  return (
    <>
      <SectionHead label="AI BRIEF" zh="四层简报" margin="22px 0 4px" />

      {/* 事实层 */}
      <LayerHead label="FACTS" zh="事实层" color="var(--ink2)" margin="14px 0 7px" />
      {brief.facts.map((f, i) => (
        <Bullet key={i} mark="›" markColor="var(--ink2)" text={f} />
      ))}

      {/* 解读层 */}
      <LayerHead label="INTERPRETATION" zh="解读层" color="var(--accent)" margin="15px 0 7px" />
      {brief.reads.map((r, i) => (
        <Bullet key={i} mark="—" markColor="var(--accent)" text={r} />
      ))}

      {/* 假设层 */}
      <LayerHead label="HYPOTHESIS" zh="假设层" color="var(--blue)" margin="15px 0 7px" />
      {brief.hypotheses.map((h, i) => (
        <div key={i} style={{ background: 'var(--paper2)', borderRadius: 4, padding: '9px 11px', marginBottom: 6 }}>
          <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--ink)', fontWeight: 500, textWrap: 'pretty' }}>
            {h.ifThen}
          </div>
          <div
            style={{
              fontSize: 10.5,
              lineHeight: 1.45,
              color: 'var(--ink2)',
              marginTop: 5,
              display: 'flex',
              gap: 6,
            }}
          >
            <span style={{ fontFamily: 'var(--mono)', color: 'var(--down)', flex: '0 0 auto' }}>✕ 失效</span>
            <span style={{ textWrap: 'pretty' }}>{h.invalidation}</span>
          </div>
        </div>
      ))}

      {/* 影响层 */}
      <LayerHead label="IMPACT" zh="影响层" color="var(--up)" margin="15px 0 7px" />
      {brief.impacts.map((im, i) => {
        const di = dirInfo(im.dir)
        return (
          <div
            key={i}
            style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12, lineHeight: 1.5, marginBottom: 5 }}
          >
            <span style={{ fontFamily: 'var(--mono)', fontSize: 12, color: di.col, flex: '0 0 auto', width: 12, textAlign: 'center' }}>
              {di.ch}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)', flex: '0 0 auto' }}>
              {im.asset}
            </span>
            <span style={{ color: 'var(--ink2)', textWrap: 'pretty' }}>{im.watch}</span>
          </div>
        )
      })}
    </>
  )
}
