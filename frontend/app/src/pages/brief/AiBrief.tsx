import { useState } from 'react'
import type { ConsensusItem, Hypothesis, Impact, TaggedItem } from '../../types'
import { ASSET_CN, dirInfo, HORIZON_CN, PRED_DIR } from '../../lib/format'
import { highlightFigures } from '../../lib/highlight'
import { Card, SectionHead } from '../../components/Card'

// 小问号标注 + hover 说明。tooltip 用 absolute 锚定到本地 relative 容器(不受祖先 transform 影响,不会漂移)。
function InfoHint({ text }: { text: string }) {
  const [show, setShow] = useState(false)
  return (
    <span
      style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <span
        aria-label={text}
        style={{
          fontFamily: 'var(--mono)', fontSize: 8, lineHeight: 1, width: 12, height: 12,
          borderRadius: '50%', border: '1px solid var(--hair)', color: 'var(--ink2)',
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', cursor: 'help', userSelect: 'none',
        }}
      >
        ?
      </span>
      {show && (
        <span
          role="tooltip"
          style={{
            position: 'absolute', bottom: 'calc(100% + 6px)', right: 0, width: 196, zIndex: 30,
            background: 'var(--ink)', color: 'var(--paper)', fontFamily: 'var(--sans)', fontWeight: 400,
            fontSize: 10.5, lineHeight: 1.5, letterSpacing: 0, textAlign: 'left', whiteSpace: 'normal',
            padding: '7px 9px', borderRadius: 5, boxShadow: '0 6px 18px rgba(0,0,0,.2)', pointerEvents: 'none',
          }}
        >
          {text}
        </span>
      )}
    </span>
  )
}

function LayerHead({ label, zh, color }: { label: string; zh: string; color: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, margin: '15px 0 8px' }}>
      <span style={{ width: 8, height: 8, borderRadius: 2, background: color }} />
      <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, letterSpacing: '1.2px', color: 'var(--ink2)' }}>
        {label}
      </span>
      <span style={{ fontSize: 11, color: 'var(--ink)', fontWeight: 600 }}>{zh}</span>
    </div>
  )
}

// 主题标签 chip(事实/解读共用)。空标签不渲染。
function TagChip({ tag, mr = 0 }: { tag: string; mr?: number }) {
  if (!tag) return null
  return (
    <span
      style={{
        display: 'inline-block',
        flex: '0 0 auto',
        fontFamily: 'var(--mono)',
        fontSize: 10,
        color: 'var(--ink2)',
        background: 'var(--paper2)',
        border: '1px solid var(--faint)',
        borderRadius: 3,
        padding: '1px 6px',
        whiteSpace: 'nowrap',
        marginRight: mr,
      }}
    >
      {tag}
    </span>
  )
}

// 跨模型共识行(代码级投票,非某模型观点)。仅在 ≥2 模型(consensus 非空)时由 BriefPage 传入。
function ConsensusRow({ items }: { items: ConsensusItem[] }) {
  const order = ['up', 'down', 'flat'] as const
  return (
    <div
      style={{
        background: 'var(--paper2)',
        border: '1px solid var(--faint)',
        borderRadius: 5,
        padding: '8px 11px',
        marginBottom: 9,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '1px', color: 'var(--ink2)' }}>
          跨模型共识 · CONSENSUS
        </span>
        <InfoHint text="对每个资产,各模型方向投票的代码级汇总(不是某一个模型的观点):多数方向 + 认同票数 + 该方向均值信心;平票记为分歧(横盘)。" />
      </div>
      {items.map((c) => {
        const d = PRED_DIR[c.direction]
        return (
          <div
            key={c.asset}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '3px 0', fontSize: 11.5, flexWrap: 'wrap' }}
          >
            <span style={{ fontWeight: 600, color: 'var(--ink)', minWidth: 52 }}>{ASSET_CN[c.asset] ?? c.asset}</span>
            <span style={{ fontFamily: 'var(--mono)', color: d.col, fontWeight: 700 }}>
              {d.ch} {d.lab}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink2)' }}>
              {c.agree}/{c.n} 认同
              {c.meanConfidence > 0 && ` · 均值信心 ${Math.round(c.meanConfidence * 100)}%`}
            </span>
            <span style={{ marginLeft: 'auto', display: 'flex', gap: 7, fontFamily: 'var(--mono)', fontSize: 10 }}>
              {order.map((k) =>
                c.votes[k] ? (
                  <span key={k} style={{ color: PRED_DIR[k].col }}>
                    {PRED_DIR[k].ch}
                    {c.votes[k]}
                  </span>
                ) : null,
              )}
            </span>
          </div>
        )
      })}
    </div>
  )
}

function PredictionCard({ h }: { h: Hypothesis }) {
  const d = PRED_DIR[h.direction]
  return (
    <div style={{ background: 'var(--paper2)', borderRadius: 5, padding: '10px 11px', marginBottom: 7 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
        <span style={{ fontSize: 12.5, fontWeight: 700, color: 'var(--ink)' }}>{ASSET_CN[h.asset] ?? h.asset}</span>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 12.5, fontWeight: 700, color: d.col }}>
          {d.ch} {d.lab}
        </span>
        <span
          style={{
            fontFamily: 'var(--mono)',
            fontSize: 9.5,
            color: 'var(--ink2)',
            border: '1px solid var(--hair)',
            borderRadius: 3,
            padding: '1px 6px',
          }}
        >
          {HORIZON_CN[h.horizon]}
        </span>
        {h.confidence > 0 && (
          <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 9.5, color: 'var(--ink2)', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              信心 {Math.round(h.confidence * 100)}%
              <InfoHint text="AI 模型对本条预测的信心自评:它自己判断这个方向有多大把握会兑现。属模型主观估计、未经校准,不是真实概率,仅供同期横向参考。" />
            </span>
            <span style={{ width: 42, height: 4, borderRadius: 3, background: 'var(--hair)', overflow: 'hidden' }}>
              <span
                style={{ display: 'block', height: '100%', width: `${Math.round(h.confidence * 100)}%`, background: d.col }}
              />
            </span>
          </span>
        )}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.5, color: 'var(--ink)', fontWeight: 500, textWrap: 'pretty' }}>
        {h.ifThen}
      </div>
      <div style={{ fontSize: 10.5, lineHeight: 1.45, color: 'var(--ink2)', marginTop: 5, display: 'flex', gap: 6 }}>
        <span style={{ fontFamily: 'var(--mono)', color: 'var(--down)', flex: '0 0 auto' }}>✕ 失效</span>
        <span style={{ textWrap: 'pretty' }}>{h.invalidation}</span>
      </div>
      {h.keyFactors.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 7 }}>
          {h.keyFactors.map((f, i) => (
            <span
              key={i}
              style={{
                fontSize: 9.5,
                color: 'var(--ink2)',
                background: 'var(--paper)',
                border: '1px solid var(--hair)',
                borderRadius: 3,
                padding: '2px 6px',
              }}
            >
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

/** AI BRIEF 四层:FACTS(带标签数据条)/ INTERPRETATION(accent 竖线论述)/ HYPOTHESIS(预测卡)/ IMPACT。 */
export default function AiBrief({
  facts,
  reads,
  hypotheses,
  impacts,
  consensus = [],
}: {
  facts: TaggedItem[]
  reads: TaggedItem[]
  hypotheses: Hypothesis[]
  impacts: Impact[]
  consensus?: ConsensusItem[]
}) {
  return (
    <Card>
      <SectionHead label="AI BRIEF" zh="四层简报" margin="0 0 4px" />

      {/* 事实层:主题标签 + 高亮数字的可扫读数据条 */}
      <LayerHead label="FACTS" zh="事实层" color="var(--ink2)" />
      {facts.map((f, i) => (
        <div
          key={i}
          style={{ display: 'flex', gap: 9, alignItems: 'baseline', padding: '6px 0', borderBottom: '1px dashed var(--hair)' }}
        >
          <TagChip tag={f.tag} />
          <span style={{ fontSize: 12.5, lineHeight: 1.55, color: 'var(--ink)', textWrap: 'pretty' }}>
            {highlightFigures(f.text, f.figures)}
          </span>
        </div>
      ))}

      {/* 解读层:accent 竖线 + 主题标签 + 论述(判断的"嗓音") */}
      <LayerHead label="INTERPRETATION" zh="解读层" color="var(--accent)" />
      {reads.map((r, i) => (
        <div key={i} style={{ borderLeft: '2px solid var(--accent)', borderRadius: 0, padding: '1px 0 1px 12px', marginBottom: 11 }}>
          <TagChip tag={r.tag} mr={7} />
          <span style={{ fontSize: 12.5, lineHeight: 1.6, color: 'var(--ink)', textWrap: 'pretty' }}>
            {highlightFigures(r.text, r.figures)}
          </span>
        </div>
      ))}

      {/* 假设层 = 预测卡(多模型时上方先给跨模型共识) */}
      <LayerHead label="HYPOTHESIS" zh="假设层 · 预测" color="var(--blue)" />
      {consensus.length > 0 && <ConsensusRow items={consensus} />}
      {hypotheses.map((h, i) => (
        <PredictionCard key={i} h={h} />
      ))}

      {/* 影响层 */}
      <LayerHead label="IMPACT" zh="影响层" color="var(--up)" />
      {impacts.map((im, i) => {
        const di = dirInfo(im.dir)
        return (
          <div
            key={i}
            style={{ display: 'flex', alignItems: 'baseline', gap: 8, fontSize: 12, lineHeight: 1.5, marginBottom: 5 }}
          >
            <span
              style={{ fontFamily: 'var(--mono)', fontSize: 12, color: di.col, flex: '0 0 auto', width: 12, textAlign: 'center' }}
            >
              {di.ch}
            </span>
            <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink)', flex: '0 0 auto' }}>
              {im.asset}
            </span>
            <span style={{ color: 'var(--ink2)', textWrap: 'pretty' }}>{im.watch}</span>
          </div>
        )
      })}
    </Card>
  )
}
